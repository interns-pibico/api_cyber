from datetime import datetime
from pydantic import BaseModel, field_validator


class ScheduledTaskCreate(BaseModel):
    catalog_key: str
    display_name: str
    schedule_type: str  # interval, cron, once
    interval_seconds: int | None = None
    cron_minute: str | None = "*"
    cron_hour: str | None = "*"
    cron_dom: str | None = "*"
    cron_month: str | None = "*"
    cron_dow: str | None = "*"
    run_at: datetime | None = None
    target_type: str  # server, agent
    agent_id: int | None = None
    parameters: dict | None = None

    @field_validator("schedule_type")
    @classmethod
    def validate_schedule_type(cls, v):
        if v not in ("interval", "cron", "once"):
            raise ValueError("schedule_type must be interval, cron, or once")
        return v

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, v):
        if v not in ("server", "agent"):
            raise ValueError("target_type must be server or agent")
        return v


class ScheduledTaskUpdate(BaseModel):
    display_name: str | None = None
    schedule_type: str | None = None
    interval_seconds: int | None = None
    cron_minute: str | None = None
    cron_hour: str | None = None
    cron_dom: str | None = None
    cron_month: str | None = None
    cron_dow: str | None = None
    run_at: datetime | None = None
    target_type: str | None = None
    agent_id: int | None = None
    parameters: dict | None = None
    is_enabled: bool | None = None


class ScheduledTaskResponse(BaseModel):
    id: int
    catalog_key: str
    display_name: str
    schedule_type: str
    interval_seconds: int | None
    cron_minute: str | None
    cron_hour: str | None
    cron_dom: str | None
    cron_month: str | None
    cron_dow: str | None
    run_at: datetime | None
    target_type: str
    agent_id: int | None
    parameters: dict | None
    is_enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    run_count: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskExecutionResponse(BaseModel):
    id: int
    scheduled_task_id: int | None
    catalog_key: str
    trigger_type: str
    status: str
    output: str | None
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: float | None
    triggered_by: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class AgentCommandResponse(BaseModel):
    id: int
    agent_id: int
    execution_id: int | None
    catalog_key: str
    command: str
    parameters: dict | None
    timeout_seconds: int
    status: str
    created_at: datetime
    delivered_at: datetime | None
    expires_at: datetime

    class Config:
        from_attributes = True


class AgentCommandResult(BaseModel):
    status: str  # completed, failed
    output: str | None = None
    error: str | None = None


class SystemTaskInfo(BaseModel):
    key: str
    name: str
    description: str
    schedule: str
    last_run: str | None = None
    status: str = "active"


class CatalogTaskResponse(BaseModel):
    key: str
    name: str
    description: str
    category: str
    icon: str
    target_type: str
    parameters: list[dict] | None = None
    default_schedule: dict | None = None
