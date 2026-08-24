"""
EventService — writes audit events to the database.

Single responsibility: persist AuditEvent rows.
Do not add business logic here — callers provide all event data.

Uses the existing AuditEvent ORM model and EventType enum.
This is the ONLY place that writes to the audit_events table.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from applyai.core.database import get_session
from applyai.models.event import AuditEvent, EventType

logger = logging.getLogger(__name__)


class EventService:
    """Async service for writing audit events."""

    async def emit(
        self,
        event_type: EventType | str,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor: str = "system",
        payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AuditEvent:
        """
        Persist an audit event.

        Args:
            event_type: EventType enum value or raw string.
            entity_type: Entity category ("job", "application", "system", etc.)
            entity_id: UUID of the relevant entity.
            actor: Who triggered the event ("system", "user", "agent:ingestion").
            payload: Optional dict of event context. JSON-serialized.
            error: Error message if event represents a failure.

        Returns:
            The persisted AuditEvent ORM instance.
        """
        payload_json: str | None = None
        if payload:
            try:
                payload_json = json.dumps(payload, ensure_ascii=False, default=str)
            except (TypeError, ValueError) as exc:
                logger.warning("Failed to serialize event payload: %s", exc)
                payload_json = json.dumps({"_serialization_error": str(exc)})

        event = AuditEvent(
            event_type=str(event_type),
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            payload=payload_json,
            error=error,
        )

        async with get_session() as session:
            session.add(event)

        logger.debug(
            "Event: %s entity=%s:%s",
            event_type, entity_type, entity_id,
        )

        return event

    async def emit_job_discovered(
        self,
        job_id: str,
        source: str,
        company: str | None = None,
        role: str | None = None,
        content_hash: str | None = None,
    ) -> AuditEvent:
        """Emit a job_discovered event."""
        return await self.emit(
            EventType.JOB_DISCOVERED,
            entity_type="job",
            entity_id=job_id,
            payload={
                "source": source,
                "company": company,
                "role": role,
                "content_hash": content_hash,
            },
        )

    async def emit_job_duplicate(
        self,
        existing_job_id: str,
        content_hash: str,
        source: str,
        duplicate_reason: str,
    ) -> AuditEvent:
        """Emit a job_duplicate_detected event."""
        return await self.emit(
            EventType.JOB_DUPLICATE_DETECTED,
            entity_type="job",
            entity_id=existing_job_id,
            payload={
                "source": source,
                "content_hash": content_hash,
                "duplicate_reason": duplicate_reason,
            },
        )

    async def emit_job_ingestion_error(
        self,
        source: str,
        error: str,
        payload: dict | None = None,
    ) -> AuditEvent:
        """Emit a job_ingestion_error event."""
        return await self.emit(
            EventType.JOB_INGESTION_ERROR,
            entity_type="job",
            actor="system",
            payload={"source": source, **(payload or {})},
            error=error,
        )
