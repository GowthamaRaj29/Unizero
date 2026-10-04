"""
Basic tests for Automated Field Mapping (field_mapping/auto_mapping.py).

Unit tests use small synthetic field-profile dicts (the exact shape
comparison.py/get_field_comparison produce) so each mapping mode is
checked in isolation and fast. One integration test ingests the actual
June OneRecon dataset (FA CSV + GL XML + join_map.txt) through the real
ingestion pipeline and field_comparison_view, to prove the whole path
works end-to-end on real data -- not just on hand-built fixtures.

Scope note: the integration test uses FA + GL only. MA is served by a
Flask app (ma_api_server_202606.py) that has to be running on
localhost:5000 to ingest; spinning that up is out of scope for "a few
basic tests" and is better covered by a separate ingestion-layer test
that starts the server itself.

Run with:
    cd OneRecon/ai-services
    pip install -r requirements.txt  # or: pip install pandas numpy rapidfuzz \
        fastapi pydantic anthropic requests pytest --break-system-packages
    pytest tests/test_auto_mapping.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from field_mapping.auto_mapping import (
    GREEN,
    LIGHT_GREEN,
    RED,
    YELLOW,
    MappingConfig,
    _is_ambiguous,
    compute_mapping_for_sources,
)
from field_mapping.crosswalk import CrosswalkError, load_crosswalk_fields
from field_mapping.field_comparison_view import get_field_comparison
from ingestion.workflow import IngestionStatus, ReviewAction, start_ingestion, submit_review

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "OneRecon_DataSet" / "Historical Data" / "june"


def _profile(name: str, values: list) -> dict:
    """Builds a field profile dict in the same shape
    comparison.build_field_profiles/serialize_field_profiles produce,
    without needing a real DataFrame -- good enough for scoring logic
    that only ever reads {"field", "dtype", "top_values"}."""
    return {
        "field": name,
        "dtype": "object",
        "null_count": 0,
        "top_values": [{"value": v, "count": 1} for v in values],
    }


# ---------- unit tests ----------

def test_exact_name_match_is_green():
    sources = [
        {"name": "SourceA", "fields": [_profile("TransactionID", ["A1", "A2"])]},
        {"name": "SourceB", "fields": [_profile("TransactionID", ["A1", "A3"])]},
    ]
    result = compute_mapping_for_sources(sources)
    match = next(m for m in result.mappings if m.source == "SourceA")
    assert match.matched_field == "TransactionID"
    assert match.mapping_method == "exact_name"
    assert match.color == GREEN
    assert match.score == 1.0


def test_crosswalk_mapping_is_authoritative(tmp_path):
    crosswalk_path = tmp_path / "join_map.txt"
    crosswalk_path.write_text(
        "gl_account_id,ma_customer_key,fa_key,entity,effective_from,effective_to\n"
        "ACC0001,CUS-000001,FA-000001,Global,2022-01-01,2099-12-31\n"
    )

    sources = [
        {"name": "GL", "fields": [_profile("gl_account_id", ["ACC0001", "ACC0002"])]},
        {"name": "FA", "fields": [_profile("fa_key", ["FA-000001", "FA-000002"])]},
    ]
    result = compute_mapping_for_sources(sources, crosswalk_path=crosswalk_path)
    match = next(m for m in result.mappings if m.source == "GL")

    assert match.matched_source == "FA"
    assert match.matched_field == "fa_key"
    assert match.mapping_method == "crosswalk"
    assert match.color == GREEN
    assert match.score == 1.0


def test_missing_crosswalk_file_raises():
    with pytest.raises(CrosswalkError):
        load_crosswalk_fields("/no/such/file.txt")


def test_semantic_mapping_without_crosswalk_uses_embeddings():
    # Different names, same underlying transactions (matching sample
    # dates) -- exactly the "compare name/meaning AND sample values"
    # case the requirement describes.
    dates = ["2026-06-04", "2026-06-05", "2026-06-06", "2026-06-07"]
    sources = [
        {"name": "FA", "fields": [_profile("Treasury Date", dates)]},
        {"name": "MA", "fields": [_profile("TransactionDate", dates)]},
    ]
    result = compute_mapping_for_sources(sources)
    match = next(m for m in result.mappings if m.source == "FA")

    assert match.mapping_method == "embedding"
    assert match.color in (GREEN, LIGHT_GREEN)  # not pinned to a single
    # embedding backend's exact score -- just that shared name fragments
    # ("date") plus fully-overlapping sample values clear the bar.


def test_yellow_flags_reconciliation_amount_despite_different_names():
    amounts = [100.0, 250.5, 99.99, 5000.0, 32.10]
    sources = [
        {"name": "FA", "fields": [_profile("Amount", amounts)]},
        {"name": "MA", "fields": [_profile("Value", amounts)]},
    ]
    result = compute_mapping_for_sources(sources)
    match = next(m for m in result.mappings if m.source == "FA")

    assert match.matched_field == "Value"
    assert match.color == YELLOW  # promoted regardless of what the
    # name/semantic score alone would have classified it as


def test_yellow_also_applies_to_identical_field_names():
    # "Amount" == "Amount" would otherwise short-circuit to plain GREEN
    # via exact_name -- YELLOW (this IS the reconciliation field) should
    # still take precedence, since that's a more important signal than
    # plain name-match confidence.
    amounts = [10.0, 20.0, 30.0]
    sources = [
        {"name": "FA", "fields": [_profile("Amount", amounts)]},
        {"name": "GL", "fields": [_profile("Amount", amounts)]},
    ]
    result = compute_mapping_for_sources(sources)
    match = next(m for m in result.mappings if m.source == "FA")
    assert match.mapping_method == "exact_name"
    assert match.color == YELLOW


def test_no_plausible_match_is_red():
    sources = [
        {"name": "FA", "fields": [_profile("Country", ["US", "GB", "DE"])]},
        {"name": "MA", "fields": [_profile("WidgetFlavor", ["chocolate", "vanilla"])]},
    ]
    result = compute_mapping_for_sources(sources)
    match = next(m for m in result.mappings if m.source == "FA")
    assert match.color == RED


def test_ambiguous_gap_flags_close_runner_up():
    config = MappingConfig(light_green_threshold=0.5, ambiguous_gap=0.05)
    assert _is_ambiguous(0.80, (0.78, "embedding", "", None, {"field": "x"}), config) is True
    assert _is_ambiguous(0.80, (0.60, "embedding", "", None, {"field": "x"}), config) is False
    assert _is_ambiguous(0.80, None, config) is False


def test_concept_group_spans_three_sources():
    # No crosswalk needed here -- exact name matches alone should chain
    # FA -> MA -> RR into one concept group, generalizing the spec's
    # "FA:Treasury Date -> MA:TransactionDate -> RR:ValueDate" example
    # to whatever fields actually match, in any order.
    sources = [
        {"name": "FA", "fields": [_profile("TransactionDate", ["2026-06-04"])]},
        {"name": "MA", "fields": [_profile("TransactionDate", ["2026-06-04"])]},
        {"name": "RR", "fields": [_profile("TransactionDate", ["2026-06-04"])]},
    ]
    result = compute_mapping_for_sources(sources)
    group = next(g for g in result.concept_groups if len(g.members) == 3)
    assert {m["source"] for m in group.members} == {"FA", "MA", "RR"}


# ---------- integration test on real OneRecon data ----------

@pytest.mark.skipif(not DATA_DIR.exists(), reason="OneRecon June dataset not present")
def test_real_fa_and_gl_data_end_to_end():
    fa_session = start_ingestion(str(DATA_DIR / "fa_report_202606.csv"))
    gl_session = start_ingestion(str(DATA_DIR / "gl_report_202606.xml"))

    # Real financial data commonly trips the default IQR outlier check on
    # Amount -- that's the human-review gate doing its job, not a bug.
    # Simulate the human clicking "Go Ahead" so we can proceed to mapping,
    # exactly like a real Investigator would.
    for session in (fa_session, gl_session):
        if session.status == IngestionStatus.REVIEW_REQUIRED:
            submit_review(session.session_id, ReviewAction.GO_AHEAD, actor="test")

    comparison = get_field_comparison([fa_session.session_id, gl_session.session_id])
    assert {s["session_id"] for s in comparison["sources"]} == {
        fa_session.session_id, gl_session.session_id,
    }

    result = compute_mapping_for_sources(
        comparison["sources"], crosswalk_path=DATA_DIR / "join_map.txt"
    )
    by_field = {(m.source, m.field): m for m in result.mappings}

    fa_name, gl_name = fa_session.metadata["source"], gl_session.metadata["source"]

    # Shared fields with identical names -> exact_name, GREEN (except Amount).
    txn_id = by_field[(fa_name, "TransactionID")]
    assert txn_id.mapping_method == "exact_name" and txn_id.color == GREEN

    # The decimal amount field -> YELLOW, regardless of exact-name match.
    amount = by_field[(fa_name, "Amount")]
    assert amount.color == YELLOW

    # fa_key <-> gl_account_id are only linked via the crosswalk file,
    # not by name -- this only resolves at all because crosswalk_path
    # was supplied.
    fa_key = by_field[(fa_name, "fa_key")]
    assert fa_key.mapping_method == "crosswalk"
    assert fa_key.matched_field == "gl_account_id"
    assert fa_key.color == GREEN
