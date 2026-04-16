"""Agent implementations for the RCM demo."""

from app.agents.analytics import AnalyticsAgent
from app.agents.base import BaseAgent
from app.agents.coding import CodingAgent
from app.agents.collections import CollectionsAgent
from app.agents.denial import DenialAgent
from app.agents.eligibility import EligibilityAgent
from app.agents.era_posting import ERAPostingAgent
from app.agents.scrubbing import ScrubbingAgent
from app.agents.tracking import TrackingAgent

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "eligibility": EligibilityAgent,
    "coding": CodingAgent,
    "scrubbing": ScrubbingAgent,
    "tracking": TrackingAgent,
    "era_posting": ERAPostingAgent,
    "denial": DenialAgent,
    "collections": CollectionsAgent,
    "analytics": AnalyticsAgent,
}

__all__ = ["AGENT_REGISTRY", "BaseAgent"]
