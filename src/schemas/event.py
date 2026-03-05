from datetime import datetime
from pydantic import BaseModel


class EventBase(BaseModel):
    event_type: str
    category: str
    title: str
    message: str | None = None
    severity: str = "info"
    extra_data: dict | None = None


class EventCreate(EventBase):
    agent_id: str
    occurred_at: datetime


class EventResponse(EventBase):
    id: int
    agent_id: int
    occurred_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class EventQuery(BaseModel):
    agent_id: int | None = None
    event_type: str | None = None
    category: str | None = None
    severity: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    search: str | None = None
    skip: int = 0
    limit: int = 100
    sort_by: str = "occurred_at"
    sort_order: str = "desc"
