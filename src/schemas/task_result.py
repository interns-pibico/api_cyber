from datetime import datetime
from pydantic import BaseModel


class TaskResultBase(BaseModel):
    task_name: str
    task_type: str
    status: str
    exit_code: int | None = None
    output: str | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None


class TaskResultCreate(TaskResultBase):
    agent_id: str


class TaskResultResponse(TaskResultBase):
    id: int
    agent_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TaskResultQuery(BaseModel):
    agent_id: int | None = None
    task_name: str | None = None
    task_type: str | None = None
    status: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    search: str | None = None
    skip: int = 0
    limit: int = 100
    sort_by: str = "started_at"
    sort_order: str = "desc"
