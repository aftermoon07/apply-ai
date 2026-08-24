"""Gemini provider using google-genai."""

from typing import Type, TypeVar
import json
from pydantic import BaseModel
from google import genai
from google.genai import types

from applyai.providers.base import AIProvider

T = TypeVar("T", bound=BaseModel)

class GeminiProvider(AIProvider):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.client = genai.Client(api_key=api_key)

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T]
    ) -> T:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=response_model,
                temperature=0.0,
            )
        )
        return response_model.model_validate_json(response.text)
