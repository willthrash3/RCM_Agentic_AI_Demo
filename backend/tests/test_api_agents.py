"""Integration tests for the agents API routes."""

from __future__ import annotations


def test_run_coding_queues_task(api_client, auth_headers):
    r = api_client.post(
        "/api/v1/agents/coding/run",
        json={"encounter_id": "enc-test-1"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "task_id" in body
    assert body["status"] == "queued"
    assert body["agent_name"] == "coding_agent"


def test_run_coding_missing_encounter_id(api_client, auth_headers):
    r = api_client.post(
        "/api/v1/agents/coding/run",
        json={},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_run_eligibility_missing_patient_id(api_client, auth_headers):
    r = api_client.post(
        "/api/v1/agents/eligibility/run",
        json={},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_run_denial_missing_denial_id(api_client, auth_headers):
    r = api_client.post(
        "/api/v1/agents/denial/run",
        json={},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_list_tasks(api_client, auth_headers):
    r = api_client.get("/api/v1/agents/tasks", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_task_not_found(api_client, auth_headers):
    r = api_client.get(
        "/api/v1/agents/tasks/task-does-not-exist-xyz",
        headers=auth_headers,
    )
    assert r.status_code == 404
