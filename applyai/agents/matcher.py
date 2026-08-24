"""
Candidate Matcher Agent.

Compares a JobAnalysisOutput and NormalizedJob against a Candidate profile.
Uses the configured AIProvider to evaluate qualitative alignment.
"""

import json
from pydantic import BaseModel
from typing import List, Dict, Any

from applyai.providers.base import AIProvider
from applyai.schemas.job import NormalizedJob
from applyai.schemas.analysis import JobAnalysisOutput
from applyai.schemas.scoring import ComponentScores
from applyai.core.config import get_settings

class MatcherOutput(BaseModel):
    """Schema for the LLM to output qualitative matching results."""
    component_scores: ComponentScores
    matching_skills: list[str]
    missing_skills: list[str]
    transferable_skills: list[str]
    concerns: list[str]
    reasons: list[str]
    confidence: float

class CandidateMatcherAgent:
    """Agent that matches candidate profile to a job."""

    def __init__(self, provider: AIProvider):
        self.provider = provider
        self.settings = get_settings()

    async def match(
        self,
        job: NormalizedJob,
        analysis: JobAnalysisOutput,
        candidate_profile: dict[str, Any]
    ) -> MatcherOutput:
        """Evaluate fit between candidate and job."""
        
        if self.settings.ai.provider == "none":
            # Return dummy output if AI is disabled
            return MatcherOutput(
                component_scores=ComponentScores(),
                matching_skills=[],
                missing_skills=[],
                transferable_skills=[],
                concerns=[],
                reasons=["Skipped: AI provider disabled"],
                confidence=0.0
            )

        system_prompt = (
            "You are an expert technical recruiter evaluating a candidate's fit for a specific role. "
            "You will be given a Candidate Profile (skills, experience, preferences) and a Job Profile (extracted requirements). "
            "Evaluate the match qualitatively and provide scores from 0.0 to 100.0 for each component. "
            "Identify matching skills, missing skills, transferable skills, concerns, and reasons for your evaluation. "
            "Be highly critical and realistic. Do not inflate scores. "
            "Return a confidence score between 0.0 and 1.0 reflecting how sure you are based on the available data."
        )

        user_prompt = f"""
        # Job Profile
        Company: {job.company}
        Role: {job.role}
        Required Skills: {analysis.required_skills}
        Tech Stack: {analysis.tech_stack}
        Role Level: {analysis.role_level}
        Key Responsibilities: {analysis.key_responsibilities}
        
        # Candidate Profile
        {json.dumps(candidate_profile, indent=2)}
        """

        try:
            return await self.provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=MatcherOutput
            )
        except Exception as e:
            return MatcherOutput(
                component_scores=ComponentScores(),
                matching_skills=[],
                missing_skills=[],
                transferable_skills=[],
                concerns=[f"Matching failed: {str(e)}"],
                reasons=[],
                confidence=0.0
            )
