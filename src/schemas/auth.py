from pydantic import BaseModel, EmailStr, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Respuesta del endpoint /login. Puede ser token directo o challenge MFA."""
    access_token: str | None = None
    token_type: str = "bearer"
    mfa_required: bool = False
    mfa_session: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class MfaVerifyRequest(BaseModel):
    mfa_session: str
    totp_code: str | None = None
    backup_code: str | None = None


class MfaSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MfaBackupCodesResponse(BaseModel):
    backup_codes: list[str]


class MfaDisableRequest(BaseModel):
    totp_code: str


class MfaTotpRequest(BaseModel):
    totp_code: str


def _validate_password_strength(v: str) -> str:
    errors = []
    if len(v) < 8:
        errors.append("mínimo 8 caracteres")
    if not any(c.isupper() for c in v):
        errors.append("al menos 1 mayúscula")
    if not any(c.islower() for c in v):
        errors.append("al menos 1 minúscula")
    if not any(c.isdigit() for c in v):
        errors.append("al menos 1 dígito")
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v):
        errors.append("al menos 1 carácter especial")
    if errors:
        raise ValueError(f"Contraseña insuficiente: {', '.join(errors)}")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        return _validate_password_strength(v)
