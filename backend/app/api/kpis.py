"""KPI dashboard API."""

from __future__ import annotations

from datetime import date, datetime
from fastapi import APIRouter, Depends

from app.agents.analytics import AnalyticsAgent, KPI_CONFIG
from app.api.deps import require_api_key
from app.database import get_connection
from app.tools.analytics_tools import (
    compute_cash_forecast,
    get_ar_aging_snapshot,
    get_denial_rate_by_payer,
    get_kpi_timeseries,
)

router = APIRouter(prefix="/kpis", tags=["kpis"], dependencies=[Depends(require_api_key)])


@router.get("/dashboard")
def dashboard(as_of_date: date | None = None) -> dict:
    agent = AnalyticsAgent()
    cards = []
    for cfg in KPI_CONFIG:
        value = agent._current_value(cfg["name"])
        status = agent._status_for(cfg, value)
        cards.append({
            "name": cfg["label"], "metric": cfg["name"], "value": value,
            "target": cfg["target"], "alert_threshold": cfg["alert"],
            "status": status, "direction_good": cfg["direction"], "unit": cfg["unit"],
        })
    conn = get_connection()
    ticker = conn.execute(
        """SELECT agent_name, action_type, entity_type, entity_id, created_at
             FROM agent_event_log
            ORDER BY created_at DESC LIMIT 20"""
    ).fetchall()
    tcols = ["agent_name", "action_type", "entity_type", "entity_id", "created_at"]
    return {
        "as_of": datetime.utcnow().isoformat() + "Z",
        "cards": cards,
        "agent_activity_ticker": [dict(zip(tcols, r)) for r in ticker],
    }


@router.get("/timeseries/{metric}")
def timeseries(metric: str, days_back: int = 30) -> dict:
    return {"metric": metric, "points": get_kpi_timeseries(metric, days_back)}


@router.get("/ar-aging")
def ar_aging(payer_id: str | None = None) -> dict:
    snapshot = get_ar_aging_snapshot()
    if payer_id:
        snapshot["buckets"] = [b for b in snapshot["buckets"] if b["payer_id"] == payer_id]
    return snapshot


@router.get("/denial-rate-by-payer")
def denial_rate(period_days: int = 30) -> list[dict]:
    return get_denial_rate_by_payer(period_days)


@router.get("/cash-forecast")
def cash_forecast(days_horizon: int = 90) -> dict:
    return compute_cash_forecast(days_horizon)


@router.get("/alerts")
def alerts(limit: int = 25) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT alert_id, alert_type, severity, description, affected_entities,
                  created_at, resolved_at
             FROM kpi_alerts ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    cols = ["alert_id", "alert_type", "severity", "description", "affected_entities",
            "created_at", "resolved_at"]
    return [dict(zip(cols, r)) for r in rows]
