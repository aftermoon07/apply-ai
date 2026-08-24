"""Tests for OutreachAgent — two-step RAG evidence-grounded messaging."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from applyai.agents.outreach_agent import OutreachAgent, OutreachDrafts, EvidenceSelection
from applyai.providers.null import NullProvider


@pytest.mark.asyncio
async def test_outreach_agent_provider_failure_returns_fallback():
    """If provider raises on both steps, a needs_review fallback is returned."""
    mock_provider = MagicMock()
    mock_provider.generate_structured = AsyncMock(side_effect=Exception("network error"))

    agent = OutreachAgent(provider=mock_provider)
    result = await agent.generate_outreach(
        job_role="Engineer", company="Acme", ats_keywords=["Python"], candidate_profile={}
    )

    assert isinstance(result, OutreachDrafts)
    assert result.needs_review is True
    assert "Failed to generate" in result.linkedin_note


@pytest.mark.asyncio
async def test_outreach_agent_two_step_evidence_isolation():
    """The drafting step must NOT receive the full candidate_profile — only selected facts."""
    call_count = 0
    drafting_prompt_args = {}

    async def mock_generate(system_prompt, user_prompt, response_model):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Evidence selection step
            return EvidenceSelection(selected_facts=["Built X with Python", "Led team of 5"])
        else:
            # Drafting step
            drafting_prompt_args["user_prompt"] = user_prompt
            return OutreachDrafts(
                linkedin_note="Hi", cold_email="Dear HM", referral_strategy="Search X", needs_review=False
            )

    mock_provider = MagicMock()
    mock_provider.generate_structured = mock_generate

    agent = OutreachAgent(provider=mock_provider)
    await agent.generate_outreach("Engineer", "Acme", ["Python"], {"identity": {"name": "Alex"}})

    assert call_count == 2, "Expected exactly 2 LLM calls (evidence + draft)"
    # The full candidate profile JSON must NOT appear in the drafting call
    assert '"identity"' not in drafting_prompt_args.get("user_prompt", "")
    # The selected facts must appear in the drafting call
    assert "Built X with Python" in drafting_prompt_args.get("user_prompt", "")


@pytest.mark.asyncio
async def test_outreach_referral_strategy_is_search_query():
    """The referral_strategy field should be a search query, not an invented contact name."""
    async def mock_generate(system_prompt, user_prompt, response_model):
        if response_model is EvidenceSelection:
            return EvidenceSelection(selected_facts=["5 yrs Python"])
        return OutreachDrafts(
            linkedin_note="note",
            cold_email="email",
            referral_strategy='LinkedIn search: "Acme" AND "Software Engineer" AND "IIT"',
            needs_review=False
        )

    mock_provider = MagicMock()
    mock_provider.generate_structured = mock_generate

    agent = OutreachAgent(provider=mock_provider)
    result = await agent.generate_outreach("Engineer", "Acme", ["Python"], {})

    assert "LinkedIn search" in result.referral_strategy or "search" in result.referral_strategy.lower()
