"""Tests for re-analysis idempotency guard — prevents duplicate LLM calls."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_analyze_and_score_skips_already_scored_job():
    """Jobs with status 'scored' must not trigger LLM calls again."""
    from applyai.services.analysis_service import AnalysisService

    # Build a mock job with the necessary string attributes
    mock_job = MagicMock(spec=["id", "status", "source", "job_url", "source_job_id",
                                "company", "role", "location", "job_description",
                                "content_hash", "date_discovered"])
    mock_job.status = "scored"
    mock_job.id = "job-already-scored"
    mock_job.source = "test"
    mock_job.job_url = "http://test.com"
    mock_job.source_job_id = None
    mock_job.company = "ACME"
    mock_job.role = "Engineer"
    mock_job.location = "Remote"
    mock_job.job_description = "Some JD"
    mock_job.content_hash = "abc123"
    mock_job.date_discovered = "2024-01-01"

    service = AnalysisService.__new__(AnalysisService)
    service._repo = MagicMock()
    service._repo.get_by_id = AsyncMock(return_value=mock_job)
    service.analyzer = MagicMock()
    service.analyzer.analyze = AsyncMock()
    service.matcher = MagicMock()
    service.matcher.match = AsyncMock()
    service.scorer = MagicMock()
    service.settings = MagicMock()
    service.settings.ai.provider = "none"
    service._events = MagicMock()

    result = await service.analyze_and_score("job-already-scored")

    # Should return immediately without calling LLM agents
    service.analyzer.analyze.assert_not_called()
    service.matcher.match.assert_not_called()
    assert result is mock_job
