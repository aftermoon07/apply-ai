"""CLI command for AI provider usage telemetry."""

import asyncio
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from applyai.core.database import init_engine
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging
from applyai.services.usage_service import UsageService

console = Console()
err_console = Console(stderr=True)

usage_app = typer.Typer(
    name="usage",
    help="View AI provider usage telemetry and estimated costs.",
    no_args_is_help=False,
)

async def _show_usage(
    provider: str | None = None,
    model: str | None = None,
    job_id: str | None = None,
    operation: str | None = None,
    summary: bool = False
):
    settings = get_settings()
    init_engine(settings.database_url)
    usage_service = UsageService(settings)
    
    data = await usage_service.get_summary(
        provider=provider,
        model=model,
        job_id=job_id,
        operation=operation
    )
    
    if data["requests"] == 0:
        console.print("[yellow]No usage records found matching criteria.[/yellow]")
        return
        
    table = Table(title="AI Usage Telemetry", box=box.SIMPLE)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    
    table.add_row("Total Requests", str(data["requests"]))
    table.add_row("Input Tokens", f"{data['input_tokens']:,}")
    table.add_row("Output Tokens", f"{data['output_tokens']:,}")
    table.add_row("Total Tokens", f"{data['total_tokens']:,}")
    table.add_row("Retries", str(data["retries"]))
    
    cost_str = f"${data['estimated_cost']:.4f}" if data['estimated_cost'] else "Unknown (No pricing config)"
    table.add_row("Estimated Cost", cost_str, style="bold green")
    
    console.print(table)
    
    if not settings.ai.pricing:
        console.print("\n[dim]Note: Pricing is not configured in settings.yaml. Estimated cost cannot be calculated.[/dim]")

@usage_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    provider: str = typer.Option(None, help="Filter by provider (e.g., gemini, anthropic)"),
    model: str = typer.Option(None, help="Filter by model name"),
    job_id: str = typer.Option(None, help="Filter by Job ID"),
    operation: str = typer.Option(None, help="Filter by operation (e.g., generate_structured)"),
    summary: bool = typer.Option(False, "--summary", help="Show summary (default behavior)")
):
    """View AI usage telemetry."""
    if ctx.invoked_subcommand is None:
        setup_logging()
        asyncio.run(_show_usage(provider, model, job_id, operation, summary))
