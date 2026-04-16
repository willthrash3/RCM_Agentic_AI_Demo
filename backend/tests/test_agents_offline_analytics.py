"""Analytics agent offline-mode tests."""

from __future__ import annotations

import pytest

from app.agents.analytics import AnalyticsAgent, KPI_CONFIG
from app.models.agent import AgentInput


@pytest.mark.asyncio
async def test_analytics_produces_kpi_cards():
    agent = AnalyticsAgent()
    result = await agent.run(AgentInput(
        entity_id="all", entity_type="system", run_mode="demo"
    ))
    assert result.status in ("complete", "escalated")
    assert result.confidence > 0
    kpi_cards = result.result.get("kpi_cards", [])
    assert isinstance(kpi_cards, list)
    # Should have one card per KPI_CONFIG entry
    assert len(kpi_cards) == len(KPI_CONFIG)
    # kpi_cards use "label" as "name" field; compare against KPI_CONFIG labels
    card_names = {c["name"] for c in kpi_cards}
    expected_labels = {cfg["label"] for cfg in KPI_CONFIG}
    assert card_names == expected_labels
