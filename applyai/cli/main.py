"""Root CLI application — placeholder for Phase 2."""

import typer

app = typer.Typer(
    name="applyai",
    help="AI-powered personal job acquisition agent.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show ApplyAI version."""
    from applyai import __version__

    typer.echo(f"ApplyAI v{__version__}")


if __name__ == "__main__":
    app()
