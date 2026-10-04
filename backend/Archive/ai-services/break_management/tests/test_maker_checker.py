import pytest
from fastapi.testclient import TestClient

from break_management import service
from break_management.models import BreakManagementError
from break_management.permissions import PermissionDeniedError


# ---------- service-level ----------

def test_investigator_submits_cause(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id

    br = service.submit_investigator_cause(
        break_id, cause="FA missed a late-day adjustment.", actor="jane", role="INVESTIGATOR",
    )

    assert len(br.investigator_findings) == 1
    assert br.investigator_findings[0].cause == "FA missed a late-day adjustment."
    assert br.investigator_findings[0].actor == "jane"


def test_approver_role_cannot_submit_cause(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    with pytest.raises(PermissionDeniedError):
        service.submit_investigator_cause(
            created[0].break_id, cause="x", actor="bob", role="APPROVER",
        )


def test_investigator_can_override_ai_rca_and_original_is_preserved(two_source_setup):
    from break_management.tests.conftest import FakeAnthropicClient

    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id

    client = FakeAnthropicClient({
        "root_cause": "GL posted a manual adjustment.", "confidence": "medium",
        "supporting_evidence": [], "suggested_action": "Confirm with GL team.",
    })
    from break_management.rca import run_rca
    run_rca(service.get_break(break_id), client=client)

    br = service.submit_investigator_cause(
        break_id, cause="Actually a timing difference, confirmed with GL.",
        actor="jane", role="INVESTIGATOR", override_rca=True,
    )

    # original AI RCA text is untouched...
    assert br.rca_history[0].root_cause == "GL posted a manual adjustment."
    # ...but is now annotated with the investigator's override
    assert br.rca_history[0].investigator_override["note"] == "Actually a timing difference, confirmed with GL."
    assert br.investigator_findings[0].overrides_rca_id == br.rca_history[0].rca_id


def test_override_rca_requires_existing_rca(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    with pytest.raises(BreakManagementError):
        service.submit_investigator_cause(
            created[0].break_id, cause="x", actor="jane", role="INVESTIGATOR", override_rca=True,
        )


def test_approver_authorizes_break(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.submit_investigator_cause(break_id, cause="Timing diff", actor="jane", role="INVESTIGATOR")
    service.change_status(break_id, "INVESTIGATING", actor="jane")  # existing status machine, reused as-is

    br = service.authorize_break(break_id, actor="bob", role="APPROVER", target_status="RESOLVED", note="Confirmed")

    assert br.status.value == "RESOLVED"
    assert len(br.authorizations) == 1
    assert br.authorizations[0].actor == "bob"
    assert br.authorizations[0].maker_actor == "jane"


def test_investigator_role_cannot_authorize(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.change_status(break_id, "INVESTIGATING", actor="jane")

    with pytest.raises(PermissionDeniedError):
        service.authorize_break(break_id, actor="jane", role="INVESTIGATOR")


def test_maker_cannot_be_checker_even_with_approver_role(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.submit_investigator_cause(break_id, cause="Timing diff", actor="jane", role="INVESTIGATOR")
    service.change_status(break_id, "INVESTIGATING", actor="jane")

    # jane submitted the cause -- even if she is (incorrectly) asserted
    # as an APPROVER here, she must not be able to authorize her own finding.
    with pytest.raises(PermissionDeniedError):
        service.authorize_break(break_id, actor="jane", role="APPROVER")


def test_different_approver_can_authorize_after_maker_checker_block(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.submit_investigator_cause(break_id, cause="Timing diff", actor="jane", role="INVESTIGATOR")
    service.change_status(break_id, "INVESTIGATING", actor="jane")

    br = service.authorize_break(break_id, actor="bob", role="APPROVER")
    assert br.status.value == "RESOLVED"


def test_bulk_authorize_partial_success(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.submit_investigator_cause(break_id, cause="Timing diff", actor="jane", role="INVESTIGATOR")
    service.change_status(break_id, "INVESTIGATING", actor="jane")

    result = service.bulk_authorize(
        [break_id, "does-not-exist"], actor="bob", role="APPROVER", target_status="RESOLVED",
    )

    assert result["authorized"] == [break_id]
    assert len(result["failed"]) == 1
    assert result["failed"][0]["break_id"] == "does-not-exist"


def test_bulk_authorize_requires_approver_role(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    with pytest.raises(PermissionDeniedError):
        service.bulk_authorize([created[0].break_id], actor="jane", role="INVESTIGATOR")


def test_upload_approvals_authorizes_from_file(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.submit_investigator_cause(break_id, cause="Timing diff", actor="jane", role="INVESTIGATOR")
    service.change_status(break_id, "INVESTIGATING", actor="jane")

    content = f"{break_id}: RESOLVED - Confirmed via bulk upload"
    result = service.upload_approvals(content, actor="bob", role="APPROVER")

    assert result["authorized"] == [break_id]
    assert result["authorized_count"] == 1
    assert result["errors"] == []
    br = service.get_break(break_id)
    assert br.status.value == "RESOLVED"
    assert br.authorizations[-1].note == "Confirmed via bulk upload"


def test_upload_approvals_reports_bad_lines_without_failing_whole_batch(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.submit_investigator_cause(break_id, cause="Timing diff", actor="jane", role="INVESTIGATOR")
    service.change_status(break_id, "INVESTIGATING", actor="jane")

    content = f"garbage line with no colon\n{break_id}: RESOLVED"
    result = service.upload_approvals(content, actor="bob", role="APPROVER")

    assert result["authorized"] == [break_id]
    assert len(result["errors"]) == 1


def test_upload_approvals_requires_approver_role(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    with pytest.raises(PermissionDeniedError):
        service.upload_approvals(f"{created[0].break_id}: RESOLVED", actor="jane", role="INVESTIGATOR")


def test_every_maker_checker_action_is_in_the_audit_log(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id
    service.submit_investigator_cause(break_id, cause="Timing diff", actor="jane", role="INVESTIGATOR")
    service.change_status(break_id, "INVESTIGATING", actor="jane")
    service.authorize_break(break_id, actor="bob", role="APPROVER")

    br = service.get_break(break_id)
    actions = [e.action for e in br.audit_log]
    assert "investigator.finding_submitted" in actions
    assert "approver.authorized" in actions


# ---------- API-level ----------

@pytest.fixture
def client():
    from app import app
    return TestClient(app)


def test_api_full_maker_checker_flow(two_source_setup, client):
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]

    resp = client.post(
        f"/breaks/{break_id}/investigator/cause",
        json={"actor": "jane", "role": "INVESTIGATOR", "cause": "FX timing difference"},
    )
    assert resp.status_code == 200
    assert resp.json()["investigator_findings"][0]["cause"] == "FX timing difference"

    client.post(f"/breaks/{break_id}/status", json={"status": "INVESTIGATING", "actor": "jane"})

    resp = client.post(
        f"/breaks/{break_id}/authorize",
        json={"actor": "bob", "role": "APPROVER", "target_status": "RESOLVED"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "RESOLVED"
    assert resp.json()["authorizations"][0]["maker_actor"] == "jane"


def test_api_rejects_wrong_role_with_403(two_source_setup, client):
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]

    resp = client.post(
        f"/breaks/{break_id}/authorize", json={"actor": "jane", "role": "INVESTIGATOR"},
    )
    assert resp.status_code == 403


def test_api_rejects_maker_as_checker_with_403(two_source_setup, client):
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]
    client.post(
        f"/breaks/{break_id}/investigator/cause",
        json={"actor": "jane", "role": "INVESTIGATOR", "cause": "x"},
    )
    client.post(f"/breaks/{break_id}/status", json={"status": "INVESTIGATING", "actor": "jane"})

    resp = client.post(
        f"/breaks/{break_id}/authorize", json={"actor": "jane", "role": "APPROVER"},
    )
    assert resp.status_code == 403


def test_api_bulk_authorize(two_source_setup, client):
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]
    client.post(
        f"/breaks/{break_id}/investigator/cause",
        json={"actor": "jane", "role": "INVESTIGATOR", "cause": "Timing diff"},
    )
    client.post(f"/breaks/{break_id}/status", json={"status": "INVESTIGATING", "actor": "jane"})

    resp = client.post(
        "/breaks/authorize/bulk",
        json={"actor": "bob", "role": "APPROVER", "break_ids": [break_id]},
    )
    assert resp.status_code == 200
    assert resp.json()["authorized"] == [break_id]


def test_api_upload_approvals(two_source_setup, client):
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]
    client.post(
        f"/breaks/{break_id}/investigator/cause",
        json={"actor": "jane", "role": "INVESTIGATOR", "cause": "Timing diff"},
    )
    client.post(f"/breaks/{break_id}/status", json={"status": "INVESTIGATING", "actor": "jane"})

    resp = client.post(
        "/breaks/authorize/upload",
        json={"actor": "bob", "role": "APPROVER", "content": f"{break_id}: RESOLVED - via upload"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorized"] == [break_id]
    assert body["authorized_count"] == 1
