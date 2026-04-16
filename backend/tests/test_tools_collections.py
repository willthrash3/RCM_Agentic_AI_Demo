"""Unit tests for collections_tools."""

from __future__ import annotations

import pytest


def test_generate_statement_contains_balance():
    from app.tools.collections_tools import generate_statement
    stmt = generate_statement("pt-001", "clm-001", 150.0)
    assert "150.00" in stmt
    assert "pt-001" in stmt


def test_generate_payment_plan_small_balance():
    from app.tools.collections_tools import generate_payment_plan
    plan = generate_payment_plan("pt-001", 300.0)
    assert plan["months"] == 3
    assert plan["patient_id"] == "pt-001"
    assert plan["apr"] == 0.0
    assert abs(plan["monthly_amount"] - 100.0) < 0.01


def test_generate_payment_plan_medium_balance():
    from app.tools.collections_tools import generate_payment_plan
    plan = generate_payment_plan("pt-001", 1000.0)
    assert plan["months"] == 6


def test_generate_payment_plan_large_balance():
    from app.tools.collections_tools import generate_payment_plan
    plan = generate_payment_plan("pt-001", 5000.0)
    assert plan["months"] == 12


def test_send_outreach_returns_sent():
    from app.tools.collections_tools import send_outreach
    result = send_outreach("pt-001", "email", "standard_statement", "Hello")
    assert result["status"] == "sent"
    assert result["outreach_id"].startswith("out-")
    assert result["patient_id"] == "pt-001"


def test_check_charity_care_eligibility_missing_patient():
    from app.tools.collections_tools import check_charity_care_eligibility
    result = check_charity_care_eligibility("pt-nonexistent-xyz", 1000.0)
    assert result["eligible"] is False


def test_get_patient_balances_returns_list():
    from app.tools.collections_tools import get_patient_balances
    result = get_patient_balances()
    assert isinstance(result, list)
    for item in result:
        assert "patient_id" in item
        assert "balance" in item
