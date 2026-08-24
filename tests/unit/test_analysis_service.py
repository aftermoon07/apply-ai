import pytest
from applyai.services.analysis_service import AnalysisService
from applyai.storage.jobs import JobRepository
from applyai.services.event_service import EventService
from applyai.schemas.job import NormalizedJob
from applyai.models.job import Job
from applyai.core.database import create_all_tables, reset_engine, init_engine

@pytest.fixture(autouse=True)
async def setup_db():
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all_tables()
    yield
    reset_engine()

@pytest.mark.asyncio
async def test_analyze_and_score():
    repo = JobRepository()
    job = await repo.create(NormalizedJob(
        source="test",
        job_url="https://test.com",
        content_hash="test",
        company="Acme",
        role="SWE",
        date_discovered="2024-01-01T00:00:00Z"
    ))

    service = AnalysisService(repo, EventService())
    
    updated_job = await service.analyze_and_score(job.id)
    assert updated_job.status == "scored"
    
    from applyai.core.database import get_session
    from applyai.models.analysis import JobAnalysis
    from applyai.models.scoring import JobScore
    from sqlalchemy import select
    
    async with get_session() as session:
        analysis = (await session.execute(select(JobAnalysis).filter_by(job_id=job.id))).scalar_one()
        score = (await session.execute(select(JobScore).filter_by(job_id=job.id))).scalar_one()
        
        assert analysis.analysis_status == "skipped"
        assert score.scoring_status == "complete"
        assert score.overall_score == 0.0

@pytest.mark.asyncio
async def test_batch_analyze_and_score():
    repo = JobRepository()
    await repo.create(NormalizedJob(
        source="test",
        job_url="https://test.com/1",
        content_hash="test1",
        company="Acme",
        role="SWE",
        date_discovered="2024-01-01T00:00:00Z"
    ))
    await repo.create(NormalizedJob(
        source="test",
        job_url="https://test.com/2",
        content_hash="test2",
        company="Acme",
        role="SWE",
        date_discovered="2024-01-01T00:00:00Z"
    ))

    service = AnalysisService(repo, EventService())
    
    results = await service.batch_analyze_and_score()
    
    assert len(results) == 2
    for job in results:
        assert job.status == "scored"

@pytest.mark.asyncio
async def test_synthetic_fallback_disabled():
    repo = JobRepository()
    job = await repo.create(NormalizedJob(
        source="test",
        job_url="https://test.com/3",
        content_hash="test3",
        company="Acme",
        role="SWE",
        date_discovered="2024-01-01T00:00:00Z"
    ))
    
    service = AnalysisService(repo)
    # Monkeypatch the config temporarily
    service.settings.candidate.allow_synthetic_fallback = False
    
    # If the private dir is empty, it should raise
    with pytest.raises(RuntimeError, match="allow_synthetic_fallback' is disabled"):
        await service.analyze_and_score(job.id)
