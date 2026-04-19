# RCM Agentic Transformation — Demo Story & Implementation Plan

## Context

We're recording a demo of an agentic AI system for the revenue cycle. Today the UI only exercises 4 of the 8 built agents (`eligibility`, `scrubbing`, `denial`, `analytics`); the other 4 (`coding`, `tracking`, `era_posting`, `collections`) ship with tests and HTTP endpoints but are never invoked in the live demo, and the LangGraph pipeline in `backend/app/orchestrator/graph.py:103-141` is dead code. That leaves the demo telling only the denial-recovery tail of the RCM story — the "save the day after things went wrong" part — rather than the full autonomous revenue cycle the PRD promises.

This plan captures (a) the narrative we want the recording to land and (b) the minimum code changes needed to stage it end-to-end on the existing codebase.

---

## The Story: A Day in the Life of an Agentic Revenue Cycle

**Setting.** A 500-patient multi-specialty group, 3,000 encounters/month. Before agentic AI, the revenue cycle looked like this: coders backlogged 4–6 days, 12% denial rate, 58 days in AR, 22% of AR over 90 days, $140k/month written off, and three FTEs spending their mornings chasing eligibility and ERAs. The CFO's monthly "why is cash down?" conversation was a ritual.

After deploying the agentic RCM system, the same day unfolds very differently.

### Act 1 — Morning: the system wakes up and triages itself

At 6:00 AM, the **Analytics Agent** runs a KPI snapshot across the full book of business (`backend/app/agents/analytics.py:124-201`). It computes eight KPIs against their thresholds — Days in AR, First Pass Rate, Denial Rate, Net Collection Rate, AR > 90, Charge Lag, Appeal Overturn Rate, open HITL queue — and writes an LLM-authored narrative of what changed overnight and which payers are drifting. Three alerts fire: Medicare denial rate jumped from 9% to 18% (a bulk CO-50 denial event), orthopedics charge lag is at 5.2 days, and AR > 90 ticked up to 21%.

Each alert is not just a dashboard color change — it's an instruction. The supervisor dispatches specialists.

### Act 2 — Mid-morning: specialists work in parallel, not in queues

**Eligibility Agent** runs ahead of the day's schedule. It processes every patient with an appointment in the next 72 hours, flags twelve coverage lapses (`scenarios.json` "Eligibility Gap"), and pushes each to a HITL task with the correct priority and suggested financial-counseling script. Front-desk staff come in to a clean, prioritized worklist instead of a FAX pile.

**Coding Agent** picks up yesterday's 180 completed encounters. For each it reads the SOAP note, proposes CPT + ICD-10, computes a confidence, and either auto-codes (>= 0.90, ~70% of the volume) or hands to a human coder for the exceptions. The coder's day shifts from data entry to adjudication — 4× throughput at measurably higher accuracy.

**Scrubbing Agent** runs every claim before submission against payer-specific edits. When a payer pushes a new LCD restriction mid-morning (`scenarios.json` "Payer Rule Change"), the scrubbing agent flags 47 in-flight claims; the coding agent re-reviews them before anything hits the payer. The rework happens *before* the denial, not six weeks after.

**Denial Agent** works the existing denial backlog — 18% of Medicare claims came back CO-50 overnight. It classifies each (Coding / Eligibility / Med-Necessity / Prior Auth / Timely Filing / Duplicate / Contractual), drafts an appeal letter from the right template, self-reviews it, and auto-submits the ones with high confidence and a safe deadline. The rest go to HITL with a pre-populated letter that cuts appeal-writing from 45 minutes to 5. The marquee beat is the **high-value overturn**: a $28,400 inpatient denial where the coding agent corrects primary Dx from R07.9 to I21.4 (NSTEMI) and the appeal comes back overturned.

### Act 3 — Afternoon: closing the loop

**ERA Posting Agent** processes the day's 835 remittance batch. It auto-posts clean payments, reconciles partials and adjustments against the expected contracted rate, and flags contract-underpayment patterns — catching that Apex PPO has been underpaying CPT 99215 by 12% for a month (`scenarios.json` "Underpayment Pattern"). What used to be a two-day manual posting job finishes in minutes.

**Tracking Agent** sweeps every open claim for aging, timely-filing windows, and payer response SLAs. It re-queues stalled claims, escalates the ones approaching deadline, and feeds the denial agent when the payer response comes back adverse. Nothing slips through the cracks because nothing relies on a human remembering.

**Collections Agent** scores patient balances by propensity-to-pay using observable features (prior payment behavior, coverage type, balance size, visit recency) and dispatches the right dunning path — text + self-service link for high-propensity small balances, payment plan offer for medium, financial counselor referral for low. Collections yield rises without any additional patient friction.

### Epilogue — End of day: the KPIs tell the story

The Analytics Agent re-runs the snapshot. Days in AR dropped from 58 to 46. First pass rate climbed from 88% to 94%. Denial rate fell from 12% to 7%. Appeal overturn rate rose from 38% to 62%. Open HITL tasks are down because the humans actually cleared the queue — because the queue was small, prioritized, and pre-populated. The CFO's monthly ritual stops being about explaining cash variance and starts being about where to redeploy the capacity that was freed.

**What changed is not just the numbers. It's what humans spend their day on.** Staff stopped being claim-processors and started being exception-handlers and relationship-managers. That is the transformation.

---

## How the Demo Should Stage the Story

The demo has **six seeded scenarios** (`backend/app/data/fixtures/scenarios.json`) that map directly to the story beats:

| Story Beat | Scenario | Agents It Should Trigger |
|---|---|---|
| Morning KPI sweep | (run analytics directly, no injection) | `analytics` |
| Eligibility gap | `eligibility_gap` | `eligibility` → HITL |
| Payer rule change | `payer_rule_change` | `scrubbing` → `coding` |
| Denial spike | `denial_spike` | `analytics` → `denial` (batch) |
| Charge lag alert | `charge_lag_alert` | `analytics` → `tracking` → HITL |
| Underpayment pattern | `underpayment_pattern` | `tracking` → `analytics` → `era_posting` |
| High-value overturn | `high_value_overturn` | `denial` → `coding` → auto-submit → (overturn) |
| Closing KPI snapshot | (rerun analytics) | `analytics` |

Today only three of those beats (eligibility_gap, denial_spike partially, high_value_overturn) land visibly in the UI because coding / tracking / era_posting / collections have no run buttons and no automatic trigger.

### Recommended implementation

**1. Add standalone "Run Agent" buttons for the missing four**, modeled on the existing pattern at `frontend/src/pages/Denials.tsx:33-39` and `frontend/src/pages/Analytics.tsx:40`. Put each on its natural home page:
- `coding` → `frontend/src/pages/ClaimDetail.tsx` (beside the existing Scrub button) and on a per-encounter surface
- `tracking` → new tile on `Dashboard.tsx`, or on `Claims.tsx`
- `era_posting` → new "Payments" or "Remittance" section (can live on `Dashboard.tsx` for now)
- `collections` → on `PatientDetail.tsx` alongside the existing eligibility trigger

Each button calls the existing endpoint in `backend/app/api/agents.py` (`/agents/coding/run`, `/agents/tracking/run`, `/agents/era/run`, `/agents/collections/run`) — no backend work required.

**2. Add a "Run Daily Briefing" supervisor button on the Dashboard.** This is the narrative centerpiece. It fires the agents in story order and lets the live `AgentTraceFeed` carry the demo:
1. `analytics` (opening KPIs)
2. `eligibility` (upcoming appointments)
3. `coding` (yesterday's encounters)
4. `scrubbing` (outbound queue)
5. `tracking` (open claims sweep)
6. `denial` (open denial backlog)
7. `era_posting` (today's 835 batch)
8. `collections` (patient balances)
9. `analytics` (closing KPIs — show the delta)

For the recording, this can be a frontend-only mutation that calls each endpoint in sequence (same pattern as `Denials.tsx:18-27`'s batch loop). No new backend code needed. If time permits, a thin `/agents/supervisor/run` endpoint that orchestrates server-side is cleaner, but a client-side sequencer is sufficient for a scripted recording.

**3. Add KPI-delta panel to `Analytics.tsx`** so the before/after in the epilogue is visible on screen — capture the `kpi_cards` from the first analytics run, diff against the last.

**4. Pre-recording configuration.** Pin determinism before filming:
- Commit an LLM cache under `data/llm_cache/` and run in replay mode (`docs/RCM_Demo_PRD_Fixes_ChangeOrder.md:183`)
- Export `DEMO_AS_OF_DATE=2026-04-15` (or equivalent) so timely-filing math is stable (`backend/app/utils/time.py`)
- Hit `POST /api/v1/scenarios/reset` immediately before recording (`backend/app/api/scenarios.py:42-49`)

---

## Critical Files

| Purpose | Path |
|---|---|
| Add "Run" buttons | `frontend/src/pages/ClaimDetail.tsx`, `Dashboard.tsx`, `PatientDetail.tsx`, `Claims.tsx` |
| Supervisor sequencer button | `frontend/src/pages/Dashboard.tsx` (new `useMutation` modeled on `Denials.tsx:18-27`) |
| Endpoints (no changes, just confirm) | `backend/app/api/agents.py:42-117` |
| KPI delta display | `frontend/src/pages/Analytics.tsx` |
| Scenarios (no changes) | `backend/app/data/fixtures/scenarios.json`, `backend/app/orchestrator/scenarios.py` |
| Determinism env | `backend/app/utils/time.py`, `backend/app/config.py` |

Reuse, don't rebuild:
- `api()` helper and `useMutation` pattern from `Denials.tsx`
- `useSSE()` and `AgentTraceFeed` already display events from all eight agents — no change needed
- Every agent emits `agent.started` / `agent.tool_call` / `agent.completed` / `kpi.alert` / `hitl.task_created` already

---

## Verification

1. **Dry-run the supervisor sequence end-to-end** against a freshly reset DB. All 9 steps should complete, the trace feed should show each agent's tool calls and reasoning, and no agent should error. This is the first time `run_pipeline`-like behavior has been exercised from the UI — budget time for bug triage.
2. **Run each scenario from `Scenarios.tsx` individually** and confirm the expected agents fire and the expected HITL tasks / KPI alerts appear. Use `expected_outcome` in `scenarios.json` as the checklist.
3. **Reset-and-repeat twice** to confirm reproducibility with the LLM cache on and `DEMO_AS_OF_DATE` pinned. Compare KPI deltas across runs — they should match within rounding.
4. **Watch the trace feed pacing** — 8 agents × several tool calls each may outrun the 200-event cap in `frontend/src/hooks/useSSE.ts`; if needed, bump the cap or narrow the filter for the recording.
5. **Existing test suite** must still pass: `cd backend && pytest` and `cd frontend && npm test`.