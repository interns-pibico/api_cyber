from datetime import datetime
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.metric import Metric
from src.schemas.metric import MetricCreate, MetricQuery


class MetricRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, metric_id: int) -> Metric | None:
        result = await self.db.execute(select(Metric).where(Metric.id == metric_id))
        return result.scalar_one_or_none()

    async def create(self, agent_db_id: int, metric_in: MetricCreate) -> Metric:
        metric = Metric(
            agent_id=agent_db_id,
            metric_type=metric_in.metric_type,
            metric_name=metric_in.metric_name,
            value=metric_in.value,
            unit=metric_in.unit,
            extra_data=metric_in.extra_data,
            collected_at=metric_in.collected_at,
        )
        self.db.add(metric)
        await self.db.commit()
        await self.db.refresh(metric)
        return metric

    async def create_batch(self, agent_db_id: int, metrics: list[dict], collected_at: datetime) -> list[Metric]:
        metric_objects = []
        for m in metrics:
            metric = Metric(
                agent_id=agent_db_id,
                metric_type=m["metric_type"],
                metric_name=m["metric_name"],
                value=m["value"],
                unit=m.get("unit"),
                extra_data=m.get("extra_data"),
                collected_at=collected_at,
            )
            self.db.add(metric)
            metric_objects.append(metric)

        await self.db.commit()
        for metric in metric_objects:
            await self.db.refresh(metric)
        return metric_objects

    async def query(self, query: MetricQuery) -> list[Metric]:
        stmt = select(Metric)
        conditions = []

        if query.agent_id:
            conditions.append(Metric.agent_id == query.agent_id)
        if query.metric_type:
            conditions.append(Metric.metric_type == query.metric_type)
        if query.metric_name:
            conditions.append(Metric.metric_name == query.metric_name)
        if query.start_time:
            conditions.append(Metric.collected_at >= query.start_time)
        if query.end_time:
            conditions.append(Metric.collected_at <= query.end_time)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        stmt = stmt.order_by(Metric.collected_at.desc()).limit(query.limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_by_agent(self, agent_id: int, metric_type: str | None = None) -> list[Metric]:
        stmt = select(Metric).where(Metric.agent_id == agent_id)
        if metric_type:
            stmt = stmt.where(Metric.metric_type == metric_type)
        stmt = stmt.order_by(Metric.collected_at.desc()).limit(100)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete_older_than(self, cutoff: datetime) -> int:
        stmt = delete(Metric).where(Metric.collected_at < cutoff)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
