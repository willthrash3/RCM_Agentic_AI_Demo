"""Patients API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_api_key
from app.database import get_connection

router = APIRouter(prefix="/patients", tags=["patients"], dependencies=[Depends(require_api_key)])


@router.get("")
def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: str | None = None,
) -> dict:
    conn = get_connection()
    offset = (page - 1) * page_size
    base_where = "WHERE 1=1"
    args: list = []
    if search:
        base_where += " AND (LOWER(first_name || ' ' || last_name) LIKE ? OR mrn LIKE ?)"
        args += [f"%{search.lower()}%", f"%{search.upper()}%"]
    total = conn.execute(f"SELECT COUNT(*) FROM patients {base_where}", args).fetchone()[0]
    rows = conn.execute(
        f"""SELECT patient_id, first_name, last_name, dob, gender, mrn,
                   primary_payer_id, secondary_payer_id, propensity_score, city, state
              FROM patients {base_where}
              ORDER BY last_name, first_name
              LIMIT ? OFFSET ?""",
        args + [page_size, offset],
    ).fetchall()
    cols = ["patient_id", "first_name", "last_name", "dob", "gender", "mrn",
            "primary_payer_id", "secondary_payer_id", "propensity_score", "city", "state"]
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [dict(zip(cols, r)) for r in rows],
    }


@router.get("/{patient_id}")
def get_patient(patient_id: str) -> dict:
    conn = get_connection()
    pt = conn.execute(
        """SELECT * FROM patients WHERE patient_id = ?""", (patient_id,)
    ).fetchone()
    if not pt:
        raise HTTPException(404, "Patient not found")
    cols = [d[0] for d in conn.description]
    patient = dict(zip(cols, pt))

    encs = conn.execute(
        """SELECT encounter_id, service_date, encounter_type, status, scenario_id
             FROM encounters WHERE patient_id = ?
             ORDER BY service_date DESC""",
        (patient_id,),
    ).fetchall()
    enc_cols = ["encounter_id", "service_date", "encounter_type", "status", "scenario_id"]

    elig = conn.execute(
        """SELECT eligibility_id, payer_id, verified_at, in_network, plan_type
             FROM eligibility_responses WHERE patient_id = ?
             ORDER BY verified_at DESC LIMIT 5""",
        (patient_id,),
    ).fetchall()
    elig_cols = ["eligibility_id", "payer_id", "verified_at", "in_network", "plan_type"]

    balance = conn.execute(
        """SELECT COALESCE(SUM(c.patient_responsibility), 0)
             FROM claims c JOIN encounters e ON c.encounter_id = e.encounter_id
            WHERE e.patient_id = ?""",
        (patient_id,),
    ).fetchone()[0]

    return {
        **patient,
        "encounters": [dict(zip(enc_cols, r)) for r in encs],
        "recent_eligibility": [dict(zip(elig_cols, r)) for r in elig],
        "balance_due": float(balance or 0),
    }
