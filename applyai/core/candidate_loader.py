"""Shared candidate profile loader — single source of truth."""

import json
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_candidate_profile(settings) -> dict:
    """
    Load candidate profile JSONs into a flat dictionary keyed by filename stem.

    Privacy rules enforced here:
    - If allow_synthetic_fallback is False and the private dir is empty/missing, raises RuntimeError.
    - NEVER silently falls back to synthetic data without explicit allow_synthetic_fallback=True.

    Does NOT expose the profile directory path in user-visible error messages.
    """
    profile_dir = settings.resolved_profile_dir()

    if not profile_dir.exists() or not list(profile_dir.glob("*.json")):
        if not settings.candidate.allow_synthetic_fallback:
            raise RuntimeError(
                "No candidate profile found and 'allow_synthetic_fallback' is disabled. "
                "Populate your private profile or enable the fallback in config."
                # NOTE: intentionally omitting the absolute path to prevent accidental logging
            )
        logger.info("Private profile directory is empty. Falling back to example profile.")
        from applyai.core.config import PROJECT_ROOT
        profile_dir = Path(settings.candidate.example_dir)
        if not profile_dir.is_absolute():
            profile_dir = PROJECT_ROOT / profile_dir

    profile: dict = {}
    if profile_dir.exists():
        for f in sorted(profile_dir.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    profile[f.stem] = json.load(fp)
            except Exception as e:
                logger.warning("Failed to load candidate file %s: %s", f.name, e)

    return profile


def candidate_profile_hash(profile: dict) -> str:
    """Return a deterministic SHA-256 hash of the candidate profile."""
    profile_json = json.dumps(profile, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(profile_json.encode()).hexdigest()
