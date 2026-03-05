from fastapi import APIRouter, Body

from src.core.dependencies import DbSession, CurrentActiveUser, AgentAuth
from src.core.exceptions import BadRequestException
from src.services.event import EventService
from src.schemas.event import EventResponse, EventCreate, EventQuery
from src.schemas.pagination import PaginatedResponse
from src.workers.tasks.event_analysis import analyze_event

router = APIRouter(prefix="/events", tags=["Events"])

EVENT_SORT_COLUMNS = {"id", "event_type", "category", "severity", "title", "occurred_at", "created_at"}


@router.get("/", response_model=PaginatedResponse[EventResponse])
async def query_events(
    db: DbSession,
    current_user: CurrentActiveUser,
    agent_id: int | None = None,
    event_type: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "occurred_at",
    sort_order: str = "desc",
):
    if sort_by not in EVENT_SORT_COLUMNS:
        raise BadRequestException(detail=f"Invalid sort_by: {sort_by}")
    if sort_order not in ("asc", "desc"):
        raise BadRequestException(detail="sort_order must be 'asc' or 'desc'")

    event_service = EventService(db)
    query = EventQuery(
        agent_id=agent_id,
        event_type=event_type,
        category=category,
        severity=severity,
        search=search,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await event_service.query(query)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    event_service = EventService(db)
    return await event_service.get_by_id(event_id)


@router.get("/agent/{agent_id}", response_model=list[EventResponse])
async def get_agent_events(
    agent_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
    limit: int = 100,
):
    event_service = EventService(db)
    return await event_service.get_by_agent(agent_id, limit)


@router.get("/severity/{severity}", response_model=list[EventResponse])
async def get_events_by_severity(
    severity: str,
    db: DbSession,
    current_user: CurrentActiveUser,
    limit: int = 100,
):
    event_service = EventService(db)
    return await event_service.get_by_severity(severity, limit)


@router.post("/delete-batch")
async def delete_events_batch(
    event_ids: list[int] = Body(...),
    db: DbSession = ...,
    current_user: CurrentActiveUser = ...,
):
    event_service = EventService(db)
    deleted = await event_service.delete_many(event_ids)
    return {"deleted": deleted}


@router.delete("/{event_id}")
async def delete_event(
    event_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    event_service = EventService(db)
    await event_service.delete(event_id)
    return {"status": "deleted"}


@router.delete("/")
async def delete_old_events(
    days: int = 7,
    db: DbSession = ...,
    current_user: CurrentActiveUser = ...,
):
    event_service = EventService(db)
    deleted = await event_service.delete_older_than(days)
    return {"deleted": deleted, "days": days}


@router.post("/", response_model=EventResponse)
async def create_event(
    event_in: EventCreate,
    db: DbSession,
    _: AgentAuth,
):
    event_service = EventService(db)
    event = await event_service.create(event_in)
    if event.severity in ("high", "critical"):
        analyze_event.delay(event.id)
    return event
