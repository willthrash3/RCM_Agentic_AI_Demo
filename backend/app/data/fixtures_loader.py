"""Loader for JSON fixture files shipped with the backend."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@lru_cache(maxsize=32)
def load_fixture(name: str) -> Any:
    """Load a fixture JSON file by base name (without extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def cpt_codes() -> list[dict]:
    return load_fixture("cpt_codes")


def icd10_codes() -> list[dict]:
    return load_fixture("icd10_codes")


def carc_rarc() -> dict:
    return load_fixture("carc_rarc")


def payers() -> list[dict]:
    return load_fixture("payers")


def soap_templates() -> list[dict]:
    return load_fixture("soap_note_templates")


def payer_edit_rules() -> dict:
    return load_fixture("payer_edit_rules")


def appeal_templates() -> dict:
    return load_fixture("appeal_templates")


def scenarios() -> list[dict]:
    return load_fixture("scenarios")
