"""Integration tests for the scenarios API routes."""

from __future__ import annotations


def test_list_scenarios(api_client, auth_headers):
    r = api_client.get("/api/v1/scenarios", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    if body:
        s = body[0]
        assert "scenario_id" in s
        assert "name" in s
        assert "description" in s
        assert "expected_outcome" in s


def test_run_scenario_bad_id(api_client, auth_headers):
    r = api_client.post(
        "/api/v1/scenarios/run",
        json={"scenario_id": "this-scenario-does-not-exist-xyz"},
        headers=auth_headers,
    )
    assert r.status_code == 404


def test_run_scenario_missing_field(api_client, auth_headers):
    r = api_client.post(
        "/api/v1/scenarios/run",
        json={},
        headers=auth_headers,
    )
    assert r.status_code == 400
