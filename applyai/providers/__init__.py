"""
applyai.providers — AI model provider abstraction layer.

V1 ships with NullProvider only (no API key required).
AnthropicProvider and GeminiProvider are implemented in Phase 3/4
when AI-dependent agent tasks are built.

Provider selection is configured in config/settings.yaml → ai.provider.
API keys come from .env only.

IMPORTANT: This layer is for the ApplyAI runtime application.
It has NO connection to the Antigravity IDE or its development agent session.
"""
