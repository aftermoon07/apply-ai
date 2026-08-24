"""Unit tests for database initialization and table creation."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from applyai.core.database import (
    create_all_tables,
    drop_all_tables,
    get_engine,
    get_session,
    init_engine,
    reset_engine,
)
from applyai.models import (
    AuditEvent,
    Base,
    Job,
    JobAnalysis,
    JobScore,
    Application,
    CandidateSnapshot,
)
from applyai.models.event import EventType


@pytest.fixture(autouse=True)
def clean_engine():
    """Reset engine state before and after each test."""
    reset_engine()
    yield
    reset_engine()


# ── Engine initialization ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_engine_creates_engine(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    init_engine(db_url)
    engine = get_engine()
    assert engine is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_init_engine_idempotent(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    init_engine(db_url)
    e1 = get_engine()
    init_engine(db_url)  # second call should be a no-op
    e2 = get_engine()
    assert e1 is e2
    await e1.dispose()


def test_get_engine_raises_before_init():
    with pytest.raises(RuntimeError, match="not initialized"):
        get_engine()


# ── Table creation ────────────────────────────────────────────────────────────

EXPECTED_TABLES = {
    "jobs",
    "job_skills",
    "job_analysis",
    "candidate_snapshots",
    "job_scores",
    "applications",
    "resume_versions",
    "responses",
    "interviews",
    "contacts",
    "outreach",
    "audit_events",
}


@pytest.mark.asyncio
async def test_create_all_tables_creates_expected_tables(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    init_engine(db_url)
    await create_all_tables()

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result.fetchall()}

    assert EXPECTED_TABLES.issubset(tables), (
        f"Missing tables: {EXPECTED_TABLES - tables}"
    )
    await engine.dispose()


@pytest.mark.asyncio
async def test_drop_all_tables_removes_tables(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    init_engine(db_url)
    await create_all_tables()
    await drop_all_tables()

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        )
        tables = {row[0] for row in result.fetchall()}

    assert len(tables) == 0
    await engine.dispose()


# ── Session and basic DB operations ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_context_manager(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    init_engine(db_url)
    await create_all_tables()

    async with get_session() as session:
        # Simple query to verify session works
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

    engine = get_engine()
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_raises_before_init():
    with pytest.raises(RuntimeError, match="not initialized"):
        async with get_session() as session:
            pass


# ── Audit event write ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_and_read_audit_event(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    init_engine(db_url)
    await create_all_tables()

    async with get_session() as session:
        event = AuditEvent(
            event_type=EventType.PIPELINE_STARTED,
            entity_type="system",
            entity_id=None,
            actor="test",
            payload='{"test": true}',
        )
        session.add(event)

    # Read back
    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(select(AuditEvent))
        events = result.scalars().all()

    assert len(events) == 1
    assert events[0].event_type == "pipeline_started"
    assert events[0].actor == "test"

    engine = get_engine()
    await engine.dispose()
