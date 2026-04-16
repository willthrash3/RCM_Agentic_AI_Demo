# Agent Specifications

## Common Interface

Every agent inherits from `app.agents.base.BaseAgent` and implements a single async `run(input: AgentInput) → AgentOutput` method. The base class handles:

- Emitting `agent.started`, `agent.tool_call`, `agent.reasoning`, `agent.completed`, and `agent.escalated` events to the SSE stream.
- Persisting each event to `agent_event_log`.
- Writing HITL task rows with priority and recommended action.
- Calling Claude (via `app.agents.llm.run_llm`) with a JSON-schema prompt and a scripted offline fallback.

## Agents

### 1. Eligibility (`eligibility_agent`)
- Input: `patient_id`, optional `payer_id` and `service_date`.
- Calls `query_payer_eligibility` → mock 270/271.
- Escalates on: inactive coverage, out-of-network, portal errors.
- Output: verified flag, copay, deductible_remaining, oop_remaining, plan_type.

### 2. Coding (`coding_agent`)
- Input: `encounter_id`.
- Reads SOAP note, suggests CPT/ICD-10 with per-code confidence and rationale.
- Auto-approve if overall confidence ≥ 0.95 AND no documentation gaps AND passes validation.
- Otherwise creates coder-review HITL task.

### 3. Scrubbing (`scrubbing_agent`)
- Input: `claim_id`.
- Runs LCD/NCD, NCCI bundling, payer-specific rules, auth, TF checks.
- Releases if scrub_score ≥ 0.90 AND no critical edits; holds otherwise.

### 4. Tracking (`tracking_agent`)
- Runs daily. Polls `/mock/payer/.../claim/status` for Submitted claims.
- Flags underpayments (paid < 95% of contract allowable, variance > $25).

### 5. ERA Posting (`era_posting_agent`)
- Reads unposted ERAs, matches to claims, posts payments, routes exceptions.
- Write-offs > $50 require HITL approval.

### 6. Denial (`denial_agent`)
- Input: `denial_id`.
- Classifies root cause, renders appeal letter, auto-submits for Coding/Eligibility denials with deadline > 7 days.

### 7. Collections (`collections_agent`)
- Segments patient balances by propensity (High/Medium/Low/Hardship).
- Runs outreach per segment, triggers charity-care screening when indicated.

### 8. Analytics (`analytics_agent`)
- Computes the 8 dashboard KPIs.
- Raises `kpi.alert` SSE events when thresholds breach.
- Produces a narrative insight via the LLM summarizing recent deteriorations.

## Agent → Tools Matrix

Each agent file imports only the tools it needs from `app.tools`. See `app/tools/__init__.py` for the public surface.

## Event Bus

All events flow through `app.agents.event_bus.get_event_bus()` — a process-local pub/sub that:

1. Persists every event to `agent_event_log` (durable).
2. Fans out to every subscribed SSE client (live).

Clients subscribe via `GET /api/v1/events/stream` (optional `task_id` / `entity_type` / `entity_id` filters). The stream auto-keepalives every 15 s and clients auto-reconnect after 5 s drops.
