"""SQLAlchemy declarative base shared by all ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, String, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for all ApplyAI ORM models."""

    type_annotation_map: dict[type, Any] = {}
