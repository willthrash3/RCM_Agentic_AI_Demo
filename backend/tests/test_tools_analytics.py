"""Unit tests for analytics_tools."""

from __future__ import annotations

def test_get_ar_aging_snapshot_returns_structure():
    from app.tools.analytics_tools import get_ar_aging_snapshot
    result = get_ar_aging_snapshot()
    assert "snapshot_date" in result
    assert "buckets" in result
    assert "total_ar" in result
    assert "overall_days_in_ar" in result


def test_get_ar_aging_snapshot_empty_db_no_crash():
    from app.tools.analytics_tools import get_ar_aging_snapshot
    # Even with an empty ar_aging_snapshot table, should not raise
    result = get_ar_aging_snapshot()
    assert isinstance(result["buckets"], list)
    assert result["total_ar"] >= 0.0


def test_get_kpi_timeseries_known_metric():
    from app.tools.analytics_tools import get_kpi_timeseries
    points = get_kpi_timeseries("days_in_ar", 7)
    assert isinstance(points, list)
    assert len(points) == 8  # days_back + 1
    assert all("date" in p and "value" in p for p in points)


def test_get_kpi_timeseries_unknown_metric_returns_zeros():
    from app.tools.analytics_tools import get_kpi_timeseries
    points = get_kpi_timeseries("unknown_metric_xyz", 3)
    assert len(points) == 4
    assert all(p["value"] == 0.0 for p in points)


def test_get_denial_rate_by_payer_returns_list():
    from app.tools.analytics_tools import get_denial_rate_by_payer
    result = get_denial_rate_by_payer(30)
    assert isinstance(result, list)
    for item in result:
        assert "payer_id" in item
        assert 0.0 <= item["denial_rate"] <= 1.0


def test_get_first_pass_rate_returns_float():
    from app.tools.analytics_tools import get_first_pass_rate
    rate = get_first_pass_rate(30)
    assert isinstance(rate, float)
    assert 0.0 <= rate <= 1.0


def test_compute_cash_forecast_structure():
    from app.tools.analytics_tools import compute_cash_forecast
    result = compute_cash_forecast(90)
    assert "total_outstanding" in result
    assert "weekly" in result
    assert isinstance(result["weekly"], list)
    assert len(result["weekly"]) == 12  # 90 // 7 = 12


def test_write_analytics_alert_persists():
    from app.tools.analytics_tools import write_analytics_alert
    from app.database import get_connection
    alert_id = write_analytics_alert("days_in_ar", "critical", "test alert from pytest")
    assert alert_id.startswith("alert-")
    conn = get_connection()
    row = conn.execute(
        "SELECT alert_id FROM kpi_alerts WHERE alert_id = ?", (alert_id,)
    ).fetchone()
    assert row is not None
    assert row[0] == alert_id
