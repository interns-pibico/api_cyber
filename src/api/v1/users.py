from fastapi import APIRouter, Request

from src.core.dependencies import DbSession, CurrentActiveUser, CurrentAdminUser
from src.core.exceptions import BadRequestException
from src.services.user import UserService
from src.services.audit import AuditService
from src.schemas.user import UserResponse, UserCreate, UserUpdate, UserQuery, NotificationPrefsUpdate, NotificationPrefsResponse
from src.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/users", tags=["Users"])

USER_SORT_COLUMNS = {"id", "email", "username", "full_name", "is_active", "is_admin", "created_at"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(current_user: CurrentActiveUser):
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    request: Request,
    user_in: UserUpdate,
    current_user: CurrentActiveUser,
    db: DbSession,
):
    user_service = UserService(db)
    updated = await user_service.update(current_user.id, user_in)
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    if ip:
        ip = ip.split(",")[0].strip()
    await AuditService.log(
        db,
        action="user_updated",
        username=current_user.username,
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        ip=ip,
    )
    return updated


@router.get("/me/notifications", response_model=NotificationPrefsResponse)
async def get_my_notifications(
    current_user: CurrentActiveUser,
    db: DbSession,
):
    user_service = UserService(db)
    return await user_service.get_notification_prefs(current_user.id)


@router.put("/me/notifications", response_model=NotificationPrefsResponse)
async def update_my_notifications(
    prefs: NotificationPrefsUpdate,
    current_user: CurrentActiveUser,
    db: DbSession,
):
    user_service = UserService(db)
    return await user_service.update_notification_prefs(current_user.id, prefs)


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def get_users(
    db: DbSession,
    current_user: CurrentAdminUser,
    skip: int = 0,
    limit: int = 100,
    is_admin: bool | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    if sort_by not in USER_SORT_COLUMNS:
        raise BadRequestException(detail=f"Invalid sort_by: {sort_by}")
    if sort_order not in ("asc", "desc"):
        raise BadRequestException(detail="sort_order must be 'asc' or 'desc'")

    user_service = UserService(db)
    query = UserQuery(
        is_admin=is_admin,
        is_active=is_active,
        search=search,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return await user_service.query_users(query)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    user_service = UserService(db)
    return await user_service.get_by_id(user_id)


@router.post("/", response_model=UserResponse)
async def create_user(
    request: Request,
    user_in: UserCreate,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    user_service = UserService(db)
    created = await user_service.create(user_in)
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    if ip:
        ip = ip.split(",")[0].strip()
    await AuditService.log(
        db,
        action="user_created",
        username=current_user.username,
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(created.id),
        ip=ip,
    )
    return created


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    request: Request,
    user_id: int,
    user_in: UserUpdate,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    user_service = UserService(db)
    updated = await user_service.update(user_id, user_in)
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    if ip:
        ip = ip.split(",")[0].strip()
    await AuditService.log(
        db,
        action="user_updated",
        username=current_user.username,
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user_id),
        ip=ip,
    )
    return updated


@router.delete("/{user_id}")
async def delete_user(
    request: Request,
    user_id: int,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    user_service = UserService(db)
    await user_service.delete(user_id)
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    if ip:
        ip = ip.split(",")[0].strip()
    await AuditService.log(
        db,
        action="user_deleted",
        username=current_user.username,
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user_id),
        ip=ip,
    )
    return {"message": "User deleted"}
