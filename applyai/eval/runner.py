"""Evaluation runner for LLM prompt accuracy."""

import json
from pathlib import Path
from applyai.agents.analyzer import JobAnalyzerAgent
from applyai.providers.factory import get_provider
from applyai.schemas.job import NormalizedJob

class EvalRunner:
    def __init__(self, dataset_path: str):
        self.dataset_path = Path(dataset_path)
        self.provider = get_provider()
        self.analyzer = JobAnalyzerAgent(self.provider)

    async def run_eval(self) -> dict:
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found at {self.dataset_path}")
            
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)
            
        results = {
            "total": len(dataset),
            "passed": 0,
            "failed": 0,
            "details": []
        }
        
        for case in dataset:
            job = NormalizedJob(
                source="eval",
                job_url="http://eval.com",
                content_hash=case["id"],
                company=case["company"],
                role=case["role"],
                job_description=case["job_description"],
                date_discovered="2024-01-01T00:00:00Z"
            )
            
            # Run analyzer
            analysis = await self.analyzer.analyze(job)
            
            # Check accuracy
            expected = case["expected"]
            errors = []
            
            if analysis.role_level != expected.get("role_level"):
                errors.append(f"Role level mismatch: got {analysis.role_level}, expected {expected.get('role_level')}")
                
            found_keywords = set(k.lower() for k in analysis.ats_keywords)
            for kw in expected.get("ats_keywords_include", []):
                if kw.lower() not in found_keywords:
                    errors.append(f"Missing ATS keyword: {kw}")
                    
            # Check Required Skills Preservation
            found_req = set(k.lower() for k in analysis.required_skills)
            for req in expected.get("required_skills_include", []):
                if not any(req.lower() in k for k in found_req):
                    errors.append(f"Missing required skill: {req}")

            # Check Hallucinations
            jd_text = case["job_description"].lower()
            
            # Helper to check if a term is hallucinated. We allow some leeway for common acronyms.
            def is_hallucinated(term: str) -> bool:
                t = term.lower()
                # Basic substring check. In a real system, you might use stemming or embeddings.
                return t not in jd_text

            hallucination_fields = [
                ("required_skills", analysis.required_skills),
                ("preferred_skills", analysis.preferred_skills),
                ("tech_stack", analysis.tech_stack)
            ]
            
            for field_name, items in hallucination_fields:
                for item in items:
                    if is_hallucinated(item):
                        errors.append(f"Hallucination detected in {field_name}: '{item}' not found in JD")
                    
            if not errors:
                results["passed"] += 1
                results["details"].append({"id": case["id"], "status": "pass"})
            else:
                results["failed"] += 1
                results["details"].append({"id": case["id"], "status": "fail", "errors": errors})
                
        return results
