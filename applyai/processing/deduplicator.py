"""
Deterministic job deduplication — zero LLM usage.

Deduplication strategy (in priority order):

1. Canonical URL match
   If the job has a normalized job_url, look it up in the database.
   Same URL = same job. Most reliable signal.

2. Source + external job ID match
   If source_job_id is provided by the adapter, look up (source, source_job_id).
   Platform IDs are stable and unambiguous.

3. Content hash match (fallback)
   SHA-256 of a canonical content fingerprint:
     - normalized job_url (if present)
     - source + source_job_id (if present)
     - otherwise: normalized(company + role + location + first 500 chars of description)
   
   The fingerprint intentionally does NOT hash the entire raw text because
   minor whitespace/formatting changes would produce different hashes for
   the same job. The fingerprint is designed to be stable across reposts.

All hashing is performed in Python — no AI calls.
"""

from __future__ import annotations

import hashlib
import re

from applyai.schemas.job import NormalizedJob


# ── Canonical fingerprint ─────────────────────────────────────────────────────


def _clean(text: str | None) -> str:
    """Lower-case, collapse whitespace, strip."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def build_content_fingerprint(job: NormalizedJob) -> str:
    """
    Build a stable, canonical string that uniquely identifies a job posting.

    Priority:
      1. Canonical URL  →  most stable identifier
      2. source + source_job_id  →  platform-assigned ID
      3. company + role + location + first 500 chars of description  →  fuzzy fallback
    
    Returns a string suitable for hashing.
    """
    if job.job_url:
        return f"url::{job.job_url}"

    if job.source and job.source_job_id:
        return f"src_id::{_clean(job.source)}::{_clean(job.source_job_id)}"

    # Fallback: structured fields + truncated description
    company = _clean(job.company)
    role = _clean(job.role)
    location = _clean(job.location)
    desc_snippet = _clean(job.job_description or "")[:500]

    return f"content::{job.source}::{company}::{role}::{location}::{desc_snippet}"


def compute_content_hash(job: NormalizedJob) -> str:
    """
    Compute the SHA-256 hex digest of the canonical job fingerprint.

    This hash is stored in jobs.content_hash and used as the UNIQUE constraint
    for deduplication at the database level.
    """
    fingerprint = build_content_fingerprint(job)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def compute_hash_from_string(text: str) -> str:
    """Compute SHA-256 of an arbitrary string. Useful for candidate snapshots."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Deduplication key extraction ──────────────────────────────────────────────


class DeduplicationKeys:
    """
    Extracted deduplication keys for a normalized job.

    These are used by the storage layer to check for existing records
    before inserting a new one.
    """

    def __init__(self, job: NormalizedJob) -> None:
        self.content_hash: str = compute_content_hash(job)
        self.job_url: str | None = job.job_url
        self.source: str = job.source
        self.source_job_id: str | None = job.source_job_id

    def __repr__(self) -> str:
        return (
            f"<DeduplicationKeys hash={self.content_hash[:12]}... "
            f"url={self.job_url!r} src_id={self.source_job_id!r}>"
        )
