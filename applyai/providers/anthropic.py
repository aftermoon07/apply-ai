"""Anthropic provider using anthropic."""

from typing import Type, TypeVar
import json
from pydantic import BaseModel
import anthropic

from applyai.providers.base import AIProvider

T = TypeVar("T", bound=BaseModel)

class AnthropicProvider(AIProvider):
    def __init__(self, model: str, api_key: str):
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

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

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        response = await self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.0
        )
        return response.content[0].text
