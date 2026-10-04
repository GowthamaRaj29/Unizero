import pytest

import explain
from break_management.models import Break
from break_management.rca import run_rca
from break_management.tests.conftest import FakeAnthropicClient
from reconciliation.matcher import FieldDifference, ReconciliationBreak


def _amount_mismatch_break() -> Break:
    rb = ReconciliationBreak(
        break_key="T2",
        key_field="TransactionID",
        present_in=["FA", "GL"],
        missing_in=[],
        records={
            "FA": {"TransactionID": "T2", "Amount": 250.0, "fa_key": "FA-002"},
            "GL": {"TransactionID": "T2", "Amount": 999.0, "gl_account_id": "ACC002"},
        },
        differences=[
            FieldDifference(
                source_a="FA", field_a="Amount", value_a=250.0,
                source_b="GL", field_b="Amount", value_b=999.0,
                difference_type="AMOUNT_MISMATCH",
                mapping_reason="Both fields are numeric/decimal-typed.",
            )
        ],
        mapping_session_id="map-1",
    )
    return Break.from_reconciliation_break(rb)


def test_run_rca_appends_entry_and_stores_original_even_after_override():
    br = _amount_mismatch_break()
    client = FakeAnthropicClient({
        "root_cause": "GL includes a reclass entry not present in FA.",
        "confidence": "medium",
        "supporting_evidence": ["FA.Amount=250.0 vs GL.Amount=999.0"],
        "suggested_action": "Confirm the GL reclass entry with the ledger team.",
    })

    entry = run_rca(br, client=client)

    assert entry.root_cause == "GL includes a reclass entry not present in FA."
    assert entry.is_unknown is False
    assert br.current_rca is entry
    assert len(br.rca_history) == 1

    # Requirement: original AI RCA is preserved even if an investigator overrides it.
    br.record_investigator_override(note="Actually a timing difference, not a reclass.", actor="jane")
    assert br.current_rca.root_cause == "GL includes a reclass entry not present in FA."  # untouched
    assert br.current_rca.investigator_override["note"] == "Actually a timing difference, not a reclass."
    assert len(br.rca_history) == 1  # override annotates, does not replace


def test_run_rca_returns_unknown_when_model_says_so():
    br = _amount_mismatch_break()
    client = FakeAnthropicClient({
        "root_cause": "UNKNOWN",
        "confidence": "low",
        "supporting_evidence": [],
        "suggested_action": "Investigator to review this break manually.",
    })

    entry = run_rca(br, client=client)

    assert entry.root_cause == "UNKNOWN"
    assert entry.is_unknown is True


def test_run_rca_only_sends_this_breaks_own_evidence():
    br = _amount_mismatch_break()
    client = FakeAnthropicClient({"root_cause": "UNKNOWN", "confidence": "low",
                                   "supporting_evidence": [], "suggested_action": ""})

    run_rca(br, client=client)

    sent_payload = client.calls[0]["messages"][0]["content"]
    assert "T2" in sent_payload
    assert "AMOUNT_MISMATCH" in sent_payload
    # never the raw ingested dataframes / other transactions
    assert "T1" not in sent_payload


def test_run_rca_falls_back_to_unknown_on_non_json_response():
    br = _amount_mismatch_break()
    client = FakeAnthropicClient("not valid json at all")

    entry = run_rca(br, client=client)

    assert entry.root_cause == "UNKNOWN"
    assert entry.confidence == "low"


def test_run_rca_uses_deterministic_rule_when_no_api_key_and_no_client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    br = _amount_mismatch_break()

    entry = run_rca(br, client=None)

    assert entry.root_cause == "The same reconciliation key has conflicting source values."
    assert entry.confidence == "medium"
