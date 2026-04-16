# RCM Agentic AI Demo

An end-to-end interactive demo showcasing agentic AI across the ten stages of healthcare Revenue Cycle Management (RCM). Built with synthetic data, real LLM-powered agents, and a purpose-built dashboard that lets a live audience observe agents reasoning, acting, and handing off to human reviewers in real time.

See [`docs/PRD.md`](docs/PRD.md) for the full product requirements document.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Data | DuckDB + JSON fixtures |
| Agents | LangGraph + Claude `claude-sonnet-4-6` (Sonnet) / `claude-opus-4-6` (reasoning agents) |
| API | FastAPI + Pydantic v2 + SSE |
| UI | React 18 + TypeScript + Tailwind + Recharts |

## Quick Start

### Using Docker Compose (recommended)

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
docker compose up --build
```

- Backend: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173

### Local development

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e .
python scripts/seed_all.py
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## The 8 Agents

| # | Agent | Role |
|---|-------|------|
| 1 | Eligibility | Verifies insurance eligibility via mock 270/271 |
| 2 | Coding | Reads SOAP notes, suggests CPT/ICD-10 with confidence |
| 3 | Scrubbing | Pre-submission edit checks + rejection prediction |
| 4 | Tracking | Monitors submitted claims, detects underpayments |
| 5 | ERA Posting | Processes 835 ERA files, routes exceptions |
| 6 | Denial | Classifies denials, drafts & submits appeals |
| 7 | Collections | Patient balance outreach by propensity |
| 8 | Analytics | KPI monitoring, anomaly detection, forecasts |

## Demo Scenarios

Ready-to-run edge cases in `backend/app/data/fixtures/scenarios.json`:

- **Payer Rule Change** — BlueStar adds LCD restriction; 47 claims flagged
- **Denial Spike** — 18% Medicare denial spike; batch appeals drafted
- **Charge Lag Alert** — Orthopedics charge lag spikes to 5.2 days
- **Eligibility Gap** — 12 patients coverage lapsed pre-service
- **Underpayment Pattern** — Apex PPO underpaying 99215 by 12%
- **High-Value Denial Overturn** — $28,400 claim denied → appealed in 90 seconds

Trigger with `POST /scenarios/run` or via the Scenarios page in the UI.

## Reset Between Demos

```bash
curl -X POST http://localhost:8000/api/v1/scenarios/reset \
  -H "X-API-Key: demo-key-12345"
```

## Repository Layout

```
rcm-agentic-demo/
├── backend/
│   ├── app/
│   │   ├── agents/          # One module per agent
│   │   ├── api/             # FastAPI routers
│   │   ├── data/            # DuckDB schema + fixtures
│   │   ├── mock_payer/      # Mock 270/271/277/835 endpoints
│   │   ├── models/          # Pydantic models
│   │   ├── orchestrator/    # LangGraph workflow
│   │   └── tools/           # Agent tool implementations
│   └── scripts/             # Seeders + scenario injectors
├── frontend/
│   └── src/
│       ├── pages/           # 10 pages (Dashboard, Claims, etc.)
│       ├── components/
│       └── hooks/
├── docs/                    # PRD + ADRs
└── docker-compose.yml
```

## License

Demo / proprietary.
