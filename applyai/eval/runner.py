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
            
            if analysis.role_level != expected["role_level"]:
                errors.append(f"Role level mismatch: got {analysis.role_level}, expected {expected['role_level']}")
                
            found_keywords = set(k.lower() for k in analysis.ats_keywords)
            for kw in expected["ats_keywords_include"]:
                if kw.lower() not in found_keywords:
                    errors.append(f"Missing ATS keyword: {kw}")
                    
            if not errors:
                results["passed"] += 1
                results["details"].append({"id": case["id"], "status": "pass"})
            else:
                results["failed"] += 1
                results["details"].append({"id": case["id"], "status": "fail", "errors": errors})
                
        return results
