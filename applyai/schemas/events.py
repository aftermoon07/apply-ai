"""Pydantic schemas for audit events."""

from __future__ import annotations

from pydantic import BaseModel, Field

from applyai.models.event import EventType


class AuditEventCreate(BaseModel):
    """Input model for creating an audit event."""

    event_type: EventType
    entity_type: str | None = None
    entity_id: str | None = None
    actor: str = "system"
    payload: dict | None = None
    error: str | None = None


class AuditEventRead(BaseModel):
    """Read model for returning audit events."""

    id: str
    event_type: str
    entity_type: str | None
    entity_id: str | None
    actor: str
    payload: dict | None
    error: str | None
    created_at: str

    model_config = {"from_attributes": True}
