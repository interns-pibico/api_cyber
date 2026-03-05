from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException
from src.db.repositories.event import EventRepository
from src.db.repositories.agent import AgentRepository
from src.schemas.event import EventCreate, EventQuery
from src.models.event import Event


class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_repo = EventRepository(db)
        self.agent_repo = AgentRepository(db)

    async def get_by_id(self, event_id: int) -> Event:
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise NotFoundException(detail="Event not found")
        return event

    async def create(self, event_in: EventCreate) -> Event:
        agent = await self.agent_repo.get_by_agent_id(event_in.agent_id)
        if not agent:
            raise NotFoundException(detail="Agent not found")
        return await self.event_repo.create(agent.id, event_in)

    async def query(self, query: EventQuery) -> dict:
        items, total = await self.event_repo.query(query)
        return {"items": items, "total": total, "skip": query.skip, "limit": query.limit}

    async def get_by_agent(self, agent_id: int, limit: int = 100) -> list[Event]:
        return await self.event_repo.get_by_agent(agent_id, limit)

    async def get_by_severity(self, severity: str, limit: int = 100) -> list[Event]:
        return await self.event_repo.get_by_severity(severity, limit)

    async def delete(self, event_id: int) -> None:
        event = await self.event_repo.get_by_id(event_id)
        if not event:
            raise NotFoundException(detail="Event not found")
        await self.event_repo.delete_by_id(event_id)

    async def delete_many(self, event_ids: list[int]) -> int:
        return await self.event_repo.delete_many(event_ids)

    async def update_extra_data(self, event_id: int, extra_data: dict) -> bool:
        return await self.event_repo.update_extra_data(event_id, extra_data)

    async def delete_older_than(self, days: int = 7) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return await self.event_repo.delete_older_than(cutoff)
