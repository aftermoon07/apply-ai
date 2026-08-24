"""Phase 2 schema additions — new columns for source_job_id, salary_raw, salary_period, experience_raw.

Revision ID: 002_phase2_columns
Revises: 001_initial
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_phase2_columns"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_job_id for deterministic deduplication from platform adapters
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("source_job_id", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("salary_raw", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("salary_period", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("experience_raw", sa.Text(), nullable=True))
        batch_op.create_index("ix_jobs_source_job_id", ["source_job_id"])


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_source_job_id")
        batch_op.drop_column("experience_raw")
        batch_op.drop_column("salary_period")
        batch_op.drop_column("salary_raw")
        batch_op.drop_column("source_job_id")
