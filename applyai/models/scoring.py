"""
JobScore and CandidateSnapshot ORM models.

Design note on score computation:
  - Component scores (technical_score, experience_score, etc.) come from the LLM matcher.
  - overall_score is computed deterministically in Python using config-driven weights.
  - The LLM never returns the final numeric score.
  - interview_potential_score is an internal heuristic — never a prediction.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from applyai.models.base import Base, utcnow


class CandidateSnapshot(Base):
    """
    Immutable snapshot of the candidate profile at the time of scoring.

    Stored so that historical scores remain reproducible even as the
    candidate profile evolves over time.
    """

    __tablename__ = "candidate_snapshots"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    snapshot: Mapped[str] = mapped_column(Text, nullable=False)  # JSON of full profile
    profile_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )

    scores: Mapped[list["JobScore"]] = relationship("JobScore", back_populates="snapshot")

    def __repr__(self) -> str:
        return f"<CandidateSnapshot id={self.id!r} hash={self.profile_hash[:8]}...>"


class JobScore(Base):
    """
    Candidate vs. job match score.

    Component scores are LLM-generated qualitative assessments (0–100 each).
    overall_score is the deterministic Python weighted sum.
    interview_potential_score is a heuristic — labeled experimental in all output.
    """

    __tablename__ = "job_scores"

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
    candidate_snapshot_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("candidate_snapshots.id")
    )

    # ── Component scores (0–100 each) — LLM-assessed ─────────────────────────
    technical_score: Mapped[float | None] = mapped_column(Float)
    experience_score: Mapped[float | None] = mapped_column(Float)
    education_score: Mapped[float | None] = mapped_column(Float)
    location_score: Mapped[float | None] = mapped_column(Float)
    level_score: Mapped[float | None] = mapped_column(Float)
    project_score: Mapped[float | None] = mapped_column(Float)
    keyword_score: Mapped[float | None] = mapped_column(Float)

    # ── Aggregate score — deterministic Python weighted sum ───────────────────
    overall_score: Mapped[float | None] = mapped_column(Float)

    # ── Qualitative LLM output ────────────────────────────────────────────────
    matching_skills: Mapped[str | None] = mapped_column(Text)      # JSON array
    missing_skills: Mapped[str | None] = mapped_column(Text)       # JSON array
    transferable_skills: Mapped[str | None] = mapped_column(Text)  # JSON array
    concerns: Mapped[str | None] = mapped_column(Text)             # JSON array
    reasons: Mapped[str | None] = mapped_column(Text)              # JSON array
    recommendation: Mapped[str | None] = mapped_column(
        String(20)
    )  # "strong_yes" | "yes" | "maybe" | "no"
    confidence: Mapped[float | None] = mapped_column(Float)        # 0.0–1.0

    # ── Interview Potential (internal heuristic — not a prediction) ───────────
    interview_potential_score: Mapped[float | None] = mapped_column(Float)
    interview_potential_factors: Mapped[str | None] = mapped_column(Text)  # JSON

    # ── Pipeline metadata ─────────────────────────────────────────────────────
    scoring_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # "pending" | "complete" | "skipped" | "error"
    error_message: Mapped[str | None] = mapped_column(Text)
    provider_used: Mapped[str | None] = mapped_column(String(50))
    model_used: Mapped[str | None] = mapped_column(String(100))
    scored_at: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    job: Mapped["Job"] = relationship("Job", back_populates="score")  # type: ignore[name-defined]
    snapshot: Mapped["CandidateSnapshot | None"] = relationship(
        "CandidateSnapshot", back_populates="scores"
    )

    def __repr__(self) -> str:
        return (
            f"<JobScore job_id={self.job_id!r} "
            f"overall={self.overall_score} rec={self.recommendation!r}>"
        )
