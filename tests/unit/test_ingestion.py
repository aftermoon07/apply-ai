import pytest
import json
from pathlib import Path
from applyai.ingestion.manual import ManualSource
from applyai.ingestion.json_file import JsonFileSource
from applyai.schemas.job import RawJobInput
from applyai.services.job_service import JobService
from applyai.storage.jobs import JobRepository
from applyai.services.event_service import EventService
from applyai.core.database import create_all_tables, reset_engine, init_engine

@pytest.fixture(autouse=True)
async def setup_db():
    init_engine("sqlite+aiosqlite:///:memory:")
    await create_all_tables()
    yield
    reset_engine()

def test_manual_ingestion():
    source = ManualSource()
    text = "We are looking for a Software Engineer."
    results = list(source.parse(text, company="Acme", role="SWE"))
    
    assert len(results) == 1
    assert results[0].company == "Acme"
    assert results[0].role == "SWE"
    assert results[0].job_description == text

def test_manual_ingestion_empty():
    source = ManualSource()
    results = list(source.parse(""))
    assert len(results) == 0

def test_json_file_ingestion(tmp_path: Path):
    source = JsonFileSource()
    jobs_data = [
        {"company": "Acme", "role": "SWE", "url": "https://test.com/1"},
        {"company": "Other", "role": "PM", "salary": "12 LPA"}
    ]
    file_path = tmp_path / "jobs.json"
    file_path.write_text(json.dumps(jobs_data))

    results = list(source.parse(file_path))
    assert len(results) == 2
    assert results[0].company == "Acme"
    assert results[0].job_url == "https://test.com/1"
    assert results[1].salary_raw == "12 LPA"

def test_json_file_ingestion_malformed():
    source = JsonFileSource()
    with pytest.raises(ValueError):
        list(source.parse("{bad_json"))

@pytest.mark.asyncio
async def test_job_service_ingest():
    service = JobService(JobRepository(), EventService())
    raw = RawJobInput(
        source="test",
        company="Acme",
        role="SWE",
        job_description="Test job description"
    )
    result = await service.ingest(raw)
    assert result.status == "inserted"
    assert result.is_duplicate is False

    # Ingest again, should be duplicate
    result2 = await service.ingest(raw)
    assert result2.status == "duplicate"
    assert result2.is_duplicate is True
    assert result2.duplicate_of == result.job_id

@pytest.mark.asyncio
async def test_job_service_ingest_batch():
    service = JobService(JobRepository(), EventService())
    raw_inputs = [
        RawJobInput(source="test", company="A", role="1"),
        RawJobInput(source="test", company="B", role="2"),
        RawJobInput(source="test", company="A", role="1") # Duplicate within batch
    ]
    results = await service.ingest_batch(raw_inputs)
    assert len(results) == 3
    assert results[0].status == "inserted"
    assert results[1].status == "inserted"
    assert results[2].status == "duplicate"
