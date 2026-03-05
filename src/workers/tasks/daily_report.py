import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from src.workers.celery_app import celery_app
from src.db.session import create_standalone_session
from src.services.email import EmailService

MARKER_DIR = "/tmp/pibicyber"


@celery_app.task
def send_daily_report(hours: int = 24):
    """Send the daily consolidated security report via email."""

    async def _send_report():
        # Anti-duplicate: skip if already sent today
        marker = f"{MARKER_DIR}/daily-report-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.sent"
        if os.path.exists(marker):
            return {
                "status": "skipped",
                "reason": "Already sent today",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                email_service = EmailService(db)

                if not email_service._is_configured():
                    return {
                        "status": "skipped",
                        "reason": "SMTP not configured",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                result = await email_service.send_daily_report(hours)
                result["timestamp"] = datetime.now(timezone.utc).isoformat()

                # Mark as sent to prevent duplicates
                has_sent = any(
                    r.get("status") == "sent"
                    for r in result.get("results", [])
                )
                if has_sent:
                    os.makedirs(MARKER_DIR, exist_ok=True)
                    Path(marker).touch()

                return result
        finally:
            await engine.dispose()

    return asyncio.run(_send_report())
