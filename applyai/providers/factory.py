"""Factory for AI Providers."""

import logging
from applyai.core.config import get_settings
from applyai.providers.base import AIProvider
from applyai.providers.null import NullProvider

logger = logging.getLogger(__name__)

def get_provider() -> AIProvider:
    """Return the configured AIProvider instance."""
    settings = get_settings()
    provider_name = settings.ai.provider

    if provider_name == "none":
        return NullProvider()
    
    if provider_name == "gemini":
        try:
            from applyai.providers.gemini import GeminiProvider
            return GeminiProvider(
                model=settings.ai.model,
                api_key=settings.api_key_for("gemini")
            )
        except ImportError:
            logger.warning("google-genai not installed. Falling back to NullProvider.")
            return NullProvider()

    if provider_name == "anthropic":
        try:
            from applyai.providers.anthropic import AnthropicProvider
            return AnthropicProvider(
                model=settings.ai.model,
                api_key=settings.api_key_for("anthropic")
            )
        except ImportError:
            logger.warning("anthropic not installed. Falling back to NullProvider.")
            return NullProvider()

    # Fallback
    return NullProvider()
