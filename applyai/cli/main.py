"""Root CLI application."""

import typer

from applyai.cli.ingest import ingest_app
from applyai.cli.analysis import analyze

app = typer.Typer(
    name="applyai",
    help="AI-powered personal job acquisition agent.",
    no_args_is_help=True,
)

app.add_typer(ingest_app, name="ingest")
app.command(name="analyze")(analyze)


@app.command()
def version() -> None:
    """Show ApplyAI version."""
    from applyai import __version__

    typer.echo(f"ApplyAI v{__version__}")


if __name__ == "__main__":
    app()
