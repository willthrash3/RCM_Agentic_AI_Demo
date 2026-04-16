"""Integration tests for the KPI API routes."""

from __future__ import annotations


def test_dashboard_ok(api_client, auth_headers):
    r = api_client.get("/api/v1/kpis/dashboard", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "cards" in body
    assert isinstance(body["cards"], list)
    assert "agent_activity_ticker" in body


def test_timeseries_known_metric(api_client, auth_headers):
    r = api_client.get("/api/v1/kpis/timeseries/days_in_ar", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["metric"] == "days_in_ar"
    assert "points" in body
    assert isinstance(body["points"], list)


def test_ar_aging(api_client, auth_headers):
    r = api_client.get("/api/v1/kpis/ar-aging", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "snapshot_date" in body
    assert "buckets" in body
    assert "total_ar" in body


def test_denial_rate_by_payer(api_client, auth_headers):
    r = api_client.get("/api/v1/kpis/denial-rate-by-payer", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_cash_forecast(api_client, auth_headers):
    r = api_client.get("/api/v1/kpis/cash-forecast", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "total_outstanding" in body
    assert "weekly" in body
