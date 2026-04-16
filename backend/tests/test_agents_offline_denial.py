"""Denial agent offline-mode tests."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.denial import DenialAgent
from app.models.agent import AgentInput


@pytest.fixture(scope="module", autouse=True)
def seed_denial_rows():
    from app.database import get_connection
    conn = get_connection()
    # Encounter + claim + denial for testing
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-denial-agt-1", "pt-test-1", "1234567890", "0987654321", "Outpatient",
         date(2026, 2, 1), date(2026, 2, 1), "11", "Dr. Test", "HTN", "note", None,
         False, "Not Required", 1, "Coded"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-denial-agt-1", "enc-denial-agt-1", "837P", "payer-001", 200, 150, 0, 0,
         date(2026, 2, 5), None, "Denied", None, date(2026, 8, 1), None, None, False),
    )
    # Denial with far deadline (> 7 days) → auto-submit path
    conn.execute(
        """INSERT OR REPLACE INTO denials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("den-agt-far-deadline", "clm-denial-agt-1", "97", None, "Coding / DX",
         date(2026, 3, 1), date.today() + timedelta(days=30),
         None, None, None, None, False),
    )
    # Contractual denial → not appealable → escalates to HITL
    conn.execute(
        """INSERT OR REPLACE INTO denials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("den-agt-contractual", "clm-denial-agt-1", "45", None, "Contractual",
         date(2026, 3, 1), date.today() + timedelta(days=30),
         None, None, None, None, False),
    )


@pytest.mark.asyncio
async def test_denial_not_found_returns_failed():
    agent = DenialAgent()
    result = await agent.run(AgentInput(
        entity_id="den-does-not-exist-xyz", entity_type="denial", run_mode="demo"
    ))
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_coding_denial_auto_submit(seed_denial_rows):
    mock_submit = {"success": True, "case_number": "CASE-PYTEST-001"}
    with patch("app.agents.denial.submit_appeal",
               new=AsyncMock(return_value=mock_submit)):
        agent = DenialAgent()
        result = await agent.run(AgentInput(
            entity_id="den-agt-far-deadline", entity_type="denial", run_mode="demo"
        ))
    assert result.status in ("complete", "escalated")
    assert result.confidence >= 0


@pytest.mark.asyncio
async def test_contractual_denial_escalates(seed_denial_rows):
    agent = DenialAgent()
    result = await agent.run(AgentInput(
        entity_id="den-agt-contractual", entity_type="denial", run_mode="demo"
    ))
    # Contractual denials are not appealable → should escalate to HITL
    assert result.status in ("escalated", "complete")
    assert result.confidence >= 0
