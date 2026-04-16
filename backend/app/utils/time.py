"""Demo-aware date helper.

Reads DEMO_AS_OF_DATE from the environment so all agents and seed scripts share
the same logical "today" without drifting as the demo ages.
"""

from __future__ import annotations

import os
from datetime import date


def get_demo_today() -> date:
    """Return the demo's logical today, or real today if the env var is unset."""
    v = os.getenv("DEMO_AS_OF_DATE")
    return date.fromisoformat(v) if v else date.today()
