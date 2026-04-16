"""Agent interface, task, and event models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

RunMode = Literal["auto", "assisted", "demo"]
AgentStatus = Literal["complete", "escalated", "failed"]
EventType = Literal[
    "agent.started",
    "agent.tool_call",
    "agent.reasoning",
    "agent.completed",
    "agent.escalated",
    "agent.failed",
    "kpi.alert",
    "hitl.task_created",
    "hitl.task_resolved",
    "scenario.injected",
]


class AgentInput(BaseModel):
    entity_id: str
    entity_type: str
    context: dict[str, Any] = Field(default_factory=dict)
    run_mode: RunMode = "assisted"


class AgentOutput(BaseModel):
    status: AgentStatus
    result: dict[str, Any] = Field(default_factory=dict)
    reasoning_trace: str = ""
    confidence: float = 0.0
    hitl_required: bool = False
    hitl_reason: Optional[str] = None


class AgentRunResponse(BaseModel):
    task_id: str
    agent_name: str
    status: Literal["queued", "running", "complete", "escalated", "failed"]
    created_at: datetime


class AgentTaskStatus(BaseModel):
    task_id: str
    agent_name: str
    status: str
    confidence: Optional[float] = None
    output: Optional[AgentOutput] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class AgentEvent(BaseModel):
    event_id: str
    event_type: EventType
    agent_name: str
    entity_type: str
    entity_id: str
    task_id: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class HITLTask(BaseModel):
    task_id: str
    agent_name: str
    entity_type: str
    entity_id: str
    task_description: str
    priority: Literal["Critical", "High", "Medium", "Low"]
    recommended_action: str
    agent_reasoning: str
    status: Literal["pending", "approved", "rejected", "modified"] = "pending"
    created_at: datetime
    resolved_at: Optional[datetime] = None
    decision: Optional[str] = None
    notes: Optional[str] = None


class HITLResolution(BaseModel):
    decision: Literal["approve", "reject", "modify"]
    notes: Optional[str] = None
