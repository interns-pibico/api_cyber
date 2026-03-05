from datetime import datetime
from typing import Any
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    username: str
    action: str
    resource_type: str | None
    resource_id: str | None
    details: Any | None
    ip_address: str | None
    success: bool
    created_at: datetime

    class Config:
        from_attributes = True
