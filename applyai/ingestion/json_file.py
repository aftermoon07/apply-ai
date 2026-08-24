"""
JSON file batch ingestion adapter.

Handles bulk ingestion from a JSON file containing one or more job records.

Source ID: "json_file"
Permitted method: file_import

Expected JSON formats:
  - A JSON array of job objects:  [{"company": ..., "role": ...}, ...]
  - A single JSON object:         {"company": ..., "role": ...}
  - A JSON object with a "jobs" key:  {"jobs": [...]}

Each job object may contain any subset of RawJobInput fields.
Unknown fields are placed into `metadata` rather than causing a parse failure.

Phase 3 note: LPA/salary extraction and role classification are done by
the normalizer and agents — not here. This adapter only maps JSON keys
to RawJobInput fields.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from applyai.ingestion.base import JobSource
from applyai.schemas.job import RawJobInput

logger = logging.getLogger(__name__)

# ── JSON key mapping ───────────────────────────────────────────────────────────
# Maps common JSON field names from various sources to RawJobInput field names.
# Case-insensitive lookup is applied before this mapping.

_FIELD_MAP: dict[str, str] = {
    # Company
    "company": "company",
    "company_name": "company",
    "employer": "company",
    "organization": "company",

    # Role
    "role": "role",
    "title": "role",
    "job_title": "role",
    "position": "role",
    "designation": "role",

    # Location
    "location": "location",
    "job_location": "location",
    "city": "location",

    # Work mode
    "work_mode": "work_mode",
    "work_type": "work_mode",
    "workplace_type": "work_mode",
    "remote": "work_mode",  # bool — handled specially

    # Employment type
    "employment_type": "employment_type",
    "job_type": "employment_type",
    "contract_type": "employment_type",

    # Salary
    "salary": "salary_raw",
    "salary_raw": "salary_raw",
    "compensation": "salary_raw",
    "ctc": "salary_raw",
    "salary_min": "salary_min",
    "salary_max": "salary_max",
    "salary_currency": "salary_currency",
    "salary_period": "salary_period",

    # Experience
    "experience": "experience_raw",
    "experience_raw": "experience_raw",
    "experience_required": "experience_raw",
    "experience_min_years": "experience_min_years",
    "experience_max_years": "experience_max_years",
    "min_experience": "experience_min_years",
    "max_experience": "experience_max_years",

    # Education
    "education": "education_required",
    "education_required": "education_required",
    "qualification": "education_required",

    # Description
    "description": "job_description",
    "job_description": "job_description",
    "details": "job_description",
    "full_description": "job_description",

    # URLs
    "url": "job_url",
    "job_url": "job_url",
    "apply_url": "job_url",
    "source_url": "source_url",
    "link": "job_url",

    # Dates
    "date_posted": "date_posted",
    "posted_at": "date_posted",
    "posted_date": "date_posted",
    "posted_on": "date_posted",
    "published_at": "date_posted",

    # IDs
    "source_job_id": "source_job_id",
    "job_id": "source_job_id",
    "external_id": "source_job_id",
    "id": "source_job_id",

    # Skills
    "required_skills": "required_skills",
    "skills": "required_skills",
    "preferred_skills": "preferred_skills",
    "good_to_have": "preferred_skills",
}

# RawJobInput fields that accept list[str]
_LIST_FIELDS = {"required_skills", "preferred_skills"}

# RawJobInput fields that accept int
_INT_FIELDS = {"salary_min", "salary_max", "experience_min_years", "experience_max_years"}


class JsonFileSource(JobSource):
    """
    Ingests jobs from a JSON file.

    Accepts:
      - Array: [job1, job2, ...]
      - Single object: {company: ..., role: ...}
      - Wrapped: {jobs: [...]}
    """

    source_id = "json_file"
    permitted_method = "file_import"

    def parse(self, data: str | bytes | Path | dict | list) -> Iterator[RawJobInput]:
        """
        Parse JSON data into RawJobInput instances.

        Args:
            data: JSON string, bytes, Path to a JSON file, dict, or list.

        Yields:
            RawJobInput for each job record found.

        Raises:
            ValueError: If JSON is malformed or contains no job records.
        """
        records = _load_records(data)
        count = 0

        for i, record in enumerate(records):
            if not isinstance(record, dict):
                logger.warning("Skipping non-dict record at index %d: %r", i, record)
                continue
            raw = _record_to_raw_input(record)
            if raw is not None:
                count += 1
                yield raw

        if count == 0:
            logger.warning("JSON data contained no valid job records")


def _load_records(data: str | bytes | Path | dict | list) -> list[dict]:
    """Load a list of job record dicts from various input types."""
    if isinstance(data, Path):
        if not data.exists():
            raise FileNotFoundError(f"JSON file not found: {data}")
        raw_text = data.read_text(encoding="utf-8")
        parsed = json.loads(raw_text)
    elif isinstance(data, (str, bytes)):
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON: {exc}") from exc
    elif isinstance(data, (dict, list)):
        parsed = data
    else:
        raise TypeError(f"Unsupported input type: {type(data)}")

    # Unwrap {"jobs": [...]} envelope
    if isinstance(parsed, dict):
        if "jobs" in parsed and isinstance(parsed["jobs"], list):
            return parsed["jobs"]
        # Single job object
        return [parsed]

    if isinstance(parsed, list):
        return parsed

    raise ValueError(f"JSON must be an object or array, got: {type(parsed)}")


def _record_to_raw_input(record: dict[str, Any]) -> RawJobInput | None:
    """Map a dict record to a RawJobInput."""
    kwargs: dict[str, Any] = {
        "source": record.get("source", "json_file"),
        "date_discovered": datetime.now(timezone.utc).isoformat(),
        "metadata": {},
    }
    extra: dict[str, Any] = {}

    for key, value in record.items():
        canonical_key = _FIELD_MAP.get(key.lower())
        if canonical_key is None:
            # Unknown key → put in metadata
            extra[key] = value
            continue

        # Handle bool remote field
        if key.lower() == "remote" and isinstance(value, bool):
            kwargs["work_mode"] = "remote" if value else None
            continue

        # Type coercion for int fields
        if canonical_key in _INT_FIELDS:
            try:
                kwargs[canonical_key] = int(value) if value is not None else None
            except (TypeError, ValueError):
                extra[key] = value
            continue

        # Type coercion for list fields
        if canonical_key in _LIST_FIELDS:
            if isinstance(value, list):
                kwargs[canonical_key] = [str(v) for v in value]
            elif isinstance(value, str):
                # Comma-separated string
                kwargs[canonical_key] = [s.strip() for s in value.split(",") if s.strip()]
            continue

        # String fields
        if isinstance(value, (str, int, float, bool)) or value is None:
            kwargs[canonical_key] = str(value) if (value is not None and canonical_key not in _INT_FIELDS) else value
        else:
            extra[key] = value

    if extra:
        kwargs["metadata"] = {**kwargs.get("metadata", {}), **extra}

    try:
        return RawJobInput(**kwargs)
    except Exception as exc:
        logger.warning("Failed to construct RawJobInput from record: %s — %r", exc, record)
        return None
