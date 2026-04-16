"""Smoke tests — assert the app starts and routes are registered."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_app_starts() -> None:
    from app.main import app
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "RCM Agentic AI Demo"


def test_healthz() -> None:
    from app.main import app
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200


def test_api_key_required() -> None:
    from app.main import app
    client = TestClient(app)
    r = client.get("/api/v1/patients")
    assert r.status_code == 401


def test_mock_eligibility() -> None:
    from app.main import app
    client = TestClient(app)
    r = client.get("/mock/payer/MCR01/eligibility", params={
        "patient_id": "pt-00001", "service_date": "2026-04-15"
    })
    assert r.status_code in (200, 503)  # may simulate error
