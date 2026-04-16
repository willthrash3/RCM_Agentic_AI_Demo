"""In-process event bus for SSE streaming.

Every agent event is:
1. Written to agent_event_log in DuckDB (durable).
2. Published to an asyncio.Queue per subscriber (live).

SSE clients subscribe via `subscribe()` → an asyncio.Queue they can `await`.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import AsyncIterator

from app.database import transaction
from app.models.agent import AgentEvent, EventType


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[AgentEvent]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[AgentEvent]:
        q: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=1024)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue[AgentEvent]) -> None:
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    async def publish(self, event: AgentEvent) -> None:
        # Persist first
        self._persist(event)
        # Then fan out (non-blocking — drop for slow subscribers)
        async with self._lock:
            dead: list[asyncio.Queue[AgentEvent]] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def _persist(self, event: AgentEvent) -> None:
        with transaction() as conn:
            conn.execute(
                """INSERT INTO agent_event_log
                       (event_id, task_id, agent_name, action_type, entity_type,
                        entity_id, input_summary, output_summary, reasoning_trace,
                        confidence, hitl_required, human_decision, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event.event_id,
                    event.task_id,
                    event.agent_name,
                    event.event_type,
                    event.entity_type,
                    event.entity_id,
                    json.dumps(event.data.get("input_summary", ""))[:2000],
                    json.dumps(event.data.get("output_summary", ""))[:2000],
                    event.data.get("reasoning", "")[:4000],
                    event.data.get("confidence"),
                    event.data.get("hitl_required", False),
                    event.data.get("human_decision"),
                    event.timestamp,
                ),
            )


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


async def emit(
    event_type: EventType,
    agent_name: str,
    entity_type: str,
    entity_id: str,
    data: dict | None = None,
    task_id: str | None = None,
) -> AgentEvent:
    event = AgentEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        agent_name=agent_name,
        entity_type=entity_type,
        entity_id=entity_id,
        task_id=task_id,
        data=data or {},
        timestamp=datetime.utcnow(),
    )
    await get_event_bus().publish(event)
    return event


async def stream() -> AsyncIterator[AgentEvent]:
    bus = get_event_bus()
    q = await bus.subscribe()
    try:
        while True:
            event = await q.get()
            yield event
    finally:
        await bus.unsubscribe(q)
