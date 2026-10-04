import pandas as pd
import pytest

from field_mapping.auto_mapping import MappingConfig
from field_mapping.crosswalk import CrosswalkError
from field_mapping.manual_mapping import COMMON, MappingEntry, ManualMappingSession
from reconciliation.aggregate import AggregateReconciliationError, reconcile_aggregates


def _amount_entry(source, matched_source):
    return MappingEntry(
        source=source, field="Amount", matched_source=matched_source, matched_field="Amount",
        score=1.0, category=COMMON, mapping_method="exact_name", reason="exact name match",
        is_amount_candidate=True,
    )


def _session(sources=("FA", "GL")):
    entries = []
    for a in sources:
        for b in sources:
            if a != b:
                entries.append(_amount_entry(a, b))
    return ManualMappingSession(
        mapping_session_id="map-1", ingestion_session_ids=list(sources),
        entries={e.key: e for e in entries}, sources={s: f"{s}-session" for s in sources},
        field_index={}, config=MappingConfig(),
    )


def _write_crosswalk(tmp_path, rows, columns=("gl_account_id", "ma_customer_key", "fa_key")):
    path = tmp_path / "join_map.txt"
    pd.DataFrame(rows, columns=list(columns)).to_csv(path, index=False)
    return path


def test_aggregate_balances_across_two_sources(tmp_path):
    crosswalk = _write_crosswalk(tmp_path, [["ACC001", "CUS-001", "FA-001"]])
    fa = pd.DataFrame([
        {"fa_key": "FA-001", "Amount": 100.0}, {"fa_key": "FA-001", "Amount": 50.0},
    ])
    gl = pd.DataFrame([{"gl_account_id": "ACC001", "Amount": 150.0}])
    session = _session(("FA", "GL"))

    breaks = reconcile_aggregates(session, {"FA": fa, "GL": gl}, crosswalk)

    assert breaks == []  # 100 + 50 == 150, balanced


def test_aggregate_mismatch_detected(tmp_path):
    crosswalk = _write_crosswalk(tmp_path, [["ACC001", "CUS-001", "FA-001"]])
    fa = pd.DataFrame([{"fa_key": "FA-001", "Amount": 100.0}])
    gl = pd.DataFrame([{"gl_account_id": "ACC001", "Amount": 250.0}])
    session = _session(("FA", "GL"))

    breaks = reconcile_aggregates(session, {"FA": fa, "GL": gl}, crosswalk)

    assert len(breaks) == 1
    br = breaks[0]
    assert br.totals == {"FA": 100.0, "GL": 250.0}
    assert br.max_difference == 150.0
    assert br.account["fa_key"] == "FA-001"
    assert br.account["gl_account_id"] == "ACC001"


def test_aggregate_within_tolerance_not_a_break(tmp_path):
    crosswalk = _write_crosswalk(tmp_path, [["ACC001", "CUS-001", "FA-001"]])
    fa = pd.DataFrame([{"fa_key": "FA-001", "Amount": 100.001}])
    gl = pd.DataFrame([{"gl_account_id": "ACC001", "Amount": 100.002}])
    session = _session(("FA", "GL"))

    breaks = reconcile_aggregates(session, {"FA": fa, "GL": gl}, crosswalk, tolerance=0.01)

    assert breaks == []


def test_aggregate_account_present_in_only_one_source_is_skipped(tmp_path):
    crosswalk = _write_crosswalk(tmp_path, [["ACC001", "CUS-001", "FA-001"], ["ACC002", "CUS-002", "FA-002"]])
    fa = pd.DataFrame([{"fa_key": "FA-001", "Amount": 100.0}, {"fa_key": "FA-002", "Amount": 999.0}])
    gl = pd.DataFrame([{"gl_account_id": "ACC001", "Amount": 100.0}])  # ACC002 absent from GL entirely
    session = _session(("FA", "GL"))

    breaks = reconcile_aggregates(session, {"FA": fa, "GL": gl}, crosswalk)

    assert breaks == []  # ACC002 only in one source -- nothing to compare, not flagged


def test_aggregate_three_way(tmp_path):
    crosswalk = _write_crosswalk(tmp_path, [["ACC001", "CUS-001", "FA-001"]])
    fa = pd.DataFrame([{"fa_key": "FA-001", "Amount": 100.0}])
    ma = pd.DataFrame([{"ma_customer_key": "CUS-001", "Amount": 100.0}])
    gl = pd.DataFrame([{"gl_account_id": "ACC001", "Amount": 999.0}])
    session = _session(("FA", "MA", "GL"))

    breaks = reconcile_aggregates(session, {"FA": fa, "MA": ma, "GL": gl}, crosswalk)

    assert len(breaks) == 1
    assert breaks[0].totals == {"FA": 100.0, "MA": 100.0, "GL": 999.0}
    assert breaks[0].max_difference == 899.0


def test_aggregate_requires_at_least_two_resolvable_sources(tmp_path):
    crosswalk = _write_crosswalk(tmp_path, [["ACC001", "CUS-001", "FA-001"]])
    fa = pd.DataFrame([{"fa_key": "FA-001", "Amount": 100.0}])
    # GL has no gl_account_id column at all -- unresolvable
    gl = pd.DataFrame([{"SomeOtherColumn": "x", "Amount": 999.0}])
    session = _session(("FA", "GL"))

    with pytest.raises(AggregateReconciliationError):
        reconcile_aggregates(session, {"FA": fa, "GL": gl}, crosswalk)


def test_aggregate_missing_crosswalk_file_raises(tmp_path):
    fa = pd.DataFrame([{"fa_key": "FA-001", "Amount": 100.0}])
    gl = pd.DataFrame([{"gl_account_id": "ACC001", "Amount": 100.0}])
    session = _session(("FA", "GL"))

    with pytest.raises(CrosswalkError):
        reconcile_aggregates(session, {"FA": fa, "GL": gl}, tmp_path / "does_not_exist.txt")
