"""
AI services — runs standalone on its own port so the backend team can
develop against it before their own service is ready, and so it stays a
stateless, independently testable component in production too.

Run from any directory: uvicorn app:app --app-dir ai-services --port 8000 --reload
"""
from __future__ import annotations
import logging
import os
import tempfile
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from break_management.api import router as break_management_router
from explain import BreakRecord, ExplainServiceError, explain_break
from field_mapping.auto_mapping import (
    MappingConfig,
    compute_field_mappings_for_sessions,
    result_to_dict,
)
from field_mapping.crosswalk import CrosswalkError
from field_mapping.field_comparison_view import FieldComparisonError
from field_mapping.manual_mapping import (
    COMMON,
    ManualMappingError,
    apply_mapping_file,
    create_mapping_session,
    decide_mapping,
    get_mapping_session,
    reset_to_ai,
    set_manual_mapping,
    undo_last,
)
from field_mapping.mapping_validation import preview_mapping, validate_mapping_session
from ingestion.workflow import (
    IngestionSession,
    IngestionStatus,
    ReviewAction,
    WorkflowError,
    get_session,
    start_ingestion,
    submit_review,
)
from mapping import FieldProfile, classify_confidence, suggest_mappings
from rules_engine import RulesFileError, apply_rules, detect_statistical_anomalies, load_rules

load_dotenv(Path(__file__).with_name(".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("Unizero.app")

app = FastAPI(title="Unizero AI services")

# ---------- Requirement 6: Break Management ----------
# Deterministic reconciliation (reconciliation/matcher.py) + AI RCA,
# prioritization, lineage, and human-in-the-loop status (break_management/).
# See break_management/api.py; nothing above this line is touched.
app.include_router(break_management_router)


# ---------- /validate ----------

class ValidateRequest(BaseModel):
    rules_file_path: str
    records: list[dict]
    anomaly_field: str = "Amount"
    anomaly_group_by: str | None = "Currency"


class ValidateResponse(BaseModel):
    rule_violations: list[dict]
    statistical_anomalies: list[dict]
    requires_human_review: bool


@app.post("/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest) -> ValidateResponse:
    if not req.records:
        raise HTTPException(status_code=400, detail="records must not be empty")

    try:
        rules = load_rules(req.rules_file_path)
    except RulesFileError as exc:
        logger.error("validate: rules file error: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        df = pd.DataFrame(req.records)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse records: {exc}") from exc

    violations = apply_rules(df, rules)
    anomalies = detect_statistical_anomalies(df, req.anomaly_field, req.anomaly_group_by)
    return ValidateResponse(
        rule_violations=violations,
        statistical_anomalies=anomalies,
        requires_human_review=bool(violations or anomalies),
    )


# ---------- /map-fields ----------

class FieldProfileIn(BaseModel):
    name: str
    samples: list


class MapFieldsRequest(BaseModel):
    source_fields: list[FieldProfileIn]
    target_fields: list[FieldProfileIn]
    min_score: float = 0.35


class MappingCandidateOut(BaseModel):
    source_field: str
    target_field: str
    name_score: float
    value_score: float
    combined_score: float
    tier: str


@app.post("/map-fields", response_model=list[MappingCandidateOut])
def map_fields(req: MapFieldsRequest) -> list[MappingCandidateOut]:
    if not req.source_fields or not req.target_fields:
        raise HTTPException(
            status_code=400, detail="source_fields and target_fields must both be non-empty"
        )

    source = [FieldProfile(f.name, f.samples) for f in req.source_fields]
    target = [FieldProfile(f.name, f.samples) for f in req.target_fields]
    candidates = suggest_mappings(source, target, req.min_score)
    return [
        MappingCandidateOut(
            source_field=c.source_field,
            target_field=c.target_field,
            name_score=round(c.name_score, 3),
            value_score=round(c.value_score, 3),
            combined_score=round(c.combined_score, 3),
            tier=classify_confidence(c.combined_score),
        )
        for c in candidates
    ]


# ---------- /explain-break ----------

class ExplainRequest(BaseModel):
    workflow_name: str
    source_a: str
    source_b: str
    field: str
    key: str
    value_a: object
    value_b: object
    mapping_context: dict = {}


class ExplainResponse(BaseModel):
    root_cause: str
    confidence: str
    suggested_action: str


@app.post("/explain-break", response_model=ExplainResponse)
def explain(req: ExplainRequest) -> ExplainResponse:
    br = BreakRecord(
        workflow_name=req.workflow_name,
        source_a=req.source_a,
        source_b=req.source_b,
        field=req.field,
        key=req.key,
        value_a=req.value_a,
        value_b=req.value_b,
        mapping_context=req.mapping_context,
    )
    try:
        result = explain_break(br)
    except ExplainServiceError as exc:
        logger.error("explain-break failed for key=%s: %s", req.key, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ExplainResponse(
        root_cause=result.root_cause,
        confidence=result.confidence,
        suggested_action=result.suggested_action,
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "Unizero-ai-services",
        "ai_provider": "gemini" if os.environ.get("GEMINI_API_KEY") else "anthropic",
    }


# ---------- Requirement 1: ingestion + human review gate ----------
#
# These endpoints wrap ingestion/workflow.py. They intentionally return
# session.to_summary() rather than the session object itself — that view
# is JSON-safe and never includes the raw dataframe. Note there is no
# auth/role check here yet: Requirement 1 is ingestion + validation only,
# maker-checker (Investigator vs Approver) and RBAC are separate,
# not-yet-built requirements.

class StartIngestionRequest(BaseModel):
    source: str  # a file path or a full URL — format is auto-detected
    sheet_name: str | int = 0
    json_data_key: str | None = None
    xml_record_tag: str | None = None
    page_param: str = "page"
    per_page_param: str = "per_page"
    per_page: int = 500
    data_key: str = "data"
    total_pages_key: str = "total_pages"
    business_rules_path: str | None = None
    outlier_field: str = "Amount"
    outlier_group_by: str | None = "Currency"
    key_fields: list[str] | None = None
    format_min_dominant_ratio: float = 0.8


class ReviewRequest(BaseModel):
    action: str  # "GO_AHEAD" | "CORRECT_DATA"
    actor: str = "user"
    patches: list[dict] | None = None
    replacement_records: list[dict] | None = None


@app.post("/ingestion/start")
def ingestion_start(req: StartIngestionRequest) -> dict:
    try:
        session = start_ingestion(
            source=req.source,
            business_rules_path=req.business_rules_path,
            outlier_field=req.outlier_field,
            outlier_group_by=req.outlier_group_by,
            key_fields=req.key_fields,
            format_min_dominant_ratio=req.format_min_dominant_ratio,
            sheet_name=req.sheet_name,
            json_data_key=req.json_data_key,
            xml_record_tag=req.xml_record_tag,
            page_param=req.page_param,
            per_page_param=req.per_page_param,
            per_page=req.per_page,
            data_key=req.data_key,
            total_pages_key=req.total_pages_key,
        )
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_summary()


@app.post("/ingestion/upload")
async def ingestion_upload(
    source_file: UploadFile = File(...),
    business_rules_path: str | None = Form(None),
) -> dict:
    """Ingest a file selected in the browser without exposing local paths."""
    suffix = Path(source_file.filename or "").suffix
    temporary_path = None
    try:
        content = await source_file.read()
        if not content:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary_file:
            temporary_file.write(content)
            temporary_path = temporary_file.name

        session = start_ingestion(
            source=temporary_path,
            business_rules_path=business_rules_path or None,
        )
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temporary_path:
            try:
                os.unlink(temporary_path)
            except OSError:
                logger.warning("Could not remove temporary upload %s", temporary_path)

    return session.to_summary()


@app.get("/ingestion/{session_id}")
def ingestion_status(session_id: str) -> dict:
    try:
        session = get_session(session_id)
    except WorkflowError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return session.to_summary()


@app.post("/ingestion/{session_id}/review")
def ingestion_review(session_id: str, req: ReviewRequest) -> dict:
    try:
        action = ReviewAction(req.action)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"action must be GO_AHEAD or CORRECT_DATA, got {req.action!r}"
        ) from exc

    try:
        session = submit_review(
            session_id,
            action,
            actor=req.actor,
            patches=req.patches,
            replacement_records=req.replacement_records,
        )
    except WorkflowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_summary()


# ---------- Requirement 2, step 2: Automated Field Mapping ----------
#
# Reuses the Field Comparison View (which itself reuses the already-
# ingested session DataFrames) for field metadata -- this endpoint never
# re-reads a source file. See field_mapping/auto_mapping.py for the
# crosswalk/embedding scoring and YELLOW reconciliation-field logic.

class AutoMapRequest(BaseModel):
    session_ids: list[str]
    crosswalk_path: str | None = None
    green_threshold: float = 0.95
    light_green_threshold: float = 0.75
    semantic_weight: float = 0.6
    value_weight: float = 0.4
    ambiguous_gap: float = 0.05
    yellow_min_value_score: float = 0.5


@app.post("/field-mapping/auto")
def auto_map_fields(req: AutoMapRequest) -> dict:
    config = MappingConfig(
        green_threshold=req.green_threshold,
        light_green_threshold=req.light_green_threshold,
        semantic_weight=req.semantic_weight,
        value_weight=req.value_weight,
        ambiguous_gap=req.ambiguous_gap,
        yellow_min_value_score=req.yellow_min_value_score,
    )
    try:
        result = compute_field_mappings_for_sessions(
            req.session_ids, crosswalk_path=req.crosswalk_path, config=config
        )
    except (FieldComparisonError, CrosswalkError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result_to_dict(result)

# ---------- Requirement 2, step 3: Manual Field Mapping Override ----------
#
# Backend/API surface only -- the drag/drop interaction itself belongs to
# the frontend; everything below is the state it drives. Human decisions
# are authoritative: no endpoint here re-runs the AI mapper over an
# existing override, and the original AI recommendation is preserved
# separately on every entry (see field_mapping/manual_mapping.py).
#
# None of these endpoints perform reconciliation or root-cause analysis.

class CreateMappingSessionRequest(BaseModel):
    session_ids: list[str]
    crosswalk_path: str | None = None
    green_threshold: float = 0.95
    light_green_threshold: float = 0.75
    semantic_weight: float = 0.6
    value_weight: float = 0.4
    ambiguous_gap: float = 0.05
    yellow_min_value_score: float = 0.5
    actor: str = "user"


class ManualMappingRequest(BaseModel):
    source: str
    field: str
    matched_source: str
    matched_field: str
    category: str = COMMON  # COMMON | POTENTIAL | UNCOMMON
    actor: str = "user"
    note: str | None = None


class DecisionRequest(BaseModel):
    key: str
    decision: str  # ACCEPT | REJECT | KEEP_POTENTIAL
    matched_field: str | None = None
    actor: str = "user"
    note: str | None = None


class MappingFileRequest(BaseModel):
    content: str  # raw text, e.g. "Counterparty Code: 1 -> Client Type: Current Ac - Retail"
    source: str
    matched_source: str
    category: str = COMMON
    actor: str = "user"


class ResetRequest(BaseModel):
    key: str
    actor: str = "user"


class UndoRequest(BaseModel):
    actor: str = "user"


class PreviewRequest(BaseModel):
    key: str | None = None
    source: str | None = None
    field: str | None = None
    matched_source: str | None = None
    matched_field: str | None = None
    rows: int = 5


def _mapping_session_or_404(mapping_session_id: str):
    try:
        return get_mapping_session(mapping_session_id)
    except ManualMappingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/field-mapping/manual/session")
def manual_create_session(req: CreateMappingSessionRequest) -> dict:
    config = MappingConfig(
        green_threshold=req.green_threshold,
        light_green_threshold=req.light_green_threshold,
        semantic_weight=req.semantic_weight,
        value_weight=req.value_weight,
        ambiguous_gap=req.ambiguous_gap,
        yellow_min_value_score=req.yellow_min_value_score,
    )
    try:
        session = create_mapping_session(
            req.session_ids, crosswalk_path=req.crosswalk_path, config=config, actor=req.actor
        )
    except (FieldComparisonError, CrosswalkError, ManualMappingError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@app.get("/field-mapping/manual/{mapping_session_id}")
def manual_get_session(mapping_session_id: str) -> dict:
    return _mapping_session_or_404(mapping_session_id).to_dict()


@app.post("/field-mapping/manual/{mapping_session_id}/override")
def manual_override(mapping_session_id: str, req: ManualMappingRequest) -> dict:
    session = _mapping_session_or_404(mapping_session_id)
    try:
        entry = set_manual_mapping(
            session,
            source=req.source,
            field_name=req.field,
            matched_source=req.matched_source,
            matched_field=req.matched_field,
            category=req.category,
            actor=req.actor,
            note=req.note,
        )
    except ManualMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry.to_dict()


@app.post("/field-mapping/manual/{mapping_session_id}/decision")
def manual_decision(mapping_session_id: str, req: DecisionRequest) -> dict:
    session = _mapping_session_or_404(mapping_session_id)
    try:
        entry = decide_mapping(
            session,
            key=req.key,
            decision=req.decision,
            actor=req.actor,
            note=req.note,
            matched_field=req.matched_field,
        )
    except ManualMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry.to_dict()


@app.post("/field-mapping/manual/{mapping_session_id}/mapping-file")
def manual_mapping_file(mapping_session_id: str, req: MappingFileRequest) -> dict:
    session = _mapping_session_or_404(mapping_session_id)
    try:
        return apply_mapping_file(
            session,
            content=req.content,
            source=req.source,
            matched_source=req.matched_source,
            actor=req.actor,
            category=req.category,
        )
    except ManualMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/field-mapping/manual/{mapping_session_id}/reset")
def manual_reset(mapping_session_id: str, req: ResetRequest) -> dict:
    session = _mapping_session_or_404(mapping_session_id)
    try:
        entry = reset_to_ai(session, req.key, actor=req.actor)
    except ManualMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry.to_dict()


@app.post("/field-mapping/manual/{mapping_session_id}/undo")
def manual_undo(mapping_session_id: str, req: UndoRequest) -> dict:
    session = _mapping_session_or_404(mapping_session_id)
    try:
        undo_last(session, actor=req.actor)
    except ManualMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.to_dict()


@app.post("/field-mapping/manual/{mapping_session_id}/preview")
def manual_preview(mapping_session_id: str, req: PreviewRequest) -> dict:
    session = _mapping_session_or_404(mapping_session_id)
    try:
        return preview_mapping(
            session,
            key=req.key,
            source=req.source,
            field_name=req.field,
            matched_source=req.matched_source,
            matched_field=req.matched_field,
            rows=req.rows,
        )
    except ManualMappingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/field-mapping/manual/{mapping_session_id}/validation")
def manual_validation(mapping_session_id: str) -> dict:
    session = _mapping_session_or_404(mapping_session_id)
    return validate_mapping_session(session)
