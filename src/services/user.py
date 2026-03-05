from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundException, ConflictException
from src.db.repositories.user import UserRepository
from src.schemas.user import UserCreate, UserUpdate, NotificationPrefsUpdate, UserQuery
from src.models.user import User


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def get_by_id(self, user_id: int) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise NotFoundException(detail="User not found")
        return user

    async def query_users(self, query: UserQuery) -> dict:
        items, total = await self.user_repo.query(query)
        return {"items": items, "total": total, "skip": query.skip, "limit": query.limit}

    async def create(self, user_in: UserCreate) -> User:
        existing_email = await self.user_repo.get_by_email(user_in.email)
        if existing_email:
            raise ConflictException(detail="Email already registered")

        existing_username = await self.user_repo.get_by_username(user_in.username)
        if existing_username:
            raise ConflictException(detail="Username already taken")

        return await self.user_repo.create(user_in)

    async def update(self, user_id: int, user_in: UserUpdate) -> User:
        user = await self.get_by_id(user_id)

        if user_in.email and user_in.email != user.email:
            existing = await self.user_repo.get_by_email(user_in.email)
            if existing:
                raise ConflictException(detail="Email already registered")

        if user_in.username and user_in.username != user.username:
            existing = await self.user_repo.get_by_username(user_in.username)
            if existing:
                raise ConflictException(detail="Username already taken")

        return await self.user_repo.update(user, user_in)

    async def get_notification_prefs(self, user_id: int) -> dict:
        user = await self.get_by_id(user_id)
        return {
            "notification_email": user.notification_email,
            "email_enabled": user.email_enabled,
            "notify_network_threats": user.notify_network_threats,
            "notify_system_threats": user.notify_system_threats,
            "notify_general_summary": user.notify_general_summary,
            "effective_email": user.notification_email or user.email,
        }

    async def update_notification_prefs(self, user_id: int, prefs: NotificationPrefsUpdate) -> dict:
        user = await self.get_by_id(user_id)
        update_data = prefs.model_dump(exclude_unset=True)
        await self.user_repo.update_notification_prefs(user, update_data)
        return await self.get_notification_prefs(user_id)

    async def delete(self, user_id: int) -> None:
        user = await self.get_by_id(user_id)
        await self.user_repo.delete(user)
