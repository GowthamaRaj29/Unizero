"""
Requirement 1, step 3: AI assessment.

Takes the deterministic ValidationReport — never the raw dataset — and
asks the LLM to interpret what it means: which issues actually matter,
how severe they are, and whether a human needs to look before continuing.

Hard constraints, enforced by what this module does and does not do:
  - It only ever READS the validation report and a small set of samples.
    It has no code path that writes to or mutates the dataframe.
  - It never sets a workflow's status itself — it returns an opinion
    (`human_review_required`), and the workflow state machine (workflow.py)
    is what actually decides and enforces the pause. This module could
    return the wrong answer and the system would still not silently
    proceed on bad data, because the gate lives elsewhere.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

import anthropic
import pandas as pd
from gemini_client import GeminiAPIError, generate_text, normalize_model_json

from ingestion.validation import ValidationReport

logger = logging.getLogger("onerecon.ingestion.ai_assessment")

MODEL = os.environ.get("GEMINI_ASSESSMENT_MODEL", "gemini-3.5-flash")
MAX_EXAMPLES_PER_ISSUE_TYPE = 5

_SYSTEM_PROMPT = """You are a data-quality assessor for a bank's reconciliation system. You will \
receive a SUMMARY of deterministic validation findings for one data load — counts and a small \
number of examples, never the full dataset — plus basic source metadata.

Your job is to interpret this evidence, not to re-derive it: decide which findings are likely to \
be genuine data-quality problems versus noise, assign a severity, and say plainly whether a human \
must review before this data is used for reconciliation.

You must NOT invent issues that are not represented in the evidence, and you must NOT suggest or \
imply that the data should be modified or auto-corrected — flagging and explaining is your only \
job. A human always makes the final call.

Respond with strict JSON only, matching this shape:
{
  "issues": [
    {"type": "<null|dtype|format|duplicate|outlier|cross_field|business_rule|schema_drift>", "severity": "high"|"medium"|"low", \
"summary": "<one sentence>", "explanation": "<why this matters for reconciliation, one or two sentences>"}
  ],
  "overall_severity": "high"|"medium"|"low"|"none",
  "human_review_required": true|false,
  "summary": "<one paragraph, plain language, for the Investigator screen>"
}"""


class AssessmentError(Exception):
    """Raised on any failure calling the AI assessment — callers must
    treat this as 'assessment unavailable' and fail toward requiring
    human review, never toward silently continuing."""


@dataclass
class AIAssessment:
    issues: list[dict] = field(default_factory=list)
    overall_severity: str = "none"
    human_review_required: bool = False
    summary: str = ""
    raw_response: str = ""


def summarize_for_ai(
    report: ValidationReport,
    df: pd.DataFrame,
    source_metadata: dict,
    max_examples: int = MAX_EXAMPLES_PER_ISSUE_TYPE,
) -> dict:
    """
    Builds the compact payload actually sent to the model. This is the
    control point for "don't send the whole dataset" — it sends counts
    and a handful of examples per issue type, never the dataframe itself.
    """
    # Cross-field validation is intentionally deferred in validation.py.
    # Keep the payload schema stable for assessment clients without requiring
    # a field that ValidationReport does not provide.
    cross_field_issues = getattr(report, "cross_field_issues", [])

    return {
        "source": {
            "source_type": source_metadata.get("source_type"),
            "row_count": source_metadata.get("row_count"),
            "columns": source_metadata.get("columns"),
        },
        "null_issues": {
            "count": len(report.null_issues),
            "examples": report.null_issues[:max_examples],
        },
        "dtype_issues": {
            "count": len(report.dtype_issues),
            "examples": report.dtype_issues[:max_examples],
        },
        "format_issues": {
            "count": len(report.format_issues),
            "examples": report.format_issues[:max_examples],
        },
        "duplicate_issues": {
            "count": len(report.duplicate_issues),
            "examples": report.duplicate_issues[:max_examples],
        },
        "outliers": {
            "count": len(report.outliers),
            "examples": report.outliers[:max_examples],
        },
        "cross_field_issues": {
            "count": len(cross_field_issues),
            "examples": cross_field_issues[:max_examples],
        },
        "business_rule_violations": {
            "count": len(report.business_rule_violations),
            "examples": report.business_rule_violations[:max_examples],
        },
        "schema_drift": report.schema_drift,
    }


def assess(
    report: ValidationReport,
    df: pd.DataFrame,
    source_metadata: dict,
    client: anthropic.Anthropic | None = None,
) -> AIAssessment:
    if not report.has_issues:
        # No deterministic issues at all — skip the AI call entirely.
        # This is also a cost/latency optimization: the AI is only ever
        # invoked when there is something to interpret.
        logger.info("assess: no deterministic issues, skipping AI call")
        return AIAssessment(overall_severity="none", human_review_required=False, summary="No issues detected.")

    payload = summarize_for_ai(report, df, source_metadata)

    try:
        if client is not None:
            response = client.messages.create(
                model=MODEL,
                max_tokens=800,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(payload)}],
            )
            raw_text = "".join(block.text for block in response.content if block.type == "text")
        else:
            raw_text = generate_text(_SYSTEM_PROMPT, json.dumps(payload), 800)
    except anthropic.APIError as exc:
        logger.error("AI assessment call failed: %s", exc)
        raise AssessmentError(f"AI assessment call failed: {exc}") from exc
    except GeminiAPIError as exc:
        logger.error("Gemini assessment call failed: %s", exc)
        raise AssessmentError(f"AI assessment call failed: {exc}") from exc
    try:
        parsed = json.loads(normalize_model_json(raw_text))
    except json.JSONDecodeError:
        logger.warning("Non-JSON response from assessment model: %r", raw_text)
        # Fail toward requiring review — never toward silently continuing.
        return AIAssessment(
            issues=[],
            overall_severity="medium",
            human_review_required=True,
            summary="AI response could not be parsed — defaulting to human review.",
            raw_response=raw_text,
        )

    assessment = AIAssessment(
        issues=parsed.get("issues", []),
        overall_severity=parsed.get("overall_severity", "medium"),
        human_review_required=parsed.get("human_review_required", True),
        summary=parsed.get("summary", ""),
        raw_response=raw_text,
    )
    logger.info(
        "assess: severity=%s human_review_required=%s issues=%d",
        assessment.overall_severity, assessment.human_review_required, len(assessment.issues),
    )
    return assessment