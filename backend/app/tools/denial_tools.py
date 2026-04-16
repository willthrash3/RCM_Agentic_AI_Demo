"""Denial-management tools."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from jinja2 import Template

from app.config import get_settings
from app.data.fixtures_loader import appeal_templates, carc_rarc, payers
from app.database import get_connection, transaction


_CARC_LOOKUP = {c["code"]: c for c in carc_rarc()["carc"]}


def get_denial_detail(denial_id: str) -> dict[str, Any]:
    conn = get_connection()
    row = conn.execute(
        """SELECT denial_id, claim_id, carc_code, rarc_code, denial_category,
                  denial_date, appeal_deadline, agent_root_cause,
                  appeal_letter_text, appeal_submitted_at, overturn_flag
             FROM denials WHERE denial_id = ?""",
        (denial_id,),
    ).fetchone()
    if not row:
        return {}
    cols = ["denial_id", "claim_id", "carc_code", "rarc_code", "denial_category",
            "denial_date", "appeal_deadline", "agent_root_cause", "appeal_letter_text",
            "appeal_submitted_at", "overturn_flag"]
    out = dict(zip(cols, row))
    carc_meta = _CARC_LOOKUP.get(out["carc_code"])
    if carc_meta:
        out["carc_description"] = carc_meta["description"]
    return out


def get_claim_detail(claim_id: str) -> dict[str, Any]:
    from app.tools.claim_tools import get_claim_with_lines
    return get_claim_with_lines(claim_id)


def get_prior_auth_record(encounter_id: str) -> dict[str, Any] | None:
    from app.tools.claim_tools import get_prior_auth_status
    out = get_prior_auth_status(encounter_id)
    return out if out.get("status") != "Not Found" else None


def get_clinical_documentation(encounter_id: str) -> dict[str, Any]:
    from app.tools.coding_tools import get_encounter_note
    return get_encounter_note(encounter_id)


def classify_denial_root_cause(
    carc_code: str, rarc_code: str | None, claim_context: dict[str, Any]
) -> dict[str, Any]:
    meta = _CARC_LOOKUP.get(carc_code, {"category": "Other", "description": ""})
    category = meta["category"]
    root_cause_text = {
        "Coding / DX": "Code combination was rejected; review procedure/diagnosis linkage.",
        "Prior Auth": "Authorization was not obtained or invalid at time of service.",
        "Eligibility": "Patient coverage issue on date of service.",
        "Timely Filing": "Claim submitted outside the payer filing window.",
        "Duplicate": "Claim duplicates an already adjudicated submission.",
        "Med Necessity": "Payer determined service does not meet medical necessity criteria.",
        "Contractual": "Payment reduced by contractual allowable; not appealable.",
        "Other": "Miscellaneous denial; review CARC narrative.",
    }.get(category, "Review CARC and clinical documentation.")
    return {
        "denial_category": category,
        "root_cause": root_cause_text,
        "carc_code": carc_code,
        "carc_description": meta["description"],
        "appealable": category not in ("Contractual",),
    }


def calculate_appeal_deadline(denial_date: date, payer_id: str) -> date:
    payer = next((p for p in payers() if p["payer_id"] == payer_id), None)
    window = (payer["timely_filing_days"] // 2) if payer else 60
    return denial_date + timedelta(days=min(60, window))


def get_appeal_template(denial_category: str, payer_id: str | None = None) -> str:
    templates = appeal_templates()
    return templates.get(denial_category, templates.get("Coding", "{{ today }}"))


def render_appeal_letter(
    template: str, claim_data: dict, denial_data: dict, clinical_summary: str
) -> str:
    payer = next((p for p in payers() if p["payer_id"] == claim_data.get("payer_id")), None)
    corrected_bullets = claim_data.get("corrected_codes_text") or "- (See corrected claim submission attached)"
    ctx = {
        "today": date.today().isoformat(),
        "payer_name": payer["payer_name"] if payer else "Payer",
        "payer_address": "Appeals Department\nP.O. Box 1234\nAnytown, USA",
        "patient_name": claim_data.get("patient_name", "Patient"),
        "member_id": claim_data.get("member_id", claim_data.get("patient_id", "")),
        "claim_id": claim_data.get("claim_id", denial_data.get("claim_id", "")),
        "service_date": claim_data.get("service_date", ""),
        "provider_npi": claim_data.get("provider_npi", ""),
        "provider_name": claim_data.get("provider_name", "Provider"),
        "facility_name": "Envision Health System",
        "billed_amount": str(claim_data.get("total_billed", "")),
        "carc_code": denial_data.get("carc_code", ""),
        "carc_description": denial_data.get("carc_description", ""),
        "corrected_codes_bullets": corrected_bullets,
        "clinical_summary": clinical_summary,
        "verified_date": claim_data.get("verified_date", ""),
        "plan_type": claim_data.get("plan_type", ""),
        "in_network_status": "In-network",
        "effective_date": claim_data.get("effective_date", ""),
        "submission_date": claim_data.get("submission_date", ""),
        "filing_days": payer["timely_filing_days"] if payer else 90,
        "filing_deadline": claim_data.get("timely_filing_deadline", ""),
    }
    return Template(template).render(**ctx)


async def submit_appeal(denial_id: str, appeal_letter_text: str) -> dict[str, Any]:
    conn = get_connection()
    row = conn.execute(
        "SELECT claim_id FROM denials WHERE denial_id = ?", (denial_id,)
    ).fetchone()
    if not row:
        return {"success": False, "reason": "denial not found"}
    claim_id = row[0]
    payer_row = conn.execute(
        "SELECT payer_id FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if not payer_row:
        return {"success": False, "reason": "claim not found"}
    payer = next((p for p in payers() if p["payer_id"] == payer_row[0]), None)
    x12 = payer["payer_id_x12"] if payer else payer_row[0]
    url = f"{get_settings().mock_payer_base_url.rstrip('/')}/payer/{x12}/appeal/submit"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            url,
            json={"denial_id": denial_id, "claim_id": claim_id, "letter_excerpt": appeal_letter_text[:500]},
        )
        body = resp.json() if resp.status_code == 200 else {"case_number": None}
    with transaction() as c:
        c.execute(
            """UPDATE denials SET appeal_letter_text = ?, appeal_submitted_at = ? WHERE denial_id = ?""",
            (appeal_letter_text, datetime.utcnow(), denial_id),
        )
        c.execute(
            "UPDATE claims SET claim_status = 'Appealed' WHERE claim_id = ?", (claim_id,)
        )
    return {"success": True, "case_number": body.get("case_number")}
