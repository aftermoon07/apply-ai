"""CLI command for daily job search workflow."""

import asyncio
import typer
from rich.console import Console

from applyai.core.database import init_engine
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging
from applyai.services.pipeline_service import PipelineService
from applyai.cli.shortlist import _list_shortlist

console = Console()
daily_app = typer.Typer(
    name="daily",
    help="Run the daily job search workflow (discover, analyze, and view shortlist).",
    no_args_is_help=False,
    invoke_without_command=True
)

@daily_app.callback()
def run_daily(
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Max concurrent LLM analyses"),
    limit: int = typer.Option(20, "--limit", help="Max shortlisted jobs to show")
) -> None:
    """Run the pipeline to discover and analyze jobs, then display the shortlist."""
    setup_logging()
    
    async def _workflow():
        console.print("[bold]1. Running automated pipeline (Discovery -> Analysis)...[/bold]")
        settings = get_settings()
        init_engine(settings.database_url)
        
        service = PipelineService()
        results = await service.run_full_pipeline(max_concurrent_analyses=concurrency)
        
        console.print(f"  [green]✓ Discovered {results['discovered']} new jobs.[/green]")
        console.print(f"  [green]✓ Analyzed {results['analyzed']} jobs.[/green]")
        console.print(f"  [green]✓ Generated {results['shortlisted_resumes_generated']} resumes.[/green]")
        
        console.print("\n[bold]2. Top Shortlisted Jobs[/bold]")
        await _list_shortlist(limit=limit)
        
        console.print("\n[dim]Next steps:[/dim]")
        console.print("  - Inspect a job:      [cyan]applyai show job <ID>[/cyan]")
        console.print("  - Generate QA/drafts: [cyan]applyai prep run <ID>[/cyan]")
        console.print("  - Update status:      [cyan]applyai track update <ID> applied[/cyan]")
        
    asyncio.run(_workflow())
