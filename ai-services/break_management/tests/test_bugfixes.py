"""
Regression tests for the bugfix pass on break_management's
Maker-Checker implementation. One section per numbered fix from the
brief, so each fix has an explicit, traceable test (in addition to the
pre-existing test files, which were updated where they exercised the
now-closed loopholes -- see test_service_api.py and
test_maker_checker.py's diffs).
"""

import pytest
from fastapi.testclient import TestClient

from break_management import service
from break_management.models import BreakManagementError, BreakStatus
from break_management.permissions import (
    Action,
    PermissionDeniedError,
    Role,
    require_permission,
)


@pytest.fixture
def client():
    from app import app
    return TestClient(app)


def _investigated_break(mapping_session_id, maker="jane"):
    created = service.analyze_breaks(mapping_session_id=mapping_session_id)
    break_id = created[0].break_id
    service.submit_investigator_cause(break_id, cause="Timing diff", actor=maker, role="INVESTIGATOR")
    service.change_status(break_id, "INVESTIGATING", actor=maker)
    return break_id


# ---------- Fix #1: /status cannot bypass maker-checker ----------

def test_fix1_change_status_rejects_resolved(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.change_status(break_id, "INVESTIGATING", actor="jane")

    with pytest.raises(BreakManagementError):
        service.change_status(break_id, "RESOLVED", actor="jane")


def test_fix1_change_status_rejects_false_positive(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id

    with pytest.raises(BreakManagementError):
        service.change_status(break_id, "FALSE_POSITIVE", actor="jane")


def test_fix1_change_status_still_allows_investigating_and_escalated(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id

    br = service.change_status(break_id, "INVESTIGATING", actor="jane")
    assert br.status == BreakStatus.INVESTIGATING
    br = service.change_status(break_id, "ESCALATED", actor="jane")
    assert br.status == BreakStatus.ESCALATED


def test_fix1_api_status_endpoint_rejects_resolved(two_source_setup, client):
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]

    resp = client.post(f"/breaks/{break_id}/status", json={"status": "RESOLVED", "actor": "jane"})
    assert resp.status_code == 400


# ---------- Fix #2: authorization requires an investigator finding ----------

def test_fix2_authorize_without_finding_rejected(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.change_status(break_id, "INVESTIGATING", actor="jane")  # investigating, but no cause submitted

    with pytest.raises(BreakManagementError):
        service.authorize_break(break_id, actor="bob", role="APPROVER")


def test_fix2_authorize_succeeds_once_finding_exists(two_source_setup):
    break_id = _investigated_break(two_source_setup)
    br = service.authorize_break(break_id, actor="bob", role="APPROVER")
    assert br.status == BreakStatus.RESOLVED


# ---------- Fix #3: maker != checker ----------

def test_fix3_same_actor_cannot_be_maker_and_checker(two_source_setup):
    break_id = _investigated_break(two_source_setup, maker="jane")
    with pytest.raises(PermissionDeniedError):
        service.authorize_break(break_id, actor="jane", role="APPROVER")


def test_fix3_different_actor_can_authorize(two_source_setup):
    break_id = _investigated_break(two_source_setup, maker="jane")
    br = service.authorize_break(break_id, actor="bob", role="APPROVER")
    assert br.status == BreakStatus.RESOLVED


# ---------- Fix #4: approval target status restricted ----------

@pytest.mark.parametrize("bad_status", ["INVESTIGATING", "OPEN", "ESCALATED", "NOT_A_STATUS"])
def test_fix4_authorize_rejects_non_approval_statuses(two_source_setup, bad_status):
    break_id = _investigated_break(two_source_setup)
    with pytest.raises(BreakManagementError):
        service.authorize_break(break_id, actor="bob", role="APPROVER", target_status=bad_status)


@pytest.mark.parametrize("good_status", ["RESOLVED", "FALSE_POSITIVE"])
def test_fix4_authorize_accepts_approval_statuses(two_source_setup, good_status):
    break_id = _investigated_break(two_source_setup)
    br = service.authorize_break(break_id, actor="bob", role="APPROVER", target_status=good_status)
    assert br.status.value == good_status


# ---------- Fix #5: empty/whitespace investigator causes rejected ----------

@pytest.mark.parametrize("bad_cause", ["", "   ", "\n\t"])
def test_fix5_empty_cause_rejected(two_source_setup, bad_cause):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    with pytest.raises(BreakManagementError):
        service.submit_investigator_cause(break_id, cause=bad_cause, actor="jane", role="INVESTIGATOR")


def test_fix5_cause_is_stripped(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    br = service.submit_investigator_cause(
        break_id, cause="  Timing diff  ", actor="jane", role="INVESTIGATOR",
    )
    assert br.investigator_findings[0].cause == "Timing diff"


# ---------- Fix #6: approval-file format / default_status consistency ----------

def test_fix6_file_line_can_omit_status_and_use_default(two_source_setup):
    break_id = _investigated_break(two_source_setup)
    content = f"{break_id}: - reviewed, no explicit status given"

    result = service.upload_approvals(content, actor="bob", role="APPROVER", default_status="FALSE_POSITIVE")

    assert result["authorized"] == [break_id]
    assert service.get_break(break_id).status == BreakStatus.FALSE_POSITIVE


def test_fix6_bare_break_id_line_omits_status_and_note(two_source_setup):
    from break_management.approval_file import parse_approval_file

    records, errors = parse_approval_file("abc-123:")
    assert errors == []
    assert records == [{"break_id": "abc-123", "status": None, "note": None, "line_number": 1}]


def test_fix6_invalid_default_status_rejected_up_front(two_source_setup):
    break_id = _investigated_break(two_source_setup)
    with pytest.raises(BreakManagementError):
        service.upload_approvals(f"{break_id}:", actor="bob", role="APPROVER", default_status="INVESTIGATING")


# ---------- Fix #7: bulk/file share the exact same rules as single authorize ----------

def test_fix7_bulk_authorize_enforces_finding_required(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id  # no investigator finding submitted

    result = service.bulk_authorize([break_id], actor="bob", role="APPROVER")
    assert result["authorized"] == []
    assert result["failed"][0]["break_id"] == break_id


def test_fix7_bulk_authorize_enforces_maker_checker(two_source_setup):
    break_id = _investigated_break(two_source_setup, maker="jane")
    result = service.bulk_authorize([break_id], actor="jane", role="APPROVER")
    assert result["authorized"] == []
    assert "maker-checker" in result["failed"][0]["error"].lower() or "cannot also authorize" in result["failed"][0]["error"]


def test_fix7_bulk_authorize_enforces_target_status_restriction(two_source_setup):
    break_id = _investigated_break(two_source_setup)
    result = service.bulk_authorize([break_id], actor="bob", role="APPROVER", target_status="ESCALATED")
    assert result["authorized"] == []
    assert len(result["failed"]) == 1


def test_fix7_upload_approvals_enforces_finding_required(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id  # no investigator finding

    result = service.upload_approvals(f"{break_id}: RESOLVED", actor="bob", role="APPROVER")
    assert result["authorized"] == []
    assert len(result["errors"]) == 1


def test_fix7_upload_approvals_enforces_maker_checker(two_source_setup):
    break_id = _investigated_break(two_source_setup, maker="jane")
    result = service.upload_approvals(f"{break_id}: RESOLVED", actor="jane", role="APPROVER")
    assert result["authorized"] == []
    assert len(result["errors"]) == 1


def test_fix7_upload_approvals_enforces_target_status_restriction(two_source_setup):
    break_id = _investigated_break(two_source_setup)
    result = service.upload_approvals(f"{break_id}: ESCALATED", actor="bob", role="APPROVER")
    assert result["authorized"] == []
    assert len(result["errors"]) == 1


# ---------- Fix #8: role resolution is a swappable seam, not a trusted client value ----------

def test_fix8_unknown_claimed_role_is_rejected():
    with pytest.raises(PermissionDeniedError):
        require_permission("mallory", "SUPERUSER", Action.AUTHORIZE_BREAK)


def test_fix8_role_resolver_is_swappable_without_touching_require_permission():
    """Demonstrates the seam: replacing permissions.ROLE_RESOLVER changes
    what role an actor resolves to WITHOUT require_permission's contract,
    service.py, or api.py changing at all -- this is what "ready for
    trusted auth/RBAC integration" means in practice."""
    import break_management.permissions as permissions

    original_resolver = permissions.ROLE_RESOLVER
    try:
        # a "trusted" resolver that ignores the claimed role entirely and
        # looks the actor up in its own (here, hardcoded-for-the-test) map
        trusted_roles = {"jane": Role.INVESTIGATOR, "bob": Role.APPROVER}

        def trusted_resolver(actor, claimed_role):
            if actor not in trusted_roles:
                raise PermissionDeniedError(f"{actor} has no trusted role assignment")
            return trusted_roles[actor]

        permissions.ROLE_RESOLVER = trusted_resolver

        # jane claims APPROVER in the request, but the trusted resolver
        # still resolves her to INVESTIGATOR and the check is denied --
        # proving the claimed value is no longer authoritative.
        with pytest.raises(PermissionDeniedError):
            require_permission("jane", "APPROVER", Action.AUTHORIZE_BREAK)

        # her real (trusted) role still works for what it's permitted to do
        assert require_permission("jane", "irrelevant-claim", Action.SUBMIT_CAUSE) == Role.INVESTIGATOR
    finally:
        permissions.ROLE_RESOLVER = original_resolver


def test_fix8_permission_audit_log_records_role_source():
    from break_management.permissions import PERMISSION_AUDIT_LOG

    require_permission("jane", "INVESTIGATOR", Action.SUBMIT_CAUSE)
    assert PERMISSION_AUDIT_LOG[-1]["role_source"] == "client_claimed"


# ---------- Fix #9: existing functionality preserved end-to-end ----------

def test_fix9_full_lifecycle_still_works_end_to_end(two_source_setup):
    """RCA history, audit logging, reconciliation, prioritization,
    lineage, and the status machine all still work together after the
    bugfix pass -- exercised as one connected flow, not just unit by unit."""
    from break_management.tests.conftest import FakeAnthropicClient

    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    br = service.get_break(break_id)

    # reconciliation + prioritization already ran during analyze_breaks
    assert br.priority is not None
    assert br.differences

    # RCA
    fake_client = FakeAnthropicClient({
        "root_cause": "GL posted a manual adjustment.", "confidence": "medium",
        "supporting_evidence": [], "suggested_action": "Confirm with GL team.",
    })
    from break_management.rca import run_rca
    run_rca(br, client=fake_client)
    assert len(br.rca_history) == 1

    # lineage
    lineage = service.get_lineage(break_id)
    assert lineage["nodes"] and lineage["edges"]

    # investigator cause + override, preserving original RCA
    service.submit_investigator_cause(
        break_id, cause="Timing diff, not a reclass", actor="jane", role="INVESTIGATOR", override_rca=True,
    )
    assert br.rca_history[0].root_cause == "GL posted a manual adjustment."  # untouched
    assert br.rca_history[0].investigator_override is not None

    # status machine (existing path)
    service.change_status(break_id, "INVESTIGATING", actor="jane")

    # maker-checker authorization (new path)
    br = service.authorize_break(break_id, actor="bob", role="APPROVER")
    assert br.status == BreakStatus.RESOLVED

    # audit trail covers every step
    actions = [e.action for e in br.audit_log]
    for expected in (
        "break.detected", "priority.scored", "rca.generated", "lineage.built",
        "investigator.finding_submitted", "rca.overridden", "status.changed", "approver.authorized",
    ):
        assert expected in actions, f"missing audit action: {expected}"
