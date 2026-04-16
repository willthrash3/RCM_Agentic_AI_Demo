"""Patient-level tools."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.database import locked


def get_patient_demographics(patient_id: str) -> dict[str, Any]:
    with locked() as conn:
        row = conn.execute(
            """SELECT patient_id, first_name, last_name, dob, gender, address_line1,
                      city, state, zip_code, phone, email, mrn, language_pref, is_self_pay
                 FROM patients WHERE patient_id = ?""",
            (patient_id,),
        ).fetchone()
    if not row:
        return {}
    cols = ["patient_id", "first_name", "last_name", "dob", "gender", "address_line1",
            "city", "state", "zip_code", "phone", "email", "mrn", "language_pref", "is_self_pay"]
    return dict(zip(cols, row))


def get_patient_insurance(patient_id: str) -> list[dict[str, Any]]:
    with locked() as conn:
        row = conn.execute(
            """SELECT primary_payer_id, secondary_payer_id FROM patients WHERE patient_id = ?""",
            (patient_id,),
        ).fetchone()
    if not row:
        return []
    insurances = []
    if row[0]:
        insurances.append({"payer_id": row[0], "priority": "primary"})
    if row[1]:
        insurances.append({"payer_id": row[1], "priority": "secondary"})
    return insurances


def get_patient_contact_preferences(patient_id: str) -> dict[str, Any]:
    with locked() as conn:
        row = conn.execute(
            """SELECT phone, email, language_pref FROM patients WHERE patient_id = ?""",
            (patient_id,),
        ).fetchone()
    if not row:
        return {}
    return {
        "phone": row[0], "email": row[1], "language_pref": row[2],
        "preferred_channel": "email" if row[1] else "phone",
    }


def get_patient_propensity(patient_id: str) -> float:
    with locked() as conn:
        row = conn.execute(
            "SELECT propensity_score FROM patients WHERE patient_id = ?", (patient_id,)
        ).fetchone()
    return float(row[0]) if row else 0.5
