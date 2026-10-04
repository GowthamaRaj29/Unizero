from fastapi.testclient import TestClient

import main


def test_health_and_root_endpoints_start():
    with TestClient(main.app) as client:
        health_response = client.get("/health")
        root_response = client.get("/")

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert root_response.status_code == 200
    assert root_response.json()["status"] == "running"
