"""Background task runner for agent runs.

POST /agents/{name}/run creates an agent_tasks row and schedules the agent
coroutine. The runner:
- sets status=running
- awaits the agent.run()
- writes output & status=complete/escalated/failed
- never raises into the FastAPI event loop (errors become failed tasks + event)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime

from app.agents.event_bus import emit
from app.database import transaction
from app.models.agent import AgentInput, AgentOutput


async def _set_status(
    task_id: str,
    status: str,
    output: AgentOutput | None = None,
    error: str | None = None,
) -> None:
    with transaction() as conn:
        conn.execute(
            """UPDATE agent_tasks
                 SET status = ?, output_json = ?, confidence = ?,
                     completed_at = ?, error_message = ?
               WHERE task_id = ?""",
            (
                status,
                json.dumps(output.model_dump(mode="json")) if output else None,
                output.confidence if output else None,
                datetime.utcnow() if status in ("complete", "escalated", "failed") else None,
                error,
                task_id,
            ),
        )


def register_task(agent_name: str, input: AgentInput) -> str:
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    with transaction() as conn:
        conn.execute(
            """INSERT INTO agent_tasks
                  (task_id, agent_name, status, input_json, output_json,
                   confidence, created_at, completed_at, error_message)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (task_id, agent_name, "queued", json.dumps(input.model_dump(mode="json")),
             None, None, datetime.utcnow(), None, None),
        )
    return task_id


async def run_agent_background(agent_cls, task_id: str, input: AgentInput) -> None:
    agent = agent_cls(task_id=task_id)
    await _set_status(task_id, "running")
    try:
        output = await agent.run(input)
        await _set_status(
            task_id,
            "escalated" if output.status == "escalated" else output.status,
            output=output,
        )
    except Exception as exc:  # pragma: no cover — demo robustness
        await _set_status(task_id, "failed", error=str(exc))
        await emit(
            "agent.failed",
            agent_name=agent.name,
            entity_type=input.entity_type,
            entity_id=input.entity_id,
            data={"error": str(exc)},
            task_id=task_id,
        )
