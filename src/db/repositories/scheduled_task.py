from datetime import datetime, timezone
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scheduled_task import ScheduledTask
from src.schemas.scheduled_task import ScheduledTaskCreate, ScheduledTaskUpdate


class ScheduledTaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, task_id: int) -> ScheduledTask | None:
        result = await self.db.execute(select(ScheduledTask).where(ScheduledTask.id == task_id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> tuple[list[ScheduledTask], int]:
        count_stmt = select(func.count()).select_from(ScheduledTask)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        stmt = (
            select(ScheduledTask)
            .order_by(ScheduledTask.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_due_tasks(self, now: datetime) -> list[ScheduledTask]:
        stmt = (
            select(ScheduledTask)
            .where(
                and_(
                    ScheduledTask.is_enabled == True,
                    ScheduledTask.next_run_at <= now,
                )
            )
            .order_by(ScheduledTask.next_run_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(self, task_in: ScheduledTaskCreate, user_id: int, next_run_at: datetime | None = None) -> ScheduledTask:
        task = ScheduledTask(
            catalog_key=task_in.catalog_key,
            display_name=task_in.display_name,
            schedule_type=task_in.schedule_type,
            interval_seconds=task_in.interval_seconds,
            cron_minute=task_in.cron_minute,
            cron_hour=task_in.cron_hour,
            cron_dom=task_in.cron_dom,
            cron_month=task_in.cron_month,
            cron_dow=task_in.cron_dow,
            run_at=task_in.run_at,
            target_type=task_in.target_type,
            agent_id=task_in.agent_id,
            parameters=task_in.parameters,
            is_enabled=True,
            next_run_at=next_run_at,
            created_by=user_id,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update(self, task: ScheduledTask, task_in: ScheduledTaskUpdate) -> ScheduledTask:
        update_data = task_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update_after_run(
        self,
        task: ScheduledTask,
        status: str,
        error: str | None,
        next_run_at: datetime | None,
    ) -> ScheduledTask:
        task.last_run_at = datetime.now(timezone.utc)
        task.last_status = status
        task.last_error = error
        task.run_count += 1
        task.next_run_at = next_run_at
        if task.schedule_type == "once":
            task.is_enabled = False
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def toggle(self, task: ScheduledTask) -> ScheduledTask:
        task.is_enabled = not task.is_enabled
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def delete(self, task: ScheduledTask) -> None:
        await self.db.delete(task)
        await self.db.commit()
