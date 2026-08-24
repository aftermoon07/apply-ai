import pytest
from applyai.processing.scorer import Scorer
from applyai.schemas.scoring import ComponentScores, Recommendation

def test_scorer_all_zeros():
    scorer = Scorer()
    scores = ComponentScores(
        technical_skills=0.0, experience_compat=0.0, education_compat=0.0,
        location_work_mode=0.0, experience_level=0.0, project_relevance=0.0,
        keyword_coverage=0.0
    )
    result = scorer.score(scores, {}, "none", "none")
    assert result.overall_score == 0.0
    assert result.recommendation == Recommendation.NO
    assert result.interview_potential_score == 0.0

def test_scorer_all_hundreds():
    scorer = Scorer()
    scores = ComponentScores(
        technical_skills=100.0, experience_compat=100.0, education_compat=100.0,
        location_work_mode=100.0, experience_level=100.0, project_relevance=100.0,
        keyword_coverage=100.0
    )
    result = scorer.score(scores, {}, "none", "none")
    assert result.overall_score == 100.0
    assert result.recommendation == Recommendation.STRONG_YES

def test_scorer_thresholds():
    scorer = Scorer()
    scores = ComponentScores(
        technical_skills=70.0, experience_compat=70.0, education_compat=70.0,
        location_work_mode=70.0, experience_level=70.0, project_relevance=70.0,
        keyword_coverage=70.0
    )
    result = scorer.score(scores, {}, "none", "none")
    assert result.overall_score == 70.0
    assert result.recommendation == Recommendation.YES

def test_scorer_with_missing_skills_friction():
    scorer = Scorer()
    scores = ComponentScores(
        technical_skills=100.0, experience_compat=100.0, education_compat=100.0,
        location_work_mode=100.0, experience_level=100.0, project_relevance=100.0,
        keyword_coverage=100.0
    )
    matcher_out = {"missing_skills": ["Python"]}
    result = scorer.score(scores, matcher_out, "none", "none")
    # friction penalty is 10.0 * 0.10 = 1.0. Overall score is 100, IP fit_weight = 0.40 -> 40.
    # IP score = 40(fit) + 20(exp) + 15(proj) + 15(skill) - 1.0(fric) = 90 - 1.0 = 89.0
    assert result.interview_potential_score == 89.0
