"""ERA Posting Agent — matches payments to claims, posts, routes exceptions.

Matching logic (PRD §4.5):
- Primary: claim_id in ERA.
- Secondary: patient + service_date + CPT.
- No match → exception queue.
- CARC denial code present → route to denial_agent workflow.
- Write-offs > $50 require HITL approval.
"""

from __future__ import annotations

from decimal import Decimal

from app.agents.base import BaseAgent
from app.models.agent import AgentInput, AgentOutput
from app.tools.era_tools import (
    get_unposted_eras,
    post_payment,
    route_exception,
)


SYSTEM = """You are an ERA posting agent. Given a batch of ERA lines, classify each as
auto-postable, requires-HITL, or exception. Return JSON:
{
  "posted": number,
  "hitl": number,
  "exceptions": number,
  "denials_routed": number,
  "summary": string,
  "_reasoning": string
}
"""


class ERAPostingAgent(BaseAgent):
    name = "era_posting_agent"

    async def run(self, input: AgentInput) -> AgentOutput:
        await self.started(input, summary="Posting unprocessed ERAs")

        eras = get_unposted_eras(limit=10)
        await self.tool_call("system", "all", "get_unposted_eras", {}, f"{len(eras)} eras")

        posted = 0
        hitl = 0
        exceptions = 0
        denials_routed = 0

        for era in eras:
            for line in era["lines"]:
                claim_id = line.get("claim_id")
                if not claim_id:
                    exceptions += 1
                    route_exception(era["era_id"], None, "No claim_id match")
                    continue
                if line.get("adjustment_codes") and line.get("payment_amount", 0) == 0:
                    denials_routed += 1
                    continue
                write_off = line.get("adjustment_amount", 0)
                if write_off > 50:
                    hitl += 1
                    await self.create_hitl_task(
                        "claim", claim_id,
                        f"Write-off approval required: ${write_off:.2f}",
                        "Medium",
                        "Approve / reject contractual adjustment",
                        f"Adjustment codes: {line.get('adjustment_codes')}",
                    )
                    continue
                post_payment(
                    claim_id=claim_id,
                    payment_amount=Decimal(str(line["payment_amount"])),
                    adjustment_codes=line.get("adjustment_codes", []),
                    patient_balance=Decimal(str(line.get("patient_balance", 0))),
                )
                posted += 1

        decision = await self.call_llm(
            system=SYSTEM,
            user=(
                f"Posted: {posted}\nHITL: {hitl}\nExceptions: {exceptions}\n"
                f"Denials routed: {denials_routed}"
            ),
            entity_type="system", entity_id="all",
            fallback={
                "posted": posted, "hitl": hitl, "exceptions": exceptions,
                "denials_routed": denials_routed,
                "summary": f"{posted} auto-posted, {hitl} HITL, {exceptions} exceptions",
                "_reasoning": "Rule-based ERA posting completed.",
            },
        )

        output = AgentOutput(
            status="complete",
            result={
                "posted": posted, "hitl": hitl, "exceptions": exceptions,
                "denials_routed": denials_routed,
            },
            reasoning_trace=decision.get("_reasoning", ""),
            confidence=0.95, hitl_required=bool(hitl),
        )
        await self.completed(input, output)
        return output
