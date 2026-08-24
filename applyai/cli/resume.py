"""CLI commands for resume generation."""

import asyncio
import typer
from rich.console import Console

from applyai.core.database import init_engine
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging
from applyai.services.resume_service import ResumeService

console = Console()
err_console = Console(stderr=True)

resume_app = typer.Typer(
    name="resume",
    help="Generate job-specific resumes.",
    no_args_is_help=True,
)

async def _generate_resume(job_id: str):
    settings = get_settings()
    init_engine(settings.database_url)
    
    service = ResumeService()
    
    try:
        version = await service.generate_resume(job_id)
        console.print(f"[green]✓ Successfully generated resume version {version.version}![/green]")
        console.print(f"File saved to: [bold]{version.file_path}[/bold]")
    except Exception as e:
        err_console.print(f"[red]Failed to generate resume: {e}[/red]")

@resume_app.command("generate")
def generate(
    job_id: str = typer.Argument(..., help="ID of the job to generate a resume for")
) -> None:
    """Generate a tailored markdown resume for a specific job."""
    setup_logging()
    
    # In a real app we might resolve prefix to full ID here,
    # but for simplicity we assume full job_id is passed.
    # To support prefix, we could do a quick lookup.
    
    # We will do a quick lookup to resolve the ID prefix
    from applyai.core.database import get_session
    from applyai.models.job import Job
    from sqlalchemy import select
    
    async def resolve_id():
        settings = get_settings()
        init_engine(settings.database_url)
        async with get_session() as session:
            stmt = select(Job).where(Job.id.startswith(job_id))
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                err_console.print(f"[red]Job matching prefix {job_id} not found.[/red]")
                return None
            return job.id
            
    full_id = asyncio.run(resolve_id())
    if full_id:
        asyncio.run(_generate_resume(full_id))
