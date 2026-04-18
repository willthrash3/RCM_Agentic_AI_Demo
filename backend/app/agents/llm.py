"""LLM invocation with JSON-mode output and offline fallback.

All agents use Claude Sonnet for decision-making. Each call returns a parsed
JSON dict (the model is instructed to respond in JSON). The `_reasoning` key
is preserved for streaming to the UI.

If `AGENT_OFFLINE_MODE=true` or no API key is configured, we return the agent's
`fallback` payload so the demo can run without an Anthropic API key. This is
strictly for local/CI use — the real demo uses the LLM.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.agents.llm_cache import get_cached, put_cached
from app.config import get_settings

try:  # Optional import — allows CI / offline mode without the SDK installed
    from anthropic import AsyncAnthropic
except Exception:  # pragma: no cover
    AsyncAnthropic = None  # type: ignore[assignment]


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_block(text: str) -> dict[str, Any] | None:
    """Best-effort JSON extraction from an LLM response."""
    text = text.strip()
    # Try direct
    try:
        return json.loads(text)
    except Exception:
        pass
    # Fenced block
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
        try:
            return json.loads(text)
        except Exception:
            pass
    # Greedy-regex any JSON object
    m = _JSON_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


async def run_llm(
    system: str,
    user: str,
    fallback: dict | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if settings.agent_offline_mode or not settings.anthropic_api_key or AsyncAnthropic is None:
        # Offline: use the agent-provided fallback payload
        fb = dict(fallback or {})
        fb.setdefault("_reasoning", "Offline mode: returning scripted demo decision.")
        return fb
    effective_model = model or settings.claude_model
    # Check cache before making API call
    cached = get_cached(effective_model, system, user)
    if cached is not None:
        return cached

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    try:
        resp = await client.messages.create(
            model=effective_model,
            max_tokens=max_tokens or settings.agent_max_tokens,
            system=system + "\n\nRespond ONLY with valid JSON matching the requested schema.",
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        parsed = _parse_json_block(text)
        if parsed is None:
            # Fall back to scripted
            fb = dict(fallback or {})
            fb["_reasoning"] = f"LLM response was not valid JSON; using fallback. Raw: {text[:200]}"
            return fb
        put_cached(effective_model, system, user, parsed)
        return parsed
    except Exception as exc:  # pragma: no cover — demo robustness
        fb = dict(fallback or {})
        fb["_reasoning"] = f"LLM call failed: {exc}. Using fallback."
        return fb
