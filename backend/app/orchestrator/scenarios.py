"""Scenario runner — injects scripted edge-case events to trigger agent response.

Scenarios are defined in fixtures/scenarios.json. Each scenario has an `inject`
payload that mutates the database and emits an `scenario.injected` event. The
agent reactions happen through the normal event-driven pipeline.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.agents.event_bus import emit
from app.data.fixtures_loader import scenarios as load_scenarios
from app.database import locked, transaction


async def run_scenario(scenario_id: str) -> dict:
    scenarios_list = load_scenarios()
    scenario = next((s for s in scenarios_list if s["scenario_id"] == scenario_id), None)
    if not scenario:
        raise ValueError(f"Unknown scenario {scenario_id}")
    inject = scenario["inject"]
    kind = inject["type"]

    affected: list[str] = []
    details: dict = {}

    with locked() as conn:
        if kind == "add_edit_rule":
            details["rule"] = inject["rule"]
        elif kind == "bulk_deny":
            fraction = inject["fraction"]
            rows = conn.execute(
                """SELECT claim_id, encounter_id FROM claims
                    WHERE payer_id = ? AND claim_status IN ('Submitted', 'Paid')""",
                (inject["payer_id"],),
            ).fetchall()
            subset = random.sample(rows, max(1, int(len(rows) * fraction)))
            with transaction() as c:
                for (claim_id, _enc_id) in subset:
                    c.execute(
                        """UPDATE claims SET claim_status = 'Denied', rejection_reason = ? WHERE claim_id = ?""",
                        (inject["carc_code"], claim_id),
                    )
                    denial_id = f"den-{uuid.uuid4().hex[:10]}"
                    c.execute(
                        """INSERT INTO denials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (denial_id, claim_id, inject["carc_code"], inject.get("rarc_code"),
                         inject["denial_category"], date.today(),
                         date.today() + timedelta(days=45),
                         None, None, None, None, False),
                    )
                    affected.append(claim_id)
        elif kind == "charge_lag_spike":
            with transaction() as c:
                c.execute(
                    "UPDATE encounters SET charge_lag_days = ? WHERE encounter_type = 'Outpatient' AND random() < 0.1",
                    (int(inject["avg_lag_days"]),),
                )
            details["service_line"] = inject["service_line"]
        elif kind == "lapse_coverage":
            count = int(inject["patient_count"])
            rows = conn.execute(
                "SELECT patient_id FROM patients ORDER BY random() LIMIT ?", (count,)
            ).fetchall()
            with transaction() as c:
                for (pid,) in rows:
                    eid = f"el-{uuid.uuid4().hex[:10]}"
                    c.execute(
                        """INSERT INTO eligibility_responses VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (eid, pid, "payer-001", datetime.utcnow(), Decimal("0"),
                         Decimal("0"), Decimal("0"), False, "Medicare",
                         '{"active": false, "reason": "coverage lapsed"}'),
                    )
                    affected.append(pid)
        elif kind == "underpayment":
            rows = conn.execute(
                """SELECT c.claim_id FROM claims c
                     JOIN claim_lines l ON c.claim_id = l.claim_id
                    WHERE c.payer_id = ? AND l.cpt_code = ? AND c.claim_status = 'Paid'
                    LIMIT 20""",
                (inject["payer_id"], inject["cpt_code"]),
            ).fetchall()
            with transaction() as c:
                for (claim_id,) in rows:
                    c.execute(
                        """UPDATE claims
                              SET total_paid = CAST(total_paid AS DOUBLE) * (1.0 - ?)
                            WHERE claim_id = ?""",
                        (inject["variance_pct"], claim_id),
                    )
                    affected.append(claim_id)
        elif kind == "high_value_denial":
            rows = conn.execute(
                "SELECT claim_id FROM claims WHERE claim_status = 'Submitted' ORDER BY total_billed DESC LIMIT 1"
            ).fetchall()
            if rows:
                (claim_id,) = rows[0]
                with transaction() as c:
                    c.execute(
                        "UPDATE claims SET total_billed = ?, claim_status = 'Denied', rejection_reason = ? WHERE claim_id = ?",
                        (Decimal(str(inject["amount"])), inject["carc_code"], claim_id),
                    )
                    denial_id = f"den-{uuid.uuid4().hex[:10]}"
                    c.execute(
                        """INSERT INTO denials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (denial_id, claim_id, inject["carc_code"], None, "Coding / DX",
                         date.today(), date.today() + timedelta(days=45),
                         None, None, None, None, False),
                    )
                    details["denial_id"] = denial_id
                    affected.append(claim_id)

    await emit(
        "scenario.injected",
        agent_name="scenario_runner",
        entity_type="scenario", entity_id=scenario_id,
        data={"scenario_id": scenario_id, "affected_count": len(affected), "details": details},
    )

    return {
        "scenario_id": scenario_id,
        "name": scenario["name"],
        "affected_count": len(affected),
        "affected_sample": affected[:10],
        "details": details,
        "expected_outcome": scenario["expected_outcome"],
    }
