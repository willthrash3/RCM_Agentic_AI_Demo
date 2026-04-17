"""Eligibility-related tools (mock 270/271)."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.config import get_settings
from app.data.fixtures_loader import payers
from app.database import locked, transaction


def _base() -> str:
    return get_settings().mock_payer_base_url.rstrip("/")


async def query_payer_eligibility(patient_id: str, payer_id: str, service_date: str) -> dict[str, Any]:
    payer_lookup = next((p for p in payers() if p["payer_id"] == payer_id), None)
    x12 = payer_lookup["payer_id_x12_fictional"] if payer_lookup else payer_id
    url = f"{_base()}/payer/{x12}/eligibility"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            url,
            params={"patient_id": patient_id, "service_date": service_date},
        )
        resp.raise_for_status()
        return resp.json()


def write_eligibility_result(patient_id: str, payer_id: str, result: dict[str, Any]) -> str:
    eid = f"el-{uuid.uuid4().hex[:10]}"
    with transaction() as conn:
        conn.execute(
            """INSERT INTO eligibility_responses VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (eid, patient_id, payer_id, datetime.utcnow(),
             Decimal(str(result.get("copay", 0))),
             Decimal(str(result.get("deductible_remaining", 0))),
             Decimal(str(result.get("oop_remaining", 0))),
             bool(result.get("in_network", True)),
             result.get("plan_type", "Unknown"),
             json.dumps(result)),
        )
    return eid


def flag_missing_info(patient_id: str, fields: list[str]) -> None:
    with locked() as conn:
        existing = conn.execute(
            """SELECT 1 FROM hitl_tasks
                WHERE entity_id = ? AND agent_name = 'eligibility_agent'
                  AND task_description LIKE 'Missing patient%' AND status = 'pending'
                LIMIT 1""",
            (patient_id,),
        ).fetchone()
    if existing:
        return
    task_id = f"hitl-{uuid.uuid4().hex[:10]}"
    with transaction() as conn:
        conn.execute(
            """INSERT INTO hitl_tasks
                   (task_id, agent_name, entity_type, entity_id, task_description,
                    priority, recommended_action, agent_reasoning, status, created_at,
                    resolved_at, decision, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id, "eligibility_agent", "patient", patient_id,
             f"Missing patient information: {', '.join(fields)}",
             "High", "Collect missing fields at next patient contact or via portal",
             f"Required fields not present in 271 or demographics: {fields}",
             "pending", datetime.utcnow(), None, None, None),
        )
