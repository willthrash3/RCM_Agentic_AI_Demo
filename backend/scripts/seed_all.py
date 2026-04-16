"""Deterministic seed script for the RCM demo.

Populates DuckDB with:
- 7 payers (from fixture)
- 500 patients
- 3,000 encounters across the 500 patients over the last 90 days
- 3,000 claims + line items
- Supporting rows: eligibility_responses, prior_auths, denials, payments, ar_aging

Seed is deterministic (random.seed + Faker.seed_instance). Target runtime: <60 s.
"""

from __future__ import annotations

import json
import random
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Allow running from the backend/ directory directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from faker import Faker

from app.config import get_settings
from app.data.fixtures_loader import carc_rarc, cpt_codes, icd10_codes, payers, soap_templates
from app.database import get_connection
from app.db_schema import init_schema, reset_all_tables

SETTINGS = get_settings()
SEED = SETTINGS.seed_random_seed
random.seed(SEED)
FAKE = Faker("en_US")
FAKE.seed_instance(SEED)

TODAY = date(2026, 4, 15)  # Fixed "today" so the demo story is consistent
NUM_PATIENTS = 500
NUM_ENCOUNTERS = 3000

SOUTHEAST_CITIES = [
    ("Birmingham", "AL", "35203"),
    ("Huntsville", "AL", "35801"),
    ("Montgomery", "AL", "36104"),
    ("Nashville", "TN", "37203"),
    ("Memphis", "TN", "38103"),
    ("Knoxville", "TN", "37902"),
    ("Chattanooga", "TN", "37402"),
    ("Atlanta", "GA", "30303"),
    ("Savannah", "GA", "31401"),
    ("Augusta", "GA", "30901"),
]

CLAIM_STATUS_MIX = [
    ("Paid", 0.55),
    ("Submitted", 0.20),
    ("Denied", 0.18),
    ("Appealed", 0.05),
    ("Draft", 0.02),
]
ENCOUNTER_TYPE_MIX = [
    ("Outpatient", 0.60),
    ("Inpatient", 0.20),
    ("ED", 0.15),
    ("Observation", 0.05),
]


def _weighted(choices: list[tuple]) -> str:
    names, weights = zip(*choices)
    return random.choices(names, weights=weights, k=1)[0]


def _decimal(value: float) -> Decimal:
    return Decimal(f"{value:.2f}")


def seed_payers(conn) -> list[dict]:
    conn.execute("DELETE FROM payers;")
    rows = payers()
    for p in rows:
        conn.execute(
            """INSERT INTO payers VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                p["payer_id"], p["payer_name"], p["payer_type"], p["payer_id_x12"],
                p["avg_days_to_pay"], p["denial_rate_baseline"], p["timely_filing_days"],
                p["fee_schedule_multiplier"], p["portal_mock_url"],
            ),
        )
    print(f"  payers: {len(rows)}")
    return rows


def seed_patients(conn, payer_rows: list[dict]) -> list[dict]:
    conn.execute("DELETE FROM patients;")
    payer_ids = [p["payer_id"] for p in payer_rows]
    payer_weights = [p.get("mix_weight", 0.1) for p in payer_rows]
    patients_out = []
    for i in range(NUM_PATIENTS):
        pid = f"pt-{i + 1:05d}"
        gender = random.choices(["F", "M", "U"], weights=[48, 48, 4])[0]
        if gender == "F":
            first = FAKE.first_name_female()
        elif gender == "M":
            first = FAKE.first_name_male()
        else:
            first = FAKE.first_name()
        last = FAKE.last_name()
        city, state, zipc = random.choice(SOUTHEAST_CITIES)
        # DOB uniform 1940–2010
        dob_year = random.randint(1940, 2010)
        dob = date(dob_year, random.randint(1, 12), random.randint(1, 28))
        primary = random.choices(payer_ids, weights=payer_weights)[0]
        secondary = random.choice(payer_ids) if random.random() < 0.22 else None
        if secondary == primary:
            secondary = None
        propensity = round(random.betavariate(2, 2), 2)
        lang = random.choices(["EN", "ES", "Other"], weights=[78, 18, 4])[0]
        email = f"{first.lower()}.{last.lower()}@example.com"
        created_at = datetime.combine(
            TODAY - timedelta(days=random.randint(0, 365)),
            datetime.min.time(),
        )
        row = {
            "patient_id": pid, "first_name": first, "last_name": last, "dob": dob,
            "gender": gender, "city": city, "state": state, "zip_code": zipc,
            "address_line1": FAKE.street_address(), "phone": FAKE.numerify("###-555-####"),
            "email": email, "mrn": f"MRN-{10000 + i}", "primary_payer_id": primary,
            "secondary_payer_id": secondary, "propensity_score": propensity,
            "language_pref": lang, "created_at": created_at,
        }
        conn.execute(
            """INSERT INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (pid, first, last, dob, gender, row["address_line1"], city, state, zipc,
             row["phone"], email, row["mrn"], primary, secondary, propensity, lang, created_at),
        )
        patients_out.append(row)
    print(f"  patients: {len(patients_out)}")
    return patients_out


def seed_encounters(conn, patients_list: list[dict]) -> list[dict]:
    conn.execute("DELETE FROM encounters;")
    templates = soap_templates()
    encounters_out = []
    for i in range(NUM_ENCOUNTERS):
        eid = f"enc-{i + 1:05d}"
        patient = random.choice(patients_list)
        etype = _weighted(ENCOUNTER_TYPE_MIX)
        svc_date = TODAY - timedelta(days=random.randint(0, 90))
        if etype == "Inpatient":
            discharge = svc_date + timedelta(days=random.randint(1, 5))
        else:
            discharge = svc_date
        template = random.choice(templates)
        age = TODAY.year - patient["dob"].year
        soap_text = template["soap_note_text"].format(
            patient_name=f"{patient['first_name']} {patient['last_name']}",
            age=age,
            gender={"F": "female", "M": "male", "U": "patient"}[patient["gender"]],
        )
        physician = "Dr. " + FAKE.last_name()
        pos = {"Outpatient": "11", "Inpatient": "21", "ED": "23", "Observation": "22"}[etype]
        auth_required = random.random() < 0.35
        auth_status = (
            random.choices(["Approved", "Pending", "Denied"], weights=[80, 15, 5])[0]
            if auth_required
            else "Not Required"
        )
        charge_lag = max(0, int(random.gauss(2.1, 1.2)))
        status = random.choices(
            ["Scheduled", "Checked-in", "Coded", "Billed", "Paid", "Denied"],
            weights=[3, 4, 8, 20, 55, 10],
        )[0]
        conn.execute(
            """INSERT INTO encounters VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (eid, patient["patient_id"], FAKE.numerify("##########"),
             FAKE.numerify("##########"), etype, svc_date, discharge, pos,
             physician, template["clinical_label"], soap_text, template["scenario_id"],
             auth_required, auth_status, charge_lag, status),
        )
        encounters_out.append({
            "encounter_id": eid, "patient_id": patient["patient_id"],
            "service_date": svc_date, "encounter_type": etype,
            "scenario_id": template["scenario_id"], "template": template,
            "status": status,
        })
    print(f"  encounters: {len(encounters_out)}")
    return encounters_out


def seed_claims_and_lines(conn, encounters_list: list[dict], patients_list: list[dict]) -> list[dict]:
    conn.execute("DELETE FROM claims;")
    conn.execute("DELETE FROM claim_lines;")
    payers_by_id = {p["payer_id"]: p for p in payers()}
    patients_by_id = {p["patient_id"]: p for p in patients_list}
    cpt_by_code = {c["code"]: c for c in cpt_codes()}
    carc_list = [r["code"] for r in carc_rarc()["carc"]]
    claims_out = []
    for i, enc in enumerate(encounters_list):
        claim_id = f"clm-{i + 1:05d}"
        patient = patients_by_id[enc["patient_id"]]
        payer_id = patient["primary_payer_id"]
        if payer_id == "payer-007":  # Self-Pay patients rarely have claims
            if random.random() < 0.7:
                continue
        payer = payers_by_id[payer_id]
        template = enc["template"]
        primary_cpt = template["expected_cpt"]
        primary_icd = template["expected_primary_icd10"]
        secondary_icd = (template["additional_icd10"] or [None])[0]
        cpt_meta = cpt_by_code.get(primary_cpt, {"base_charge": 200.0})
        base_charge = cpt_meta["base_charge"]
        units = 1
        charge = _decimal(base_charge * units)
        allowed = _decimal(float(charge) * payer["fee_schedule_multiplier"] * 0.75)
        claim_type = "837I" if enc["encounter_type"] in ("Inpatient", "ED") else "837P"
        status = _weighted(CLAIM_STATUS_MIX)
        submission_date: date | None = None
        adjudication_date: date | None = None
        paid: Decimal = Decimal("0.00")
        pt_resp: Decimal = Decimal("0.00")
        rejection: str | None = None
        if status in ("Submitted", "Paid", "Denied", "Appealed"):
            submission_date = enc["service_date"] + timedelta(days=random.randint(1, 5))
            if status in ("Paid", "Denied", "Appealed"):
                adjudication_date = submission_date + timedelta(days=payer["avg_days_to_pay"])
        if status == "Paid":
            paid = _decimal(float(allowed) * 0.82)
            pt_resp = _decimal(float(allowed) - float(paid))
        if status in ("Denied", "Appealed"):
            rejection = random.choice(carc_list)
        tf_deadline = enc["service_date"] + timedelta(days=payer["timely_filing_days"])
        scrub_score = round(random.uniform(0.82, 0.99), 2) if status != "Draft" else None
        era_posted = status == "Paid"
        conn.execute(
            """INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (claim_id, enc["encounter_id"], claim_type, payer_id, charge, allowed,
             paid, pt_resp, submission_date, adjudication_date, status, rejection,
             tf_deadline, scrub_score, None, era_posted),
        )
        conn.execute(
            """INSERT INTO claim_lines VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (f"line-{claim_id}-1", claim_id, primary_cpt, primary_icd, secondary_icd,
             None, units, charge, allowed, None, None, None),
        )
        claims_out.append({
            "claim_id": claim_id, "encounter_id": enc["encounter_id"],
            "payer_id": payer_id, "status": status, "rejection": rejection,
            "charge": charge, "allowed": allowed, "paid": paid,
            "submission_date": submission_date, "adjudication_date": adjudication_date,
            "primary_cpt": primary_cpt,
        })
    print(f"  claims: {len(claims_out)} / claim_lines: {len(claims_out)}")
    return claims_out


def seed_denials(conn, claims_list: list[dict]) -> int:
    conn.execute("DELETE FROM denials;")
    carc_map = {c["code"]: c for c in carc_rarc()["carc"]}
    rarc_list = [r["code"] for r in carc_rarc()["rarc"]]
    payers_by_id = {p["payer_id"]: p for p in payers()}
    count = 0
    for cl in claims_list:
        if cl["status"] not in ("Denied", "Appealed"):
            continue
        carc = cl["rejection"] or "CO-16"
        meta = carc_map.get(carc, {"category": "Other"})
        denial_id = f"den-{count + 1:05d}"
        denial_date = cl["adjudication_date"] or TODAY
        payer = payers_by_id[cl["payer_id"]]
        appeal_deadline = denial_date + timedelta(days=min(60, payer["timely_filing_days"] // 2))
        overturn_flag = cl["status"] == "Appealed" and random.random() < 0.55
        overturn_date = denial_date + timedelta(days=random.randint(14, 45)) if overturn_flag else None
        rarc = random.choice(rarc_list) if random.random() < 0.6 else None
        conn.execute(
            """INSERT INTO denials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (denial_id, cl["claim_id"], carc, rarc, meta["category"], denial_date,
             appeal_deadline, None, None, None, overturn_date, overturn_flag),
        )
        count += 1
    print(f"  denials: {count}")
    return count


def seed_eligibility(conn, patients_list: list[dict]) -> int:
    conn.execute("DELETE FROM eligibility_responses;")
    count = 0
    for pt in patients_list:
        if random.random() < 0.4:
            continue
        eid = f"el-{count + 1:05d}"
        verified = datetime.combine(TODAY - timedelta(days=random.randint(0, 45)), datetime.min.time())
        copay = _decimal(random.choice([0, 10, 20, 25, 30, 40, 50]))
        ded = _decimal(random.choice([0, 250, 500, 1000, 1500, 2500, 3500]))
        oop = _decimal(random.choice([500, 1500, 3000, 5000, 7500]))
        in_network = random.random() > 0.08
        plan_type = random.choice(["HMO", "PPO", "EPO", "POS", "Medicare"])
        response_json = json.dumps({"active": in_network, "plan_type": plan_type, "copay": float(copay)})
        conn.execute(
            """INSERT INTO eligibility_responses VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (eid, pt["patient_id"], pt["primary_payer_id"], verified, copay, ded, oop,
             in_network, plan_type, response_json),
        )
        count += 1
    print(f"  eligibility_responses: {count}")
    return count


def seed_payments(conn, claims_list: list[dict]) -> int:
    conn.execute("DELETE FROM payments;")
    count = 0
    for cl in claims_list:
        if cl["status"] != "Paid":
            continue
        pid = f"pay-{count + 1:05d}"
        pay_date = cl["adjudication_date"] or TODAY
        pay_type = random.choices(["EFT", "Check"], weights=[85, 15])[0]
        era_id = f"era-{(count // 40) + 1:04d}"
        check_no = FAKE.numerify("#######") if pay_type == "Check" else None
        conn.execute(
            """INSERT INTO payments VALUES (?,?,?,?,?,?,?,?,?)""",
            (pid, cl["claim_id"], pay_date, cl["paid"], pay_type, era_id,
             check_no, "Posted", False),
        )
        count += 1
    print(f"  payments: {count}")
    return count


def seed_ar_aging(conn) -> int:
    conn.execute("DELETE FROM ar_aging_snapshot;")
    payer_rows = payers()
    count = 0
    for days_back in range(30, -1, -1):
        snap_date = TODAY - timedelta(days=days_back)
        for p in payer_rows:
            b_0_30 = _decimal(random.uniform(30000, 110000) * p["mix_weight"] * 3)
            b_31_60 = _decimal(random.uniform(20000, 70000) * p["mix_weight"] * 3)
            b_61_90 = _decimal(random.uniform(10000, 40000) * p["mix_weight"] * 3)
            b_91_120 = _decimal(random.uniform(5000, 20000) * p["mix_weight"] * 3)
            b_over = _decimal(random.uniform(3000, 15000) * p["mix_weight"] * 3)
            total = b_0_30 + b_31_60 + b_61_90 + b_91_120 + b_over
            days_in_ar = round(random.uniform(32, 58), 1)
            conn.execute(
                """INSERT INTO ar_aging_snapshot VALUES (?,?,?,?,?,?,?,?,?)""",
                (snap_date, p["payer_id"], b_0_30, b_31_60, b_61_90, b_91_120,
                 b_over, total, days_in_ar),
            )
            count += 1
    print(f"  ar_aging_snapshot: {count}")
    return count


def seed_prior_auths(conn) -> int:
    conn.execute("DELETE FROM prior_auths;")
    count = 0
    res = conn.execute(
        "SELECT encounter_id FROM encounters WHERE auth_required = TRUE"
    ).fetchall()
    for (enc_id,) in res:
        aid = f"auth-{count + 1:05d}"
        status = random.choices(["Approved", "Pending", "Denied"], weights=[80, 15, 5])[0]
        submitted = datetime.combine(TODAY - timedelta(days=random.randint(10, 40)), datetime.min.time())
        decision = submitted + timedelta(days=random.randint(1, 7)) if status != "Pending" else None
        expiration = (decision.date() + timedelta(days=90)) if decision else None
        denial_reason = "Medical necessity not established" if status == "Denied" else None
        conn.execute(
            """INSERT INTO prior_auths VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (aid, enc_id, "99223", FAKE.bothify("AUTH#######"), status, submitted,
             decision, expiration, denial_reason, False),
        )
        count += 1
    print(f"  prior_auths: {count}")
    return count


def main() -> None:
    print("== Seeding RCM demo database ==")
    conn = get_connection()
    init_schema(conn)
    reset_all_tables(conn)

    payer_rows = seed_payers(conn)
    patients_list = seed_patients(conn, payer_rows)
    encounters_list = seed_encounters(conn, patients_list)
    claims_list = seed_claims_and_lines(conn, encounters_list, patients_list)
    seed_denials(conn, claims_list)
    seed_eligibility(conn, patients_list)
    seed_payments(conn, claims_list)
    seed_ar_aging(conn)
    seed_prior_auths(conn)

    print(f"Seed complete. DB at {SETTINGS.db_path}")


if __name__ == "__main__":
    main()
