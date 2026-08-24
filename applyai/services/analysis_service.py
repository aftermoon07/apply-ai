"""
Analysis Service.

Orchestrates Phase 3 pipeline: 
Job -> JobAnalyzer -> CandidateMatcher -> DeterministicScorer -> Update DB
"""

import logging
import json
from pathlib import Path
from applyai.models.job import Job
from applyai.storage.jobs import JobRepository
from applyai.services.event_service import EventService
from applyai.agents.analyzer import JobAnalyzerAgent
from applyai.agents.matcher import CandidateMatcherAgent
from applyai.processing.scorer import Scorer
from applyai.providers.factory import get_provider
from applyai.core.config import get_settings

logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(
        self,
        repository: JobRepository | None = None,
        event_service: EventService | None = None
    ):
        self._repo = repository or JobRepository()
        self._events = event_service or EventService()
        self.settings = get_settings()
        self.provider = get_provider()
        self.analyzer = JobAnalyzerAgent(self.provider)
        self.matcher = CandidateMatcherAgent(self.provider)
        self.scorer = Scorer()

    def _load_candidate_profile(self) -> dict:
        """Loads all candidate profile JSONs into a single dictionary."""
        profile = {}
        profile_dir = self.settings.resolved_profile_dir()
        
        # If the private dir doesn't exist or is empty, use example/
        if not profile_dir.exists() or not any(profile_dir.iterdir()):
            logger.info(f"Private profile dir {profile_dir} empty. Falling back to example dir.")
            profile_dir = Path(self.settings.candidate.example_dir)
            if not profile_dir.is_absolute():
                from applyai.core.config import PROJECT_ROOT
                profile_dir = PROJECT_ROOT / profile_dir

        if profile_dir.exists():
            for f in profile_dir.glob("*.json"):
                try:
                    with open(f, "r") as fp:
                        profile[f.stem] = json.load(fp)
                except Exception as e:
                    logger.warning("Failed to load %s: %s", f, e)
        
        return profile

    async def analyze_and_score(self, job_id: str) -> Job:
        """
        Run the full analysis and scoring pipeline on a job.
        """
        job = await self._repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found.")

        # Reconstruct NormalizedJob for agent input
        from applyai.schemas.job import NormalizedJob
        normalized = NormalizedJob(
            source=job.source,
            job_url=job.job_url,
            source_job_id=job.source_job_id,
            company=job.company,
            role=job.role,
            location=job.location,
            job_description=job.job_description,
            content_hash=job.content_hash,
            date_discovered=job.date_discovered
        )

        logger.info("Starting analysis for job %s", job_id)
        
        # 1. Analyzer
        analysis = await self.analyzer.analyze(normalized)
        
        # 2. Matcher
        candidate_profile = self._load_candidate_profile()
        matcher_output = await self.matcher.match(normalized, analysis, candidate_profile)
        
        # 3. Scorer
        score_output = self.scorer.score(
            component_scores=matcher_output.component_scores,
            matcher_output_dict=matcher_output.model_dump(),
            provider_used=analysis.provider_used or "none",
            model_used=analysis.model_used or "none"
        )
        
        # 4. Update DB
        from applyai.models.analysis import JobAnalysis
        from applyai.models.scoring import JobScore, CandidateSnapshot
        from applyai.core.database import get_session
        import hashlib
        
        # Create a candidate snapshot
        profile_json = json.dumps(candidate_profile, sort_keys=True)
        profile_hash = hashlib.sha256(profile_json.encode()).hexdigest()
        
        async with get_session() as session:
            job_obj = await session.get(Job, job_id)
            if not job_obj:
                raise ValueError(f"Job {job_id} disappeared")
                
            # JobAnalysis
            job_analysis = JobAnalysis(
                job_id=job_id,
                summary=analysis.summary,
                role_level=analysis.role_level,
                team_signals=json.dumps(analysis.team_signals),
                culture_signals=json.dumps(analysis.culture_signals),
                red_flags=json.dumps(analysis.red_flags),
                green_flags=json.dumps(analysis.green_flags),
                key_responsibilities=json.dumps(analysis.key_responsibilities),
                tech_stack=json.dumps(analysis.tech_stack),
                domain=analysis.domain,
                analysis_status=analysis.analysis_status,
                provider_used=analysis.provider_used,
                model_used=analysis.model_used
            )
            session.add(job_analysis)
            
            # Candidate Snapshot
            snapshot = CandidateSnapshot(snapshot=profile_json, profile_hash=profile_hash)
            session.add(snapshot)
            await session.flush() # get snapshot.id
            
            # JobScore
            c_scores = matcher_output.component_scores
            job_score = JobScore(
                job_id=job_id,
                candidate_snapshot_id=snapshot.id,
                technical_score=c_scores.technical_skills,
                experience_score=c_scores.experience_compat,
                education_score=c_scores.education_compat,
                location_score=c_scores.location_work_mode,
                level_score=c_scores.experience_level,
                project_score=c_scores.project_relevance,
                keyword_score=c_scores.keyword_coverage,
                overall_score=score_output.overall_score,
                matching_skills=json.dumps(score_output.matching_skills),
                missing_skills=json.dumps(score_output.missing_skills),
                transferable_skills=json.dumps(score_output.transferable_skills),
                concerns=json.dumps(score_output.concerns),
                reasons=json.dumps(score_output.reasons),
                recommendation=score_output.recommendation,
                confidence=score_output.confidence,
                interview_potential_score=score_output.interview_potential_score,
                interview_potential_factors=score_output.interview_potential_factors.model_dump_json() if score_output.interview_potential_factors else None,
                scoring_status=score_output.scoring_status,
                provider_used=score_output.provider_used,
                model_used=score_output.model_used
            )
            session.add(job_score)
            
            # Update Job status
            job_obj.status = "scored" if score_output.scoring_status == "complete" else "analyzed"
            updated_job = job_obj
            
        # 5. Emit Events
        await self._events.emit(
            event_type="job_analyzed",
            entity_type="job",
            entity_id=job_id,
            payload={"provider": analysis.provider_used, "status": analysis.analysis_status}
        )
        
        await self._events.emit(
            event_type="job_scored",
            entity_type="job",
            entity_id=job_id,
            payload={
                "score": score_output.overall_score,
                "recommendation": score_output.recommendation,
                "provider": score_output.provider_used
            }
        )
        
        if score_output.overall_score >= self.settings.scoring.thresholds.shortlist_min_score:
            await self._events.emit(
                event_type="job_shortlisted",
                entity_type="job",
                entity_id=job_id,
                payload={"score": score_output.overall_score}
            )

        logger.info("Completed analysis and scoring for job %s", job_id)
        
        return updated_job

    async def batch_analyze_and_score(self, limit: int = 50) -> list[Job]:
        """Analyze and score jobs that have not been analyzed yet."""
        # Find jobs with status="new" or "normalized"
        jobs = await self._repo.list(limit=limit)
        pending_jobs = [j for j in jobs if j.status in ("new", "normalized", "pending")]
        
        results = []
        for job in pending_jobs:
            try:
                res = await self.analyze_and_score(job.id)
                results.append(res)
            except Exception as e:
                logger.error("Failed batch analysis for job %s: %s", job.id, e)
                
        return results
