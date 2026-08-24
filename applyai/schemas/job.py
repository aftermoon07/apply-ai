"""
Pydantic schemas for job data — raw input, normalized output, and ingestion results.

RawJobInput is designed to be fully source-agnostic.
No field is required except `source`.
Future adapters (Naukri, LinkedIn, Wellfound, Telegram, etc.) can omit fields
they cannot provide — the pipeline handles missing data gracefully.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class RawJobInput(BaseModel):
    """
    Unvalidated raw input from any job source — before normalization.

    All fields except `source` are optional because different sources
    provide different levels of structured data. Never populate fields
    with invented or inferred values.

    Field guidance:
      source_job_id : Platform-assigned job ID (e.g. Naukri job code, LinkedIn jk param).
                      Used for deterministic deduplication when available.
      raw_text      : Full unstructured job description text (manual paste, scraped HTML text).
      raw_url       : URL where the job was found — may be unnormalized.
      raw_data      : Structured payload from a source API (dict/JSON).
      metadata      : Arbitrary source-specific key-value pairs (e.g. scrape timestamp).
    """

    # ── Required ──────────────────────────────────────────────────────────────
    source: str = Field(
        description="Source identifier: 'manual' | 'json_file' | 'naukri' | 'linkedin' | ..."
    )

    # ── Source tracking ───────────────────────────────────────────────────────
    source_job_id: str | None = Field(
        default=None,
        description="Platform-assigned job ID. Used for deduplication when present.",
    )

    # ── Structured fields (may be extracted by adapter before passing in) ─────
    company: str | None = None
    role: str | None = Field(default=None, description="Job title / role name")
    location: str | None = None
    work_mode: str | None = Field(
        default=None,
        description="'remote' | 'hybrid' | 'onsite' | 'unknown'",
    )
    employment_type: str | None = Field(
        default=None,
        description="'full_time' | 'contract' | 'part_time' | 'internship' | 'unknown'",
    )

    # ── Compensation ──────────────────────────────────────────────────────────
    salary_raw: str | None = Field(
        default=None,
        description="Original salary text exactly as provided by the source. Never invent.",
    )
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = Field(
        default=None,
        description="'annual' | 'monthly' | 'lpa' | 'unknown'",
    )

    # ── Requirements ──────────────────────────────────────────────────────────
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    experience_raw: str | None = Field(
        default=None,
        description="Original experience string (e.g. '3-5 years'). Never invent.",
    )
    education_required: str | None = None

    # ── Content ───────────────────────────────────────────────────────────────
    job_description: str | None = Field(
        default=None,
        description="Full job description text. Primary content for analysis.",
    )
    raw_text: str | None = Field(
        default=None,
        description="Raw unstructured text from manual paste or file. "
        "Used when job_description is not separately extracted.",
    )

    # ── URLs ──────────────────────────────────────────────────────────────────
    job_url: str | None = Field(
        default=None,
        description="Canonical URL of the job posting. Normalized by url_normalizer.",
    )
    source_url: str | None = Field(
        default=None,
        description="URL where this job was discovered (may differ from job_url).",
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    date_posted: str | None = Field(
        default=None,
        description="Original date posted string from source. Parsed by date_parser.",
    )
    date_discovered: str | None = Field(
        default=None,
        description="ISO 8601 UTC datetime when this job was ingested. "
        "Set automatically if not provided.",
    )

    # ── Skills (pre-extracted by adapter, if available) ───────────────────────
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    # ── Raw payload ───────────────────────────────────────────────────────────
    raw_data: dict[str, Any] | None = Field(
        default=None,
        description="Full structured payload from source API. Stored for traceability.",
    )

    # ── Extensible metadata ───────────────────────────────────────────────────
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific key-value pairs (scrape timestamp, page rank, etc.).",
    )


class NormalizedJob(BaseModel):
    """
    Fully normalized job representation.

    Produced by deterministic preprocessing (processing/) on a RawJobInput.
    For Phase 2: all normalization is Python-only — no LLM involved.
    For Phase 3: the Job Normalizer agent will add semantic extraction
    for unstructured fields.
    """

    source: str
    source_job_id: str | None = None

    company: str | None = None
    role: str | None = None
    location: str | None = None
    work_mode: str | None = None
    employment_type: str | None = None

    # ── Compensation ──────────────────────────────────────────────────────────
    salary_raw: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = "INR"
    salary_period: str | None = None

    # ── Requirements ──────────────────────────────────────────────────────────
    experience_min_years: int | None = None
    experience_max_years: int | None = None
    experience_raw: str | None = None
    education_required: str | None = None

    # ── Content ───────────────────────────────────────────────────────────────
    job_description: str | None = None  # merged from raw_text + job_description

    # ── URLs (normalized) ─────────────────────────────────────────────────────
    job_url: str | None = None        # normalized canonical URL
    source_url: str | None = None

    # ── Dates (normalized to ISO 8601 UTC where parseable) ───────────────────
    date_posted: str | None = None
    date_discovered: str            = Field(
        description="UTC ISO 8601 timestamp of ingestion"
    )

    # ── Skills ────────────────────────────────────────────────────────────────
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)

    # ── Deduplication ─────────────────────────────────────────────────────────
    content_hash: str = Field(description="SHA-256 of canonical content for deduplication")

    # ── Raw payload ───────────────────────────────────────────────────────────
    raw_data: dict[str, Any] | None = None


class IngestionResult(BaseModel):
    """Result returned by JobService.ingest() for each processed job."""

    job_id: str
    source: str
    company: str | None
    role: str | None
    content_hash: str
    job_url: str | None
    is_duplicate: bool
    duplicate_of: str | None = Field(
        default=None,
        description="job_id of the existing record if this was a duplicate",
    )
    status: str  # "inserted" | "duplicate"
    message: str
