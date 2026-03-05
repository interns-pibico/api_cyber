import logging
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.audit_log import AuditLogRepository

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    async def log(
        db: AsyncSession,
        action: str,
        username: str,
        user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict | None = None,
        ip: str | None = None,
        success: bool = True,
    ) -> None:
        try:
            repo = AuditLogRepository(db)
            await repo.create(
                action=action,
                username=username,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip,
                success=success,
            )
        except Exception:
            logger.exception("Failed to write audit log (action=%s, username=%s)", action, username)
