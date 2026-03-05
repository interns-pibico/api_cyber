from dataclasses import dataclass, field


@dataclass
class CatalogParameter:
    name: str
    label: str
    type: str  # int, str, bool
    default: str | int | bool | None = None
    required: bool = False


@dataclass
class CatalogTask:
    key: str
    name: str
    description: str
    category: str  # server, agent
    icon: str
    target_type: str  # server, agent
    celery_task: str | None = None
    agent_command: str | None = None
    parameters: list[CatalogParameter] = field(default_factory=list)
    default_schedule: dict | None = None


# Server tasks catalog
SERVER_TASKS = [
    CatalogTask(
        key="server_cleanup_metrics",
        name="Limpiar metricas antiguas",
        description="Elimina metricas con mas de N dias de antiguedad",
        category="server",
        icon="fa-broom",
        target_type="server",
        celery_task="src.workers.tasks.cleanup.cleanup_old_metrics",
        parameters=[CatalogParameter(name="days", label="Dias", type="int", default=30)],
        default_schedule={"type": "interval", "interval_seconds": 86400},
    ),
    CatalogTask(
        key="server_cleanup_events",
        name="Limpiar eventos antiguos",
        description="Elimina eventos con mas de N dias de antiguedad",
        category="server",
        icon="fa-trash-can",
        target_type="server",
        celery_task="src.workers.tasks.cleanup.cleanup_old_events",
        parameters=[CatalogParameter(name="days", label="Dias", type="int", default=7)],
        default_schedule={"type": "interval", "interval_seconds": 604800},
    ),
    CatalogTask(
        key="server_test_smtp",
        name="Probar email SMTP",
        description="Envia un email de prueba para verificar la configuracion SMTP",
        category="server",
        icon="fa-envelope",
        target_type="server",
        celery_task="src.workers.tasks.scheduler.server_test_smtp",
    ),
    CatalogTask(
        key="server_generate_report",
        name="Generar informe ahora",
        description="Genera y envia el informe de seguridad inmediatamente",
        category="server",
        icon="fa-file-lines",
        target_type="server",
        celery_task="src.workers.tasks.daily_report.send_daily_report",
        parameters=[CatalogParameter(name="hours", label="Horas", type="int", default=24)],
    ),
    CatalogTask(
        key="server_db_vacuum",
        name="Optimizar base de datos",
        description="Ejecuta VACUUM ANALYZE en PostgreSQL para optimizar rendimiento",
        category="server",
        icon="fa-database",
        target_type="server",
        celery_task="src.workers.tasks.scheduler.server_db_vacuum",
    ),
    CatalogTask(
        key="server_check_agents",
        name="Verificar estado agentes",
        description="Actualiza el estado de conectividad de todos los agentes",
        category="server",
        icon="fa-heartbeat",
        target_type="server",
        celery_task="src.workers.tasks.notifications.check_agent_status",
    ),
    CatalogTask(
        key="server_export_events_csv",
        name="Exportar eventos CSV",
        description="Genera un archivo CSV con los eventos recientes",
        category="server",
        icon="fa-file-csv",
        target_type="server",
        celery_task="src.workers.tasks.scheduler.server_export_events_csv",
        parameters=[CatalogParameter(name="days", label="Dias", type="int", default=7)],
    ),
]

# Agent tasks catalog
AGENT_TASKS = [
    CatalogTask(
        key="agent_force_heartbeat",
        name="Forzar heartbeat",
        description="Solicita un heartbeat inmediato del agente",
        category="agent",
        icon="fa-heart-pulse",
        target_type="agent",
        agent_command="force_heartbeat",
    ),
    CatalogTask(
        key="agent_collect_metrics",
        name="Recolectar metricas ahora",
        description="Solicita recoleccion inmediata de metricas del sistema",
        category="agent",
        icon="fa-chart-line",
        target_type="agent",
        agent_command="collect_metrics",
    ),
    CatalogTask(
        key="agent_run_security_scan",
        name="Analisis de seguridad",
        description="Ejecuta el script de monitorizacion de seguridad",
        category="agent",
        icon="fa-shield-halved",
        target_type="agent",
        agent_command="security_scan",
    ),
    CatalogTask(
        key="agent_check_disk_space",
        name="Verificar espacio disco",
        description="Reporta el espacio disponible en todos los discos",
        category="agent",
        icon="fa-hard-drive",
        target_type="agent",
        agent_command="check_disk_space",
    ),
    CatalogTask(
        key="agent_check_services",
        name="Verificar servicios",
        description="Lista todos los servicios y su estado actual",
        category="agent",
        icon="fa-gears",
        target_type="agent",
        agent_command="check_services",
    ),
    CatalogTask(
        key="agent_network_connections",
        name="Conexiones de red",
        description="Lista las conexiones de red establecidas",
        category="agent",
        icon="fa-network-wired",
        target_type="agent",
        agent_command="network_connections",
    ),
    CatalogTask(
        key="agent_system_uptime",
        name="Uptime del sistema",
        description="Reporta el tiempo activo y ultimo reinicio del sistema",
        category="agent",
        icon="fa-clock",
        target_type="agent",
        agent_command="system_uptime",
    ),
]

ALL_TASKS = {t.key: t for t in SERVER_TASKS + AGENT_TASKS}


def get_catalog_task(key: str) -> CatalogTask | None:
    return ALL_TASKS.get(key)


def get_all_catalog_tasks() -> list[CatalogTask]:
    return SERVER_TASKS + AGENT_TASKS


def get_server_catalog_tasks() -> list[CatalogTask]:
    return SERVER_TASKS


def get_agent_catalog_tasks() -> list[CatalogTask]:
    return AGENT_TASKS
