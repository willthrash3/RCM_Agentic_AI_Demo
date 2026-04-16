"""Collections Agent — segments patient balances, runs outreach.

Segmentation rules (PRD §4.7):
- 0.80-1.00 High  → text/email, standard statement
- 0.50-0.79 Medium → email+paper, 3-month plan
- 0.20-0.49 Low   → paper+call, extended plan + charity screen
- 0.00-0.19 Hardship → call, financial counseling referral
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.agent import AgentInput, AgentOutput
from app.tools.collections_tools import (
    check_charity_care_eligibility,
    generate_payment_plan,
    generate_statement,
    get_patient_balances,
    send_outreach,
)
from app.tools.patient_tools import get_patient_contact_preferences, get_patient_propensity


SYSTEM = """You are a patient collections agent. Given a list of accounts with balances
and propensity scores, produce a segmented outreach plan. Return JSON:
{
  "segments": {"High": number, "Medium": number, "Low": number, "Hardship": number},
  "outreach_sent": number,
  "charity_screens": number,
  "summary": string,
  "_reasoning": string
}
"""


class CollectionsAgent(BaseAgent):
    name = "collections_agent"

    async def run(self, input: AgentInput) -> AgentOutput:
        await self.started(input, summary="Running collections segmentation")
        balances = get_patient_balances(min_balance=25.0, limit=50)
        await self.tool_call("system", "all", "get_patient_balances", {"limit": 50},
                             f"{len(balances)} patients w/ balance")

        segments = {"High": 0, "Medium": 0, "Low": 0, "Hardship": 0}
        charity_screens = 0
        outreach_sent = 0

        for row in balances:
            patient_id = row["patient_id"]
            balance = row["balance"]
            prop = get_patient_propensity(patient_id)
            prefs = get_patient_contact_preferences(patient_id)

            if prop >= 0.80:
                seg = "High"; channel = prefs.get("preferred_channel", "email")
                msg_type = "standard_statement"
            elif prop >= 0.50:
                seg = "Medium"; channel = "email"
                msg_type = "payment_plan_3mo"
            elif prop >= 0.20:
                seg = "Low"; channel = "paper"
                msg_type = "extended_plan"
                charity = check_charity_care_eligibility(patient_id, balance)
                if charity["eligible"]:
                    charity_screens += 1
            else:
                seg = "Hardship"; channel = "call"
                msg_type = "financial_counseling"
                charity_screens += 1

            segments[seg] += 1
            statement = generate_statement(patient_id, "multiple", balance, prefs.get("language_pref", "EN"))
            if seg in ("Medium", "Low"):
                plan = generate_payment_plan(patient_id, balance)
                statement += f"\n\nPayment plan: {plan['months']} months @ ${plan['monthly_amount']}/mo"
            send_outreach(patient_id, channel, msg_type, statement)
            outreach_sent += 1

        decision = await self.call_llm(
            system=SYSTEM,
            user=(
                f"Segmented {outreach_sent} patients. Breakdown: {segments}. "
                f"Charity screens triggered: {charity_screens}."
            ),
            entity_type="system", entity_id="all",
            fallback={
                "segments": segments,
                "outreach_sent": outreach_sent,
                "charity_screens": charity_screens,
                "summary": f"{outreach_sent} outreaches sent; {charity_screens} charity screens",
                "_reasoning": "Rule-based segmentation executed.",
            },
        )

        output = AgentOutput(
            status="complete",
            result={
                "segments": segments,
                "outreach_sent": outreach_sent,
                "charity_screens": charity_screens,
            },
            reasoning_trace=decision.get("_reasoning", ""),
            confidence=0.95, hitl_required=False,
        )
        await self.completed(input, output)
        return output
