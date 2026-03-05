from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException
from src.db.repositories.metric import MetricRepository
from src.db.repositories.agent import AgentRepository
from src.schemas.metric import MetricCreate, MetricBatch, MetricQuery
from src.models.metric import Metric


class MetricService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.metric_repo = MetricRepository(db)
        self.agent_repo = AgentRepository(db)

    async def get_by_id(self, metric_id: int) -> Metric:
        metric = await self.metric_repo.get_by_id(metric_id)
        if not metric:
            raise NotFoundException(detail="Metric not found")
        return metric

    async def create(self, metric_in: MetricCreate) -> Metric:
        agent = await self.agent_repo.get_by_agent_id(metric_in.agent_id)
        if not agent:
            raise NotFoundException(detail="Agent not found")
        return await self.metric_repo.create(agent.id, metric_in)

    async def create_batch(self, batch: MetricBatch) -> list[Metric]:
        agent = await self.agent_repo.get_by_agent_id(batch.agent_id)
        if not agent:
            raise NotFoundException(detail="Agent not found")

        metrics_data = [m.model_dump() for m in batch.metrics]
        return await self.metric_repo.create_batch(agent.id, metrics_data, batch.collected_at)

    async def query(self, query: MetricQuery) -> list[Metric]:
        return await self.metric_repo.query(query)

    async def get_latest_by_agent(self, agent_id: int, metric_type: str | None = None) -> list[Metric]:
        metrics = await self.metric_repo.get_latest_by_agent(agent_id, metric_type)
        if metrics:
            return metrics

        # If no metrics found and agent is a device, try its collector (same hostname)
        agent = await self.agent_repo.get_by_id(agent_id)
        if agent and agent.agent_type == "device":
            collector = await self.agent_repo.get_collector_by_hostname(agent.hostname)
            if collector:
                return await self.metric_repo.get_latest_by_agent(collector.id, metric_type)

        return metrics

    async def delete_older_than(self, days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return await self.metric_repo.delete_older_than(cutoff)
