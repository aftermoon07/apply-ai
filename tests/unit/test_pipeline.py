import pytest
from applyai.services.pipeline_service import PipelineService
from applyai.core.database import create_all_tables, reset_engine, init_engine

@pytest.fixture(autouse=True)
async def setup_db():
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all_tables()
    yield
    reset_engine()

@pytest.mark.asyncio
async def test_run_full_pipeline():
    service = PipelineService()
    
    # Enable discovery mock source 1, and ensure threshold is low enough so mock jobs pass
    # Actually, with NullProvider, the score might be defaults (0) depending on thresholds.
    # NullProvider returns a dummy job analysis and dummy job score if structured.
    # Let's adjust settings to ensure jobs are shortlisted.
    service.settings.scoring.thresholds.shortlist_min_score = 0.0
    
    results = await service.run_full_pipeline(max_concurrent_analyses=2)
    
    # MockAdapter returns 5 jobs by default config
    assert results["discovered"] == 5
    assert results["analyzed"] == 5
    assert results["errors"] == 0
    # Because they all score >= 0.0, they all get resumes
    assert results["shortlisted_resumes_generated"] == 5
