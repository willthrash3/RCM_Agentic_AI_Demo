# Data Dictionary

Quick reference for the DuckDB schema. See `backend/app/db_schema.py` for source of truth.

## Core tables

### patients (target: 500 rows)
| Column | Type | Notes |
|---|---|---|
| patient_id | VARCHAR PK | `pt-00001` style prefixed id |
| first_name / last_name | VARCHAR | Faker-generated |
| dob | DATE | uniform 1940–2010 |
| gender | VARCHAR | M/F/U weighted 48/48/4 |
| address_line1, city, state, zip_code | VARCHAR | Southeast US cities |
| mrn | VARCHAR | `MRN-10000+i` |
| primary_payer_id / secondary_payer_id | VARCHAR FK | → payers |
| propensity_score | DOUBLE | 0-1, beta distribution |
| language_pref | VARCHAR | EN/ES/Other weighted 78/18/4 |

### payers (7 rows, fixture-seeded)
Medicare, TennCare Medicaid, BlueStar Commercial, Apex PPO, HealthFirst HMO, SunBridge EPO, Self-Pay.

### encounters (target: 3,000)
| Column | Notes |
|---|---|
| encounter_type | Outpatient 60% / Inpatient 20% / ED 15% / Observation 5% |
| service_date | Within last 90 days |
| scenario_id | References a SOAP note template |
| auth_required | 35% true |

### claims (≈ 2,400 — self-pay patients mostly don't claim)
| Column | Notes |
|---|---|
| claim_status | Paid 55% / Submitted 20% / Denied 18% / Appealed 5% / Draft 2% |
| scrub_score | 0.82-0.99 |
| rejection_reason | CARC code when denied |
| timely_filing_deadline | service_date + payer.timely_filing_days |

### claim_lines
One row per CPT line with ICD-10 linkage. `coding_confidence` is set by the coding agent.

### denials
One row per denied claim. Links to CARC code and carries appeal letter text & submission state.

### eligibility_responses
Mock 271 responses per (patient, payer, verification date).

### prior_auths
One row per auth request with status (Approved 80% / Pending 15% / Denied 5%).

### payments
One row per payment event (EFT 85% / Check 15%).

### ar_aging_snapshot
Daily snapshot per payer across aging buckets.

## Agent operational tables

### agent_event_log
Immutable log of every agent event streamed to SSE. Powers the Agent Trace Viewer.

### agent_tasks
Request-per-agent-run lifecycle (queued → running → complete/escalated/failed).

### hitl_tasks
Queue of human-in-the-loop tasks. Priority Critical > High > Medium > Low.

### kpi_alerts
Raised when a metric crosses its Alert threshold.

## Fixtures

| File | Purpose |
|---|---|
| `cpt_codes.json` | Billing code master with base charges |
| `icd10_codes.json` | Diagnosis code master |
| `carc_rarc.json` | Denial reason codes (PRD §9.3 list) |
| `payers.json` | 7 payers with financial attributes |
| `soap_note_templates.json` | 15 clinical scenarios with expected CPT/ICD-10 |
| `payer_edit_rules.json` | Payer-specific LCD + auth rules |
| `appeal_templates.json` | Jinja2 appeal letter templates by category |
| `scenarios.json` | 6 demo edge-case injectors |
