from datetime import datetime
from sqlalchemy import select, delete, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.event import Event
from src.schemas.event import EventCreate, EventQuery


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, event_id: int) -> Event | None:
        result = await self.db.execute(select(Event).where(Event.id == event_id))
        return result.scalar_one_or_none()

    async def create(self, agent_db_id: int, event_in: EventCreate) -> Event:
        event = Event(
            agent_id=agent_db_id,
            event_type=event_in.event_type,
            category=event_in.category,
            title=event_in.title,
            message=event_in.message,
            severity=event_in.severity,
            extra_data=event_in.extra_data,
            occurred_at=event_in.occurred_at,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def query(self, query: EventQuery) -> tuple[list[Event], int]:
        stmt = select(Event)
        conditions = []

        if query.agent_id:
            conditions.append(Event.agent_id == query.agent_id)
        if query.event_type:
            conditions.append(Event.event_type == query.event_type)
        if query.category:
            conditions.append(Event.category == query.category)
        if query.severity:
            conditions.append(Event.severity == query.severity)
        if query.start_time:
            conditions.append(Event.occurred_at >= query.start_time)
        if query.end_time:
            conditions.append(Event.occurred_at <= query.end_time)
        if query.search:
            conditions.append(Event.title.ilike(f"%{query.search}%"))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()

        sort_column = getattr(Event, query.sort_by)
        if query.sort_order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        stmt = stmt.offset(query.skip).limit(query.limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_agent(self, agent_id: int, limit: int = 100) -> list[Event]:
        stmt = (
            select(Event)
            .where(Event.agent_id == agent_id)
            .order_by(Event.occurred_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_severity(self, severity: str, limit: int = 100) -> list[Event]:
        stmt = (
            select(Event)
            .where(Event.severity == severity)
            .order_by(Event.occurred_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_agent_since(
        self, agent_id: int, since: datetime, limit: int = 100
    ) -> list[Event]:
        stmt = (
            select(Event)
            .where(and_(Event.agent_id == agent_id, Event.occurred_at >= since))
            .order_by(Event.occurred_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_id(self, event_id: int) -> bool:
        event = await self.get_by_id(event_id)
        if not event:
            return False
        await self.db.delete(event)
        await self.db.commit()
        return True

    async def delete_many(self, event_ids: list[int]) -> int:
        stmt = delete(Event).where(Event.id.in_(event_ids))
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def update_extra_data(self, event_id: int, extra_data: dict) -> bool:
        event = await self.get_by_id(event_id)
        if not event:
            return False
        merged = {**(event.extra_data or {}), **extra_data}
        await self.db.execute(
            update(Event).where(Event.id == event_id).values(extra_data=merged)
        )
        await self.db.commit()
        return True

    async def delete_older_than(self, cutoff: datetime) -> int:
        stmt = delete(Event).where(Event.occurred_at < cutoff)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
