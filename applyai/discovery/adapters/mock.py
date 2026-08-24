"""Mock Discovery Adapter for generating synthetic jobs."""

import uuid
from typing import Any, Dict, List
from applyai.discovery.base import DiscoveryAdapter
import applyai.discovery.registry as registry

class MockAdapter(DiscoveryAdapter):
    """Generates fake job postings for testing the pipeline."""
    
    async def discover(self, limit: int) -> List[Dict[str, Any]]:
        prefix = self.config.get("company_prefix", "MockCorp")
        
        jobs = []
        for i in range(limit):
            job_id = str(uuid.uuid4())
            jobs.append({
                "source": self.name,
                "job_url": f"https://example.com/jobs/{job_id}",
                "source_job_id": job_id,
                "company": f"{prefix} {i+1}",
                "role": "Software Engineer",
                "location": "Remote",
                "job_description": (
                    f"We are looking for a Software Engineer at {prefix}. "
                    "You will work with Python, Kubernetes, and React.js. "
                    "This is a fast-paced environment where you will build scalable APIs. "
                    "Required: 3+ years experience. Nice to have: AWS."
                ),
                "salary_raw": "$120k - $150k",
            })
        
        return jobs

# Register the adapter
registry.register_adapter("mock", MockAdapter)
