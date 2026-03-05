import asyncio
import csv
import io
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from src.workers.celery_app import celery_app
from src.db.session import create_standalone_session
from src.services.task_catalog import get_catalog_task


@celery_app.task
def execute_server_task(execution_id: int, celery_task_name: str, params: dict | None = None):
    """Execute a server task directly (not via send_task) and update the execution record."""
    import json
    import importlib

    async def _update_execution(status, output=None, error=None, started_at=None, finished_at=None, duration=None):
        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                from src.db.repositories.task_execution import TaskExecutionRepository
                exec_repo = TaskExecutionRepository(db)
                execution = await exec_repo.get_by_id(execution_id)
                if execution:
                    await exec_repo.update_status(
                        execution, status,
                        output=output, error=error,
                        started_at=started_at, finished_at=finished_at,
                        duration_seconds=duration,
                    )
        finally:
            await engine.dispose()

    started_at = datetime.now(timezone.utc)
    asyncio.run(_update_execution("running", started_at=started_at))

    try:
        # Import and call the task function directly
        module_path, func_name = celery_task_name.rsplit(".", 1)
        module = importlib.import_module(module_path)
        task_func = getattr(module, func_name)

        task_kwargs = params or {}
        # Call the underlying function (unwrap Celery task decorator)
        if hasattr(task_func, 'run'):
            task_result = task_func.run(**task_kwargs)
        else:
            task_result = task_func(**task_kwargs)

        finished_at = datetime.now(timezone.utc)
        duration = (finished_at - started_at).total_seconds()
        output = json.dumps(task_result) if task_result else None
        status = "success"
        error = None

        if isinstance(task_result, dict) and task_result.get("status") == "failed":
            status = "failed"
            error = task_result.get("error", "Task returned failed status")

        asyncio.run(_update_execution(status, output=output, error=error,
                                       finished_at=finished_at, duration=duration))
        return {"status": status, "execution_id": execution_id}

    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        duration = (finished_at - started_at).total_seconds()
        asyncio.run(_update_execution("failed", error=str(e),
                                       finished_at=finished_at, duration=duration))
        return {"status": "failed", "error": str(e)}


@celery_app.task
def check_scheduled_tasks():
    """Check for due scheduled tasks and dispatch them."""

    async def _check():
        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                from src.db.repositories.scheduled_task import ScheduledTaskRepository
                from src.db.repositories.task_execution import TaskExecutionRepository
                from src.db.repositories.agent_command import AgentCommandRepository
                from src.services.scheduled_task import ScheduledTaskService

                task_repo = ScheduledTaskRepository(db)
                exec_repo = TaskExecutionRepository(db)
                cmd_repo = AgentCommandRepository(db)
                service = ScheduledTaskService(db)

                now = datetime.now(timezone.utc)
                due_tasks = await task_repo.get_due_tasks(now)
                dispatched = 0

                for task in due_tasks:
                    try:
                        catalog = get_catalog_task(task.catalog_key)
                        if not catalog:
                            continue

                        execution = await exec_repo.create(
                            scheduled_task_id=task.id,
                            catalog_key=task.catalog_key,
                            trigger_type="scheduled",
                            status="pending",
                        )

                        if task.target_type == "server" and catalog.celery_task:
                            params = task.parameters or {}
                            execute_server_task.delay(execution.id, catalog.celery_task, params)
                        elif task.target_type == "agent" and catalog.agent_command and task.agent_id:
                            expires_at = now + timedelta(seconds=300)
                            await cmd_repo.create(
                                agent_id=task.agent_id,
                                execution_id=execution.id,
                                catalog_key=task.catalog_key,
                                command=catalog.agent_command,
                                parameters=task.parameters,
                                timeout_seconds=300,
                                expires_at=expires_at,
                            )
                            await exec_repo.update_status(
                                execution, "running", started_at=now
                            )

                        next_run = service._calculate_next_run_from_task(task)
                        await task_repo.update_after_run(task, "success", None, next_run)
                        dispatched += 1

                    except Exception as e:
                        next_run = service._calculate_next_run_from_task(task)
                        await task_repo.update_after_run(task, "failed", str(e), next_run)

                return {
                    "status": "completed",
                    "dispatched": dispatched,
                    "checked": len(due_tasks),
                    "timestamp": now.isoformat(),
                }
        finally:
            await engine.dispose()

    return asyncio.run(_check())


@celery_app.task
def cleanup_expired_commands():
    """Mark expired agent commands as expired."""

    async def _cleanup():
        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                from src.db.repositories.agent_command import AgentCommandRepository
                cmd_repo = AgentCommandRepository(db)
                expired = await cmd_repo.expire_old_commands()
                return {
                    "status": "completed",
                    "expired": expired,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    return asyncio.run(_cleanup())


@celery_app.task
def server_test_smtp():
    """Send a test email to verify SMTP configuration."""
    import platform
    from email.mime.multipart import MIMEMultipart
    from src.core.config import settings

    try:
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            return {"status": "skipped", "reason": "SMTP not configured"}

        now = datetime.now(timezone.utc)
        hostname = platform.node()
        now_str = now.strftime("%d/%m/%Y %H:%M UTC")

        html_body = f"""\
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F2F5;">
<tr><td align="center" style="padding:20px 10px;">
<table width="520" cellpadding="0" cellspacing="0" style="font-family:Arial,Helvetica,sans-serif;color:#333;line-height:1.6;">
<tr><td style="background:#4682B4;padding:24px 30px;text-align:center;border-radius:8px 8px 0 0;">
<div style="font-size:20px;font-weight:700;color:#FFFFFF;">&#128737; PibiCyber</div>
<div style="font-size:12px;color:#B0C4DE;margin-top:4px;">Verificacion SMTP</div>
</td></tr>
<tr><td style="background:#FFFFFF;padding:28px 30px;">
<div style="font-size:16px;font-weight:700;color:#4682B4;margin-bottom:16px;">
&#10003; Configuracion SMTP correcta</div>
<div style="font-size:13px;color:#333;margin-bottom:18px;">
La conexion con el servidor de correo se ha verificado correctamente.
Este email confirma que el sistema de notificaciones esta operativo.</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F8F9FA;border-radius:6px;border:1px solid #DEE2E6;">
<tr><td style="padding:12px 16px;font-size:12px;color:#6C757D;border-bottom:1px solid #DEE2E6;">Servidor</td>
<td style="padding:12px 16px;font-size:12px;color:#333;font-weight:600;border-bottom:1px solid #DEE2E6;">{hostname}</td></tr>
<tr><td style="padding:12px 16px;font-size:12px;color:#6C757D;border-bottom:1px solid #DEE2E6;">SMTP Host</td>
<td style="padding:12px 16px;font-size:12px;color:#333;font-weight:600;border-bottom:1px solid #DEE2E6;">{settings.SMTP_HOST}:{settings.SMTP_PORT}</td></tr>
<tr><td style="padding:12px 16px;font-size:12px;color:#6C757D;border-bottom:1px solid #DEE2E6;">Remitente</td>
<td style="padding:12px 16px;font-size:12px;color:#333;font-weight:600;border-bottom:1px solid #DEE2E6;">{settings.SMTP_FROM or settings.SMTP_USER}</td></tr>
<tr><td style="padding:12px 16px;font-size:12px;color:#6C757D;">Fecha</td>
<td style="padding:12px 16px;font-size:12px;color:#333;font-weight:600;">{now_str}</td></tr>
</table>
</td></tr>
<tr><td style="background:#4682B4;padding:16px 30px;text-align:center;border-radius:0 0 8px 8px;">
<div style="color:#B0C4DE;font-size:11px;">Enviado automaticamente por PibiCyber</div>
</td></tr>
</table>
</td></tr></table>"""

        msg = MIMEMultipart()
        msg["Subject"] = "[PibiCyber] Verificacion SMTP correcta"
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = settings.SMTP_TO
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(msg["From"], [settings.SMTP_TO], msg.as_string())

        return {"status": "success", "message": f"Email enviado a {settings.SMTP_TO}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@celery_app.task
def server_db_vacuum():
    """Run VACUUM ANALYZE on PostgreSQL."""
    from src.core.config import settings
    from sqlalchemy import create_engine, text as sa_text

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    sync_engine = create_engine(sync_url, isolation_level="AUTOCOMMIT")

    try:
        with sync_engine.connect() as conn:
            conn.execute(sa_text("VACUUM ANALYZE"))
        return {
            "status": "success",
            "message": "VACUUM ANALYZE completado",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
    finally:
        sync_engine.dispose()


@celery_app.task
def server_export_events_csv(days: int = 7):
    """Export recent events to CSV and store in /tmp/pibicyber/ for download."""

    async def _export():
        engine, SessionLocal = create_standalone_session()
        try:
            async with SessionLocal() as db:
                from sqlalchemy import select
                from src.models.agent import Agent
                from src.services.event import EventService
                from src.schemas.event import EventQuery

                # Build integer agent_id → string agent_id map
                agents_result = await db.execute(select(Agent))
                agents_map = {a.id: a.agent_id for a in agents_result.scalars().all()}

                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                query = EventQuery(start_time=cutoff, limit=10000)
                event_service = EventService(db)
                result = await event_service.query(query)
                events = result["items"]

                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["ID", "Agent", "Type", "Category", "Severity", "Title", "Message", "Date"])

                for e in events:
                    agent_name = agents_map.get(e.agent_id, str(e.agent_id))
                    writer.writerow([
                        e.id, agent_name, e.event_type, e.category,
                        e.severity, e.title, e.message or "", e.occurred_at.isoformat(),
                    ])

                csv_content = output.getvalue()
                filename = f"events_export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
                csv_path = f"/tmp/pibicyber/{filename}"

                os.makedirs("/tmp/pibicyber", exist_ok=True)
                with open(csv_path, "w", encoding="utf-8") as f:
                    f.write(csv_content)

                return {
                    "status": "success",
                    "events_exported": len(events),
                    "filename": filename,
                    "download_path": f"/scheduled-tasks/exports/{filename}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
        finally:
            await engine.dispose()

    return asyncio.run(_export())
