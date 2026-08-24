"""CLI commands for evaluation."""

import asyncio
import typer
from rich.console import Console
from rich.panel import Panel

from applyai.core.logging import setup_logging
from applyai.eval.runner import EvalRunner
from applyai.core.config import get_settings

console = Console()
err_console = Console(stderr=True)

eval_app = typer.Typer(
    name="eval",
    help="Run the evaluation framework against synthetic datasets.",
    no_args_is_help=True,
)

async def _run_eval(dataset: str):
    settings = get_settings()
    
    # Check if provider is none, we should probably warn them
    if settings.ai.provider == "none":
        console.print("[yellow]Warning: Running eval with NullProvider. It will return dummy data and likely fail.[/yellow]")
        
    runner = EvalRunner(dataset)
    try:
        results = await runner.run_eval()
        
        passed = results["passed"]
        failed = results["failed"]
        total = results["total"]
        
        if failed == 0:
            color = "green"
        else:
            color = "red"
            
        panel_text = (
            f"[bold {color}]Evaluation Results:[/bold {color}]\n"
            f"Total: {total}\n"
            f"Passed: {passed}\n"
            f"Failed: {failed}\n\n"
        )
        
        for detail in results["details"]:
            if detail["status"] == "fail":
                panel_text += f"[red]ID {detail['id']} failed:[/red]\n"
                for err in detail["errors"]:
                    panel_text += f"  - {err}\n"
                    
        console.print(Panel.fit(panel_text, title="Eval Run", border_style=color))
    except Exception as e:
        err_console.print(f"[red]Eval run failed: {e}[/red]")

@eval_app.command("run")
def run(
    dataset: str = typer.Option("data/eval_dataset.json", "--dataset", "-d", help="Path to eval dataset")
) -> None:
    """Run prompt evaluation suite."""
    setup_logging()
    console.print(f"[bold]Starting evaluation against {dataset}...[/bold]")
    asyncio.run(_run_eval(dataset))
