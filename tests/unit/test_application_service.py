import pytest
from applyai.services.application_service import ApplicationService
from applyai.core.database import create_all_tables, reset_engine, init_engine, get_session
from applyai.models.job import Job
from applyai.models.event import AuditEvent

@pytest.fixture(autouse=True)
async def setup_db():
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all_tables()
    yield
    reset_engine()

async def create_job(job_id: str):
    async with get_session() as session:
        j = Job(id=job_id, source="test", job_url="http://test.com", content_hash=job_id, company="c", role="r", status="new")
        session.add(j)
        await session.commit()

@pytest.mark.asyncio
async def test_get_or_create_draft():
    await create_job("test-job-id")
    service = ApplicationService()
    job_id = "test-job-id"
    app = await service.get_or_create_application(job_id)
    assert app.status == "draft"
    assert app.job_id == job_id
    
    # Second call should return the same
    app2 = await service.get_or_create_application(job_id)
    assert app2.id == app.id

@pytest.mark.asyncio
async def test_valid_transitions():
    await create_job("job-1")
    service = ApplicationService()
    app = await service.get_or_create_application("job-1")
    
    app = await service.update_status(app.id, "prepared")
    assert app.status == "prepared"
    
    app = await service.update_status(app.id, "applied")
    assert app.status == "applied"
    
    app = await service.update_status(app.id, "interviewing")
    assert app.status == "interviewing"
    
    app = await service.update_status(app.id, "offer")
    assert app.status == "offer"
    
    app = await service.update_status(app.id, "withdrawn")
    assert app.status == "withdrawn"

@pytest.mark.asyncio
async def test_invalid_transitions():
    await create_job("job-2")
    service = ApplicationService()
    app = await service.get_or_create_application("job-2")
    
    # Cannot jump from draft to interviewing
    with pytest.raises(ValueError, match="Invalid transition from 'draft' to 'interviewing'"):
        await service.update_status(app.id, "interviewing")

@pytest.mark.asyncio
async def test_unknown_status():
    await create_job("job-3")
    service = ApplicationService()
    app = await service.get_or_create_application("job-3")
    
    with pytest.raises(ValueError, match="Unknown status: unknown"):
        await service.update_status(app.id, "unknown")
