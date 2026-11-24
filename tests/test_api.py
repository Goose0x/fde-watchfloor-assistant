from __future__ import annotations

from fastapi.testclient import TestClient

from watchfloor.pii import contains_raw_pii


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_requires_user(client: TestClient) -> None:
    response = client.post("/ask", json={"query": "site hours"})
    assert response.status_code == 401


def test_ask_as_ops_lead_does_not_return_finance_chunks(client: TestClient) -> None:
    response = client.post(
        "/ask",
        json={"query": "Harborline Carriers payment memo"},
        headers={"X-User-Id": "ops-lead"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "finance-vendor-memo" not in body["citations"]
    assert not contains_raw_pii(body["model_prompt"])


def test_share_and_approve_via_http(client: TestClient) -> None:
    created = client.post(
        "/actions/share",
        json={"summary": "Share the visitor desk hours with Harborline Carriers"},
        headers={"X-User-Id": "ops-lead"},
    )
    assert created.status_code == 200
    approval_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    forbidden = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reason": "nope"},
        headers={"X-User-Id": "ops-lead"},
    )
    assert forbidden.status_code == 403

    approved = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reason": "Packet is unclassified and already public on the desk"},
        headers={"X-User-Id": "approver"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    listed = client.get("/audit")
    assert listed.status_code == 200
    actions = [entry["action"] for entry in listed.json()]
    assert "approval_requested" in actions
    assert "approval_decided" in actions
