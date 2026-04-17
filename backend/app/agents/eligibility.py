"""Eligibility Agent — verifies patient insurance via mock 270/271.

HITL triggers (PRD §4.1):
- Plan is out-of-network for the scheduled service
- Coverage has lapsed or policy is inactive
- COB order cannot be determined from 271 response
- Eligibility check fails 3 times (payer portal error)
"""

from __future__ import annotations

from datetime import date

from app.agents.base import BaseAgent
from app.utils.time import get_demo_today
from app.models.agent import AgentInput, AgentOutput
from app.tools.eligibility_tools import flag_missing_info, query_payer_eligibility, write_eligibility_result
from app.tools.patient_tools import get_patient_demographics, get_patient_insurance


SYSTEM = """You are a healthcare eligibility verification agent. Given a patient's
demographics, insurance records, and a 271 response from the payer portal, determine:
1. Is eligibility verified clean?
2. Does the patient require financial counseling (deductible remaining < $200 or OOP met)?
3. Does the case need HITL escalation (out-of-network, inactive policy, COB issue)?

Return JSON:
{
  "verified": boolean,
  "in_network": boolean,
  "financial_counseling_flag": boolean,
  "cob_uncertain": boolean,
  "escalate": boolean,
  "escalation_reason": string,
  "summary": string,
  "_reasoning": string
}
"""


class EligibilityAgent(BaseAgent):
    name = "eligibility_agent"

    async def run(self, input: AgentInput) -> AgentOutput:
        patient_id = input.entity_id
        service_date = input.context.get("service_date", str(get_demo_today()))
        await self.started(input, summary=f"Verifying eligibility for {patient_id}")

        demographics = get_patient_demographics(patient_id)
        await self.tool_call("patient", patient_id, "get_patient_demographics",
                             {"patient_id": patient_id},
                             f"{demographics.get('first_name','')} {demographics.get('last_name','')}")

        # Self-pay patients do not need eligibility verification
        if demographics.get("is_self_pay"):
            output = AgentOutput(
                status="complete",
                result={"reason": "self_pay", "eligible": False},
                reasoning_trace="Patient is self-pay; eligibility check skipped.",
                confidence=1.0, hitl_required=False,
            )
            await self.completed(input, output)
            return output

        insurances = get_patient_insurance(patient_id)
        await self.tool_call("patient", patient_id, "get_patient_insurance",
                             {"patient_id": patient_id}, f"{len(insurances)} insurance(s)")

        if not insurances:
            await self.create_hitl_task(
                "patient", patient_id, "No insurance records on file",
                "High", "Collect insurance at registration",
                "Patient has no payer_id assigned",
            )
            output = AgentOutput(
                status="escalated", result={"reason": "no_insurance"},
                reasoning_trace="No insurance records", confidence=1.0,
                hitl_required=True, hitl_reason="No insurance",
            )
            await self.escalated(input, "no insurance", output)
            await self.completed(input, output)
            return output

        primary = insurances[0]
        response_271: dict = {}
        try:
            response_271 = await query_payer_eligibility(
                patient_id, primary["payer_id"], service_date
            )
            await self.tool_call("patient", patient_id, "query_payer_eligibility",
                                 {"payer_id": primary["payer_id"], "service_date": service_date},
                                 f"active={response_271.get('active')} in_network={response_271.get('in_network')}")
        except Exception as exc:  # pragma: no cover
            await self.tool_call("patient", patient_id, "query_payer_eligibility",
                                 {"payer_id": primary["payer_id"]}, f"error: {exc}")
            await self.create_hitl_task(
                "patient", patient_id, "Eligibility portal unreachable",
                "High", "Retry or verify via phone",
                f"Portal error: {exc}",
            )
            out = AgentOutput(status="escalated", result={"reason": "portal_error"},
                              reasoning_trace=str(exc), confidence=0.0,
                              hitl_required=True, hitl_reason="portal_error")
            await self.escalated(input, "portal error", out)
            await self.completed(input, out)
            return out

        write_eligibility_result(patient_id, primary["payer_id"], response_271)

        decision = await self.call_llm(
            system=SYSTEM,
            user=(
                f"Patient: {demographics}\nInsurance: {insurances}\n"
                f"271 response: {response_271}\n"
                f"Service date: {service_date}"
            ),
            entity_type="patient", entity_id=patient_id,
            fallback={
                "verified": bool(response_271.get("active")),
                "in_network": bool(response_271.get("in_network")),
                "financial_counseling_flag": float(response_271.get("deductible_remaining", 0)) < 200,
                "cob_uncertain": len(insurances) > 1,
                "escalate": (
                    not response_271.get("active")
                    or not response_271.get("in_network")
                ),
                "escalation_reason": (
                    "Coverage inactive" if not response_271.get("active")
                    else "Out of network" if not response_271.get("in_network")
                    else ""
                ),
                "summary": (
                    f"Active={response_271.get('active')}; "
                    f"copay=${response_271.get('copay')}; "
                    f"deductible_remaining=${response_271.get('deductible_remaining')}"
                ),
                "_reasoning": "Rule-based eligibility evaluation from 271 response.",
            },
        )

        escalate = bool(decision.get("escalate"))
        fc_flag = bool(decision.get("financial_counseling_flag"))

        missing: list[str] = []
        if not response_271.get("plan_type") or response_271.get("plan_type") == "Unknown":
            missing.append("plan_type")
        if decision.get("cob_uncertain"):
            missing.append("cob_order")
        if missing:
            flag_missing_info(patient_id, missing)

        if escalate:
            await self.create_hitl_task(
                "patient", patient_id,
                f"Eligibility escalation: {decision.get('escalation_reason', 'review')}",
                "High",
                "Review coverage and contact patient",
                decision.get("_reasoning", ""),
            )

        output = AgentOutput(
            status="escalated" if escalate else "complete",
            result={
                "verified": decision.get("verified"),
                "in_network": decision.get("in_network"),
                "financial_counseling_flag": fc_flag,
                "copay": response_271.get("copay"),
                "deductible_remaining": response_271.get("deductible_remaining"),
                "oop_remaining": response_271.get("oop_remaining"),
                "plan_type": response_271.get("plan_type"),
            },
            reasoning_trace=decision.get("_reasoning", ""),
            confidence=0.95,
            hitl_required=escalate,
            hitl_reason=decision.get("escalation_reason") if escalate else None,
        )
        if escalate:
            await self.escalated(input, decision.get("escalation_reason", ""), output)
        await self.completed(input, output)
        return output
