"""Multi-model fallback chain with health tracking.

Provider order: Gemini (free) -> Anthropic -> OpenAI.
Each provider tracks consecutive failures and enters cooldown after 2+.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from time import time
from typing import Awaitable, Callable

import httpx

try:
    from intent import config as _cfg_intent  # type: ignore[import]

    _get_key = lambda name: getattr(_cfg_intent, name, "")  # noqa: E731
except ImportError:
    pass

# Try relative then direct import for config (matches codebase convention D-0202-1)
try:
    from . import _cfg  # type: ignore[import]
except ImportError:
    try:
        import config as _cfg  # type: ignore[import]
    except ImportError:
        _cfg = None  # type: ignore[assignment]


def _config_key(name: str) -> str:
    """Get a config value by attribute name, or fall back to empty string."""
    if _cfg is not None:
        return getattr(_cfg, name, "")
    return ""


logger = logging.getLogger("copilot.intent.chain")

# Regex to strip markdown code fences from LLM responses
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Remove markdown ```json ... ``` wrappers if present."""
    text = text.strip()
    m = _CODE_FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


# ---------------------------------------------------------------------------
# Health tracking
# ---------------------------------------------------------------------------


@dataclass
class ModelHealth:
    """Track provider health with cooldown after consecutive failures."""

    last_fail: float = 0
    consecutive_fails: int = 0
    cooldown_seconds: float = 300  # 5 min cooldown after 2+ failures

    def is_available(self) -> bool:
        if self.consecutive_fails < 2:
            return True
        return (time() - self.last_fail) > self.cooldown_seconds

    def record_failure(self) -> None:
        self.consecutive_fails += 1
        self.last_fail = time()

    def record_success(self) -> None:
        self.consecutive_fails = 0
        self.last_fail = 0


# ---------------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------------


@dataclass
class ModelProvider:
    name: str
    call: Callable[[str], Awaitable[str]]
    health: ModelHealth = field(default_factory=ModelHealth)


# ---------------------------------------------------------------------------
# FallbackChain
# ---------------------------------------------------------------------------


class FallbackChain:
    """Try providers in order, skip unhealthy ones, return first success."""

    def __init__(self, providers: list[ModelProvider]) -> None:
        self.providers = providers

    async def call(self, prompt: str) -> tuple[str | None, str]:
        """Try each provider in order.

        Returns ``(response_text, model_name)`` on success, or
        ``(None, "none")`` if every provider fails.
        """
        for provider in self.providers:
            if not provider.health.is_available():
                logger.debug("Skipping %s (in cooldown)", provider.name)
                continue
            try:
                raw = await provider.call(prompt)
                provider.health.record_success()
                return strip_code_fences(raw), provider.name
            except Exception:
                provider.health.record_failure()
                logger.warning(
                    "Provider %s failed (consecutive=%d)",
                    provider.name,
                    provider.health.consecutive_fails,
                    exc_info=True,
                )
        return None, "none"


# ---------------------------------------------------------------------------
# Provider implementations (async, httpx-based)
# ---------------------------------------------------------------------------

_TIMEOUT = httpx.Timeout(30.0)


async def call_gemini(prompt: str) -> str:
    """Call Gemini 2.0 Flash via REST API."""
    api_key = _config_key("GEMINI_API_KEY")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.0-flash:generateContent?key={api_key}"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def call_anthropic(prompt: str) -> str:
    """Call Claude Haiku via Anthropic Messages API."""
    api_key = _config_key("ANTHROPIC_API_KEY")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["content"][0]["text"]


async def call_openai(prompt: str) -> str:
    """Call GPT-4o-mini via OpenAI Chat Completions API."""
    api_key = _config_key("OPENAI_API_KEY")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-4o-mini",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_default_chain() -> FallbackChain:
    """Build the default fallback chain: Gemini -> Anthropic -> OpenAI.

    Only includes providers whose API key is configured.
    Gemini is first because Anthropic has zero credits currently.
    """
    providers: list[ModelProvider] = []

    if _config_key("GEMINI_API_KEY"):
        providers.append(ModelProvider(name="gemini", call=call_gemini))
    if _config_key("ANTHROPIC_API_KEY"):
        providers.append(ModelProvider(name="anthropic", call=call_anthropic))
    if _config_key("OPENAI_API_KEY"):
        providers.append(ModelProvider(name="openai", call=call_openai))

    if not providers:
        logger.warning("No LLM API keys configured — keyword fallback only")

    return FallbackChain(providers)
