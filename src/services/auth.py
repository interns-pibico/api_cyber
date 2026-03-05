import secrets
from datetime import timedelta

import pyotp
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from src.core.config import settings
from src.core.security import verify_password, create_access_token, get_password_hash
from src.core.exceptions import CredentialsException, ConflictException, BadRequestException
from src.db.repositories.user import UserRepository
from src.schemas.auth import (
    Token, LoginRequest, LoginResponse, RegisterRequest,
    MfaVerifyRequest, MfaSetupResponse, MfaBackupCodesResponse,
)
from src.schemas.user import UserCreate
from src.models.user import User
from src.services.audit import AuditService


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def login(self, login_data: LoginRequest, ip: str | None = None) -> LoginResponse:
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            locked_key = f"login_locked:{login_data.username}"
            fail_key = f"login_failed:{login_data.username}"

            if await redis.exists(locked_key):
                ttl = await redis.ttl(locked_key)
                minutes_left = max(1, (ttl + 59) // 60)
                await AuditService.log(
                    self.db,
                    action="login_blocked",
                    username=login_data.username,
                    ip=ip,
                    success=False,
                    details={"reason": "account_locked", "ttl_seconds": ttl},
                )
                raise CredentialsException(
                    detail=f"Account temporarily locked. Try again in {minutes_left} minute(s)."
                )

            user = await self.user_repo.get_by_username(login_data.username)
            if not user:
                user = await self.user_repo.get_by_email(login_data.username)

            if not user or not verify_password(login_data.password, user.hashed_password):
                count = await redis.incr(fail_key)
                await redis.expire(fail_key, settings.LOGIN_LOCKOUT_MINUTES * 60)
                if count >= settings.LOGIN_MAX_ATTEMPTS:
                    await redis.set(
                        locked_key, "1", ex=settings.LOGIN_LOCKOUT_MINUTES * 60
                    )
                    await redis.delete(fail_key)
                await AuditService.log(
                    self.db,
                    action="login_failed",
                    username=login_data.username,
                    user_id=user.id if user else None,
                    ip=ip,
                    success=False,
                    details={"attempt": count},
                )
                raise CredentialsException(detail="Incorrect username or password")

            if not user.is_active:
                await AuditService.log(
                    self.db,
                    action="login_failed",
                    username=user.username,
                    user_id=user.id,
                    ip=ip,
                    success=False,
                    details={"reason": "inactive_user"},
                )
                raise CredentialsException(detail="User is inactive")

            # Successful password check — clear lockout state
            await redis.delete(fail_key)
            await redis.delete(locked_key)

            # MFA check: if enabled, return mfa_session instead of token
            if user.totp_enabled:
                session_id = secrets.token_hex(32)
                await redis.set(f"mfa_pending:{session_id}", str(user.id), ex=300)
                await AuditService.log(
                    self.db,
                    action="mfa_required",
                    username=user.username,
                    user_id=user.id,
                    ip=ip,
                    success=True,
                )
                return LoginResponse(mfa_required=True, mfa_session=session_id)

            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)

            await AuditService.log(
                self.db,
                action="login_success",
                username=user.username,
                user_id=user.id,
                ip=ip,
                success=True,
            )

            return LoginResponse(access_token=access_token)
        finally:
            await redis.aclose()

    async def verify_mfa(self, req: MfaVerifyRequest, ip: str | None = None) -> LoginResponse:
        if not req.totp_code and not req.backup_code:
            raise BadRequestException(detail="totp_code or backup_code is required")

        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            mfa_key = f"mfa_pending:{req.mfa_session}"
            user_id_str = await redis.get(mfa_key)
            if not user_id_str:
                raise CredentialsException(detail="MFA session expired or invalid")

            user = await self.user_repo.get_by_id(int(user_id_str))
            if not user or not user.totp_enabled:
                raise CredentialsException(detail="MFA session invalid")

            if req.totp_code:
                totp = pyotp.TOTP(user.totp_secret)
                if not totp.verify(req.totp_code, valid_window=1):
                    await AuditService.log(
                        self.db,
                        action="login_mfa_failed",
                        username=user.username,
                        user_id=user.id,
                        ip=ip,
                        success=False,
                        details={"reason": "invalid_totp"},
                    )
                    raise CredentialsException(detail="Invalid TOTP code")
            elif req.backup_code:
                if not await self._verify_and_consume_backup_code(user, req.backup_code):
                    await AuditService.log(
                        self.db,
                        action="login_mfa_failed",
                        username=user.username,
                        user_id=user.id,
                        ip=ip,
                        success=False,
                        details={"reason": "invalid_backup_code"},
                    )
                    raise CredentialsException(detail="Invalid backup code")

            # MFA verified — clean up session and issue token
            await redis.delete(mfa_key)

            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(subject=user.id, expires_delta=access_token_expires)

            await AuditService.log(
                self.db,
                action="login_success",
                username=user.username,
                user_id=user.id,
                ip=ip,
                success=True,
                details={"mfa": "totp" if req.totp_code else "backup_code"},
            )

            return LoginResponse(access_token=access_token)
        finally:
            await redis.aclose()

    async def setup_mfa(self, user: User) -> MfaSetupResponse:
        if user.totp_enabled:
            raise BadRequestException(detail="MFA is already enabled")

        secret = pyotp.random_base32()

        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            await redis.set(f"mfa_setup_pending:{user.id}", secret, ex=600)
        finally:
            await redis.aclose()

        totp = pyotp.TOTP(secret)
        display_name = user.email
        otpauth_uri = totp.provisioning_uri(name=display_name, issuer_name="pibiCo api_cyber")

        return MfaSetupResponse(secret=secret, otpauth_uri=otpauth_uri)

    async def confirm_mfa(self, user: User, totp_code: str) -> MfaBackupCodesResponse:
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        try:
            setup_key = f"mfa_setup_pending:{user.id}"
            secret = await redis.get(setup_key)
            if not secret:
                raise BadRequestException(detail="MFA setup session expired. Start setup again.")

            totp = pyotp.TOTP(secret)
            if not totp.verify(totp_code, valid_window=1):
                raise BadRequestException(detail="Invalid TOTP code. Check your authenticator app.")

            # Generate 8 backup codes and hash them
            plaintext_codes = [secrets.token_hex(4) for _ in range(8)]
            hashed_codes = [get_password_hash(code) for code in plaintext_codes]

            await self.user_repo.update_mfa(
                user,
                totp_secret=secret,
                totp_enabled=True,
                backup_codes=hashed_codes,
            )

            await redis.delete(setup_key)

            await AuditService.log(
                self.db,
                action="mfa_enabled",
                username=user.username,
                user_id=user.id,
                success=True,
            )

        finally:
            await redis.aclose()

        return MfaBackupCodesResponse(backup_codes=plaintext_codes)

    async def disable_mfa(self, user: User, totp_code: str) -> None:
        if not user.totp_enabled:
            raise BadRequestException(detail="MFA is not enabled")

        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise CredentialsException(detail="Invalid TOTP code")

        await self.user_repo.update_mfa(
            user,
            totp_secret=None,
            totp_enabled=False,
            backup_codes=None,
        )

        await AuditService.log(
            self.db,
            action="mfa_disabled",
            username=user.username,
            user_id=user.id,
            success=True,
        )

    async def regenerate_backup_codes(self, user: User, totp_code: str) -> MfaBackupCodesResponse:
        if not user.totp_enabled:
            raise BadRequestException(detail="MFA is not enabled")

        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise CredentialsException(detail="Invalid TOTP code")

        plaintext_codes = [secrets.token_hex(4) for _ in range(8)]
        hashed_codes = [get_password_hash(code) for code in plaintext_codes]

        await self.user_repo.update_mfa(user, backup_codes=hashed_codes)

        await AuditService.log(
            self.db,
            action="mfa_backup_codes_regenerated",
            username=user.username,
            user_id=user.id,
            success=True,
        )

        return MfaBackupCodesResponse(backup_codes=plaintext_codes)

    async def register(self, register_data: RegisterRequest) -> User:
        existing_email = await self.user_repo.get_by_email(register_data.email)
        if existing_email:
            raise ConflictException(detail="Email already registered")

        existing_username = await self.user_repo.get_by_username(register_data.username)
        if existing_username:
            raise ConflictException(detail="Username already taken")

        user_create = UserCreate(
            email=register_data.email,
            username=register_data.username,
            password=register_data.password,
            full_name=register_data.full_name,
        )
        return await self.user_repo.create(user_create)

    async def _verify_and_consume_backup_code(self, user: User, code: str) -> bool:
        if not user.backup_codes:
            return False
        for i, hashed in enumerate(user.backup_codes):
            if verify_password(code, hashed):
                remaining = list(user.backup_codes)
                remaining.pop(i)
                await self.user_repo.update_mfa(user, backup_codes=remaining)
                return True
        return False
