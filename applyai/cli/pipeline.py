"""CLI commands for end-to-end pipeline orchestration."""

import asyncio
import typer
from rich.console import Console
from rich.panel import Panel

from applyai.core.database import init_engine
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging
from applyai.services.pipeline_service import PipelineService

console = Console()
err_console = Console(stderr=True)

pipeline_app = typer.Typer(
    name="pipeline",
    help="Run the end-to-end automation pipeline.",
    no_args_is_help=True,
)

async def _run_pipeline(concurrency: int):
    settings = get_settings()
    init_engine(settings.database_url)
    
    service = PipelineService()
    results = await service.run_full_pipeline(max_concurrent_analyses=concurrency)
    
    panel_text = (
        f"[bold cyan]Discovered:[/bold cyan] {results['discovered']} new jobs\n"
        f"[bold green]Analyzed:[/bold green] {results['analyzed']} jobs\n"
        f"[bold magenta]Resumes Generated:[/bold magenta] {results['shortlisted_resumes_generated']} resumes\n"
        f"[bold red]Errors:[/bold red] {results['errors']}"
    )
    
    console.print(Panel.fit(panel_text, title="Pipeline Results", border_style="green"))

@pipeline_app.command("run")
def run(
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Max concurrent LLM analyses")
) -> None:
    """Run the full job acquisition pipeline: Discovery -> Analysis -> Shortlist -> Resumes."""
    setup_logging()
    console.print("[bold]Starting automated pipeline...[/bold]")
    asyncio.run(_run_pipeline(concurrency))
