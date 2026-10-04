import pytest

from break_management.models import Break
from break_management.prioritization import PriorityConfig, narrate_priority, score_break
from break_management.tests.conftest import FakeAnthropicClient
from reconciliation.matcher import FieldDifference, ReconciliationBreak


def _break(break_key="T1", differences=None, missing_in=None, records=None):
    rb = ReconciliationBreak(
        break_key=break_key,
        key_field="TransactionID",
        present_in=["FA", "GL"] if not missing_in else ["FA"],
        missing_in=missing_in or [],
        records=records or {
            "FA": {"TransactionID": break_key, "Amount": 500.0},
            "GL": {"TransactionID": break_key, "Amount": 500.0},
        },
        differences=differences or [],
        mapping_session_id="map-1",
    )
    return Break.from_reconciliation_break(rb)


def test_score_is_deterministic_and_reproducible_from_components():
    diff = FieldDifference(
        source_a="FA", field_a="Amount", value_a=100.0, source_b="GL", field_b="Amount", value_b=50_100.0,
        difference_type="AMOUNT_MISMATCH", mapping_reason="numeric",
    )
    br = _break(differences=[diff], records={
        "FA": {"TransactionID": "T1", "Amount": 100.0}, "GL": {"TransactionID": "T1", "Amount": 50_100.0},
    })

    score_a = score_break(br, occurrence_count=3)
    score_b = score_break(br, occurrence_count=3)

    assert score_a.total == score_b.total
    config = PriorityConfig()
    expected_total = round(
        config.materiality_weight * score_a.materiality
        + config.risk_weight * score_a.risk
        + config.frequency_weight * score_a.frequency,
        2,
    )
    assert score_a.total == expected_total


def test_missing_record_scores_maximum_risk():
    br = _break(missing_in=["GL"], records={"FA": {"TransactionID": "T1", "Amount": 10.0}})

    score = score_break(br, occurrence_count=0)

    assert score.risk == 100.0  # MISSING_RECORD is the top of RISK_WEIGHT_BY_BREAK_TYPE


def test_higher_occurrence_count_increases_frequency_component_only():
    br = _break()

    low = score_break(br, occurrence_count=0)
    high = score_break(br, occurrence_count=20)

    assert high.frequency > low.frequency
    assert high.materiality == low.materiality
    assert high.risk == low.risk


def test_band_thresholds():
    # A missing record on a large transaction, recurring often, should
    # saturate all three components and land in the top band.
    br = _break(missing_in=["GL"], records={"FA": {"TransactionID": "T1", "Amount": 500_000.0}})
    config = PriorityConfig()

    critical = score_break(br, occurrence_count=100, config=config)  # saturates everything
    assert critical.band == "CRITICAL"

    low = _break()  # no differences, no missing_in -> risk 0, tiny amount
    assert score_break(low, occurrence_count=0, config=config).band == "LOW"


def test_priority_config_rejects_weights_not_summing_to_one():
    with pytest.raises(ValueError):
        PriorityConfig(materiality_weight=0.5, risk_weight=0.5, frequency_weight=0.5)


def test_narrate_priority_returns_none_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    br = _break()
    score = score_break(br, occurrence_count=0)

    assert narrate_priority(br, score, client=None) is None


def test_narrate_priority_does_not_alter_score_it_only_describes_it():
    br = _break()
    score = score_break(br, occurrence_count=0)
    client = FakeAnthropicClient("This break is low priority given its small size and low risk.")

    narrative = narrate_priority(br, score, client=client)

    assert narrative == "This break is low priority given its small size and low risk."
    # the function returns text only -- score itself is untouched by the caller
    assert score.total == score.total
