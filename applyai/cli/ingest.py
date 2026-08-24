"""
CLI ingestion commands.

Usage:
  applyai ingest --file job.txt --source manual
  applyai ingest --text --source manual
  applyai ingest --batch jobs.json --source json_file

All commands are synchronous wrappers around async service calls.
No business logic lives here — all orchestration is in JobService.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from applyai.core.database import create_all_tables, init_engine
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging

console = Console()
err_console = Console(stderr=True)

ingest_app = typer.Typer(
    name="ingest",
    help="Ingest job postings into the pipeline.",
    no_args_is_help=True,
)

# ── Database bootstrap helper ──────────────────────────────────────────────────


async def _ensure_db() -> None:
    """Initialize the database engine and create tables if needed."""
    settings = get_settings()
    init_engine(settings.database_url)
    await create_all_tables()


# ── Single file ingestion ──────────────────────────────────────────────────────


@ingest_app.command("file")
def ingest_file(
    file: Path = typer.Option(..., "--file", "-f", help="Path to job description file (.txt)"),
    source: str = typer.Option("manual", "--source", "-s", help="Source identifier"),
    company: Optional[str] = typer.Option(None, "--company", help="Company name (optional)"),
    role: Optional[str] = typer.Option(None, "--role", help="Job title (optional)"),
    url: Optional[str] = typer.Option(None, "--url", help="Job URL (optional)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """
    Ingest a job from a plain-text file.

    Example:
        applyai ingest file --file job.txt --source manual
        applyai ingest file --file job.txt --company "Acme Corp" --role "SWE" --url https://...
    """
    setup_logging()

    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(code=1)

    text = file.read_text(encoding="utf-8").strip()
    if not text:
        err_console.print(f"[red]File is empty:[/red] {file}")
        raise typer.Exit(code=1)

    from applyai.ingestion.manual import ManualSource
    from applyai.schemas.job import RawJobInput
    from applyai.services.job_service import JobService

    source_adapter = ManualSource()
    raw_inputs = list(
        source_adapter.parse(
            text,
            company=company,
            role=role,
            job_url=url,
        )
    )

    if not raw_inputs:
        err_console.print("[red]No content extracted from file.[/red]")
        raise typer.Exit(code=1)

    results = asyncio.run(_run_ingest(raw_inputs))
    _display_results(results, verbose=verbose)

    if any(r.status == "error" for r in results):
        raise typer.Exit(code=1)


# ── Stdin text ingestion ───────────────────────────────────────────────────────


@ingest_app.command("text")
def ingest_text(
    source: str = typer.Option("manual", "--source", "-s"),
    company: Optional[str] = typer.Option(None, "--company"),
    role: Optional[str] = typer.Option(None, "--role"),
    url: Optional[str] = typer.Option(None, "--url"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """
    Ingest a job from stdin (piped text).

    Example:
        cat job.txt | applyai ingest text --source manual
        cat job.txt | applyai ingest text --company "Acme" --role "Backend Engineer"
    """
    setup_logging()

    if sys.stdin.isatty():
        err_console.print(
            "[red]No stdin provided.[/red] "
            "Pipe text: [dim]cat job.txt | applyai ingest text[/dim]"
        )
        raise typer.Exit(code=1)

    text = sys.stdin.read().strip()
    if not text:
        err_console.print("[red]Stdin was empty.[/red]")
        raise typer.Exit(code=1)

    from applyai.ingestion.manual import ManualSource

    source_adapter = ManualSource()
    raw_inputs = list(
        source_adapter.parse(
            text,
            company=company,
            role=role,
            job_url=url,
        )
    )

    results = asyncio.run(_run_ingest(raw_inputs))
    _display_results(results, verbose=verbose)

    if any(r.status == "error" for r in results):
        raise typer.Exit(code=1)


# ── Batch JSON ingestion ───────────────────────────────────────────────────────


@ingest_app.command("batch")
def ingest_batch(
    file: Path = typer.Option(..., "--file", "-f", help="Path to JSON file"),
    source: str = typer.Option("json_file", "--source", "-s"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """
    Ingest jobs from a JSON file (array of job objects).

    Expected format:
        [{"company": "...", "role": "...", "job_description": "..."}, ...]

    Also accepts:
        {"jobs": [...]}
        Single object: {"company": "...", ...}

    Example:
        applyai ingest batch --file jobs.json
        applyai ingest batch --file jobs.json --source naukri_export
    """
    setup_logging()

    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(code=1)

    from applyai.ingestion.json_file import JsonFileSource

    try:
        source_adapter = JsonFileSource()
        source_adapter.source_id = source  # allow override
        raw_inputs = list(source_adapter.parse(file))
    except (json.JSONDecodeError, ValueError) as exc:
        err_console.print(f"[red]JSON parse error:[/red] {exc}")
        raise typer.Exit(code=1)

    if not raw_inputs:
        err_console.print("[yellow]Warning:[/yellow] No job records found in file.")
        raise typer.Exit(code=0)

    console.print(f"[dim]Loaded {len(raw_inputs)} job record(s) from {file.name}[/dim]")
    results = asyncio.run(_run_ingest(raw_inputs))
    _display_results(results, verbose=verbose)

    if any(r.status == "error" for r in results):
        raise typer.Exit(code=1)


# ── Async runner ───────────────────────────────────────────────────────────────


async def _run_ingest(raw_inputs):
    """Initialize DB and run batch ingestion."""
    from applyai.services.job_service import JobService

    await _ensure_db()
    service = JobService()
    return await service.ingest_batch(raw_inputs)


# ── Result display ─────────────────────────────────────────────────────────────


def _display_results(results, *, verbose: bool = False) -> None:
    """Display ingestion results as a Rich table."""
    from applyai.schemas.job import IngestionResult

    if not results:
        console.print("[yellow]No results.[/yellow]")
        return

    table = Table(
        title=f"Ingestion Results ({len(results)} job{'s' if len(results) != 1 else ''})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Status", style="bold", width=10)
    table.add_column("Company", width=20)
    table.add_column("Role", width=25)
    table.add_column("Source", width=12)
    table.add_column("Job ID", width=38)

    if verbose:
        table.add_column("Hash", width=14)
        table.add_column("URL", width=40)

    for r in results:
        status_style = {
            "inserted": "[green]✓ inserted[/green]",
            "duplicate": "[yellow]↺ duplicate[/yellow]",
            "error": "[red]✗ error[/red]",
        }.get(r.status, r.status)

        row = [
            status_style,
            r.company or "[dim]unknown[/dim]",
            r.role or "[dim]unknown[/dim]",
            r.source,
            r.job_id or "[dim]—[/dim]",
        ]

        if verbose:
            row.append(r.content_hash[:12] + "..." if r.content_hash else "—")
            row.append(r.job_url or "—")

        table.add_row(*row)

    console.print(table)

    # Summary
    inserted = sum(1 for r in results if r.status == "inserted")
    dupes = sum(1 for r in results if r.status == "duplicate")
    errors = sum(1 for r in results if r.status == "error")

    if inserted:
        console.print(f"[green]✓[/green] {inserted} new job(s) ingested")
    if dupes:
        console.print(f"[yellow]↺[/yellow] {dupes} duplicate(s) skipped")
    if errors:
        console.print(f"[red]✗[/red] {errors} error(s) — check logs")

    # Error messages
    for r in results:
        if r.status == "error":
            err_console.print(f"  [red]Error:[/red] {r.message}")
