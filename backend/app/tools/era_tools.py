"""ERA / payment posting tools."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from app.database import locked, transaction
from app.utils.time import get_demo_today


def get_unposted_eras(limit: int = 25) -> list[dict[str, Any]]:
    """Return pseudo-ERA batches derived from claims marked Paid but not era_posted."""
    with locked() as conn:
        rows = conn.execute(
            """SELECT claim_id, payer_id, total_paid, total_allowed, patient_responsibility
                 FROM claims
                WHERE claim_status = 'Paid' AND era_posted = FALSE
                LIMIT ?""",
            (limit,),
        ).fetchall()
    # Group into fake ERAs of 4 lines each
    eras: list[dict[str, Any]] = []
    for i in range(0, len(rows), 4):
        batch = rows[i : i + 4]
        era_id = f"era-{uuid.uuid4().hex[:8]}"
        eras.append({
            "era_id": era_id,
            "lines": [
                {"claim_id": r[0], "payer_id": r[1], "payment_amount": float(r[2] or 0),
                 "adjustment_amount": float((r[3] or 0) - (r[2] or 0)),
                 "patient_balance": float(r[4] or 0)}
                for r in batch
            ],
        })
    return eras


def get_claim_by_service_info(patient_id: str, service_date: date, cpt_code: str) -> dict[str, Any]:
    with locked() as conn:
        row = conn.execute(
            """SELECT c.claim_id, c.encounter_id, c.total_billed
                 FROM claims c
                 JOIN encounters e ON c.encounter_id = e.encounter_id
                 JOIN claim_lines l ON l.claim_id = c.claim_id
                WHERE e.patient_id = ? AND e.service_date = ? AND l.cpt_code = ?
                LIMIT 1""",
            (patient_id, service_date, cpt_code),
        ).fetchone()
    if not row:
        return {}
    return {"claim_id": row[0], "encounter_id": row[1], "total_billed": row[2]}


def post_payment(
    claim_id: str,
    payment_amount: Decimal,
    adjustment_codes: list[str],
    patient_balance: Decimal,
) -> None:
    with transaction() as conn:
        conn.execute(
            """INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?)""",
            (f"pay-{uuid.uuid4().hex[:10]}", claim_id, get_demo_today(), payment_amount,
             "EFT", None, None, "Posted", False),
        )
        conn.execute(
            """UPDATE claims SET era_posted = TRUE, total_paid = ?,
                   patient_responsibility = ?, claim_status = 'Paid'
             WHERE claim_id = ?""",
            (payment_amount, patient_balance, claim_id),
        )


def create_patient_statement(patient_id: str, claim_id: str, balance_amount: Decimal) -> str:
    statement_id = f"stmt-{uuid.uuid4().hex[:8]}"
    return statement_id


def route_exception(era_id: str, line_id: str | None, reason: str) -> None:
    return None
