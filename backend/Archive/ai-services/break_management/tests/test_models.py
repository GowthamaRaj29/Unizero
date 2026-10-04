import pytest

from break_management.models import Break, BreakManagementError, BreakStatus, RCAEntry
from reconciliation.matcher import ReconciliationBreak


def _break():
    rb = ReconciliationBreak(
        break_key="T1", key_field="TransactionID", present_in=["FA", "GL"], missing_in=[],
        records={"FA": {"TransactionID": "T1"}, "GL": {"TransactionID": "T1"}},
        differences=[], mapping_session_id="map-1",
    )
    return Break.from_reconciliation_break(rb)


def test_break_starts_open_with_a_detected_audit_entry():
    br = _break()
    assert br.status == BreakStatus.OPEN
    assert br.audit_log[0].action == "break.detected"


def test_disallowed_transition_raises():
    br = _break()
    with pytest.raises(BreakManagementError):
        br.transition(BreakStatus.RESOLVED, actor="jane")  # OPEN -> RESOLVED is not direct


def test_allowed_transition_logs_previous_and_new():
    br = _break()
    br.transition(BreakStatus.INVESTIGATING, actor="jane", note="looking into it")
    event = br.audit_log[-1]
    assert event.action == "status.changed"
    assert event.details["previous"] == "OPEN"
    assert event.details["new"] == "INVESTIGATING"


def test_terminal_statuses_can_be_reopened():
    br = _break()
    br.transition(BreakStatus.FALSE_POSITIVE, actor="jane")
    br.transition(BreakStatus.INVESTIGATING, actor="jane", note="reopening")
    assert br.status == BreakStatus.INVESTIGATING


def test_rca_history_is_append_only_and_current_rca_is_latest():
    br = _break()
    first = RCAEntry(rca_id="1", root_cause="A", confidence="low", supporting_evidence=[],
                      suggested_action="", is_unknown=False, generated_at="t1", model="m")
    second = RCAEntry(rca_id="2", root_cause="B", confidence="high", supporting_evidence=[],
                       suggested_action="", is_unknown=False, generated_at="t2", model="m")

    br.add_rca(first)
    br.add_rca(second)

    assert br.rca_history == [first, second]
    assert br.current_rca is second
    assert br.rca_history[0].root_cause == "A"  # original preserved verbatim
