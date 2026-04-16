"""Base class for all RCM agents.

Common responsibilities:
- Emit agent.started / agent.tool_call / agent.reasoning / agent.completed / agent.escalated events.
- Write to agent_event_log.
- Push HITLTask rows when escalating.
- Call the Claude LLM via Anthropic SDK (or return a scripted offline response).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.agents.event_bus import emit
from app.agents.llm import run_llm
from app.config import get_settings
from app.database import transaction
from app.models.agent import AgentInput, AgentOutput, HITLTask


class BaseAgent(ABC):
    #: Unique name for the agent, used in event_type prefix and registry keys.
    name: str = ""

    def __init__(self, task_id: str | None = None) -> None:
        self.task_id = task_id or str(uuid.uuid4())
        self.settings = get_settings()

    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput:
        ...

    # -- helpers ----------------------------------------------------------

    async def started(self, input: AgentInput, summary: str = "") -> None:
        await emit(
            "agent.started",
            agent_name=self.name,
            entity_type=input.entity_type,
            entity_id=input.entity_id,
            data={"input_summary": summary, "run_mode": input.run_mode},
            task_id=self.task_id,
        )

    async def tool_call(self, entity_type: str, entity_id: str, tool: str, args: dict, result_summary: str) -> None:
        await emit(
            "agent.tool_call",
            agent_name=self.name,
            entity_type=entity_type,
            entity_id=entity_id,
            data={"tool": tool, "args": args, "result_summary": result_summary[:500]},
            task_id=self.task_id,
        )

    async def reasoning(self, entity_type: str, entity_id: str, text: str) -> None:
        await emit(
            "agent.reasoning",
            agent_name=self.name,
            entity_type=entity_type,
            entity_id=entity_id,
            data={"reasoning": text},
            task_id=self.task_id,
        )

    async def completed(self, input: AgentInput, output: AgentOutput) -> None:
        await emit(
            "agent.completed",
            agent_name=self.name,
            entity_type=input.entity_type,
            entity_id=input.entity_id,
            data={
                "output_summary": output.result,
                "reasoning": output.reasoning_trace[:1500],
                "confidence": output.confidence,
                "hitl_required": output.hitl_required,
            },
            task_id=self.task_id,
        )

    async def escalated(self, input: AgentInput, reason: str, output: AgentOutput) -> None:
        await emit(
            "agent.escalated",
            agent_name=self.name,
            entity_type=input.entity_type,
            entity_id=input.entity_id,
            data={"reason": reason, "confidence": output.confidence},
            task_id=self.task_id,
        )

    async def create_hitl_task(
        self,
        entity_type: str,
        entity_id: str,
        description: str,
        priority: str,
        recommended_action: str,
        reasoning: str,
    ) -> HITLTask:
        task_id = f"hitl-{uuid.uuid4().hex[:10]}"
        now = datetime.utcnow()
        with transaction() as conn:
            conn.execute(
                """INSERT INTO hitl_tasks
                       (task_id, agent_name, entity_type, entity_id, task_description,
                        priority, recommended_action, agent_reasoning, status, created_at,
                        resolved_at, decision, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (task_id, self.name, entity_type, entity_id, description, priority,
                 recommended_action, reasoning, "pending", now, None, None, None),
            )
        task = HITLTask(
            task_id=task_id, agent_name=self.name, entity_type=entity_type,
            entity_id=entity_id, task_description=description, priority=priority,
            recommended_action=recommended_action, agent_reasoning=reasoning,
            status="pending", created_at=now,
        )
        await emit(
            "hitl.task_created",
            agent_name=self.name,
            entity_type=entity_type,
            entity_id=entity_id,
            data={"task_id": task_id, "priority": priority, "description": description},
            task_id=self.task_id,
        )
        return task

    async def call_llm(
        self,
        system: str,
        user: str,
        entity_type: str,
        entity_id: str,
        fallback: dict | None = None,
        model: str | None = None,
    ) -> dict:
        """Call Claude and stream reasoning events. Returns parsed JSON dict."""
        await self.reasoning(entity_type, entity_id, "Calling Claude for decision...")
        response = await run_llm(system=system, user=user, fallback=fallback, model=model)
        reasoning = response.get("_reasoning", "")
        if reasoning:
            await self.reasoning(entity_type, entity_id, reasoning)
        return response

    def _escape(self, text: str | None, limit: int = 1800) -> str:
        if not text:
            return ""
        return text.replace("{", "{{").replace("}", "}}")[:limit]
