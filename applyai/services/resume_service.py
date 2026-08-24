"""
Resume Service.

Orchestrates Phase 4: Job-specific resume generation using the Resume Tailor Agent.
"""

import logging
from pathlib import Path
import json

from applyai.models.job import Job
from applyai.models.analysis import JobAnalysis
from applyai.models.scoring import JobScore, CandidateSnapshot
from applyai.models.application import ResumeVersion
from applyai.storage.jobs import JobRepository
from applyai.services.event_service import EventService
from applyai.agents.resume_tailor import ResumeTailorAgent
from applyai.providers.factory import get_provider
from applyai.core.config import get_settings
from applyai.core.database import get_session
from sqlalchemy import select

logger = logging.getLogger(__name__)

class ResumeService:
    def __init__(
        self,
        event_service: EventService | None = None
    ):
        self._events = event_service or EventService()
        self.settings = get_settings()
        self.provider = get_provider()
        self.agent = ResumeTailorAgent(self.provider)

    async def generate_resume(self, job_id: str) -> ResumeVersion:
        """
        Generate a tailored resume for a scored job.
        """
        logger.info("Starting resume generation for job %s", job_id)
        
        async with get_session() as session:
            # 1. Fetch Job and ensure it is scored
            job_obj = await session.get(Job, job_id)
            if not job_obj:
                raise ValueError(f"Job {job_id} not found.")
            
            if job_obj.status not in ("scored", "analyzed", "shortlisted"):
                raise ValueError(f"Job {job_id} must be analyzed/scored before generating a resume. Current status: {job_obj.status}")

            # 2. Fetch JobAnalysis and JobScore
            analysis_obj = (await session.execute(select(JobAnalysis).filter_by(job_id=job_id))).scalar_one_or_none()
            score_obj = (await session.execute(select(JobScore).filter_by(job_id=job_id))).scalar_one_or_none()
            
            if not analysis_obj or not score_obj or not score_obj.candidate_snapshot_id:
                raise ValueError(f"Missing analysis, score, or candidate snapshot for job {job_id}.")
                
            snapshot = await session.get(CandidateSnapshot, score_obj.candidate_snapshot_id)
            
            # Convert JobAnalysis ORM to Pydantic JobAnalysisOutput
            from applyai.schemas.analysis import JobAnalysisOutput
            analysis_output = JobAnalysisOutput(
                summary=analysis_obj.summary,
                role_level=analysis_obj.role_level,
                team_signals=json.loads(analysis_obj.team_signals or "[]"),
                culture_signals=json.loads(analysis_obj.culture_signals or "[]"),
                red_flags=json.loads(analysis_obj.red_flags or "[]"),
                green_flags=json.loads(analysis_obj.green_flags or "[]"),
                key_responsibilities=json.loads(analysis_obj.key_responsibilities or "[]"),
                tech_stack=json.loads(analysis_obj.tech_stack or "[]"),
                domain=analysis_obj.domain,
                ats_keywords=json.loads(analysis_obj.ats_keywords or "[]"),
                analysis_status=analysis_obj.analysis_status,
                provider_used=analysis_obj.provider_used,
                model_used=analysis_obj.model_used
            )
            
            # 3. Generate resume content
            resume_md = await self.agent.tailor(
                company=job_obj.company or "Unknown",
                role=job_obj.role or "Unknown",
                analysis=analysis_output,
                snapshot=snapshot
            )
            
            # 4. Save to disk
            resumes_dir = Path(self.settings.app.data_dir) / "resumes"
            resumes_dir.mkdir(parents=True, exist_ok=True)
            
            # Get latest version number
            existing_versions = (await session.execute(
                select(ResumeVersion).filter_by(job_id=job_id)
            )).scalars().all()
            version_num = len(existing_versions) + 1
            
            # Sanitize job_id: only allow alphanumeric chars and dashes (UUIDs)
            # This prevents path traversal if a malicious source_job_id leaks into job.id.
            safe_job_id = "".join(c for c in job_id if c.isalnum() or c == "-")
            if not safe_job_id:
                raise ValueError(f"Job ID {job_id!r} produced an empty safe filename.")

            file_name = f"resume_job_{safe_job_id}_v{version_num}.md"
            file_path = resumes_dir / file_name
            
            with open(file_path, "w") as f:
                f.write(resume_md)
                
            # 5. Persist ResumeVersion ORM
            resume_version = ResumeVersion(
                job_id=job_id,
                version=version_num,
                format="markdown",
                content=resume_md,
                file_path=str(file_path)
            )
            session.add(resume_version)
            await session.commit()
            
            await session.refresh(resume_version)
            
            await self._events.emit(
                event_type="resume_generated",
                entity_type="job",
                entity_id=job_id,
                payload={"version": version_num, "file_path": str(file_path)}
            )
            
            return resume_version
