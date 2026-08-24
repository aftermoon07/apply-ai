"""Initial schema — all ApplyAI V1 tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── jobs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("company", sa.String(255)),
        sa.Column("role", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("work_mode", sa.String(20)),
        sa.Column("employment_type", sa.String(30)),
        sa.Column("salary_min", sa.Integer()),
        sa.Column("salary_max", sa.Integer()),
        sa.Column("salary_currency", sa.String(10), server_default="INR"),
        sa.Column("experience_min_years", sa.Integer()),
        sa.Column("experience_max_years", sa.Integer()),
        sa.Column("education_required", sa.String(255)),
        sa.Column("job_description", sa.Text()),
        sa.Column("job_url", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("date_discovered", sa.String(30)),
        sa.Column("date_posted", sa.String(30)),
        sa.Column("status", sa.String(30), nullable=False, server_default="new"),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("raw_data", sa.Text()),
        sa.Column("normalized_at", sa.String(30)),
        sa.Column("created_at", sa.String(30)),
        sa.Column("updated_at", sa.String(30)),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_content_hash", "jobs", ["content_hash"])
    op.create_index("ix_jobs_source", "jobs", ["source"])

    # ── job_skills ────────────────────────────────────────────────────────────
    op.create_table(
        "job_skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill", sa.String(255), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
    )
    op.create_index("ix_job_skills_job_id", "job_skills", ["job_id"])

    # ── job_analysis ──────────────────────────────────────────────────────────
    op.create_table(
        "job_analysis",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("summary", sa.Text()),
        sa.Column("role_level", sa.String(30)),
        sa.Column("team_signals", sa.Text()),
        sa.Column("culture_signals", sa.Text()),
        sa.Column("red_flags", sa.Text()),
        sa.Column("green_flags", sa.Text()),
        sa.Column("key_responsibilities", sa.Text()),
        sa.Column("tech_stack", sa.Text()),
        sa.Column("domain", sa.String(100)),
        sa.Column("analysis_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text()),
        sa.Column("provider_used", sa.String(50)),
        sa.Column("model_used", sa.String(100)),
        sa.Column("analyzed_at", sa.String(30)),
        sa.Column("created_at", sa.String(30)),
    )
    op.create_index("ix_job_analysis_job_id", "job_analysis", ["job_id"])

    # ── candidate_snapshots ───────────────────────────────────────────────────
    op.create_table(
        "candidate_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot", sa.Text(), nullable=False),
        sa.Column("profile_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(30)),
    )

    # ── job_scores ────────────────────────────────────────────────────────────
    op.create_table(
        "job_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("candidate_snapshot_id", sa.String(36), sa.ForeignKey("candidate_snapshots.id")),
        sa.Column("technical_score", sa.Float()),
        sa.Column("experience_score", sa.Float()),
        sa.Column("education_score", sa.Float()),
        sa.Column("location_score", sa.Float()),
        sa.Column("level_score", sa.Float()),
        sa.Column("project_score", sa.Float()),
        sa.Column("keyword_score", sa.Float()),
        sa.Column("overall_score", sa.Float()),
        sa.Column("matching_skills", sa.Text()),
        sa.Column("missing_skills", sa.Text()),
        sa.Column("transferable_skills", sa.Text()),
        sa.Column("concerns", sa.Text()),
        sa.Column("reasons", sa.Text()),
        sa.Column("recommendation", sa.String(20)),
        sa.Column("confidence", sa.Float()),
        sa.Column("interview_potential_score", sa.Float()),
        sa.Column("interview_potential_factors", sa.Text()),
        sa.Column("scoring_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text()),
        sa.Column("provider_used", sa.String(50)),
        sa.Column("model_used", sa.String(100)),
        sa.Column("scored_at", sa.String(30)),
        sa.Column("created_at", sa.String(30)),
    )
    op.create_index("ix_job_scores_job_id", "job_scores", ["job_id"])

    # ── applications ──────────────────────────────────────────────────────────
    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("applied_at", sa.String(30)),
        sa.Column("platform", sa.String(100)),
        sa.Column("portal_url", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(30)),
        sa.Column("updated_at", sa.String(30)),
    )
    op.create_index("ix_applications_job_id", "applications", ["job_id"])

    # ── resume_versions ───────────────────────────────────────────────────────
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("format", sa.String(20)),
        sa.Column("content", sa.Text()),
        sa.Column("file_path", sa.Text()),
        sa.Column("qa_score", sa.Float()),
        sa.Column("qa_notes", sa.Text()),
        sa.Column("created_at", sa.String(30)),
    )

    # ── responses ─────────────────────────────────────────────────────────────
    op.create_table(
        "responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("response_type", sa.String(30)),
        sa.Column("received_at", sa.String(30)),
        sa.Column("channel", sa.String(30)),
        sa.Column("raw_content", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(30)),
    )

    # ── interviews ────────────────────────────────────────────────────────────
    op.create_table(
        "interviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("interview_type", sa.String(30)),
        sa.Column("scheduled_at", sa.String(30)),
        sa.Column("completed_at", sa.String(30)),
        sa.Column("outcome", sa.String(20)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(30)),
    )

    # ── contacts ──────────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company", sa.String(255)),
        sa.Column("name", sa.String(255)),
        sa.Column("role", sa.String(255)),
        sa.Column("linkedin_url", sa.Text()),
        sa.Column("email", sa.String(255)),
        sa.Column("is_referral", sa.Integer(), server_default="0"),
        sa.Column("source", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(30)),
    )

    # ── outreach ──────────────────────────────────────────────────────────────
    op.create_table(
        "outreach",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id", ondelete="SET NULL")),
        sa.Column("channel", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("subject", sa.Text()),
        sa.Column("body", sa.Text()),
        sa.Column("sent_at", sa.String(30)),
        sa.Column("replied_at", sa.String(30)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.String(30)),
    )

    # ── audit_events ──────────────────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(30)),
        sa.Column("entity_id", sa.String(36)),
        sa.Column("actor", sa.String(60), nullable=False, server_default="system"),
        sa.Column("payload", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.String(30), nullable=False),
    )
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("outreach")
    op.drop_table("contacts")
    op.drop_table("interviews")
    op.drop_table("responses")
    op.drop_table("resume_versions")
    op.drop_table("applications")
    op.drop_table("job_scores")
    op.drop_table("candidate_snapshots")
    op.drop_table("job_analysis")
    op.drop_table("job_skills")
    op.drop_table("jobs")
