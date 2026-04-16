"""Integration tests for the HITL queue API routes."""

from __future__ import annotations

from datetime import datetime

import pytest


@pytest.fixture(scope="module", autouse=True)
def seed_hitl_task():
    from app.database import get_connection
    conn = get_connection()
    # hitl_tasks columns: task_id, agent_name, entity_type, entity_id,
    # task_description, priority, recommended_action, agent_reasoning,
    # status, created_at, resolved_at, decision, notes
    conn.execute(
        """INSERT OR REPLACE INTO hitl_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("task-api-test-1", "coding_agent", "encounter", "enc-test-1",
         "Review coding suggestion", "Medium", "approve",
         "High confidence match", "pending", datetime.utcnow(), None, None, None),
    )


def test_list_queue_ok(api_client, auth_headers):
    r = api_client.get("/api/v1/hitl/queue", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)


def test_list_queue_no_auth(api_client):
    r = api_client.get("/api/v1/hitl/queue")
    assert r.status_code == 401


def test_list_queue_filter_by_status(api_client, auth_headers):
    r = api_client.get("/api/v1/hitl/queue?status=pending", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    task_ids = [t["task_id"] for t in body]
    assert "task-api-test-1" in task_ids


def test_resolve_task_approve(api_client, auth_headers):
    r = api_client.post(
        "/api/v1/hitl/task-api-test-1/resolve",
        json={"decision": "approve", "notes": "Looks good"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "approved"
    assert body["task_id"] == "task-api-test-1"


def test_resolve_task_not_found(api_client, auth_headers):
    r = api_client.post(
        "/api/v1/hitl/task-does-not-exist-xyz/resolve",
        json={"decision": "approve"},
        headers=auth_headers,
    )
    assert r.status_code == 404
