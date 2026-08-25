"""Anthropic provider using anthropic."""

from typing import Type, TypeVar
import json
from pydantic import BaseModel
import anthropic
import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from applyai.providers.base import AIProvider, ProviderContext
from applyai.core.config import get_settings

T = TypeVar("T", bound=BaseModel)

class AnthropicProvider(AIProvider):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.settings = get_settings()
        timeout = self.settings.ai.timeout_seconds
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key, 
            timeout=httpx.Timeout(timeout)
        )
        self.retry_config = {
            "stop": stop_after_attempt(self.settings.ai.max_retries),
            "wait": wait_exponential(multiplier=self.settings.ai.retry_backoff_seconds, min=1, max=10),
            "retry": retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError)),
        }

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        context: ProviderContext | None = None
    ) -> T:
        schema = response_model.model_json_schema()
        
        tools = [
            {
                "name": "provide_structured_output",
                "description": "Provide the final structured output matching the schema.",
                "input_schema": schema
            }
        ]

        from applyai.services.usage_service import UsageService, UsageRecord
        usage_service = UsageService(self.settings)

        async for attempt in AsyncRetrying(**self.retry_config):
            with attempt:
                import time
                start_time = time.monotonic()
                try:
                    response = await self.client.messages.create(
                        model=self.model,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                        tools=tools,
                        tool_choice={"type": "tool", "name": "provide_structured_output"},
                        temperature=0.0
                    )
                    latency = int((time.monotonic() - start_time) * 1000)
                    
                    input_tokens = getattr(response.usage, "input_tokens", None) if hasattr(response, "usage") else None
                    output_tokens = getattr(response.usage, "output_tokens", None) if hasattr(response, "usage") else None
                    total_tokens = (input_tokens + output_tokens) if input_tokens is not None and output_tokens is not None else None

                    await usage_service.record_usage(UsageRecord(
                        provider_name="anthropic",
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

                    # The API will return a tool_use block
                    for content in response.content:
                        if content.type == "tool_use" and content.name == "provide_structured_output":
                            return response_model.model_validate(content.input)
                    
                    raise ValueError("Anthropic API did not return the expected tool_use block.")
                except Exception as e:
                    latency = int((time.monotonic() - start_time) * 1000)
                    if attempt.retry_state.attempt_number >= self.settings.ai.max_retries:
                        await usage_service.record_usage(UsageRecord(
                            provider_name="anthropic",
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
        from applyai.services.usage_service import UsageService, UsageRecord
        usage_service = UsageService(self.settings)

        async for attempt in AsyncRetrying(**self.retry_config):
            with attempt:
                import time
                start_time = time.monotonic()
                try:
                    response = await self.client.messages.create(
                        model=self.model,
                        system=system_prompt,
                        messages=[{"role": "user", "content": user_prompt}],
                        temperature=0.0
                    )
                    latency = int((time.monotonic() - start_time) * 1000)
                    
                    input_tokens = getattr(response.usage, "input_tokens", None) if hasattr(response, "usage") else None
                    output_tokens = getattr(response.usage, "output_tokens", None) if hasattr(response, "usage") else None
                    total_tokens = (input_tokens + output_tokens) if input_tokens is not None and output_tokens is not None else None

                    await usage_service.record_usage(UsageRecord(
                        provider_name="anthropic",
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

                    return response.content[0].text
                except Exception as e:
                    latency = int((time.monotonic() - start_time) * 1000)
                    if attempt.retry_state.attempt_number >= self.settings.ai.max_retries:
                        await usage_service.record_usage(UsageRecord(
                            provider_name="anthropic",
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
