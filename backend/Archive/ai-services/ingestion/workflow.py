"""
Requirement 1, step 4: the state machine that ties ingestion, validation,
and AI assessment together and enforces the human review gate.

Design decision, stated explicitly because it matters for audit and for
anyone reading this later: deterministic validation finding ANY issue
always results in status REVIEW_REQUIRED. The AI assessment's own
`human_review_required` opinion is captured and shown to the reviewer,
but it never overrides the pause — only a human action (GO_AHEAD or
CORRECT_DATA) can move a session out of REVIEW_REQUIRED. This is the
literal, safe reading of "AI must not automatically approve problematic
data": the AI is never in the code path that sets a session to APPROVED.

Storage is in-memory for this requirement — a real deployment would back
this with the workflow database, but nothing about the interface here
assumes that; SESSIONS could become a repository-backed store later
without changing start_ingestion/get_session/submit_review's signatures.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import pandas as pd

from ingestion.ai_assessment import AIAssessment, AssessmentError, assess
from ingestion.ingest import IngestionError, ingest
from ingestion.validation import SchemaSnapshot, ValidationReport, run_validation

logger = logging.getLogger("onerecon.ingestion.workflow")


class IngestionStatus(str, Enum):
    CLEAN = "CLEAN"                    # no deterministic issues, ready to continue
    REVIEW_REQUIRED = "REVIEW_REQUIRED"  # paused, waiting for a human decision
    APPROVED = "APPROVED"              # human said GO_AHEAD despite known issues
    FAILED = "FAILED"                  # ingestion itself could not complete


class ReviewAction(str, Enum):
    GO_AHEAD = "GO_AHEAD"
    CORRECT_DATA = "CORRECT_DATA"


class WorkflowError(Exception):
    """Raised for invalid session operations (unknown session, wrong
    state for the requested action, malformed correction payload)."""


@dataclass
class AuditEvent:
    timestamp: str
    actor: str
    action: str
    details: dict = field(default_factory=dict)


@dataclass
class IngestionSession:
    session_id: str
    status: IngestionStatus
    df: pd.DataFrame
    metadata: dict
    validation_report: ValidationReport | None = None
    ai_assessment: AIAssessment | None = None
    reference_schema: SchemaSnapshot | None = None
    business_rules_path: str | None = None
    outlier_field: str = "Amount"
    outlier_group_by: str | None = "Currency"
    key_fields: list[str] | None = None
    format_min_dominant_ratio: float = 0.8
    error: str | None = None
    audit_log: list[AuditEvent] = field(default_factory=list)

    def log(self, actor: str, action: str, **details) -> None:
        self.audit_log.append(
            AuditEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                actor=actor,
                action=action,
                details=details,
            )
        )

    def to_summary(self) -> dict:
        """A JSON-safe view for API responses — never includes the raw df."""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "metadata": self.metadata,
            "validation_report": self.validation_report.to_dict() if self.validation_report else None,
            "ai_assessment": (
                {
                    "issues": self.ai_assessment.issues,
                    "overall_severity": self.ai_assessment.overall_severity,
                    "human_review_required": self.ai_assessment.human_review_required,
                    "summary": self.ai_assessment.summary,
                }
                if self.ai_assessment
                else None
            ),
            "error": self.error,
            "audit_log": [vars(e) for e in self.audit_log],
        }


# In-memory session store for this requirement's scope.
SESSIONS: dict[str, IngestionSession] = {}


def _validate_and_assess(session: IngestionSession, actor: str) -> None:
    """Shared by start_ingestion and the REVALIDATE path after a correction."""
    report = run_validation(
        session.df,
        business_rules_path=session.business_rules_path,
        reference_schema=session.reference_schema,
        outlier_field=session.outlier_field,
        outlier_group_by=session.outlier_group_by,
        key_fields=session.key_fields,
        format_min_dominant_ratio=session.format_min_dominant_ratio,
    )
    session.validation_report = report
    session.log(actor, "validation.completed", has_issues=report.has_issues)

    if not report.has_issues:
        session.status = IngestionStatus.CLEAN
        session.ai_assessment = None
        session.log(actor, "status.set", status="CLEAN", reason="no deterministic issues found")
        return

    try:
        session.ai_assessment = assess(report, session.df, session.metadata)
        session.log(
            actor,
            "ai_assessment.completed",
            overall_severity=session.ai_assessment.overall_severity,
            ai_human_review_required=session.ai_assessment.human_review_required,
        )
    except AssessmentError as exc:
        logger.warning("AI assessment unavailable, pausing on deterministic findings alone: %s", exc)
        session.ai_assessment = None
        session.log(actor, "ai_assessment.failed", reason=str(exc))

    # Deterministic issues found -> always pause, regardless of the AI's
    # own opinion (see module docstring for why).
    session.status = IngestionStatus.REVIEW_REQUIRED
    session.log(actor, "status.set", status="REVIEW_REQUIRED", reason="deterministic issues found")


def start_ingestion(
    source: str,
    business_rules_path: str | Path | None = None,
    reference_schema: SchemaSnapshot | None = None,
    outlier_field: str = "Amount",
    outlier_group_by: str | None = "Currency",
    key_fields: list[str] | None = None,
    format_min_dominant_ratio: float = 0.8,
    actor: str = "system",
    **ingest_kwargs,
) -> IngestionSession:
    """
    source: a file path or a full URL — its format (CSV/Excel/JSON/XML/API)
    is detected automatically, never declared by the caller.
    key_fields: columns that must be unique; if omitted, duplicate
    detection auto-detects likely identifier columns by name pattern and
    uniqueness ratio instead of checking every "id"/"key"-named column
    blindly (see check_duplicates for why that distinction matters).
    ingest_kwargs: forwarded to ingest() — sheet_name for Excel;
    json_data_key for JSON; xml_record_tag for XML; page_param/
    per_page_param/per_page/data_key/total_pages_key for API.
    Irrelevant kwargs for the detected format are simply unused.
    """
    session_id = str(uuid.uuid4())

    try:
        result = ingest(source, **ingest_kwargs)
    except IngestionError as exc:
        session = IngestionSession(
            session_id=session_id,
            status=IngestionStatus.FAILED,
            df=pd.DataFrame(),
            metadata={"source": source},
            error=str(exc),
        )
        session.log(actor, "ingestion.failed", reason=str(exc))
        SESSIONS[session_id] = session
        logger.error("Ingestion failed for session %s: %s", session_id, exc)
        return session

    session = IngestionSession(
        session_id=session_id,
        status=IngestionStatus.CLEAN,  # provisional, set properly below
        df=result.df,
        metadata=result.metadata,
        reference_schema=reference_schema,
        business_rules_path=str(business_rules_path) if business_rules_path else None,
        outlier_field=outlier_field,
        outlier_group_by=outlier_group_by,
        key_fields=key_fields,
        format_min_dominant_ratio=format_min_dominant_ratio,
    )
    session.log(actor, "ingestion.completed", **result.metadata)
    SESSIONS[session_id] = session

    _validate_and_assess(session, actor)
    logger.info("start_ingestion: session=%s final_status=%s", session_id, session.status.value)
    return session


def get_session(session_id: str) -> IngestionSession:
    session = SESSIONS.get(session_id)
    if session is None:
        raise WorkflowError(f"No such ingestion session: {session_id}")
    return session


def _apply_correction(
    df: pd.DataFrame,
    patches: list[dict] | None,
    replacement_records: list[dict] | None,
) -> pd.DataFrame:
    if replacement_records is not None:
        return pd.DataFrame(replacement_records)

    if not patches:
        raise WorkflowError("CORRECT_DATA requires either 'patches' or 'replacement_records'")

    corrected = df.copy()
    for patch in patches:
        row, field_name, value = patch.get("row"), patch.get("field"), patch.get("value")
        if row is None or field_name is None:
            raise WorkflowError(f"Malformed patch (needs row and field): {patch}")
        if row not in corrected.index:
            raise WorkflowError(f"Patch references row {row}, which does not exist")
        if field_name not in corrected.columns:
            raise WorkflowError(f"Patch references unknown field {field_name!r}")
        corrected.at[row, field_name] = value
    return corrected


def submit_review(
    session_id: str,
    action: ReviewAction,
    actor: str = "user",
    patches: list[dict] | None = None,
    replacement_records: list[dict] | None = None,
) -> IngestionSession:
    session = get_session(session_id)

    if session.status != IngestionStatus.REVIEW_REQUIRED:
        raise WorkflowError(
            f"Session {session_id} is not awaiting review (status={session.status.value})"
        )

    if action == ReviewAction.GO_AHEAD:
        session.status = IngestionStatus.APPROVED
        session.log(actor, "review.go_ahead", note="approved with known issues, no data changed")
        logger.info("submit_review: session=%s approved via GO_AHEAD", session_id)
        return session

    if action == ReviewAction.CORRECT_DATA:
        before_rows = len(session.df)
        session.df = _apply_correction(session.df, patches, replacement_records)
        session.log(
            actor,
            "review.correct_data",
            rows_before=before_rows,
            rows_after=len(session.df),
            patch_count=len(patches) if patches else None,
            full_replacement=replacement_records is not None,
        )
        logger.info("submit_review: session=%s correction applied, revalidating", session_id)
        _validate_and_assess(session, actor)
        return session

    raise WorkflowError(f"Unknown review action: {action!r}")