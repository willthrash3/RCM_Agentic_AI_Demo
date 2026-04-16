"""DuckDB connection management."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import duckdb

from app.config import get_settings

_lock = threading.RLock()
_conn: duckdb.DuckDBPyConnection | None = None


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a process-wide DuckDB connection (thread-safe via module lock)."""
    global _conn
    with _lock:
        if _conn is None:
            path = get_settings().db_path
            _ensure_parent(path)
            _conn = duckdb.connect(str(path))
        return _conn


@contextmanager
def transaction() -> Iterator[duckdb.DuckDBPyConnection]:
    """Context manager that acquires the shared connection lock.

    DuckDB in a single-file scenario handles concurrency via a module lock —
    sufficient for the demo's single-process model.
    """
    with _lock:
        conn = get_connection()
        try:
            conn.begin()
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def close_connection() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
