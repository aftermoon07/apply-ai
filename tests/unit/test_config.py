"""Unit tests for applyai.core.config — settings loading and validation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from applyai.core.config import (
    AIConfig,
    ScoringWeights,
    Settings,
    get_settings,
    invalidate_settings_cache,
    _build_settings,
)
from applyai.core.exceptions import ConfigError


# ── Settings loading ──────────────────────────────────────────────────────────


def test_get_settings_returns_settings_instance():
    settings = get_settings()
    assert isinstance(settings, Settings)


def test_get_settings_is_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_invalidate_settings_cache_allows_fresh_load():
    s1 = get_settings()
    invalidate_settings_cache()
    s2 = get_settings()
    # They are equal in value but different objects after cache clear
    assert s1.ai.provider == s2.ai.provider


def test_settings_default_provider_is_none():
    settings = get_settings()
    assert settings.ai.provider == "none"


def test_settings_default_model_is_empty():
    settings = get_settings()
    assert settings.ai.model == ""


def test_settings_loads_from_yaml(tmp_path: Path):
    """Verify YAML override of ai.provider is respected."""
    yaml_content = {
        "ai": {
            "provider": "none",
            "model": "",
        }
    }
    yaml_file = tmp_path / "settings.yaml"
    yaml_file.write_text(yaml.dump(yaml_content))

    settings = _build_settings(yaml_file)
    assert settings.ai.provider == "none"


def test_settings_missing_yaml_uses_defaults(tmp_path: Path):
    """Missing YAML file should fall back to Pydantic defaults."""
    nonexistent = tmp_path / "nonexistent.yaml"
    settings = _build_settings(nonexistent)
    assert settings.ai.provider == "none"
    assert settings.scoring.weights.technical_skills == pytest.approx(0.30)


# ── AI Config validation ──────────────────────────────────────────────────────


def test_ai_config_none_provider_no_model_required():
    cfg = AIConfig(provider="none", model="")
    assert cfg.provider == "none"


def test_ai_config_anthropic_requires_model():
    with pytest.raises(ValueError, match="ai.model must be set"):
        AIConfig(provider="anthropic", model="")


def test_ai_config_gemini_requires_model():
    with pytest.raises(ValueError, match="ai.model must be set"):
        AIConfig(provider="gemini", model="")


def test_ai_config_anthropic_with_model_valid():
    cfg = AIConfig(provider="anthropic", model="some-model-from-config")
    assert cfg.model == "some-model-from-config"


def test_ai_config_invalid_provider():
    with pytest.raises(ValueError, match="ai.provider must be one of"):
        AIConfig(provider="openai", model="gpt-4")


# ── Scoring weights ───────────────────────────────────────────────────────────


def test_default_weights_sum_to_one():
    weights = ScoringWeights()
    total = sum(weights.as_dict().values())
    assert abs(total - 1.0) < 1e-9


def test_weights_must_sum_to_one():
    with pytest.raises((ValueError, ConfigError)):
        ScoringWeights(
            technical_skills=0.50,
            experience_compat=0.20,
            education_compat=0.10,
            location_work_mode=0.10,
            experience_level=0.10,
            project_relevance=0.10,
            keyword_coverage=0.10,  # Total = 1.20 — invalid
        )


def test_weights_as_dict_has_all_keys():
    weights = ScoringWeights()
    d = weights.as_dict()
    expected_keys = {
        "technical_skills",
        "experience_compat",
        "education_compat",
        "location_work_mode",
        "experience_level",
        "project_relevance",
        "keyword_coverage",
    }
    assert set(d.keys()) == expected_keys


def test_custom_weights_sum_to_one():
    """Valid custom weight distribution should be accepted."""
    weights = ScoringWeights(
        technical_skills=0.40,
        experience_compat=0.20,
        education_compat=0.05,
        location_work_mode=0.10,
        experience_level=0.10,
        project_relevance=0.10,
        keyword_coverage=0.05,
    )
    total = sum(weights.as_dict().values())
    assert abs(total - 1.0) < 1e-9


# ── API key access ────────────────────────────────────────────────────────────


def test_api_key_for_unknown_provider_returns_empty():
    settings = get_settings()
    assert settings.api_key_for("unknown_provider") == ""


def test_api_key_for_anthropic_returns_env_value(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-anthropic")
    invalidate_settings_cache()
    settings = get_settings()
    assert settings.api_key_for("anthropic") == "test-key-anthropic"
    invalidate_settings_cache()


def test_api_key_for_gemini_returns_env_value(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-gemini")
    invalidate_settings_cache()
    settings = get_settings()
    assert settings.api_key_for("gemini") == "test-key-gemini"
    invalidate_settings_cache()
