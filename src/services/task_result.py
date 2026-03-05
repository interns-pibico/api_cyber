from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException
from src.db.repositories.task_result import TaskResultRepository
from src.db.repositories.agent import AgentRepository
from src.schemas.task_result import TaskResultCreate, TaskResultQuery
from src.models.task_result import TaskResult


class TaskResultService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_repo = TaskResultRepository(db)
        self.agent_repo = AgentRepository(db)

    async def get_by_id(self, task_id: int) -> TaskResult:
        task = await self.task_repo.get_by_id(task_id)
        if not task:
            raise NotFoundException(detail="Task result not found")
        return task

    async def create(self, task_in: TaskResultCreate) -> TaskResult:
        agent = await self.agent_repo.get_by_agent_id(task_in.agent_id)
        if not agent:
            raise NotFoundException(detail="Agent not found")
        return await self.task_repo.create(agent.id, task_in)

    async def query(self, query: TaskResultQuery) -> dict:
        items, total = await self.task_repo.query(query)
        return {"items": items, "total": total, "skip": query.skip, "limit": query.limit}

    async def get_by_agent(self, agent_id: int, limit: int = 100) -> list[TaskResult]:
        return await self.task_repo.get_by_agent(agent_id, limit)
