.PHONY: help install seed dev test frontend up reset

help:
	@echo "Targets:"
	@echo "  install   — install backend + frontend deps"
	@echo "  seed      — run the deterministic seeder"
	@echo "  dev       — run FastAPI in reload mode"
	@echo "  frontend  — run the Vite dev server"
	@echo "  test      — run backend pytest suite"
	@echo "  up        — docker compose up --build"
	@echo "  reset     — POST /scenarios/reset"

install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install

seed:
	cd backend && python scripts/seed_all.py

dev:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && AGENT_OFFLINE_MODE=true pytest -q

up:
	docker compose up --build

reset:
	curl -X POST http://localhost:8000/api/v1/scenarios/reset \
	  -H "X-API-Key: $${DEMO_API_KEY:-demo-key-12345}"
