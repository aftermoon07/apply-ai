"""Service for AI provider usage telemetry and cost calculation."""

import logging
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import select, func

from applyai.core.database import get_session
from applyai.core.config import get_settings
from applyai.models.usage import ProviderUsage

logger = logging.getLogger(__name__)

@dataclass
class UsageRecord:
    """Normalized usage telemetry from any AI provider."""
    provider_name: str
    model_name: str
    operation: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    retry_count: int = 0
    latency_ms: Optional[int] = None
    success: bool = True
    error_type: Optional[str] = None
    job_id: Optional[str] = None
    agent_name: Optional[str] = None

class UsageService:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def calculate_estimated_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float | None:
        """Calculate estimated cost deterministically based on configuration."""
        if not self.settings.ai.pricing:
            return None
        
        provider_pricing = self.settings.ai.pricing.get(provider, {})
        model_pricing = provider_pricing.get(model)
        
        if not model_pricing:
            return None
            
        input_cost = (input_tokens / 1_000_000) * model_pricing.input_per_million_tokens
        output_cost = (output_tokens / 1_000_000) * model_pricing.output_per_million_tokens
        
        return input_cost + output_cost

    async def record_usage(self, record: UsageRecord) -> None:
        """Persist a usage record and its calculated cost."""
        estimated_cost = None
        if record.input_tokens is not None and record.output_tokens is not None:
            estimated_cost = self.calculate_estimated_cost(
                record.provider_name, 
                record.model_name, 
                record.input_tokens, 
                record.output_tokens
            )
            
        async with get_session() as session:
            db_usage = ProviderUsage(
                provider_name=record.provider_name,
                model_name=record.model_name,
                operation=record.operation,
                job_id=record.job_id,
                agent_name=record.agent_name,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                total_tokens=record.total_tokens,
                retry_count=record.retry_count,
                latency_ms=record.latency_ms,
                success=record.success,
                error_type=record.error_type,
                estimated_cost=estimated_cost
            )
            session.add(db_usage)
            await session.commit()
            
    async def get_summary(self, provider: str | None = None, model: str | None = None, job_id: str | None = None, operation: str | None = None) -> dict:
        """Get aggregate usage statistics."""
        async with get_session() as session:
            stmt = select(
                func.count(ProviderUsage.id).label("requests"),
                func.sum(ProviderUsage.input_tokens).label("input_tokens"),
                func.sum(ProviderUsage.output_tokens).label("output_tokens"),
                func.sum(ProviderUsage.total_tokens).label("total_tokens"),
                func.sum(ProviderUsage.estimated_cost).label("estimated_cost"),
                func.sum(ProviderUsage.retry_count).label("retries"),
            )
            
            if provider:
                stmt = stmt.where(ProviderUsage.provider_name == provider)
            if model:
                stmt = stmt.where(ProviderUsage.model_name == model)
            if job_id:
                stmt = stmt.where(ProviderUsage.job_id == job_id)
            if operation:
                stmt = stmt.where(ProviderUsage.operation == operation)
                
            result = (await session.execute(stmt)).first()
            
            if not result or result.requests == 0:
                return {
                    "requests": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "estimated_cost": 0.0,
                    "retries": 0,
                }
                
            return {
                "requests": result.requests or 0,
                "input_tokens": result.input_tokens or 0,
                "output_tokens": result.output_tokens or 0,
                "total_tokens": result.total_tokens or 0,
                "estimated_cost": result.estimated_cost or 0.0,
                "retries": result.retries or 0,
            }
