"""SSE streaming endpoint for agent events."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.agents.event_bus import get_event_bus
from app.config import get_settings
from app.database import locked

router = APIRouter(tags=["events"])


@router.get("/events/stream")
async def stream(
    request: Request,
    task_id: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
):
    """Server-Sent Events stream of AgentEvent objects."""
    settings = get_settings()
    bus = get_event_bus()
    queue = await bus.subscribe()

    async def generator():
        try:
            # First: send a connection-established event
            yield {
                "event": "connected",
                "data": json.dumps({"timestamp": datetime.utcnow().isoformat() + "Z"}),
            }
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=settings.sse_keepalive_interval
                    )
                except asyncio.TimeoutError:
                    yield {"event": "keepalive", "data": "{}"}
                    continue
                # Filter
                if task_id and event.task_id != task_id:
                    continue
                if entity_type and event.entity_type != entity_type:
                    continue
                if entity_id and event.entity_id != entity_id:
                    continue
                yield {
                    "event": event.event_type,
                    "id": event.event_id,
                    "data": event.model_dump_json(),
                }
        finally:
            await bus.unsubscribe(queue)

    return EventSourceResponse(generator())


@router.get("/events/recent")
def recent_events(limit: int = 100) -> list[dict]:
    with locked() as conn:
        rows = conn.execute(
            """SELECT event_id, task_id, agent_name, action_type, entity_type,
                      entity_id, reasoning_trace, confidence, hitl_required, created_at
                 FROM agent_event_log
                ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    cols = ["event_id", "task_id", "agent_name", "action_type", "entity_type",
            "entity_id", "reasoning_trace", "confidence", "hitl_required", "created_at"]
    return [dict(zip(cols, r)) for r in rows]
