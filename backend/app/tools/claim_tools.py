"""Claim-level tools: lookup, scrubbing, tracking."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.config import get_settings
from app.data.fixtures_loader import cpt_codes, payer_edit_rules, payers
from app.database import locked, transaction
from app.utils.time import get_demo_today


def get_claim_with_lines(claim_id: str) -> dict[str, Any]:
    with locked() as conn:
        claim_row = conn.execute(
            """SELECT claim_id, encounter_id, claim_type, payer_id, total_billed,
                      total_allowed, total_paid, patient_responsibility, submission_date,
                      adjudication_date, claim_status, rejection_reason,
                      timely_filing_deadline, scrub_score, era_posted
                 FROM claims WHERE claim_id = ?""",
            (claim_id,),
        ).fetchone()
        if not claim_row:
            return {}
        cols = ["claim_id", "encounter_id", "claim_type", "payer_id", "total_billed",
                "total_allowed", "total_paid", "patient_responsibility", "submission_date",
                "adjudication_date", "claim_status", "rejection_reason",
                "timely_filing_deadline", "scrub_score", "era_posted"]
        claim = dict(zip(cols, claim_row))
        lines = conn.execute(
            """SELECT line_id, cpt_code, icd10_primary, icd10_secondary, modifier,
                      units, charge_amount, allowed_amount, coding_confidence
                 FROM claim_lines WHERE claim_id = ?""",
            (claim_id,),
        ).fetchall()
        lcols = ["line_id", "cpt_code", "icd10_primary", "icd10_secondary", "modifier",
                 "units", "charge_amount", "allowed_amount", "coding_confidence"]
        claim["lines"] = [dict(zip(lcols, r)) for r in lines]
    return claim


def get_payer_edit_rules(payer_id: str) -> list[dict[str, Any]]:
    rules = payer_edit_rules()
    return rules.get(payer_id, [])


def check_lcd_ncd(cpt_code: str, icd10_code: str) -> dict[str, Any]:
    """Simplified LCD/NCD check: look across all payer rules for dx restrictions."""
    for payer_id, rules in payer_edit_rules().items():
        for rule in rules:
            if rule.get("cpt") == cpt_code and rule.get("requires_dx_in"):
                if icd10_code not in rule["requires_dx_in"]:
                    return {
                        "covered": False,
                        "reason": f"{payer_id}: {rule['description']}",
                    }
    return {"covered": True, "reason": ""}


def check_bundling_rules(cpt_list: list[str]) -> list[dict[str, Any]]:
    from app.tools.coding_tools import BUNDLING_CONFLICTS
    conflicts: list[dict[str, Any]] = []
    for a, b in BUNDLING_CONFLICTS:
        if a in cpt_list and b in cpt_list:
            conflicts.append({"cpt1": a, "cpt2": b, "rule": "NCCI bundle"})
    return conflicts


def get_prior_auth_status(encounter_id: str, cpt_code: str | None = None) -> dict[str, Any]:
    with locked() as conn:
        row = conn.execute(
            """SELECT auth_id, cpt_code, status, auth_number, decision_at
                 FROM prior_auths WHERE encounter_id = ? LIMIT 1""",
            (encounter_id,),
        ).fetchone()
    if not row:
        return {"status": "Not Found", "encounter_id": encounter_id}
    return {
        "auth_id": row[0], "cpt_code": row[1], "status": row[2],
        "auth_number": row[3], "decision_at": row[4],
    }


# Simple "logistic" rejection predictor — demo-grade but deterministic.
_PAYER_RISK = {p["payer_id"]: p["denial_rate_baseline"] for p in payers()}


def predict_rejection_probability(claim_features: dict[str, Any]) -> float:
    """Probability the claim will be rejected (0..1)."""
    baseline = _PAYER_RISK.get(claim_features.get("payer_id"), 0.10)
    score = baseline
    if claim_features.get("missing_auth"):
        score += 0.35
    if claim_features.get("lcd_fail"):
        score += 0.30
    if claim_features.get("missing_modifier"):
        score += 0.15
    if claim_features.get("has_bundling_conflict"):
        score += 0.25
    if claim_features.get("timely_filing_risk"):
        score += 0.10
    return min(0.99, round(score, 3))


def write_scrub_result(claim_id: str, score: float, edits: list[dict], release_flag: bool) -> None:
    with transaction() as conn:
        conn.execute("UPDATE claims SET scrub_score = ? WHERE claim_id = ?", (score, claim_id))
        if release_flag:
            conn.execute(
                "UPDATE claims SET claim_status = 'Submitted', submission_date = ? WHERE claim_id = ?",
                (get_demo_today(), claim_id),
            )


def get_submitted_claims(days_submitted_min: int = 1) -> list[dict[str, Any]]:
    threshold = get_demo_today() - timedelta(days=days_submitted_min)
    with locked() as conn:
        rows = conn.execute(
            """SELECT claim_id, payer_id, submission_date, total_billed, claim_status
                 FROM claims
                WHERE claim_status = 'Submitted' AND submission_date <= ?""",
            (threshold,),
        ).fetchall()
    return [
        {"claim_id": r[0], "payer_id": r[1], "submission_date": r[2],
         "total_billed": r[3], "claim_status": r[4]}
        for r in rows
    ]


async def query_payer_claim_status(claim_id: str, payer_id: str) -> dict[str, Any]:
    payer_lookup = next((p for p in payers() if p["payer_id"] == payer_id), None)
    x12 = payer_lookup["payer_id_x12_fictional"] if payer_lookup else payer_id
    url = f"{get_settings().mock_payer_base_url.rstrip('/')}/payer/{x12}/claim/status"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(url, params={"claim_id": claim_id})
        resp.raise_for_status()
        return resp.json()


def get_contract_allowable(cpt_code: str, payer_id: str) -> Decimal:
    payer = next((p for p in payers() if p["payer_id"] == payer_id), None)
    cpt = next((c for c in cpt_codes() if c["code"] == cpt_code), None)
    if not payer or not cpt:
        return Decimal("0.00")
    return Decimal(str(round(cpt["base_charge"] * payer["fee_schedule_multiplier"] * 0.75, 2)))


def flag_underpayment(claim_id: str, expected: Decimal, actual: Decimal, variance_pct: float) -> str:
    task_id = f"hitl-{uuid.uuid4().hex[:10]}"
    with transaction() as conn:
        conn.execute(
            """INSERT INTO hitl_tasks
                   (task_id, agent_name, entity_type, entity_id, task_description,
                    priority, recommended_action, agent_reasoning, status, created_at,
                    resolved_at, decision, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id, "tracking_agent", "claim", claim_id,
             f"Potential underpayment: ${expected - actual:.2f} below contract allowable",
             "Medium", "Review payer contract and file short-pay appeal if justified",
             f"Expected ${expected:.2f}, received ${actual:.2f} ({variance_pct:.1%} variance)",
             "pending", datetime.utcnow(), None, None, None),
        )
    return task_id


def flag_timely_filing_risk(claim_id: str, days_remaining: int) -> str:
    with locked() as conn:
        existing = conn.execute(
            """SELECT task_id FROM hitl_tasks
                WHERE entity_id = ? AND agent_name = 'tracking_agent'
                  AND task_description LIKE 'Timely filing%' AND status = 'pending'
                LIMIT 1""",
            (claim_id,),
        ).fetchone()
    if existing:
        return existing[0]
    task_id = f"hitl-{uuid.uuid4().hex[:10]}"
    priority = "High" if days_remaining < 7 else "Medium"
    with transaction() as conn:
        conn.execute(
            """INSERT INTO hitl_tasks
                   (task_id, agent_name, entity_type, entity_id, task_description,
                    priority, recommended_action, agent_reasoning, status, created_at,
                    resolved_at, decision, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (task_id, "tracking_agent", "claim", claim_id,
             f"Timely filing risk: {days_remaining} days remaining before deadline",
             priority, "Submit or escalate immediately to avoid timely filing denial",
             f"{days_remaining} days left before timely filing deadline",
             "pending", datetime.utcnow(), None, None, None),
        )
    return task_id


def update_claim_status(claim_id: str, new_status: str) -> None:
    with transaction() as conn:
        conn.execute("UPDATE claims SET claim_status = ? WHERE claim_id = ?", (new_status, claim_id))
