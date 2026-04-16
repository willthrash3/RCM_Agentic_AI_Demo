"""Unit tests for era_tools."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest


@pytest.fixture(scope="module", autouse=True)
def seed_era_rows():
    from app.database import get_connection
    conn = get_connection()
    # Seed an encounter for ERA claims to reference
    conn.execute(
        """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("enc-era-1", "pt-era-1", "1111111111", "2222222222", "Outpatient",
         date(2026, 2, 1), date(2026, 2, 1), "11", "Dr. ERA", "HTN", "note", None,
         False, "Not Required", 1, "Coded"),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("clm-era-1", "enc-era-1", "837P", "payer-001", 500, 450, None, 50,
         date(2026, 2, 5), None, "Paid", None, date(2026, 8, 1), None, None, False),
    )
    conn.execute(
        """INSERT OR REPLACE INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("line-era-1", "clm-era-1", "99214", "I10", None, None, 1, 500, 450,
         None, None, 0.92),
    )


def test_get_unposted_eras_returns_list():
    from app.tools.era_tools import get_unposted_eras
    eras = get_unposted_eras()
    assert isinstance(eras, list)


def test_post_payment_updates_claim(seed_era_rows):
    from app.tools.era_tools import post_payment
    from app.database import get_connection
    post_payment("clm-era-1", Decimal("450.00"), [], Decimal("50.00"))
    conn = get_connection()
    row = conn.execute(
        "SELECT era_posted, claim_status, total_paid FROM claims WHERE claim_id = ?",
        ("clm-era-1",),
    ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] == "Paid"
    assert float(row[2]) == pytest.approx(450.0)


def test_create_patient_statement_returns_id():
    from app.tools.era_tools import create_patient_statement
    stmt_id = create_patient_statement("pt-era-1", "clm-era-1", Decimal("50.00"))
    assert stmt_id.startswith("stmt-")


def test_route_exception_no_crash():
    from app.tools.era_tools import route_exception
    result = route_exception("era-001", None, "test reason")
    assert result is None


def test_era_grouping_batches_of_four():
    """Five eligible claims → 2 ERA objects (batch of 4, batch of 1)."""
    from app.database import get_connection
    from app.tools.era_tools import get_unposted_eras
    conn = get_connection()
    # Insert 5 unposted Paid claims
    for i in range(5):
        enc_id = f"enc-era-batch-{i}"
        clm_id = f"clm-era-batch-{i}"
        conn.execute(
            """INSERT OR REPLACE INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (enc_id, f"pt-era-batch-{i}", "1111111111", "2222222222", "Outpatient",
             date(2026, 1, i + 1), date(2026, 1, i + 1), "11", "Dr. ERA", "HTN",
             "note", None, False, "Not Required", 1, "Coded"),
        )
        conn.execute(
            """INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (clm_id, enc_id, "837P", "payer-001", 100, 90, 80, 10,
             date(2026, 1, i + 2), None, "Paid", None, None, None, None, False),
        )
    eras = get_unposted_eras()
    # Should have at least 2 ERA batches for our 5 new rows
    assert len(eras) >= 2
