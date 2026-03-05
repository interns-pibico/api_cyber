import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.core.dependencies import DbSession, CurrentActiveUser, CurrentAdminUser, AgentAuth
from src.services.scheduled_task import ScheduledTaskService
from src.services.task_catalog import get_all_catalog_tasks, get_catalog_task
from src.schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskUpdate,
    ScheduledTaskResponse,
    TaskExecutionResponse,
    AgentCommandResponse,
    AgentCommandResult,
    CatalogTaskResponse,
    SystemTaskInfo,
)
from src.schemas.pagination import PaginatedResponse
from src.db.repositories.agent_command import AgentCommandRepository
from src.db.repositories.task_execution import TaskExecutionRepository

router = APIRouter(prefix="/scheduled-tasks", tags=["Scheduled Tasks"])


@router.get("/catalog", response_model=list[CatalogTaskResponse])
async def get_catalog(current_user: CurrentActiveUser):
    tasks = get_all_catalog_tasks()
    return [
        CatalogTaskResponse(
            key=t.key,
            name=t.name,
            description=t.description,
            category=t.category,
            icon=t.icon,
            target_type=t.target_type,
            parameters=[
                {"name": p.name, "label": p.label, "type": p.type, "default": p.default, "required": p.required}
                for p in t.parameters
            ] if t.parameters else None,
            default_schedule=t.default_schedule,
        )
        for t in tasks
    ]


@router.get("/system", response_model=list[SystemTaskInfo])
async def get_system_tasks(current_user: CurrentActiveUser):
    return [
        SystemTaskInfo(
            key="cleanup-old-metrics",
            name="Limpiar metricas antiguas",
            description="Elimina metricas con mas de 30 dias",
            schedule="Cada hora",
            status="active",
        ),
        SystemTaskInfo(
            key="check-agent-status",
            name="Verificar estado de agentes",
            description="Marca agentes inactivos segun su ultimo heartbeat",
            schedule="Cada 5 minutos",
            status="active",
        ),
        SystemTaskInfo(
            key="send-daily-report",
            name="Informe diario de seguridad",
            description="Genera y envia el informe consolidado por email",
            schedule="Diario a las 08:00",
            status="active",
        ),
        SystemTaskInfo(
            key="cleanup-old-events",
            name="Limpiar eventos antiguos",
            description="Elimina eventos con mas de 7 dias de antiguedad",
            schedule="Domingos a las 03:00",
            status="active",
        ),
    ]


@router.get("/", response_model=PaginatedResponse[ScheduledTaskResponse])
async def list_scheduled_tasks(
    db: DbSession,
    current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
):
    service = ScheduledTaskService(db)
    return await service.get_all(skip=skip, limit=limit)


@router.post("/", response_model=ScheduledTaskResponse)
async def create_scheduled_task(
    task_in: ScheduledTaskCreate,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    service = ScheduledTaskService(db)
    return await service.create(task_in, current_user.id)


@router.get("/executions/recent", response_model=list[TaskExecutionResponse])
async def get_recent_executions(
    db: DbSession,
    current_user: CurrentActiveUser,
    limit: int = 50,
):
    service = ScheduledTaskService(db)
    return await service.get_recent_executions(limit)


@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_scheduled_task(
    task_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    service = ScheduledTaskService(db)
    return await service.get_by_id(task_id)


@router.put("/{task_id}", response_model=ScheduledTaskResponse)
async def update_scheduled_task(
    task_id: int,
    task_in: ScheduledTaskUpdate,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    service = ScheduledTaskService(db)
    return await service.update(task_id, task_in)


@router.delete("/{task_id}")
async def delete_scheduled_task(
    task_id: int,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    service = ScheduledTaskService(db)
    await service.delete(task_id)
    return {"message": "Task deleted"}


@router.patch("/{task_id}/toggle", response_model=ScheduledTaskResponse)
async def toggle_scheduled_task(
    task_id: int,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    service = ScheduledTaskService(db)
    return await service.toggle(task_id)


@router.post("/{task_id}/run")
async def run_scheduled_task(
    task_id: int,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    service = ScheduledTaskService(db)
    return await service.run_now(task_id, current_user.id)


@router.get("/{task_id}/executions", response_model=list[TaskExecutionResponse])
async def get_task_executions(
    task_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
    limit: int = 20,
):
    service = ScheduledTaskService(db)
    return await service.get_executions(task_id, limit)


@router.post("/commands/{command_id}/result")
async def report_command_result(
    command_id: int,
    result: AgentCommandResult,
    db: DbSession,
    _: AgentAuth,
):
    cmd_repo = AgentCommandRepository(db)
    exec_repo = TaskExecutionRepository(db)

    command = await cmd_repo.get_by_id(command_id)
    if not command:
        from src.core.exceptions import NotFoundException
        raise NotFoundException(detail="Command not found")

    from datetime import datetime, timezone
    await cmd_repo.update_status(command, result.status)

    # Update associated execution if exists
    if command.execution_id:
        execution = await exec_repo.get_by_id(command.execution_id)
        if execution:
            now = datetime.now(timezone.utc)
            duration = None
            if execution.started_at:
                duration = (now - execution.started_at).total_seconds()
            await exec_repo.update_status(
                execution,
                status=result.status,
                output=result.output,
                error=result.error,
                finished_at=now,
                duration_seconds=duration,
            )

    return {"status": "ok"}


@router.get("/exports/{filename}")
async def download_export(filename: str, current_user: CurrentActiveUser):
    """Download a CSV export file generated by server_export_events_csv."""
    from src.core.exceptions import NotFoundException
    # Restrict to safe filenames: only alphanumeric, underscores, dots, dashes
    import re
    if not re.match(r'^[\w\-.]+\.csv$', filename):
        raise NotFoundException(detail="Archivo no encontrado")
    filepath = f"/tmp/pibicyber/{filename}"
    if not os.path.isfile(filepath):
        raise NotFoundException(detail="Archivo no encontrado")
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="text/csv",
    )
