import pytest
from applyai.services.discovery_service import DiscoveryService
from applyai.storage.jobs import JobRepository
from applyai.schemas.job import NormalizedJob
from applyai.core.database import create_all_tables, reset_engine, init_engine
from applyai.discovery.registry import get_adapter_class
import applyai.discovery.adapters.mock  # Ensure mock adapter is registered

@pytest.fixture(autouse=True)
async def setup_db():
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all_tables()
    yield
    reset_engine()

@pytest.mark.asyncio
async def test_mock_adapter():
    adapter_cls = get_adapter_class("mock")
    adapter = adapter_cls("test_mock", {"company_prefix": "TestCorp"})
    jobs = await adapter.discover(limit=2)
    assert len(jobs) == 2
    assert jobs[0]["company"] == "TestCorp 1"
    assert jobs[1]["company"] == "TestCorp 2"

@pytest.mark.asyncio
async def test_discovery_service_run_and_deduplicate():
    service = DiscoveryService()
    
    # Run once to ingest jobs
    results = await service.run_discovery()
    assert "mock_jobs_1" in results
    net_new_first = results["mock_jobs_1"]
    assert net_new_first > 0
    
    # Run again, deduplication should kick in since source_job_ids will overlap if they were deterministic,
    # wait, the mock adapter generates random UUIDs for source_job_id!
    # So running again will generate NEW jobs. Let's fix the mock adapter to be deterministic
    # for testing, or we just manually inject a duplicate.
    
    # Let's test deduplication directly
    repo = JobRepository()
    await repo.create(NormalizedJob(
        source="test",
        job_url="https://test.com/dedup",
        source_job_id="dedup-id-123",
        content_hash="hash1",
        company="Acme",
        role="SWE",
        date_discovered="2024-01-01T00:00:00Z"
    ))
    
    raw_jobs = [
        {"source_job_id": "dedup-id-123", "company": "Dup1"},  # should be filtered
        {"job_url": "https://test.com/dedup", "company": "Dup2"}, # should be filtered
        {"source_job_id": "new-id-456", "company": "New1"}, # should pass
    ]
    
    net_new = await service._filter_existing_jobs(raw_jobs)
    assert len(net_new) == 1
    assert net_new[0]["company"] == "New1"

@pytest.mark.asyncio
async def test_discovery_disabled_globally():
    service = DiscoveryService()
    service.settings.discovery.enabled = False
    results = await service.run_discovery()
    assert results == {}
