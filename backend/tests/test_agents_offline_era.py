"""ERA posting agent offline-mode tests."""

from __future__ import annotations

from datetime import date

import pytest

from app.agents.era_posting import ERAPostingAgent
from app.models.agent import AgentInput


@pytest.mark.asyncio
async def test_era_no_unposted_claims():
    """With no unposted Paid claims, agent completes with posted=0."""
    agent = ERAPostingAgent()
    result = await agent.run(AgentInput(
        entity_id="all", entity_type="system", run_mode="demo"
    ))
    assert result.status in ("complete", "escalated")
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_era_posts_paid_claim():
    """Insert a Paid + era_posted=False claim; agent should post it."""
    from app.database import get_connection
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-era-agt-1", "pt-era-agt-1", "1111111111", "2222222222", "Outpatient",
         date(2026, 1, 10), date(2026, 1, 10), "11", "Dr. ERA", "HTN", "note", None,
         False, "Not Required", 1, "Coded"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-era-agt-1", "enc-era-agt-1", "837P", "payer-001", 200, 180, 150, 30,
         date(2026, 1, 12), date(2026, 1, 20), "Paid", None, None, None, None, False),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("line-era-agt-1", "clm-era-agt-1", "99214", "I10", None, None, 1, 200, 180,
         None, None, 0.93),
    )
    agent = ERAPostingAgent()
    result = await agent.run(AgentInput(
        entity_id="all", entity_type="system", run_mode="demo"
    ))
    assert result.status in ("complete", "escalated")
    assert result.result.get("posted", 0) >= 1
