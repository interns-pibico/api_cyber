from datetime import datetime
from pydantic import BaseModel


class MetricBase(BaseModel):
    metric_type: str
    metric_name: str
    value: float
    unit: str | None = None
    extra_data: dict | None = None


class MetricCreate(MetricBase):
    agent_id: str
    collected_at: datetime


class MetricBatch(BaseModel):
    agent_id: str
    metrics: list[MetricBase]
    collected_at: datetime


class MetricResponse(MetricBase):
    id: int
    agent_id: int
    collected_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class MetricQuery(BaseModel):
    agent_id: int | None = None
    metric_type: str | None = None
    metric_name: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    limit: int = 100
