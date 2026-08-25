import pytest
from applyai.core.candidate_loader import validate_candidate_profile, ProfileValidationError, profile_completeness

@pytest.fixture
def base_raw_profile():
    return {
        "identity": {"full_name": "Test User", "email": "test@test.com"},
        "education": {"entries": []},
        "experience": {"entries": [
            {"id": "exp1", "company": "A", "title": "SE", "start_date": "2020-01"}
        ]},
        "projects": {"entries": [
            {"id": "proj1", "name": "B", "description": "Proj B"}
        ]},
        "skills": {"categories": []},
        "skill_levels": {"skills": []},
        "achievements": {"entries": []},
        "certifications": {"entries": []},
        "portfolio": {},
        "preferences": {},
        "target_roles": {"roles": []},
        "constraints": {}
    }

def test_valid_experience_evidence_passes(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": ["experience:exp1"]}
    ]
    profile = validate_candidate_profile(base_raw_profile)
    assert len(profile.skill_levels.skills) == 1
    assert profile.skill_levels.skills[0].evidence == ["experience:exp1"]

def test_valid_project_evidence_passes(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "working", "evidence": ["project:proj1"]}
    ]
    profile = validate_candidate_profile(base_raw_profile)
    assert profile.skill_levels.skills[0].evidence == ["project:proj1"]

def test_missing_experience_id_fails(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": ["experience:exp2"]}
    ]
    with pytest.raises(ProfileValidationError, match="ID not found in experience"):
        validate_candidate_profile(base_raw_profile)

def test_missing_project_id_fails(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": ["project:proj2"]}
    ]
    with pytest.raises(ProfileValidationError, match="ID not found in projects"):
        validate_candidate_profile(base_raw_profile)

def test_unsupported_evidence_prefix_fails(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": ["company:A"]}
    ]
    with pytest.raises(ProfileValidationError, match="Unsupported evidence reference type: company"):
        validate_candidate_profile(base_raw_profile)

def test_duplicate_experience_ids_fail(base_raw_profile):
    base_raw_profile["experience"]["entries"].append(
        {"id": "exp1", "company": "C", "title": "SE2", "start_date": "2021-01"}
    )
    with pytest.raises(ProfileValidationError, match="experience.json: contains duplicate IDs"):
        validate_candidate_profile(base_raw_profile)

def test_duplicate_project_ids_fail(base_raw_profile):
    base_raw_profile["projects"]["entries"].append(
        {"id": "proj1", "name": "C", "description": "Proj C"}
    )
    with pytest.raises(ProfileValidationError, match="projects.json: contains duplicate IDs"):
        validate_candidate_profile(base_raw_profile)

def test_same_id_across_experience_and_project_allowed(base_raw_profile):
    base_raw_profile["projects"]["entries"].append(
        {"id": "exp1", "name": "Matching ID", "description": "Proj C"}
    )
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": ["experience:exp1", "project:exp1"]}
    ]
    profile = validate_candidate_profile(base_raw_profile)
    assert profile.skill_levels.skills[0].evidence == ["experience:exp1", "project:exp1"]

def test_strong_skill_no_evidence_fails(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": []}
    ]
    with pytest.raises(ProfileValidationError, match="skill 'Python' \\(strong\\) requires evidence"):
        validate_candidate_profile(base_raw_profile)

def test_working_skill_no_evidence_fails(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "working", "evidence": []}
    ]
    with pytest.raises(ProfileValidationError, match="skill 'Python' \\(working\\) requires evidence"):
        validate_candidate_profile(base_raw_profile)

def test_basic_skill_no_evidence_passes(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "basic", "evidence": []}
    ]
    profile = validate_candidate_profile(base_raw_profile)
    assert profile.skill_levels.skills[0].level == "basic"

def test_learning_skill_no_evidence_passes(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "learning", "evidence": []}
    ]
    profile = validate_candidate_profile(base_raw_profile)
    assert profile.skill_levels.skills[0].level == "learning"

def test_none_skill_no_evidence_passes(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "none", "evidence": []}
    ]
    profile = validate_candidate_profile(base_raw_profile)
    assert profile.skill_levels.skills[0].level == "none"

def test_multiple_evidence_references_all_checked(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": ["experience:exp1", "project:missing_proj"]}
    ]
    with pytest.raises(ProfileValidationError, match="ID not found in projects"):
        validate_candidate_profile(base_raw_profile)

def test_validation_error_privacy(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": ["company:A"]}
    ]
    try:
        validate_candidate_profile(base_raw_profile)
    except ProfileValidationError as e:
        msg = str(e)
        assert "/" not in msg  # No paths
        assert "\\" not in msg
        assert base_raw_profile["identity"]["full_name"] not in msg  # No sensitive info

def test_completeness_report_metrics(base_raw_profile):
    base_raw_profile["skill_levels"]["skills"] = [
        {"name": "Python", "level": "strong", "evidence": ["experience:exp1", "project:proj1"]},
        {"name": "Java", "level": "basic", "evidence": ["experience:bad_id", "bad_format", "certification:123"]},
        {"name": "C++", "level": "learning", "evidence": []}
    ]
    
    report = profile_completeness(base_raw_profile)
    
    metrics = report["evidence_metrics"]
    assert metrics["valid"] == 2  # exp1, proj1
    assert metrics["invalid"] == 3  # bad_id, bad_format, certification:123
