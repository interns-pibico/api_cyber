from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.task_result import TaskResult
from src.schemas.task_result import TaskResultCreate, TaskResultQuery


class TaskResultRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, task_id: int) -> TaskResult | None:
        result = await self.db.execute(select(TaskResult).where(TaskResult.id == task_id))
        return result.scalar_one_or_none()

    async def create(self, agent_db_id: int, task_in: TaskResultCreate) -> TaskResult:
        task = TaskResult(
            agent_id=agent_db_id,
            task_name=task_in.task_name,
            task_type=task_in.task_type,
            status=task_in.status,
            exit_code=task_in.exit_code,
            output=task_in.output,
            error=task_in.error,
            started_at=task_in.started_at,
            finished_at=task_in.finished_at,
            duration_seconds=task_in.duration_seconds,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def query(self, query: TaskResultQuery) -> tuple[list[TaskResult], int]:
        stmt = select(TaskResult)
        conditions = []

        if query.agent_id:
            conditions.append(TaskResult.agent_id == query.agent_id)
        if query.task_name:
            conditions.append(TaskResult.task_name == query.task_name)
        if query.task_type:
            conditions.append(TaskResult.task_type == query.task_type)
        if query.status:
            conditions.append(TaskResult.status == query.status)
        if query.start_time:
            conditions.append(TaskResult.started_at >= query.start_time)
        if query.end_time:
            conditions.append(TaskResult.started_at <= query.end_time)
        if query.search:
            conditions.append(TaskResult.task_name.ilike(f"%{query.search}%"))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        sort_column = getattr(TaskResult, query.sort_by)
        if query.sort_order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        stmt = stmt.offset(query.skip).limit(query.limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_agent(self, agent_id: int, limit: int = 100) -> list[TaskResult]:
        stmt = (
            select(TaskResult)
            .where(TaskResult.agent_id == agent_id)
            .order_by(TaskResult.started_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
