"""Unit tests for claim_tools."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture(scope="module", autouse=True)
def seed_claim_rows():
    from app.database import get_connection
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-claim-1", "pt-claim-1", "1234567890", "0987654321", "Outpatient",
         date(2026, 3, 1), date(2026, 3, 1), "11", "Dr. Claim", "HTN", "note", None,
         False, "Not Required", 1, "Coded"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-claim-1", "enc-claim-1", "837P", "payer-001", 300, 250, 200, 50,
         date(2026, 3, 5), date(2026, 3, 20), "Paid", None,
         date(2026, 6, 1), None, None, False),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("line-claim-1", "clm-claim-1", "99214", "I10", None, None, 1, 300, 250,
         None, None, 0.95),
    )


def test_predict_rejection_probability_baseline():
    from app.tools.claim_tools import predict_rejection_probability
    prob = predict_rejection_probability({"payer_id": "payer-001"})
    assert 0.0 <= prob <= 1.0


def test_predict_rejection_probability_with_missing_auth():
    from app.tools.claim_tools import predict_rejection_probability
    base = predict_rejection_probability({"payer_id": "payer-001"})
    high = predict_rejection_probability({"payer_id": "payer-001", "missing_auth": True})
    assert high > base


def test_predict_rejection_probability_capped():
    from app.tools.claim_tools import predict_rejection_probability
    prob = predict_rejection_probability({
        "payer_id": "payer-001",
        "missing_auth": True,
        "lcd_fail": True,
        "missing_modifier": True,
        "has_bundling_conflict": True,
        "timely_filing_risk": True,
    })
    assert prob <= 0.99


def test_predict_rejection_unknown_payer_uses_default():
    from app.tools.claim_tools import predict_rejection_probability
    prob = predict_rejection_probability({"payer_id": "unknown-payer-xyz"})
    assert prob == pytest.approx(0.10)


def test_check_lcd_ncd_common_combination():
    from app.tools.claim_tools import check_lcd_ncd
    result = check_lcd_ncd("99214", "I10")
    assert "covered" in result


def test_check_bundling_rules_conflict():
    from app.tools.claim_tools import check_bundling_rules
    conflicts = check_bundling_rules(["80053", "82947"])
    assert len(conflicts) > 0
    assert conflicts[0]["cpt1"] == "80053"


def test_check_bundling_rules_no_conflict():
    from app.tools.claim_tools import check_bundling_rules
    conflicts = check_bundling_rules(["99214"])
    assert conflicts == []


def test_get_claim_with_lines_known():
    from app.tools.claim_tools import get_claim_with_lines
    claim = get_claim_with_lines("clm-claim-1")
    assert claim["claim_id"] == "clm-claim-1"
    assert "lines" in claim
    assert len(claim["lines"]) > 0


def test_get_claim_with_lines_missing():
    from app.tools.claim_tools import get_claim_with_lines
    claim = get_claim_with_lines("clm-does-not-exist")
    assert claim == {}


def test_write_scrub_result_persists():
    from app.tools.claim_tools import write_scrub_result
    from app.database import get_connection
    write_scrub_result("clm-claim-1", score=0.88, edits=[], release_flag=False)
    conn = get_connection()
    row = conn.execute(
        "SELECT scrub_score FROM claims WHERE claim_id = ?", ("clm-claim-1",)
    ).fetchone()
    assert row is not None
    assert abs(float(row[0]) - 0.88) < 0.001


def test_update_claim_status():
    from app.tools.claim_tools import update_claim_status
    from app.database import get_connection
    update_claim_status("clm-claim-1", "Denied")
    conn = get_connection()
    row = conn.execute(
        "SELECT claim_status FROM claims WHERE claim_id = ?", ("clm-claim-1",)
    ).fetchone()
    assert row[0] == "Denied"
    # restore
    update_claim_status("clm-claim-1", "Paid")


def test_get_contract_allowable_known():
    from app.tools.claim_tools import get_contract_allowable
    from app.data.fixtures_loader import cpt_codes, payers
    # pick a CPT and payer that exist in fixtures
    cplist = cpt_codes()
    pylist = payers()
    if not cplist or not pylist:
        pytest.skip("Fixtures empty")
    cpt = cplist[0]["code"]
    payer = pylist[0]["payer_id"]
    allowable = get_contract_allowable(cpt, payer)
    assert allowable > Decimal("0.00")


def test_get_contract_allowable_unknown():
    from app.tools.claim_tools import get_contract_allowable
    allowable = get_contract_allowable("ZZZZ", "unknown-payer")
    assert allowable == Decimal("0.00")
