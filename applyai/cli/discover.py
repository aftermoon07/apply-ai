"""CLI commands for discovery."""

import asyncio
import typer
from rich.console import Console

from applyai.core.database import init_engine
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging
from applyai.services.discovery_service import DiscoveryService

console = Console()
err_console = Console(stderr=True)

discover_app = typer.Typer(
    name="discover",
    help="Run the job discovery pipeline.",
    no_args_is_help=True,
)

async def _run_discovery():
    settings = get_settings()
    init_engine(settings.database_url)
    
    service = DiscoveryService()
    results = await service.run_discovery()
    
    if not results:
        console.print("[yellow]No new jobs discovered or discovery is disabled.[/yellow]")
        return
        
    for source, net_new in results.items():
        if net_new > 0:
            console.print(f"[green]✓ {source}: {net_new} net-new jobs ingested.[/green]")
        else:
            console.print(f"[dim]- {source}: 0 net-new jobs.[/dim]")

@discover_app.command("run")
def run() -> None:
    """Iterate over all enabled sources and discover net-new jobs."""
    setup_logging()
    console.print("Starting job discovery...")
    asyncio.run(_run_discovery())
