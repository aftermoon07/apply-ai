"""
Deterministic Scoring Engine.

Aggregates qualitative component scores from the Matcher Agent
using configured weights to produce a final JobScoreOutput.
"""

from applyai.schemas.scoring import (
    ComponentScores,
    JobScoreOutput,
    Recommendation,
    InterviewPotentialFactors,
)
from applyai.core.config import get_settings

class Scorer:
    """Computes final job scores deterministically."""

    def __init__(self):
        self.settings = get_settings()

    def score(
        self,
        component_scores: ComponentScores,
        matcher_output_dict: dict,
        provider_used: str,
        model_used: str
    ) -> JobScoreOutput:
        """Calculate the final overall score and interview potential."""
        
        weights = self.settings.scoring.weights.as_dict()
        
        overall_score = 0.0
        
        # If AI was disabled, component_scores will be None for fields. Treat None as 0.0
        c_dict = component_scores.model_dump()
        for key, weight in weights.items():
            val = c_dict.get(key) or 0.0
            overall_score += val * weight
            
        # Determine recommendation based on thresholds
        thresholds = self.settings.scoring.thresholds
        if overall_score >= thresholds.strong_yes:
            rec = Recommendation.STRONG_YES
        elif overall_score >= thresholds.yes_score:
            rec = Recommendation.YES
        elif overall_score >= thresholds.maybe:
            rec = Recommendation.MAYBE
        else:
            rec = Recommendation.NO

        # Experimental heuristic: interview potential
        ip_config = self.settings.scoring.interview_potential
        fit_val = overall_score * ip_config.fit_weight
        exp_val = (c_dict.get("experience_compat") or 0.0) * ip_config.experience_compat_weight
        proj_val = (c_dict.get("project_relevance") or 0.0) * ip_config.project_weight
        skill_val = (c_dict.get("technical_skills") or 0.0) * ip_config.skill_alignment_weight
        
        friction_pen = 0.0 # Could calculate based on missing skills or concerns
        if matcher_output_dict.get("missing_skills"):
            friction_pen = 10.0 * ip_config.friction_penalty_weight
            
        ip_score = fit_val + exp_val + proj_val + skill_val - friction_pen
        ip_score = max(0.0, min(100.0, ip_score))
        
        ip_factors = InterviewPotentialFactors(
            fit_score=fit_val,
            experience_compat=exp_val,
            project_relevance=proj_val,
            skill_alignment=skill_val,
            friction_penalty=friction_pen,
            notes="Calculated deterministically via configured weights."
        )

        return JobScoreOutput(
            overall_score=overall_score,
            recommendation=rec,
            component_scores=component_scores,
            matching_skills=matcher_output_dict.get("matching_skills", []),
            missing_skills=matcher_output_dict.get("missing_skills", []),
            transferable_skills=matcher_output_dict.get("transferable_skills", []),
            concerns=matcher_output_dict.get("concerns", []),
            reasons=matcher_output_dict.get("reasons", []),
            confidence=matcher_output_dict.get("confidence", 0.0),
            interview_potential_score=ip_score,
            interview_potential_factors=ip_factors,
            provider_used=provider_used,
            model_used=model_used,
            scoring_status="complete"
        )
