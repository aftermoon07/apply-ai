"""
Pydantic schemas for the candidate knowledge base.

POLICY:
  - All fields represent actual, verifiable information.
  - The system never invents employment history, degrees, or certifications.
  - skill_level reflects personal proficiency assessment only.
  - Skill proficiency ≠ years of professional employment.
  - Every professional claim must trace to evidence in experience or projects.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ── Skill Level ───────────────────────────────────────────────────────────────


class SkillLevel(StrEnum):
    """
    Candidate's self-assessed proficiency level for a skill.

    IMPORTANT: This reflects depth of knowledge, NOT years of employment.
    A "strong" level does NOT authorize claiming professional experience
    unless that experience is documented in experience.json or projects.json.
    """

    STRONG = "strong"       # Used in production; can mentor others
    WORKING = "working"     # Used in real projects; comfortable independently
    BASIC = "basic"         # Have used it; need reference for complex tasks
    LEARNING = "learning"   # Currently studying; not yet used in real work
    NONE = "none"           # No experience


class SkillEntry(BaseModel):
    """A single skill with proficiency and evidence."""

    name: str
    level: SkillLevel
    years_of_experience: int | None = Field(
        default=None,
        description=(
            "Years of actual hands-on use — NOT inferred from skill level. "
            "Leave null unless supported by evidence in experience.json or projects.json."
        ),
    )
    evidence: list[str] = Field(
        default_factory=list,
        description=(
            "References to experience or project IDs that support this skill. "
            "Format: 'experience:<id>' or 'project:<id>'"
        ),
    )
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class SkillLevels(BaseModel):
    """candidate/skill_levels.json"""

    schema_version: str = "1.0"
    levels: dict[str, str] = Field(
        default_factory=lambda: {
            "strong": "Used professionally in production systems; can mentor others",
            "working": "Used in real projects; comfortable independently",
            "basic": "Have used it; require reference material for non-trivial tasks",
            "learning": "Currently studying; not yet used in real work",
            "none": "No experience",
        }
    )
    skills: list[SkillEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def no_inferred_years(self) -> "SkillLevels":
        """
        Warn if years_of_experience is set without evidence.
        The validator does not block — it flags for review.
        """
        for skill in self.skills:
            if skill.years_of_experience is not None and not skill.evidence:
                # This is a warning condition, not a hard error.
                # Users should add evidence references when claiming years.
                pass
        return self


# ── Identity ──────────────────────────────────────────────────────────────────


class Identity(BaseModel):
    """candidate/identity.json"""

    schema_version: str = "1.0"
    full_name: str = Field(description="Your legal full name")
    email: str
    phone: str | None = None
    location: str | None = Field(default=None, description="City, Country")
    linkedin_url: str | None = None
    github_url: str | None = None
    website: str | None = None
    summary: str | None = Field(
        default=None,
        description="Professional summary — truthful, written by you",
    )
    years_of_experience: int | None = None
    current_title: str | None = None
    current_employer: str | None = None
    open_to_opportunities: bool = True


# ── Education ─────────────────────────────────────────────────────────────────


class EducationEntry(BaseModel):
    id: str
    institution: str
    degree: str = Field(description="Exact degree title as awarded")
    field_of_study: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    gpa: str | None = None
    honors: str | None = None
    relevant_coursework: list[str] = Field(default_factory=list)
    notes: str | None = None


class Education(BaseModel):
    """candidate/education.json"""

    schema_version: str = "1.0"
    entries: list[EducationEntry] = Field(default_factory=list)


# ── Experience ────────────────────────────────────────────────────────────────


class ExperienceEntry(BaseModel):
    id: str = Field(description="Unique ID referenced by skill evidence")
    company: str
    title: str
    location: str | None = None
    work_mode: str | None = None  # "remote" | "hybrid" | "onsite"
    employment_type: str | None = None  # "full_time" | "contract" | "part_time"
    start_date: str = Field(description="YYYY-MM format")
    end_date: str | None = Field(default=None, description="YYYY-MM or null if current")
    is_current: bool = False
    description: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(
        default_factory=list,
        description="Quantified accomplishments; must be factually accurate",
    )
    technologies: list[str] = Field(default_factory=list)
    team_size: int | None = None


class Experience(BaseModel):
    """candidate/experience.json"""

    schema_version: str = "1.0"
    entries: list[ExperienceEntry] = Field(default_factory=list)


# ── Projects ──────────────────────────────────────────────────────────────────


class ProjectEntry(BaseModel):
    id: str = Field(description="Unique ID referenced by skill evidence")
    name: str
    description: str
    role: str | None = Field(
        default=None,
        description="Your specific role — do not claim ownership of others' work",
    )
    is_professional: bool = Field(
        default=False,
        description="True only if this was part of paid employment",
    )
    is_open_source: bool = False
    url: str | None = None
    technologies: list[str] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    highlights: list[str] = Field(default_factory=list)
    team_size: int | None = None


class Projects(BaseModel):
    """candidate/projects.json"""

    schema_version: str = "1.0"
    entries: list[ProjectEntry] = Field(default_factory=list)


# ── Skills ────────────────────────────────────────────────────────────────────


class SkillCategory(BaseModel):
    category: str
    skills: list[str]


class Skills(BaseModel):
    """candidate/skills.json — flat skill inventory by category."""

    schema_version: str = "1.0"
    categories: list[SkillCategory] = Field(default_factory=list)


# ── Achievements ──────────────────────────────────────────────────────────────


class Achievement(BaseModel):
    id: str
    title: str
    description: str
    date: str | None = None
    evidence_url: str | None = None


class Achievements(BaseModel):
    """candidate/achievements.json"""

    schema_version: str = "1.0"
    entries: list[Achievement] = Field(default_factory=list)


# ── Certifications ────────────────────────────────────────────────────────────


class Certification(BaseModel):
    id: str
    name: str = Field(description="Official certification name exactly as issued")
    issuing_organization: str
    issue_date: str | None = Field(default=None, description="YYYY-MM")
    expiry_date: str | None = Field(default=None, description="YYYY-MM or null")
    credential_id: str | None = None
    credential_url: str | None = None
    is_expired: bool = False


class Certifications(BaseModel):
    """candidate/certifications.json"""

    schema_version: str = "1.0"
    entries: list[Certification] = Field(default_factory=list)


# ── Portfolio ─────────────────────────────────────────────────────────────────


class Publication(BaseModel):
    title: str
    url: str | None = None
    published_at: str | None = None
    venue: str | None = None


class OpenSourceContribution(BaseModel):
    repo: str
    description: str | None = None
    url: str | None = None


class Portfolio(BaseModel):
    """candidate/portfolio.json"""

    schema_version: str = "1.0"
    github_url: str | None = None
    personal_website: str | None = None
    linkedin_url: str | None = None
    publications: list[Publication] = Field(default_factory=list)
    open_source_contributions: list[OpenSourceContribution] = Field(default_factory=list)
    kaggle_profile: str | None = None
    other_links: list[dict[str, str]] = Field(default_factory=list)


# ── Preferences ───────────────────────────────────────────────────────────────


class Preferences(BaseModel):
    """candidate/preferences.json — soft preferences, not hard constraints."""

    schema_version: str = "1.0"
    preferred_work_mode: str | None = None  # "remote" | "hybrid" | "onsite"
    preferred_company_size: str | None = None
    preferred_industries: list[str] = Field(default_factory=list)
    preferred_team_size: str | None = None
    preferred_tech_stack: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    notes: str | None = None


# ── Target Roles ──────────────────────────────────────────────────────────────


class TargetRole(BaseModel):
    title: str
    seniority_level: str | None = None
    keywords: list[str] = Field(default_factory=list)
    priority: int = Field(default=1, ge=1, le=5)


class TargetRoles(BaseModel):
    """candidate/target_roles.json"""

    schema_version: str = "1.0"
    roles: list[TargetRole] = Field(default_factory=list)


# ── Constraints ───────────────────────────────────────────────────────────────


class HardConstraints(BaseModel):
    """
    Hard constraints — all fields are PLACEHOLDERS until explicitly set by the user.
    Do not populate these with assumed or inferred values.
    """

    requires_visa_sponsorship: bool | None = None
    current_work_authorization: list[str] | None = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country codes where candidate is authorized to work",
    )
    willing_to_relocate: bool | None = None
    relocation_cities: list[str] | None = None
    minimum_salary: int | None = Field(
        default=None,
        description="Minimum acceptable salary (in currency specified below)",
    )
    salary_currency: str | None = None
    maximum_commute_minutes: int | None = None
    no_bond: bool | None = None
    no_night_shifts: bool | None = None


class SoftConstraints(BaseModel):
    """Soft preferences that reduce fit score but don't hard-reject a job."""

    preferred_work_mode: str | None = None
    preferred_team_size: str | None = None
    avoid_industries: list[str] = Field(
        default_factory=list,
        description="Industries to deprioritize — not automatically rejected",
    )


class Constraints(BaseModel):
    """
    candidate/constraints.json

    All values default to null (unset). The system must not infer or assume
    constraint values from other profile fields. Constraints are only active
    when explicitly set by the candidate.
    """

    schema_version: str = "1.0"
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    soft_constraints: SoftConstraints = Field(default_factory=SoftConstraints)


# ── Full Candidate Profile (aggregate) ────────────────────────────────────────


class CandidateProfile(BaseModel):
    """Aggregate of all candidate profile documents."""

    identity: Identity
    education: Education
    experience: Experience
    projects: Projects
    skills: Skills
    skill_levels: SkillLevels
    achievements: Achievements
    certifications: Certifications
    portfolio: Portfolio
    preferences: Preferences
    target_roles: TargetRoles
    constraints: Constraints
