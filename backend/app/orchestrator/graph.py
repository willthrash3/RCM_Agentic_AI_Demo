"""LangGraph workflow for the RCM pipeline.

Linear pipeline for a single encounter:
  START → eligibility → coding → scrubbing → submit → tracking
Branching:
  eligibility.escalated → HITL queue
  coding low confidence → HITL queue
  scrubbing critical edits → HITL queue
  tracking denial → denial agent
  era posting patient balance → collections
  kpi threshold → analytics agent

For the demo we expose a `run_pipeline` helper that streams events through each
stage. Full LangGraph StateGraph is defined below and usable programmatically.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover — allow import-time guard in offline / test
    StateGraph = None  # type: ignore[assignment]
    START = "START"
    END = "END"

from app.agents import AGENT_REGISTRY
from app.models.agent import AgentInput, AgentOutput, HITLTask


class RCMWorkflowState(TypedDict, total=False):
    encounter_id: Optional[str]
    claim_id: Optional[str]
    denial_id: Optional[str]
    patient_id: Optional[str]
    current_stage: str
    agent_outputs: dict[str, AgentOutput]
    hitl_queue: list[HITLTask]
    errors: list[str]
    run_mode: Literal["auto", "assisted", "demo"]


async def _run_node(agent_key: str, input: AgentInput) -> AgentOutput:
    agent_cls = AGENT_REGISTRY[agent_key]
    agent = agent_cls()
    return await agent.run(input)


async def run_eligibility(state: RCMWorkflowState) -> RCMWorkflowState:
    if not state.get("patient_id"):
        return state
    out = await _run_node("eligibility", AgentInput(
        entity_id=state["patient_id"], entity_type="patient", run_mode=state.get("run_mode", "demo"),
    ))
    state.setdefault("agent_outputs", {})["eligibility"] = out
    state["current_stage"] = "eligibility"
    return state


async def run_coding(state: RCMWorkflowState) -> RCMWorkflowState:
    if not state.get("encounter_id"):
        return state
    out = await _run_node("coding", AgentInput(
        entity_id=state["encounter_id"], entity_type="encounter",
        run_mode=state.get("run_mode", "demo"),
    ))
    state.setdefault("agent_outputs", {})["coding"] = out
    state["current_stage"] = "coding"
    return state


async def run_scrubbing(state: RCMWorkflowState) -> RCMWorkflowState:
    if not state.get("claim_id"):
        return state
    out = await _run_node("scrubbing", AgentInput(
        entity_id=state["claim_id"], entity_type="claim",
        run_mode=state.get("run_mode", "demo"),
    ))
    state.setdefault("agent_outputs", {})["scrubbing"] = out
    state["current_stage"] = "scrubbing"
    return state


async def run_tracking(state: RCMWorkflowState) -> RCMWorkflowState:
    out = await _run_node("tracking", AgentInput(
        entity_id="all", entity_type="system", run_mode=state.get("run_mode", "demo"),
    ))
    state.setdefault("agent_outputs", {})["tracking"] = out
    state["current_stage"] = "tracking"
    return state


async def run_analytics(state: RCMWorkflowState) -> RCMWorkflowState:
    out = await _run_node("analytics", AgentInput(
        entity_id="all", entity_type="system", run_mode=state.get("run_mode", "demo"),
    ))
    state.setdefault("agent_outputs", {})["analytics"] = out
    state["current_stage"] = "analytics"
    return state


def build_graph() -> Any:
    """Build the LangGraph StateGraph. Returns `None` if LangGraph unavailable."""
    if StateGraph is None:
        return None
    graph = StateGraph(RCMWorkflowState)
    graph.add_node("eligibility", run_eligibility)
    graph.add_node("coding", run_coding)
    graph.add_node("scrubbing", run_scrubbing)
    graph.add_node("tracking", run_tracking)
    graph.add_node("analytics", run_analytics)

    graph.add_edge(START, "eligibility")
    graph.add_edge("eligibility", "coding")
    graph.add_edge("coding", "scrubbing")
    graph.add_edge("scrubbing", "tracking")
    graph.add_edge("tracking", "analytics")
    graph.add_edge("analytics", END)
    return graph.compile()


async def run_pipeline(
    patient_id: str | None = None,
    encounter_id: str | None = None,
    claim_id: str | None = None,
    run_mode: str = "demo",
) -> RCMWorkflowState:
    state: RCMWorkflowState = {
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "claim_id": claim_id,
        "current_stage": "start",
        "agent_outputs": {},
        "hitl_queue": [],
        "errors": [],
        "run_mode": run_mode,  # type: ignore[typeddict-item]
    }
    for fn in (run_eligibility, run_coding, run_scrubbing, run_tracking, run_analytics):
        state = await fn(state)
    return state
