"""
Pipeline Service.

Orchestrates the end-to-end flow:
1. Discovery
2. Analysis (concurrently via Semaphore)
3. Resume Generation for shortlisted jobs
"""

import asyncio
import logging
from applyai.services.discovery_service import DiscoveryService
from applyai.services.analysis_service import AnalysisService
from applyai.services.resume_service import ResumeService
from applyai.core.database import get_session
from applyai.models.job import Job
from applyai.models.scoring import JobScore
from applyai.core.config import get_settings
from sqlalchemy import select

logger = logging.getLogger(__name__)

class PipelineService:
    def __init__(self):
        self.discovery = DiscoveryService()
        self.analysis = AnalysisService()
        self.resume = ResumeService()
        self.settings = get_settings()

    async def run_full_pipeline(self, max_concurrent_analyses: int = 5) -> dict:
        """Run the end-to-end job acquisition pipeline."""
        
        results = {
            "discovered": 0,
            "analyzed": 0,
            "shortlisted_resumes_generated": 0,
            "errors": 0
        }

        # 1. Discovery
        logger.info("Starting Pipeline: Discovery Phase")
        discovery_results = await self.discovery.run_discovery()
        results["discovered"] = sum(discovery_results.values())
        
        # 2. Find pending jobs (status == 'new')
        async with get_session() as session:
            stmt = select(Job).filter_by(status="new")
            pending_jobs = (await session.execute(stmt)).scalars().all()
            
        if not pending_jobs:
            logger.info("Pipeline: No pending jobs to analyze.")
            return results
            
        logger.info(f"Pipeline: Analyzing {len(pending_jobs)} jobs concurrently (max {max_concurrent_analyses}).")
        
        # 3. Concurrent Analysis
        semaphore = asyncio.Semaphore(max_concurrent_analyses)
        
        async def bounded_analyze(job_id: str):
            async with semaphore:
                try:
                    await self.analysis.analyze_and_score(job_id)
                    return True
                except Exception as e:
                    logger.exception(f"Error analyzing job {job_id}: {e}")
                    return False

        analysis_tasks = [bounded_analyze(j.id) for j in pending_jobs]
        analysis_outcomes = await asyncio.gather(*analysis_tasks)
        
        results["analyzed"] = sum(1 for o in analysis_outcomes if o)
        results["errors"] += sum(1 for o in analysis_outcomes if not o)
        
        # 4. Resume Generation for Shortlisted
        # We need to find jobs we just scored that meet the shortlist criteria, 
        # and don't already have a resume generated today (or at all). For simplicity, we just generate
        # resumes for any job that is "scored" and above threshold, but maybe just limit to the ones we just processed.
        # Actually, let's just query the DB for jobs that are shortlisted but have no ResumeVersion.
        from applyai.models.application import ResumeVersion
        
        async with get_session() as session:
            # Join JobScore and outerjoin ResumeVersion, where ResumeVersion.id is null and score >= min
            min_score = self.settings.scoring.thresholds.shortlist_min_score
            stmt = (
                select(Job.id)
                .join(JobScore, Job.id == JobScore.job_id)
                .outerjoin(ResumeVersion, Job.id == ResumeVersion.job_id)
                .where(JobScore.overall_score >= min_score)
                .where(ResumeVersion.id.is_(None))
            )
            jobs_needing_resumes = (await session.execute(stmt)).scalars().all()
            
        if not jobs_needing_resumes:
            logger.info("Pipeline: No new shortlisted jobs requiring resumes.")
            return results
            
        logger.info(f"Pipeline: Generating resumes for {len(jobs_needing_resumes)} shortlisted jobs.")
        
        for job_id in jobs_needing_resumes:
            try:
                await self.resume.generate_resume(job_id)
                results["shortlisted_resumes_generated"] += 1
            except Exception as e:
                logger.exception(f"Error generating resume for job {job_id}: {e}")
                results["errors"] += 1
                
        logger.info("Pipeline complete: %s", results)
        return results
