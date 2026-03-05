import hashlib
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from src.core.config import settings
from src.core.exceptions import CredentialsException, ForbiddenException
from src.core.security import decode_token
from src.db.session import get_db
from src.models.user import User
from src.db.repositories.user import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.ROOT_PATH}/api/v1/auth/login")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    payload = decode_token(token)
    if payload is None:
        raise CredentialsException()

    # Check JWT blacklist (logout)
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        blacklist_key = f"jwt_blacklist:{_token_hash(token)}"
        if await redis.exists(blacklist_key):
            raise CredentialsException(detail="Token has been revoked")
    finally:
        await redis.aclose()

    user_id: str = payload.get("sub")
    if user_id is None:
        raise CredentialsException()

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(int(user_id))
    if user is None:
        raise CredentialsException()

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_active:
        raise ForbiddenException(detail="Inactive user")
    return current_user


async def get_current_admin_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    if not current_user.is_admin:
        raise ForbiddenException(detail="Admin access required")
    return current_user


async def verify_agent_api_key(
    x_api_key: Annotated[str, Header()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> bool:
    # Per-agent key: format pak{agent_db_id}_{random_hex}
    if x_api_key.startswith("pak"):
        import hashlib as _hl
        from src.db.repositories.agent import AgentRepository
        try:
            underscore_pos = x_api_key.index("_")
            agent_db_id = int(x_api_key[3:underscore_pos])
        except (ValueError, IndexError):
            raise CredentialsException(detail="Invalid API key format")

        agent_repo = AgentRepository(db)
        agent = await agent_repo.get_by_id(agent_db_id)
        if agent and agent.api_key_hash:
            key_hash = _hl.sha256(x_api_key.encode()).hexdigest()
            if key_hash == agent.api_key_hash:
                return True
        raise CredentialsException(detail="Invalid API key")

    # Global key (backward compat)
    if x_api_key != settings.AGENT_API_KEY:
        raise CredentialsException(detail="Invalid API key")
    return True


# Type aliases for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
CurrentAdminUser = Annotated[User, Depends(get_current_admin_user)]
AgentAuth = Annotated[bool, Depends(verify_agent_api_key)]
