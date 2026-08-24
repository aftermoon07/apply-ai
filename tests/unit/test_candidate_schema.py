"""
Unit tests for candidate profile schemas.

Tests:
  - All example JSON files are valid (parseable, no truncation)
  - Pydantic models parse example data without errors
  - Skill level taxonomy is correct
  - constraints.json defaults are all null (placeholder policy)
  - Skill evidence format validation
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from applyai.schemas.candidate import (
    Certifications,
    Constraints,
    Education,
    Experience,
    Identity,
    Portfolio,
    Preferences,
    Projects,
    SkillLevel,
    SkillLevels,
    Skills,
    Achievements,
    TargetRoles,
)

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "candidate" / "example"

EXAMPLE_FILES = [
    "identity.json",
    "education.json",
    "experience.json",
    "projects.json",
    "skills.json",
    "skill_levels.json",
    "achievements.json",
    "certifications.json",
    "portfolio.json",
    "preferences.json",
    "target_roles.json",
    "constraints.json",
]


# ── File integrity ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_file_exists(filename: str):
    """All 12 candidate example files must be present."""
    path = EXAMPLE_DIR / filename
    assert path.exists(), f"Missing example file: {filename}"


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_file_is_valid_json(filename: str):
    """All example files must be parseable JSON."""
    path = EXAMPLE_DIR / filename
    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    assert isinstance(data, dict)


@pytest.mark.parametrize("filename", EXAMPLE_FILES)
def test_example_file_has_schema_version(filename: str):
    """All example files must declare schema_version."""
    path = EXAMPLE_DIR / filename
    data = json.loads(path.read_text())
    assert "schema_version" in data, f"{filename} missing schema_version"
    assert data["schema_version"] == "1.0"


# ── Pydantic model parsing ────────────────────────────────────────────────────


def test_parse_identity():
    data = json.loads((EXAMPLE_DIR / "identity.json").read_text())
    identity = Identity(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert identity.full_name == "Alex Chen"
    assert identity.open_to_opportunities is True


def test_parse_education():
    data = json.loads((EXAMPLE_DIR / "education.json").read_text())
    edu = Education(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert len(edu.entries) == 1
    assert edu.entries[0].id == "edu_btech_cs"


def test_parse_experience():
    data = json.loads((EXAMPLE_DIR / "experience.json").read_text())
    exp = Experience(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert len(exp.entries) == 2
    assert exp.entries[0].is_current is True


def test_parse_projects():
    data = json.loads((EXAMPLE_DIR / "projects.json").read_text())
    projects = Projects(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert len(projects.entries) == 2
    # One professional, one personal
    pro_flags = {p.is_professional for p in projects.entries}
    assert True in pro_flags
    assert False in pro_flags


def test_parse_skills():
    data = json.loads((EXAMPLE_DIR / "skills.json").read_text())
    skills = Skills(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert len(skills.categories) > 0


def test_parse_certifications():
    data = json.loads((EXAMPLE_DIR / "certifications.json").read_text())
    certs = Certifications(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert len(certs.entries) == 1
    assert certs.entries[0].name == "Certified Kubernetes Administrator (CKA)"


def test_parse_portfolio():
    data = json.loads((EXAMPLE_DIR / "portfolio.json").read_text())
    portfolio = Portfolio(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert portfolio.github_url is not None


def test_parse_target_roles():
    data = json.loads((EXAMPLE_DIR / "target_roles.json").read_text())
    roles = TargetRoles(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert len(roles.roles) == 3
    priorities = [r.priority for r in roles.roles]
    assert sorted(priorities) == priorities  # ordered by priority


# ── Skill level taxonomy ──────────────────────────────────────────────────────


def test_skill_level_enum_values():
    assert SkillLevel.STRONG == "strong"
    assert SkillLevel.WORKING == "working"
    assert SkillLevel.BASIC == "basic"
    assert SkillLevel.LEARNING == "learning"
    assert SkillLevel.NONE == "none"


def test_parse_skill_levels():
    data = json.loads((EXAMPLE_DIR / "skill_levels.json").read_text())
    sl = SkillLevels(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert len(sl.skills) > 0


def test_skill_levels_strong_has_evidence():
    """Strong skills in the example profile should have evidence references."""
    data = json.loads((EXAMPLE_DIR / "skill_levels.json").read_text())
    sl = SkillLevels(**{k: v for k, v in data.items() if not k.startswith("_")})
    strong_skills = [s for s in sl.skills if s.level == SkillLevel.STRONG]
    for skill in strong_skills:
        assert len(skill.evidence) > 0, (
            f"Strong skill '{skill.name}' has no evidence references. "
            "Professional claims must trace to experience or project IDs."
        )


def test_skill_levels_learning_has_no_years():
    """Learning skills must not claim years of professional experience."""
    data = json.loads((EXAMPLE_DIR / "skill_levels.json").read_text())
    sl = SkillLevels(**{k: v for k, v in data.items() if not k.startswith("_")})
    learning_skills = [s for s in sl.skills if s.level == SkillLevel.LEARNING]
    for skill in learning_skills:
        assert skill.years_of_experience is None, (
            f"Learning skill '{skill.name}' should not claim years_of_experience"
        )


def test_skill_levels_none_has_no_years():
    """Skills with level 'none' must not claim years of professional experience."""
    data = json.loads((EXAMPLE_DIR / "skill_levels.json").read_text())
    sl = SkillLevels(**{k: v for k, v in data.items() if not k.startswith("_")})
    none_skills = [s for s in sl.skills if s.level == SkillLevel.NONE]
    for skill in none_skills:
        assert skill.years_of_experience is None


# ── Constraints — placeholder policy ─────────────────────────────────────────


def test_constraints_all_hard_constraints_are_null():
    """
    The example constraints.json must have all hard constraint values as null.
    No real personal data should appear in committed example files.
    """
    data = json.loads((EXAMPLE_DIR / "constraints.json").read_text())
    hard = data.get("hard_constraints", {})

    nullable_fields = [
        "requires_visa_sponsorship",
        "current_work_authorization",
        "willing_to_relocate",
        "relocation_cities",
        "minimum_salary",
        "salary_currency",
        "maximum_commute_minutes",
        "no_bond",
        "no_night_shifts",
    ]
    for field in nullable_fields:
        if field in hard:
            assert hard[field] is None, (
                f"constraints.json hard_constraints.{field} must be null in example file. "
                "Real values belong in candidate/private/constraints.json only."
            )


def test_constraints_parse_all_null():
    data = json.loads((EXAMPLE_DIR / "constraints.json").read_text())
    c = Constraints(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert c.hard_constraints.minimum_salary is None
    assert c.hard_constraints.current_work_authorization is None
    assert c.hard_constraints.willing_to_relocate is None


def test_constraints_soft_avoid_industries_is_empty_in_example():
    data = json.loads((EXAMPLE_DIR / "constraints.json").read_text())
    c = Constraints(**{k: v for k, v in data.items() if not k.startswith("_")})
    assert c.soft_constraints.avoid_industries == []
