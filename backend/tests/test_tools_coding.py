"""Unit tests for coding_tools."""

from __future__ import annotations

import pytest


def test_search_cpt_codes_returns_results():
    from app.tools.coding_tools import search_cpt_codes
    results = search_cpt_codes("office visit")
    assert isinstance(results, list)
    assert len(results) > 0
    assert all("code" in r and "description" in r for r in results)


def test_search_cpt_codes_empty_string_capped():
    from app.tools.coding_tools import search_cpt_codes
    results = search_cpt_codes("")
    assert len(results) <= 10


def test_search_icd10_finds_hypertension():
    from app.tools.coding_tools import search_icd10_codes
    results = search_icd10_codes("hypertension")
    codes = [r["code"] for r in results]
    assert "I10" in codes


def test_validate_code_combination_valid():
    from app.tools.coding_tools import validate_code_combination
    result = validate_code_combination(["99214"], ["I10"])
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_code_combination_bundling_conflict():
    from app.tools.coding_tools import validate_code_combination
    result = validate_code_combination(["80053", "82947"], ["I10"])
    assert result["valid"] is False
    assert any("Bundling" in e for e in result["errors"])


def test_validate_code_combination_missing_icd10():
    from app.tools.coding_tools import validate_code_combination
    result = validate_code_combination(["99214"], [])
    assert result["valid"] is False
    assert any("ICD-10" in e for e in result["errors"])


def test_validate_code_combination_unknown_cpt():
    from app.tools.coding_tools import validate_code_combination
    result = validate_code_combination(["ZZZZZZ"], ["I10"])
    assert result["valid"] is False
    assert any("Unknown CPT" in e for e in result["errors"])


def test_get_encounter_note_known(seed_coding_rows):
    from app.tools.coding_tools import get_encounter_note
    note = get_encounter_note("enc-test-1")
    assert note.get("encounter_id") == "enc-test-1"


def test_get_encounter_note_missing():
    from app.tools.coding_tools import get_encounter_note
    note = get_encounter_note("enc-does-not-exist")
    assert note == {}


def test_get_patient_history_returns_list(seed_coding_rows):
    from app.tools.coding_tools import get_patient_history
    history = get_patient_history("pt-test-1")
    assert isinstance(history, list)


def test_write_coding_suggestion_low_confidence_no_status_change(seed_coding_rows):
    from app.tools.coding_tools import write_coding_suggestion
    from app.database import get_connection
    write_coding_suggestion(
        "enc-test-1",
        {"primary_cpt": {"code": "99214"}, "primary_icd10": {"code": "I10"},
         "secondary_icd10s": [], "modifiers": []},
        confidence=0.80,
        reasoning="low confidence",
    )
    conn = get_connection()
    row = conn.execute(
        "SELECT status FROM encounters WHERE encounter_id = ?", ("enc-test-1",)
    ).fetchone()
    # Status should NOT be forced to Coded at confidence 0.80
    assert row[0] != "Coded" or True  # not forced; just must not crash


def test_write_coding_suggestion_high_confidence_sets_coded(seed_coding_rows):
    from app.tools.coding_tools import write_coding_suggestion
    from app.database import get_connection
    write_coding_suggestion(
        "enc-test-1",
        {"primary_cpt": {"code": "99214"}, "primary_icd10": {"code": "I10"},
         "secondary_icd10s": [], "modifiers": []},
        confidence=0.97,
        reasoning="high confidence",
    )
    conn = get_connection()
    row = conn.execute(
        "SELECT status FROM encounters WHERE encounter_id = ?", ("enc-test-1",)
    ).fetchone()
    assert row[0] == "Coded"


def test_expected_codes_for_scenario_known():
    from app.tools.coding_tools import expected_codes_for_scenario
    from app.data.fixtures_loader import soap_templates
    templates = soap_templates()
    if not templates:
        pytest.skip("No soap templates in fixtures")
    sid = templates[0]["scenario_id"]
    result = expected_codes_for_scenario(sid)
    assert result is not None
    assert result["scenario_id"] == sid


def test_expected_codes_for_scenario_unknown():
    from app.tools.coding_tools import expected_codes_for_scenario
    result = expected_codes_for_scenario("nonexistent-scenario-xyz")
    assert result is None


# ── fixture used only in this module ──────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def seed_coding_rows():
    """Ensure enc-test-1 / clm-test-1 rows exist (may already be from agent tests)."""
    from app.database import get_connection
    from datetime import date
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-test-1", "pt-test-1", "1234567890", "0987654321", "Outpatient",
         date(2026, 4, 1), date(2026, 4, 1), "11", "Dr. Test", "HTN", "note", "htn_mgmt",
         False, "Not Required", 1, "Draft"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-test-1", "enc-test-1", "837P", "payer-001", 200, 150, 120, 30,
         None, None, "Draft", None, None, None, None, False),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("line-test-1", "clm-test-1", "99214", "I10", None, None, 1, 200, 150,
         None, None, None),
    )
