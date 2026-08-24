"""
Abstract base class for AI providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class AIProvider(ABC):
    """Abstract base class for all AI model providers."""

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T]
    ) -> T:
        """
        Generate a structured response conforming to the provided Pydantic model.

        Args:
            system_prompt: High-level instructions (e.g. persona, output rules).
            user_prompt: The specific task data (e.g. job description, candidate profile).
            response_model: A Pydantic BaseModel subclass defining the output schema.

        Returns:
            An instance of the response_model.
        """
        ...
