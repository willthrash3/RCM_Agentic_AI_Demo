"""Scenario endpoints — list, run, reset."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_api_key
from app.data.fixtures_loader import scenarios as load_scenarios
from app.database import locked
from app.db_schema import init_schema, reset_all_tables
from app.orchestrator.scenarios import run_scenario

router = APIRouter(prefix="/scenarios", tags=["scenarios"], dependencies=[Depends(require_api_key)])


@router.get("")
def list_scenarios() -> list[dict]:
    return [
        {
            "scenario_id": s["scenario_id"],
            "name": s["name"],
            "description": s["description"],
            "expected_outcome": s["expected_outcome"],
        }
        for s in load_scenarios()
    ]


@router.post("/run")
async def run(payload: dict) -> dict:
    scenario_id = payload.get("scenario_id")
    if not scenario_id:
        raise HTTPException(400, "scenario_id is required")
    try:
        return await run_scenario(scenario_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.post("/reset")
def reset() -> dict:
    """Reset DB back to seed state. PRD §10.2: <10s."""
    from scripts.seed_all import main as seed_main
    with locked() as conn:
        init_schema(conn)
        reset_all_tables(conn)
    seed_main()
    return {"status": "reset", "message": "Database reseeded"}
