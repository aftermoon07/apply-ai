"""
Abstract base class for AI providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar, Type
from dataclasses import dataclass
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

@dataclass
class ProviderContext:
    """Context for AI provider telemetry."""
    job_id: str | None = None
    agent_name: str | None = None


class AIProvider(ABC):
    """Abstract base class for all AI model providers."""

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        context: ProviderContext | None = None
    ) -> T:
        """
        Generate a structured response conforming to the provided Pydantic model.

        Args:
            system_prompt: High-level instructions (e.g. persona, output rules).
            user_prompt: The specific task data (e.g. job description, candidate profile).
            response_model: A Pydantic BaseModel subclass defining the output schema.
            context: Optional context for usage telemetry.

        Returns:
            An instance of the response_model.
        """
        ...
        
    @abstractmethod
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        context: ProviderContext | None = None
    ) -> str:
        """
        Generate a raw text response.
        
        Args:
            system_prompt: High-level instructions.
            user_prompt: The specific task data.
            context: Optional context for usage telemetry.
            
        Returns:
            The raw text string from the model.
        """
        ...
