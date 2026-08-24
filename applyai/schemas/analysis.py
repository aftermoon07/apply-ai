"""Pydantic schemas for job analysis output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class JobAnalysisOutput(BaseModel):
    """Structured output from the Job Analyzer agent."""

    summary: str | None = None
    role_level: str | None = None
    # "intern" | "junior" | "mid" | "senior" | "staff" | "principal" | "director"
    team_signals: list[str] = Field(default_factory=list)
    culture_signals: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    green_flags: list[str] = Field(default_factory=list)
    key_responsibilities: list[str] = Field(default_factory=list)
    tech_stack: list[str] = Field(default_factory=list)
    domain: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    # Provider metadata
    provider_used: str | None = None
    model_used: str | None = None
    analysis_status: str = "complete"
