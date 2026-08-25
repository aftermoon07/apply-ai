"""applyai.models package — imports all ORM models so Alembic can discover them."""

from applyai.models.base import Base
from applyai.models.job import Job, JobSkill
from applyai.models.analysis import JobAnalysis
from applyai.models.scoring import CandidateSnapshot, JobScore
from applyai.models.application import Application, Interview, Response, ResumeVersion
from applyai.models.outreach import Contact, Outreach
from applyai.models.event import AuditEvent, EventType
from applyai.models.usage import ProviderUsage

__all__ = [
    "Base",
    "Job",
    "JobSkill",
    "JobAnalysis",
    "CandidateSnapshot",
    "JobScore",
    "Application",
    "ResumeVersion",
    "Response",
    "Interview",
    "Contact",
    "Outreach",
    "AuditEvent",
    "EventType",
    "ProviderUsage",
]
