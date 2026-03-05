from datetime import datetime
from fastapi import APIRouter

from src.core.dependencies import DbSession, CurrentAdminUser
from src.db.repositories.audit_log import AuditLogRepository
from src.schemas.pagination import PaginatedResponse
from src.schemas.audit_log import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/", response_model=PaginatedResponse[AuditLogResponse])
async def get_audit_logs(
    db: DbSession,
    current_user: CurrentAdminUser,
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    success: bool | None = None,
    skip: int = 0,
    limit: int = 100,
):
    repo = AuditLogRepository(db)
    items, total = await repo.query(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_time=start_time,
        end_time=end_time,
        success=success,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)
