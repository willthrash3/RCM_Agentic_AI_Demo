"""Claims API."""

from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_api_key
from app.database import locked

router = APIRouter(prefix="/claims", tags=["claims"], dependencies=[Depends(require_api_key)])


@router.get("")
def list_claims(
    status: str | None = None,
    payer_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> dict:
    offset = (page - 1) * page_size
    where = ["1=1"]
    args: list = []
    if status:
        where.append("claim_status = ?"); args.append(status)
    if payer_id:
        where.append("payer_id = ?"); args.append(payer_id)
    if date_from:
        where.append("submission_date >= ?"); args.append(date_from)
    if date_to:
        where.append("submission_date <= ?"); args.append(date_to)
    clause = " AND ".join(where)
    with locked() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM claims WHERE {clause}", args).fetchone()[0]
        rows = conn.execute(
            f"""SELECT claim_id, encounter_id, payer_id, total_billed, total_paid,
                       claim_status, submission_date, adjudication_date,
                       rejection_reason, scrub_score
                  FROM claims WHERE {clause}
                  ORDER BY COALESCE(submission_date, DATE '2020-01-01') DESC
                  LIMIT ? OFFSET ?""",
            args + [page_size, offset],
        ).fetchall()
    cols = ["claim_id", "encounter_id", "payer_id", "total_billed", "total_paid",
            "claim_status", "submission_date", "adjudication_date", "rejection_reason", "scrub_score"]
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [dict(zip(cols, r)) for r in rows],
    }


@router.get("/{claim_id}")
def get_claim(claim_id: str) -> dict:
    with locked() as conn:
        cl = conn.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
        if not cl:
            raise HTTPException(404, "Claim not found")
        cols = [d[0] for d in conn.description]
        claim = dict(zip(cols, cl))

        lines = conn.execute(
            """SELECT line_id, cpt_code, icd10_primary, icd10_secondary, modifier,
                      units, charge_amount, allowed_amount, coding_confidence
                 FROM claim_lines WHERE claim_id = ?""",
            (claim_id,),
        ).fetchall()
        lcols = ["line_id", "cpt_code", "icd10_primary", "icd10_secondary", "modifier",
                 "units", "charge_amount", "allowed_amount", "coding_confidence"]

        denial = conn.execute(
            """SELECT denial_id, carc_code, rarc_code, denial_category, denial_date,
                      appeal_deadline, overturn_flag, appeal_submitted_at, appeal_letter_text
                 FROM denials WHERE claim_id = ? LIMIT 1""",
            (claim_id,),
        ).fetchone()
        dcols = ["denial_id", "carc_code", "rarc_code", "denial_category", "denial_date",
                 "appeal_deadline", "overturn_flag", "appeal_submitted_at", "appeal_letter_text"]

        events = conn.execute(
            """SELECT event_id, agent_name, action_type, reasoning_trace, confidence,
                      hitl_required, created_at
                 FROM agent_event_log
                WHERE entity_type = 'claim' AND entity_id = ?
                ORDER BY created_at DESC LIMIT 100""",
            (claim_id,),
        ).fetchall()
        ecols = ["event_id", "agent_name", "action_type", "reasoning_trace", "confidence",
                 "hitl_required", "created_at"]

    return {
        **claim,
        "lines": [dict(zip(lcols, r)) for r in lines],
        "denial": dict(zip(dcols, denial)) if denial else None,
        "events": [dict(zip(ecols, r)) for r in events],
    }


@router.get("/{claim_id}/trace")
def claim_trace(claim_id: str) -> list[dict]:
    with locked() as conn:
        rows = conn.execute(
            """SELECT event_id, task_id, agent_name, action_type, reasoning_trace,
                      output_summary, confidence, hitl_required, created_at
                 FROM agent_event_log
                WHERE entity_type = 'claim' AND entity_id = ?
                ORDER BY created_at ASC""",
            (claim_id,),
        ).fetchall()
    cols = ["event_id", "task_id", "agent_name", "action_type", "reasoning_trace",
            "output_summary", "confidence", "hitl_required", "created_at"]
    return [dict(zip(cols, r)) for r in rows]
