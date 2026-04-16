"""Integration tests for the patients API routes."""

from __future__ import annotations

import pytest
from datetime import date


@pytest.fixture(scope="module", autouse=True)
def seed_patient_rows():
    from app.database import get_connection
    conn = get_connection()
    # patients columns: patient_id, first_name, last_name, dob, gender,
    # address_line1, city, state, zip_code, phone, email, mrn,
    # primary_payer_id, secondary_payer_id, propensity_score, language_pref, created_at
    conn.execute(
        """INSERT OR REPLACE INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("pt-api-test-1", "John", "Apitester", date(1980, 5, 15), "M",
         "123 Main St", "Springfield", "IL", "62701", "555-1234",
         "john@test.com", "MRN-API-001", "payer-001", None, 0.72, "EN", None),
    )


def test_list_patients_ok(api_client, auth_headers):
    r = api_client.get("/api/v1/patients", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "items" in body


def test_list_patients_no_auth(api_client):
    r = api_client.get("/api/v1/patients")
    assert r.status_code == 401


def test_list_patients_search_no_crash(api_client, auth_headers):
    r = api_client.get("/api/v1/patients?search=Apitester", headers=auth_headers)
    assert r.status_code == 200


def test_list_patients_pagination(api_client, auth_headers):
    r = api_client.get("/api/v1/patients?page_size=2", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) <= 2


def test_get_patient_known(api_client, auth_headers):
    r = api_client.get("/api/v1/patients/pt-api-test-1", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["patient_id"] == "pt-api-test-1"


def test_get_patient_not_found(api_client, auth_headers):
    r = api_client.get("/api/v1/patients/pt-does-not-exist-xyz", headers=auth_headers)
    assert r.status_code == 404
