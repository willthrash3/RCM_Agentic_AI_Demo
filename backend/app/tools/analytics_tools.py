"""Analytics / KPI tools."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.database import get_connection, transaction


def get_ar_aging_snapshot(as_of_date: date | None = None) -> dict[str, Any]:
    conn = get_connection()
    if as_of_date is None:
        row = conn.execute("SELECT MAX(snapshot_date) FROM ar_aging_snapshot").fetchone()
        as_of_date = row[0] if row and row[0] else date.today()
    rows = conn.execute(
        """SELECT payer_id, bucket_0_30, bucket_31_60, bucket_61_90,
                  bucket_91_120, bucket_over_120, total_ar, days_in_ar
             FROM ar_aging_snapshot WHERE snapshot_date = ?""",
        (as_of_date,),
    ).fetchall()
    buckets = [
        {
            "payer_id": r[0], "bucket_0_30": float(r[1]), "bucket_31_60": float(r[2]),
            "bucket_61_90": float(r[3]), "bucket_91_120": float(r[4]),
            "bucket_over_120": float(r[5]), "total_ar": float(r[6]), "days_in_ar": float(r[7]),
        }
        for r in rows
    ]
    total = sum(b["total_ar"] for b in buckets)
    days = sum(b["days_in_ar"] * b["total_ar"] for b in buckets) / total if total else 0
    return {
        "snapshot_date": str(as_of_date),
        "buckets": buckets,
        "total_ar": total,
        "overall_days_in_ar": round(days, 1),
    }


def get_kpi_timeseries(metric: str, days_back: int = 30) -> list[dict[str, Any]]:
    conn = get_connection()
    today = date.today()
    points: list[dict[str, Any]] = []
    for i in range(days_back, -1, -1):
        d = today - timedelta(days=i)
        if metric == "days_in_ar":
            row = conn.execute(
                """SELECT SUM(total_ar * days_in_ar) / NULLIF(SUM(total_ar), 0)
                     FROM ar_aging_snapshot WHERE snapshot_date = ?""",
                (d,),
            ).fetchone()
            value = float(row[0]) if row and row[0] else 0.0
        elif metric == "denial_rate":
            row = conn.execute(
                """SELECT COUNT(*) FILTER (WHERE claim_status = 'Denied')::DOUBLE /
                          NULLIF(COUNT(*) FILTER (WHERE claim_status IN ('Submitted','Paid','Denied','Appealed')), 0)
                     FROM claims WHERE submission_date = ?""",
                (d,),
            ).fetchone()
            value = float(row[0]) if row and row[0] else 0.0
        elif metric == "first_pass_rate":
            row = conn.execute(
                """SELECT COUNT(*) FILTER (WHERE claim_status IN ('Paid', 'Submitted'))::DOUBLE /
                          NULLIF(COUNT(*) FILTER (WHERE submission_date IS NOT NULL), 0)
                     FROM claims WHERE submission_date = ?""",
                (d,),
            ).fetchone()
            value = float(row[0]) if row and row[0] else 0.0
        elif metric == "cash_forecast":
            # Forward-looking: use historical avg_days_to_pay trend
            value = 0.0
        else:
            value = 0.0
        points.append({"date": str(d), "value": round(value, 4)})
    return points


def get_denial_rate_by_payer(period_days: int = 30) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT payer_id,
                  COUNT(*) FILTER (WHERE claim_status = 'Denied')::DOUBLE /
                  NULLIF(COUNT(*), 0) AS rate,
                  COUNT(*) AS total
             FROM claims
            WHERE submission_date >= ?
            GROUP BY payer_id
            ORDER BY rate DESC""",
        (date.today() - timedelta(days=period_days),),
    ).fetchall()
    return [{"payer_id": r[0], "denial_rate": float(r[1] or 0), "total_claims": r[2]} for r in rows]


def get_first_pass_rate(period_days: int = 30) -> float:
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) FILTER (WHERE claim_status IN ('Paid', 'Submitted'))::DOUBLE /
                  NULLIF(COUNT(*), 0)
             FROM claims
            WHERE submission_date >= ?""",
        (date.today() - timedelta(days=period_days),),
    ).fetchone()
    return float(row[0]) if row and row[0] else 0.0


def get_days_in_ar_by_payer() -> list[dict[str, Any]]:
    conn = get_connection()
    row = conn.execute("SELECT MAX(snapshot_date) FROM ar_aging_snapshot").fetchone()
    if not row or not row[0]:
        return []
    rows = conn.execute(
        """SELECT payer_id, days_in_ar, total_ar
             FROM ar_aging_snapshot WHERE snapshot_date = ?
            ORDER BY days_in_ar DESC""",
        (row[0],),
    ).fetchall()
    return [{"payer_id": r[0], "days_in_ar": float(r[1]), "total_ar": float(r[2])} for r in rows]


def compute_cash_forecast(days_horizon: int = 90) -> dict[str, Any]:
    conn = get_connection()
    row = conn.execute(
        """SELECT SUM(total_billed - COALESCE(total_paid, 0))
             FROM claims WHERE claim_status IN ('Submitted', 'Paid')"""
    ).fetchone()
    outstanding = float(row[0]) if row and row[0] else 0.0
    # Simple linear model: assume collection rate of 0.96 spread evenly over horizon
    weekly_buckets = days_horizon // 7
    weekly = outstanding * 0.96 / weekly_buckets if weekly_buckets else 0.0
    points = [
        {"week": i + 1, "projected_collections": round(weekly, 2),
         "lower_band": round(weekly * 0.85, 2), "upper_band": round(weekly * 1.15, 2)}
        for i in range(weekly_buckets)
    ]
    return {"total_outstanding": outstanding, "weekly": points}


def write_analytics_alert(
    alert_type: str,
    severity: str,
    description: str,
    affected_entities: list[str] | None = None,
) -> str:
    alert_id = f"alert-{uuid.uuid4().hex[:10]}"
    with transaction() as conn:
        conn.execute(
            """INSERT INTO kpi_alerts VALUES (?,?,?,?,?,?,?)""",
            (alert_id, alert_type, severity, description,
             ",".join(affected_entities or []), datetime.utcnow(), None),
        )
    return alert_id
