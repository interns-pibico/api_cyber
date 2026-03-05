from datetime import datetime
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.task_execution import TaskExecution


class TaskExecutionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, execution_id: int) -> TaskExecution | None:
        result = await self.db.execute(select(TaskExecution).where(TaskExecution.id == execution_id))
        return result.scalar_one_or_none()

    async def get_by_task(self, task_id: int, limit: int = 20) -> list[TaskExecution]:
        stmt = (
            select(TaskExecution)
            .where(TaskExecution.scheduled_task_id == task_id)
            .order_by(TaskExecution.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent(self, limit: int = 50) -> list[TaskExecution]:
        stmt = (
            select(TaskExecution)
            .order_by(TaskExecution.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        scheduled_task_id: int | None,
        catalog_key: str,
        trigger_type: str,
        status: str = "pending",
        triggered_by: int | None = None,
    ) -> TaskExecution:
        execution = TaskExecution(
            scheduled_task_id=scheduled_task_id,
            catalog_key=catalog_key,
            trigger_type=trigger_type,
            status=status,
            triggered_by=triggered_by,
        )
        self.db.add(execution)
        await self.db.commit()
        await self.db.refresh(execution)
        return execution

    async def update_status(
        self,
        execution: TaskExecution,
        status: str,
        output: str | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_seconds: float | None = None,
    ) -> TaskExecution:
        execution.status = status
        if output is not None:
            execution.output = output
        if error is not None:
            execution.error = error
        if started_at is not None:
            execution.started_at = started_at
        if finished_at is not None:
            execution.finished_at = finished_at
        if duration_seconds is not None:
            execution.duration_seconds = duration_seconds
        await self.db.commit()
        await self.db.refresh(execution)
        return execution
