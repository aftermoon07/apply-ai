"""CLI commands for application tracking."""

import asyncio
import typer
from rich.console import Console
from rich.table import Table

from applyai.core.database import init_engine, get_session
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging
from applyai.services.application_service import ApplicationService
from applyai.models.application import Application
from applyai.models.job import Job
from sqlalchemy import select

console = Console()
err_console = Console(stderr=True)

track_app = typer.Typer(
    name="track",
    help="Track application lifecycle states.",
    no_args_is_help=True,
)

async def _update_status(job_id: str, status: str):
    settings = get_settings()
    init_engine(settings.database_url)
    service = ApplicationService()
    try:
        app = await service.get_or_create_application(job_id)
        app = await service.update_status(app.id, status)
        console.print(f"[green]Successfully updated application for job {job_id} to '{status}'.[/green]")
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")

@track_app.command("update")
def update(
    job_id: str = typer.Argument(..., help="Job ID"),
    status: str = typer.Argument(..., help="New status (e.g. prepared, applied, interviewing)")
) -> None:
    """Update an application's status."""
    setup_logging()
    asyncio.run(_update_status(job_id, status))

async def _list_status(status: str):
    settings = get_settings()
    init_engine(settings.database_url)
    
    async with get_session() as session:
        stmt = (
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(Application.status == status)
        )
        results = (await session.execute(stmt)).all()
        
    if not results:
        console.print(f"No applications in status: {status}")
        return
        
    table = Table(title=f"Applications - {status.upper()}")
    table.add_column("App ID", style="dim")
    table.add_column("Job ID", style="dim")
    table.add_column("Company", style="cyan")
    table.add_column("Role", style="magenta")
    
    for app, job in results:
        table.add_row(app.id[:8], job.id[:8], job.company, job.role)
        
    console.print(table)

@track_app.command("list")
def list_status(
    status: str = typer.Option(..., "--status", "-s", help="Status to filter by")
) -> None:
    """List applications by status."""
    setup_logging()
    asyncio.run(_list_status(status))
