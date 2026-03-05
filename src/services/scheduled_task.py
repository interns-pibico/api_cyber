from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException, BadRequestException
from src.db.repositories.scheduled_task import ScheduledTaskRepository
from src.db.repositories.task_execution import TaskExecutionRepository
from src.db.repositories.agent_command import AgentCommandRepository
from src.schemas.scheduled_task import ScheduledTaskCreate, ScheduledTaskUpdate
from src.models.scheduled_task import ScheduledTask
from src.services.task_catalog import get_catalog_task


class ScheduledTaskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_repo = ScheduledTaskRepository(db)
        self.exec_repo = TaskExecutionRepository(db)
        self.cmd_repo = AgentCommandRepository(db)

    async def get_by_id(self, task_id: int) -> ScheduledTask:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(detail="Scheduled task not found")
        return task

    async def get_all(self, skip: int = 0, limit: int = 100) -> dict:
        items, total = await self.task_repo.get_all(skip=skip, limit=limit)
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def create(self, task_in: ScheduledTaskCreate, user_id: int) -> ScheduledTask:
        catalog = get_catalog_task(task_in.catalog_key)
        if not catalog:
            raise BadRequestException(detail=f"Unknown catalog key: {task_in.catalog_key}")

        if task_in.target_type == "agent" and not task_in.agent_id:
            raise BadRequestException(detail="agent_id is required for agent tasks")

        next_run_at = self.calculate_next_run(task_in)
        return await self.task_repo.create(task_in, user_id, next_run_at)

    async def update(self, task_id: int, task_in: ScheduledTaskUpdate) -> ScheduledTask:
        task = await self.get_by_id(task_id)
        task = await self.task_repo.update(task, task_in)

        # Recalculate next_run_at if schedule changed
        if any(
            getattr(task_in, f, None) is not None
            for f in ("schedule_type", "interval_seconds", "cron_minute", "cron_hour", "cron_dom", "cron_month", "cron_dow", "run_at")
        ):
            next_run_at = self._calculate_next_run_from_task(task)
            task.next_run_at = next_run_at
            await self.db.commit()
            await self.db.refresh(task)

        return task

    async def delete(self, task_id: int) -> None:
        task = await self.get_by_id(task_id)
        await self.task_repo.delete(task)

    async def toggle(self, task_id: int) -> ScheduledTask:
        task = await self.get_by_id(task_id)
        task = await self.task_repo.toggle(task)

        # If re-enabling, recalculate next_run_at
        if task.is_enabled:
            task.next_run_at = self._calculate_next_run_from_task(task)
            await self.db.commit()
            await self.db.refresh(task)

        return task

    async def run_now(self, task_id: int, user_id: int) -> dict:
        task = await self.get_by_id(task_id)
        catalog = get_catalog_task(task.catalog_key)
        if not catalog:
            raise BadRequestException(detail=f"Unknown catalog key: {task.catalog_key}")

        execution = await self.exec_repo.create(
            scheduled_task_id=task.id,
            catalog_key=task.catalog_key,
            trigger_type="manual",
            status="pending",
            triggered_by=user_id,
        )

        if task.target_type == "server" and catalog.celery_task:
            # Dispatch via wrapper that tracks execution status
            from src.workers.tasks.scheduler import execute_server_task
            params = task.parameters or {}
            execute_server_task.delay(execution.id, catalog.celery_task, params)
        elif task.target_type == "agent" and catalog.agent_command and task.agent_id:
            # Create agent command
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=300)
            await self.cmd_repo.create(
                agent_id=task.agent_id,
                execution_id=execution.id,
                catalog_key=task.catalog_key,
                command=catalog.agent_command,
                parameters=task.parameters,
                timeout_seconds=300,
                expires_at=expires_at,
            )
            await self.exec_repo.update_status(
                execution, "running", started_at=datetime.now(timezone.utc)
            )

        return {"execution_id": execution.id, "status": "dispatched"}

    async def get_executions(self, task_id: int, limit: int = 20) -> list:
        await self.get_by_id(task_id)  # Ensure exists
        return await self.exec_repo.get_by_task(task_id, limit)

    async def get_recent_executions(self, limit: int = 50) -> list:
        return await self.exec_repo.get_recent(limit)

    def calculate_next_run(self, task_in: ScheduledTaskCreate) -> datetime | None:
        now = datetime.now(timezone.utc)

        if task_in.schedule_type == "interval" and task_in.interval_seconds:
            return now + timedelta(seconds=task_in.interval_seconds)

        if task_in.schedule_type == "cron":
            return self._next_cron_run(
                task_in.cron_minute or "*",
                task_in.cron_hour or "*",
                task_in.cron_dom or "*",
                task_in.cron_month or "*",
                task_in.cron_dow or "*",
            )

        if task_in.schedule_type == "once" and task_in.run_at:
            return task_in.run_at

        return now + timedelta(minutes=5)

    def _calculate_next_run_from_task(self, task: ScheduledTask) -> datetime | None:
        now = datetime.now(timezone.utc)

        if task.schedule_type == "interval" and task.interval_seconds:
            return now + timedelta(seconds=task.interval_seconds)

        if task.schedule_type == "cron":
            return self._next_cron_run(
                task.cron_minute or "*",
                task.cron_hour or "*",
                task.cron_dom or "*",
                task.cron_month or "*",
                task.cron_dow or "*",
            )

        if task.schedule_type == "once" and task.run_at:
            return task.run_at

        return None

    def _next_cron_run(
        self, minute: str, hour: str, dom: str, month: str, dow: str
    ) -> datetime:
        try:
            from croniter import croniter
            cron_expr = f"{minute} {hour} {dom} {month} {dow}"
            now = datetime.now(timezone.utc)
            cron = croniter(cron_expr, now)
            return cron.get_next(datetime).replace(tzinfo=timezone.utc)
        except Exception:
            # Fallback: next hour
            now = datetime.now(timezone.utc)
            return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
