"""Pydantic schemas for job scoring output."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Recommendation(StrEnum):
    STRONG_YES = "strong_yes"
    YES = "yes"
    MAYBE = "maybe"
    NO = "no"


class ComponentScores(BaseModel):
    """
    Raw component scores returned by the LLM matcher (0–100 each).
    These are qualitative assessments — the LLM does NOT compute the final score.
    """

    technical_skills: float | None = None
    experience_compat: float | None = None
    education_compat: float | None = None
    location_work_mode: float | None = None
    experience_level: float | None = None
    project_relevance: float | None = None
    keyword_coverage: float | None = None


class InterviewPotentialFactors(BaseModel):
    """
    Factors contributing to the Interview Potential Score.

    DISCLAIMER: This is an internal experimental heuristic.
    It is NOT a prediction or probability of receiving an interview.
    It is based on observable profile factors only.
    """

    fit_score: float | None = None
    experience_compat: float | None = None
    project_relevance: float | None = None
    skill_alignment: float | None = None
    friction_penalty: float | None = None
    notes: str | None = None


class JobScoreOutput(BaseModel):
    """Full scoring output — combination of LLM qualitative assessment + Python aggregation."""

    # Deterministic Python result
    overall_score: float = Field(ge=0, le=100)
    recommendation: Recommendation

    # LLM-generated qualitative output
    component_scores: ComponentScores
    matching_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    # Experimental heuristic — clearly labeled
    interview_potential_score: float | None = Field(
        default=None,
        description=(
            "EXPERIMENTAL INTERNAL HEURISTIC. "
            "Not a prediction. Not a probability. "
            "Based on observable profile factors only."
        ),
    )
    interview_potential_factors: InterviewPotentialFactors | None = None

    # Provider metadata
    provider_used: str | None = None
    model_used: str | None = None
    scoring_status: str = "complete"
