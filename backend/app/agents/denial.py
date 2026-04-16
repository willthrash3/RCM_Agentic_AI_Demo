"""Denial Management Agent — classifies denials, drafts and submits appeals.

Auto-submit criteria (PRD §4.6):
- Category is Coding OR Eligibility
- Corrected data available
- Appeal deadline > 7 days away
- Rendered appeal letter passes self-review
"""

from __future__ import annotations

from datetime import date, timedelta

from app.agents.base import BaseAgent
from app.utils.time import get_demo_today
from app.models.agent import AgentInput, AgentOutput
from app.tools.denial_tools import (
    calculate_appeal_deadline,
    classify_denial_root_cause,
    get_appeal_template,
    get_claim_detail,
    get_clinical_documentation,
    get_denial_detail,
    get_prior_auth_record,
    render_appeal_letter,
    self_review_appeal_letter,
    submit_appeal,
)


SYSTEM = """You are the highest-stakes agent in the RCM pipeline: denial management.
Given a denial record, its CARC/RARC codes, the associated claim, the encounter's
clinical documentation, and any prior auth record, you must:
1. Confirm the root cause classification (Coding, Eligibility, Prior Auth, Med Necessity,
   Timely Filing, Duplicate, Contractual, Other).
2. Decide appeal_recommended (boolean) and auto_submit (boolean).
3. Produce a clinical_summary (3-6 sentences) that will be embedded in the appeal letter.
4. List corrected_codes if the denial was coding-related (CPT + ICD-10).

Return JSON:
{
  "denial_category": string,
  "root_cause_narrative": string,
  "appeal_recommended": boolean,
  "auto_submit": boolean,
  "clinical_summary": string,
  "corrected_codes": {"cpt": string|null, "icd10": string|null},
  "_reasoning": string
}
"""


class DenialAgent(BaseAgent):
    name = "denial_agent"

    async def run(self, input: AgentInput) -> AgentOutput:
        denial_id = input.entity_id
        await self.started(input, summary=f"Processing denial {denial_id}")

        denial = get_denial_detail(denial_id)
        if not denial:
            out = AgentOutput(status="failed", result={"error": "Denial not found"}, confidence=0.0)
            await self.completed(input, out)
            return out
        await self.tool_call("denial", denial_id, "get_denial_detail",
                             {"denial_id": denial_id},
                             f"CARC={denial.get('carc_code')} category={denial.get('denial_category')}")

        claim = get_claim_detail(denial["claim_id"])
        await self.tool_call("denial", denial_id, "get_claim_detail",
                             {"claim_id": denial["claim_id"]},
                             f"billed=${claim.get('total_billed')}")

        encounter_id = claim.get("encounter_id", "")
        clinical = get_clinical_documentation(encounter_id) if encounter_id else {}
        if encounter_id:
            await self.tool_call("denial", denial_id, "get_clinical_documentation",
                                 {"encounter_id": encounter_id},
                                 f"note_len={len(clinical.get('soap_note_text', '') or '')}")
            auth = get_prior_auth_record(encounter_id)
            if auth:
                await self.tool_call("denial", denial_id, "get_prior_auth_record",
                                     {"encounter_id": encounter_id},
                                     f"auth status={auth.get('status')}")

        classification = classify_denial_root_cause(
            denial["carc_code"], denial.get("rarc_code"), claim
        )
        await self.tool_call("denial", denial_id, "classify_denial_root_cause",
                             {"carc_code": denial["carc_code"]},
                             f"category={classification['denial_category']} appealable={classification['appealable']}")

        appeal_deadline = calculate_appeal_deadline(denial["denial_date"], claim["payer_id"])
        days_to_deadline = (appeal_deadline - get_demo_today()).days if isinstance(appeal_deadline, date) else 60

        decision = await self.call_llm(
            system=SYSTEM,
            user=(
                f"Denial: {denial}\nClaim: {claim}\n"
                f"Classification: {classification}\n"
                f"Clinical note excerpt: {self._escape(clinical.get('soap_note_text', ''))}\n"
                f"Days until appeal deadline: {days_to_deadline}\n"
                "Decide appeal_recommended and auto_submit per PRD rules."
            ),
            entity_type="denial", entity_id=denial_id,
            fallback={
                "denial_category": classification["denial_category"],
                "root_cause_narrative": classification["root_cause"],
                "appeal_recommended": classification["appealable"],
                "auto_submit": (
                    classification["denial_category"] in ("Coding / DX", "Eligibility")
                    and days_to_deadline > 7
                ),
                "clinical_summary": (
                    f"The patient presented with {claim.get('encounter_id', 'this encounter')}. "
                    f"Documentation in the medical record supports the services rendered "
                    f"and the correct code assignment. The denial under {denial['carc_code']} "
                    "is therefore subject to reconsideration."
                ),
                "corrected_codes": {"cpt": None, "icd10": None},
                "_reasoning": "Rule-based denial classification and auto-submit check.",
            },
            model=self.settings.claude_model_reasoning,
        )

        category = decision.get("denial_category") or classification["denial_category"]
        appeal_recommended = bool(decision.get("appeal_recommended"))
        auto_submit = (
            bool(decision.get("auto_submit"))
            and category in ("Coding / DX", "Eligibility", "Coding")
            and days_to_deadline > 7
        )

        appeal_text: str | None = None
        submitted = False
        case_number = None
        if appeal_recommended:
            template_cat = "Coding" if "Coding" in category else (
                "Eligibility" if "Eligibility" in category else (
                    "Prior Auth" if "Auth" in category else (
                        "Med Necessity" if "Necessity" in category else (
                            "Timely Filing" if "Timely" in category else "Coding"
                        )
                    )
                )
            )
            template = get_appeal_template(template_cat, claim["payer_id"])
            appeal_text = render_appeal_letter(
                template,
                {
                    **claim,
                    "patient_name": clinical.get("patient_name", "Patient"),
                    "provider_npi": clinical.get("attending_physician", ""),
                    "corrected_codes_text": (
                        f"- CPT: {decision['corrected_codes'].get('cpt', '')}\n"
                        f"- ICD-10: {decision['corrected_codes'].get('icd10', '')}"
                        if decision.get("corrected_codes") else ""
                    ),
                },
                denial,
                decision.get("clinical_summary", ""),
            )

            if auto_submit:
                # Self-review gate: only submit if review passes with confidence >= 0.85
                review = self_review_appeal_letter(appeal_text, claim)
                await self.tool_call("denial", denial_id, "self_review_appeal_letter",
                                     {"denial_id": denial_id},
                                     f"passes={review['passes']} confidence={review['confidence']}")
                if review["passes"] and review["confidence"] >= 0.85:
                    result = await submit_appeal(denial_id, appeal_text)
                    submitted = bool(result.get("success"))
                    case_number = result.get("case_number")
                    await self.tool_call("denial", denial_id, "submit_appeal",
                                         {"denial_id": denial_id},
                                         f"submitted={submitted} case_number={case_number}")
                else:
                    # Review failed — route to human
                    await self.create_hitl_task(
                        "denial", denial_id,
                        f"Appeal self-review failed — {review['failed_checks']}",
                        "High",
                        "Review and fix appeal letter before submission",
                        decision.get("_reasoning", ""),
                    )
            else:
                await self.create_hitl_task(
                    "denial", denial_id,
                    f"Appeal ready for review — {category}",
                    "High",
                    "Review and submit appeal letter",
                    decision.get("_reasoning", ""),
                )

        status = "complete" if submitted else "escalated" if appeal_recommended else "complete"
        output = AgentOutput(
            status=status,
            result={
                "denial_category": category,
                "appeal_recommended": appeal_recommended,
                "auto_submitted": submitted,
                "case_number": case_number,
                "appeal_letter_text": appeal_text,
                "days_to_deadline": days_to_deadline,
            },
            reasoning_trace=decision.get("_reasoning", ""),
            confidence=0.92 if auto_submit else 0.80,
            hitl_required=appeal_recommended and not submitted,
            hitl_reason=None if submitted else "Appeal review",
        )
        if status == "escalated":
            await self.escalated(input, "appeal HITL review", output)
        await self.completed(input, output)
        return output
