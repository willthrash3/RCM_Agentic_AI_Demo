"""Claim Scrubbing Agent — pre-submission edits + rejection probability.

Release criteria (PRD §4.3):
- scrub_score >= 0.90 AND no critical edits → release.
- Critical edits present → hold for review (HITL).
- Score 0.75–0.89 → flag for review.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.agents.base import BaseAgent
from app.utils.time import get_demo_today
from app.models.agent import AgentInput, AgentOutput
from app.tools.claim_tools import (
    check_bundling_rules,
    check_lcd_ncd,
    get_claim_with_lines,
    get_payer_edit_rules,
    get_prior_auth_status,
    predict_rejection_probability,
    write_scrub_result,
)


SYSTEM = """You are a claim scrubbing agent. Analyze the claim edits and produce a summary.
Return JSON:
{
  "release": boolean,
  "critical_edits": [string],
  "warnings": [string],
  "summary": string,
  "_reasoning": string
}
"""


class ScrubbingAgent(BaseAgent):
    name = "scrubbing_agent"

    async def run(self, input: AgentInput) -> AgentOutput:
        claim_id = input.entity_id
        await self.started(input, summary=f"Scrubbing claim {claim_id}")

        claim = get_claim_with_lines(claim_id)
        if not claim:
            out = AgentOutput(status="failed", result={"error": "Claim not found"},
                              reasoning_trace="", confidence=0.0)
            await self.completed(input, out)
            return out
        await self.tool_call("claim", claim_id, "get_claim_with_lines",
                             {"claim_id": claim_id},
                             f"{len(claim.get('lines', []))} line(s), "
                             f"payer={claim['payer_id']}")

        cpt_list = [ln["cpt_code"] for ln in claim.get("lines", [])]
        icd_list = [ln["icd10_primary"] for ln in claim.get("lines", [])]
        rules = get_payer_edit_rules(claim["payer_id"])
        await self.tool_call("claim", claim_id, "get_payer_edit_rules",
                             {"payer_id": claim["payer_id"]}, f"{len(rules)} rule(s)")

        critical: list[str] = []
        warnings: list[str] = []
        features = {"payer_id": claim["payer_id"]}

        # LCD/NCD
        for ln in claim.get("lines", []):
            cov = check_lcd_ncd(ln["cpt_code"], ln["icd10_primary"])
            if not cov["covered"]:
                critical.append(f"LCD fail: CPT {ln['cpt_code']} / ICD {ln['icd10_primary']} — {cov['reason']}")
                features["lcd_fail"] = True

        # Bundling
        conflicts = check_bundling_rules(cpt_list)
        if conflicts:
            critical.append(f"Bundling conflicts: {conflicts}")
            features["has_bundling_conflict"] = True

        # Payer-specific rules
        for rule in rules:
            if rule.get("requires_auth") and rule.get("cpt") in cpt_list:
                auth = get_prior_auth_status(claim.get("encounter_id", ""), rule["cpt"])
                if auth.get("status") not in ("Approved",):
                    critical.append(f"Auth missing for CPT {rule['cpt']}")
                    features["missing_auth"] = True
            if rule.get("requires_dx_in"):
                for ln in claim.get("lines", []):
                    if ln["cpt_code"] == rule["cpt"] and ln["icd10_primary"] not in rule["requires_dx_in"]:
                        critical.append(f"Payer LCD: {rule['description']}")
                        features["lcd_fail"] = True
            if rule.get("requires_modifier_if_same_day_as"):
                if rule["cpt"] in cpt_list and any(c in cpt_list for c in rule["requires_modifier_if_same_day_as"]):
                    if not any(ln["modifier"] == rule["modifier"] for ln in claim.get("lines", [])):
                        warnings.append(f"Missing modifier {rule['modifier']} on CPT {rule['cpt']}")
                        features["missing_modifier"] = True

        # Timely filing
        tf = claim.get("timely_filing_deadline")
        if tf:
            days_remaining = (tf - get_demo_today()).days if hasattr(tf, "days") else (
                (tf - get_demo_today()).days if tf else 999
            )
            if days_remaining < 14 and days_remaining >= 0:
                warnings.append(f"Timely filing risk: {days_remaining} days left")
                features["timely_filing_risk"] = True

        rejection_prob = predict_rejection_probability(features)
        scrub_score = round(1.0 - rejection_prob, 3)
        await self.tool_call("claim", claim_id, "predict_rejection_probability", features,
                             f"p_reject={rejection_prob} scrub_score={scrub_score}")

        decision = await self.call_llm(
            system=SYSTEM,
            user=(
                f"Claim: {claim_id} payer={claim['payer_id']} "
                f"status={claim['claim_status']} lines={len(claim.get('lines', []))}\n"
                f"Critical edits: {critical}\n"
                f"Warnings: {warnings}\n"
                f"Scrub score: {scrub_score}\n"
                "Should we release this claim?"
            ),
            entity_type="claim", entity_id=claim_id,
            fallback={
                "release": scrub_score >= 0.90 and not critical,
                "critical_edits": critical,
                "warnings": warnings,
                "summary": f"Scrub score {scrub_score}; {len(critical)} critical, {len(warnings)} warning",
                "_reasoning": "Rule-based fallback evaluation.",
            },
        )

        release = bool(decision.get("release", False)) and not critical
        write_scrub_result(claim_id, scrub_score, [{"c": c} for c in critical], release)

        if not release:
            priority = "Critical" if critical else "High"
            await self.create_hitl_task(
                "claim", claim_id,
                f"Claim hold: {'critical edits' if critical else 'review recommended'}",
                priority,
                "Correct edits and re-scrub, or submit with notes",
                decision.get("_reasoning", ""),
            )

        status = "complete" if release else "escalated"
        output = AgentOutput(
            status=status,
            result={
                "scrub_score": scrub_score,
                "released": release,
                "critical_edits": critical,
                "warnings": warnings,
            },
            reasoning_trace=decision.get("_reasoning", ""),
            confidence=scrub_score,
            hitl_required=not release,
            hitl_reason=("critical edits" if critical else "scrub review") if not release else None,
        )
        if status == "escalated":
            await self.escalated(input, "scrub hold", output)
        await self.completed(input, output)
        return output
