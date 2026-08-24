"""Anthropic provider using anthropic."""

from typing import Type, TypeVar
import json
from pydantic import BaseModel
import anthropic
import httpx
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from applyai.providers.base import AIProvider
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
        response_model: Type[T]
    ) -> T:
        schema = response_model.model_json_schema()
        
        tools = [
            {
                "name": "provide_structured_output",
                "description": "Provide the final structured output matching the schema.",
                "input_schema": schema
            }
        ]

        async for attempt in AsyncRetrying(**self.retry_config):
            with attempt:
                response = await self.client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    tools=tools,
                    tool_choice={"type": "tool", "name": "provide_structured_output"},
                    temperature=0.0
                )
                
                # The API will return a tool_use block
                for content in response.content:
                    if content.type == "tool_use" and content.name == "provide_structured_output":
                        return response_model.model_validate(content.input)
                
                raise ValueError("Anthropic API did not return the expected tool_use block.")
                
        raise RuntimeError("Retries exhausted.")

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        async for attempt in AsyncRetrying(**self.retry_config):
            with attempt:
                response = await self.client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.0
                )
                return response.content[0].text
                
        raise RuntimeError("Retries exhausted.")
