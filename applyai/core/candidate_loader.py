"""Shared candidate profile loader — single source of truth.

Public API:
    load_candidate_profile(settings) -> dict
        Loads the profile dict (backward-compatible).

    load_candidate_profile_with_source(settings) -> ProfileLoadResult
        Same load but also returns profile_source: "private" | "example".

    validate_candidate_profile(raw: dict) -> CandidateProfile
        Validates the raw dict through the Pydantic CandidateProfile schema.
        Raises ProfileValidationError on failure (privacy-safe messages).

    candidate_profile_hash(profile: dict) -> str
        SHA-256 hash of the profile — deterministic, key-order independent.
"""

import json
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


# ── Result type ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProfileLoadResult:
    """Result of loading a candidate profile, including source metadata."""
    profile: dict
    profile_source: Literal["private", "example"]


# ── Custom exception ──────────────────────────────────────────────────────────


class ProfileValidationError(ValueError):
    """Raised when a candidate profile fails Pydantic schema validation.

    Message is always privacy-safe: no filesystem paths, no raw field values.
    """


# ── Core loader ───────────────────────────────────────────────────────────────


def _load_json_files_from_dir(profile_dir: Path) -> dict:
    """Load all *.json files from a directory into a dict keyed by stem."""
    profile: dict = {}
    if profile_dir.exists():
        for f in sorted(profile_dir.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    profile[f.stem] = json.load(fp)
            except Exception as e:
                logger.warning("Failed to load candidate file %s: %s", f.name, e)
    return profile


def load_candidate_profile_with_source(settings) -> ProfileLoadResult:
    """
    Load candidate profile JSONs, returning profile dict AND source label.

    Privacy rules:
    - If allow_synthetic_fallback is False and the private dir is empty/missing → RuntimeError.
    - NEVER silently falls back without explicit allow_synthetic_fallback=True.
    - Error messages never expose absolute filesystem paths.
    """
    profile_dir = settings.resolved_profile_dir()

    if not profile_dir.exists() or not list(profile_dir.glob("*.json")):
        if not settings.candidate.allow_synthetic_fallback:
            raise RuntimeError(
                "No candidate profile found and 'allow_synthetic_fallback' is disabled. "
                "Populate your private profile or enable the fallback in config."
                # NOTE: path intentionally omitted to prevent accidental log exposure
            )
        logger.info("Private profile directory is empty. Falling back to example profile.")
        from applyai.core.config import PROJECT_ROOT
        example_dir = Path(settings.candidate.example_dir)
        if not example_dir.is_absolute():
            example_dir = PROJECT_ROOT / example_dir
        return ProfileLoadResult(
            profile=_load_json_files_from_dir(example_dir),
            profile_source="example",
        )

    return ProfileLoadResult(
        profile=_load_json_files_from_dir(profile_dir),
        profile_source="private",
    )


def load_candidate_profile(settings) -> dict:
    """
    Backward-compatible loader — returns only the profile dict.

    Callers that need the profile_source should use
    load_candidate_profile_with_source() instead.
    """
    return load_candidate_profile_with_source(settings).profile


# ── Validation ────────────────────────────────────────────────────────────────

# Required document keys that must be present for a complete profile.
REQUIRED_DOCUMENTS = {
    "identity",
    "education",
    "experience",
    "projects",
    "skills",
    "skill_levels",
    "achievements",
    "certifications",
    "portfolio",
    "preferences",
    "target_roles",
    "constraints",
}


def validate_candidate_profile(raw: dict):
    """
    Validate a raw candidate profile dict against the CandidateProfile Pydantic schema.

    Returns:
        CandidateProfile — the validated, typed profile object.

    Raises:
        ProfileValidationError — on any validation failure, with a privacy-safe message
            that never contains filesystem paths or raw sensitive field values.
    """
    from applyai.schemas.candidate import (
        CandidateProfile,
        Identity,
        Education,
        Experience,
        Projects,
        Skills,
        SkillLevels,
        Achievements,
        Certifications,
        Portfolio,
        Preferences,
        TargetRoles,
        Constraints,
    )
    from pydantic import ValidationError

    # Helper: strip private metadata keys before parsing
    def clean(d: dict) -> dict:
        return {k: v for k, v in d.items() if not k.startswith("_")}

    # Check required documents presence
    missing = REQUIRED_DOCUMENTS - set(raw.keys())
    if missing:
        raise ProfileValidationError(
            f"Candidate profile is missing required documents: {sorted(missing)}. "
            "Add the missing files to your profile directory."
        )

    # Validate each sub-document individually for clearer error messages
    sub_models = {
        "identity": Identity,
        "education": Education,
        "experience": Experience,
        "projects": Projects,
        "skills": Skills,
        "skill_levels": SkillLevels,
        "achievements": Achievements,
        "certifications": Certifications,
        "portfolio": Portfolio,
        "preferences": Preferences,
        "target_roles": TargetRoles,
        "constraints": Constraints,
    }

    parsed: dict = {}
    errors: list[str] = []
    for key, model_cls in sub_models.items():
        data = raw.get(key, {})
        try:
            parsed[key] = model_cls(**clean(data))
        except ValidationError as ve:
            # Surface field names and error types — NOT raw field values
            field_errors = "; ".join(
                f"{'.'.join(str(loc) for loc in e['loc'])}: {e['type']}"
                for e in ve.errors()
            )
            errors.append(f"{key}: {field_errors}")
        except Exception as exc:
            errors.append(f"{key}: unexpected error ({type(exc).__name__})")

    if errors:
        raise ProfileValidationError(
            "Candidate profile failed schema validation:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    try:
        profile = CandidateProfile(**parsed)
    except ValidationError as ve:
        field_errors = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['type']}"
            for e in ve.errors()
        )
        raise ProfileValidationError(
            f"CandidateProfile assembly failed: {field_errors}"
        )

    # Cross-document evidence validation
    _validate_cross_document_evidence(profile)

    return profile

def _validate_cross_document_evidence(profile):
    """
    Validates that evidence references actually exist in experience/projects,
    checks for duplicate IDs, and enforces skill-level evidence rules.
    Raises ProfileValidationError on failure.
    """
    errors = []

    # 1. Check for duplicate IDs
    exp_ids = []
    for exp in profile.experience.entries:
        exp_ids.append(exp.id)
    if len(exp_ids) != len(set(exp_ids)):
        errors.append("experience.json: contains duplicate IDs")
        
    proj_ids = []
    for proj in profile.projects.entries:
        proj_ids.append(proj.id)
    if len(proj_ids) != len(set(proj_ids)):
        errors.append("projects.json: contains duplicate IDs")

    exp_id_set = set(exp_ids)
    proj_id_set = set(proj_ids)

    # 2. Validate skill evidence
    for skill in profile.skill_levels.skills:
        # Check professional skill evidence rule
        if skill.level in ("strong", "working") and not skill.evidence:
            errors.append(f"skill_levels.json: skill '{skill.name}' ({skill.level}) requires evidence but none was provided")

        for ref in skill.evidence:
            if not ":" in ref:
                errors.append(f"skill_levels.json: invalid evidence reference format '{ref}'")
                continue
            
            ref_type, ref_id = ref.split(":", 1)
            
            if ref_type == "experience":
                if ref_id not in exp_id_set:
                    errors.append(f"skill_levels.json: invalid evidence reference \"{ref}\" (ID not found in experience)")
            elif ref_type == "project":
                if ref_id not in proj_id_set:
                    errors.append(f"skill_levels.json: invalid evidence reference \"{ref}\" (ID not found in projects)")
            else:
                errors.append(f"skill_levels.json: Unsupported evidence reference type: {ref_type}")

    if errors:
        raise ProfileValidationError(
            "Candidate profile failed cross-document validation:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


def profile_completeness(raw: dict) -> dict:
    """
    Return a summary of profile completeness without exposing sensitive values.

    Returns a dict with:
        present_documents: list[str]
        missing_documents: list[str]
        is_complete: bool
        skill_summary: dict  (counts by level, no actual skill names)
        evidence_metrics: dict (valid vs invalid evidence counts)
    """
    present = [k for k in REQUIRED_DOCUMENTS if k in raw]
    missing = sorted(REQUIRED_DOCUMENTS - set(raw.keys()))

    skill_summary: dict = {}
    valid_evidence = 0
    invalid_evidence = 0
    
    # Precompute valid IDs for completeness checking
    exp_ids = set()
    for exp in raw.get("experience", {}).get("entries", []):
        if "id" in exp:
            exp_ids.add(exp["id"])
            
    proj_ids = set()
    for proj in raw.get("projects", {}).get("entries", []):
        if "id" in proj:
            proj_ids.add(proj["id"])
            
    sl_raw = raw.get("skill_levels", {})
    skills_list = sl_raw.get("skills", [])
    for entry in skills_list:
        level = entry.get("level", "unknown")
        skill_summary[level] = skill_summary.get(level, 0) + 1
        
        evidence = entry.get("evidence", [])
        if isinstance(evidence, list):
            for ref in evidence:
                if not isinstance(ref, str) or ":" not in ref:
                    invalid_evidence += 1
                    continue
                ref_type, ref_id = ref.split(":", 1)
                if ref_type == "experience" and ref_id in exp_ids:
                    valid_evidence += 1
                elif ref_type == "project" and ref_id in proj_ids:
                    valid_evidence += 1
                else:
                    invalid_evidence += 1

    exp_count = len(raw.get("experience", {}).get("entries", []))
    edu_count = len(raw.get("education", {}).get("entries", []))
    proj_count = len(raw.get("projects", {}).get("entries", []))
    cert_count = len(raw.get("certifications", {}).get("entries", []))

    return {
        "present_documents": sorted(present),
        "missing_documents": missing,
        "is_complete": len(missing) == 0,
        "skill_counts_by_level": skill_summary,
        "experience_entries": exp_count,
        "education_entries": edu_count,
        "project_entries": proj_count,
        "certification_entries": cert_count,
        "evidence_metrics": {
            "valid": valid_evidence,
            "invalid": invalid_evidence,
        }
    }


# ── Hash ──────────────────────────────────────────────────────────────────────


def candidate_profile_hash(profile: dict) -> str:
    """Return a deterministic SHA-256 hash of the candidate profile.

    Properties:
    - Key-order independent (sort_keys=True)
    - Whitespace/formatting independent
    - Same logical content → same hash
    - Any meaningful data change → different hash
    """
    profile_json = json.dumps(profile, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(profile_json.encode()).hexdigest()
