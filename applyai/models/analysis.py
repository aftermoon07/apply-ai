"""JobAnalysis ORM model — stores LLM-generated job description analysis."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from applyai.models.base import Base, utcnow


class JobAnalysis(Base):
    """
    AI-generated analysis of a job description.

    One-to-one with Job. analysis_status tracks whether the LLM call succeeded,
    was skipped (no provider configured), or errored.
    """

    __tablename__ = "job_analysis"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # ── LLM output ────────────────────────────────────────────────────────────
    summary: Mapped[str | None] = mapped_column(Text)
    role_level: Mapped[str | None] = mapped_column(
        String(30)
    )  # "intern"|"junior"|"mid"|"senior"|"staff"|"principal"|"director"
    team_signals: Mapped[str | None] = mapped_column(Text)       # JSON array
    culture_signals: Mapped[str | None] = mapped_column(Text)    # JSON array
    red_flags: Mapped[str | None] = mapped_column(Text)          # JSON array
    green_flags: Mapped[str | None] = mapped_column(Text)        # JSON array
    key_responsibilities: Mapped[str | None] = mapped_column(Text)  # JSON array
    tech_stack: Mapped[str | None] = mapped_column(Text)         # JSON array
    domain: Mapped[str | None] = mapped_column(String(100))      # e.g. "fintech"

    # ── Pipeline metadata ─────────────────────────────────────────────────────
    analysis_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # "pending" | "complete" | "skipped" | "error"
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_used: Mapped[str | None] = mapped_column(String(50))
    model_used: Mapped[str | None] = mapped_column(String(100))
    analyzed_at: Mapped[str | None] = mapped_column(String(30))

    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    job: Mapped["Job"] = relationship("Job", back_populates="analysis")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<JobAnalysis job_id={self.job_id!r} status={self.analysis_status!r}>"
