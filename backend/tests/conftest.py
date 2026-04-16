"""Pytest fixtures: fresh in-memory DuckDB and seeded data for every test run."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["AGENT_OFFLINE_MODE"] = "true"  # force offline/fallback for CI

API_KEY = "demo-key-12345"  # matches Settings.demo_api_key default


@pytest.fixture(scope="session", autouse=True)
def _tmp_db(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("db") / "test.duckdb"
    os.environ["DATABASE_PATH"] = str(path)
    from app.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]
    return path


@pytest.fixture(scope="session", autouse=True)
def _seed(_tmp_db) -> None:
    from app.database import get_connection, close_connection
    from app.db_schema import init_schema
    conn = get_connection()
    init_schema(conn)
    # Minimal: real seed_all may be expensive. We seed a tiny subset.
    from app.data.fixtures_loader import payers
    for p in payers():
        conn.execute(
            """INSERT OR REPLACE INTO payers VALUES (?,?,?,?,?,?,?,?,?)""",
            (p["payer_id"], p["payer_name"], p["payer_type"], p["payer_id_x12_fictional"],
             p["avg_days_to_pay"], p["denial_rate_baseline"], p["timely_filing_days"],
             p["fee_schedule_multiplier"], p["portal_mock_url"]),
        )
    yield
    close_connection()


@pytest.fixture(scope="session")
def api_client(_seed):
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers():
    return {"X-API-Key": API_KEY}
