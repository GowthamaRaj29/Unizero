import pandas as pd
import pytest

from field_mapping.auto_mapping import MappingConfig
from field_mapping.manual_mapping import COMMON, MappingEntry, ManualMappingSession
from reconciliation.matcher import (
    AMOUNT_MISMATCH,
    CURRENCY_MISMATCH,
    DATE_MISMATCH,
    DUPLICATE_RECORD,
    MISSING_RECORD,
    MatchConfig,
    MatcherError,
    reconcile,
)


def _entry(source, field_name, matched_source, matched_field, *, amount=False, method="exact_name"):
    return MappingEntry(
        source=source,
        field=field_name,
        matched_source=matched_source,
        matched_field=matched_field,
        score=1.0,
        category=COMMON,
        mapping_method=method,
        reason=f"'{field_name}' and '{matched_field}' match exactly.",
        is_amount_candidate=amount,
    )


def _session(entries: list[MappingEntry], sources=("FA", "GL")) -> ManualMappingSession:
    entry_dict = {e.key: e for e in entries}
    return ManualMappingSession(
        mapping_session_id="map-1",
        ingestion_session_ids=list(sources),
        entries=entry_dict,
        sources={s: f"{s}-session" for s in sources},
        field_index={},
        config=MappingConfig(),
    )


def _fa_gl_entries():
    return [
        _entry("FA", "Amount", "GL", "Amount", amount=True),
        _entry("GL", "Amount", "FA", "Amount", amount=True),
        _entry("FA", "TransactionDate", "GL", "TransactionDate"),
        _entry("GL", "TransactionDate", "FA", "TransactionDate"),
        _entry("FA", "Currency", "GL", "Currency"),
        _entry("GL", "Currency", "FA", "Currency"),
        _entry("FA", "TransactionID", "GL", "TransactionID"),  # join key itself -- must be skipped
        _entry("FA", "fa_key", "GL", "gl_account_id", method="crosswalk"),  # must never be value-diffed
    ]


def test_clean_match_produces_no_break():
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "fa_key": "FA-001"}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "gl_account_id": "ACC001"}])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert breaks == []


def test_amount_mismatch_detected_beyond_tolerance():
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.00, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "fa_key": "FA-001"}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 105.50, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "gl_account_id": "ACC001"}])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert len(breaks) == 1
    br = breaks[0]
    assert br.break_key == "T1"
    assert AMOUNT_MISMATCH in br.break_types
    assert len(br.differences) == 1
    diff = br.differences[0]
    assert diff.difference_type == AMOUNT_MISMATCH
    assert diff.value_a == 100.00
    assert diff.value_b == 105.50


def test_amount_within_tolerance_is_not_a_break():
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.001, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "fa_key": "FA-001"}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.002, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "gl_account_id": "ACC001"}])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl}, MatchConfig(amount_tolerance=0.01))

    assert breaks == []


def test_missing_record_detected():
    fa = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
        {"TransactionID": "T2", "Amount": 50.0, "TransactionDate": "2026-08-02", "Currency": "EUR", "fa_key": "FA-002"},
    ])
    gl = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "gl_account_id": "ACC001"},
    ])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert len(breaks) == 1
    assert breaks[0].break_key == "T2"
    assert breaks[0].missing_in == ["GL"]
    assert breaks[0].present_in == ["FA"]
    assert breaks[0].break_types == [MISSING_RECORD]
    assert breaks[0].differences == []


def test_date_and_currency_mismatch_classified_correctly():
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "fa_key": "FA-001"}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-05",
                         "Currency": "EUR", "gl_account_id": "ACC001"}])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    types = breaks[0].break_types
    assert DATE_MISMATCH in types
    assert CURRENCY_MISMATCH in types


def test_crosswalk_mapped_fields_are_never_value_diffed():
    # fa_key ("FA-001") and gl_account_id ("ACC001") are linked via
    # crosswalk, not equal in value -- must never surface as a break.
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "fa_key": "FA-999"}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "gl_account_id": "ACC-000"}])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert breaks == []


def test_only_common_category_mappings_are_diffed():
    entries = _fa_gl_entries()
    # a LIGHT_GREEN/POTENTIAL pair on Description must not be diffed.
    entries.append(MappingEntry(
        source="FA", field="Description", matched_source="GL", matched_field="Description",
        score=0.8, category="POTENTIAL", mapping_method="embedding", reason="not yet confirmed",
    ))
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "fa_key": "FA-001", "Description": "Wire transfer"}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "gl_account_id": "ACC001", "Description": "Completely different text"}])
    session = _session(entries)

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert breaks == []


def test_missing_key_field_raises_matcher_error():
    fa = pd.DataFrame([{"Amount": 100.0}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0}])
    session = _session(_fa_gl_entries())

    with pytest.raises(MatcherError):
        reconcile(session, {"FA": fa, "GL": gl})


def test_requires_at_least_two_matching_sources():
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0}])
    session = _session(_fa_gl_entries())

    with pytest.raises(MatcherError):
        reconcile(session, {"FA": fa})


def test_three_way_reconciliation_fa_ma_gl():
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "fa_key": "FA-001"}])
    ma = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "ma_customer_key": "CUS-001"}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 999.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "gl_account_id": "ACC001"}])
    entries = _fa_gl_entries() + [
        _entry("FA", "Amount", "MA", "Amount", amount=True),
        _entry("MA", "Amount", "FA", "Amount", amount=True),
        _entry("MA", "Amount", "GL", "Amount", amount=True),
        _entry("GL", "Amount", "MA", "Amount", amount=True),
        _entry("FA", "TransactionDate", "MA", "TransactionDate"),
        _entry("MA", "TransactionDate", "GL", "TransactionDate"),
        _entry("FA", "Currency", "MA", "Currency"),
        _entry("MA", "Currency", "GL", "Currency"),
        _entry("FA", "TransactionID", "MA", "TransactionID"),
    ]
    session = _session(entries, sources=("FA", "MA", "GL"))

    breaks = reconcile(session, {"FA": fa, "MA": ma, "GL": gl})

    assert len(breaks) == 1
    br = breaks[0]
    assert set(br.present_in) == {"FA", "MA", "GL"}
    assert br.missing_in == []
    assert AMOUNT_MISMATCH in br.break_types
    # FA-GL and MA-GL both mismatch; FA-MA agree.
    pairs = {frozenset({d.source_a, d.source_b}) for d in br.differences}
    assert frozenset({"FA", "GL"}) in pairs
    assert frozenset({"MA", "GL"}) in pairs
    assert frozenset({"FA", "MA"}) not in pairs


# ---------- Bugfix #10 (part 1): duplicate TransactionIDs are reported, not silently dropped ----------

def test_bugfix10_duplicate_key_in_one_source_is_reported_as_a_break():
    fa = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
    ])
    gl = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "gl_account_id": "ACC001"},
    ])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert len(breaks) == 1
    br = breaks[0]
    assert br.break_key == "T1"
    assert DUPLICATE_RECORD in br.break_types
    assert br.duplicate_in == {"FA": 2}


def test_bugfix10_duplicate_key_does_not_silently_disappear_even_when_values_agree():
    # Previously: drop_duplicates(keep="first") would make this look like
    # a perfectly clean, un-flagged match. It must not, any more.
    fa = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
    ])
    gl = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "gl_account_id": "ACC001"},
    ])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert len(breaks) == 1
    assert breaks[0].duplicate_in == {"FA": 3}
    assert breaks[0].differences == []  # values genuinely agree -- but it's still a break, per duplicate_in


def test_bugfix10_duplicates_in_multiple_sources_both_reported():
    fa = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
    ])
    gl = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "gl_account_id": "ACC001"},
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "gl_account_id": "ACC001"},
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "gl_account_id": "ACC001"},
    ])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert breaks[0].duplicate_in == {"FA": 2, "GL": 3}


def test_bugfix10_no_duplicates_no_duplicate_record_type():
    fa = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "fa_key": "FA-001"}])
    gl = pd.DataFrame([{"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01",
                         "Currency": "USD", "gl_account_id": "ACC001"}])
    session = _session(_fa_gl_entries())

    breaks = reconcile(session, {"FA": fa, "GL": gl})

    assert breaks == []  # clean, unique, matching -- still not a break
