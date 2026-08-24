"""CLI commands for application prep and outreach generation."""

import asyncio
import typer
import json
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from applyai.core.database import init_engine, get_session
from applyai.core.config import get_settings
from applyai.core.logging import setup_logging
from applyai.models.job import Job
from applyai.models.analysis import JobAnalysis
from applyai.agents.qa_agent import QAAgent
from applyai.agents.outreach_agent import OutreachAgent
from sqlalchemy import select

console = Console()
err_console = Console(stderr=True)

prep_app = typer.Typer(
    name="prep",
    help="Prepare application QA and outreach drafts (Human-in-the-loop).",
    no_args_is_help=True,
)

async def _run_prep(job_id: str):
    settings = get_settings()
    init_engine(settings.database_url)
    
    async with get_session() as session:
        stmt = select(Job, JobAnalysis).join(JobAnalysis, Job.id == JobAnalysis.job_id).where(Job.id == job_id)
        result = (await session.execute(stmt)).first()
        
    if not result:
        err_console.print(f"[red]Job {job_id} or its analysis not found.[/red]")
        return
        
    job, analysis = result
    
    console.print(f"[bold cyan]Preparing Application for {job.company} - {job.role}...[/bold cyan]")
    
    # Load profile via shared loader (not via private AnalysisService method)
    from applyai.core.candidate_loader import load_candidate_profile
    profile = load_candidate_profile(settings)
    
    # QA
    console.print("[dim]Running QA Agent...[/dim]")
    qa_agent = QAAgent()
    qa_result = await qa_agent.generate_answers(job.job_description or "", profile)
    
    qa_text = ""
    for ans in qa_result.answers:
        review_tag = "[red][NEEDS REVIEW][/red] " if ans.needs_review else "[green][OK][/green] "
        qa_text += f"**Q:** {ans.question}\n{review_tag}**A:** {ans.answer}\n\n"
        
    console.print(Panel(Markdown(qa_text), title="Application Form QA Drafts", border_style="blue"))
    
    # Outreach
    console.print("[dim]Running Outreach Agent (Evidence-Grounded)...[/dim]")
    outreach_agent = OutreachAgent()
    ats_keywords = json.loads(analysis.ats_keywords) if analysis.ats_keywords else []
    
    drafts = await outreach_agent.generate_outreach(job.role, job.company, ats_keywords, profile)
    
    outreach_text = (
        f"### LinkedIn Note\n{drafts.linkedin_note}\n\n"
        f"### Cold Email\n{drafts.cold_email}\n\n"
        f"### Referral Strategy\n{drafts.referral_strategy}"
    )
    
    console.print(Panel(Markdown(outreach_text), title="Outreach Drafts", border_style="magenta"))
    console.print("[bold yellow]Remember: These are local drafts only. No external actions were taken.[/bold yellow]")

@prep_app.command("run")
def run(
    job_id: str = typer.Argument(..., help="Job ID")
) -> None:
    """Generate QA and Outreach drafts for human review."""
    setup_logging()
    asyncio.run(_run_prep(job_id))
