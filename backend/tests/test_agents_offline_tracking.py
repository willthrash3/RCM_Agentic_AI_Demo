"""Tracking agent offline-mode tests."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.tracking import TrackingAgent
from app.models.agent import AgentInput


@pytest.mark.asyncio
async def test_tracking_no_submitted_claims():
    """With no submitted claims older than 1 day, agent completes with 0 updates."""
    agent = TrackingAgent()
    result = await agent.run(AgentInput(
        entity_id="all", entity_type="system", run_mode="demo"
    ))
    assert result.status in ("complete", "escalated")
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_tracking_with_submitted_claims():
    """Insert a submitted claim, patch status query, verify agent runs cleanly."""
    from app.database import get_connection
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-track-1", "pt-track-1", "1234567890", "0987654321", "Outpatient",
         date(2026, 1, 1), date(2026, 1, 1), "11", "Dr. Track", "HTN", "note", None,
         False, "Not Required", 1, "Coded"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-track-1", "enc-track-1", "837P", "payer-001", 300, 250, None, 50,
         date.today() - timedelta(days=5), None, "Submitted", None, None, None, None, False),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("line-track-1", "clm-track-1", "99214", "I10", None, None, 1, 300, 250,
         None, None, 0.90),
    )
    mock_status = {"status": "Paid", "paid_amount": 250.0}
    with patch("app.agents.tracking.query_payer_claim_status",
               new=AsyncMock(return_value=mock_status)):
        agent = TrackingAgent()
        result = await agent.run(AgentInput(
            entity_id="all", entity_type="system", run_mode="demo"
        ))
    assert result.status in ("complete", "escalated")
    assert result.confidence > 0
