# RCM Agentic AI Demo — PRD Change Order v1.1

**Source PRD:** `RCM_Agentic_AI_Demo_PRD_v1_0.docx`
**Purpose:** This document specifies corrections and improvements to the already-generated RCM demo codebase. Apply each change in the order listed. Each section specifies the file(s) to modify, the change to make, and the rationale. When in doubt, prefer minimal edits that preserve existing structure.

**Execution guidance for Claude Code:**
- Work through sections sequentially. Each section is independently testable.
- After each section, run the existing test suite and the seed script; fix any regressions before proceeding.
- Do not refactor beyond the stated scope. This is a corrections pass, not a rewrite.
- When a change touches both seed data and agent logic, update seed data first, then agents, then tests.

---

## Section 1 — Critical Fixes (Must apply before next demo)

### 1.1 Update Claude model identifier everywhere

**Problem:** The codebase references `claude-sonnet-4-20250514`, which is scheduled for API retirement on June 15, 2026.

**Change:**
- Replace all occurrences of `claude-sonnet-4-20250514` with `claude-sonnet-4-6`.
- For the Denial Management Agent and Coding Agent only, introduce a separate model setting `CLAUDE_MODEL_REASONING=claude-opus-4-7` and use it in those two agents. Rationale: these two agents do the highest-stakes reasoning (appeal letter generation, clinical code extraction) and benefit from the stronger model; the others can run on Sonnet for cost.

**Files to modify:**
- `.env.example` — update `CLAUDE_MODEL=claude-sonnet-4-6`; add `CLAUDE_MODEL_REASONING=claude-opus-4-7`
- `backend/agents/base.py` (or wherever the model is loaded) — add a `model_override` parameter
- `backend/agents/denial.py` and `backend/agents/coding.py` — load `CLAUDE_MODEL_REASONING` instead of the default
- Any agent unit tests that assert a specific model string
- `docker-compose.yml` if the model is passed as an env var
- README references

**Acceptance check:** `grep -r "claude-sonnet-4-20250514" .` returns zero matches.

---

### 1.2 Fix CO-29 duplicate categorization in Denial Agent

**Problem:** The Denial Categories table lists CO-29 under both "Eligibility" and "Timely Filing". CO-29 is *Time limit for filing has expired* — it is timely filing only.

**Change:**
In `backend/agents/denial.py` (or wherever the denial category mapping lives), update the CARC-to-category mapping:

```python
DENIAL_CATEGORY_MAP = {
    # Eligibility
    "CO-27": "Eligibility",
    "CO-31": "Eligibility",
    "CO-32": "Eligibility",  # Patient not eligible dependent — added
    # Prior Auth
    "CO-197": "Prior Auth",  # Primary — current standard
    "CO-15":  "Prior Auth",  # Legacy — some payers still use
    # Coding / DX
    "CO-4":  "Coding",
    "CO-11": "Coding",
    "CO-16": "Coding",
    # Medical Necessity
    "CO-50":  "Medical Necessity",
    "CO-167": "Medical Necessity",
    # Timely Filing
    "CO-29": "Timely Filing",  # Only here — not Eligibility
    # Duplicate
    "CO-18": "Duplicate",
    # Contractual
    "CO-45":  "Contractual",
    "CO-253": "Contractual",
}
```

**Files to modify:**
- `backend/agents/denial.py` — the denial category mapping
- `backend/data/fixtures/carc_rarc.json` — if category is stored alongside the CARC, update it there
- Any unit test that asserts CO-29 maps to Eligibility — update to Timely Filing

---

### 1.3 Fix the "High-Value Denial Overturn" scenario (DRG/CO-4 incoherence)

**Problem:** The scenario narrates a CO-4 denial (modifier inconsistency) that the agent "corrects to DRG 194." DRGs are inpatient grouping codes assigned by a grouper from ICD-10-CM/PCS codes; changing a DRG does not resolve a modifier denial.

**Change:** In `scripts/scenarios.json` (or wherever scenarios are defined), replace the scenario definition:

```json
{
  "scenario_id": "high_value_denial_overturn",
  "display_name": "High-Value Denial Overturn",
  "injected_event": {
    "claim_id": "clm-SEEDED-HIGH-VALUE",
    "claim_type": "837I",
    "total_billed": 28400.00,
    "carc_code": "CO-11",
    "denial_reason": "Diagnosis inconsistent with procedure",
    "original_primary_dx": "R07.9",
    "corrected_primary_dx": "I21.4"
  },
  "expected_agent_response": "Denial agent classifies as Coding; coding agent re-reviews clinical note and suggests I21.4 (NSTEMI) as primary dx; appeal letter auto-generated citing the corrected dx and clinical evidence; auto-submitted to mock payer."
}
```

**Files to modify:**
- `scripts/scenarios.json`
- The seed script section that creates `clm-SEEDED-HIGH-VALUE` — ensure the claim is institutional (837I), has a clinical note that supports NSTEMI, and that the mock payer's overturn logic returns favorable on resubmission
- Any UI copy that mentions "DRG 194" — replace with "corrected primary diagnosis"

---

### 1.4 Anchor all demo dates to `DEMO_AS_OF_DATE`

**Problem:** Seed data uses real current dates at seed time. After a few weeks, every claim is past timely filing and every appeal deadline has expired, breaking the demo narrative.

**Change:**

1. Add to `.env.example`:
   ```
   DEMO_AS_OF_DATE=2026-04-15
   ```
   (The seed script should read this and treat it as "today" for all date computations. If unset, default to the current system date.)

2. In `scripts/seed_all.py`, replace every use of `date.today()` or `datetime.now()` with a module-level `AS_OF_DATE` loaded from the environment:
   ```python
   import os
   from datetime import date, datetime
   AS_OF_DATE = date.fromisoformat(os.getenv("DEMO_AS_OF_DATE") or date.today().isoformat())
   ```

3. All date offsets (service_date, submission_date, adjudication_date, timely_filing_deadline, appeal_deadline, ar_aging_snapshot.snapshot_date) must be computed relative to `AS_OF_DATE`, not `date.today()`.

4. The `POST /scenarios/reset` endpoint must re-run `seed_all.py` so reset behaves identically regardless of wall-clock time.

5. In the agent code (tracking agent's timely-filing check, denial agent's appeal deadline calc), add a helper `get_demo_today()` that reads the same env var so agents and seed data agree on "today."

**Files to modify:**
- `.env.example`
- `scripts/seed_all.py` and any helper seed modules
- `backend/api/scenarios.py` — make `/scenarios/reset` re-run the seed
- `backend/agents/tracking.py` and `backend/agents/denial.py` — use `get_demo_today()`
- `backend/utils/time.py` (create if absent) — contains `get_demo_today()`

**Acceptance check:** After running the seed with `DEMO_AS_OF_DATE=2026-04-15`, no claim should have a timely filing deadline in the past unless it was intentionally seeded that way for the "timely filing risk" scenario.

---

### 1.5 Replace "deterministic LLM" claim with actual LLM response caching

**Problem:** The codebase (likely in the README or config) claims temperature=0 makes the LLM deterministic. It does not — it reduces variance, not to zero. Real demo stability requires caching.

**Change:**

1. Add an LLM response cache keyed by a hash of `(model, system_prompt, messages, tools)`:

   ```python
   # backend/agents/llm_cache.py
   import hashlib, json, os
   from pathlib import Path

   CACHE_DIR = Path(os.getenv("LLM_CACHE_DIR", "./data/llm_cache"))
   CACHE_ENABLED = os.getenv("LLM_CACHE_MODE", "replay") in ("replay", "record")
   CACHE_MODE = os.getenv("LLM_CACHE_MODE", "replay")  # replay | record | off

   def _key(model, system, messages, tools):
       payload = json.dumps({"m": model, "s": system, "msgs": messages, "t": tools}, sort_keys=True)
       return hashlib.sha256(payload.encode()).hexdigest()

   def get_cached(model, system, messages, tools):
       if CACHE_MODE == "off": return None
       p = CACHE_DIR / f"{_key(model, system, messages, tools)}.json"
       return json.loads(p.read_text()) if p.exists() else None

   def put_cached(model, system, messages, tools, response):
       if CACHE_MODE == "off": return
       CACHE_DIR.mkdir(parents=True, exist_ok=True)
       p = CACHE_DIR / f"{_key(model, system, messages, tools)}.json"
       p.write_text(json.dumps(response))
   ```

2. Wrap the Anthropic client call: check cache first, fall back to live call, store response if in `record` mode.

3. Add env vars:
   ```
   LLM_CACHE_MODE=replay        # replay | record | off
   LLM_CACHE_DIR=./data/llm_cache
   ```

4. Commit a pre-recorded cache to the repo under `data/llm_cache/` so a fresh clone can run the full demo in `replay` mode with no API calls. Add a `scripts/record_llm_cache.py` that walks through all scenarios in `record` mode to regenerate the cache after prompt changes.

5. Update README: replace any "deterministic temperature=0" language with "demo replay stability is achieved via a committed LLM response cache; live mode is available by setting `LLM_CACHE_MODE=off`."

**Files to modify:**
- `backend/agents/llm_cache.py` (new)
- `backend/agents/base.py` — integrate cache wrapper
- `.env.example`
- `scripts/record_llm_cache.py` (new)
- `README.md`
- `data/llm_cache/` (new directory, committed)

---

## Section 2 — Substantive Fixes

### 2.1 Reconcile Coding Agent confidence thresholds

**Problem:** Acceptance criteria US-C2 allows confidence ≥ 0.85 for 13 of 15 scenarios, but the auto-approval rule requires confidence ≥ 0.95. With the current rule, auto-approval will almost never fire and the autonomous-agent narrative collapses.

**Change:**
1. Lower the auto-approval threshold to 0.90 in `backend/agents/coding.py`.
2. Update US-C2 acceptance target to: confidence ≥ 0.90 for at least 13 of 15 scenarios, with primary ICD-10 correct for at least 13 of 15.
3. In the seed SOAP note templates, verify each of the 15 templates contains sufficient clinical detail to realistically produce ≥ 0.90 confidence. Templates that are too terse should be expanded.
4. Update the Coding Agent unit tests to the 0.90 threshold.

**Files to modify:**
- `backend/agents/coding.py` — auto-approval constant
- `backend/data/fixtures/soap_note_templates.json` — review and expand thin templates
- `tests/agents/test_coding_agent.py`

---

### 2.2 Recalibrate batch performance budget

**Problem:** "Batch runs (nightly eligibility, 500 patients) must complete within 3 minutes" implies 360ms per patient including multiple tool calls and an LLM round-trip. This is not achievable with live LLM calls.

**Change:** Redesign the eligibility batch as a tiered flow:

1. **Tier 1 (deterministic, no LLM):** For each of the 500 patients, call `query_payer_eligibility` directly. Categorize the 271 response via rule-based logic (active / inactive / OON / COB conflict). ~200ms per patient on mock payer → ~100 seconds total.

2. **Tier 2 (LLM, only on exceptions):** For patients flagged in Tier 1 as OON, COB conflict, or high-balance exposure, invoke the LLM-based eligibility agent to reason about the case and draft the HITL task description. Typically 5–15% of batch → 25–75 patients × ~8 seconds each.

3. Total target: under 5 minutes for a full 500-patient batch with 10% exception rate. Update NFR §10.1 language accordingly.

4. Update the batch endpoint to emit progress events so the UI can show a progress bar during the 5-minute run.

**Files to modify:**
- `backend/agents/eligibility.py` — split into `run_tier1_batch()` and `run_tier2_exception()`
- `backend/api/agents.py` — batch endpoint emits SSE progress events
- `frontend/src/pages/EligibilityBatch.tsx` (if exists) or the dashboard — progress bar
- README NFR section

---

### 2.3 Reposition the first-pass rate uplift claim

**Problem:** Section 1.2 of the PRD claims the demo will "show first-pass claim acceptance rate improvement from a baseline of 85% to 94%+." On synthetic data, the demo author controls both numbers — this is not a demonstration of anything, and sophisticated buyers will say so.

**Change:** Update any UI copy, README language, or demo narration script to reframe this as mechanism-of-action rather than outcome:

- Before: "Agents improve first-pass rate from 85% to 94%+."
- After: "Agents identify and correct the specific error classes that drive first-pass rejections — missing modifiers, LCD mismatches, unbundling conflicts, and auth gaps — each shown live in the trace viewer. Customer uplift will depend on baseline error distribution."

**Files to modify:**
- `frontend/src/pages/Dashboard.tsx` — any copy referencing the uplift
- Demo narration script in `docs/demo_script.md` if present
- README "Strategic Objectives" section

---

### 2.4 Fix the orchestration graph: ERA arrival trigger

**Problem:** Current edge `tracking_agent → era_posting_agent (on payment ERA received)` misrepresents the real workflow. ERAs arrive from the payer asynchronously; tracking does not produce them.

**Change:** In `backend/orchestrator/workflow.py` (LangGraph StateGraph definition):

1. Remove the edge `tracking_agent → era_posting_agent`.
2. Add a new event source: a scheduled/manual trigger `era_arrival` that reads unposted ERAs from the fixture queue and invokes `era_posting_agent` directly.
3. Keep `era_posting_agent → collections_agent (on patient balance created)` as-is.
4. Keep `era_posting_agent → denial_agent (on CARC denial detected in ERA line)` — this is the correct relationship.

Add to the scenarios runner an "ERA batch arrives" event that injects a batch of unposted ERAs, triggering the posting agent.

**Files to modify:**
- `backend/orchestrator/workflow.py`
- `backend/api/scenarios.py`
- `scripts/scenarios.json`
- Diagram / ADR in `docs/` if one exists

---

### 2.5 Add the missing `self_review_appeal_letter` tool to the Denial Agent

**Problem:** The auto-submit criteria requires that "rendered appeal letter passes a self-review check," but no such tool is defined.

**Change:** In `backend/agents/denial.py`:

1. Add a new tool:
   ```python
   def self_review_appeal_letter(letter_text: str, claim_context: dict) -> dict:
       """Returns {'passes': bool, 'issues': List[str], 'confidence': float}.
       Invokes the LLM with a critic prompt that checks: (1) payer address present,
       (2) claim reference numbers present, (3) clinical justification cited,
       (4) coverage policy referenced, (5) clear demand for reconsideration,
       (6) no hallucinated facts not in claim_context."""
   ```

2. Add the critic system prompt under `backend/agents/prompts/appeal_critic.txt`.

3. Auto-submit only if `self_review_appeal_letter` returns `passes=True` AND `confidence >= 0.85`.

4. Add unit test with a deliberately weak appeal letter that should fail self-review.

**Files to modify:**
- `backend/agents/denial.py`
- `backend/agents/prompts/appeal_critic.txt` (new)
- `tests/agents/test_denial_agent.py`

---

### 2.6 Ground the propensity_score in observable features

**Problem:** `propensity_score` is currently a uniform random draw. Buyers will ask how it is computed and the answer is currently "it isn't."

**Change:** In `scripts/seed_patients.py` (or wherever patients are generated), derive propensity from observable features:

```python
def compute_propensity(patient, prior_payments):
    base = 0.5
    # ZIP-based income proxy (fixture-driven)
    base += ZIP_INCOME_ADJUSTMENT.get(patient.zip_code, 0.0)  # +/- 0.15
    # Age
    if patient.age >= 65: base += 0.10   # Medicare population pays more reliably
    elif patient.age < 30: base -= 0.05
    # Prior payment behavior
    if prior_payments:
        paid_on_time_ratio = sum(p.on_time for p in prior_payments) / len(prior_payments)
        base += (paid_on_time_ratio - 0.5) * 0.30
    # Current balance size
    if patient.current_balance > 2000: base -= 0.10
    return max(0.0, min(1.0, base))
```

Add `ZIP_INCOME_ADJUSTMENT` as a fixture with ~50 synthetic ZIP → income-tier mappings for AL/TN/GA.

**Files to modify:**
- `scripts/seed_patients.py`
- `backend/data/fixtures/zip_income.json` (new)
- Unit test to assert propensity distribution is reasonable (not uniform)

---

## Section 3 — Data and Fixture Corrections

### 3.1 Update invalid or outdated ICD-10 codes

**Problem:** Fixture contains codes that are deleted, renamed, or potentially invalid in the current ICD-10-CM code set.

**Change:** In `backend/data/fixtures/icd10_codes.json`:

| Old | New | Reason |
|-----|-----|--------|
| M54.5 | M54.50 | M54.5 was retired Oct 1, 2021; use M54.50 (Low back pain, unspecified) or M54.51 / M54.59 as clinically appropriate |
| Verify I12.9 | Keep if valid for "hypertensive CKD with stage 1-4 or unspecified" | Confirm against current ICD-10-CM; if invalid, use I12.0 instead |
| Verify E11.319 | Confirm exact descriptor | Should be "T2DM with unspecified diabetic retinopathy without macular edema" |

For any SOAP note template that currently references M54.5, update the expected code to M54.50.

**Files to modify:**
- `backend/data/fixtures/icd10_codes.json`
- `backend/data/fixtures/soap_note_templates.json` — any template referencing M54.5
- `tests/agents/test_coding_agent.py` — assertions against expected codes

---

### 3.2 Make synthetic NPIs Luhn-valid

**Problem:** `provider_npi` is generated as 10 random digits. Real NPIs use the Luhn check digit and anyone technical in the audience will notice.

**Change:** In the seed script, generate Luhn-valid 10-digit NPIs:

```python
def generate_npi():
    # NPI = 9 random digits + Luhn check digit, prefixed with the "80840" constant
    # for the Luhn calculation only (per NPI spec).
    base = ''.join(random.choices('0123456789', k=9))
    # Luhn check on "80840" + base
    check_input = "80840" + base
    total = 0
    for i, d in enumerate(reversed(check_input)):
        n = int(d)
        if i % 2 == 0:
            n *= 2
            if n > 9: n -= 9
        total += n
    check = (10 - (total % 10)) % 10
    return base + str(check)
```

**Files to modify:**
- `scripts/seed_encounters.py` — provider_npi and facility_npi generation
- Add a unit test that validates Luhn digit correctness on generated NPIs

---

### 3.3 Fix self-pay patient primary/secondary payer semantics

**Problem:** 10% of patients are self-pay, but `primary_payer_id` is not nullable in the schema and self-pay is both a patient status and a `payer-007` record, creating ambiguity.

**Change:**

1. In `backend/data/schema.sql` (or the DuckDB init), make `primary_payer_id` nullable.
2. In `scripts/seed_patients.py`:
   - Self-pay patients: `primary_payer_id = NULL`, `secondary_payer_id = NULL`, add a boolean column `is_self_pay = TRUE`.
   - Add `is_self_pay` column to the patients table.
3. Update the Eligibility Agent to skip self-pay patients entirely (no 271 call) and route directly to the collections agent for balance management.
4. Remove the `payer-007` record (or keep as "Self-Pay" for reporting only, never referenced as a primary_payer_id FK). Document the chosen approach in a code comment.

**Files to modify:**
- `backend/data/schema.sql`
- `scripts/seed_patients.py`
- `backend/agents/eligibility.py` — early return for self-pay
- `backend/models/patient.py` — Pydantic model

---

### 3.4 Reorganize claim status to separate status from appeal state

**Problem:** `claim_status` has "Appealed" as a top-level value, which overlaps with "Denied" (an appealed claim was first denied). The seeded distribution undercounts denials as a result.

**Change:**

1. Remove "Appealed" from the `claim_status` enum. Valid values: Draft / Submitted / Accepted / Denied / Paid.
2. Appeal state lives in two places already in the schema: `appeal_id` (FK, nullable) and `denials.appeal_submitted_at`. Use these.
3. Update the seeded distribution: 55% Paid, 20% Submitted, 23% Denied (of which roughly 22% — i.e., ~5% of all claims — have an `appeal_id` set), 2% Draft.
4. Update any UI filter that shows "Appealed" as a status chip — derive it from `claim_status='Denied' AND appeal_id IS NOT NULL`.

**Files to modify:**
- `backend/data/schema.sql`
- `scripts/seed_claims.py`
- `backend/models/claim.py`
- `frontend/src/pages/Claims.tsx` — status chip logic
- `frontend/src/pages/Denials.tsx` — appeal tracker logic

---

### 3.5 Clarify fictional X12 payer IDs

**Problem:** Fictional IDs like "BSC01" look like real X12 payer IDs and could confuse an integration-minded reviewer.

**Change:** In `backend/data/fixtures/payers.json`, rename `payer_id_x12` to `payer_id_x12_fictional` and add a top-of-file comment:

```json
{
  "_comment": "All payer_id_x12_fictional values are synthetic and do not correspond to any real payer ID in any X12 directory. For demo purposes only.",
  "payers": [...]
}
```

Update any API response that exposes this field to use the renamed key.

**Files to modify:**
- `backend/data/fixtures/payers.json`
- `backend/models/payer.py`
- Any API serializer exposing payer records

---

## Section 4 — Smaller Consistency Fixes

### 4.1 CORS for localhost development

Add explicit CORS configuration in `backend/main.py`:
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Add `FRONTEND_ORIGIN=http://localhost:3000` to `.env.example`.

### 4.2 Realistic effort estimates in README

Update the implementation phases in the README. Honest revised estimates:

| Phase | Original | Revised |
|-------|----------|---------|
| 1. Data Foundation | 4 hrs | 6–8 hrs |
| 2. Mock Payer API | 2 hrs | 3 hrs |
| 3. Agent Framework | 3 hrs | 5 hrs |
| 4. Core Agents (Eligibility, Coding, Scrubbing) | 5 hrs | 12–15 hrs |
| 5. Revenue Agents (Tracking, ERA, Denial, Collections) | 5 hrs | 15–18 hrs |
| 6. Analytics Agent | 3 hrs | 5 hrs |
| 7. FastAPI Routes | 4 hrs | 6 hrs |
| 8. React Frontend | 6 hrs | 18–22 hrs |
| 9. Scenarios + Polish | 3 hrs | 6 hrs |
| **Total** | **35–40 hrs** | **76–88 hrs** |

### 4.3 Promote CO-197 above CO-15 in prior-auth copy

In any UI copy, narration, or docs that mention prior-auth denials, list CO-197 first and treat CO-15 as legacy. The denial agent's category-to-CARC mapping (already updated in §1.2) handles this at the data layer.

---

## Section 5 — Verification Checklist

After applying all changes, verify:

- [ ] `grep -r "claude-sonnet-4-20250514" .` returns zero matches
- [ ] `grep -r "M54.5" .` returns zero matches (except in a migration note if any)
- [ ] `grep -r "DRG 194" .` returns zero matches
- [ ] Seed script runs cleanly with `DEMO_AS_OF_DATE=2026-04-15` and produces a demo where no claim is unintentionally past timely filing
- [ ] `POST /scenarios/reset` restores the demo in under 10 seconds and re-runs the seed
- [ ] Running the demo in `LLM_CACHE_MODE=replay` completes without making any Anthropic API calls
- [ ] Coding agent auto-approves at least 10 of 15 SOAP template scenarios
- [ ] Denial agent's high-value overturn scenario completes end-to-end with a corrected primary dx (not a DRG change)
- [ ] Self-pay patients have NULL `primary_payer_id` and are skipped by the Eligibility Agent
- [ ] Eligibility batch of 500 patients completes in under 5 minutes with progress events streaming
- [ ] All unit tests pass
- [ ] UI copy no longer claims first-pass rate uplift as a demo outcome

---

## Section 6 — Out of Scope for This Change Order

The following were considered but deliberately excluded. Do not address them in this pass:

- Multi-tenant architecture
- Real X12 transaction parsing (stay with JSON fixtures)
- HIPAA compliance infrastructure
- Real payer integrations
- Authentication beyond the demo API key
- Anything marked "Out of Scope" in the original PRD Section 1.3

If questions arise about changes not covered here, stop and ask rather than guessing.
