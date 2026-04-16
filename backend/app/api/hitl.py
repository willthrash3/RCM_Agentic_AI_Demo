"""HITL queue API."""

from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from app.agents.event_bus import emit
from app.api.deps import require_api_key
from app.database import locked, transaction
from app.models.agent import HITLResolution

router = APIRouter(prefix="/hitl", tags=["hitl"], dependencies=[Depends(require_api_key)])


@router.get("/queue")
def list_queue(status: str = "pending", limit: int = 50) -> list[dict]:
    with locked() as conn:
        rows = conn.execute(
            """SELECT task_id, agent_name, entity_type, entity_id, task_description,
                      priority, recommended_action, agent_reasoning, status, created_at
                 FROM hitl_tasks
                WHERE status = ?
                ORDER BY
                  CASE priority
                    WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                    WHEN 'Medium' THEN 3 ELSE 4 END,
                  created_at DESC
                LIMIT ?""",
            (status, limit),
        ).fetchall()
    cols = ["task_id", "agent_name", "entity_type", "entity_id", "task_description",
            "priority", "recommended_action", "agent_reasoning", "status", "created_at"]
    return [dict(zip(cols, r)) for r in rows]


@router.post("/{task_id}/resolve")
async def resolve_task(task_id: str, resolution: HITLResolution) -> dict:
    with locked() as conn:
        row = conn.execute(
            """SELECT agent_name, entity_type, entity_id FROM hitl_tasks WHERE task_id = ?""",
            (task_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Task not found")
    status = {"approve": "approved", "reject": "rejected", "modify": "modified"}[resolution.decision]
    with transaction() as c:
        c.execute(
            """UPDATE hitl_tasks
                 SET status = ?, resolved_at = ?, decision = ?, notes = ?
               WHERE task_id = ?""",
            (status, datetime.utcnow(), resolution.decision, resolution.notes, task_id),
        )
    await emit(
        "hitl.task_resolved",
        agent_name=row[0],
        entity_type=row[1],
        entity_id=row[2],
        data={"task_id": task_id, "decision": resolution.decision, "notes": resolution.notes},
    )
    return {"task_id": task_id, "status": status, "decision": resolution.decision}
