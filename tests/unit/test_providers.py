import pytest

try:
    from applyai.providers.anthropic import AnthropicProvider
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    from applyai.providers.gemini import GeminiProvider, HAS_GENAI
except ImportError:
    HAS_GENAI = False

@pytest.mark.asyncio
async def test_anthropic_init():
    if not HAS_ANTHROPIC:
        pytest.skip("anthropic not installed")
    provider = AnthropicProvider(model="claude-3", api_key="test")
    assert provider.model == "claude-3"
    assert provider.retry_config is not None

@pytest.mark.asyncio
async def test_gemini_init():
    if not HAS_GENAI:
        pytest.skip("google-genai not installed")
    provider = GeminiProvider(model="gemini-2", api_key="test")
    assert provider.model == "gemini-2"
    assert provider.retry_config is not None
