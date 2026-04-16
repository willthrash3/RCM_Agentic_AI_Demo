"""Agent offline-mode tests: verify fallbacks produce non-empty output.

These tests run without any ANTHROPIC_API_KEY and rely on the scripted
fallback each agent provides.
"""

from __future__ import annotations

import pytest

from app.agents.coding import CodingAgent
from app.agents.scrubbing import ScrubbingAgent
from app.models.agent import AgentInput


@pytest.mark.asyncio
async def test_coding_offline_produces_output():
    # Need an encounter & a claim in the DB to operate on
    from app.database import get_connection
    from datetime import date
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-test-1", "pt-test-1", "1234567890", "0987654321", "Outpatient",
         date(2026, 4, 1), date(2026, 4, 1), "11", "Dr. Test", "HTN", "note", "htn_mgmt",
         False, "Not Required", 1, "Coded"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-test-1", "enc-test-1", "837P", "payer-001", 200, 150, 120, 30,
         None, None, "Draft", None, None, None, None, False),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("line-test-1", "clm-test-1", "99214", "I10", None, None, 1, 200, 150,
         None, None, None),
    )
    agent = CodingAgent()
    result = await agent.run(AgentInput(
        entity_id="enc-test-1", entity_type="encounter", run_mode="demo"
    ))
    assert result.status in ("complete", "escalated")
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_scrubbing_offline_produces_output():
    from app.database import get_connection
    from datetime import date
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-test-2", "enc-test-1", "837P", "payer-003", 200, 150, 0, 0,
         None, None, "Draft", None, date(2026, 7, 1), None, None, False),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("line-test-2", "clm-test-2", "99214", "I10", None, None, 1, 200, 150,
         None, None, 0.91),
    )
    agent = ScrubbingAgent()
    result = await agent.run(AgentInput(
        entity_id="clm-test-2", entity_type="claim", run_mode="demo"
    ))
    assert result.status in ("complete", "escalated")
    assert "scrub_score" in result.result
