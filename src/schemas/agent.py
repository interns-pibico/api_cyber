from datetime import datetime
from pydantic import BaseModel


class AgentBase(BaseModel):
    hostname: str
    agent_type: str = "device"
    os_type: str
    os_version: str | None = None
    ip_address: str | None = None
    agent_version: str | None = None
    description: str | None = None


class AgentCreate(AgentBase):
    agent_id: str


class AgentUpdate(BaseModel):
    hostname: str | None = None
    agent_type: str | None = None
    os_type: str | None = None
    os_version: str | None = None
    ip_address: str | None = None
    agent_version: str | None = None
    description: str | None = None
    is_active: bool | None = None


class AgentResponse(AgentBase):
    id: int
    agent_id: str
    is_active: bool
    last_seen: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentHeartbeat(BaseModel):
    agent_id: str
    hostname: str
    agent_type: str = "device"
    os_type: str
    os_version: str | None = None
    ip_address: str | None = None
    agent_version: str | None = None
