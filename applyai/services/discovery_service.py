"""
Discovery Service.

Orchestrates Phase 5: Searching configured sources for new jobs,
deduplicating them against the DB, and pushing them to Ingestion.
"""

import asyncio
import logging
from applyai.core.config import get_settings
from applyai.discovery.registry import get_adapter_class
from applyai.services.job_service import JobService
from applyai.services.event_service import EventService
from applyai.core.database import get_session
from applyai.models.job import Job
from sqlalchemy import select

logger = logging.getLogger(__name__)

class DiscoveryService:
    def __init__(
        self,
        job_service: JobService | None = None,
        event_service: EventService | None = None
    ):
        self._jobs = job_service or JobService()
        self._events = event_service or EventService()
        self.settings = get_settings()
        
    async def _filter_existing_jobs(self, raw_jobs: list[dict]) -> list[dict]:
        """
        Pre-ingestion deduplication.
        Returns only the jobs that do not exist in the database (by source_job_id or job_url).
        """
        if not raw_jobs:
            return []
            
        new_jobs = []
        async with get_session() as session:
            for job in raw_jobs:
                source_id = job.get("source_job_id")
                job_url = job.get("job_url")
                
                # Check source_id if present
                if source_id:
                    stmt = select(Job).filter_by(source_job_id=source_id).limit(1)
                    if (await session.execute(stmt)).scalar_one_or_none():
                        continue
                        
                # Check job_url if present
                if job_url:
                    stmt = select(Job).filter_by(job_url=job_url).limit(1)
                    if (await session.execute(stmt)).scalar_one_or_none():
                        continue
                        
                new_jobs.append(job)
                
        return new_jobs

    async def run_discovery(self) -> dict[str, int]:
        """
        Iterate over all enabled sources, discover jobs, deduplicate, and ingest.
        Returns a dict of source names to number of net-new jobs ingested.
        """
        config = self.settings.discovery
        if not config.enabled:
            logger.info("Discovery is disabled globally in config.")
            return {}
            
        results = {}
        for source in config.sources:
            if not source.enabled:
                logger.info("Skipping disabled source: %s", source.name)
                continue
                
            logger.info("Running discovery on source: %s", source.name)
            
            try:
                # 1. Instantiate Adapter
                adapter_cls = get_adapter_class(source.type)
                adapter = adapter_cls(name=source.name, config=source.config)
                
                # 2. Fetch Jobs
                raw_jobs = await adapter.discover(limit=source.limit)
                
                # 3. Deduplicate
                net_new = await self._filter_existing_jobs(raw_jobs)
                
                # 4. Ingest
                if net_new:
                    from applyai.schemas.job import RawJobInput
                    raw_job_inputs = [RawJobInput(**job) for job in net_new]
                    # JobService.ingest_batch handles deduplication by content hash too,
                    # but our pre-check prevents unnecessary DB constraints and normalizations
                    await self._jobs.ingest_batch(raw_job_inputs)
                    
                results[source.name] = len(net_new)
                
                await self._events.emit(
                    event_type="discovery_run_completed",
                    entity_type="system",
                    entity_id=source.name,
                    payload={"found": len(raw_jobs), "net_new": len(net_new)}
                )
                
            except Exception as e:
                logger.exception("Error running discovery on %s: %s", source.name, e)
                await self._events.emit(
                    event_type="discovery_error",
                    entity_type="system",
                    entity_id=source.name,
                    payload={"error": str(e)}
                )
                
            # 5. Rate Limiting / Sleep
            if config.global_rate_limit_seconds > 0:
                await asyncio.sleep(config.global_rate_limit_seconds)
                
        return results
