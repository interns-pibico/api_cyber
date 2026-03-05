import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from src.workers.celery_app import celery_app
from src.db.session import create_standalone_session
from src.models.agent import Agent


@celery_app.task
def check_agent_status():
    """Mark agents as inactive if they haven't sent a heartbeat recently.

    - Collectors (metrics agent): inactive after 10 minutes
    - Devices (equipment): inactive after 25 hours (daily cron + margin)
    """

    async def _check():
        now = datetime.now(timezone.utc)
        collector_cutoff = now - timedelta(minutes=10)
        device_cutoff = now - timedelta(hours=25)

        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                # Mark collectors inactive if no heartbeat in 10 minutes
                await db.execute(
                    update(Agent)
                    .where(Agent.agent_type == "collector")
                    .where(Agent.is_active == True)
                    .where(Agent.last_seen < collector_cutoff)
                    .values(is_active=False)
                )

                # Mark devices inactive if no heartbeat in 25 hours
                await db.execute(
                    update(Agent)
                    .where(Agent.agent_type == "device")
                    .where(Agent.is_active == True)
                    .where(Agent.last_seen < device_cutoff)
                    .values(is_active=False)
                )

                # Re-activate agents that have recently sent a heartbeat
                await db.execute(
                    update(Agent)
                    .where(Agent.agent_type == "collector")
                    .where(Agent.is_active == False)
                    .where(Agent.last_seen >= collector_cutoff)
                    .values(is_active=True)
                )
                await db.execute(
                    update(Agent)
                    .where(Agent.agent_type == "device")
                    .where(Agent.is_active == False)
                    .where(Agent.last_seen >= device_cutoff)
                    .values(is_active=True)
                )

                await db.commit()

            return {"status": "checked", "timestamp": now.isoformat()}
        finally:
            await engine.dispose()

    return asyncio.run(_check())
