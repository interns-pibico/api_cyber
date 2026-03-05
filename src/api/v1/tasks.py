from fastapi import APIRouter

from src.core.dependencies import DbSession, CurrentActiveUser, AgentAuth
from src.core.exceptions import BadRequestException
from src.services.task_result import TaskResultService
from src.schemas.task_result import TaskResultResponse, TaskResultCreate, TaskResultQuery
from src.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/tasks", tags=["Task Results"])

TASK_SORT_COLUMNS = {"id", "task_name", "task_type", "status", "started_at", "duration_seconds", "created_at"}


@router.get("/results", response_model=PaginatedResponse[TaskResultResponse])
async def query_task_results(
    db: DbSession,
    current_user: CurrentActiveUser,
    agent_id: int | None = None,
    task_name: str | None = None,
    task_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "started_at",
    sort_order: str = "desc",
):
    if sort_by not in TASK_SORT_COLUMNS:
        raise BadRequestException(detail=f"Invalid sort_by: {sort_by}")
    if sort_order not in ("asc", "desc"):
        raise BadRequestException(detail="sort_order must be 'asc' or 'desc'")

    task_service = TaskResultService(db)
    query = TaskResultQuery(
        agent_id=agent_id,
        task_name=task_name,
        task_type=task_type,
        status=status,
        search=search,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await task_service.query(query)


@router.get("/results/{task_id}", response_model=TaskResultResponse)
async def get_task_result(
    task_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    task_service = TaskResultService(db)
    return await task_service.get_by_id(task_id)


@router.get("/results/agent/{agent_id}", response_model=list[TaskResultResponse])
async def get_agent_task_results(
    agent_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
    limit: int = 100,
):
    task_service = TaskResultService(db)
    return await task_service.get_by_agent(agent_id, limit)


@router.post("/results", response_model=TaskResultResponse)
async def create_task_result(
    task_in: TaskResultCreate,
    db: DbSession,
    _: AgentAuth,
):
    task_service = TaskResultService(db)
    return await task_service.create(task_in)
