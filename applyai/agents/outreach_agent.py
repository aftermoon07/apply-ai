"""Outreach Intelligence Agent — Two-step RAG for evidence-based messaging."""

import json
from pydantic import BaseModel
from typing import Any
from applyai.providers.factory import get_provider
from applyai.providers.base import AIProvider

class EvidenceSelection(BaseModel):
    selected_facts: list[str]

class OutreachDrafts(BaseModel):
    linkedin_note: str
    cold_email: str
    referral_strategy: str
    needs_review: bool

class OutreachAgent:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_provider()

    async def generate_outreach(
        self,
        job_role: str,
        company: str,
        ats_keywords: list[str],
        candidate_profile: dict[str, Any]
    ) -> OutreachDrafts:
        
        # Step 1: Evidence Selection
        evidence_prompt = (
            "You are an evidence selection layer. Given a Candidate Profile and Job Requirements, "
            "select 2 to 3 factual bullet points or metrics from the candidate's experience that directly align "
            "with the job requirements. DO NOT invent facts."
        )
        
        user_evidence_prompt = (
            f"Job: {job_role} at {company}\n"
            f"Keywords: {', '.join(ats_keywords)}\n\n"
            f"Candidate Profile:\n{json.dumps(candidate_profile, indent=2)}"
        )

        try:
            evidence = await self.provider.generate_structured(
                system_prompt=evidence_prompt,
                user_prompt=user_evidence_prompt,
                response_model=EvidenceSelection
            )
            facts = evidence.selected_facts
        except Exception:
            facts = ["Could not extract facts due to provider error."]

        # Step 2: Generation
        drafting_prompt = (
            "You are an expert career coach drafting outreach messages. "
            "You will be given the Job details and a set of STRICTLY verified facts about the candidate. "
            "Generate:\n"
            "1. A short LinkedIn connection note (under 300 chars) to the Hiring Manager.\n"
            "2. A concise cold email to the Hiring Manager.\n"
            "3. A Referral Strategy (actionable search strings to find alumni or mutuals, DO NOT invent names).\n"
            "CRITICAL: Base your drafts ONLY on the provided verified facts. Do not invent experience."
        )

        user_drafting_prompt = (
            f"Job: {job_role} at {company}\n"
            f"Verified Facts to include:\n- " + "\n- ".join(facts)
        )

        try:
            return await self.provider.generate_structured(
                system_prompt=drafting_prompt,
                user_prompt=user_drafting_prompt,
                response_model=OutreachDrafts
            )
        except Exception:
            return OutreachDrafts(
                linkedin_note="Failed to generate.",
                cold_email="Failed to generate.",
                referral_strategy="Failed to generate.",
                needs_review=True
            )
