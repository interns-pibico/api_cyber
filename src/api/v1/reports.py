from fastapi import APIRouter, HTTPException

from src.core.dependencies import DbSession, CurrentActiveUser
from src.services.email import EmailService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/send-daily")
async def send_daily_report(
    db: DbSession,
    current_user: CurrentActiveUser,
    hours: int = 24,
):
    """
    Send the daily consolidated security report via email.

    This endpoint is for testing. In production, use the scheduled task.
    """
    email_service = EmailService(db)

    if not email_service._is_configured():
        raise HTTPException(
            status_code=400,
            detail="SMTP no configurado. Configure SMTP_HOST, SMTP_USER, SMTP_PASSWORD y SMTP_TO en .env"
        )

    result = await email_service.send_daily_report(hours)
    return result


@router.get("/preview")
async def preview_daily_report(
    db: DbSession,
    current_user: CurrentActiveUser,
    hours: int = 24,
):
    """Preview the daily report without sending email."""
    email_service = EmailService(db)

    report_data = await email_service.get_daily_report_data(hours)
    report_text = email_service.format_report_text(report_data)
    report_html = email_service.format_report_html(report_data)

    return {
        "data": report_data,
        "text": report_text,
        "html": report_html,
    }
