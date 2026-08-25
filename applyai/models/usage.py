"""Database model for provider usage telemetry."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Boolean, Float, Text

from applyai.models.base import Base

class ProviderUsage(Base):
    __tablename__ = "provider_usage"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_name = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    operation = Column(String(50), nullable=False)
    
    # Context
    job_id = Column(String(36), nullable=True)
    agent_name = Column(String(50), nullable=True)
    
    # Metrics
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    
    # Status
    success = Column(Boolean, default=True, nullable=False)
    error_type = Column(Text, nullable=True)
    
    # Cost
    estimated_cost = Column(Float, nullable=True)
    
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
