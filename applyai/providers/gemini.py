"""Gemini provider using google-genai."""

from typing import Type, TypeVar
from pydantic import BaseModel
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from applyai.providers.base import AIProvider, ProviderContext
from applyai.core.config import get_settings

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

T = TypeVar("T", bound=BaseModel)

class GeminiProvider(AIProvider):
    def __init__(self, model: str, api_key: str):
        if not HAS_GENAI:
            raise RuntimeError("google-genai is not installed.")
        self.model = model
        self.client = genai.Client(api_key=api_key)
        self.settings = get_settings()
        self.retry_config = {
            "stop": stop_after_attempt(self.settings.ai.max_retries),
            "wait": wait_exponential(multiplier=self.settings.ai.retry_backoff_seconds, min=1, max=10),
            "retry": retry_if_exception_type(APIError),
        }

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        context: ProviderContext | None = None
    ) -> T:
        schema = response_model.model_json_schema()
        
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=schema,
        )

        from applyai.services.usage_service import UsageService, UsageRecord
        usage_service = UsageService(self.settings)

        async for attempt in AsyncRetrying(**self.retry_config):
            with attempt:
                import time
                start_time = time.monotonic()
                try:
                    # The GenAI SDK supports async via client.aio
                    response = await self.client.aio.models.generate_content(
                        model=self.model,
                        contents=user_prompt,
                        config=config,
                    )
                    latency = int((time.monotonic() - start_time) * 1000)
                    
                    if not response.text:
                        raise ValueError("Empty response from Gemini")
                        
                    result = response_model.model_validate_json(response.text)
                    
                    # Extract usage metadata
                    input_tokens = None
                    output_tokens = None
                    total_tokens = None
                    
                    if response.usage_metadata:
                        input_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
                        output_tokens = getattr(response.usage_metadata, "candidates_token_count", None)
                        total_tokens = getattr(response.usage_metadata, "total_token_count", None)

                    await usage_service.record_usage(UsageRecord(
                        provider_name="gemini",
                        model_name=self.model,
                        operation="generate_structured",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        retry_count=attempt.retry_state.attempt_number - 1,
                        latency_ms=latency,
                        success=True,
                        job_id=context.job_id if context else None,
                        agent_name=context.agent_name if context else None,
                    ))
                    
                    return result
                except Exception as e:
                    latency = int((time.monotonic() - start_time) * 1000)
                    if attempt.retry_state.attempt_number >= self.settings.ai.max_retries:
                        await usage_service.record_usage(UsageRecord(
                            provider_name="gemini",
                            model_name=self.model,
                            operation="generate_structured",
                            retry_count=attempt.retry_state.attempt_number - 1,
                            latency_ms=latency,
                            success=False,
                            error_type=type(e).__name__,
                            job_id=context.job_id if context else None,
                            agent_name=context.agent_name if context else None,
                        ))
                    raise
                
        raise RuntimeError("Retries exhausted.")

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        context: ProviderContext | None = None
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
        )

        from applyai.services.usage_service import UsageService, UsageRecord
        usage_service = UsageService(self.settings)

        async for attempt in AsyncRetrying(**self.retry_config):
            with attempt:
                import time
                start_time = time.monotonic()
                try:
                    response = await self.client.aio.models.generate_content(
                        model=self.model,
                        contents=user_prompt,
                        config=config,
                    )
                    latency = int((time.monotonic() - start_time) * 1000)
                    
                    input_tokens = None
                    output_tokens = None
                    total_tokens = None
                    
                    if response.usage_metadata:
                        input_tokens = getattr(response.usage_metadata, "prompt_token_count", None)
                        output_tokens = getattr(response.usage_metadata, "candidates_token_count", None)
                        total_tokens = getattr(response.usage_metadata, "total_token_count", None)

                    await usage_service.record_usage(UsageRecord(
                        provider_name="gemini",
                        model_name=self.model,
                        operation="generate_text",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        total_tokens=total_tokens,
                        retry_count=attempt.retry_state.attempt_number - 1,
                        latency_ms=latency,
                        success=True,
                        job_id=context.job_id if context else None,
                        agent_name=context.agent_name if context else None,
                    ))
                    
                    return response.text or ""
                except Exception as e:
                    latency = int((time.monotonic() - start_time) * 1000)
                    if attempt.retry_state.attempt_number >= self.settings.ai.max_retries:
                        await usage_service.record_usage(UsageRecord(
                            provider_name="gemini",
                            model_name=self.model,
                            operation="generate_text",
                            retry_count=attempt.retry_state.attempt_number - 1,
                            latency_ms=latency,
                            success=False,
                            error_type=type(e).__name__,
                            job_id=context.job_id if context else None,
                            agent_name=context.agent_name if context else None,
                        ))
                    raise
                
        raise RuntimeError("Retries exhausted.")
