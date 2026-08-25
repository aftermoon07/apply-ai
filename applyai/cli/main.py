"""Root CLI application."""

import typer

from applyai.cli.ingest import ingest_app
from applyai.cli.analysis import analyze
from applyai.cli.shortlist import shortlist_app, show_app
from applyai.cli.resume import resume_app
from applyai.cli.discover import discover_app
from applyai.cli.pipeline import pipeline_app
from applyai.cli.eval import eval_app
from applyai.cli.track import track_app
from applyai.cli.prep import prep_app
from applyai.cli.profile import profile_app
from applyai.cli.usage import usage_app

app = typer.Typer(
    name="applyai",
    help="AI-powered personal job acquisition agent.",
    no_args_is_help=True,
)

app.add_typer(ingest_app, name="ingest")
app.command(name="analyze")(analyze)
app.add_typer(shortlist_app, name="shortlist")
app.add_typer(show_app, name="show")
app.add_typer(resume_app, name="resume")
app.add_typer(discover_app, name="discover")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(eval_app, name="eval")
app.add_typer(track_app, name="track")
app.add_typer(prep_app, name="prep")
app.add_typer(profile_app, name="profile")
app.add_typer(usage_app, name="usage")



@app.command()
def version() -> None:
    """Show ApplyAI version."""
    from applyai import __version__

    typer.echo(f"ApplyAI v{__version__}")


if __name__ == "__main__":
    app()
