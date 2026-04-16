"""Coding-related tools: encounter notes, CPT/ICD lookup, code validation."""

from __future__ import annotations

from typing import Any

from app.data.fixtures_loader import cpt_codes, icd10_codes, soap_templates
from app.database import locked, transaction


def get_encounter_note(encounter_id: str) -> dict[str, Any]:
    with locked() as conn:
        row = conn.execute(
            """SELECT encounter_id, patient_id, service_date, encounter_type,
                      place_of_service, chief_complaint, soap_note_text, scenario_id,
                      attending_physician
                 FROM encounters WHERE encounter_id = ?""",
            (encounter_id,),
        ).fetchone()
    if not row:
        return {}
    cols = ["encounter_id", "patient_id", "service_date", "encounter_type",
            "place_of_service", "chief_complaint", "soap_note_text", "scenario_id",
            "attending_physician"]
    return dict(zip(cols, row))


def get_patient_history(patient_id: str, limit: int = 5) -> list[dict[str, Any]]:
    with locked() as conn:
        rows = conn.execute(
            """SELECT encounter_id, service_date, chief_complaint, status
                 FROM encounters WHERE patient_id = ?
                 ORDER BY service_date DESC LIMIT ?""",
            (patient_id, limit),
        ).fetchall()
    return [
        {"encounter_id": r[0], "service_date": r[1], "chief_complaint": r[2], "status": r[3]}
        for r in rows
    ]


def search_cpt_codes(description: str) -> list[dict[str, Any]]:
    needle = description.lower()
    return [c for c in cpt_codes() if needle in c["description"].lower()][:10]


def search_icd10_codes(description: str) -> list[dict[str, Any]]:
    needle = description.lower()
    return [c for c in icd10_codes() if needle in c["description"].lower()][:10]


def _known_cpt() -> set[str]:
    return {c["code"] for c in cpt_codes()}


def _known_icd() -> set[str]:
    return {c["code"] for c in icd10_codes()}


# NCCI-style simplified bundling: certain CPT pairs should not be billed together
BUNDLING_CONFLICTS: set[tuple[str, str]] = {
    ("80053", "82947"),  # CMP includes glucose
    ("80053", "80061"),  # CMP includes lipid panel
}


def validate_code_combination(
    cpt_codes_in: list[str],
    icd10_codes_in: list[str],
    modifiers: list[str] | None = None,
) -> dict[str, Any]:
    cpt_set = _known_cpt()
    icd_set = _known_icd()
    errors: list[str] = []
    for c in cpt_codes_in:
        if c not in cpt_set:
            errors.append(f"Unknown CPT {c}")
    for i in icd10_codes_in:
        if i not in icd_set:
            errors.append(f"Unknown ICD-10 {i}")
    for a, b in BUNDLING_CONFLICTS:
        if a in cpt_codes_in and b in cpt_codes_in:
            errors.append(f"Bundling: {a} includes {b}")
    if not icd10_codes_in:
        errors.append("At least one ICD-10 code required")
    return {"valid": not errors, "errors": errors}


def write_coding_suggestion(encounter_id: str, codes: dict, confidence: float, reasoning: str) -> None:
    """Apply the coding agent's suggestion by updating or inserting claim lines.

    For the demo we update the single claim_line for this encounter's claim with
    the suggested primary CPT + ICD and confidence score.
    """
    with locked() as conn:
        claim = conn.execute(
            "SELECT claim_id FROM claims WHERE encounter_id = ? LIMIT 1", (encounter_id,)
        ).fetchone()
    if not claim:
        return
    claim_id = claim[0]
    primary_cpt = codes.get("primary_cpt", {}).get("code")
    primary_icd = codes.get("primary_icd10", {}).get("code")
    secondary = (codes.get("secondary_icd10s") or [None])[0]
    if isinstance(secondary, dict):
        secondary = secondary.get("code")
    modifier = (codes.get("modifiers") or [None])[0]
    with transaction() as c:
        c.execute(
            """UPDATE claim_lines
                 SET cpt_code = COALESCE(?, cpt_code),
                     icd10_primary = COALESCE(?, icd10_primary),
                     icd10_secondary = COALESCE(?, icd10_secondary),
                     modifier = COALESCE(?, modifier),
                     coding_confidence = ?
               WHERE claim_id = ?""",
            (primary_cpt, primary_icd, secondary, modifier, confidence, claim_id),
        )
        if confidence >= 0.95:
            c.execute(
                "UPDATE encounters SET status = 'Coded' WHERE encounter_id = ?",
                (encounter_id,),
            )


def expected_codes_for_scenario(scenario_id: str) -> dict[str, Any] | None:
    for t in soap_templates():
        if t["scenario_id"] == scenario_id:
            return t
    return None
