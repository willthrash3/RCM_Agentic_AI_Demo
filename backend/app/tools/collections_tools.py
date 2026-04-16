"""Patient collections tools."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from app.database import get_connection


def get_patient_balances(min_balance: float = 10.0, limit: int = 100) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT e.patient_id, SUM(c.patient_responsibility) AS balance
             FROM claims c
             JOIN encounters e ON c.encounter_id = e.encounter_id
            WHERE c.patient_responsibility > 0
            GROUP BY e.patient_id
           HAVING SUM(c.patient_responsibility) >= ?
            ORDER BY balance DESC
            LIMIT ?""",
        (min_balance, limit),
    ).fetchall()
    return [{"patient_id": r[0], "balance": float(r[1])} for r in rows]


def check_charity_care_eligibility(patient_id: str, balance: float) -> dict[str, Any]:
    """Income-based mock screening — the demo assumes income correlates inversely with propensity."""
    conn = get_connection()
    row = conn.execute(
        "SELECT propensity_score FROM patients WHERE patient_id = ?", (patient_id,)
    ).fetchone()
    if not row:
        return {"eligible": False, "tier": None}
    prop = float(row[0])
    if prop < 0.20 and balance > 500:
        return {"eligible": True, "tier": "100%", "reason": "Low propensity + high balance"}
    if prop < 0.40 and balance > 1500:
        return {"eligible": True, "tier": "50%", "reason": "Low-mid propensity + high balance"}
    return {"eligible": False, "tier": None, "reason": "Does not meet screening criteria"}


def generate_statement(patient_id: str, claim_id: str, balance: float, language: str = "EN") -> str:
    return (
        f"STATEMENT FOR PATIENT {patient_id}\n"
        f"Claim: {claim_id}\nBalance Due: ${balance:.2f}\n"
        f"Payment Plans available. Pay online or call 1-800-555-PAY."
    )


def generate_payment_plan(patient_id: str, balance: float, income_estimate: float | None = None) -> dict[str, Any]:
    months = 3 if balance < 500 else 6 if balance < 2000 else 12
    monthly = round(balance / months, 2)
    return {"patient_id": patient_id, "months": months, "monthly_amount": monthly, "apr": 0.0}


def send_outreach(patient_id: str, channel: str, message_type: str, content: str) -> dict[str, Any]:
    return {
        "outreach_id": f"out-{uuid.uuid4().hex[:8]}",
        "patient_id": patient_id,
        "channel": channel,
        "message_type": message_type,
        "status": "sent",
    }
