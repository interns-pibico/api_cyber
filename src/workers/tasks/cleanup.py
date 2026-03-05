import asyncio
from datetime import datetime, timezone

from src.workers.celery_app import celery_app
from src.db.session import create_standalone_session
from src.services.event import EventService
from src.services.metric import MetricService


@celery_app.task
def cleanup_old_metrics(days: int = 30):
    """Remove metrics older than specified days."""

    async def _cleanup():
        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                metric_service = MetricService(db)
                deleted = await metric_service.delete_older_than(days)
                return {
                    "status": "completed",
                    "deleted": deleted,
                    "days": days,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    return asyncio.run(_cleanup())


@celery_app.task
def cleanup_old_events(days: int = 365):
    """Remove events older than specified days."""

    async def _cleanup():
        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                event_service = EventService(db)
                deleted = await event_service.delete_older_than(days)
                return {
                    "status": "completed",
                    "deleted": deleted,
                    "days": days,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    return asyncio.run(_cleanup())
