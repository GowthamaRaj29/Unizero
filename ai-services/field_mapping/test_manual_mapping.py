"""
Tests for Manual Field Mapping Override (field_mapping/manual_mapping.py)
and Preview/Validation (field_mapping/mapping_validation.py).

Sessions are built from synthetic field profiles -- the exact shape
comparison.py/get_field_comparison produce -- so the override logic is
exercised without needing a live ingestion session. One test ingests the
real June dataset to prove preview reads actual DataFrame rows.

Run with:
    cd OneRecon/ai-services
    pytest field_mapping/tests/test_manual_mapping.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from field_mapping.auto_mapping import (
    GREEN,
    LIGHT_GREEN,
    RED,
    compute_mapping_for_sources,
)
from field_mapping.manual_mapping import (
    ACCEPT,
    COMMON,
    KEEP_POTENTIAL,
    MANUAL_METHOD,
    MAPPING_FILE_METHOD,
    POTENTIAL,
    REJECT,
    UNCOMMON,
    ManualMappingError,
    apply_mapping_file,
    create_mapping_session,
    decide_mapping,
    make_key,
    parse_mapping_file,
    reset_to_ai,
    set_manual_mapping,
    translate_value,
    undo_last,
)
from field_mapping.mapping_validation import (
    datatype_warnings,
    detect_duplicate_mappings,
    preview_mapping,
    validate_mapping_session,
)
from ingestion.workflow import IngestionStatus, ReviewAction, start_ingestion, submit_review

# The repo root is two levels up from ai-services/, but this test file also
# runs from ai-services/tests/ in some checkouts -- resolve whichever exists.
_REL = Path("data") / "OneRecon_DataSet" / "Historical Data" / "june"
DATA_DIR = next(
    (parent / _REL for parent in Path(__file__).resolve().parents if (parent / _REL).exists()),
    Path(__file__).resolve().parents[2] / _REL,
)


def _profile(name: str, values: list) -> dict:
    return {
        "field": name,
        "dtype": "object",
        "null_count": 0,
        "top_values": [{"value": v, "count": 1} for v in values],
    }


def _session(actor: str = "test"):
    """Two panels with a deliberate mix: an exact-name match (Common), a
    near match the AI should treat as Potential, and two fields with
    nothing in common (Uncommon) -- plus a String/Numeric pair for the
    datatype-warning test."""
    sources = [
        {
            "name": "FA",
            "session_id": "",
            "fields": [
                _profile("TransactionID", ["A1", "A2", "A3"]),
                _profile("Counterparty Code", ["1", "2", "3"]),
                _profile("Branch", ["Chennai", "Mumbai"]),
            ],
        },
        {
            "name": "GL",
            "session_id": "",
            "fields": [
                _profile("TransactionID", ["A1", "A4", "A5"]),
                _profile("Client Type", ["Current Ac - Retail", "Savings"]),
                _profile("Posting Office", ["Chennai", "Delhi"]),
            ],
        },
    ]
    auto_result = compute_mapping_for_sources(sources)
    return create_mapping_session(
        session_ids=[], auto_result=auto_result, sources=sources, actor=actor
    )


# ---------- manual accept / override ----------

def test_accept_ai_match_moves_to_common_and_marks_manual():
    session = _session()
    key = make_key("FA", "TransactionID", "GL")
    entry = decide_mapping(session, key, ACCEPT, actor="analyst", note="verified by hand")

    assert entry.category == COMMON
    assert entry.mapping_method == MANUAL_METHOD
    assert entry.is_manual_override is True
    assert entry.override["actor"] == "analyst"
    # The AI's own recommendation survives the human decision untouched.
    assert entry.ai_recommendation["mapping_method"] == "exact_name"
    assert entry.ai_recommendation["matched_field"] == "TransactionID"
    # ...and the pre-decision state is retained for audit.
    assert entry.previous_mapping["is_manual_override"] is False


def test_reject_moves_to_uncommon_but_keeps_ai_recommendation():
    session = _session()
    key = make_key("FA", "Branch", "GL")
    entry = decide_mapping(session, key, REJECT, actor="analyst")

    assert entry.category == UNCOMMON
    assert entry.is_manual_override is True
    assert entry.ai_recommendation is not None
    assert entry.override["ai_matched_field"] == entry.ai_recommendation["matched_field"]


def test_override_ai_match_with_different_target_field():
    session = _session()
    key = make_key("FA", "Branch", "GL")
    entry = decide_mapping(session, key, ACCEPT, matched_field="Posting Office", actor="analyst")

    assert entry.matched_field == "Posting Office"
    assert entry.category == COMMON
    assert entry.mapping_method == MANUAL_METHOD
    # The human's target overrode whatever the AI picked, and both are visible.
    assert entry.ai_recommendation["matched_field"] is not None


def test_manual_mapping_while_keeping_field_potential():
    session = _session()
    entry = set_manual_mapping(
        session, "FA", "Branch", "GL", "Posting Office", category=POTENTIAL, actor="analyst"
    )
    assert entry.category == POTENTIAL
    assert entry.color == LIGHT_GREEN
    assert entry.needs_review is True
    assert entry.is_manual_override is True


def test_keep_potential_decision_leaves_it_unconfirmed():
    session = _session()
    key = make_key("FA", "TransactionID", "GL")
    entry = decide_mapping(session, key, KEEP_POTENTIAL, actor="analyst")
    assert entry.category == POTENTIAL
    assert entry.needs_review is True


# ---------- RED / Uncommon field mapping ----------

def test_can_manually_map_two_uncommon_fields():
    session = _session()
    # Nothing links these by name or value -- the AI would never pair them.
    entry = set_manual_mapping(
        session, "FA", "Counterparty Code", "GL", "Client Type", actor="analyst",
        note="business rule: counterparty code encodes client type",
    )
    assert entry.matched_field == "Client Type"
    assert entry.category == COMMON
    assert entry.color == GREEN
    assert entry.mapping_method == MANUAL_METHOD
    assert "counterparty code" in entry.reason.lower()


def test_manual_mapping_rejects_unknown_field():
    session = _session()
    with pytest.raises(ManualMappingError):
        set_manual_mapping(session, "FA", "TransactionID", "GL", "NoSuchField")


# ---------- mapping file ----------

def test_parse_mapping_file_is_literal():
    records, errors = parse_mapping_file(
        "# comment\n"
        "Counterparty Code: 1 -> Client Type: Current Ac - Retail\n"
        "Counterparty Code: 2 \u2192 Client Type: Savings\n"
        "\n"
        "garbage line without an arrow\n"
    )
    assert len(records) == 2
    assert records[0] == {
        "source_field": "Counterparty Code",
        "source_value": "1",
        "target_field": "Client Type",
        "target_value": "Current Ac - Retail",
        "line_number": 2,
    }
    assert len(errors) == 1 and errors[0]["line_number"] == 5


def test_mapping_file_upload_creates_authoritative_mapping():
    session = _session()
    result = apply_mapping_file(
        session,
        "Counterparty Code: 1 -> Client Type: Current Ac - Retail\n"
        "Counterparty Code: 2 -> Client Type: Savings\n",
        source="FA",
        matched_source="GL",
        actor="analyst",
    )
    assert result["applied_count"] == 1
    assert result["value_mapping_count"] == 2

    entry = session.entries[make_key("FA", "Counterparty Code", "GL")]
    assert entry.mapping_method == MAPPING_FILE_METHOD
    assert entry.matched_field == "Client Type"
    assert entry.score == 1.0

    # Explicit values translate; anything not in the file does not.
    assert translate_value(entry, "1")["target_value"] == "Current Ac - Retail"
    unmapped = translate_value(entry, "99")
    assert unmapped["mapped"] is False and unmapped["target_value"] is None


def test_mapping_file_reports_unknown_fields_instead_of_guessing():
    session = _session()
    result = apply_mapping_file(
        session, "Nonexistent Field: 1 -> Client Type: Savings\n",
        source="FA", matched_source="GL",
    )
    assert result["applied_count"] == 0
    assert len(result["errors"]) == 1


# ---------- reset / undo ----------

def test_reset_restores_the_ai_recommendation():
    session = _session()
    key = make_key("FA", "TransactionID", "GL")
    original = session.entries[key].ai_recommendation["matched_field"]

    set_manual_mapping(session, "FA", "TransactionID", "GL", "Posting Office", actor="analyst")
    assert session.entries[key].matched_field == "Posting Office"

    restored = reset_to_ai(session, key, actor="analyst")
    assert restored.matched_field == original
    assert restored.is_manual_override is False
    assert restored.mapping_method == "exact_name"
    assert restored.previous_mapping["matched_field"] == "Posting Office"


def test_undo_walks_back_through_changes():
    session = _session()
    key = make_key("FA", "TransactionID", "GL")

    decide_mapping(session, key, ACCEPT, actor="analyst")
    set_manual_mapping(session, "FA", "TransactionID", "GL", "Posting Office", actor="analyst")
    assert session.entries[key].matched_field == "Posting Office"

    undo_last(session)                       # back to the ACCEPT state
    assert session.entries[key].matched_field == "TransactionID"
    assert session.entries[key].category == COMMON

    undo_last(session)                       # back to the raw AI state
    assert session.entries[key].is_manual_override is False


def test_undo_removes_a_mapping_the_human_created():
    session = _session()
    key = make_key("FA", "Counterparty Code", "GL")
    set_manual_mapping(session, "FA", "Counterparty Code", "GL", "Client Type")
    had_ai_entry = session.entries[key].ai_recommendation is not None

    undo_last(session)
    if not had_ai_entry:
        assert key not in session.entries


def test_undo_with_empty_stack_raises():
    session = _session()
    with pytest.raises(ManualMappingError):
        undo_last(session)


# ---------- preview ----------

def test_preview_returns_sample_values_for_both_sides():
    session = _session()
    set_manual_mapping(session, "FA", "Counterparty Code", "GL", "Client Type")
    preview = preview_mapping(session, key=make_key("FA", "Counterparty Code", "GL"), rows=5)

    assert preview["left"]["field"] == "Counterparty Code"
    assert preview["right"]["field"] == "Client Type"
    assert preview["left"]["values"][:3] == ["1", "2", "3"]
    assert "Current Ac - Retail" in preview["right"]["values"]


def test_preview_works_for_an_uncommitted_pair():
    session = _session()
    preview = preview_mapping(
        session, source="FA", field_name="Branch",
        matched_source="GL", matched_field="Posting Office", rows=2,
    )
    assert len(preview["left"]["values"]) == 2
    assert preview["key"] == make_key("FA", "Branch", "GL")


def test_preview_shows_explicit_value_translations_only():
    session = _session()
    apply_mapping_file(
        session, "Counterparty Code: 1 -> Client Type: Current Ac - Retail\n",
        source="FA", matched_source="GL",
    )
    preview = preview_mapping(session, key=make_key("FA", "Counterparty Code", "GL"))
    translations = {t["source_value"]: t for t in preview["value_translations"]}
    assert translations["1"]["target_value"] == "Current Ac - Retail"
    assert translations["2"]["mapped"] is False  # never invented


# ---------- datatype warnings ----------

def test_datatype_mismatch_is_warned_not_corrected():
    session = _session()
    set_manual_mapping(session, "FA", "Counterparty Code", "GL", "Client Type")
    key = make_key("FA", "Counterparty Code", "GL")
    warnings, left_type, right_type = datatype_warnings(session, key)

    assert (left_type, right_type) == ("Numeric", "String")
    assert len(warnings) == 1
    assert warnings[0]["type"] == "DATATYPE_MISMATCH"
    assert "FA: Numeric vs GL: String" in warnings[0]["message"]

    # The stored values are untouched -- nothing was cast.
    profile = session.field_index["FA"]["Counterparty Code"]
    assert profile["top_values"][0]["value"] == "1"


def test_matching_types_produce_no_warning():
    session = _session()
    set_manual_mapping(session, "FA", "Branch", "GL", "Posting Office")
    warnings, _, _ = datatype_warnings(session, make_key("FA", "Branch", "GL"))
    assert warnings == []


# ---------- duplicate detection ----------

def test_duplicate_target_is_detected():
    session = _session()
    set_manual_mapping(session, "FA", "Branch", "GL", "Client Type")
    set_manual_mapping(session, "FA", "Counterparty Code", "GL", "Client Type")

    alerts = detect_duplicate_mappings(session)
    duplicate_targets = [a for a in alerts if a["type"] == "DUPLICATE_TARGET"]
    assert duplicate_targets
    assert set(duplicate_targets[0]["fields"]) == {"Branch", "Counterparty Code"}
    assert "multiple fields" in duplicate_targets[0]["message"]


def test_uncommon_mappings_do_not_trigger_duplicate_alerts():
    session = _session()
    set_manual_mapping(session, "FA", "Branch", "GL", "Client Type", category=UNCOMMON)
    set_manual_mapping(session, "FA", "Counterparty Code", "GL", "Client Type", category=UNCOMMON)
    assert detect_duplicate_mappings(session) == []


def test_validate_session_bundles_warnings_and_alerts():
    session = _session()
    set_manual_mapping(session, "FA", "Counterparty Code", "GL", "Client Type")
    set_manual_mapping(session, "FA", "Branch", "GL", "Client Type")

    report = validate_mapping_session(session)
    assert report["warning_count"] >= 1
    assert report["alert_count"] >= 1
    assert report["mapping_session_id"] == session.mapping_session_id


# ---------- audit ----------

def test_audit_log_records_every_change():
    session = _session()
    key = make_key("FA", "TransactionID", "GL")
    decide_mapping(session, key, ACCEPT, actor="analyst")
    reset_to_ai(session, key, actor="approver")

    actions = [event["action"] for event in session.audit_log]
    assert "mapping_session.created" in actions
    assert "mapping.decision" in actions
    assert "mapping.reset" in actions
    assert {e["actor"] for e in session.audit_log} >= {"analyst", "approver"}


# ---------- integration: preview reads real ingested rows ----------

@pytest.mark.skipif(not DATA_DIR.exists(), reason="OneRecon June dataset not present")
def test_preview_reads_first_rows_of_real_data():
    fa = start_ingestion(str(DATA_DIR / "fa_report_202606.csv"))
    gl = start_ingestion(str(DATA_DIR / "gl_report_202606.xml"))
    for session in (fa, gl):
        if session.status == IngestionStatus.REVIEW_REQUIRED:
            submit_review(session.session_id, ReviewAction.GO_AHEAD, actor="test")

    mapping_session = create_mapping_session(
        [fa.session_id, gl.session_id], crosswalk_path=DATA_DIR / "join_map.txt"
    )
    fa_name = fa.metadata["source"]
    key = make_key(fa_name, "fa_key", gl.metadata["source"])

    preview = preview_mapping(mapping_session, key=key, rows=5)
    assert len(preview["left"]["values"]) == 5
    assert preview["left"]["values"][0].startswith("FA-")

    # Overriding a crosswalk mapping still preserves what the AI said.
    entry = decide_mapping(mapping_session, key, ACCEPT, actor="analyst")
    assert entry.ai_recommendation["mapping_method"] == "crosswalk"
    assert entry.mapping_method == MANUAL_METHOD
