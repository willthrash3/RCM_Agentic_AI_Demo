# ADR 001 — Architecture and Technology Choices

Status: Accepted
Date: 2026-04-15

## Context

The PRD requires a live-demo-ready RCM system with synthetic data, 8 real agents, a dashboard, and the ability to reset between back-to-back presentations.

## Decision

- **DuckDB** (single-file, in-process) as the data layer. Zero operational cost; sub-ms reads for the KPI queries; seed → query round-trip in <60 s; trivially resettable for the back-to-back demo requirement.
- **FastAPI + Pydantic v2** for the API layer. First-class async support for SSE and background tasks, automatic OpenAPI docs, and matches the team's Python stack.
- **LangGraph** for orchestration with a simple `StateGraph` over the 8 agents. Agent logic lives in plain async Python so unit tests don't require LangGraph.
- **Anthropic SDK direct** for LLM calls. Each agent defines a JSON-mode system prompt and a scripted fallback that executes when `AGENT_OFFLINE_MODE=true` or no API key is set. This means CI runs without network access and without burning budget.
- **React 18 + Vite + Tailwind + Recharts + TanStack Query** for the UI. Small, modern, and the right shape for the 10 page inventory.
- **SSE** (via sse-starlette) for the agent event stream. WebSockets overkill for uni-directional event push; SSE auto-reconnects in most browsers and is trivial to filter server-side.

## Consequences

- The demo runs on a laptop with `docker compose up`, no cloud dependencies.
- Because DuckDB is single-writer, high-concurrency scenarios would require a different backing store; this is explicitly out of scope per PRD §1.3.
- Offline-mode fallbacks keep the demo from crashing on flaky Wi-Fi, at the cost of somewhat less "live" reasoning in that mode. This is acceptable for the pre-sales use case.

## Alternatives Considered

- **SQLite instead of DuckDB** — rejected; analytics queries on AR aging are more ergonomic in DuckDB's SQL dialect and column store.
- **OpenAI-style function calling** — rejected in favor of structured JSON output because the agents each have a small, fixed tool set called deterministically from code. Structured JSON keeps the agent decision boundary crisp and testable.
- **WebSocket event bus** — rejected; SSE is lighter and the event flow is one-way.
