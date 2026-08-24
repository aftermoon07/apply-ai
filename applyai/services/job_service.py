"""
JobService — orchestrates the job ingestion pipeline.

Pipeline flow for each job:
  RawJobInput
    → JobNormalizer.normalize()       [deterministic, no LLM]
    → JobRepository.find_duplicate()  [check all deduplication vectors]
    → If duplicate: emit job_duplicate_detected, return IngestionResult(is_duplicate=True)
    → JobRepository.create()          [persist to database]
    → EventService.emit_job_discovered()
    → Return IngestionResult(is_duplicate=False, status="inserted")

The service is idempotent: ingesting the same job twice returns a duplicate
result on the second call without inserting a new record.

No LLM provider is required for Phase 2. AI-based extraction (Phase 3)
will be added as a post-ingestion step that updates existing records.
"""

from __future__ import annotations

import logging
from typing import Sequence

from sqlalchemy.exc import IntegrityError

from applyai.models.job import Job
from applyai.processing.normalizer import JobNormalizer
from applyai.schemas.job import IngestionResult, NormalizedJob, RawJobInput
from applyai.services.event_service import EventService
from applyai.storage.jobs import JobRepository

logger = logging.getLogger(__name__)


class JobService:
    """
    Orchestrates job ingestion: normalize → deduplicate → persist → audit.

    Dependencies are injected to keep the service testable.
    """

    def __init__(
        self,
        repository: JobRepository | None = None,
        event_service: EventService | None = None,
        normalizer: JobNormalizer | None = None,
    ) -> None:
        self._repo = repository or JobRepository()
        self._events = event_service or EventService()
        self._normalizer = normalizer or JobNormalizer()

    # ── Single job ingestion ───────────────────────────────────────────────────

    async def ingest(self, raw: RawJobInput) -> IngestionResult:
        """
        Ingest a single job from a RawJobInput.

        Returns an IngestionResult indicating whether the job was newly
        inserted or detected as a duplicate.
        """
        # ── 1. Normalize ──────────────────────────────────────────────────────
        try:
            normalized = self._normalizer.normalize(raw)
        except Exception as exc:
            logger.error("Normalization failed for source %s: %s", raw.source, exc)
            await self._events.emit_job_ingestion_error(
                source=raw.source,
                error=f"Normalization failed: {exc}",
                payload={"raw_url": raw.job_url, "company": raw.company, "role": raw.role},
            )
            raise

        # ── 2. Check for duplicates ───────────────────────────────────────────
        existing = await self._repo.find_duplicate(normalized)

        if existing is not None:
            duplicate_reason = _determine_duplicate_reason(existing, normalized)
            logger.info(
                "Duplicate detected: %s (existing job_id=%s, reason=%s)",
                normalized.content_hash[:12],
                existing.id,
                duplicate_reason,
            )
            await self._events.emit_job_duplicate(
                existing_job_id=existing.id,
                content_hash=normalized.content_hash,
                source=normalized.source,
                duplicate_reason=duplicate_reason,
            )
            return IngestionResult(
                job_id=existing.id,
                source=existing.source,
                company=existing.company,
                role=existing.role,
                content_hash=normalized.content_hash,
                job_url=normalized.job_url,
                is_duplicate=True,
                duplicate_of=existing.id,
                status="duplicate",
                message=f"Duplicate of existing job {existing.id} ({duplicate_reason})",
            )

        # ── 3. Persist ────────────────────────────────────────────────────────
        try:
            job = await self._repo.create(normalized)
        except IntegrityError as exc:
            # Race condition: another process inserted the same job concurrently.
            # Treat as a duplicate.
            logger.warning(
                "IntegrityError on insert (concurrent duplicate): %s", exc
            )
            existing = await self._repo.get_by_content_hash(normalized.content_hash)
            if existing:
                return IngestionResult(
                    job_id=existing.id,
                    source=existing.source,
                    company=existing.company,
                    role=existing.role,
                    content_hash=normalized.content_hash,
                    job_url=normalized.job_url,
                    is_duplicate=True,
                    duplicate_of=existing.id,
                    status="duplicate",
                    message=f"Concurrent duplicate of job {existing.id}",
                )
            raise

        # ── 4. Emit discovery event ───────────────────────────────────────────
        await self._events.emit_job_discovered(
            job_id=job.id,
            source=job.source,
            company=job.company,
            role=job.role,
            content_hash=job.content_hash,
        )

        logger.info(
            "Job inserted: id=%s source=%s company=%r role=%r",
            job.id, job.source, job.company, job.role,
        )

        return IngestionResult(
            job_id=job.id,
            source=job.source,
            company=job.company,
            role=job.role,
            content_hash=job.content_hash,
            job_url=job.job_url,
            is_duplicate=False,
            status="inserted",
            message=f"Job inserted successfully (id={job.id})",
        )

    # ── Batch ingestion ────────────────────────────────────────────────────────

    async def ingest_batch(
        self, raw_inputs: list[RawJobInput]
    ) -> list[IngestionResult]:
        """
        Ingest a list of RawJobInputs.

        Processes each job independently. Errors on individual jobs are caught,
        logged, and included as error results — they do not abort the batch.

        Returns a list of IngestionResult, one per input.
        """
        results: list[IngestionResult] = []

        for i, raw in enumerate(raw_inputs):
            try:
                result = await self.ingest(raw)
                results.append(result)
            except Exception as exc:
                logger.error(
                    "Batch ingestion error at index %d (source=%s): %s",
                    i, raw.source, exc,
                )
                # Return a synthetic error result so callers can see which jobs failed
                results.append(
                    IngestionResult(
                        job_id="",
                        source=raw.source,
                        company=raw.company,
                        role=raw.role,
                        content_hash="",
                        job_url=raw.job_url,
                        is_duplicate=False,
                        status="error",
                        message=f"Ingestion error: {exc}",
                    )
                )

        # Emit batch summary event
        inserted = sum(1 for r in results if r.status == "inserted")
        duplicates = sum(1 for r in results if r.status == "duplicate")
        errors = sum(1 for r in results if r.status == "error")

        await self._events.emit(
            "job_ingestion_complete",
            entity_type="system",
            payload={
                "total": len(raw_inputs),
                "inserted": inserted,
                "duplicates": duplicates,
                "errors": errors,
            },
        )

        logger.info(
            "Batch complete: %d total, %d inserted, %d duplicates, %d errors",
            len(results), inserted, duplicates, errors,
        )

        return results

    # ── Read-only helpers ──────────────────────────────────────────────────────

    async def get_job(self, job_id: str) -> Job | None:
        """Get a Job by ID."""
        return await self._repo.get_by_id(job_id)

    async def list_jobs(
        self,
        *,
        source: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Job]:
        """List jobs with optional filters."""
        return await self._repo.list(source=source, status=status, limit=limit, offset=offset)

    async def count_jobs(
        self,
        *,
        source: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count jobs with optional filters."""
        return await self._repo.count(source=source, status=status)


# ── Helper ────────────────────────────────────────────────────────────────────


def _determine_duplicate_reason(existing: Job, normalized: NormalizedJob) -> str:
    """Return a human-readable reason for why a job was detected as a duplicate."""
    if existing.job_url and normalized.job_url and existing.job_url == normalized.job_url:
        return "url_match"
    if (
        existing.source_job_id
        and normalized.source_job_id
        and existing.source == normalized.source
        and existing.source_job_id == normalized.source_job_id
    ):
        return "source_id_match"
    return "content_hash_match"
