from celery import Celery
from celery.schedules import crontab

from src.core.config import settings

celery_app = Celery(
    "api_cyber",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "src.workers.tasks.notifications",
        "src.workers.tasks.cleanup",
        "src.workers.tasks.daily_report",
        "src.workers.tasks.scheduler",
        "src.workers.tasks.event_analysis",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Madrid",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "cleanup-old-metrics": {
        "task": "src.workers.tasks.cleanup.cleanup_old_metrics",
        "schedule": 3600.0,  # Every hour
    },
    "check-agent-status": {
        "task": "src.workers.tasks.notifications.check_agent_status",
        "schedule": 300.0,  # Every 5 minutes
    },
    "send-daily-report": {
        "task": "src.workers.tasks.daily_report.send_daily_report",
        "schedule": crontab(hour=8, minute=0),  # 8:00 AM Europe/Madrid
    },
    "cleanup-old-events": {
        "task": "src.workers.tasks.cleanup.cleanup_old_events",
        "schedule": crontab(hour=3, minute=0),  # Diario a las 3:00 AM Europe/Madrid
    },
    "check-scheduled-tasks": {
        "task": "src.workers.tasks.scheduler.check_scheduled_tasks",
        "schedule": 60.0,  # Every 60 seconds
    },
    "cleanup-expired-commands": {
        "task": "src.workers.tasks.scheduler.cleanup_expired_commands",
        "schedule": 300.0,  # Every 5 minutes
    },
}
