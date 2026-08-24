"""
Pytest fixtures shared across all tests.

Test databases use temporary in-memory or tmp_path SQLite instances.
No real API keys or external services are required for any test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio

from applyai.core.config import invalidate_settings_cache
from applyai.core.database import create_all_tables, drop_all_tables, init_engine, reset_engine

# ── Paths ─────────────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CANDIDATE_DIR = FIXTURES_DIR / "sample_candidate"
EXAMPLE_CANDIDATE_DIR = Path(__file__).parent.parent / "candidate" / "example"


# ── Config isolation ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Ensure settings cache is fresh for each test."""
    invalidate_settings_cache()
    yield
    invalidate_settings_cache()


# ── Database fixtures ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_db(tmp_path: Path):
    """
    Provide a temporary SQLite test database with all tables created.
    Torn down after each test.
    """
    db_path = tmp_path / "test_apply_ai.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    init_engine(db_url, echo=False)
    await create_all_tables()

    yield db_url

    await drop_all_tables()
    reset_engine()


# ── Candidate fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def example_candidate_dir() -> Path:
    """Path to the committed synthetic example candidate profile."""
    return EXAMPLE_CANDIDATE_DIR


@pytest.fixture
def example_identity(example_candidate_dir: Path) -> dict:
    return json.loads((example_candidate_dir / "identity.json").read_text())


@pytest.fixture
def example_skill_levels(example_candidate_dir: Path) -> dict:
    return json.loads((example_candidate_dir / "skill_levels.json").read_text())


@pytest.fixture
def example_constraints(example_candidate_dir: Path) -> dict:
    return json.loads((example_candidate_dir / "constraints.json").read_text())
