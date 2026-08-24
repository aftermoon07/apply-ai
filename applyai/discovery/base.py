"""Base interface for Job Discovery Adapters."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

class DiscoveryAdapter(ABC):
    """Abstract base class for all job discovery sources."""

    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    async def discover(self, limit: int) -> List[Dict[str, Any]]:
        """
        Discover new jobs from the source.
        
        Args:
            limit: Maximum number of jobs to fetch in this run.
            
        Returns:
            A list of raw job dictionaries ready for JobService.ingest_batch.
        """
        ...
