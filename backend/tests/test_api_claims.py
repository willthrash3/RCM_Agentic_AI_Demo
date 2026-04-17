"""Integration tests for the claims API routes."""

from __future__ import annotations

import pytest
from datetime import date


@pytest.fixture(scope="module", autouse=True)
def seed_claim_rows(_seed):
    from app.database import get_connection
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-test-1", "pt-test-1", "1234567890", "0987654321", "Outpatient",
         date(2026, 4, 1), date(2026, 4, 1), "11", "Dr. Test", "HTN", "note", "htn_mgmt",
         False, "Not Required", 1, "Coded"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-test-1", "enc-test-1", "837P", "payer-001", 200, 150, 120, 30,
         None, None, "Draft", None, None, None, None, False),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("line-test-1", "clm-test-1", "99214", "I10", None, None, 1, 200, 150,
         None, None, None),
    )


def test_list_claims_ok(api_client, auth_headers):
    r = api_client.get("/api/v1/claims", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "page" in body
    assert "items" in body


def test_list_claims_no_auth(api_client):
    r = api_client.get("/api/v1/claims")
    assert r.status_code == 401


def test_list_claims_filter_by_status(api_client, auth_headers):
    r = api_client.get("/api/v1/claims?status=Draft", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["claim_status"] == "Draft"


def test_list_claims_pagination(api_client, auth_headers):
    r = api_client.get("/api/v1/claims?page=1&page_size=5", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["page_size"] == 5
    assert len(body["items"]) <= 5


def test_list_claims_combined_filter_no_crash(api_client, auth_headers):
    r = api_client.get(
        "/api/v1/claims?payer_id=payer-001&date_from=2025-01-01",
        headers=auth_headers,
    )
    assert r.status_code == 200


def test_get_claim_known(api_client, auth_headers):
    r = api_client.get("/api/v1/claims/clm-test-1", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["claim_id"] == "clm-test-1"
    assert "lines" in body


def test_get_claim_not_found(api_client, auth_headers):
    r = api_client.get("/api/v1/claims/clm-does-not-exist-xyz", headers=auth_headers)
    assert r.status_code == 404


def test_get_claim_trace(api_client, auth_headers):
    r = api_client.get("/api/v1/claims/clm-test-1/trace", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
