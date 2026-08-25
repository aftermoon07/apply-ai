"""CLI commands for candidate profile management.

Commands:
    applyai profile validate   — validate the loaded candidate profile
"""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from applyai.core.config import get_settings
from applyai.core.logging import setup_logging

console = Console()
err_console = Console(stderr=True)

profile_app = typer.Typer(
    name="profile",
    help="Candidate profile management commands.",
    no_args_is_help=True,
)


@profile_app.command("validate")
def validate_profile() -> None:
    """Validate the candidate profile and show a completeness report.

    Shows validation status, completeness, and missing fields.
    Does NOT print private candidate values.
    """
    setup_logging()
    settings = get_settings()

    from applyai.core.candidate_loader import (
        load_candidate_profile_with_source,
        validate_candidate_profile,
        profile_completeness,
        ProfileValidationError,
        REQUIRED_DOCUMENTS,
    )

    # 1. Load
    try:
        result = load_candidate_profile_with_source(settings)
    except RuntimeError as e:
        err_console.print(f"[red bold]Profile Load Error:[/red bold] {e}")
        raise typer.Exit(code=1)

    profile = result.profile
    source_label = (
        "[green]private[/green]" if result.profile_source == "private"
        else "[yellow]example (synthetic)[/yellow]"
    )

    console.print(f"\n[bold]Profile source:[/bold] {source_label}")

    # 2. Validate
    validation_ok = True
    try:
        validate_candidate_profile(profile)
        console.print("[green bold]Schema validation: PASS[/green bold]")
    except ProfileValidationError as e:
        console.print(f"[red bold]Schema validation: FAIL[/red bold]")
        console.print(Panel(str(e), title="Validation Errors", border_style="red"))
        validation_ok = False

    # 3. Completeness
    completeness = profile_completeness(profile)

    # Documents table
    doc_table = Table(title="Required Documents", box=box.SIMPLE)
    doc_table.add_column("Document", style="cyan")
    doc_table.add_column("Status")
    for doc in sorted(REQUIRED_DOCUMENTS):
        if doc in completeness["present_documents"]:
            doc_table.add_row(doc, "[green]✓ present[/green]")
        else:
            doc_table.add_row(doc, "[red]✗ missing[/red]")
    console.print(doc_table)

    # Skills summary (counts only — no actual skill names)
    skill_counts = completeness["skill_counts_by_level"]
    if skill_counts:
        skill_table = Table(title="Skill Count by Level", box=box.SIMPLE)
        skill_table.add_column("Level", style="cyan")
        skill_table.add_column("Count")
        for level in ("strong", "working", "basic", "learning", "none"):
            count = skill_counts.get(level, 0)
            if count:
                skill_table.add_row(level, str(count))
        console.print(skill_table)

    # Summary counts
    console.print(f"  Experience entries: {completeness['experience_entries']}")
    console.print(f"  Education entries:  {completeness['education_entries']}")
    console.print(f"  Project entries:    {completeness['project_entries']}")
    console.print(f"  Certifications:     {completeness['certification_entries']}")
    
    # Evidence Integrity
    evidence = completeness.get("evidence_metrics", {})
    valid_ev = evidence.get("valid", 0)
    invalid_ev = evidence.get("invalid", 0)
    total_ev = valid_ev + invalid_ev
    if total_ev > 0:
        if invalid_ev == 0:
            console.print(f"\n[bold green]✓ Evidence Integrity:[/bold green] All {valid_ev} evidence references are valid.")
        else:
            console.print(f"\n[bold red]✗ Evidence Integrity:[/bold red] {invalid_ev} invalid references out of {total_ev} total.")
    else:
        console.print("\n[dim]Evidence Integrity: No evidence references found.[/dim]")

    if completeness["missing_documents"]:
        console.print(
            f"\n[yellow]Missing optional/required documents:[/yellow] "
            f"{', '.join(completeness['missing_documents'])}"
        )

    # Final status
    if validation_ok and completeness["is_complete"]:
        console.print("\n[bold green]✓ Profile is valid and complete.[/bold green]")
    elif validation_ok and not completeness["is_complete"]:
        console.print(
            "\n[bold yellow]⚠ Profile is valid but incomplete "
            f"(missing: {', '.join(completeness['missing_documents'])}).[/bold yellow]"
        )
    else:
        console.print("\n[bold red]✗ Profile has validation errors. See above.[/bold red]")
        raise typer.Exit(code=1)
