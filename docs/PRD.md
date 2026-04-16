



1.1  Purpose & Vision
This document defines the complete product requirements for an interactive demo system that showcases the application of agentic AI across the ten stages of healthcare Revenue Cycle Management (RCM). The system will be built with synthetic patient and claim data, real LLM-powered agents, and a purpose-built dashboard that allows a live audience to observe agents reasoning, acting, and handing off work to human reviewers in real time.

The demo is designed to serve two audiences simultaneously:
Prospect buyers — healthcare CFOs, Revenue Cycle Directors, and HIT leaders who need to see measurable ROI and understand how agents fit their existing workflows.
Technical evaluators — solution architects and IT leads who need to see clean API contracts, agent orchestration patterns, and security posture.

1.2  Strategic Objectives
Demonstrate that agentic AI can reduce Days-in-AR by a simulated 15–25% through faster claim resolution and proactive denial management.
Demonstrate how agents identify and correct the specific error classes that drive first-pass rejections — missing modifiers, LCD mismatches, unbundling conflicts, and auth gaps — each shown live in the reasoning trace viewer. Customer uplift will depend on baseline error distribution.
Illustrate the human-in-the-loop (HITL) pattern: agents act autonomously on high-confidence tasks and escalate to queues for exceptions.
Provide a fully runnable codebase that Claude Code can generate end-to-end from this PRD.

1.3  Scope




2.1  High-Level Architecture
The system consists of four primary layers:


2.2  Repository Structure
The monorepo will be organized as follows:


2.3  Data Flow Overview
The primary data flow follows the RCM pipeline. Agents are triggered either by scheduled jobs (e.g., nightly eligibility re-verification), by upstream events (e.g., a new encounter triggers the coding agent), or by user action (e.g., a billing coordinator clicking "Run Denial Agent" on a batch).

All agent actions are written to an immutable event log table in DuckDB. The UI subscribes to a Server-Sent Events (SSE) endpoint that streams agent status updates, reasoning traces, and task completions in real time.



3.1  Data Generation Approach
All patient, encounter, claim, and payer data must be entirely synthetic — generated via Python scripts using Faker and custom domain logic. The seed scripts must be deterministic (fixed random seed) so that the demo presents a consistent "story" across runs while remaining realistic enough to demonstrate meaningful agent behavior.

3.2  Patient Roster — patients table
Target volume: 500 patients.

3.3  Payer Table — payers
Seed 7 payers: Medicare (payer-001), TennCare Medicaid (payer-002), BlueStar Commercial (payer-003), Apex PPO (payer-004), HealthFirst HMO (payer-005), SunBridge EPO (payer-006), Self-Pay (payer-007). Payer mix: Medicare 28%, Medicaid 18%, 3 commercial plans 44%, self-pay 10%.

3.4  Encounter Table — encounters
Target volume: 3,000 encounters across the 500 patients, spanning a 90-day window. Distribution: 60% outpatient, 20% inpatient, 15% ED, 5% observation.

3.5  Claims Table — claims
Seed claims with the following distribution: 55% Paid, 20% Submitted/Pending, 18% Denied, 5% Appealed, 2% Draft. Denied claims must have a valid CARC code drawn from the CARC fixture list.

3.6  Claim Line Items — claim_lines

3.7  Supporting Tables
The following additional tables must be seeded:
eligibility_responses — stores mock 271 responses per patient per payer per verification date. Fields: eligibility_id, patient_id, payer_id, verified_at, copay, deductible_remaining, oop_remaining, in_network, plan_type, response_json.
prior_auths — one row per auth request. Fields: auth_id, encounter_id, cpt_code, auth_number, status, submitted_at, decision_at, expiration_date, denial_reason, peer_to_peer_requested.
denials — one row per denied claim. Fields: denial_id, claim_id, carc_code, rarc_code, denial_category (Eligibility / Auth / Coding / Timely Filing / Medical Necessity / Duplicate / Other), denial_date, appeal_deadline, agent_root_cause, appeal_letter_text, appeal_submitted_at, overturn_date, overturn_flag.
payments — one row per payment event. Fields: payment_id, claim_id, payment_date, payment_amount, payment_type (EFT / Check / Patient), era_id, check_number, posting_status, exception_flag.
ar_aging_snapshot — daily snapshot. Fields: snapshot_date, payer_id, bucket_0_30, bucket_31_60, bucket_61_90, bucket_91_120, bucket_over_120, total_ar, days_in_ar.
agent_event_log — immutable. Fields: event_id UUID, agent_name, action_type, entity_type, entity_id, input_summary, output_summary, reasoning_trace TEXT, confidence FLOAT, hitl_required BOOLEAN, human_decision VARCHAR, created_at TIMESTAMP.

3.8  Synthetic SOAP Notes
The coding agent requires synthetic clinical text to demonstrate NLP-based code suggestion. Generate 15 note templates with the following characteristics:
Each template covers a distinct clinical scenario: HTN management, Type 2 diabetes follow-up, COPD exacerbation, chest pain rule-out ACS, knee osteoarthritis injection, upper respiratory infection, back pain, anxiety/depression follow-up, hyperlipidemia, post-op wound check, skin lesion excision, urinary tract infection, new patient comprehensive exam, annual wellness visit, ED chest pain workup.
Each template must contain enough clinical detail that the coding agent can correctly suggest 2–4 ICD-10 codes and 1–2 CPT codes with high confidence.
Templates are stored as fixture JSON: soap_note_templates.json, keyed by scenario_id.
Encounters are assigned a scenario_id; the soap_note_text field is the template text with patient name/date substituted in.



Each agent is a LangGraph node that receives a structured input, has access to a defined set of tools, reasons through its task using Claude claude-sonnet-4-20250514, writes its output to the database, and emits events to the SSE stream. All agents share a common interface contract:


4.1  Eligibility Agent
Purpose
Verifies patient insurance eligibility in real time by querying the mock payer portal API. Runs nightly as a batch for all patients with appointments in the next 7 days and on-demand for any patient at registration.
Tools Available
query_payer_eligibility(patient_id, payer_id, service_date) → EligibilityResponse271 — calls the mock 270/271 endpoint
get_patient_demographics(patient_id) → PatientRecord
get_patient_insurance(patient_id) → List[InsuranceRecord]
write_eligibility_result(patient_id, payer_id, result) → None
flag_missing_info(patient_id, fields: List[str]) → None
Decision Logic
For each patient: (1) fetch demographics and insurance records; (2) call eligibility endpoint for primary and secondary payers; (3) if deductible remaining < $200 or OOP met, flag for financial counseling; (4) if out-of-network or plan inactive, escalate to HITL queue with reason; (5) if eligibility verified clean, mark as verified and store response.
HITL Escalation Triggers
Plan is out-of-network for the scheduled service
Coverage has lapsed or policy is inactive
COB order cannot be determined from 271 response
Eligibility check fails 3 times (payer portal error)
Output Events
eligibility.verified — clean verification
eligibility.escalated — sent to human queue
eligibility.financial_counseling_flag — patient has high balance exposure

4.2  Coding Agent
Purpose
Reads the clinical encounter note (SOAP/H&P/op report) and suggests CPT, ICD-10-CM, and modifier codes with confidence scores. Operates in "assisted" mode by default — a human coder reviews and approves before the claim is dropped.
Tools Available
get_encounter_note(encounter_id) → EncounterNote including soap_note_text
get_patient_history(patient_id) → List[PriorEncounterSummary]
search_cpt_codes(description) → List[CPTCode] — fixture-based lookup
search_icd10_codes(description) → List[ICD10Code] — fixture-based lookup
validate_code_combination(cpt_codes, icd10_codes, modifiers) → ValidationResult — bundling/editing rules
write_coding_suggestion(encounter_id, codes, confidence, reasoning) → None
System Prompt (abbreviated)
Output Requirements
The agent must return a structured CodeSuggestion object containing: primary_cpt (with confidence), additional_cpts (list), primary_icd10, secondary_icd10s (list), modifiers, documentation_gaps (list of free-text warnings), overall_confidence, and full reasoning_trace.
Auto-Approval Rule
If overall_confidence >= 0.95 AND documentation_gaps is empty AND the code combination passes validation, the agent may auto-approve and drop the charge. Otherwise, route to coder review queue.

4.3  Claim Scrubbing Agent
Purpose
Applies a rule engine and ML-based rejection prediction to each claim before it is submitted to the clearinghouse. Identifies edits, estimates rejection probability per payer, and either releases the claim or holds it for correction.
Tools Available
get_claim_with_lines(claim_id) → ClaimWithLines
get_payer_edit_rules(payer_id) → List[EditRule] — from fixture JSON per payer
check_lcd_ncd(cpt_code, icd10_code) → CoverageDecision — mock CMS LCD/NCD lookup
check_bundling_rules(cpt_codes) → List[BundlingConflict] — NCCI edits
get_prior_auth_status(encounter_id, cpt_code) → AuthStatus
predict_rejection_probability(claim_features) → float — simple logistic model trained on seeded history
write_scrub_result(claim_id, score, edits, release_flag) → None
Edit Categories
The agent must check for: missing or invalid modifier, diagnosis not supporting medical necessity (LCD mismatch), unbundling violation, auth required but not obtained, timely filing approaching (<14 days), demographic mismatch (patient vs insured), duplicate claim (same service date + CPT + patient), and place-of-service mismatch.
Release Criteria
Release claim for submission if: scrub_score >= 0.90 AND no critical edits (auth missing, LCD fail) are present. Hold if critical edits exist. Flag for review if score is 0.75–0.89.

4.4  Claim Tracking Agent
Purpose
Monitors all submitted claims for payer status updates. Runs daily as a scheduled job. Surfaces claims that are approaching timely filing limits, stuck in "pending" state, or adjudicated with unexpected underpayments.
Tools Available
get_submitted_claims(days_submitted_min=1) → List[ClaimSummary]
query_payer_claim_status(claim_id, payer_id) → ClaimStatusResponse277 — mock 277 endpoint
get_contract_allowable(cpt_code, payer_id) → Decimal — fee schedule lookup
flag_underpayment(claim_id, expected, actual, variance_pct) → None
flag_timely_filing_risk(claim_id, days_remaining) → None
update_claim_status(claim_id, new_status) → None
Underpayment Detection
If (actual_paid / contract_allowable) < 0.95 and variance > $25, flag as potential underpayment and add to the underpayment review queue with the computed variance amount.

4.5  ERA Posting Agent
Purpose
Processes incoming Electronic Remittance Advice (835 files). Matches payments to claims, posts contractual adjustments, creates patient balance records, and routes unmatched or exception payments to a human review queue.
Tools Available
get_unposted_eras() → List[ERAFile] — reads from fixture ERA JSON files
get_claim_by_service_info(patient_id, service_date, cpt_code) → Claim — for matching
post_payment(claim_id, payment_amount, adjustment_codes, patient_balance) → None
create_patient_statement(patient_id, claim_id, balance_amount) → None
route_exception(era_id, line_id, reason) → None
Matching Logic & Exception Handling
Primary match: claim_id present in ERA. Secondary match: patient + service date + CPT. If no match found after both attempts, route to exception queue. If CARC code is present (denial), route to denial agent workflow. Write-offs require HITL approval for amounts > $50.

4.6  Denial Management Agent
Purpose
The highest-value agent in the demo. Receives a denied claim, classifies the root cause, determines whether an appeal is warranted, generates a fully drafted appeal letter, and submits it to the payer (via mock API) if confidence is high.
Tools Available
get_denial_detail(denial_id) → DenialRecord including CARC/RARC codes
get_claim_detail(claim_id) → ClaimWithLines
get_prior_auth_record(encounter_id) → PriorAuth or None
get_clinical_documentation(encounter_id) → EncounterNote
classify_denial_root_cause(carc_code, rarc_code, claim_context) → DenialClassification
calculate_appeal_deadline(denial_date, payer_id) → date
get_appeal_template(denial_category, payer_id) → str — fixture Jinja2 template
render_appeal_letter(template, claim_data, denial_data, clinical_summary) → str
submit_appeal(denial_id, appeal_letter_text) → AppealSubmissionResult — mock endpoint
Denial Categories & Suggested Actions
Auto-Submit Criteria
Agent may auto-submit appeal if: denial category is Coding or Eligibility AND corrected data is available AND appeal deadline is >7 days away AND rendered appeal letter passes a self-review check. All other appeals route to the human appeal queue.

4.7  Collections Agent
Purpose
Manages the patient balance after insurance adjudication. Segments patient accounts by propensity-to-pay score, selects the optimal outreach channel and message, generates personalized payment plan offers, and flags accounts for financial counseling.
Tools Available
get_patient_balances(min_balance=10) → List[PatientBalance]
get_patient_propensity(patient_id) → float
get_patient_contact_preferences(patient_id) → ContactPrefs
check_charity_care_eligibility(patient_id, balance) → CharityCareResult — income-based mock screening
generate_statement(patient_id, claim_id, balance, language) → str
generate_payment_plan(patient_id, balance, income_estimate) → PaymentPlanOffer
send_outreach(patient_id, channel, message_type, content) → OutreachRecord — mock send
Segmentation Rules

4.8  AR Analytics Agent
Purpose
The system-level monitoring agent. Runs daily and after any significant batch operation. Monitors KPIs, detects anomalies, generates narrative insights, and proactively alerts on deteriorating metrics before they become revenue leakage events.
Tools Available
get_ar_aging_snapshot(as_of_date) → ARAgingSnapshot
get_kpi_timeseries(metric_name, days_back) → List[KPIDataPoint]
get_denial_rate_by_payer(period_days) → List[PayerDenialStats]
get_first_pass_rate(period_days) → float
get_days_in_ar_by_payer() → List[PayerARStats]
compute_cash_forecast(days_horizon) → CashForecast
write_analytics_alert(alert_type, severity, description, affected_entities) → None
KPIs Monitored



5.1  LangGraph Workflow
Agents are wired together in a LangGraph StateGraph. The workflow supports both linear pipeline execution (encounter → code → scrub → submit) and event-driven branching (denial received → denial agent → appeal or write-off → analytics update).

State Schema

Graph Edges
START → eligibility_agent
eligibility_agent → coding_agent (if eligibility verified)
eligibility_agent → HITL_QUEUE (if escalated)
coding_agent → scrubbing_agent (if codes suggested)
scrubbing_agent → submission_node (if scrub_score >= 0.90)
scrubbing_agent → HITL_QUEUE (if critical edits or score < 0.90)
submission_node → tracking_agent
tracking_agent → era_posting_agent (on payment ERA received)
tracking_agent → denial_agent (on denial received)
denial_agent → analytics_agent (after appeal action)
era_posting_agent → collections_agent (on patient balance created)
[any agent] → analytics_agent (on KPI threshold breach event)

5.2  Human-in-the-Loop Queue
The HITL queue is a first-class feature of the demo. Any agent can push a HITLTask to the queue with: task_id, agent_name, entity_type, entity_id, task_description, priority (Critical / High / Medium / Low), recommended_action, and agent_reasoning. The UI surfaces this as a "Review Queue" panel where a human can approve, reject, or modify the agent recommendation. Human decisions are written back to the agent_event_log with a human_decision field.

5.3  Scenario Runner
The demo includes a scenario runner that injects pre-scripted events to demonstrate agent response to real-world edge cases. Scenarios are defined in scenarios.json and triggered via the UI or API:



6.1  Base Configuration
Base URL: http://localhost:8000/api/v1
Authentication: API key header (X-API-Key: demo-key-12345) for demo purposes only
Content-Type: application/json
Agent event streaming: GET /events/stream returns text/event-stream (SSE)

6.2  Core Endpoints

6.3  SSE Event Schema
All agent events emitted to the SSE stream follow this schema:



7.1  Page Inventory

7.2  Dashboard KPI Cards
The dashboard must display 8 KPI cards in a 4×2 grid. Each card shows: metric name, current value, target value, trend arrow (7-day direction), and a color-coded status chip (On Track / Watch / Alert). Cards must update in real time from the SSE stream.
Days in AR (Overall)  |  Target: <45  |  Color: green <45, amber 45–55, red >55
First Pass Rate  |  Target: >94%  |  Color: green >94%, amber 90–94%, red <90%
Denial Rate  |  Target: <8%  |  Color: green <8%, amber 8–12%, red >12%
Net Collection Rate  |  Target: >96%  |  Color: green >96%, amber 93–96%, red <93%
AR > 90 Days  |  Target: <15%  |  Color: as above
Avg Charge Lag (days)  |  Target: <2.5  |  Color: green <2.5, amber 2.5–4, red >4
Appeal Overturn Rate  |  Target: >55%  |  Color: green >55%, amber 40–55%, red <40%
Open HITL Tasks  |  Target: <10  |  Color: green <10, amber 10–25, red >25

7.3  Agent Trace Viewer
This is the hero feature of the demo. When an agent is running, the trace viewer shows a live stream of:
Agent thinking — the LLM reasoning steps between tool calls (displayed as typewriter-effect text)
Tool calls — each tool invocation shown as a collapsible card with input parameters and response
Decisions — when the agent reaches a conclusion (approve / escalate / draft appeal), shown as a highlighted result card
Confidence score — displayed as a progress bar that updates as the agent works
The trace viewer must connect to the /events/stream SSE endpoint and filter by the active task_id. It must handle reconnection gracefully if the stream drops.

7.4  Review Queue UX
The review queue is a split-panel view. Left: prioritized task list with color-coded priority badges, entity type chip, and time-since-created. Right: task detail panel showing the agent reasoning summary, the recommended action with rationale, the supporting data (claim detail, patient info, denial codes), and Approve / Reject / Modify action buttons. Approving or rejecting a task calls POST /hitl/{task_id}/resolve and updates the task status in real time.



8.1  Eligibility Agent Stories
US-E1: Nightly eligibility batch
As a registration manager, I want the eligibility agent to automatically verify insurance for all patients with appointments in the next 7 days, so that I can identify coverage issues before the day of service.
Acceptance Criteria:
Running POST /agents/eligibility/run with run_mode="batch" triggers verification for all qualifying patients.
Each verification result is stored in eligibility_responses.
Patients with lapsed or out-of-network coverage appear in the HITL queue within 60 seconds.
The dashboard "Open HITL Tasks" count increments accordingly.
Agent event log contains reasoning traces for each verification.

US-E2: Real-time eligibility check
As a front-desk coordinator, I want to trigger a live eligibility check for a walk-in patient and see the result within 10 seconds, so that I can collect the correct copay at check-in.
Acceptance Criteria:
GET /patients/:id shows current eligibility status and last verified timestamp.
POST /agents/eligibility/run with a single patient_id returns AgentRunResponse with task_id immediately (async).
The trace viewer shows the eligibility check in progress within 2 seconds.
Result card shows copay, deductible remaining, and OOP remaining from the 271 response.

8.2  Coding Agent Stories
US-C1: Auto-suggest codes from clinical note
As a medical coder, I want the coding agent to analyze the encounter note and suggest the correct CPT and ICD-10 codes with confidence scores, so that I spend my time reviewing rather than searching.
Acceptance Criteria:
POST /agents/coding/run with encounter_id triggers the coding agent.
The agent returns at minimum one CPT code, one primary ICD-10 code, and an overall confidence score.
Suggestions include per-code rationale drawn directly from the note text.
If documentation gaps are found, they are listed with specific guidance on what additional documentation is needed.
If overall_confidence >= 0.95 and no gaps, the encounter status is set to "Coded" automatically.
If confidence < 0.95 or gaps exist, a HITL coder review task is created.

US-C2: Code suggestion accuracy for 15 scenarios
As a demo engineer, I want each of the 15 synthetic SOAP note scenarios to produce an accurate and clinically defensible code suggestion, so that the demo is credible to healthcare coding experts.
Acceptance Criteria:
Running the coding agent on all 15 note templates produces expected CPT codes with confidence >= 0.85 for at least 13 of 15 scenarios.
ICD-10 primary code matches expected code for at least 12 of 15 scenarios.
No scenario produces a code combination flagged as invalid by the validation tool.

8.3  Scrubbing Agent Stories
US-S1: Pre-submission claim scrub
As a biller, I want every claim to be automatically scrubbed before submission so that we catch fixable errors before they become denials.
Acceptance Criteria:
POST /agents/scrubbing/run with claim_id runs all edit checks and returns a scrub_score.
Edit report lists each triggered edit with code, description, and severity (Warning / Error / Critical).
Claims with no critical edits and scrub_score >= 0.90 are automatically released.
Claims with critical edits are held and a HITL correction task is created.
The claim detail page shows the scrub score badge in color (green/amber/red).

8.4  Denial Agent Stories
US-D1: Denial root cause classification
As a denial management specialist, I want every new denial to be automatically classified by root cause within minutes of the ERA posting, so that I can prioritize my work queue by appeal opportunity.
Acceptance Criteria:
When a denial is posted, the denial agent runs automatically and writes denial_category within 2 minutes.
The denials page shows a donut chart of denial_category distribution that updates in real time.
Each denial record shows agent_root_cause and a plain-language explanation.

US-D2: Auto-drafted appeal letter
As a denial specialist, I want the denial agent to generate a complete, professional appeal letter for each Coding or Eligibility denial, so that I can review and submit with a single click.
Acceptance Criteria:
Appeal letter contains: payer address, claim reference numbers, date of service, provider NPI, corrected clinical justification, cited coverage policy, and a clear demand for reconsideration.
Letter is stored in denials.appeal_letter_text and displayed in the HITL review panel.
For auto-submit-eligible denials, POST /agents/denial/run triggers mock appeal submission and sets appeal_submitted_at.
A "high-value denial overturn" scenario demo shows a $28,400 claim going from denied to appeal-submitted in under 90 seconds of live demo time.

8.5  Analytics Agent Stories
US-A1: KPI anomaly detection
As a revenue cycle director, I want to be notified immediately when a key metric crosses a critical threshold, so that I can act before the issue compounds into significant revenue leakage.
Acceptance Criteria:
Analytics agent runs after every batch denial processing and every nightly eligibility run.
Any KPI that crosses an Alert threshold triggers a kpi.alert SSE event within 30 seconds.
The dashboard alert banner appears with the KPI name, current value, threshold, and a "View Details" link.
Alert history is accessible at GET /kpis/alerts.

US-A2: Cash flow forecast
As a CFO, I want a 30/60/90-day cash forecast based on current AR aging and historical payer payment patterns, so that I can manage working capital effectively.
Acceptance Criteria:
GET /kpis/timeseries/cash_forecast returns projected collections by week for 90 days.
Forecast is displayed as a line chart on the Analytics page with confidence bands.
When a denial spike scenario is run, the forecast updates downward within 10 seconds.



9.1  Overview
All payer interactions are simulated by an internal FastAPI mock payer service that mirrors real X12 transaction semantics without requiring external connectivity. The mock service introduces configurable latency (50–300ms) and failure rates (2% error simulation) to make the demo realistic.

9.2  Mock Endpoints

9.3  CARC/RARC Fixture
Include a fixture file carc_rarc.json containing at minimum the following denial reason codes used in seed data generation and agent decision logic:
CO-4 — The service code is inconsistent with the modifier used
CO-11 — Diagnosis inconsistent with procedure
CO-15 — Payment adjusted because authorization/precertification was absent
CO-16 — Claim/service lacks information which is needed for adjudication
CO-18 — Duplicate claim
CO-27 — Expenses incurred after coverage terminated
CO-29 — Time limit for filing has expired
CO-31 — Patient cannot be identified as our insured
CO-45 — Charge exceeds fee schedule / maximum allowable amount
CO-50 — Non-covered service
CO-167 — Service not medically necessary
CO-197 — Precertification/authorization/notification absent
CO-253 — Sequestration — reduction in federal payment



10.1  Performance
Individual agent runs (single claim/encounter) must complete within 30 seconds end-to-end in demo mode.
Batch runs (nightly eligibility, 500 patients) must complete within 3 minutes.
Dashboard KPI queries must respond within 500ms from DuckDB.
SSE stream must deliver first event within 1 second of agent start.
Frontend must render initial dashboard within 2 seconds on localhost.

10.2  Reliability & Demo Stability
POST /scenarios/reset must restore the entire database to seed state within 10 seconds to support back-to-back live demonstrations.
All agent runs must be idempotent — re-running an agent on the same entity produces consistent results (deterministic LLM temperature=0 for demo runs).
The SSE connection must auto-reconnect after 5-second drops without user action.
No unhandled exceptions should crash the demo; all errors must be surfaced as structured error events on the SSE stream and in the UI.

10.3  Developer Experience
Full environment setup from clone to running demo: single command — docker compose up.
Seed script must complete in under 60 seconds: python scripts/seed_all.py.
All API endpoints must have OpenAPI docs auto-generated at /docs.
Agent reasoning traces must be human-readable and exportable as JSON.
Code coverage target: 80% for agent logic, 70% for API routes.

10.4  Security (Demo Context)
No real PHI. All names, dates, and identifiers must be synthetic.
API key authentication is sufficient for demo purposes (header: X-API-Key).
No external network calls from agents — all payer interactions route to internal mock endpoints.
Sensitive configuration (API keys, model names) must be in .env file, not committed to source.



Claude Code should implement this system in the following phases. Each phase is independently runnable and testable before proceeding to the next.





Appendix A — CPT Code Fixture List
The following CPT codes must be included in the cpt_codes.json fixture. This list covers the most common codes across the 15 clinical scenarios and represents a realistic outpatient and inpatient mix:
E&M Outpatient: 99202, 99203, 99204, 99205 (new patient), 99212, 99213, 99214, 99215 (established)
E&M Inpatient: 99221, 99222, 99223 (initial), 99231, 99232, 99233 (subsequent), 99238, 99239 (discharge)
E&M Emergency: 99281, 99282, 99283, 99284, 99285
Preventive: 99385, 99386, 99395, 99396 (annual wellness), G0438, G0439 (AWV Medicare)
Procedures: 20610 (joint injection), 11400–11406 (skin excision), 93000 (ECG), 71046 (chest X-ray), 80053 (CMP), 85025 (CBC), 80061 (lipid panel), 82947 (glucose), 83036 (HbA1c)
Critical Care: 99291, 99292

Appendix B — ICD-10 Code Fixture List
Seed data must use codes from this fixture. Codes are matched to clinical scenarios:
Hypertension: I10 (essential HTN), I11.9 (hypertensive heart disease), I12.9 (hypertensive CKD)
Diabetes: E11.9 (T2DM uncontrolled), E11.65 (T2DM with hyperglycemia), E11.40 (diabetic neuropathy), E11.319 (diabetic retinopathy)
Cardiovascular: I25.10 (CAD), I50.9 (heart failure), I21.9 (AMI), R07.9 (chest pain NOS), R00.0 (tachycardia)
Respiratory: J44.1 (COPD exacerbation), J06.9 (URI), J18.9 (pneumonia), R05.9 (cough)
Musculoskeletal: M17.11 (osteoarthritis knee R), M54.5 (low back pain), M25.561 (pain in R knee)
Mental Health: F32.9 (MDD), F41.1 (GAD), F10.10 (AUD mild)
Other: N39.0 (UTI), L21.9 (seborrheic dermatitis), K21.0 (GERD with esophagitis), E78.5 (hyperlipidemia)

Appendix C — Environment Variables (.env)

Appendix D — Glossary

PRODUCT REQUIREMENTS DOCUMENT
Agentic AI Revenue Cycle
Management Demo System
An end-to-end demo platform demonstrating agentic AI across the full healthcare revenue cycle — from patient scheduling through AR analytics — using synthetic data and real autonomous agents.
Version 1.0  |  April 2026  |  CONFIDENTIAL DRAFT | 
Attribute | Value | 
Document Title | Agentic AI RCM Demo System — PRD v1.0 | 
Product Owner | TBD — Demo Engineering Lead | 
Target Platform | FastAPI (backend) + React (frontend) + LangGraph (agents) | 
Data Layer | Synthetic / Dummy — DuckDB + fixture JSON files | 
Primary Audience | Healthcare mid-market prospects, demo engineers, AI solution architects | 
Status | DRAFT — ready for Claude Code implementation | 
SECTION 1 — EXECUTIVE SUMMARY | 
In Scope: All 10 RCM stages with agents, synthetic data generation, dashboard UI, agent reasoning trace viewer, KPI analytics, and a scenario runner that injects edge-case events (payer rule change, denial spike, charge lag alert) to demonstrate agent response. | 
Out of Scope: Real PHI / production payer integrations, HIPAA compliance infrastructure, billing module checkout, multi-tenant architecture. | 
SECTION 2 — SYSTEM ARCHITECTURE | 
Layer | Technology | Role | Key Dependencies | 
Data Layer | DuckDB + JSON fixtures | Synthetic patient, claim, and payer data | Faker, custom generators | 
Agent Layer | LangGraph + Claude claude-sonnet-4-20250514 | Autonomous RCM agents + orchestrator | Anthropic SDK, tool definitions | 
API Layer | FastAPI + Pydantic v2 | REST endpoints, SSE agent event stream | SQLAlchemy, background tasks | 
UI Layer | React 18 + TypeScript + Tailwind | Dashboard, queue views, trace viewer | Recharts, React Query | 
rcm-agentic-demo/
├── backend/
│   ├── agents/          # One module per agent (eligibility, coding, scrubbing, denial, posting, analytics)
│   ├── api/             # FastAPI routers (claims, patients, agents, events, kpis)
│   ├── data/            # DuckDB schema, seed scripts, fixture JSON
│   ├── models/          # Pydantic models (shared across agents and API)
│   ├── orchestrator/    # LangGraph workflow definition
│   └── tools/           # Agent tool implementations (payer mock, coding engine, etc.)
├── frontend/
│   ├── src/
│   │   ├── pages/       # Dashboard, ClaimQueue, AgentTrace, PatientSearch, Analytics
│   │   ├── components/  # Shared UI components
│   │   └── hooks/       # React Query hooks, SSE hook
│   └── public/
├── scripts/             # Seed scripts, scenario injectors
├── tests/               # Pytest + Playwright
└── docs/                # ADRs, data dictionary, agent specs | 
SECTION 3 — SYNTHETIC DATA LAYER | 
Column | Type | Example | Notes | 
patient_id | UUID PK | pt-00001 | Prefixed string for readability | 
first_name | VARCHAR | Maria | Faker: first_name() | 
last_name | VARCHAR | Gonzalez | Faker: last_name() | 
dob | DATE | 1968-04-12 | Uniform distribution 1940–2010 | 
gender | VARCHAR | F | M/F/U weighted 48/48/4 | 
address_line1 | VARCHAR | 412 Oak Street | Faker: street_address() | 
city | VARCHAR | Birmingham | Weighted: AL/TN/GA cities | 
state | VARCHAR | AL | — | 
zip_code | VARCHAR | 35203 | Valid USPS ZIP from fixture list | 
phone | VARCHAR | 205-555-0174 | Faker: numerify | 
email | VARCHAR | maria.g@example.com | Non-real domain | 
mrn | VARCHAR | MRN-10042 | Sequential, prefixed | 
primary_payer_id | VARCHAR FK | payer-001 | FK → payers table | 
secondary_payer_id | VARCHAR FK | payer-004 | Nullable; 22% of patients have secondary | 
propensity_score | FLOAT | 0.73 | Synthetic 0–1; used by collections agent | 
language_pref | VARCHAR | ES | EN/ES/Other weighted 78/18/4 | 
created_at | TIMESTAMP | 2025-01-15 08:32:00 | Seeded within last 12 months | 
Column | Type | Example | Notes | 
payer_id | VARCHAR PK | payer-001 | — | 
payer_name | VARCHAR | BlueStar Commercial | Fictional payer names | 
payer_type | VARCHAR | Commercial | Medicare / Medicaid / Commercial / Self-Pay | 
payer_id_x12 | VARCHAR | BSC01 | Fictional X12 payer ID | 
avg_days_to_pay | INTEGER | 28 | Used to simulate adjudication lag | 
denial_rate_baseline | FLOAT | 0.12 | Fraction of claims denied; payer-specific | 
timely_filing_days | INTEGER | 90 | Days from service date to submit | 
fee_schedule_multiplier | FLOAT | 1.18 | Multiplier on Medicare rates for contracted allowed | 
portal_mock_url | VARCHAR | /mock/payer/BSC01/eligibility | Internal mock endpoint | 
Column | Type | Example | Notes | 
encounter_id | VARCHAR PK | enc-00001 | — | 
patient_id | VARCHAR FK | pt-00142 | — | 
provider_npi | VARCHAR | 1234567890 | 10 digit synthetic NPI | 
facility_npi | VARCHAR | 9876543210 | — | 
encounter_type | VARCHAR | Outpatient | Outpatient / Inpatient / ED / Observation | 
service_date | DATE | 2026-02-14 | Spread across last 90 days | 
discharge_date | DATE | 2026-02-14 | Same as service_date for outpatient | 
place_of_service | VARCHAR | 11 | CMS POS codes | 
attending_physician | VARCHAR | Dr. Sandra Okonkwo | Faker + title | 
chief_complaint | TEXT | Chest pain, shortness of breath | Synthetic clinical text | 
soap_note_text | TEXT | (see §3.8) | Synthetic clinical note for coding agent | 
auth_required | BOOLEAN | true | 35% of encounters require prior auth | 
auth_status | VARCHAR | Approved | Pending / Approved / Denied / Not Required | 
charge_lag_days | INTEGER | 2 | Days between service_date and charge_drop_date | 
status | VARCHAR | Billed | Scheduled / Checked-in / Coded / Billed / Paid / Denied | 
Column | Type | Example | Notes | 
claim_id | VARCHAR PK | clm-00001 | — | 
encounter_id | VARCHAR FK | enc-00001 | — | 
claim_type | VARCHAR | 837P | 837P (professional) or 837I (institutional) | 
payer_id | VARCHAR FK | payer-003 | — | 
total_billed | DECIMAL(10,2) | 1250.00 | Sum of charge line items | 
total_allowed | DECIMAL(10,2) | 892.40 | Payer contractual allowable | 
total_paid | DECIMAL(10,2) | 714.00 | Actual payment received | 
patient_responsibility | DECIMAL(10,2) | 178.40 | Copay + coinsurance + deductible | 
submission_date | DATE | 2026-02-17 | Date submitted to clearinghouse | 
adjudication_date | DATE | 2026-03-10 | Date payer adjudicated | 
claim_status | VARCHAR | Paid | Draft / Submitted / Accepted / Denied / Paid / Appealed | 
rejection_reason | VARCHAR | CO-4 | CARC code if denied; NULL if paid | 
timely_filing_deadline | DATE | 2026-05-15 | Computed: service_date + payer TF days | 
scrub_score | FLOAT | 0.94 | 0–1 rejection probability from scrubbing agent | 
appeal_id | VARCHAR FK | app-00012 | FK → appeals table; NULL if not appealed | 
era_posted | BOOLEAN | true | Whether ERA has been auto-posted | 
Column | Type | Example | Notes | 
line_id | VARCHAR PK | line-00001 | — | 
claim_id | VARCHAR FK | clm-00001 | — | 
cpt_code | VARCHAR | 99214 | E&M / procedure CPT from fixture list | 
icd10_primary | VARCHAR | I10 | Primary diagnosis code | 
icd10_secondary | VARCHAR | E11.9 | Secondary dx; nullable | 
modifier | VARCHAR | 25 | CPT modifier; nullable | 
units | INTEGER | 1 | — | 
charge_amount | DECIMAL(10,2) | 275.00 | Per-unit charge | 
allowed_amount | DECIMAL(10,2) | 196.00 | Payer allowable | 
revenue_code | VARCHAR | 0450 | UB-04 revenue code for institutional | 
ndc_code | VARCHAR | 12345-678-90 | For drug charges; nullable | 
coding_confidence | FLOAT | 0.91 | From coding agent; 1.0 = manual | 
SECTION 4 — AGENT SPECIFICATIONS | 
AgentInput: { entity_id: str, entity_type: str, context: dict, run_mode: "auto" | "assisted" }
AgentOutput: { status: "complete" | "escalated" | "failed", result: dict, reasoning_trace: str, confidence: float, hitl_required: bool, hitl_reason: Optional[str] } | 
You are a certified professional coder (CPC) AI assistant. Analyze the clinical note provided and suggest the most accurate CPT procedure codes, ICD-10-CM diagnosis codes, and modifiers. For each code, provide: the code itself, its description, your confidence score (0–1), and a brief clinical rationale drawn from the note. Flag any documentation gaps that would prevent accurate coding. Always adhere to CMS coding guidelines and payer-specific policies where known. | 
Category | Common CARCs | Agent Action | HITL Trigger | 
Eligibility | CO-27, CO-29, CO-31 | Verify current eligibility; rebill | If coverage gap confirmed | 
Prior Auth | CO-15, CO-197 | Obtain retro auth or draft appeal | Always — retro auth | 
Coding / DX | CO-4, CO-11, CO-16 | Suggest corrected codes; correct & rebill | If code change required | 
Med Necessity | CO-50, CO-167 | Pull clinical docs; draft appeal | Always — clinical review | 
Timely Filing | CO-29 | Compile proof of timely filing | If proof unclear | 
Duplicate | CO-18 | Verify — write off if confirmed duplicate | If original not found | 
Contractual | CO-45, CO-253 | Auto write-off if ≤$50; else flag | If >$50 variance | 
Propensity Score | Segment | Primary Channel | Offer Type | 
0.80–1.00 | High | Text / Email | Standard statement | 
0.50–0.79 | Medium | Email + Paper | 3-month payment plan | 
0.20–0.49 | Low | Paper + Call | Extended plan + charity screen | 
0.00–0.19 | Hardship | Call required | Financial counseling referral | 
KPI | Target | Alert Threshold | Calculation | 
Days in AR (overall) | < 45 | > 55 | Total AR / Avg daily charges | 
First Pass Rate | > 94% | < 90% | Clean claims / total submitted | 
Denial Rate | < 8% | > 12% | Denied claims / total submitted | 
Net Collection Rate | > 96% | < 93% | Collected / (Billed − contractual) | 
AR > 90 Days | < 15% | > 20% | 90+ AR / total AR | 
Charge Lag (avg) | < 2.5 days | > 4 days | Avg(charge_drop − service_date) | 
Appeal Overturn Rate | > 55% | < 40% | Overturned / total appealed | 
Auth Denial Rate | < 5% | > 8% | Auth denials / total auth requests | 
SECTION 5 — AGENT ORCHESTRATION | 
class RCMWorkflowState(TypedDict):
    encounter_id: Optional[str]
    claim_id: Optional[str]
    denial_id: Optional[str]
    patient_id: Optional[str]
    current_stage: str
    agent_outputs: Dict[str, AgentOutput]
    hitl_queue: List[HITLTask]
    errors: List[str]
    run_mode: Literal["auto", "assisted", "demo"] | 
Scenario | Injected Event | Expected Agent Response | 
Payer Rule Change | BlueStar adds new LCD restriction on CPT 99214 | Scrubbing agent flags 47 affected claims; coding agent re-reviews | 
Denial Spike | 18% of Medicare claims denied CO-50 on same day | Analytics agent alerts; denial agent batch-classifies and drafts appeals | 
Charge Lag Alert | Charge lag spikes to 5.2 days for orthopedics | Analytics agent alerts; dashboard shows trend; HITL task created | 
Eligibility Gap | 12 patients coverage lapsed before scheduled service | Eligibility agent flags; HITL queue shows 12 tasks; financial counseling offered | 
Underpayment Pattern | Apex PPO underpaying 99215 by 12% for 30 days | Tracking agent flags variance; analytics agent surfaces systemic pattern | 
High-Value Denial Overturn | $28,400 inpatient claim denied CO-11 (Dx inconsistent); coding agent corrects primary diagnosis; appeal auto-submitted | Denial agent classifies CO-11 as Coding/DX; corrected primary diagnosis from R07.9 to I21.4; appeal generated and submitted | 
SECTION 6 — API SPECIFICATIONS | 
Method | Path | Request Body / Params | Response | 
GET | /patients | page, page_size, search | PaginatedPatientList | 
GET | /patients/{id} | — | PatientDetail with encounters | 
GET | /claims | status, payer_id, date_from, date_to | PaginatedClaimList | 
GET | /claims/{id} | — | ClaimDetail with lines and events | 
GET | /claims/{id}/trace | — | AgentEventList for this claim | 
POST | /agents/eligibility/run | { patient_id, payer_id, service_date } | AgentRunResponse with task_id | 
POST | /agents/coding/run | { encounter_id } | AgentRunResponse with task_id | 
POST | /agents/scrubbing/run | { claim_id } | AgentRunResponse with task_id | 
POST | /agents/denial/run | { denial_id } | AgentRunResponse with task_id | 
POST | /agents/analytics/run | { as_of_date? } | AgentRunResponse with task_id | 
GET | /agents/tasks/{task_id} | — | AgentTaskStatus with output | 
GET | /hitl/queue | status=pending | HITLTaskList | 
POST | /hitl/{task_id}/resolve | { decision, notes } | HITLResolutionResult | 
GET | /kpis/dashboard | as_of_date? | KPIDashboardSnapshot | 
GET | /kpis/timeseries/{metric} | days_back=30 | KPITimeseries | 
GET | /kpis/ar-aging | payer_id? | ARAgingSnapshot | 
GET | /events/stream | — | SSE stream of AgentEvent objects | 
POST | /scenarios/run | { scenario_id } | ScenarioRunResult | 
POST | /scenarios/reset | — | Resets DB to seed state | 
{
  "event_id": "uuid",
  "event_type": "agent.started" | "agent.tool_call" | "agent.reasoning" | "agent.completed" | "agent.escalated" | "kpi.alert" | "hitl.task_created",
  "agent_name": "coding_agent",
  "entity_type": "encounter" | "claim" | "denial" | "patient",
  "entity_id": "enc-00142",
  "data": { ... event-specific payload ... },
  "timestamp": "2026-04-15T14:32:00Z"
} | 
SECTION 7 — FRONTEND REQUIREMENTS | 
Page / Route | Primary Purpose | Key Components | 
/dashboard | Executive KPI overview | KPI card grid, AR aging bar chart, denial rate trend, Days-in-AR gauge, live agent activity ticker | 
/claims | Claim worklist and search | Filterable table (status, payer, date range), scrub score badge, claim status chip, quick-action buttons | 
/claims/:id | Single claim detail | Claim header, line items table, ERA detail, agent event timeline, "Run Agent" actions | 
/patients | Patient search | Search by name/MRN, encounter history, insurance status, balance due | 
/patients/:id | Patient 360 | Demographics, insurance, encounter timeline, balance summary, eligibility status badge | 
/review-queue | Human-in-the-loop queue | Prioritized task list, task detail panel with agent reasoning and recommended action, approve/reject controls | 
/denials | Denial management center | Denial list with CARC breakdown, root cause donut chart, appeal status tracker, batch run denial agent | 
/agent-trace | Agent reasoning viewer | Live SSE feed of agent events, expandable reasoning traces, tool call log, confidence timeline | 
/analytics | AR analytics deep-dive | KPI timeseries charts, payer performance matrix, cash flow forecast, anomaly alert history | 
/scenarios | Demo scenario runner | Scenario cards, run button, real-time progress panel showing agent reactions | 
SECTION 8 — USER STORIES & ACCEPTANCE CRITERIA | 
SECTION 9 — MOCK PAYER API | 
Endpoint | Mirrors | Behavior | 
/mock/payer/{id}/eligibility | X12 270/271 | Returns eligibility based on patient fixture; 5% return "inactive" to demonstrate escalation | 
/mock/payer/{id}/auth/submit | PA portal POST | Returns auth_number for 80% of requests; 15% pend; 5% deny | 
/mock/payer/{id}/auth/status | PA status check | Returns current auth status by auth_id; pending auths resolve after 2 seconds in demo | 
/mock/payer/{id}/claim/status | X12 277 | Returns adjudication status; denied claims have CARC/RARC codes from fixture | 
/mock/era/{id} | 835 ERA | Returns fixture ERA JSON with payment detail and adjustment codes | 
/mock/payer/{id}/appeal/submit | Payer portal POST | Accepts appeal; returns case_number; 60% eventually overturn in scenario simulation | 
SECTION 10 — NON-FUNCTIONAL REQUIREMENTS | 
SECTION 11 — RECOMMENDED IMPLEMENTATION SEQUENCE | 
Phase | Name | Deliverables | Est. Effort | 
1 | Data Foundation | DuckDB schema, all table definitions, seed scripts for all 9 tables, SOAP note fixtures, CARC/RARC fixture, payer fixture, 500 patients + 3,000 encounters + 3,000 claims + line items | ~4 hrs | 
2 | Mock Payer API | FastAPI mock payer service with all 6 endpoints, configurable latency/error injection, fixture-based responses | ~2 hrs | 
3 | Agent Framework | LangGraph state schema, agent base class, tool registry, AgentOutput model, SSE event emitter, agent_event_log writer | ~3 hrs | 
4 | Core Agents | Eligibility agent (full), Coding agent (full), Scrubbing agent (full) — all with HITL queue integration | ~5 hrs | 
5 | Revenue Agents | Tracking agent, ERA Posting agent, Denial Management agent, Collections agent | ~5 hrs | 
6 | Analytics Agent | Analytics agent with all 8 KPI monitors, anomaly detection, cash forecast, alert system | ~3 hrs | 
7 | FastAPI Routes | All 20 API endpoints, SSE stream, OpenAPI docs, background task runner, scenario endpoints | ~4 hrs | 
8 | React Frontend | All 10 pages, KPI dashboard, claim worklist, agent trace viewer, HITL review queue, scenario runner | ~6 hrs | 
9 | Scenarios + Polish | 6 demo scenarios, reset endpoint, Docker Compose, README, end-to-end tests | ~3 hrs | 
Total estimated implementation effort for a skilled Claude Code session: 35–40 hours of compute. Phases 1–3 must be completed before any agent work begins. The mock payer API must be running for all agent tests. | 
SECTION 12 — APPENDICES | 
ANTHROPIC_API_KEY=your_key_here
CLAUDE_MODEL=claude-sonnet-4-20250514
DEMO_API_KEY=demo-key-12345
DATABASE_PATH=./data/rcm_demo.duckdb
SEED_RANDOM_SEED=42
MOCK_PAYER_BASE_URL=http://localhost:8000/mock
MOCK_PAYER_LATENCY_MS=150
MOCK_PAYER_ERROR_RATE=0.02
AGENT_TEMPERATURE=0.0
AGENT_MAX_TOKENS=2048
SSE_KEEPALIVE_INTERVAL=15
LOG_LEVEL=INFO | 
Term | Definition | 
CARC | Claim Adjustment Reason Code — standardized code explaining why a claim was adjusted or denied | 
RARC | Remittance Advice Remark Code — supplemental code providing additional denial context | 
835 | X12 EDI transaction: Electronic Remittance Advice (ERA) — payer payment detail file | 
837P/837I | X12 EDI transaction: Electronic claim submission — Professional (837P) or Institutional (837I) | 
270/271 | X12 EDI transaction: Eligibility inquiry (270) and response (271) | 
277 | X12 EDI transaction: Claim status inquiry and response | 
DRG | Diagnosis-Related Group — inpatient reimbursement classification system | 
CPT | Current Procedural Terminology — AMA procedure code set | 
ICD-10 | International Classification of Diseases, 10th Revision — diagnosis and procedure codes | 
LCD/NCD | Local/National Coverage Determination — CMS rules defining when a service is covered | 
NCCI | National Correct Coding Initiative — CMS bundling rules preventing unbundling of procedures | 
HITL | Human-in-the-Loop — workflow pattern where AI acts autonomously but escalates uncertain cases to humans | 
First Pass Rate | Percentage of claims accepted by the payer on first submission without rejection or denial | 
Days in AR | Average number of days from service date to payment receipt; key RCM efficiency metric | 
ERA | Electronic Remittance Advice — machine-readable version of the Explanation of Benefits (EOB) | 
Prior Auth | Pre-service authorization required by the payer before a procedure will be covered | 
COB | Coordination of Benefits — process for determining primary vs. secondary payer when a patient has multiple insurers | 
Propensity Score | Model-derived probability (0–1) that a patient will pay their balance; drives collections strategy | 
Scrub Score | Agent-assigned probability (0–1) that a claim will be accepted on first submission | 
Ready for Claude Code
This PRD is written to be handed directly to Claude Code as a complete implementation brief. Begin with Section 11 (Implementation Sequence) and execute each phase in order. All data schemas, agent tool signatures, API contracts, and acceptance criteria are specified at the level of precision required for direct code generation without additional clarification. | 
