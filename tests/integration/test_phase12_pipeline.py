import pytest
import os
import json
import time
from pathlib import Path

from pydantic import BaseModel
from typing import Type, TypeVar

from applyai.providers.base import AIProvider, ProviderContext
from applyai.core.config import get_settings
from applyai.core.database import get_session
from applyai.services.pipeline_service import PipelineService
from applyai.services.application_service import ApplicationService
from applyai.services.usage_service import UsageService
from applyai.services.usage_service import UsageService, UsageRecord
from applyai.models.job import Job
from applyai.models.analysis import JobAnalysis
from applyai.models.scoring import JobScore
from applyai.models.application import Application, ResumeVersion
from applyai.models.event import AuditEvent, EventType
from applyai.agents.qa_agent import QAAgent
from applyai.agents.outreach_agent import OutreachAgent

T = TypeVar("T", bound=BaseModel)

class MockProvider(AIProvider):
    """Deterministic MockProvider that emits usage telemetry like a real provider."""
    
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        context: ProviderContext | None = None
    ) -> T:
        start_time = time.monotonic()
        
        # Emulate latency
        latency_ms = int((time.monotonic() - start_time) * 1000)
        
        # Record usage
        usage_service = UsageService()
        record = UsageRecord(
            provider_name="mock",
            model_name="mock-model",
            operation="generate_structured",
            job_id=context.job_id if context else None,
            agent_name=context.agent_name if context else None,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            latency_ms=latency_ms,
            retry_count=0,
            success=True,
            error_type=None
        )
        await usage_service.record_usage(record)
            
        if getattr(response_model, "__name__", "") == "MatcherOutput":
            from applyai.schemas.scoring import ComponentScores
            return response_model.model_construct(
                component_scores=ComponentScores(skills=0.8, experience=0.9, domain=0.8, cultural=0.9, career_trajectory=1.0),
                matching_skills=["mock_skill"],
                missing_skills=[],
                transferable_skills=[],
                concerns=[],
                reasons=[],
                confidence=1.0
            )
        elif getattr(response_model, "__name__", "") == "JobAnalysisOutput":
            return response_model.model_construct(
                role_summary="Mock summary",
                required_skills=["mock_skill"],
                preferred_skills=[],
                tech_stack=["mock_tech"],
                key_responsibilities=["mock_resp"],
                role_level="mock_level",
                domain="mock_domain",
                is_remote=True,
                estimated_salary_usd=None,
                ats_keywords=["mock"]
            )
        elif getattr(response_model, "__name__", "") == "QAResult":
            from applyai.agents.qa_agent import QAAnswer
            return response_model.model_construct(
                answers=[QAAnswer(question="Q", answer="A", needs_review=False)]
            )
        elif getattr(response_model, "__name__", "") == "EvidenceSelection":
            return response_model.model_construct(
                selected_experience=[],
                selected_projects=[],
                reasoning="Mock reasoning"
            )
        elif getattr(response_model, "__name__", "") == "OutreachDrafts":
            return response_model.model_construct(
                linkedin_note="Deterministic Mock Text",
                cold_email="Deterministic Mock Text",
                referral_strategy="Deterministic Mock Text",
                needs_review=False
            )
        return response_model.model_construct()
        
    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        context: ProviderContext | None = None
    ) -> str:
        start_time = time.monotonic()
        
        latency_ms = int((time.monotonic() - start_time) * 1000)
        
        usage_service = UsageService()
        record = UsageRecord(
            provider_name="mock",
            model_name="mock-model",
            operation="generate_text",
            job_id=context.job_id if context else None,
            agent_name=context.agent_name if context else None,
            input_tokens=150,
            output_tokens=100,
            total_tokens=250,
            latency_ms=latency_ms,
            retry_count=0,
            success=True,
            error_type=None
        )
        await usage_service.record_usage(record)
            
        return "Deterministic Mock Text"

@pytest.fixture
def mock_provider_setup(monkeypatch):
    settings = get_settings()
    settings.ai.provider = "mock"
    settings.ai.model = "mock-model"
    settings.scoring.thresholds.shortlist_min_score = 0.0
    
    from applyai.core.config import ModelPricingConfig
    settings.ai.pricing = {
        "mock": {
            "mock-model": ModelPricingConfig(
                input_per_million_tokens=1.0,
                output_per_million_tokens=2.0
            )
        }
    }
    
    import applyai.providers.factory as factory
    import applyai.services.analysis_service as analysis_service
    
    original_get_provider = factory.get_provider
    
    def mock_get_provider():
        _settings = get_settings()
        if _settings.ai.provider == "mock":
            return MockProvider()
        return original_get_provider()
        
    monkeypatch.setattr(factory, "get_provider", mock_get_provider)
    if hasattr(analysis_service, "get_provider"):
        monkeypatch.setattr(analysis_service, "get_provider", mock_get_provider)
    
    # Also fix it for Matcher and QA Agent if they import it directly
    import applyai.agents.matcher as matcher
    if hasattr(matcher, "get_provider"):
        monkeypatch.setattr(matcher, "get_provider", mock_get_provider)
        
    return settings

@pytest.mark.asyncio
async def test_phase12_pipeline(test_db, mock_provider_setup, monkeypatch):
    settings = mock_provider_setup
    
    pipeline = PipelineService()
    results = await pipeline.run_full_pipeline(max_concurrent_analyses=2)
    
    assert results["discovered"] > 0
    assert results["analyzed"] == results["discovered"]
    assert results["errors"] == 0
    assert results["shortlisted_resumes_generated"] == results["discovered"]
    
    async with get_session() as session:
        from sqlalchemy import select
        job = (await session.execute(select(Job))).scalars().first()
        
        assert job.status == "scored"
        
        analysis = (await session.execute(select(JobAnalysis).filter_by(job_id=job.id))).scalars().first()
        assert analysis is not None
        
        score = (await session.execute(select(JobScore).filter_by(job_id=job.id))).scalars().first()
        assert score is not None
        
        resume = (await session.execute(select(ResumeVersion).filter_by(job_id=job.id))).scalars().first()
        assert resume is not None
        assert Path(resume.file_path).exists()
        assert ".." not in resume.file_path
        
        # QA Agent
        from applyai.core.candidate_loader import load_candidate_profile
        profile = load_candidate_profile(settings)
        qa = QAAgent()
        # Ensure QAAgent uses our mock
        qa.provider = MockProvider() 
        qa_result = await qa.generate_answers(job.job_description, profile)
        assert qa_result is not None
        
        # Outreach
        outreach = OutreachAgent()
        outreach.provider = MockProvider()
        outreach_result = await outreach.generate_outreach(job.role, job.company, [], profile)
        assert outreach_result.linkedin_note == "Deterministic Mock Text"
        
        # State Machine
        app_service = ApplicationService()
        app = await app_service.get_or_create_application(job.id)
        assert app.status == "draft"
        
        app = await app_service.update_status(app.id, "prepared")
        assert app.status == "prepared"
        
        app = await app_service.update_status(app.id, "applied")
        assert app.status == "applied"
        
        with pytest.raises(ValueError):
            await app_service.update_status(app.id, "draft")
            
        app = await app_service.update_status(app.id, "rejected")
        assert app.status == "rejected"
        
        events = (await session.execute(select(AuditEvent).filter_by(entity_id=app.id))).scalars().all()
        assert len(events) >= 3
        
        # Telemetry verification
        from applyai.models.usage import ProviderUsage
        usage_records = (await session.execute(select(ProviderUsage))).scalars().all()
        assert len(usage_records) > 0
        
        has_mock_usage = False
        for record in usage_records:
            if record.provider_name == "mock":
                has_mock_usage = True
                assert record.model_name == "mock-model"
                assert record.input_tokens in (100, 150)
                assert record.output_tokens in (50, 100)
                assert record.estimated_cost > 0
                # job_id and agent_name can be None since we might not have passed ProviderContext
        
        assert has_mock_usage, "No mock provider usage recorded"
            
    # Idempotency
    from applyai.discovery.adapters.mock import MockAdapter
    
    original_discover = MockAdapter.discover
    
    async def deterministic_discover(self, limit: int):
        # Always return the same 5 jobs
        jobs = []
        for i in range(limit):
            job_id = f"static-mock-job-{i}"
            jobs.append({
                "source": self.name,
                "job_url": f"https://example.com/jobs/{job_id}",
                "source_job_id": job_id,
                "company": f"StaticCorp {i+1}",
                "role": "Software Engineer",
                "location": "Remote",
                "job_description": "Static job.",
                "salary_raw": "$120k - $150k",
            })
        return jobs
        
    monkeypatch.setattr(MockAdapter, "discover", deterministic_discover)
    
    # Run once to ingest the static jobs
    await pipeline.run_full_pipeline(max_concurrent_analyses=2)
    
    # Run again to verify idempotency (they should be skipped)
    results_idempotent = await pipeline.run_full_pipeline(max_concurrent_analyses=2)
    assert results_idempotent["discovered"] == 0
    assert results_idempotent["analyzed"] == 0
