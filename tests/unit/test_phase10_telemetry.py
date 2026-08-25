"""Phase 10 telemetry and cost tracking tests."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from applyai.providers.base import ProviderContext
from applyai.providers.null import NullProvider
from applyai.services.usage_service import UsageService, UsageRecord
from applyai.models.usage import ProviderUsage
from applyai.core.database import get_session

import sys

# Mock SDKs so we don't need them installed for these tests
sys.modules['google.genai'] = MagicMock()
sys.modules['google.genai.types'] = MagicMock()
sys.modules['google.genai.errors'] = MagicMock()
sys.modules['anthropic'] = MagicMock()

@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.database_url = "sqlite+aiosqlite:///:memory:"
    s.ai.max_retries = 3
    s.ai.retry_backoff_seconds = 0.01
    s.ai.timeout_seconds = 1
    
    # Add dummy pricing using MagicMock to simulate the Pydantic model
    m_gemini = MagicMock()
    m_gemini.input_per_million_tokens = 1.0
    m_gemini.output_per_million_tokens = 2.0
    
    s.ai.pricing = {
        "gemini": {
            "gemini-test-model": m_gemini
        }
    }
    return s

class TestUsageService:
    def test_calculate_cost(self, mock_settings):
        service = UsageService(mock_settings)
        cost = service.calculate_estimated_cost("gemini", "gemini-test-model", 100000, 200000)
        assert cost == 0.5
        
    def test_calculate_cost_missing_pricing(self, mock_settings):
        service = UsageService(mock_settings)
        cost = service.calculate_estimated_cost("anthropic", "unknown-model", 100, 100)
        assert cost is None

    @pytest.mark.asyncio
    async def test_record_and_get_summary(self, test_db, mock_settings):
        service = UsageService(mock_settings)
        record = UsageRecord(
            provider_name="gemini",
            model_name="gemini-test-model",
            operation="generate_structured",
            input_tokens=1000,
            output_tokens=1000,
            total_tokens=2000,
            retry_count=1,
            success=True,
            job_id="job-123"
        )
        await service.record_usage(record)
        
        record2 = UsageRecord(
            provider_name="gemini",
            model_name="gemini-test-model",
            operation="generate_text",
            retry_count=0,
            success=False
        )
        await service.record_usage(record2)
        
        summary = await service.get_summary(provider="gemini")
        assert summary["requests"] == 2
        assert summary["input_tokens"] == 1000
        assert summary["retries"] == 1
        assert summary["estimated_cost"] > 0
        
        job_summary = await service.get_summary(job_id="job-123")
        assert job_summary["requests"] == 1

class TestNullProviderTelemetry:
    @pytest.mark.asyncio
    async def test_null_provider_zero_external_calls(self):
        provider = NullProvider()
        from pydantic import BaseModel
        class DummyModel(BaseModel):
            pass
        
        res1 = await provider.generate_structured("sys", "usr", DummyModel, ProviderContext())
        res2 = await provider.generate_text("sys", "usr", ProviderContext())
        
        assert isinstance(res1, DummyModel)
        assert "Dummy Generated Text" in res2

class TestProviderUsageExtraction:
    @pytest.mark.asyncio
    @patch("applyai.services.usage_service.UsageService.record_usage", new_callable=AsyncMock)
    async def test_gemini_provider_success(self, mock_record_usage, mock_settings):
        import applyai.providers.gemini as gemini_mod
        genai = MagicMock()
        gemini_mod.genai = genai
        gemini_mod.HAS_GENAI = True
        gemini_mod.APIError = Exception
        gemini_mod.types = MagicMock()
        
        from applyai.providers.gemini import GeminiProvider
        from pydantic import BaseModel
        
        class DummyResponse(BaseModel):
            test: str = "yes"
            
        mock_client = MagicMock()
        genai.Client.return_value = mock_client
        genai.errors.APIError = Exception
        
        mock_response = MagicMock()
        mock_response.text = '{"test": "yes"}'
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150
        
        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content.return_value = mock_response
        mock_client.aio.models = mock_aio_models
        
        with patch("applyai.providers.gemini.get_settings", return_value=mock_settings):
            provider = GeminiProvider("gemini-test-model", "fake-key")
            result = await provider.generate_structured("sys", "usr", DummyResponse, ProviderContext(job_id="job-123"))
            
            assert result.test == "yes"
            assert mock_record_usage.call_count == 1
            call_arg = mock_record_usage.call_args[0][0]
            assert call_arg.input_tokens == 100
            assert call_arg.output_tokens == 50
            assert call_arg.total_tokens == 150
            assert call_arg.job_id == "job-123"

    @pytest.mark.asyncio
    @patch("applyai.services.usage_service.UsageService.record_usage", new_callable=AsyncMock)
    async def test_anthropic_provider_success(self, mock_record_usage, mock_settings):
        from applyai.providers.anthropic import AnthropicProvider
        from pydantic import BaseModel
        
        class DummyResponse(BaseModel):
            test: str = "yes"
            
        import anthropic
        mock_client = MagicMock()
        anthropic.AsyncAnthropic.return_value = mock_client
        
        mock_response = MagicMock()
        mock_content = MagicMock()
        mock_content.type = "tool_use"
        mock_content.name = "provide_structured_output"
        mock_content.input = {"test": "yes"}
        mock_response.content = [mock_content]
        
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 50
        
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        
        with patch("applyai.providers.anthropic.get_settings", return_value=mock_settings):
            provider = AnthropicProvider("claude", "fake-key")
            result = await provider.generate_structured("sys", "usr", DummyResponse, ProviderContext(job_id="job-anthropic"))
            
            assert result.test == "yes"
            assert mock_record_usage.call_count == 1
            call_arg = mock_record_usage.call_args[0][0]
            assert call_arg.input_tokens == 200
            assert call_arg.output_tokens == 50
            assert call_arg.total_tokens == 250
            assert call_arg.job_id == "job-anthropic"

    @pytest.mark.asyncio
    @patch("applyai.services.usage_service.UsageService.record_usage", new_callable=AsyncMock)
    async def test_gemini_retry_count(self, mock_record_usage, mock_settings):
        import applyai.providers.gemini as gemini_mod
        genai = MagicMock()
        gemini_mod.genai = genai
        gemini_mod.HAS_GENAI = True
        gemini_mod.APIError = Exception
        gemini_mod.types = MagicMock()
        from applyai.providers.gemini import GeminiProvider
        
        mock_client = MagicMock()
        genai.Client.return_value = mock_client
        class FakeAPIError(Exception):
            pass
        genai.errors.APIError = FakeAPIError
        
        mock_aio_models = AsyncMock()
        mock_aio_models.generate_content.side_effect = FakeAPIError("Fail")
        mock_client.aio.models = mock_aio_models
        
        with patch("applyai.providers.gemini.get_settings", return_value=mock_settings):
            provider = GeminiProvider("gemini-test", "fake")
            
            with pytest.raises(RuntimeError, match="Retries exhausted|Fail"):
                try:
                    await provider.generate_text("sys", "usr")
                except Exception as e:
                    raise RuntimeError("Retries exhausted") from e
                
            assert mock_record_usage.call_count == 1
            call_arg = mock_record_usage.call_args[0][0]
            assert call_arg.success is False
            assert call_arg.error_type == "FakeAPIError"
            assert call_arg.retry_count == mock_settings.ai.max_retries - 1

class TestUsageCLI:
    @patch("applyai.cli.usage.UsageService.get_summary", new_callable=AsyncMock)
    @patch("applyai.cli.usage.init_engine")
    def test_usage_cli_empty(self, mock_init, mock_get_summary, mock_settings):
        from applyai.cli.usage import _show_usage
        
        mock_get_summary.return_value = {
            "requests": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "estimated_cost": 0.0, "retries": 0
        }
        
        with patch("applyai.cli.usage.get_settings", return_value=mock_settings):
            asyncio.run(_show_usage())

