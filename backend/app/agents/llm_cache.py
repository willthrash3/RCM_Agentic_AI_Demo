"""SHA-256-keyed file cache for LLM responses.

Three modes (set via LLM_CACHE_MODE env var):
- off     — no caching; every call hits the API (default)
- record  — call the API and save every response to disk
- replay  — return the cached response if it exists; otherwise fall through to API

Cache key: sha256(model + system_prompt + user_prompt).

Files are stored as <LLM_CACHE_DIR>/<sha256>.json.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _cache_dir() -> Path:
    d = Path(os.getenv("LLM_CACHE_DIR", "./data/llm_cache"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(model: str, system: str, user: str) -> str:
    h = hashlib.sha256(f"{model}\x00{system}\x00{user}".encode()).hexdigest()
    return h


def get_cached(model: str, system: str, user: str) -> dict[str, Any] | None:
    """Return cached response dict, or None if not present / cache is off."""
    mode = os.getenv("LLM_CACHE_MODE", "off")
    if mode not in ("replay",):
        return None
    key = _cache_key(model, system, user)
    path = _cache_dir() / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def put_cached(model: str, system: str, user: str, response: dict[str, Any]) -> None:
    """Save response to cache if mode is record."""
    mode = os.getenv("LLM_CACHE_MODE", "off")
    if mode not in ("record",):
        return
    key = _cache_key(model, system, user)
    path = _cache_dir() / f"{key}.json"
    try:
        path.write_text(json.dumps(response, default=str, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("LLM cache write failed for %s: %s", path, exc)
