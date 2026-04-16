"""Denials API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_api_key
from app.data.fixtures_loader import carc_rarc
from app.database import get_connection

router = APIRouter(prefix="/denials", tags=["denials"], dependencies=[Depends(require_api_key)])

_CARC = {c["code"]: c for c in carc_rarc()["carc"]}


@router.get("")
def list_denials(
    category: str | None = None,
    payer_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> dict:
    conn = get_connection()
    offset = (page - 1) * page_size
    where = ["1=1"]
    args: list = []
    if category:
        where.append("d.denial_category = ?"); args.append(category)
    if payer_id:
        where.append("c.payer_id = ?"); args.append(payer_id)
    clause = " AND ".join(where)
    total = conn.execute(
        f"""SELECT COUNT(*) FROM denials d JOIN claims c ON d.claim_id = c.claim_id WHERE {clause}""",
        args,
    ).fetchone()[0]
    rows = conn.execute(
        f"""SELECT d.denial_id, d.claim_id, d.carc_code, d.rarc_code, d.denial_category,
                   d.denial_date, d.appeal_deadline, d.overturn_flag,
                   d.appeal_submitted_at, c.payer_id, c.total_billed
              FROM denials d JOIN claims c ON d.claim_id = c.claim_id
             WHERE {clause}
             ORDER BY d.denial_date DESC
             LIMIT ? OFFSET ?""",
        args + [page_size, offset],
    ).fetchall()
    cols = ["denial_id", "claim_id", "carc_code", "rarc_code", "denial_category",
            "denial_date", "appeal_deadline", "overturn_flag", "appeal_submitted_at",
            "payer_id", "total_billed"]
    items = []
    for r in rows:
        row = dict(zip(cols, r))
        row["carc_description"] = _CARC.get(row["carc_code"], {}).get("description", "")
        items.append(row)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/summary")
def denial_summary() -> dict:
    conn = get_connection()
    rows = conn.execute(
        """SELECT denial_category, COUNT(*) FROM denials GROUP BY denial_category"""
    ).fetchall()
    return {"by_category": [{"category": r[0], "count": r[1]} for r in rows]}


@router.get("/{denial_id}")
def get_denial(denial_id: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM denials WHERE denial_id = ?", (denial_id,)
    ).fetchone()
    if not row:
        raise HTTPException(404, "Denial not found")
    cols = [d[0] for d in conn.description]
    out = dict(zip(cols, row))
    out["carc_description"] = _CARC.get(out["carc_code"], {}).get("description", "")
    return out
