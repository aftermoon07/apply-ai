"""AuditEvent ORM model — immutable event log for all state transitions."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from applyai.models.base import Base, utcnow


class EventType(StrEnum):
    """All recognized event types. Add new types here before using them."""

    # Job pipeline
    JOB_DISCOVERED = "job_discovered"
    JOB_NORMALIZED = "job_normalized"
    JOB_DEDUPLICATED = "job_deduplicated"       # duplicate detected; not inserted
    JOB_ANALYZED = "job_analyzed"
    JOB_SCORED = "job_scored"
    JOB_SHORTLISTED = "job_shortlisted"
    JOB_REJECTED = "job_rejected"               # fell below threshold or hard constraint
    JOB_ERROR = "job_error"                     # pipeline error on a job

    # Resume
    RESUME_GENERATED = "resume_generated"

    # Application
    APPLICATION_PREPARED = "application_prepared"
    APPLICATION_SUBMITTED = "application_submitted"   # V3; requires human approval

    # Outreach
    OUTREACH_PREPARED = "outreach_prepared"
    OUTREACH_SENT = "outreach_sent"             # V3; requires human approval

    # Responses
    RESPONSE_RECEIVED = "response_received"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER_RECEIVED = "offer_received"

    # System
    PROFILE_VALIDATED = "profile_validated"
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_ERROR = "pipeline_error"


class AuditEvent(Base):
    """
    Immutable audit log entry.

    Records every significant state transition in the system.
    Events are written synchronously — failures are always captured.
    Rows are never updated or deleted.
    """

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(
        String(30), index=True
    )  # "job" | "application" | "outreach" | "interview" | "system"
    entity_id: Mapped[str | None] = mapped_column(
        String(36), index=True
    )  # UUID of the relevant entity
    actor: Mapped[str] = mapped_column(
        String(60), nullable=False, default="system"
    )  # "system" | "user" | "agent:<name>"

    payload: Mapped[str | None] = mapped_column(Text)   # JSON: relevant context
    error: Mapped[str | None] = mapped_column(Text)     # set if event represents a failure

    created_at: Mapped[str] = mapped_column(
        String(30), nullable=False, default=lambda: utcnow().isoformat(), index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEvent type={self.event_type!r} "
            f"entity={self.entity_type}:{self.entity_id} at={self.created_at!r}>"
        )
