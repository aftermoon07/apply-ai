"""CLI commands for shortlist and show."""

import asyncio
import json
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from applyai.core.database import init_engine, get_session
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging
from applyai.models.job import Job
from applyai.models.scoring import JobScore
from applyai.models.analysis import JobAnalysis
from sqlalchemy import select, desc

console = Console()
err_console = Console(stderr=True)

shortlist_app = typer.Typer(
    name="shortlist",
    help="View shortlisted jobs.",
    no_args_is_help=False,
    invoke_without_command=True
)

async def _list_shortlist(limit: int):
    settings = get_settings()
    init_engine(settings.database_url)
    
    async with get_session() as session:
        # Join Job and JobScore, filter by score >= shortlist_min_score
        stmt = (
            select(Job, JobScore)
            .join(JobScore, Job.id == JobScore.job_id)
            .where(JobScore.overall_score >= settings.scoring.thresholds.shortlist_min_score)
            .order_by(desc(JobScore.overall_score))
            .limit(limit)
        )
        
        result = await session.execute(stmt)
        rows = result.all()
        
        if not rows:
            console.print("[yellow]No shortlisted jobs found.[/yellow]")
            return
            
        table = Table(title="Shortlisted Jobs")
        table.add_column("ID", justify="left", style="cyan", no_wrap=True)
        table.add_column("Company", style="magenta")
        table.add_column("Role", style="green")
        table.add_column("Score", justify="right", style="blue")
        table.add_column("Recommendation", justify="right")
        
        for job, score in rows:
            table.add_row(
                job.id[:8],
                job.company or "Unknown",
                job.role or "Unknown",
                f"{score.overall_score:.1f}",
                score.recommendation
            )
            
        console.print(table)

@shortlist_app.callback()
def shortlist_main(
    limit: int = typer.Option(20, "--limit", help="Max jobs to show"),
) -> None:
    """View the top shortlisted jobs."""
    setup_logging()
    asyncio.run(_list_shortlist(limit))


show_app = typer.Typer(name="show", help="Show detailed job analysis.")

async def _show_job(job_id: str):
    settings = get_settings()
    init_engine(settings.database_url)
    
    async with get_session() as session:
        # Try to find job by full ID or prefix
        stmt = select(Job).where(Job.id.startswith(job_id))
        job = (await session.execute(stmt)).scalar_one_or_none()
        
        if not job:
            console.print(f"[red]Job {job_id} not found.[/red]")
            return
            
        console.print(Panel.fit(f"[bold]{job.role}[/bold] at [bold]{job.company}[/bold]", title=f"Job {job.id}"))
        
        analysis = (await session.execute(select(JobAnalysis).filter_by(job_id=job.id))).scalar_one_or_none()
        score = (await session.execute(select(JobScore).filter_by(job_id=job.id))).scalar_one_or_none()
        
        if analysis:
            console.print(f"[bold cyan]Analysis Status:[/bold cyan] {analysis.analysis_status}")
            console.print(f"[bold cyan]Role Level:[/bold cyan] {analysis.role_level}")
            console.print(f"[bold cyan]Tech Stack:[/bold cyan] {', '.join(json.loads(analysis.tech_stack or '[]'))}")
        
        if score:
            console.print(f"\n[bold green]Overall Score:[/bold green] {score.overall_score:.1f} ({score.recommendation})")
            console.print(f"[bold green]Matching Skills:[/bold green] {', '.join(json.loads(score.matching_skills or '[]'))}")
            console.print(f"[bold red]Missing Skills:[/bold red] {', '.join(json.loads(score.missing_skills or '[]'))}")
            console.print(f"[bold yellow]Concerns:[/bold yellow] {', '.join(json.loads(score.concerns or '[]'))}")
            
@show_app.command("job")
def show_job(job_id: str = typer.Argument(..., help="Job ID (or prefix)")) -> None:
    """Show detailed analysis and score for a job."""
    setup_logging()
    asyncio.run(_show_job(job_id))
