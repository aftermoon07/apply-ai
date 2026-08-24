import os
import pytest
from applyai.services.resume_service import ResumeService
from applyai.services.analysis_service import AnalysisService
from applyai.storage.jobs import JobRepository
from applyai.schemas.job import NormalizedJob
from applyai.core.database import create_all_tables, reset_engine, init_engine

@pytest.fixture(autouse=True)
async def setup_db():
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all_tables()
    yield
    reset_engine()

@pytest.mark.asyncio
async def test_generate_resume_for_scored_job():
    repo = JobRepository()
    job = await repo.create(NormalizedJob(
        source="test",
        job_url="https://test.com",
        content_hash="test",
        company="Acme",
        role="SWE",
        date_discovered="2024-01-01T00:00:00Z"
    ))

    # First we need to analyze and score the job to get the requisite models
    analysis_service = AnalysisService(repo)
    # The default behavior falls back to example schemas so snapshot works
    await analysis_service.analyze_and_score(job.id)
    
    resume_service = ResumeService()
    resume_version = await resume_service.generate_resume(job.id)
    
    assert resume_version.job_id == job.id
    assert resume_version.version == 1
    assert resume_version.format == "markdown"
    assert "Placeholder" in resume_version.content or "Dummy" in resume_version.content
    assert os.path.exists(resume_version.file_path)

@pytest.mark.asyncio
async def test_generate_resume_unscored_job_fails():
    repo = JobRepository()
    job = await repo.create(NormalizedJob(
        source="test",
        job_url="https://test.com",
        content_hash="test",
        company="Acme",
        role="SWE",
        date_discovered="2024-01-01T00:00:00Z"
    ))
    
    resume_service = ResumeService()
    with pytest.raises(ValueError, match="must be analyzed/scored"):
        await resume_service.generate_resume(job.id)
