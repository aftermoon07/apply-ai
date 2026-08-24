"""Gemini provider using google-genai."""

from typing import Type, TypeVar
from pydantic import BaseModel
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

from applyai.providers.base import AIProvider
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
        response_model: Type[T]
    ) -> T:
        schema = response_model.model_json_schema()
        
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=schema,
        )

        async for attempt in AsyncRetrying(**self.retry_config):
            with attempt:
                # The GenAI SDK supports async via client.aio
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=config,
                )
                
                if not response.text:
                    raise ValueError("Empty response from Gemini")
                    
                return response_model.model_validate_json(response.text)
                
        raise RuntimeError("Retries exhausted.")

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.0,
        )

        async for attempt in AsyncRetrying(**self.retry_config):
            with attempt:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=config,
                )
                return response.text or ""
                
        raise RuntimeError("Retries exhausted.")
