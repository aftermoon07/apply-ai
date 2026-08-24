"""Pydantic schemas for normalized job data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RawJobInput(BaseModel):
    """Unvalidated raw input from any job source — before normalization."""

    source: str
    raw_text: str | None = None
    raw_url: str | None = None
    raw_data: dict | None = None
    metadata: dict = Field(default_factory=dict)


class NormalizedJob(BaseModel):
    """Validated, normalized job representation — output of the Job Normalizer agent."""

    source: str
    company: str | None = None
    role: str | None = None
    location: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = "INR"
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    education_required: str | None = None
    job_description: str | None = None
    job_url: str | None = None
    source_url: str | None = None
    date_posted: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
