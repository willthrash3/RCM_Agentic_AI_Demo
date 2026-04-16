"""FastAPI application entrypoint — RCM Agentic AI Demo backend."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agents, claims, denials, events, hitl, kpis, patients
from app.api import scenarios as scenarios_api
from app.config import get_settings
from app.database import close_connection, locked
from app.db_schema import init_schema
from app.mock_payer.router import router as mock_payer_router


settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("rcm-demo")


app = FastAPI(
    title="RCM Agentic AI Demo",
    version="1.0.0",
    description="Agentic AI across the 10 stages of healthcare Revenue Cycle Management.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Demo only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    with locked() as conn:
        init_schema(conn)
    logger.info("DuckDB initialized at %s", settings.db_path)


@app.on_event("shutdown")
def _shutdown() -> None:
    close_connection()


@app.get("/", tags=["health"])
def root() -> dict:
    return {
        "name": "RCM Agentic AI Demo",
        "version": "1.0.0",
        "docs": "/docs",
        "api": "/api/v1",
    }


@app.get("/healthz", tags=["health"])
def healthz() -> dict:
    return {"status": "ok"}


# API v1 mount ---------------------------------------------------------------
API_PREFIX = "/api/v1"
app.include_router(patients.router, prefix=API_PREFIX)
app.include_router(claims.router, prefix=API_PREFIX)
app.include_router(denials.router, prefix=API_PREFIX)
app.include_router(agents.router, prefix=API_PREFIX)
app.include_router(hitl.router, prefix=API_PREFIX)
app.include_router(kpis.router, prefix=API_PREFIX)
app.include_router(events.router, prefix=API_PREFIX)
app.include_router(scenarios_api.router, prefix=API_PREFIX)

# Mock payer is mounted at root (unauthenticated — internal use only)
app.include_router(mock_payer_router)
