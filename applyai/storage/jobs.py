"""
Job storage repository — pure data access, no business logic.

This layer is the ONLY place that reads/writes the `jobs` and `job_skills` tables.
Business logic lives in services/job_service.py.
Deduplication logic lives in processing/deduplicator.py.

All methods are async to work with the SQLAlchemy async engine.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError

from applyai.core.database import get_session
from applyai.models.job import Job, JobSkill
from applyai.schemas.job import NormalizedJob

logger = logging.getLogger(__name__)


class JobRepository:
    """Async CRUD operations for Job and JobSkill records."""

    # ── Create ─────────────────────────────────────────────────────────────────

    async def create(self, normalized: NormalizedJob) -> Job:
        """
        Persist a normalized job to the database.

        Returns the created Job ORM instance.
        Raises IntegrityError if content_hash already exists (duplicate).
        """
        job = _normalized_to_orm(normalized)
        async with get_session() as session:
            session.add(job)
            # Flush to detect constraint violations before skills
            try:
                await session.flush()
            except IntegrityError:
                raise

            # Add skills
            for skill in normalized.required_skills:
                session.add(JobSkill(job_id=job.id, skill=skill, category="required"))
            for skill in normalized.preferred_skills:
                session.add(JobSkill(job_id=job.id, skill=skill, category="preferred"))

        return job

    # ── Read ───────────────────────────────────────────────────────────────────

    async def get_by_id(self, job_id: str) -> Job | None:
        """Get a Job by its UUID."""
        async with get_session() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            return result.scalar_one_or_none()

    async def get_by_content_hash(self, content_hash: str) -> Job | None:
        """Get a Job by its SHA-256 content hash."""
        async with get_session() as session:
            result = await session.execute(
                select(Job).where(Job.content_hash == content_hash)
            )
            return result.scalar_one_or_none()

    async def get_by_job_url(self, normalized_url: str) -> Job | None:
        """Get a Job by its normalized job URL."""
        async with get_session() as session:
            result = await session.execute(
                select(Job).where(Job.job_url == normalized_url)
            )
            return result.scalar_one_or_none()

    async def get_by_source_and_id(self, source: str, source_job_id: str) -> Job | None:
        """Get a Job by its (source, source_job_id) pair."""
        async with get_session() as session:
            result = await session.execute(
                select(Job).where(
                    and_(Job.source == source, Job.source_job_id == source_job_id)
                )
            )
            return result.scalar_one_or_none()

    async def list(
        self,
        *,
        source: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Job]:
        """
        List jobs with optional filters.

        Args:
            source: Filter by source identifier.
            status: Filter by pipeline status.
            limit: Maximum number of records.
            offset: Pagination offset.
        """
        stmt = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
        if source:
            stmt = stmt.where(Job.source == source)
        if status:
            stmt = stmt.where(Job.status == status)

        async with get_session() as session:
            result = await session.execute(stmt)
            return result.scalars().all()

    async def count(
        self,
        *,
        source: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count jobs with optional filters."""
        stmt = select(func.count(Job.id))
        if source:
            stmt = stmt.where(Job.source == source)
        if status:
            stmt = stmt.where(Job.status == status)

        async with get_session() as session:
            result = await session.execute(stmt)
            return result.scalar_one()

    # ── Update ─────────────────────────────────────────────────────────────────

    async def update_status(self, job_id: str, status: str) -> bool:
        """
        Update the pipeline status of a job.

        Returns True if a row was updated, False if job_id not found.
        """
        from applyai.models.base import utcnow

        async with get_session() as session:
            result = await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status=status, updated_at=utcnow().isoformat())
            )
            return result.rowcount > 0

    async def update_fields(self, job_id: str, **fields: Any) -> bool:
        """
        Update arbitrary fields on a Job record.

        Returns True if updated, False if not found.
        Only use for non-schema-changing updates (status, normalized_at, etc.).
        """
        from applyai.models.base import utcnow

        if not fields:
            return False

        fields["updated_at"] = utcnow().isoformat()

        async with get_session() as session:
            result = await session.execute(
                update(Job).where(Job.id == job_id).values(**fields)
            )
            return result.rowcount > 0

    # ── Deduplication helpers ──────────────────────────────────────────────────

    async def find_duplicate(self, normalized: NormalizedJob) -> Job | None:
        """
        Check all deduplication vectors and return an existing Job if found.

        Priority (matches deduplicator.py strategy):
          1. Canonical URL match
          2. Source + source_job_id match
          3. Content hash match
        """
        # 1. URL match
        if normalized.job_url:
            existing = await self.get_by_job_url(normalized.job_url)
            if existing:
                logger.debug("Duplicate found via URL: %s", normalized.job_url)
                return existing

        # 2. Source + external ID match
        if normalized.source_job_id:
            existing = await self.get_by_source_and_id(
                normalized.source, normalized.source_job_id
            )
            if existing:
                logger.debug(
                    "Duplicate found via source+id: %s/%s",
                    normalized.source, normalized.source_job_id,
                )
                return existing

        # 3. Content hash match
        existing = await self.get_by_content_hash(normalized.content_hash)
        if existing:
            logger.debug("Duplicate found via content hash: %s", normalized.content_hash[:12])
            return existing

        return None


# ── Mapping helpers ────────────────────────────────────────────────────────────


def _normalized_to_orm(normalized: NormalizedJob) -> Job:
    """Convert a NormalizedJob to a Job ORM instance."""
    from applyai.models.base import utcnow

    raw_data_json: str | None = None
    if normalized.raw_data:
        raw_data_json = json.dumps(normalized.raw_data, ensure_ascii=False)

    now_iso = utcnow().isoformat()

    return Job(
        source=normalized.source,
        source_job_id=normalized.source_job_id,
        company=normalized.company,
        role=normalized.role,
        location=normalized.location,
        work_mode=normalized.work_mode,
        employment_type=normalized.employment_type,
        salary_min=normalized.salary_min,
        salary_max=normalized.salary_max,
        salary_currency=normalized.salary_currency,
        salary_raw=normalized.salary_raw,
        salary_period=normalized.salary_period,
        experience_min_years=normalized.experience_min_years,
        experience_max_years=normalized.experience_max_years,
        experience_raw=normalized.experience_raw,
        education_required=normalized.education_required,
        job_description=normalized.job_description,
        job_url=normalized.job_url,
        source_url=normalized.source_url,
        date_discovered=normalized.date_discovered,
        date_posted=normalized.date_posted,
        status="new",
        content_hash=normalized.content_hash,
        raw_data=raw_data_json,
        normalized_at=now_iso,
        created_at=now_iso,
        updated_at=now_iso,
    )
