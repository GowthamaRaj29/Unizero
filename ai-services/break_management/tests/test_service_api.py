import pytest
from fastapi.testclient import TestClient

from break_management import service
from break_management.models import BreakManagementError, BreakStatus
from break_management.tests.conftest import FakeAnthropicClient


# ---------- service-level ----------

def test_analyze_breaks_creates_only_genuine_breaks(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)

    # T1 matches cleanly across FA/GL -- must not become a break.
    assert len(created) == 1
    assert created[0].break_key == "T2"
    assert created[0].status == BreakStatus.OPEN
    assert created[0].priority is not None  # deterministic score always attached


def test_analyze_breaks_is_idempotent_for_still_open_breaks(two_source_setup):
    first = service.analyze_breaks(mapping_session_id=two_source_setup)
    second = service.analyze_breaks(mapping_session_id=two_source_setup)

    assert len(first) == 1
    assert len(second) == 0  # T2 is already OPEN, not recreated
    assert len(service.BREAKS) == 1


def test_analyze_breaks_unknown_mapping_session_raises():
    with pytest.raises(BreakManagementError):
        service.analyze_breaks(mapping_session_id="does-not-exist")


def test_status_transition_state_machine(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id

    br = service.change_status(break_id, "INVESTIGATING", actor="jane")
    assert br.status == BreakStatus.INVESTIGATING

    # Bugfix #1: RESOLVED can no longer be set through change_status --
    # it must go through the maker-checker authorize_break path.
    with pytest.raises(BreakManagementError):
        service.change_status(break_id, "RESOLVED", actor="jane", note="Confirmed FX timing diff")

    service.submit_investigator_cause(break_id, cause="Timing diff", actor="jane", role="INVESTIGATOR")
    br = service.authorize_break(break_id, actor="bob", role="APPROVER", note="Confirmed FX timing diff")
    assert br.status == BreakStatus.RESOLVED

    # RESOLVED -> ESCALATED is not an allowed direct transition
    with pytest.raises(BreakManagementError):
        service.change_status(break_id, "ESCALATED", actor="jane")


def test_status_transition_unknown_status_rejected(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    with pytest.raises(BreakManagementError):
        service.change_status(created[0].break_id, "NOT_A_STATUS", actor="jane")


def test_investigator_override_requires_existing_rca(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    break_id = created[0].break_id

    # no RCA has run yet -- overriding must fail rather than fabricate one
    with pytest.raises(BreakManagementError):
        service.change_status(
            break_id, "INVESTIGATING", actor="jane", note="disagree",
            investigator_disagrees=True,
        )


def test_lineage_available_for_a_break(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    lineage = service.get_lineage(created[0].break_id)
    assert lineage["nodes"]
    assert lineage["edges"]


def test_get_summary_counts_by_status_and_type(two_source_setup):
    created = service.analyze_breaks(mapping_session_id=two_source_setup)
    service.change_status(created[0].break_id, "INVESTIGATING", actor="jane")

    summary = service.get_summary()
    assert summary["total"] == 1
    assert summary["by_status"]["INVESTIGATING"] == 1
    assert "AMOUNT_MISMATCH" in summary["by_break_type"]


# ---------- API-level ----------

@pytest.fixture
def client():
    from app import app
    return TestClient(app)


def test_api_analyze_and_list_and_detail(two_source_setup, client):
    resp = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup})
    assert resp.status_code == 200
    created = resp.json()
    assert len(created) == 1
    break_id = created[0]["break_id"]

    resp = client.get("/breaks")
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = client.get(f"/breaks/{break_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["break_key"] == "T2"
    assert detail["differences"]


def test_api_unknown_break_returns_404(client):
    resp = client.get("/breaks/does-not-exist")
    assert resp.status_code == 404


def test_api_status_change_and_invalid_transition(two_source_setup, client):
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]

    resp = client.post(f"/breaks/{break_id}/status", json={"status": "INVESTIGATING", "actor": "jane"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "INVESTIGATING"

    resp = client.post(f"/breaks/{break_id}/status", json={"status": "NOT_REAL", "actor": "jane"})
    assert resp.status_code == 400


def test_api_lineage_endpoint(two_source_setup, client):
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]

    resp = client.get(f"/breaks/{break_id}/lineage")
    assert resp.status_code == 200
    body = resp.json()
    assert body["nodes"] and body["edges"]


def test_api_summary_endpoint(two_source_setup, client):
    client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup})
    resp = client.get("/breaks/summary")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_api_rca_endpoint_uses_mocked_anthropic_client(two_source_setup, client, monkeypatch):
    """The API layer resolves its own anthropic.Anthropic() client (see
    explain.explain_reconciliation_break), so this test mocks at that
    boundary -- the lowest point shared by the API, service, and rca
    layers -- rather than needing a real ANTHROPIC_API_KEY."""
    created = client.post("/breaks/analyze", json={"mapping_session_id": two_source_setup}).json()
    break_id = created[0]["break_id"]

    fake_client = FakeAnthropicClient({
        "root_cause": "GL posted a manual adjustment not reflected in FA.",
        "confidence": "medium",
        "supporting_evidence": ["Amount differs by 749.0"],
        "suggested_action": "Ask GL team to confirm the adjustment.",
    })
    monkeypatch.setattr("explain.anthropic.Anthropic", lambda: fake_client)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    resp = client.post(f"/breaks/{break_id}/rca", json={"actor": "jane"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_rca"]["root_cause"] == "GL posted a manual adjustment not reflected in FA."
    assert len(body["rca_history"]) == 1
