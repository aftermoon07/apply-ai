"""Job and JobSkill ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from applyai.models.base import Base, utcnow


class Job(Base):
    """Normalized job posting — single source of truth for a discovered job."""

    __tablename__ = "jobs"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # ── Company & Role ────────────────────────────────────────────────────────
    company: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))

    # ── Location ──────────────────────────────────────────────────────────────
    location: Mapped[str | None] = mapped_column(String(255))
    work_mode: Mapped[str | None] = mapped_column(
        String(20)
    )  # "remote" | "hybrid" | "onsite" | "unknown"

    # ── Employment ────────────────────────────────────────────────────────────
    employment_type: Mapped[str | None] = mapped_column(
        String(30)
    )  # "full_time" | "contract" | "part_time" | "unknown"

    # ── Compensation ──────────────────────────────────────────────────────────
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(10), default="INR")

    # ── Requirements ──────────────────────────────────────────────────────────
    experience_min_years: Mapped[int | None] = mapped_column(Integer)
    experience_max_years: Mapped[int | None] = mapped_column(Integer)
    education_required: Mapped[str | None] = mapped_column(String(255))

    # ── Content ───────────────────────────────────────────────────────────────
    job_description: Mapped[str | None] = mapped_column(Text)
    job_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)

    # ── Dates ─────────────────────────────────────────────────────────────────
    date_discovered: Mapped[str | None] = mapped_column(String(30))  # ISO 8601
    date_posted: Mapped[str | None] = mapped_column(String(30))

    # ── Pipeline state ────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="new", index=True
    )
    # Allowed values:
    # "new" | "normalizing" | "normalized" | "analyzing" | "analyzed" |
    # "scoring" | "scored" | "shortlisted" | "applied" | "rejected" | "error"

    # ── Deduplication ─────────────────────────────────────────────────────────
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # SHA-256 of normalized content — computed deterministically in Python, no LLM

    # ── Raw data ──────────────────────────────────────────────────────────────
    raw_data: Mapped[str | None] = mapped_column(Text)  # JSON blob of original payload

    # ── Timestamps ────────────────────────────────────────────────────────────
    normalized_at: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[str] = mapped_column(String(30), default=lambda: utcnow().isoformat())
    updated_at: Mapped[str] = mapped_column(
        String(30),
        default=lambda: utcnow().isoformat(),
        onupdate=lambda: utcnow().isoformat(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    skills: Mapped[list["JobSkill"]] = relationship(
        "JobSkill", back_populates="job", cascade="all, delete-orphan"
    )
    analysis: Mapped["JobAnalysis | None"] = relationship(  # type: ignore[name-defined]
        "JobAnalysis", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    score: Mapped["JobScore | None"] = relationship(  # type: ignore[name-defined]
        "JobScore", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(  # type: ignore[name-defined]
        "Application", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id!r} role={self.role!r} company={self.company!r}>"


class JobSkill(Base):
    """Skills extracted from a job description."""

    __tablename__ = "job_skills"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # "required" | "preferred" | "nice_to_have"
    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0–1.0

    job: Mapped["Job"] = relationship("Job", back_populates="skills")

    def __repr__(self) -> str:
        return f"<JobSkill skill={self.skill!r} category={self.category!r}>"
