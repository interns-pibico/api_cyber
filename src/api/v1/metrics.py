from fastapi import APIRouter

from src.core.dependencies import DbSession, CurrentActiveUser, AgentAuth
from src.services.metric import MetricService
from src.schemas.metric import MetricResponse, MetricCreate, MetricBatch, MetricQuery

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/", response_model=list[MetricResponse])
async def query_metrics(
    db: DbSession,
    current_user: CurrentActiveUser,
    agent_id: int | None = None,
    metric_type: str | None = None,
    metric_name: str | None = None,
    limit: int = 100,
):
    metric_service = MetricService(db)
    query = MetricQuery(
        agent_id=agent_id,
        metric_type=metric_type,
        metric_name=metric_name,
        limit=limit,
    )
    return await metric_service.query(query)


@router.get("/{metric_id}", response_model=MetricResponse)
async def get_metric(
    metric_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    metric_service = MetricService(db)
    return await metric_service.get_by_id(metric_id)


@router.get("/agent/{agent_id}", response_model=list[MetricResponse])
async def get_agent_metrics(
    agent_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
    metric_type: str | None = None,
):
    metric_service = MetricService(db)
    return await metric_service.get_latest_by_agent(agent_id, metric_type)


@router.post("/", response_model=MetricResponse)
async def create_metric(
    metric_in: MetricCreate,
    db: DbSession,
    _: AgentAuth,
):
    metric_service = MetricService(db)
    return await metric_service.create(metric_in)


@router.post("/batch", response_model=list[MetricResponse])
async def create_metrics_batch(
    batch: MetricBatch,
    db: DbSession,
    _: AgentAuth,
):
    metric_service = MetricService(db)
    return await metric_service.create_batch(batch)
