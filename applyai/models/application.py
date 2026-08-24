"""Application lifecycle ORM models.

Full schema is defined now; V1 leaves most columns null.
Populated incrementally in V2/V3.

Lifecycle: Job → Application → ResumeVersion → Response → Interview
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from applyai.models.base import Base, utcnow


class Application(Base):
    """A job application — one per job per attempt."""

    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    # "draft" | "prepared" | "submitted" | "acknowledged" |
    # "interviewing" | "offer" | "rejected" | "withdrawn" | "ghosted"

    applied_at: Mapped[str | None] = mapped_column(String(30))  # ISO 8601
    platform: Mapped[str | None] = mapped_column(String(100))   # submission platform
    portal_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )
    updated_at: Mapped[str] = mapped_column(
        String(30),
        default=lambda: utcnow().isoformat(),
        onupdate=lambda: utcnow().isoformat(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    job: Mapped["Job"] = relationship("Job", back_populates="applications")  # type: ignore[name-defined]
    resume_versions: Mapped[list["ResumeVersion"]] = relationship(
        "ResumeVersion", back_populates="application", cascade="all, delete-orphan"
    )
    responses: Mapped[list["Response"]] = relationship(
        "Response", back_populates="application", cascade="all, delete-orphan"
    )
    interviews: Mapped[list["Interview"]] = relationship(
        "Interview", back_populates="application", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Application id={self.id!r} job_id={self.job_id!r} status={self.status!r}>"


class ResumeVersion(Base):
    """A tailored resume variant generated for a specific job."""

    __tablename__ = "resume_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("applications.id")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    format: Mapped[str | None] = mapped_column(
        String(20)
    )  # "markdown" | "latex" | "docx" | "html"
    content: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    qa_score: Mapped[float | None] = mapped_column()  # Resume QA agent score (V2)
    qa_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )

    application: Mapped["Application | None"] = relationship(
        "Application", back_populates="resume_versions"
    )

    def __repr__(self) -> str:
        return f"<ResumeVersion job_id={self.job_id!r} v={self.version}>"


class Response(Base):
    """A response received for an application (ack, rejection, interview invite, offer)."""

    __tablename__ = "responses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    response_type: Mapped[str | None] = mapped_column(
        String(30)
    )  # "ack" | "rejection" | "interview_invite" | "offer" | "other"
    received_at: Mapped[str | None] = mapped_column(String(30))
    channel: Mapped[str | None] = mapped_column(String(30))  # "email" | "portal" | "phone"
    raw_content: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )

    application: Mapped["Application"] = relationship("Application", back_populates="responses")

    def __repr__(self) -> str:
        return f"<Response type={self.response_type!r} app={self.application_id!r}>"


class Interview(Base):
    """An interview round associated with an application."""

    __tablename__ = "interviews"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    interview_type: Mapped[str | None] = mapped_column(
        String(30)
    )  # "phone" | "technical" | "system_design" | "hr" | "final"
    scheduled_at: Mapped[str | None] = mapped_column(String(30))
    completed_at: Mapped[str | None] = mapped_column(String(30))
    outcome: Mapped[str | None] = mapped_column(
        String(20)
    )  # "passed" | "failed" | "withdrew" | "pending"
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )

    application: Mapped["Application"] = relationship(
        "Application", back_populates="interviews"
    )

    def __repr__(self) -> str:
        return f"<Interview round={self.round} type={self.interview_type!r}>"
