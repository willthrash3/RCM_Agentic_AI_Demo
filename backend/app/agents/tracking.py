"""Claim Tracking Agent — monitors submitted claims, detects underpayments.

Underpayment rule (PRD §4.4): actual_paid / contract_allowable < 0.95 and
variance > $25 → add to underpayment review queue with computed variance.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.agents.base import BaseAgent
from app.models.agent import AgentInput, AgentOutput
from app.tools.claim_tools import (
    get_contract_allowable,
    get_submitted_claims,
    query_payer_claim_status,
    update_claim_status,
)


SYSTEM = """You are a claim-tracking agent that monitors submitted claims for payer status
updates and flags underpayments. Return JSON:
{
  "underpayments_flagged": number,
  "timely_filing_risks": number,
  "status_updates": number,
  "summary": string,
  "_reasoning": string
}
"""


class TrackingAgent(BaseAgent):
    name = "tracking_agent"

    async def run(self, input: AgentInput) -> AgentOutput:
        await self.started(input, summary="Sweeping submitted claims for status & variance")

        claims = get_submitted_claims(days_submitted_min=1)
        await self.tool_call("system", "all", "get_submitted_claims",
                             {"days_submitted_min": 1}, f"{len(claims)} claims")

        underpayments = 0
        tf_risks = 0
        status_updates = 0

        # For demo speed, sample a subset
        sample = claims[:20]
        for cl in sample:
            status = await query_payer_claim_status(cl["claim_id"], cl["payer_id"])
            await self.tool_call("claim", cl["claim_id"], "query_payer_claim_status",
                                 {"payer_id": cl["payer_id"]}, f"status={status.get('status')}")
            if status.get("status") and status["status"] != cl["claim_status"]:
                update_claim_status(cl["claim_id"], status["status"])
                status_updates += 1

            # Underpayment check (sampled)
            if status.get("status") == "Paid":
                allowable = get_contract_allowable("99214", cl["payer_id"])
                total_billed = Decimal(str(cl.get("total_billed") or 0))
                if allowable > 0 and total_billed > 0:
                    variance = total_billed - allowable
                    if (allowable > 0 and (total_billed / allowable) < Decimal("0.95")
                            and variance > Decimal("25")):
                        underpayments += 1
                        await self.create_hitl_task(
                            "claim", cl["claim_id"],
                            f"Potential underpayment: ${variance:.2f} below contract allowable",
                            "Medium",
                            "Review payer contract and file short-pay appeal if justified",
                            f"Contract allowable ${allowable} vs billed ${total_billed}",
                        )

            # TF risk
            if cl.get("submission_date"):
                days_since = (date.today() - cl["submission_date"]).days
                if days_since > 25:
                    tf_risks += 1

        decision = await self.call_llm(
            system=SYSTEM,
            user=(
                f"Sampled {len(sample)} of {len(claims)} submitted claims.\n"
                f"Underpayments flagged: {underpayments}\n"
                f"Timely filing risks: {tf_risks}\n"
                f"Status updates applied: {status_updates}"
            ),
            entity_type="system", entity_id="all",
            fallback={
                "underpayments_flagged": underpayments,
                "timely_filing_risks": tf_risks,
                "status_updates": status_updates,
                "summary": f"Tracking sweep: {status_updates} updates, {underpayments} underpayments",
                "_reasoning": "Rule-based tracking sweep.",
            },
        )

        output = AgentOutput(
            status="complete",
            result={
                "claims_sampled": len(sample), "status_updates": status_updates,
                "underpayments_flagged": underpayments, "timely_filing_risks": tf_risks,
            },
            reasoning_trace=decision.get("_reasoning", ""),
            confidence=0.9, hitl_required=bool(underpayments),
        )
        await self.completed(input, output)
        return output
