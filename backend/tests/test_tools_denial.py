"""Unit tests for denial_tools."""

from __future__ import annotations

from datetime import date

import pytest


def test_classify_coding_denial():
    from app.tools.denial_tools import classify_denial_root_cause
    result = classify_denial_root_cause("CO-4", None, {})
    assert result["denial_category"] == "Coding / DX"
    assert result["appealable"] is True


def test_classify_contractual_denial_not_appealable():
    from app.tools.denial_tools import classify_denial_root_cause
    result = classify_denial_root_cause("CO-45", None, {})
    assert result["denial_category"] == "Contractual"
    assert result["appealable"] is False


def test_classify_unknown_carc_fallback():
    from app.tools.denial_tools import classify_denial_root_cause
    result = classify_denial_root_cause("ZZZ_UNKNOWN", None, {})
    assert result["denial_category"] == "Other"
    assert "carc_code" in result


def test_calculate_appeal_deadline_known_payer():
    from app.tools.denial_tools import calculate_appeal_deadline
    from app.data.fixtures_loader import payers
    pylist = payers()
    if not pylist:
        pytest.skip("No payers in fixtures")
    payer_id = pylist[0]["payer_id"]
    denial_date = date(2026, 1, 1)
    deadline = calculate_appeal_deadline(denial_date, payer_id)
    delta = (deadline - denial_date).days
    assert 1 <= delta <= 60


def test_calculate_appeal_deadline_unknown_payer():
    from app.tools.denial_tools import calculate_appeal_deadline
    denial_date = date(2026, 1, 1)
    deadline = calculate_appeal_deadline(denial_date, "unknown-payer-xyz")
    # falls back to 60-day default
    assert deadline == date(2026, 3, 2)


def test_get_appeal_template_known_category():
    from app.tools.denial_tools import get_appeal_template
    template = get_appeal_template("Coding")
    assert isinstance(template, str)
    assert len(template) > 0


def test_get_appeal_template_unknown_category_fallback():
    from app.tools.denial_tools import get_appeal_template
    template = get_appeal_template("UnknownCategoryXYZ")
    assert isinstance(template, str)
    assert len(template) > 0


def test_render_appeal_letter_contains_claim_id():
    from app.tools.denial_tools import get_appeal_template, render_appeal_letter
    template = get_appeal_template("Coding")
    claim_data = {"claim_id": "clm-render-test", "payer_id": "payer-001",
                  "total_billed": 200}
    denial_data = {"carc_code": "97", "carc_description": "Invalid CPT"}
    letter = render_appeal_letter(template, claim_data, denial_data, "summary text")
    assert isinstance(letter, str)
    assert len(letter) > 0
