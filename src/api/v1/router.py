from fastapi import APIRouter

from src.api.v1 import health, auth, users, agents, metrics, tasks, events, reports, scheduled_tasks, globe, downloads, audit

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(agents.router)
api_router.include_router(metrics.router)
api_router.include_router(tasks.router)
api_router.include_router(events.router)
api_router.include_router(reports.router)
api_router.include_router(scheduled_tasks.router)
api_router.include_router(globe.router)
api_router.include_router(downloads.router)
api_router.include_router(audit.router)
