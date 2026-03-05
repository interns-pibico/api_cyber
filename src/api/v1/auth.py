import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from src.core.config import settings
from src.core.limiter import limiter
from src.core.dependencies import CurrentActiveUser, oauth2_scheme, get_current_active_user
from src.core.security import decode_token
from src.db.session import get_db
from src.services.auth import AuthService
from src.services.audit import AuditService
from src.schemas.auth import (
    Token, LoginResponse, RegisterRequest,
    MfaVerifyRequest, MfaSetupResponse, MfaBackupCodesResponse,
    MfaDisableRequest, MfaTotpRequest,
)
from src.models.user import User
from src.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    from src.schemas.auth import LoginRequest
    login_data = LoginRequest(username=form_data.username, password=form_data.password)
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    if ip:
        ip = ip.split(",")[0].strip()
    auth_service = AuthService(db)
    return await auth_service.login(login_data, ip=ip)


@router.post("/register", response_model=UserResponse)
async def register(
    register_data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    auth_service = AuthService(db)
    return await auth_service.register(register_data)


@router.post("/logout")
async def logout(
    request: Request,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(token)
    if payload and "exp" in payload:
        exp_ts = payload["exp"]
        now_ts = int(datetime.now(timezone.utc).timestamp())
        ttl = max(exp_ts - now_ts, 1)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await redis.set(f"jwt_blacklist:{token_hash}", "1", ex=ttl)
        finally:
            await redis.aclose()

    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    if ip:
        ip = ip.split(",")[0].strip()
    await AuditService.log(
        db,
        action="logout",
        username=current_user.username,
        user_id=current_user.id,
        ip=ip,
    )
    return {"message": "Logged out successfully"}


# ── MFA endpoints ──────────────────────────────────────────────────────────────

@router.post("/mfa/verify", response_model=LoginResponse)
@limiter.limit("10/minute")
async def mfa_verify(
    request: Request,
    req: MfaVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Phase 2 of MFA login: verify TOTP code or backup code."""
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
    if ip:
        ip = ip.split(",")[0].strip()
    auth_service = AuthService(db)
    return await auth_service.verify_mfa(req, ip=ip)


@router.get("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new TOTP secret and return the otpauth URI for QR code rendering."""
    auth_service = AuthService(db)
    return await auth_service.setup_mfa(current_user)


@router.post("/mfa/setup/confirm", response_model=MfaBackupCodesResponse)
async def mfa_setup_confirm(
    req: MfaTotpRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm MFA setup with a TOTP code. Returns 8 one-time backup codes."""
    auth_service = AuthService(db)
    return await auth_service.confirm_mfa(current_user, req.totp_code)


@router.delete("/mfa", status_code=200)
async def mfa_disable(
    req: MfaDisableRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Disable MFA. Requires current TOTP code."""
    auth_service = AuthService(db)
    await auth_service.disable_mfa(current_user, req.totp_code)
    return {"message": "MFA disabled successfully"}


@router.post("/mfa/backup-codes/regenerate", response_model=MfaBackupCodesResponse)
async def mfa_regenerate_backup_codes(
    req: MfaTotpRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Regenerate backup codes. Requires current TOTP code. Old codes are invalidated."""
    auth_service = AuthService(db)
    return await auth_service.regenerate_backup_codes(current_user, req.totp_code)
