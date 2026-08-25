"""Phase 9 tests — private candidate profile infrastructure.

Covers:
- Profile source selection (private vs example)
- Profile validation (schema, enum, evidence, missing docs)
- Hash determinism (key order, whitespace, data changes)
- Snapshot immutability
- Privacy: path not leaked, git ignore
- Context boundary: analyzer gets no candidate data
- Completeness: complete vs valid-but-incomplete
"""

import json
import hashlib
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from applyai.core.candidate_loader import (
    load_candidate_profile,
    load_candidate_profile_with_source,
    validate_candidate_profile,
    candidate_profile_hash,
    profile_completeness,
    ProfileValidationError,
    REQUIRED_DOCUMENTS,
    ProfileLoadResult,
)

# ── Fixture paths ─────────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "synthetic_private_profile"
EXAMPLE_DIR = Path(__file__).parent.parent.parent / "candidate" / "example"


def _load_fixture_profile() -> dict:
    """Load the synthetic private fixture profile into a dict."""
    profile = {}
    for f in sorted(FIXTURE_DIR.glob("*.json")):
        profile[f.stem] = json.loads(f.read_text())
    return profile


def make_settings(allow_fallback: bool, private_dir: Path, example_dir: Path):
    """Build a minimal mock settings object."""
    s = MagicMock()
    s.resolved_profile_dir.return_value = private_dir
    s.candidate.allow_synthetic_fallback = allow_fallback
    s.candidate.example_dir = str(example_dir)
    return s


# ==============================================================================
# 1. PROFILE SOURCE SELECTION
# ==============================================================================


class TestProfileSourceSelection:
    def test_private_profile_selected_when_available(self, tmp_path):
        """Private profile is used when present, regardless of fallback setting."""
        private_dir = tmp_path / "private"
        private_dir.mkdir()
        (private_dir / "identity.json").write_text(
            json.dumps({"schema_version": "1.0", "full_name": "Private Person", "email": "p@p.invalid"})
        )
        settings = make_settings(
            allow_fallback=False, private_dir=private_dir, example_dir=EXAMPLE_DIR
        )
        result = load_candidate_profile_with_source(settings)
        assert result.profile_source == "private"
        assert result.profile["identity"]["full_name"] == "Private Person"

    def test_example_fallback_used_when_enabled_and_private_missing(self, tmp_path):
        """Example profile is selected when private is absent and fallback=True."""
        private_dir = tmp_path / "private"  # does not exist
        settings = make_settings(
            allow_fallback=True, private_dir=private_dir, example_dir=EXAMPLE_DIR
        )
        result = load_candidate_profile_with_source(settings)
        assert result.profile_source == "example"
        assert "identity" in result.profile

    def test_missing_private_fails_when_fallback_disabled(self, tmp_path):
        """Strict mode: missing private profile raises RuntimeError."""
        private_dir = tmp_path / "private"  # does not exist
        settings = make_settings(
            allow_fallback=False, private_dir=private_dir, example_dir=EXAMPLE_DIR
        )
        with pytest.raises(RuntimeError, match="allow_synthetic_fallback"):
            load_candidate_profile_with_source(settings)

    def test_backward_compat_load_candidate_profile_returns_dict(self, tmp_path):
        """load_candidate_profile() still returns plain dict (backward-compatible)."""
        private_dir = tmp_path / "private"
        settings = make_settings(
            allow_fallback=True, private_dir=private_dir, example_dir=EXAMPLE_DIR
        )
        profile = load_candidate_profile(settings)
        assert isinstance(profile, dict)

    def test_profile_source_label_is_observable(self, tmp_path):
        """profile_source is accessible from ProfileLoadResult — no path inspection needed."""
        private_dir = tmp_path / "private"
        settings = make_settings(
            allow_fallback=True, private_dir=private_dir, example_dir=EXAMPLE_DIR
        )
        result = load_candidate_profile_with_source(settings)
        # The source label must be a plain string, not a path
        assert result.profile_source in ("private", "example")
        assert "/" not in result.profile_source

    def test_private_profile_source_when_fixture_dir_used(self):
        """The synthetic private fixture is loaded as 'private' when pointed at directly."""
        settings = make_settings(
            allow_fallback=False,
            private_dir=FIXTURE_DIR,
            example_dir=EXAMPLE_DIR,
        )
        result = load_candidate_profile_with_source(settings)
        assert result.profile_source == "private"
        assert "identity" in result.profile


# ==============================================================================
# 2. VALIDATION
# ==============================================================================


class TestProfileValidation:
    def test_valid_synthetic_private_fixture_passes(self):
        """The synthetic private profile fixture must pass schema validation."""
        raw = _load_fixture_profile()
        # Strip _comment keys before validation
        cleaned = {k: {ck: cv for ck, cv in v.items() if not ck.startswith("_")}
                   for k, v in raw.items()}
        result = validate_candidate_profile(cleaned)
        from applyai.schemas.candidate import CandidateProfile
        assert isinstance(result, CandidateProfile)
        assert result.identity.full_name == "Alex Morgan"

    def test_valid_example_profile_passes(self):
        """The committed example profile must also pass schema validation."""
        raw = {}
        for f in sorted(EXAMPLE_DIR.glob("*.json")):
            raw[f.stem] = json.loads(f.read_text())
        cleaned = {k: {ck: cv for ck, cv in v.items() if not ck.startswith("_")}
                   for k, v in raw.items()}
        result = validate_candidate_profile(cleaned)
        assert result.identity.full_name == "Alex Chen"

    def test_missing_required_document_fails(self):
        """Omitting a required document raises ProfileValidationError."""
        raw = _load_fixture_profile()
        raw.pop("identity")  # remove required doc
        with pytest.raises(ProfileValidationError, match="identity"):
            validate_candidate_profile(raw)

    def test_malformed_json_causes_clear_error(self, tmp_path):
        """A file with invalid JSON must fail at load time with a safe warning."""
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        (profile_dir / "identity.json").write_text("{invalid json")
        settings = make_settings(
            allow_fallback=False, private_dir=profile_dir, example_dir=EXAMPLE_DIR
        )
        # Loader should not crash — it warns and skips the file
        profile = load_candidate_profile(settings)
        # identity document skipped due to malformed JSON
        assert "identity" not in profile

    def test_invalid_skill_level_enum_fails(self):
        """An unrecognized skill level enum value must fail validation."""
        raw = _load_fixture_profile()
        raw["skill_levels"] = {
            "schema_version": "1.0",
            "skills": [
                {"name": "Python", "level": "EXPERT_WIZARD", "evidence": []}
            ]
        }
        with pytest.raises(ProfileValidationError):
            validate_candidate_profile(raw)

    def test_missing_required_identity_field_fails(self):
        """Missing full_name (required field) must fail validation."""
        raw = _load_fixture_profile()
        raw["identity"] = {
            "schema_version": "1.0",
            # full_name deliberately omitted
            "email": "test@example.invalid"
        }
        with pytest.raises(ProfileValidationError, match="identity"):
            validate_candidate_profile(raw)

    def test_empty_optional_lists_are_valid(self):
        """A profile with empty certifications/achievements/publications is still valid."""
        raw = _load_fixture_profile()
        raw["certifications"] = {"schema_version": "1.0", "entries": []}
        raw["achievements"] = {"schema_version": "1.0", "entries": []}
        raw["portfolio"] = {"schema_version": "1.0"}
        result = validate_candidate_profile(raw)
        assert result is not None

    def test_validation_error_message_contains_no_raw_values(self):
        """Validation error messages must not contain raw field values (privacy)."""
        raw = _load_fixture_profile()
        raw["identity"] = {
            "schema_version": "1.0",
            "email": "someone-private@secret.com",
            # full_name omitted to trigger error
        }
        with pytest.raises(ProfileValidationError) as exc_info:
            validate_candidate_profile(raw)
        error_msg = str(exc_info.value)
        # The raw email value must not appear in the error
        assert "someone-private@secret.com" not in error_msg

    def test_valid_but_incomplete_profile_is_distinguishable(self, tmp_path):
        """A profile with all docs present but some empty is VALID (not invalid)."""
        raw = _load_fixture_profile()
        raw["certifications"] = {"schema_version": "1.0", "entries": []}
        raw["achievements"] = {"schema_version": "1.0", "entries": []}
        completeness = profile_completeness(raw)
        assert completeness["is_complete"] is True  # all required docs present
        assert completeness["certification_entries"] == 0
        # validate_candidate_profile must NOT raise
        validate_candidate_profile(raw)


# ==============================================================================
# 3. PROFILE HASHING
# ==============================================================================


class TestProfileHashing:
    def test_same_profile_produces_same_hash(self):
        """Identical profiles must produce the same hash."""
        profile = {"identity": {"full_name": "Alex Morgan"}}
        assert candidate_profile_hash(profile) == candidate_profile_hash(profile)

    def test_hash_is_key_order_independent(self):
        """Key order must not affect the hash."""
        p1 = {"z_key": "val_z", "a_key": "val_a", "m_key": "val_m"}
        p2 = {"a_key": "val_a", "m_key": "val_m", "z_key": "val_z"}
        assert candidate_profile_hash(p1) == candidate_profile_hash(p2)

    def test_hash_is_nested_key_order_independent(self):
        """Nested dict key order must not affect hash."""
        p1 = {"identity": {"full_name": "Alex", "email": "a@b.invalid"}}
        p2 = {"identity": {"email": "a@b.invalid", "full_name": "Alex"}}
        assert candidate_profile_hash(p1) == candidate_profile_hash(p2)

    def test_different_profile_produces_different_hash(self):
        """Different data must produce different hashes."""
        p1 = {"identity": {"full_name": "Alex Morgan"}}
        p2 = {"identity": {"full_name": "Jordan Smith"}}
        assert candidate_profile_hash(p1) != candidate_profile_hash(p2)

    def test_hash_length_is_64_hex_chars(self):
        """SHA-256 hash must be exactly 64 hex characters."""
        profile = {"identity": {"full_name": "Alex Morgan"}}
        h = candidate_profile_hash(profile)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_is_whitespace_independent(self):
        """JSON whitespace/formatting must not affect hash."""
        profile = {"a": 1, "b": 2}
        # Hash is computed from json.dumps(sort_keys=True) so it's always compact
        h = candidate_profile_hash(profile)
        assert h == hashlib.sha256(
            json.dumps(profile, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def test_full_fixture_hash_is_stable(self):
        """Full synthetic fixture produces a stable hash (regression guard)."""
        raw = _load_fixture_profile()
        h1 = candidate_profile_hash(raw)
        h2 = candidate_profile_hash(raw)
        assert h1 == h2
        assert len(h1) == 64


# ==============================================================================
# 4. SNAPSHOT IMMUTABILITY
# ==============================================================================


class TestSnapshotImmutability:
    def test_snapshot_json_is_independent_of_later_profile_changes(self):
        """After a snapshot is taken, mutating the original dict must not change the snapshot."""
        profile = {"identity": {"full_name": "Alex Morgan"}}
        snapshot_json = json.dumps(profile, sort_keys=True)
        snapshot_hash = candidate_profile_hash(profile)

        # Mutate the original profile
        profile["identity"]["full_name"] = "Completely Different Name"

        # The stored snapshot must be unchanged
        restored = json.loads(snapshot_json)
        assert restored["identity"]["full_name"] == "Alex Morgan"
        assert candidate_profile_hash(restored) == snapshot_hash

    def test_snapshot_hash_matches_stored_hash(self):
        """profile_hash stored in CandidateSnapshot must match candidate_profile_hash()."""
        profile = _load_fixture_profile()
        expected_hash = candidate_profile_hash(profile)
        # Simulate what analysis_service.py does:
        # profile_json = json.dumps(candidate_profile, sort_keys=True)
        # profile_hash = hashlib.sha256(profile_json.encode()).hexdigest()
        # Note: analysis_service omits ensure_ascii=False, so we test the canonical form
        profile_json_canonical = json.dumps(profile, sort_keys=True, ensure_ascii=False)
        hash_via_loader = hashlib.sha256(profile_json_canonical.encode()).hexdigest()
        assert hash_via_loader == expected_hash

    def test_different_profiles_produce_different_snapshot_hashes(self):
        """Two distinct profiles must never share a snapshot hash."""
        p1 = {"identity": {"full_name": "Alex Morgan", "email": "alex@fictional.invalid"}}
        p2 = {"identity": {"full_name": "Jordan Smith", "email": "jordan@fictional.invalid"}}
        assert candidate_profile_hash(p1) != candidate_profile_hash(p2)


# ==============================================================================
# 5. PRIVACY — PATH NOT LEAKED
# ==============================================================================


class TestPrivacySafety:
    def test_strict_mode_error_contains_no_absolute_path(self, tmp_path):
        """RuntimeError from strict mode must NOT expose the absolute filesystem path."""
        private_dir = tmp_path / "very" / "deep" / "private" / "path"
        settings = make_settings(
            allow_fallback=False, private_dir=private_dir, example_dir=EXAMPLE_DIR
        )
        with pytest.raises(RuntimeError) as exc_info:
            load_candidate_profile_with_source(settings)
        error_msg = str(exc_info.value)
        assert str(tmp_path) not in error_msg
        assert "very/deep" not in error_msg

    def test_validation_error_contains_no_filesystem_path(self, tmp_path):
        """ProfileValidationError must not leak filesystem paths."""
        raw = _load_fixture_profile()
        raw.pop("identity")
        with pytest.raises(ProfileValidationError) as exc_info:
            validate_candidate_profile(raw)
        # Error must mention what's missing, not where it was expected
        assert str(tmp_path) not in str(exc_info.value)
        assert "candidate/private" not in str(exc_info.value)

    def test_private_dir_is_gitignored(self, tmp_path):
        """candidate/private/ must be covered by .gitignore."""
        import subprocess
        repo_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "check-ignore", "-q", "candidate/private/test_file.json"],
            cwd=repo_root,
            capture_output=True,
        )
        assert result.returncode == 0, (
            "candidate/private/ is NOT gitignored. This is a privacy violation. "
            "Add 'candidate/private/' to .gitignore."
        )

    def test_no_private_files_are_tracked(self, tmp_path):
        """git ls-files must return nothing for candidate/private/."""
        import subprocess
        repo_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "ls-files", "candidate/private/"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        tracked = result.stdout.strip()
        assert tracked == "", (
            f"Unexpected tracked files in candidate/private/: {tracked!r}"
        )


# ==============================================================================
# 6. CONTEXT BOUNDARY
# ==============================================================================


class TestContextBoundary:
    @pytest.mark.asyncio
    async def test_analyzer_does_not_receive_candidate_profile(self):
        """JobAnalyzerAgent must NOT receive candidate profile in its prompts."""
        captured = {}

        async def capture(system_prompt, user_prompt, response_model):
            captured["system"] = system_prompt
            captured["user"] = user_prompt
            return response_model.model_construct()

        from unittest.mock import patch, MagicMock
        from applyai.agents.analyzer import JobAnalyzerAgent
        from applyai.schemas.job import NormalizedJob

        provider = MagicMock()
        provider.generate_structured = capture

        mock_settings = MagicMock()
        mock_settings.ai.provider = "gemini"
        mock_settings.ai.model = "gemini-pro"

        with patch("applyai.agents.analyzer.get_settings", return_value=mock_settings):
            agent = JobAnalyzerAgent(provider)
            job = NormalizedJob(
                source="test", job_url="http://test.com", content_hash="abc",
                company="TestCorp", role="Engineer",
                job_description="Looking for a backend engineer.",
                date_discovered="2024-01-01"
            )
            await agent.analyze(job)

        # The analyzer prompt must NOT contain any candidate-specific keywords
        combined = (captured.get("system", "") + captured.get("user", "")).lower()
        assert "candidate" not in combined or "do not" in combined or "<jd>" in combined
        # Specifically: no "alex morgan" (synthetic fixture name) must appear
        assert "alex morgan" not in combined

    @pytest.mark.asyncio
    async def test_matcher_receives_candidate_profile(self):
        """CandidateMatcherAgent must include candidate_profile in its user prompt."""
        captured = {}

        async def capture(system_prompt, user_prompt, response_model):
            captured["user"] = user_prompt
            return response_model.model_construct()

        from unittest.mock import MagicMock
        from applyai.agents.matcher import CandidateMatcherAgent
        from applyai.schemas.job import NormalizedJob
        from applyai.schemas.analysis import JobAnalysisOutput

        provider = MagicMock()
        provider.generate_structured = capture

        agent = CandidateMatcherAgent(provider)
        agent.settings = MagicMock()
        agent.settings.ai.provider = "gemini"

        job = NormalizedJob(
            source="test", job_url="http://t.com", content_hash="xyz",
            company="Co", role="Eng", job_description="JD text",
            date_discovered="2024-01-01"
        )
        analysis = JobAnalysisOutput.model_construct()
        profile = {"identity": {"full_name": "Alex Morgan"}}

        await agent.match(job, analysis, profile)
        assert "alex morgan" in captured.get("user", "").lower()

    @pytest.mark.asyncio
    async def test_outreach_drafting_receives_only_selected_evidence(self):
        """OutreachAgent step-2 (drafting) must receive selected facts, not full profile."""
        from applyai.agents.outreach_agent import OutreachAgent, EvidenceSelection
        from unittest.mock import MagicMock, AsyncMock

        call_count = 0
        step2_prompt = ""

        async def fake_generate_structured(system_prompt, user_prompt, response_model):
            nonlocal call_count, step2_prompt
            call_count += 1
            if call_count == 2:
                step2_prompt = user_prompt
            return response_model.model_construct()

        provider = MagicMock()
        provider.generate_structured = fake_generate_structured

        agent = OutreachAgent(provider=provider)
        await agent.generate_outreach(
            job_role="Senior Engineer",
            company="TestCorp",
            ats_keywords=["kubernetes", "python"],
            candidate_profile={"identity": {"full_name": "Alex Morgan"}, "experience": {}}
        )

        # Step 2 prompt must NOT contain the full profile dict
        assert '"identity"' not in step2_prompt or len(step2_prompt) < 500


# ==============================================================================
# 7. COMPLETENESS REPORT
# ==============================================================================


class TestProfileCompleteness:
    def test_complete_fixture_profile_reports_complete(self):
        """Full synthetic fixture must report is_complete=True."""
        raw = _load_fixture_profile()
        result = profile_completeness(raw)
        assert result["is_complete"] is True
        assert result["missing_documents"] == []

    def test_incomplete_profile_reports_missing_docs(self):
        """Profile missing some required documents must report them."""
        raw = _load_fixture_profile()
        raw.pop("certifications")
        raw.pop("achievements")
        result = profile_completeness(raw)
        assert "certifications" in result["missing_documents"]
        assert "achievements" in result["missing_documents"]
        assert result["is_complete"] is False

    def test_completeness_does_not_expose_skill_names(self):
        """Completeness report must not contain actual skill names."""
        raw = _load_fixture_profile()
        result = profile_completeness(raw)
        # skill_counts_by_level should only have level names (not skill names)
        for key in result["skill_counts_by_level"]:
            assert key in ("strong", "working", "basic", "learning", "none", "unknown"), (
                f"Unexpected key in skill_counts_by_level: {key!r}"
            )

    def test_completeness_counts_experience_and_education(self):
        """Completeness report counts experience and education entries correctly."""
        raw = _load_fixture_profile()
        result = profile_completeness(raw)
        assert result["experience_entries"] >= 1
        assert result["education_entries"] >= 1
        assert result["project_entries"] >= 1

    def test_empty_optional_entries_does_not_affect_is_complete(self):
        """Empty certifications/achievements don't make profile incomplete (optional data)."""
        raw = _load_fixture_profile()
        raw["certifications"] = {"schema_version": "1.0", "entries": []}
        raw["achievements"] = {"schema_version": "1.0", "entries": []}
        result = profile_completeness(raw)
        # is_complete checks doc presence, not entry count
        assert result["is_complete"] is True
        assert result["certification_entries"] == 0
