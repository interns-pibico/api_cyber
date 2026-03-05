from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException
from src.db.repositories.agent import AgentRepository
from src.schemas.agent import AgentCreate, AgentUpdate, AgentHeartbeat
from src.models.agent import Agent


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.agent_repo = AgentRepository(db)

    async def get_by_id(self, agent_id: int) -> Agent:
        agent = await self.agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(detail="Agent not found")
        return agent

    async def get_by_agent_id(self, agent_id: str) -> Agent:
        agent = await self.agent_repo.get_by_agent_id(agent_id)
        if not agent:
            raise NotFoundException(detail="Agent not found")
        return agent

    async def get_all(self, skip: int = 0, limit: int = 100, active_only: bool = False, agent_type: str | None = None) -> list[Agent]:
        return await self.agent_repo.get_all(skip=skip, limit=limit, active_only=active_only, agent_type=agent_type)

    async def create(self, agent_in: AgentCreate) -> Agent:
        return await self.agent_repo.create(agent_in)

    async def update(self, agent_id: int, agent_in: AgentUpdate) -> Agent:
        agent = await self.get_by_id(agent_id)
        return await self.agent_repo.update(agent, agent_in)

    async def delete(self, agent_id: int) -> None:
        agent = await self.get_by_id(agent_id)
        await self.agent_repo.delete(agent)

    async def heartbeat(self, heartbeat: AgentHeartbeat) -> tuple[Agent, bool]:
        return await self.agent_repo.get_or_create(heartbeat)
