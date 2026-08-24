"""Application QA Agent — Evidence-grounded form answering."""

import json
from pydantic import BaseModel
from typing import Any
from applyai.providers.factory import get_provider
from applyai.providers.base import AIProvider

class QAAnswer(BaseModel):
    question: str
    answer: str
    needs_review: bool
    evidence_used: str | None

class QAResult(BaseModel):
    answers: list[QAAnswer]

class QAAgent:
    def __init__(self, provider: AIProvider | None = None):
        self.provider = provider or get_provider()

    async def generate_answers(
        self,
        job_description: str,
        candidate_profile: dict[str, Any]
    ) -> QAResult:
        
        system_prompt = (
            "You are an AI assistant helping a candidate fill out a job application. "
            "First, deduce the 5 most likely standard application questions for this job based on its description "
            "(e.g., years of experience with X, right to work in Y, remote work willingness). "
            "Then, answer them strictly using the provided Candidate Profile. "
            "CRITICAL: You must be strictly evidence-grounded. Do NOT fabricate qualifications, years of experience, "
            "work authorization, or education. If an answer cannot be explicitly supported by the profile, "
            "you MUST set 'needs_review' to true and explain what is missing in the answer."
        )

        user_prompt = (
            f"Job Description:\n{job_description}\n\n"
            f"Candidate Profile:\n{json.dumps(candidate_profile, indent=2)}"
        )

        try:
            return await self.provider.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=QAResult
            )
        except Exception:
            # Fallback if provider is none or fails
            return QAResult(answers=[
                QAAnswer(question="Dummy question", answer="Dummy answer", needs_review=True, evidence_used=None)
            ])
