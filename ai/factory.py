"""AI Provider Factory — creates the configured AI provider or returns None.

Usage:
    provider = get_ai_provider()   # returns AIProvider or None
    if provider:
        analysis = await provider.analyze_listing(...)
    else:
        # heuristic-only mode
        pass
"""

from __future__ import annotations

import logging
from typing import Optional

from ai.base import AIProvider

log = logging.getLogger("market_agent.ai.factory")

_PROVIDERS = ("openai", "gemini", "anthropic")


def get_ai_provider(provider_name: str = "", **kwargs) -> Optional[AIProvider]:
    """Return configured AI provider or None if no AI is configured.

    Args:
        provider_name: "openai" | "gemini" | "anthropic" | "" (auto-detect from settings)
        **kwargs: api_key, model overrides (useful for per-user settings)

    Returns:
        AIProvider instance or None (heuristics-only mode)
    """
    from config import settings

    name = (provider_name or settings.ai_provider or "").lower().strip()

    if not name:
        # Auto-detect: pick first configured provider
        if settings.openai_api_key:
            name = "openai"
        elif settings.gemini_api_key:
            name = "gemini"
        elif settings.anthropic_api_key:
            name = "anthropic"
        else:
            log.debug("No AI provider configured — heuristics-only mode")
            return None

    if name == "openai":
        from ai.openai_provider import OpenAIProvider
        key = kwargs.get("api_key") or settings.openai_api_key
        model = kwargs.get("model") or settings.ai_model or "gpt-4o-mini"
        if not key:
            log.warning("OpenAI provider selected but MA_OPENAI_API_KEY not set")
            return None
        log.info("AI provider: OpenAI (%s)", model)
        return OpenAIProvider(api_key=key, model=model)

    if name == "gemini":
        from ai.gemini_provider import GeminiProvider
        key = kwargs.get("api_key") or settings.gemini_api_key
        model = kwargs.get("model") or settings.ai_model or "gemini-1.5-flash"
        if not key:
            log.warning("Gemini provider selected but MA_GEMINI_API_KEY not set")
            return None
        log.info("AI provider: Gemini (%s)", model)
        return GeminiProvider(api_key=key, model=model)

    if name == "anthropic":
        from ai.anthropic_provider import AnthropicProvider
        key = kwargs.get("api_key") or settings.anthropic_api_key
        model = kwargs.get("model") or settings.ai_model or "claude-haiku-4-5"
        if not key:
            log.warning("Anthropic provider selected but MA_ANTHROPIC_API_KEY not set")
            return None
        log.info("AI provider: Anthropic Claude (%s)", model)
        return AnthropicProvider(api_key=key, model=model)

    log.warning("Unknown AI provider: %s. Supported: %s", name, _PROVIDERS)
    return None


def get_user_ai_provider(user_settings: dict) -> Optional[AIProvider]:
    """Get AI provider from per-user settings stored in DB.

    Falls back to global settings if user has no custom provider.
    """
    provider = user_settings.get("ai_provider", "")
    api_key = user_settings.get("ai_api_key", "")
    model = user_settings.get("ai_model", "")

    if provider and api_key:
        return get_ai_provider(provider_name=provider, api_key=api_key, model=model)

    # Fall back to global config
    return get_ai_provider()


def provider_display_name(provider_name: str) -> str:
    """Human-friendly display name for a provider."""
    return {
        "openai": "🤖 OpenAI GPT",
        "gemini": "✨ Google Gemini",
        "anthropic": "🔮 Claude",
        "": "⚙️ Без AI (эвристики)",
    }.get(provider_name.lower(), provider_name)
