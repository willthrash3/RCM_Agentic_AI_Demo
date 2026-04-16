"""Mock payer FastAPI router — simulates X12 270/271/277/835 semantics.

All endpoints introduce configurable latency (50–300 ms) and a random error rate
to keep the demo realistic without any external connectivity.
"""

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.data.fixtures_loader import carc_rarc, payers

router = APIRouter(prefix="/mock", tags=["mock-payer"])


async def _apply_latency_and_error() -> None:
    settings = get_settings()
    # Clamp latency to [50, 300] around configured mean
    jitter = random.randint(-50, 100)
    latency = max(50, min(300, settings.mock_payer_latency_ms + jitter))
    await asyncio.sleep(latency / 1000.0)
    if random.random() < settings.mock_payer_error_rate:
        raise HTTPException(status_code=503, detail="Simulated payer portal error")


def _payer_or_404(payer_id: str) -> dict:
    for p in payers():
        if p["payer_id_x12_fictional"].lower() == payer_id.lower() or p["payer_id"] == payer_id:
            return p
    raise HTTPException(status_code=404, detail=f"Unknown payer {payer_id}")


# ---------------------------------------------------------------------------
# 270/271 — Eligibility
# ---------------------------------------------------------------------------

@router.get("/payer/{payer_id}/eligibility")
async def eligibility(payer_id: str, patient_id: str, service_date: str) -> dict[str, Any]:
    await _apply_latency_and_error()
    payer = _payer_or_404(payer_id)
    # 5% return "inactive" to demonstrate escalation
    active = random.random() > 0.05
    plan_type = random.choice(["HMO", "PPO", "EPO", "POS", "Medicare"])
    in_network = active and random.random() > 0.10
    response = {
        "transaction": "271",
        "payer_id": payer["payer_id"],
        "payer_name": payer["payer_name"],
        "patient_id": patient_id,
        "service_date": service_date,
        "active": active,
        "in_network": in_network,
        "plan_type": plan_type,
        "copay": random.choice([0, 10, 20, 25, 30, 40, 50]) if active else 0,
        "deductible_remaining": round(random.uniform(0, 3500), 2) if active else 0,
        "oop_remaining": round(random.uniform(0, 7500), 2) if active else 0,
        "coverage_start": str(date.today() - timedelta(days=365)),
        "coverage_end": str(date.today() + timedelta(days=365)) if active else str(date.today() - timedelta(days=30)),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    return response


# ---------------------------------------------------------------------------
# Prior Auth
# ---------------------------------------------------------------------------

@router.post("/payer/{payer_id}/auth/submit")
async def auth_submit(payer_id: str, payload: dict) -> dict[str, Any]:
    await _apply_latency_and_error()
    _payer_or_404(payer_id)
    r = random.random()
    if r < 0.80:
        status = "Approved"
    elif r < 0.95:
        status = "Pending"
    else:
        status = "Denied"
    return {
        "auth_number": f"AUTH{uuid.uuid4().hex[:8].upper()}",
        "status": status,
        "encounter_id": payload.get("encounter_id"),
        "cpt_code": payload.get("cpt_code"),
        "decision_at": datetime.utcnow().isoformat() + "Z" if status != "Pending" else None,
    }


@router.get("/payer/{payer_id}/auth/status")
async def auth_status(payer_id: str, auth_id: str) -> dict[str, Any]:
    await _apply_latency_and_error()
    _payer_or_404(payer_id)
    # Pending auths resolve after 2 seconds in demo
    status = random.choices(["Approved", "Pending", "Denied"], weights=[85, 10, 5])[0]
    return {"auth_id": auth_id, "status": status, "updated_at": datetime.utcnow().isoformat() + "Z"}


# ---------------------------------------------------------------------------
# 277 — Claim status
# ---------------------------------------------------------------------------

@router.get("/payer/{payer_id}/claim/status")
async def claim_status(payer_id: str, claim_id: str) -> dict[str, Any]:
    await _apply_latency_and_error()
    _payer_or_404(payer_id)
    bucket = random.choices(
        ["Paid", "Denied", "Pending", "Accepted"], weights=[55, 20, 15, 10]
    )[0]
    carc = random.choice([c["code"] for c in carc_rarc()["carc"]]) if bucket == "Denied" else None
    return {
        "transaction": "277",
        "claim_id": claim_id,
        "status": bucket,
        "status_category": bucket,
        "carc_code": carc,
        "rarc_code": None,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# 835 — ERA
# ---------------------------------------------------------------------------

@router.get("/era/{era_id}")
async def era_file(era_id: str) -> dict[str, Any]:
    await _apply_latency_and_error()
    # Minimal 835-like JSON payload
    line_count = random.randint(5, 12)
    lines = []
    for i in range(line_count):
        paid = round(random.uniform(40, 450), 2)
        adj = round(paid * random.uniform(0.1, 0.3), 2)
        lines.append({
            "claim_id": f"clm-{random.randint(1, 3000):05d}",
            "payment_amount": paid,
            "adjustment_codes": ["CO-45"] if random.random() < 0.2 else [],
            "adjustment_amount": adj,
            "patient_balance": round(random.uniform(0, 200), 2),
        })
    return {
        "transaction": "835",
        "era_id": era_id,
        "check_number": f"CHK{random.randint(1000000, 9999999)}",
        "payment_date": str(date.today()),
        "total_payment": round(sum(ln["payment_amount"] for ln in lines), 2),
        "lines": lines,
    }


# ---------------------------------------------------------------------------
# Appeals
# ---------------------------------------------------------------------------

@router.post("/payer/{payer_id}/appeal/submit")
async def appeal_submit(payer_id: str, payload: dict) -> dict[str, Any]:
    await _apply_latency_and_error()
    _payer_or_404(payer_id)
    return {
        "case_number": f"APL-{uuid.uuid4().hex[:10].upper()}",
        "status": "Received",
        "denial_id": payload.get("denial_id"),
        "submitted_at": datetime.utcnow().isoformat() + "Z",
        "estimated_decision_days": random.randint(14, 45),
    }
