from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent import Agent
from src.schemas.agent import AgentCreate, AgentUpdate, AgentHeartbeat


class AgentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, agent_id: int) -> Agent | None:
        result = await self.db.execute(select(Agent).where(Agent.id == agent_id))
        return result.scalar_one_or_none()

    async def get_by_agent_id(self, agent_id: str) -> Agent | None:
        result = await self.db.execute(select(Agent).where(Agent.agent_id == agent_id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100, active_only: bool = False, agent_type: str | None = None) -> list[Agent]:
        query = select(Agent)
        if active_only:
            query = query.where(Agent.is_active == True)
        if agent_type:
            query = query.where(Agent.agent_type == agent_type)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, agent_in: AgentCreate) -> Agent:
        agent = Agent(
            agent_id=agent_in.agent_id,
            hostname=agent_in.hostname,
            agent_type=agent_in.agent_type,
            os_type=agent_in.os_type,
            os_version=agent_in.os_version,
            ip_address=agent_in.ip_address,
            agent_version=agent_in.agent_version,
            description=agent_in.description,
            last_seen=datetime.now(timezone.utc),
        )
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def update(self, agent: Agent, agent_in: AgentUpdate) -> Agent:
        update_data = agent_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def update_heartbeat(self, agent: Agent, heartbeat: AgentHeartbeat) -> Agent:
        agent.hostname = heartbeat.hostname
        agent.agent_type = heartbeat.agent_type
        agent.os_type = heartbeat.os_type
        agent.os_version = heartbeat.os_version
        agent.ip_address = heartbeat.ip_address
        agent.agent_version = heartbeat.agent_version
        agent.last_seen = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def delete(self, agent: Agent) -> None:
        await self.db.delete(agent)
        await self.db.commit()

    async def get_collector_by_hostname(self, hostname: str) -> Agent | None:
        result = await self.db.execute(
            select(Agent).where(Agent.hostname == hostname, Agent.agent_type == "collector")
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, heartbeat: AgentHeartbeat) -> tuple[Agent, bool]:
        agent = await self.get_by_agent_id(heartbeat.agent_id)
        if agent:
            agent = await self.update_heartbeat(agent, heartbeat)
            return agent, False

        agent_create = AgentCreate(
            agent_id=heartbeat.agent_id,
            hostname=heartbeat.hostname,
            agent_type=heartbeat.agent_type,
            os_type=heartbeat.os_type,
            os_version=heartbeat.os_version,
            ip_address=heartbeat.ip_address,
            agent_version=heartbeat.agent_version,
        )
        agent = await self.create(agent_create)
        return agent, True
