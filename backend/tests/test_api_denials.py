"""Integration tests for the denials API routes."""

from __future__ import annotations

from datetime import date

import pytest


@pytest.fixture(scope="module", autouse=True)
def seed_denial_rows():
    from app.database import get_connection
    conn = get_connection()
    # Ensure the claim clm-test-1 exists (may already exist from other test modules)
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-denial-api-1", "pt-denial-api-1", "1234567890", "0987654321", "Outpatient",
         date(2026, 3, 1), date(2026, 3, 1), "11", "Dr. Denial", "HTN", "note", None,
         False, "Not Required", 1, "Coded"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-denial-api-1", "enc-denial-api-1", "837P", "payer-001", 200, 150, 0, 0,
         date(2026, 3, 5), None, "Denied", None, date(2026, 6, 1), None, None, False),
    )
    # denials columns: denial_id, claim_id, carc_code, rarc_code, denial_category,
    # denial_date, appeal_deadline, agent_root_cause, appeal_letter_text,
    # appeal_submitted_at, overturn_date, overturn_flag
    conn.execute(
        """INSERT OR REPLACE INTO denials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("den-api-test-1", "clm-denial-api-1", "97", None, "Coding / DX",
         date(2026, 3, 10), date(2026, 5, 10), None, None, None, None, False),
    )


def test_list_denials_ok(api_client, auth_headers):
    r = api_client.get("/api/v1/denials", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "items" in body


def test_list_denials_no_auth(api_client):
    r = api_client.get("/api/v1/denials")
    assert r.status_code == 401


def test_list_denials_filter_by_category(api_client, auth_headers):
    r = api_client.get("/api/v1/denials?category=Coding+%2F+DX", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    for item in body["items"]:
        assert item["denial_category"] == "Coding / DX"


def test_denial_summary(api_client, auth_headers):
    r = api_client.get("/api/v1/denials/summary", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "by_category" in body
    assert isinstance(body["by_category"], list)


def test_get_denial_known(api_client, auth_headers):
    r = api_client.get("/api/v1/denials/den-api-test-1", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["denial_id"] == "den-api-test-1"
    assert "carc_description" in body


def test_get_denial_not_found(api_client, auth_headers):
    r = api_client.get("/api/v1/denials/den-does-not-exist-xyz", headers=auth_headers)
    assert r.status_code == 404
