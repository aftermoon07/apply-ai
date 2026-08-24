"""CLI analysis commands."""

import asyncio
import typer
from rich.console import Console

from applyai.core.database import init_engine
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging

console = Console()
err_console = Console(stderr=True)

analysis_app = typer.Typer(
    name="analysis",
    help="Run analysis and scoring pipelines.",
    no_args_is_help=True,
)

async def _run_analysis(limit: int):
    settings = get_settings()
    init_engine(settings.database_url)
    
    from applyai.services.analysis_service import AnalysisService
    service = AnalysisService()
    return await service.batch_analyze_and_score(limit=limit)

@analysis_app.command("analyze")
def analyze(
    limit: int = typer.Option(50, "--limit", help="Max jobs to analyze"),
) -> None:
    """Analyze and score pending jobs."""
    setup_logging()
    console.print(f"Starting batch analysis (limit {limit})...")
    
    results = asyncio.run(_run_analysis(limit))
    
    if not results:
        console.print("[yellow]No pending jobs to analyze.[/yellow]")
        return
        
    for r in results:
        console.print(f"[green]✓[/green] Analyzed job {r.id[:8]}... - Score: {r.score}")
