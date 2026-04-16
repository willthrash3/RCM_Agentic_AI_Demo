"""Agents API — POST /agents/{name}/run and GET /agents/tasks/{task_id}."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.agents import AGENT_REGISTRY
from app.agents.task_runner import register_task, run_agent_background
from app.api.deps import require_api_key
from app.database import get_connection
from app.models.agent import AgentInput, AgentOutput, AgentRunResponse, AgentTaskStatus

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(require_api_key)])


@router.post("/eligibility/run", response_model=AgentRunResponse)
async def run_eligibility(
    payload: dict, background_tasks: BackgroundTasks
) -> AgentRunResponse:
    patient_id = payload.get("patient_id")
    if not patient_id:
        raise HTTPException(400, "patient_id is required")
    input = AgentInput(
        entity_id=patient_id, entity_type="patient",
        context={
            "payer_id": payload.get("payer_id"),
            "service_date": payload.get("service_date"),
        },
        run_mode=payload.get("run_mode", "assisted"),
    )
    task_id = register_task("eligibility_agent", input)
    background_tasks.add_task(run_agent_background, AGENT_REGISTRY["eligibility"], task_id, input)
    return AgentRunResponse(task_id=task_id, agent_name="eligibility_agent",
                            status="queued", created_at=datetime.utcnow())


@router.post("/coding/run", response_model=AgentRunResponse)
async def run_coding(payload: dict, background_tasks: BackgroundTasks) -> AgentRunResponse:
    encounter_id = payload.get("encounter_id")
    if not encounter_id:
        raise HTTPException(400, "encounter_id is required")
    input = AgentInput(
        entity_id=encounter_id, entity_type="encounter",
        run_mode=payload.get("run_mode", "assisted"),
    )
    task_id = register_task("coding_agent", input)
    background_tasks.add_task(run_agent_background, AGENT_REGISTRY["coding"], task_id, input)
    return AgentRunResponse(task_id=task_id, agent_name="coding_agent",
                            status="queued", created_at=datetime.utcnow())


@router.post("/scrubbing/run", response_model=AgentRunResponse)
async def run_scrubbing(payload: dict, background_tasks: BackgroundTasks) -> AgentRunResponse:
    claim_id = payload.get("claim_id")
    if not claim_id:
        raise HTTPException(400, "claim_id is required")
    input = AgentInput(
        entity_id=claim_id, entity_type="claim",
        run_mode=payload.get("run_mode", "assisted"),
    )
    task_id = register_task("scrubbing_agent", input)
    background_tasks.add_task(run_agent_background, AGENT_REGISTRY["scrubbing"], task_id, input)
    return AgentRunResponse(task_id=task_id, agent_name="scrubbing_agent",
                            status="queued", created_at=datetime.utcnow())


@router.post("/tracking/run", response_model=AgentRunResponse)
async def run_tracking(background_tasks: BackgroundTasks) -> AgentRunResponse:
    input = AgentInput(entity_id="all", entity_type="system", run_mode="demo")
    task_id = register_task("tracking_agent", input)
    background_tasks.add_task(run_agent_background, AGENT_REGISTRY["tracking"], task_id, input)
    return AgentRunResponse(task_id=task_id, agent_name="tracking_agent",
                            status="queued", created_at=datetime.utcnow())


@router.post("/era-posting/run", response_model=AgentRunResponse)
async def run_era(background_tasks: BackgroundTasks) -> AgentRunResponse:
    input = AgentInput(entity_id="all", entity_type="system", run_mode="demo")
    task_id = register_task("era_posting_agent", input)
    background_tasks.add_task(run_agent_background, AGENT_REGISTRY["era_posting"], task_id, input)
    return AgentRunResponse(task_id=task_id, agent_name="era_posting_agent",
                            status="queued", created_at=datetime.utcnow())


@router.post("/denial/run", response_model=AgentRunResponse)
async def run_denial(payload: dict, background_tasks: BackgroundTasks) -> AgentRunResponse:
    denial_id = payload.get("denial_id")
    if not denial_id:
        raise HTTPException(400, "denial_id is required")
    input = AgentInput(
        entity_id=denial_id, entity_type="denial",
        run_mode=payload.get("run_mode", "assisted"),
    )
    task_id = register_task("denial_agent", input)
    background_tasks.add_task(run_agent_background, AGENT_REGISTRY["denial"], task_id, input)
    return AgentRunResponse(task_id=task_id, agent_name="denial_agent",
                            status="queued", created_at=datetime.utcnow())


@router.post("/collections/run", response_model=AgentRunResponse)
async def run_collections(background_tasks: BackgroundTasks) -> AgentRunResponse:
    input = AgentInput(entity_id="all", entity_type="system", run_mode="demo")
    task_id = register_task("collections_agent", input)
    background_tasks.add_task(run_agent_background, AGENT_REGISTRY["collections"], task_id, input)
    return AgentRunResponse(task_id=task_id, agent_name="collections_agent",
                            status="queued", created_at=datetime.utcnow())


@router.post("/analytics/run", response_model=AgentRunResponse)
async def run_analytics(payload: dict | None = None, *, background_tasks: BackgroundTasks) -> AgentRunResponse:
    input = AgentInput(entity_id="all", entity_type="system", run_mode="demo")
    task_id = register_task("analytics_agent", input)
    background_tasks.add_task(run_agent_background, AGENT_REGISTRY["analytics"], task_id, input)
    return AgentRunResponse(task_id=task_id, agent_name="analytics_agent",
                            status="queued", created_at=datetime.utcnow())


@router.get("/tasks/{task_id}", response_model=AgentTaskStatus)
def get_task(task_id: str) -> AgentTaskStatus:
    conn = get_connection()
    row = conn.execute(
        """SELECT task_id, agent_name, status, confidence, output_json,
                  created_at, completed_at, error_message
             FROM agent_tasks WHERE task_id = ?""",
        (task_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    output = None
    if row[4]:
        try:
            output = AgentOutput(**json.loads(row[4]))
        except Exception:
            output = None
    return AgentTaskStatus(
        task_id=row[0], agent_name=row[1], status=row[2],
        confidence=row[3], output=output,
        created_at=row[5], completed_at=row[6], error_message=row[7],
    )


@router.get("/tasks")
def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT task_id, agent_name, status, confidence, created_at, completed_at
             FROM agent_tasks ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    cols = ["task_id", "agent_name", "status", "confidence", "created_at", "completed_at"]
    return [dict(zip(cols, r)) for r in rows]
