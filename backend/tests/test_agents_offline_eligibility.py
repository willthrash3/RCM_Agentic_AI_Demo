"""Eligibility agent offline-mode tests."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.eligibility import EligibilityAgent
from app.models.agent import AgentInput


@pytest.fixture(scope="module", autouse=True)
def seed_elig_rows():
    from app.database import get_connection
    conn = get_connection()
    # Patient with no insurance
    conn.execute(
        """INSERT OR REPLACE INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("pt-elig-no-ins", "NoIns", "Patient", date(1990, 1, 1), "F",
         "123 Test St", "Chicago", "IL", "60601", "555-0001",
         "noons@test.com", "MRN-ELIG-001", None, None, 0.5, "EN", None, False),
    )
    # Patient with primary insurance
    conn.execute(
        """INSERT OR REPLACE INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("pt-elig-has-ins", "HasIns", "Patient", date(1985, 6, 15), "M",
         "456 Test Ave", "Chicago", "IL", "60602", "555-0002",
         "hasins@test.com", "MRN-ELIG-002", "payer-001", None, 0.8, "EN", None, False),
    )


@pytest.mark.asyncio
async def test_eligibility_no_insurance_escalates(seed_elig_rows):
    agent = EligibilityAgent()
    result = await agent.run(AgentInput(
        entity_id="pt-elig-no-ins", entity_type="patient", run_mode="demo"
    ))
    assert result.status == "escalated"
    assert result.hitl_required is True
    assert result.result.get("reason") == "no_insurance"


@pytest.mark.asyncio
async def test_eligibility_in_network_completes(seed_elig_rows):
    mock_271 = {
        "active": True, "in_network": True,
        "copay": 20, "deductible_remaining": 500,
        "oop_remaining": 1000, "plan_type": "PPO",
    }
    with patch("app.agents.eligibility.query_payer_eligibility",
               new=AsyncMock(return_value=mock_271)):
        agent = EligibilityAgent()
        result = await agent.run(AgentInput(
            entity_id="pt-elig-has-ins", entity_type="patient", run_mode="demo"
        ))
    assert result.status in ("complete", "escalated")
    assert result.confidence > 0
    assert "verified" in result.result


@pytest.mark.asyncio
async def test_eligibility_out_of_network_escalates(seed_elig_rows):
    mock_271 = {
        "active": True, "in_network": False,
        "copay": 100, "deductible_remaining": 2000,
        "oop_remaining": 5000, "plan_type": "HMO",
    }
    with patch("app.agents.eligibility.query_payer_eligibility",
               new=AsyncMock(return_value=mock_271)):
        agent = EligibilityAgent()
        result = await agent.run(AgentInput(
            entity_id="pt-elig-has-ins", entity_type="patient", run_mode="demo"
        ))
    assert result.status == "escalated"
    assert result.hitl_required is True
