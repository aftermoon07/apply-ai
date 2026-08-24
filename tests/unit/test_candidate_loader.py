"""Tests for candidate_loader — privacy boundary and fallback enforcement."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from applyai.core.candidate_loader import load_candidate_profile, candidate_profile_hash


def make_settings(allow_fallback: bool, private_exists: bool, tmp_path: Path):
    """Build a mock settings object for testing."""
    private_dir = tmp_path / "private"
    example_dir = tmp_path / "example"

    if private_exists:
        private_dir.mkdir(parents=True)
        (private_dir / "identity.json").write_text(
            json.dumps({"schema_version": "1.0", "name": "Real Person"})
        )

    example_dir.mkdir(parents=True)
    (example_dir / "identity.json").write_text(
        json.dumps({"schema_version": "1.0", "name": "Alex Doe (Synthetic)"})
    )

    settings = MagicMock()
    settings.resolved_profile_dir.return_value = private_dir
    settings.candidate.allow_synthetic_fallback = allow_fallback
    settings.candidate.example_dir = str(example_dir)
    return settings


def test_private_profile_loaded_when_exists(tmp_path):
    settings = make_settings(allow_fallback=False, private_exists=True, tmp_path=tmp_path)
    profile = load_candidate_profile(settings)
    assert "identity" in profile
    assert profile["identity"]["name"] == "Real Person"


def test_strict_mode_raises_when_private_missing(tmp_path):
    settings = make_settings(allow_fallback=False, private_exists=False, tmp_path=tmp_path)
    with pytest.raises(RuntimeError, match="allow_synthetic_fallback"):
        load_candidate_profile(settings)


def test_fallback_allowed_uses_example(tmp_path):
    settings = make_settings(allow_fallback=True, private_exists=False, tmp_path=tmp_path)
    profile = load_candidate_profile(settings)
    assert "identity" in profile
    assert profile["identity"]["name"] == "Alex Doe (Synthetic)"


def test_error_message_does_not_expose_absolute_path(tmp_path):
    """Error message must not leak the actual filesystem path."""
    settings = make_settings(allow_fallback=False, private_exists=False, tmp_path=tmp_path)
    with pytest.raises(RuntimeError) as exc_info:
        load_candidate_profile(settings)
    error_msg = str(exc_info.value)
    # Must not contain the actual absolute path to the private directory
    assert str(tmp_path) not in error_msg


def test_candidate_profile_hash_is_deterministic(tmp_path):
    settings = make_settings(allow_fallback=True, private_exists=False, tmp_path=tmp_path)
    profile = load_candidate_profile(settings)
    h1 = candidate_profile_hash(profile)
    h2 = candidate_profile_hash(profile)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_candidate_profile_hash_changes_with_profile(tmp_path):
    settings = make_settings(allow_fallback=True, private_exists=False, tmp_path=tmp_path)
    p1 = {"identity": {"name": "Alex"}}
    p2 = {"identity": {"name": "Bob"}}
    assert candidate_profile_hash(p1) != candidate_profile_hash(p2)
