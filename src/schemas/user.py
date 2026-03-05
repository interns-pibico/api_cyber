from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
from email_validator import validate_email, EmailNotValidError
from src.schemas.auth import _validate_password_strength


def validate_email_list(v: str | None) -> str | None:
    """Validate a single email or comma-separated list of emails."""
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    emails = [e.strip() for e in v.split(",") if e.strip()]
    for email in emails:
        try:
            validate_email(email, check_deliverability=False)
        except EmailNotValidError:
            raise ValueError(f"Email no valido: {email}")
    return ", ".join(emails)


class UserBase(BaseModel):
    email: EmailStr
    username: str
    full_name: str | None = None
    is_active: bool = True
    is_admin: bool = False
    notification_email: str | None = None

    @field_validator("notification_email", mode="before")
    @classmethod
    def validate_notification_email(cls, v):
        return validate_email_list(v)

    email_enabled: bool = False
    notify_network_threats: bool = True
    notify_system_threats: bool = True
    notify_general_summary: bool = True


class UserCreate(UserBase):
    password: str

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        return _validate_password_strength(v)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    full_name: str | None = None
    is_active: bool | None = None
    is_admin: bool | None = None
    password: str | None = None
    notification_email: str | None = None

    @field_validator("notification_email", mode="before")
    @classmethod
    def validate_notification_email(cls, v):
        return validate_email_list(v)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password_strength(cls, v):
        if v is None:
            return v
        return _validate_password_strength(v)

    email_enabled: bool | None = None
    notify_network_threats: bool | None = None
    notify_system_threats: bool | None = None
    notify_general_summary: bool | None = None


class NotificationPrefsUpdate(BaseModel):
    notification_email: str | None = None

    @field_validator("notification_email", mode="before")
    @classmethod
    def validate_notification_email(cls, v):
        return validate_email_list(v)

    email_enabled: bool | None = None
    notify_network_threats: bool | None = None
    notify_system_threats: bool | None = None
    notify_general_summary: bool | None = None


class NotificationPrefsResponse(BaseModel):
    notification_email: str | None
    email_enabled: bool
    notify_network_threats: bool
    notify_system_threats: bool
    notify_general_summary: bool
    effective_email: str

    class Config:
        from_attributes = True


class UserResponse(UserBase):
    id: int
    totp_enabled: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserQuery(BaseModel):
    is_admin: bool | None = None
    is_active: bool | None = None
    search: str | None = None
    skip: int = 0
    limit: int = 100
    sort_by: str = "created_at"
    sort_order: str = "desc"
