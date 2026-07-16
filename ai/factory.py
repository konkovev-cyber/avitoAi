"""AI Provider Factory — creates the configured AI provider or returns None.

Usage:
    provider = get_ai_provider()   # returns AIProvider or None
    if provider:
        analysis = await provider.analyze_listing(...)
    else:
        # heuristic-only mode
        pass

Supported providers:
    wormsoft  — WormSoft агентские модели (рекомендуется, по себестоимости)
    openai    — OpenAI GPT-4o / GPT-4o-mini
    gemini    — Google Gemini 1.5 Flash / Pro
    anthropic — Anthropic Claude Haiku / Sonnet
"""

from __future__ import annotations

import logging
from typing import Optional

from ai.base import AIProvider

log = logging.getLogger("market_agent.ai.factory")

_PROVIDERS = ("wormsoft", "openai", "gemini", "anthropic")


def get_ai_provider(provider_name: str = "", **kwargs) -> Optional[AIProvider]:
    """Return configured AI provider or None if no AI is configured.

    Args:
        provider_name: "wormsoft" | "openai" | "gemini" | "anthropic" | ""
                       Empty = auto-detect from settings (wormsoft first)
        **kwargs: api_key, model, base_url overrides

    Returns:
        AIProvider instance or None (heuristics-only mode)
    """
    from config import settings

    name = (provider_name or settings.ai_provider or "").lower().strip()

    if not name:
        # Auto-detect: wormsoft first (cheapest/fastest), then others
        if settings.wormsoft_api_key:
            name = "wormsoft"
        elif settings.openai_api_key:
            name = "openai"
        elif settings.gemini_api_key:
            name = "gemini"
        elif settings.anthropic_api_key:
            name = "anthropic"
        else:
            log.debug("No AI provider configured — heuristics-only mode")
            return None

    # ── WormSoft ──────────────────────────────────────────────────────────────
    if name == "wormsoft":
        from ai.wormsoft_provider import WormSoftProvider
        key = kwargs.get("api_key") or settings.wormsoft_api_key
        model = kwargs.get("model") or settings.ai_model or "wormsoft/agent/low"
        base_url = kwargs.get("base_url") or settings.wormsoft_base_url
        if not key:
            log.warning("WormSoft selected but MA_WORMSOFT_API_KEY not set")
            return None
        log.info("AI provider: WormSoft (%s)", model)
        return WormSoftProvider(api_key=key, model=model, base_url=base_url)

    # ── OpenAI ────────────────────────────────────────────────────────────────
    if name == "openai":
        from ai.openai_provider import OpenAIProvider
        key = kwargs.get("api_key") or settings.openai_api_key
        model = kwargs.get("model") or settings.ai_model or "gpt-4o-mini"
        if not key:
            log.warning("OpenAI selected but MA_OPENAI_API_KEY not set")
            return None
        log.info("AI provider: OpenAI (%s)", model)
        return OpenAIProvider(api_key=key, model=model)

    # ── Gemini ────────────────────────────────────────────────────────────────
    if name == "gemini":
        from ai.gemini_provider import GeminiProvider
        key = kwargs.get("api_key") or settings.gemini_api_key
        model = kwargs.get("model") or settings.ai_model or "gemini-1.5-flash"
        if not key:
            log.warning("Gemini selected but MA_GEMINI_API_KEY not set")
            return None
        log.info("AI provider: Gemini (%s)", model)
        return GeminiProvider(api_key=key, model=model)

    # ── Anthropic ─────────────────────────────────────────────────────────────
    if name == "anthropic":
        from ai.anthropic_provider import AnthropicProvider
        key = kwargs.get("api_key") or settings.anthropic_api_key
        model = kwargs.get("model") or settings.ai_model or "claude-haiku-4-5"
        if not key:
            log.warning("Anthropic selected but MA_ANTHROPIC_API_KEY not set")
            return None
        log.info("AI provider: Anthropic Claude (%s)", model)
        return AnthropicProvider(api_key=key, model=model)

    log.warning("Unknown AI provider: '%s'. Supported: %s", name, _PROVIDERS)
    return None


def get_user_ai_provider(user_settings: dict) -> Optional[AIProvider]:
    """Get AI provider from per-user settings (DB row).

    Falls back to global config if user has no custom provider configured.
    """
    provider = user_settings.get("ai_provider", "")
    api_key = user_settings.get("ai_api_key", "")
    model = user_settings.get("ai_model", "")

    if provider and api_key:
        return get_ai_provider(provider_name=provider, api_key=api_key, model=model)

    return get_ai_provider()


def provider_display_name(provider_name: str) -> str:
    """Human-friendly display name for UI."""
    return {
        "wormsoft": "🦾 WormSoft AI",
        "openai": "🤖 OpenAI GPT",
        "gemini": "✨ Google Gemini",
        "anthropic": "🔮 Claude",
        "": "⚙️ Без AI (эвристики)",
    }.get(provider_name.lower(), provider_name)


def provider_model_hint(provider_name: str) -> str:
    """Default model suggestion for a provider shown in settings UI."""
    return {
        "wormsoft": "wormsoft/agent/low  или  wormsoft/agent/medium",
        "openai": "gpt-4o-mini  или  gpt-4o",
        "gemini": "gemini-1.5-flash  или  gemini-1.5-pro",
        "anthropic": "claude-haiku-4-5  или  claude-sonnet-4-5",
    }.get(provider_name.lower(), "")
