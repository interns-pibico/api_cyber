import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from src.workers.celery_app import celery_app
from src.db.session import create_standalone_session
from src.models.event import Event
from src.services.explainer import generate_explanation


@celery_app.task(bind=True, max_retries=1)
def analyze_event(self, event_id: int):
    """Analyze an event and generate an auto-explanation."""

    async def _analyze():
        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                result = await db.execute(select(Event).where(Event.id == event_id))
                event = result.scalar_one_or_none()
                if not event:
                    return {"status": "event_not_found", "event_id": event_id}

                # Build event_data dict for the explainer
                event_data = {
                    "event_type": event.event_type,
                    "category": event.category,
                    "severity": event.severity,
                    "title": event.title,
                    "message": event.message,
                    "extra_data": event.extra_data or {},
                }

                explanation = generate_explanation(event_data)
                if not explanation:
                    return {"status": "no_explanation", "event_id": event_id}

                # Merge into extra_data
                extra = dict(event.extra_data or {})
                extra["auto_explanation"] = explanation
                extra["analyzed_at"] = datetime.now(timezone.utc).isoformat()

                from sqlalchemy import update
                await db.execute(
                    update(Event)
                    .where(Event.id == event_id)
                    .values(extra_data=extra)
                )
                await db.commit()

                return {
                    "status": "analyzed",
                    "event_id": event_id,
                    "explanation_length": len(explanation),
                }
        finally:
            await engine.dispose()

    return asyncio.run(_analyze())
