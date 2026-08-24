"""
Application settings loader.

Loads configuration from two sources in priority order:
  1. Environment variables / .env file  (secrets and overrides)
  2. config/settings.yaml               (non-secret application config)

IMPORTANT: This module configures the ApplyAI Python runtime only.
           It has no relationship to the Antigravity IDE or its model session.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from applyai.core.exceptions import ConfigError

# Project root: two levels up from this file (applyai/core/config.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent


# ── Sub-config models ─────────────────────────────────────────────────────────


class AIConfig(BaseModel):
    """AI provider runtime configuration.

    The provider and model are set in config/settings.yaml.
    API keys come from .env.
    Neither is hardcoded in source.
    """

    provider: str = "none"  # "none" | "anthropic" | "gemini"
    model: str = ""  # validated against provider at startup
    thinking_enabled: bool = False
    thinking_budget_tokens: int = 8000
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    timeout_seconds: float = 60.0

    @model_validator(mode="after")
    def validate_provider(self) -> "AIConfig":
        allowed = {"none", "anthropic", "gemini"}
        if self.provider not in allowed:
            raise ValueError(f"ai.provider must be one of {allowed}, got: {self.provider!r}")
        if self.provider != "none" and not self.model:
            raise ValueError(
                f"ai.model must be set when ai.provider is {self.provider!r}. "
                "Set it in config/settings.yaml."
            )
        return self


class ScoringWeights(BaseModel):
    """Configurable scoring weights — must sum to exactly 1.0."""

    technical_skills: float = 0.30
    experience_compat: float = 0.20
    education_compat: float = 0.10
    location_work_mode: float = 0.10
    experience_level: float = 0.10
    project_relevance: float = 0.10
    keyword_coverage: float = 0.10

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "ScoringWeights":
        total = (
            self.technical_skills
            + self.experience_compat
            + self.education_compat
            + self.location_work_mode
            + self.experience_level
            + self.project_relevance
            + self.keyword_coverage
        )
        if abs(total - 1.0) > 1e-9:
            raise ConfigError(
                f"scoring.weights must sum to 1.0, got {total:.10f}. "
                "Check config/settings.yaml."
            )
        return self

    def as_dict(self) -> dict[str, float]:
        return {
            "technical_skills": self.technical_skills,
            "experience_compat": self.experience_compat,
            "education_compat": self.education_compat,
            "location_work_mode": self.location_work_mode,
            "experience_level": self.experience_level,
            "project_relevance": self.project_relevance,
            "keyword_coverage": self.keyword_coverage,
        }


class ScoringThresholds(BaseModel):
    strong_yes: float = 80.0
    yes_score: float = 65.0    # YAML key: "yes_score" (avoids YAML boolean coercion of bare 'yes')
    maybe: float = 45.0
    shortlist_min_score: float = 65.0


class InterviewPotentialConfig(BaseModel):
    fit_weight: float = 0.40
    experience_compat_weight: float = 0.20
    project_weight: float = 0.15
    skill_alignment_weight: float = 0.15
    friction_penalty_weight: float = 0.10


class ScoringConfig(BaseModel):
    weights: ScoringWeights = ScoringWeights()
    thresholds: ScoringThresholds = ScoringThresholds()
    interview_potential: InterviewPotentialConfig = InterviewPotentialConfig()


class IngestionConfig(BaseModel):
    default_source: str = "manual"
    max_batch_size: int = 100


class CandidateConfig(BaseModel):
    profile_dir: str = "candidate/private"
    example_dir: str = "candidate/example"
    allow_synthetic_fallback: bool = False
    require_complete_profile: bool = False


class AppMeta(BaseModel):
    log_level: str = "INFO"
    data_dir: str = "data"


# ── Main Settings ─────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """
    Root settings object.

    Secrets (API keys, DB URL) come from .env / environment variables.
    Structured config (ai, scoring, ingestion) comes from settings.yaml.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── From .env / environment ───────────────────────────────────────────────
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/apply_ai.db",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    candidate_profile_dir: str = Field(
        default="candidate/private",
        alias="CANDIDATE_PROFILE_DIR",
    )
    settings_path: str = Field(
        default="config/settings.yaml",
        alias="SETTINGS_PATH",
    )

    # ── From YAML (populated by from_yaml_and_env factory) ───────────────────
    ai: AIConfig = AIConfig()
    scoring: ScoringConfig = ScoringConfig()
    ingestion: IngestionConfig = IngestionConfig()
    candidate: CandidateConfig = CandidateConfig()
    app: AppMeta = AppMeta()

    def api_key_for(self, provider: str) -> str:
        """Return the API key for the given provider, or empty string if unset."""
        match provider:
            case "anthropic":
                return self.anthropic_api_key
            case "gemini":
                return self.google_api_key
            case _:
                return ""

    def resolved_profile_dir(self) -> Path:
        """Resolve the candidate profile directory against the project root."""
        # Env var takes precedence over yaml config
        dir_path = Path(self.candidate_profile_dir)
        if not dir_path.is_absolute():
            dir_path = PROJECT_ROOT / dir_path
        return dir_path

    def resolved_data_dir(self) -> Path:
        data_dir = Path(self.app.data_dir)
        if not data_dir.is_absolute():
            data_dir = PROJECT_ROOT / data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file; return empty dict if missing."""
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _build_settings(yaml_path: Path | None = None) -> Settings:
    """
    Build Settings by merging YAML config with environment variables.

    Environment variables always override YAML values.
    """
    resolved_yaml = yaml_path or (PROJECT_ROOT / "config" / "settings.yaml")
    raw = _load_yaml(resolved_yaml)

    try:
        ai_cfg = AIConfig(**raw.get("ai", {}))
        scoring_raw = raw.get("scoring", {})
        scoring_cfg = ScoringConfig(
            weights=ScoringWeights(**scoring_raw.get("weights", {})),
            thresholds=ScoringThresholds(**scoring_raw.get("thresholds", {})),
            interview_potential=InterviewPotentialConfig(
                **scoring_raw.get("interview_potential", {})
            ),
        )
        ingestion_cfg = IngestionConfig(**raw.get("ingestion", {}))
        candidate_cfg = CandidateConfig(**raw.get("candidate", {}))
        app_cfg = AppMeta(**raw.get("app", {}))
    except (ValueError, TypeError) as exc:
        raise ConfigError(f"Invalid settings.yaml: {exc}") from exc

    return Settings(
        ai=ai_cfg,
        scoring=scoring_cfg,
        ingestion=ingestion_cfg,
        candidate=candidate_cfg,
        app=app_cfg,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Call invalidate_settings_cache() in tests to reset between test cases.
    """
    yaml_path_env = os.environ.get("SETTINGS_PATH")
    yaml_path = Path(yaml_path_env) if yaml_path_env else None
    return _build_settings(yaml_path)


def invalidate_settings_cache() -> None:
    """Clear the settings cache. Use in tests only."""
    get_settings.cache_clear()
