"""DuckDB DDL for the RCM demo.

All tables defined per PRD §3. Schemas are idempotent — CREATE TABLE IF NOT EXISTS.
"""

from __future__ import annotations

import duckdb

DDL_STATEMENTS: list[str] = [
    # Patients ------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS patients (
        patient_id VARCHAR PRIMARY KEY,
        first_name VARCHAR,
        last_name VARCHAR,
        dob DATE,
        gender VARCHAR,
        address_line1 VARCHAR,
        city VARCHAR,
        state VARCHAR,
        zip_code VARCHAR,
        phone VARCHAR,
        email VARCHAR,
        mrn VARCHAR,
        primary_payer_id VARCHAR,
        secondary_payer_id VARCHAR,
        propensity_score DOUBLE,
        language_pref VARCHAR,
        created_at TIMESTAMP
    );
    """,
    # Payers --------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS payers (
        payer_id VARCHAR PRIMARY KEY,
        payer_name VARCHAR,
        payer_type VARCHAR,
        payer_id_x12 VARCHAR,
        avg_days_to_pay INTEGER,
        denial_rate_baseline DOUBLE,
        timely_filing_days INTEGER,
        fee_schedule_multiplier DOUBLE,
        portal_mock_url VARCHAR
    );
    """,
    # Encounters ----------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS encounters (
        encounter_id VARCHAR PRIMARY KEY,
        patient_id VARCHAR,
        provider_npi VARCHAR,
        facility_npi VARCHAR,
        encounter_type VARCHAR,
        service_date DATE,
        discharge_date DATE,
        place_of_service VARCHAR,
        attending_physician VARCHAR,
        chief_complaint TEXT,
        soap_note_text TEXT,
        scenario_id VARCHAR,
        auth_required BOOLEAN,
        auth_status VARCHAR,
        charge_lag_days INTEGER,
        status VARCHAR
    );
    """,
    # Claims --------------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS claims (
        claim_id VARCHAR PRIMARY KEY,
        encounter_id VARCHAR,
        claim_type VARCHAR,
        payer_id VARCHAR,
        total_billed DECIMAL(10,2),
        total_allowed DECIMAL(10,2),
        total_paid DECIMAL(10,2),
        patient_responsibility DECIMAL(10,2),
        submission_date DATE,
        adjudication_date DATE,
        claim_status VARCHAR,
        rejection_reason VARCHAR,
        timely_filing_deadline DATE,
        scrub_score DOUBLE,
        appeal_id VARCHAR,
        era_posted BOOLEAN
    );
    """,
    # Claim lines ---------------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS claim_lines (
        line_id VARCHAR PRIMARY KEY,
        claim_id VARCHAR,
        cpt_code VARCHAR,
        icd10_primary VARCHAR,
        icd10_secondary VARCHAR,
        modifier VARCHAR,
        units INTEGER,
        charge_amount DECIMAL(10,2),
        allowed_amount DECIMAL(10,2),
        revenue_code VARCHAR,
        ndc_code VARCHAR,
        coding_confidence DOUBLE
    );
    """,
    # Supporting tables ---------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS eligibility_responses (
        eligibility_id VARCHAR PRIMARY KEY,
        patient_id VARCHAR,
        payer_id VARCHAR,
        verified_at TIMESTAMP,
        copay DECIMAL(10,2),
        deductible_remaining DECIMAL(10,2),
        oop_remaining DECIMAL(10,2),
        in_network BOOLEAN,
        plan_type VARCHAR,
        response_json TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS prior_auths (
        auth_id VARCHAR PRIMARY KEY,
        encounter_id VARCHAR,
        cpt_code VARCHAR,
        auth_number VARCHAR,
        status VARCHAR,
        submitted_at TIMESTAMP,
        decision_at TIMESTAMP,
        expiration_date DATE,
        denial_reason VARCHAR,
        peer_to_peer_requested BOOLEAN
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS denials (
        denial_id VARCHAR PRIMARY KEY,
        claim_id VARCHAR,
        carc_code VARCHAR,
        rarc_code VARCHAR,
        denial_category VARCHAR,
        denial_date DATE,
        appeal_deadline DATE,
        agent_root_cause TEXT,
        appeal_letter_text TEXT,
        appeal_submitted_at TIMESTAMP,
        overturn_date DATE,
        overturn_flag BOOLEAN
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS payments (
        payment_id VARCHAR PRIMARY KEY,
        claim_id VARCHAR,
        payment_date DATE,
        payment_amount DECIMAL(10,2),
        payment_type VARCHAR,
        era_id VARCHAR,
        check_number VARCHAR,
        posting_status VARCHAR,
        exception_flag BOOLEAN
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS ar_aging_snapshot (
        snapshot_date DATE,
        payer_id VARCHAR,
        bucket_0_30 DECIMAL(12,2),
        bucket_31_60 DECIMAL(12,2),
        bucket_61_90 DECIMAL(12,2),
        bucket_91_120 DECIMAL(12,2),
        bucket_over_120 DECIMAL(12,2),
        total_ar DECIMAL(12,2),
        days_in_ar DOUBLE,
        PRIMARY KEY (snapshot_date, payer_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_event_log (
        event_id VARCHAR PRIMARY KEY,
        task_id VARCHAR,
        agent_name VARCHAR,
        action_type VARCHAR,
        entity_type VARCHAR,
        entity_id VARCHAR,
        input_summary TEXT,
        output_summary TEXT,
        reasoning_trace TEXT,
        confidence DOUBLE,
        hitl_required BOOLEAN,
        human_decision VARCHAR,
        created_at TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS hitl_tasks (
        task_id VARCHAR PRIMARY KEY,
        agent_name VARCHAR,
        entity_type VARCHAR,
        entity_id VARCHAR,
        task_description TEXT,
        priority VARCHAR,
        recommended_action TEXT,
        agent_reasoning TEXT,
        status VARCHAR,
        created_at TIMESTAMP,
        resolved_at TIMESTAMP,
        decision VARCHAR,
        notes TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS kpi_alerts (
        alert_id VARCHAR PRIMARY KEY,
        alert_type VARCHAR,
        severity VARCHAR,
        description TEXT,
        affected_entities TEXT,
        created_at TIMESTAMP,
        resolved_at TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_tasks (
        task_id VARCHAR PRIMARY KEY,
        agent_name VARCHAR,
        status VARCHAR,
        input_json TEXT,
        output_json TEXT,
        confidence DOUBLE,
        created_at TIMESTAMP,
        completed_at TIMESTAMP,
        error_message TEXT
    );
    """,
    # Indexes -------------------------------------------------------------
    "CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(claim_status);",
    "CREATE INDEX IF NOT EXISTS idx_claims_payer ON claims(payer_id);",
    "CREATE INDEX IF NOT EXISTS idx_claims_encounter ON claims(encounter_id);",
    "CREATE INDEX IF NOT EXISTS idx_claim_lines_claim ON claim_lines(claim_id);",
    "CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id);",
    "CREATE INDEX IF NOT EXISTS idx_denials_claim ON denials(claim_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_entity ON agent_event_log(entity_type, entity_id);",
    "CREATE INDEX IF NOT EXISTS idx_events_task ON agent_event_log(task_id);",
    "CREATE INDEX IF NOT EXISTS idx_hitl_status ON hitl_tasks(status);",
]


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables and indexes if they do not already exist."""
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)


def reset_all_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Truncate all tables (for the /scenarios/reset endpoint)."""
    tables = [
        "agent_event_log",
        "hitl_tasks",
        "kpi_alerts",
        "agent_tasks",
        "ar_aging_snapshot",
        "payments",
        "denials",
        "prior_auths",
        "eligibility_responses",
        "claim_lines",
        "claims",
        "encounters",
        "patients",
        "payers",
    ]
    for table in tables:
        conn.execute(f"DELETE FROM {table};")
