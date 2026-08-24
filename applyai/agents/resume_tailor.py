"""
Resume Tailor Agent.

Uses the configured AIProvider to generate a job-specific resume in Markdown.
It relies on the JobAnalysisOutput and CandidateSnapshot, avoiding the raw
job description to save context tokens.
"""

import json
from applyai.providers.base import AIProvider
from applyai.schemas.analysis import JobAnalysisOutput
from applyai.models.scoring import CandidateSnapshot
from applyai.core.config import get_settings

class ResumeTailorAgent:
    """Agent that generates tailored resumes."""

    def __init__(self, provider: AIProvider):
        self.provider = provider
        self.settings = get_settings()

    async def tailor(
        self,
        company: str,
        role: str,
        analysis: JobAnalysisOutput,
        snapshot: CandidateSnapshot
    ) -> str:
        """Generate a tailored markdown resume."""
        
        system_prompt = (
            "You are an expert resume writer. Generate a highly tailored resume in Markdown format. "
            "You will be given a specific job's extracted requirements and a candidate's profile. "
            "Follow these strict rules:\n"
            "1. Do NOT invent or fabricate any experience, skills, degrees, or certifications.\n"
            "2. Re-order and emphasize existing facts to highlight relevance to the job.\n"
            "3. Use a clean, professional Markdown layout with standard sections: Summary, Experience, Projects, Education, Skills.\n"
            "4. Only output the markdown content, no extra conversational text.\n"
        )

        user_prompt = f"""
        # Job Target
        Company: {company or 'Unknown'}
        Role: {role or 'Unknown'}
        Role Level: {analysis.role_level}
        Tech Stack: {analysis.tech_stack}
        Required Skills: {analysis.required_skills}
        Key Responsibilities: {analysis.key_responsibilities}
        
        # Candidate Profile
        {snapshot.snapshot}
        """

        try:
            resume_md = await self.provider.generate_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            return resume_md
        except Exception as e:
            return f"# Generation Failed\n\nError: {str(e)}"
