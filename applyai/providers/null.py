"""Null AI Provider — used when ai.provider is 'none'."""

from __future__ import annotations

from typing import Type, TypeVar
from pydantic import BaseModel

from applyai.providers.base import AIProvider

T = TypeVar("T", bound=BaseModel)

class NullProvider(AIProvider):
    """
    A no-op provider that returns empty/default Pydantic objects.
    Used when no AI API key is configured.
    """

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T]
    ) -> T:
        """Return a default instance of the response model."""
        # Attempt to construct an instance with default values.
        # Note: This requires the model to have defaults for all fields,
        # or we might get a ValidationError. Our schemas in Phase 3
        # should have Optional/defaults for this to work smoothly.
        return response_model.model_construct()

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        return "# Dummy Generated Text\n\nThis is a placeholder since the AI provider is 'none'."
