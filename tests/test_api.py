from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_orchestrator.engine.orchestrator import Orchestrator, load_flows
from agent_orchestrator.main import build_app

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    orch = Orchestrator()
    orch._flows = load_flows(str(REPO_ROOT / "data" / "flows.json"))
    app = build_app(orch)
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["flows"] >= 1
    assert data["tools"] >= 1


def test_flows_and_tools(client):
    assert client.get("/flows").status_code == 200
    assert any(f["id"] == "invoice-reimbursement" for f in client.get("/flows").json())
    assert client.get("/tools").status_code == 200


def test_run_and_approve(client):
    r = client.post(
        "/run",
        json={"flow_id": "invoice-reimbursement", "role": "finance",
              "inputs": {"file": "invoice_15000.00.pdf"}},
    )
    assert r.status_code == 200
    rep = r.json()
    assert rep["status"] == "WAITING_APPROVAL"
    run_id = rep["run_id"]

    r2 = client.post("/approve", json={"run_id": run_id, "approver": "lead"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "SUCCEEDED"

    r3 = client.get(f"/runs/{run_id}/report")
    assert r3.status_code == 200
    assert r3.json()["status"] == "SUCCEEDED"


def test_run_flow_level_permission(client):
    r = client.post(
        "/run",
        json={"flow_id": "invoice-reimbursement", "role": "viewer",
              "inputs": {"file": "invoice_100.pdf"}},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ABORTED"


def test_export_plan_markdown(client):
    r = client.post(
        "/run",
        json={"flow_id": "invoice-reimbursement", "role": "finance",
              "inputs": {"file": "invoice_15000.00.pdf"}},
    )
    run_id = r.json()["run_id"]
    client.post("/approve", json={"run_id": run_id})
    r3 = client.post("/export-plan", json={"run_id": run_id, "fmt": "markdown"})
    assert r3.status_code == 200
    assert "方案包" in r3.json()["markdown"]


def test_unknown_flow_404(client):
    r = client.post("/run", json={"flow_id": "nope", "role": "finance"})
    assert r.status_code == 404
