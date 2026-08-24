"""
JobNormalizer — orchestrates deterministic preprocessing of a RawJobInput.

Transforms a RawJobInput into a NormalizedJob by applying:
  1. URL normalization
  2. Date parsing
  3. Salary extraction (if salary_raw provided and salary_min/max not pre-extracted)
  4. Description consolidation (raw_text → job_description)
  5. Content hash computation for deduplication

All steps are deterministic — no LLM is called here.
Phase 3 will add LLM-based semantic extraction on top of this layer.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from applyai.processing.date_parser import parse_date_to_iso
from applyai.processing.deduplicator import compute_content_hash
from applyai.processing.salary_extractor import SalaryConfidence, extract_salary
from applyai.processing.url_normalizer import normalize_url
from applyai.schemas.job import NormalizedJob, RawJobInput

logger = logging.getLogger(__name__)


class JobNormalizer:
    """
    Stateless normalizer — creates a NormalizedJob from a RawJobInput.

    Usage:
        normalizer = JobNormalizer()
        normalized = normalizer.normalize(raw_input)
    """

    def normalize(self, raw: RawJobInput) -> NormalizedJob:
        """
        Normalize a RawJobInput into a NormalizedJob.

        Does not mutate the input. Returns a new NormalizedJob.
        """
        # ── 1. URLs ───────────────────────────────────────────────────────────
        job_url = normalize_url(raw.job_url)
        source_url = normalize_url(raw.source_url)

        # ── 2. Dates ──────────────────────────────────────────────────────────
        date_posted = parse_date_to_iso(raw.date_posted)
        date_discovered = (
            parse_date_to_iso(raw.date_discovered)
            or datetime.now(timezone.utc).isoformat()
        )

        # ── 3. Salary ─────────────────────────────────────────────────────────
        salary_min = raw.salary_min
        salary_max = raw.salary_max
        salary_currency = raw.salary_currency or "INR"
        salary_period = raw.salary_period
        salary_raw = raw.salary_raw

        if salary_raw and salary_min is None and salary_max is None:
            # Only extract if not pre-extracted by adapter
            result = extract_salary(salary_raw)
            if result.confidence not in (SalaryConfidence.FAILED,):
                salary_min = result.salary_min
                salary_max = result.salary_max
                salary_currency = result.currency or "INR"
                salary_period = result.period
                logger.debug(
                    "Salary extracted [%s]: min=%s max=%s %s %s",
                    result.confidence, salary_min, salary_max, salary_currency, salary_period
                )

        # ── 4. Job description ────────────────────────────────────────────────
        # Consolidate: job_description takes precedence; fall back to raw_text
        job_description = raw.job_description or raw.raw_text

        # ── 5. Build NormalizedJob ────────────────────────────────────────────
        normalized = NormalizedJob(
            source=raw.source,
            source_job_id=raw.source_job_id,
            company=raw.company,
            role=raw.role,
            location=raw.location,
            work_mode=_normalize_work_mode(raw.work_mode),
            employment_type=_normalize_employment_type(raw.employment_type),
            salary_raw=salary_raw,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            salary_period=salary_period,
            experience_min_years=raw.experience_min_years,
            experience_max_years=raw.experience_max_years,
            experience_raw=raw.experience_raw,
            education_required=raw.education_required,
            job_description=job_description,
            job_url=job_url,
            source_url=source_url,
            date_posted=date_posted,
            date_discovered=date_discovered,
            required_skills=raw.required_skills,
            preferred_skills=raw.preferred_skills,
            raw_data=raw.raw_data,
            content_hash="",  # placeholder — computed below
        )

        # ── 6. Compute content hash ────────────────────────────────────────────
        content_hash = compute_content_hash(normalized)
        normalized = normalized.model_copy(update={"content_hash": content_hash})

        return normalized


def _normalize_work_mode(value: str | None) -> str | None:
    """Normalize work mode to canonical values."""
    if not value:
        return None
    mapping = {
        "remote": "remote",
        "work from home": "remote",
        "wfh": "remote",
        "full remote": "remote",
        "hybrid": "hybrid",
        "onsite": "onsite",
        "on-site": "onsite",
        "on site": "onsite",
        "office": "onsite",
        "in-office": "onsite",
        "in office": "onsite",
    }
    return mapping.get(value.lower().strip(), value.lower().strip() or None)


def _normalize_employment_type(value: str | None) -> str | None:
    """Normalize employment type to canonical values."""
    if not value:
        return None
    mapping = {
        "full_time": "full_time",
        "full time": "full_time",
        "fulltime": "full_time",
        "permanent": "full_time",
        "contract": "contract",
        "contractor": "contract",
        "contractual": "contract",
        "part_time": "part_time",
        "part time": "part_time",
        "parttime": "part_time",
        "internship": "internship",
        "intern": "internship",
        "trainee": "internship",
        "freelance": "contract",
    }
    return mapping.get(value.lower().strip(), value.lower().strip() or None)
