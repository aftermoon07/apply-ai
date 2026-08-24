import pytest
from typer.testing import CliRunner
from applyai.cli.main import app
from applyai.core.database import init_engine, create_all_tables, reset_engine
import json

runner = CliRunner()

@pytest.fixture(autouse=True)
def setup_db():
    import asyncio
    
    async def _setup():
        init_engine("sqlite+aiosqlite:///:memory:")
        await create_all_tables()
        
    asyncio.run(_setup())
    yield
    reset_engine()

def test_cli_ingest_file(tmp_path):
    job_file = tmp_path / "job.txt"
    job_file.write_text("We are looking for a Python developer.")
    
    result = runner.invoke(app, ["ingest", "file", "--file", str(job_file), "--company", "Acme", "--role", "Python Dev"])
    assert result.exit_code == 0
    assert "1 new job(s) ingested" in result.stdout

def test_cli_ingest_batch(tmp_path):
    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps([{"company": "A", "role": "R1"}, {"company": "B", "role": "R2"}]))
    
    result = runner.invoke(app, ["ingest", "batch", "--file", str(jobs_file)])
    assert result.exit_code == 0
    assert "2 new job(s) ingested" in result.stdout

def test_cli_ingest_file_empty(tmp_path):
    job_file = tmp_path / "empty.txt"
    job_file.write_text("")
    
    result = runner.invoke(app, ["ingest", "file", "--file", str(job_file)])
    assert result.exit_code == 1
    assert "File is empty" in result.output
