import html
import io
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.repositories.event import EventRepository
from src.db.repositories.agent import AgentRepository
from src.db.repositories.user import UserRepository


class EmailService:
    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        if db:
            self.event_repo = EventRepository(db)
            self.agent_repo = AgentRepository(db)

    def _format_datetime(self, iso_string: str | None) -> str:
        """Convert ISO datetime to readable format: DD/MM/YYYY HH:MM (Europe/Madrid)"""
        if not iso_string:
            return "Desconocida"
        try:
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            dt_spain = dt.astimezone(ZoneInfo("Europe/Madrid"))
            return dt_spain.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return iso_string

    def _is_configured(self) -> bool:
        """Check if SMTP is configured."""
        return bool(
            settings.SMTP_HOST
            and settings.SMTP_USER
            and settings.SMTP_PASSWORD
            and settings.SMTP_TO
        )

    def _has_real_threats(self, event: dict) -> bool:
        """Check if an event contains actual threat data."""
        severity = event.get("severity", "info")

        # Critical and high severity events are always real threats
        if severity in ("critical", "high"):
            return True

        # Medium and low require specific extra_data fields
        extra = event.get("extra_data", {}) or {}
        return (
            severity in ("low", "medium")
            and bool(
                extra.get("ssh_failures")
                or extra.get("nginx_suspicious")
                or extra.get("firewall_blocked")
                or extra.get("sudo_failures")
                or extra.get("high_risk_ips")
                or extra.get("service_failures")
                or extra.get("defender_alerts")
                or extra.get("defender_protection_disabled")
                or extra.get("failed_logins")
                or extra.get("anomalies")
                or extra.get("sudo_sessions")
            )
        )

    def send_email(
        self,
        subject: str,
        body: str,
        to: str | None = None,
        content_type: str = "html",
        attachment: tuple[str, bytes] | None = None,
    ) -> bool:
        """Send an email using SMTP. Optional attachment as (filename, bytes)."""
        if not self._is_configured():
            print("SMTP no configurado, no se puede enviar correo")
            return False

        to_str = to or settings.SMTP_TO
        from_addr = settings.SMTP_FROM or settings.SMTP_USER
        to_list = [e.strip() for e in to_str.split(",") if e.strip()]

        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_str
        msg["Subject"] = subject

        msg.attach(MIMEText(body, content_type, "utf-8"))

        if attachment:
            filename, file_bytes = attachment
            part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            part.set_payload(file_bytes)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)

        try:
            tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            tls_context.minimum_version = ssl.TLSVersion.TLSv1_2
            tls_context.load_default_certs()
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls(context=tls_context)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(from_addr, to_list, msg.as_string())
            print(f"Correo enviado a {to_str}")
            return True
        except Exception as e:
            print(f"Error enviando correo: {e}")
            return False

    async def get_daily_report_data(self, hours: int = 24) -> dict:
        """Get events from the last N hours grouped by device agents."""
        if not self.db:
            raise ValueError("Database session required")

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        agents = await self.agent_repo.get_all(agent_type="device")

        report_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_hours": hours,
            "agents": []
        }

        for agent in agents:
            events = await self.event_repo.get_by_agent_since(agent.id, cutoff)

            agent_data = {
                "agent_id": agent.agent_id,
                "hostname": agent.hostname,
                "os_type": agent.os_type,
                "agent_type": agent.agent_type,
                "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
                "events_count": len(events),
                "events": []
            }

            for event in events:
                agent_data["events"].append({
                    "title": event.title,
                    "severity": event.severity,
                    "category": event.category,
                    "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
                    "extra_data": event.extra_data
                })

            report_data["agents"].append(agent_data)

        return report_data

    def format_report_text(self, report_data: dict, categories: dict | None = None) -> str:
        """Convert report data to readable text format (fallback/debug)."""
        include_network = categories.get("network_threats", True) if categories else True
        include_system = categories.get("system_threats", True) if categories else True
        include_summary = categories.get("general_summary", True) if categories else True

        lines = []
        lines.append("=" * 60)
        lines.append("INFORME CONSOLIDADO DE SEGURIDAD - PIBICYBER")
        lines.append(f"Generado: {self._format_datetime(report_data['generated_at'])}")
        lines.append(f"Periodo: ultimas {report_data['period_hours']} horas")
        lines.append("=" * 60)
        lines.append("")

        if include_summary:
            agentes_con_amenazas = 0
            total_amenazas = 0
            for agent in report_data["agents"]:
                for event in agent.get("events", []):
                    if self._has_real_threats(event):
                        total_amenazas += 1
                        agentes_con_amenazas += 1
                        break

            lines.append(f"RESUMEN: {len(report_data['agents'])} equipos monitorizados")
            if total_amenazas == 0:
                lines.append("Estado: Sin amenazas detectadas en las ultimas 24h")
            else:
                lines.append(f"Estado: {total_amenazas} amenazas detectadas en {agentes_con_amenazas} equipos")
            lines.append("")

        for agent in report_data["agents"]:
            if include_summary:
                lines.append("-" * 60)
                lines.append(f"EQUIPO: {agent['hostname']} ({agent['os_type']})")
                lines.append(f"ID: {agent['agent_id']}")
                lines.append(f"Ultima conexion: {self._format_datetime(agent['last_seen'])}")
                lines.append("")

            if not include_network and not include_system:
                continue

            eventos_con_amenazas = [e for e in agent.get("events", []) if self._has_real_threats(e)]

            if not eventos_con_amenazas:
                if include_summary:
                    lines.append("  Sin amenazas detectadas")
                    lines.append("")
                continue

            if not include_summary:
                lines.append("-" * 60)
                lines.append(f"EQUIPO: {agent['hostname']} ({agent['os_type']})")
                lines.append("")

            for event in eventos_con_amenazas:
                lines.append(f"  [{event['severity'].upper()}] {event['title']}")
                extra = event.get("extra_data", {}) or {}

                has_known_data = bool(
                    extra.get("ssh_failures") or extra.get("nginx_suspicious")
                    or extra.get("firewall_blocked") or extra.get("sudo_failures")
                    or extra.get("high_risk_ips") or extra.get("service_failures")
                    or extra.get("defender_alerts") or extra.get("defender_protection_disabled")
                )
                if not has_known_data:
                    occurred = self._format_datetime(event.get("occurred_at"))
                    lines.append(f"    Fecha: {occurred}")
                    lines.append("")
                    continue

                if include_network:
                    ssh = extra.get("ssh_failures", [])
                    if ssh:
                        lines.append(f"    SSH fallidos: {len(ssh)} IPs")
                        for item in ssh[:5]:
                            lines.append(f"      - {item.get('ip')}: {item.get('attempts')} intentos")

                    nginx = extra.get("nginx_suspicious", [])
                    if nginx:
                        lines.append(f"    Nginx/Apache sospechosos: {len(nginx)} IPs")
                        for item in nginx[:5]:
                            lines.append(f"      - {item.get('ip')}: {item.get('count')} peticiones")

                    fw = extra.get("firewall_blocked", [])
                    if fw:
                        lines.append(f"    Firewall bloqueados: {len(fw)} IPs")
                        for item in fw[:5]:
                            lines.append(f"      - {item.get('ip')}: {item.get('blocks')} bloqueos")

                    high_risk = extra.get("high_risk_ips", [])
                    if high_risk:
                        lines.append(f"    IPs alto riesgo: {', '.join(high_risk)}")

                if include_system:
                    sudo = extra.get("sudo_failures", [])
                    if sudo:
                        lines.append(f"    Sudo/Su fallidos: {len(sudo)} IPs")
                        for item in sudo[:5]:
                            lines.append(f"      - {item.get('ip')}: {item.get('attempts')} intentos")

                    services = extra.get("service_failures", [])
                    if services:
                        lines.append(f"    Servicios con errores: {len(services)}")
                        for svc in services[:5]:
                            lines.append(f"      - {svc.get('service')}: {svc.get('error_count')} errores")

                    if extra.get("defender_protection_disabled"):
                        lines.append("    !! WINDOWS DEFENDER: Proteccion DESACTIVADA !!")

                    defender = extra.get("defender_alerts", [])
                    if defender:
                        lines.append(f"    Windows Defender: {len(defender)} alertas")
                        for alert in defender[:5]:
                            lines.append(f"      - [{alert.get('event_id')}] {alert.get('message')}")

                lines.append("")

        lines.append("=" * 60)
        lines.append("Reporte generado automaticamente por PibiCyber")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _aggregate_threats(self, events: list) -> dict:
        """Aggregate all threat data across events for a device."""
        agg = {
            "ssh_failures": [],
            "nginx_suspicious": [],
            "firewall_blocked": [],
            "high_risk_ips": [],
            "sudo_failures": [],
            "service_failures": [],
            "defender_alerts": [],
            "defender_protection_disabled": False,
            "max_severity": "info",
            "standalone_alerts": [],
        }
        severity_rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        seen_ips = {"ssh": set(), "nginx": set(), "fw": set(), "sudo": set(), "risk": set()}
        seen_services = set()

        for event in events:
            sev = event.get("severity", "info")
            if severity_rank.get(sev, 0) > severity_rank.get(agg["max_severity"], 0):
                agg["max_severity"] = sev

            extra = event.get("extra_data", {}) or {}

            for item in extra.get("ssh_failures", []):
                ip = item.get("ip")
                if ip and ip not in seen_ips["ssh"]:
                    seen_ips["ssh"].add(ip)
                    agg["ssh_failures"].append(item)

            for item in extra.get("nginx_suspicious", []):
                ip = item.get("ip")
                if ip and ip not in seen_ips["nginx"]:
                    seen_ips["nginx"].add(ip)
                    agg["nginx_suspicious"].append(item)

            for item in extra.get("firewall_blocked", []):
                ip = item.get("ip")
                if ip and ip not in seen_ips["fw"]:
                    seen_ips["fw"].add(ip)
                    agg["firewall_blocked"].append(item)

            for ip in extra.get("high_risk_ips", []):
                if ip and ip not in seen_ips["risk"]:
                    seen_ips["risk"].add(ip)
                    agg["high_risk_ips"].append(ip)

            for item in extra.get("sudo_failures", []):
                ip = item.get("ip")
                if ip and ip not in seen_ips["sudo"]:
                    seen_ips["sudo"].add(ip)
                    agg["sudo_failures"].append(item)

            for item in extra.get("service_failures", []):
                svc = item.get("service")
                if svc and svc not in seen_services:
                    seen_services.add(svc)
                    agg["service_failures"].append(item)

            if extra.get("defender_protection_disabled"):
                agg["defender_protection_disabled"] = True

            for item in extra.get("defender_alerts", []):
                agg["defender_alerts"].append(item)

            # Collect high/critical events that have no recognized extra_data fields
            has_known_data = bool(
                extra.get("ssh_failures") or extra.get("nginx_suspicious")
                or extra.get("firewall_blocked") or extra.get("sudo_failures")
                or extra.get("high_risk_ips") or extra.get("service_failures")
                or extra.get("defender_alerts") or extra.get("defender_protection_disabled")
            )
            if not has_known_data and sev in ("critical", "high"):
                agg["standalone_alerts"].append({
                    "title": event.get("title", "Alerta"),
                    "severity": sev,
                    "occurred_at": event.get("occurred_at"),
                })

        return agg

    def generate_excel_report(self, report_data: dict) -> bytes:
        """Generate a comprehensive Excel report extracting ALL data from events.

        Processes login_monitor, security_monitor, resource_monitor, pip-audit CVE,
        and Windows Defender events. Applies PibiCyber brand styling with Steel Blue
        headers, severity-coded rows, freeze panes, auto-filter, and tab colors.
        """
        wb = Workbook()

        # --- Brand colors ---
        STEEL_BLUE = "4682B4"
        NAVY       = "2D4A6B"
        RED_BRICK  = "CB4154"

        header_font  = Font(bold=True, color="FFFFFF", size=10, name="Calibri")
        title_font   = Font(bold=True, color="FFFFFF", size=13, name="Calibri")
        info_font    = Font(italic=True, color="6C757D", size=9,  name="Calibri")
        num_align    = Alignment(horizontal="right",  vertical="center")
        center_align = Alignment(horizontal="center", vertical="center")
        left_align   = Alignment(horizontal="left",   vertical="center", indent=1)

        header_fill = PatternFill(start_color=STEEL_BLUE, end_color=STEEL_BLUE, fill_type="solid")
        title_fill  = PatternFill(start_color=NAVY,       end_color=NAVY,       fill_type="solid")
        alt_fill    = PatternFill(start_color="EEF3F8",   end_color="EEF3F8",   fill_type="solid")
        info_fill   = PatternFill(start_color="F4F7FB",   end_color="F4F7FB",   fill_type="solid")

        severity_fills = {
            "critical": PatternFill(start_color="FADADD", end_color="FADADD", fill_type="solid"),
            "high":     PatternFill(start_color="FDE8E8", end_color="FDE8E8", fill_type="solid"),
            "medium":   PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid"),
        }

        thin  = Side(style="thin", color="DEE2E6")
        bdr   = Border(left=thin, right=thin, top=thin, bottom=thin)

        generated = self._format_datetime(report_data["generated_at"])
        hours     = report_data["period_hours"]
        info_text = f"PibiCyber  ·  Generado: {generated}  |  Período: últimas {hours}h"

        def setup_sheet(ws, sheet_title, columns, tab_color=None, banner=None):
            ws.title = sheet_title[:31]
            if tab_color:
                ws.sheet_properties.tabColor = tab_color
            ncols = len(columns)
            display_title = banner or sheet_title

            # Row 1 — sheet title banner
            ws.append([display_title] + [""] * (ncols - 1))
            if ncols > 1:
                ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
            c = ws.cell(row=1, column=1)
            c.font = title_font; c.fill = title_fill; c.alignment = left_align
            ws.row_dimensions[1].height = 26

            # Row 2 — info bar
            ws.append([info_text] + [""] * (ncols - 1))
            if ncols > 1:
                ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
            c = ws.cell(row=2, column=1)
            c.font = info_font; c.fill = info_fill; c.alignment = left_align
            ws.row_dimensions[2].height = 16

            # Row 3 — column headers
            ws.append(columns)
            for ci in range(1, ncols + 1):
                c = ws.cell(row=3, column=ci)
                c.font = header_font; c.fill = header_fill
                c.alignment = center_align; c.border = bdr
            ws.row_dimensions[3].height = 20

            ws.freeze_panes = ws.cell(row=4, column=1)

        def add_row(ws, values, row_fill=None, row_num=0):
            ws.append(values)
            ridx  = ws.max_row
            ncols = len(values)
            fill  = row_fill if row_fill else (alt_fill if row_num % 2 == 1 else None)
            for ci in range(1, ncols + 1):
                c = ws.cell(row=ridx, column=ci)
                c.border = bdr
                if fill:
                    c.fill = fill

        def finalize_sheet(ws, ncols):
            if ws.max_row >= 3:
                ws.auto_filter.ref = f"A3:{get_column_letter(ncols)}{ws.max_row}"
            for col in ws.columns:
                max_len = 8
                col_letter = None
                for cell in col:
                    if col_letter is None and hasattr(cell, "column_letter"):
                        col_letter = cell.column_letter
                    max_len = max(max_len, len(str(cell.value) if cell.value else ""))
                if col_letter:
                    ws.column_dimensions[col_letter].width = min(max_len + 3, 55)

        # --- Collect ALL data from ALL events across ALL agents ---
        all_failed_logins     = []
        all_successful_logins = []
        all_anomalies         = []
        all_sudo_sessions     = []
        all_ssh               = []
        all_fw                = []
        all_nginx             = []
        all_sudo_failures     = []
        all_services          = []
        all_defender          = []
        all_high_risk         = []
        all_threat_scores     = []
        all_resource_alerts   = []
        all_cve_alerts        = []
        all_bans              = []
        all_standalone        = []
        summary_rows          = []

        severity_rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

        for agent in report_data["agents"]:
            hostname  = agent.get("hostname", "?")
            os_type   = agent.get("os_type", "?")
            last_seen = self._format_datetime(agent.get("last_seen"))
            cnt = dict(failed=0, success=0, anomalies=0, ssh=0, fw=0,
                       nginx=0, resources=0, cves=0)
            max_severity = "info"

            for event in agent.get("events", []):
                extra      = event.get("extra_data", {}) or {}
                sev        = event.get("severity", "info")
                event_time = self._format_datetime(event.get("occurred_at"))
                if severity_rank.get(sev, 0) > severity_rank.get(max_severity, 0):
                    max_severity = sev

                # login_monitor
                for item in extra.get("failed_logins", []):
                    all_failed_logins.append({
                        "user": item.get("user", "?"), "ip": item.get("ip", "?"),
                        "method": item.get("method", "?"), "time": item.get("time", "?"),
                        "device": hostname, "os": os_type,
                    })
                cnt["failed"] += len(extra.get("failed_logins", []))

                for item in extra.get("successful_logins", []):
                    all_successful_logins.append({
                        "user": item.get("user", "?"), "ip": item.get("ip", "?"),
                        "method": item.get("method", "?"), "time": item.get("time", "?"),
                        "device": hostname, "os": os_type,
                    })
                cnt["success"] += len(extra.get("successful_logins", []))

                for item in extra.get("anomalies", []):
                    all_anomalies.append({
                        "type": item.get("type", "?"), "ip": item.get("ip", "?"),
                        "count": item.get("count", 0), "detail": item.get("detail", ""),
                        "device": hostname, "os": os_type,
                    })
                cnt["anomalies"] += len(extra.get("anomalies", []))

                for item in extra.get("sudo_sessions", []):
                    all_sudo_sessions.append({
                        "user": item.get("user", "?"), "command": item.get("command", "?"),
                        "time": item.get("time", "?"), "device": hostname, "os": os_type,
                    })

                # security_monitor
                for item in extra.get("ssh_failures", []):
                    all_ssh.append({
                        "ip": item.get("ip", "?"), "attempts": item.get("attempts", 0),
                        "device": hostname, "os": os_type,
                    })
                cnt["ssh"] += len(extra.get("ssh_failures", []))

                for item in extra.get("firewall_blocked", []):
                    all_fw.append({
                        "ip": item.get("ip", "?"), "blocks": item.get("blocks", 0),
                        "device": hostname, "os": os_type,
                    })
                cnt["fw"] += len(extra.get("firewall_blocked", []))

                for item in extra.get("nginx_suspicious", []):
                    all_nginx.append({
                        "ip": item.get("ip", "?"), "count": item.get("count", 0),
                        "device": hostname, "os": os_type,
                    })
                cnt["nginx"] += len(extra.get("nginx_suspicious", []))

                for item in extra.get("sudo_failures", []):
                    all_sudo_failures.append({
                        "ip": item.get("ip", "?"), "attempts": item.get("attempts", 0),
                        "device": hostname, "os": os_type,
                    })

                for item in extra.get("service_failures", []):
                    all_services.append({
                        "service": item.get("service", "?"), "errors": item.get("error_count", 0),
                        "device": hostname, "os": os_type,
                    })

                for item in extra.get("defender_alerts", []):
                    all_defender.append({
                        "type": item.get("type", "?"), "message": item.get("message", "?"),
                        "event_id": item.get("event_id", "?"), "date": item.get("date", "?"),
                        "device": hostname,
                    })

                for ip in extra.get("high_risk_ips", []):
                    all_high_risk.append({"ip": ip, "device": hostname, "os": os_type})

                for item in extra.get("threat_scores", []):
                    reasons = item.get("reasons", [])
                    all_threat_scores.append({
                        "ip": item.get("ip", "?"), "score": item.get("score", 0),
                        "reasons": ", ".join(reasons) if isinstance(reasons, list) else str(reasons),
                        "device": hostname, "os": os_type,
                    })

                # resource_monitor (disk / RAM / CPU)
                is_resource = (extra.get("disk") is not None
                               or extra.get("ram") is not None
                               or extra.get("cpu") is not None)
                if is_resource:
                    disk_items   = extra.get("disk") or []
                    disk_pct_max = max((d.get("pct", 0) for d in disk_items), default=0)
                    ram          = extra.get("ram") or {}
                    cpu          = extra.get("cpu") or {}
                    alerts_raw   = extra.get("alerts") or []
                    all_resource_alerts.append({
                        "time": event_time, "device": hostname, "os": os_type,
                        "severity": sev, "disk_pct_max": disk_pct_max,
                        "ram_pct": ram.get("pct", 0),
                        "cpu_load": cpu.get("load_per_core", "—"),
                        "alerts": "; ".join(str(a) for a in alerts_raw) if alerts_raw else event.get("title", ""),
                    })
                    cnt["resources"] += 1

                # pip_audit CVEs
                for vuln in extra.get("vulnerabilities", []):
                    cves  = vuln.get("cves", [])
                    fixes = vuln.get("fix_versions", [])
                    all_cve_alerts.append({
                        "package": vuln.get("package", "?"),
                        "version": vuln.get("version", "?"),
                        "cves": ", ".join(cves) if isinstance(cves, list) else str(cves),
                        "fix_versions": ", ".join(fixes) if isinstance(fixes, list) and fixes else "N/A",
                        "device": hostname, "time": event_time,
                    })
                cnt["cves"] += len(extra.get("vulnerabilities", []))

                # Ban events (ssh_threat_manager)
                if extra.get("banned_ip"):
                    all_bans.append({
                        "ip": extra.get("banned_ip", "?"),
                        "reason": extra.get("ban_reason", "?"),
                        "device": hostname, "os": os_type, "time": event_time,
                    })

                # Standalone high/critical events with no recognized structured data
                has_known = bool(
                    extra.get("ssh_failures") or extra.get("nginx_suspicious")
                    or extra.get("firewall_blocked") or extra.get("sudo_failures")
                    or extra.get("high_risk_ips") or extra.get("service_failures")
                    or extra.get("defender_alerts") or extra.get("defender_protection_disabled")
                    or extra.get("failed_logins") or extra.get("successful_logins")
                    or extra.get("anomalies") or extra.get("sudo_sessions")
                    or extra.get("threat_scores") or extra.get("banned_ip")
                    or is_resource or extra.get("vulnerabilities")
                )
                if not has_known and sev in ("critical", "high", "medium"):
                    all_standalone.append({
                        "time": event_time, "title": event.get("title", "Alerta"),
                        "category": event.get("category", "?"),
                        "severity": sev, "device": hostname, "os": os_type,
                    })

            summary_rows.append({
                "hostname": hostname, "os": os_type, "last_seen": last_seen,
                "max_severity": max_severity,
                "total_events": len(agent.get("events", [])),
                "failed": cnt["failed"], "success": cnt["success"],
                "anomalies": cnt["anomalies"],
                "ssh": cnt["ssh"], "fw": cnt["fw"], "nginx": cnt["nginx"],
                "resources": cnt["resources"], "cves": cnt["cves"],
            })

        # ============== SHEET 1: Resumen (always present) ==============
        ws = wb.active
        RESUMEN_COLS = [
            "Dispositivo", "SO", "Última conexión", "Severidad máx.",
            "Eventos", "Logins fallidos", "Logins OK", "Anomalías",
            "SSH IPs", "FW bloqueados", "Nginx susp.", "Alertas recursos", "CVEs",
        ]
        setup_sheet(ws, "Resumen", RESUMEN_COLS, tab_color=STEEL_BLUE,
                    banner="Resumen — PibiCyber Security Report")
        for i, r in enumerate(summary_rows):
            add_row(ws, [
                r["hostname"], r["os"], r["last_seen"], r["max_severity"].upper(),
                r["total_events"], r["failed"], r["success"], r["anomalies"],
                r["ssh"], r["fw"], r["nginx"], r["resources"], r["cves"],
            ], row_fill=severity_fills.get(r["max_severity"]), row_num=i)
        finalize_sheet(ws, len(RESUMEN_COLS))

        # ============== SHEET 2: Anomalías / Fuerza bruta ==============
        if all_anomalies:
            ws = wb.create_sheet()
            COLS = ["IP", "Tipo", "Intentos", "Detalle", "Dispositivo", "SO"]
            setup_sheet(ws, "Anomalías", COLS, tab_color=RED_BRICK,
                        banner="Anomalías / Fuerza bruta")
            for i, item in enumerate(sorted(all_anomalies, key=lambda x: x["count"], reverse=True)):
                add_row(ws, [item["ip"], item["type"], item["count"],
                             item["detail"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 3: Logins fallidos ==============
        if all_failed_logins:
            ws = wb.create_sheet()
            COLS = ["Hora", "IP", "Usuario", "Método", "Dispositivo", "SO"]
            setup_sheet(ws, "Logins fallidos", COLS, tab_color=RED_BRICK)
            for i, item in enumerate(all_failed_logins):
                add_row(ws, [item["time"], item["ip"], item["user"],
                             item["method"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 4: Logins exitosos ==============
        if all_successful_logins:
            ws = wb.create_sheet()
            COLS = ["Hora", "IP", "Usuario", "Método", "Dispositivo", "SO"]
            setup_sheet(ws, "Logins exitosos", COLS, tab_color="28A745")
            for i, item in enumerate(all_successful_logins):
                add_row(ws, [item["time"], item["ip"], item["user"],
                             item["method"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 5: Sesiones sudo ==============
        if all_sudo_sessions:
            ws = wb.create_sheet()
            COLS = ["Hora", "Usuario", "Comando", "Dispositivo", "SO"]
            setup_sheet(ws, "Sesiones sudo", COLS, tab_color="E6960B")
            for i, item in enumerate(all_sudo_sessions):
                add_row(ws, [item["time"], item["user"], item["command"],
                             item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 6: Ataques SSH ==============
        if all_ssh:
            ws = wb.create_sheet()
            COLS = ["IP", "Intentos", "Dispositivo", "SO"]
            setup_sheet(ws, "Ataques SSH", COLS, tab_color=RED_BRICK)
            for i, item in enumerate(sorted(all_ssh, key=lambda x: x["attempts"], reverse=True)):
                add_row(ws, [item["ip"], item["attempts"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 7: Firewall bloqueados ==============
        if all_fw:
            ws = wb.create_sheet()
            COLS = ["IP", "Bloqueos", "Dispositivo", "SO"]
            setup_sheet(ws, "Firewall bloqueados", COLS, tab_color=RED_BRICK)
            for i, item in enumerate(sorted(all_fw, key=lambda x: x["blocks"], reverse=True)):
                add_row(ws, [item["ip"], item["blocks"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 8: Nginx / Apache sospechosos ==============
        if all_nginx:
            ws = wb.create_sheet()
            COLS = ["IP", "Peticiones", "Dispositivo", "SO"]
            setup_sheet(ws, "Nginx", COLS, tab_color="E6960B",
                        banner="Nginx / Apache sospechosos")
            for i, item in enumerate(sorted(all_nginx, key=lambda x: x["count"], reverse=True)):
                add_row(ws, [item["ip"], item["count"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 9: Sudo / Su fallidos ==============
        if all_sudo_failures:
            ws = wb.create_sheet()
            COLS = ["IP", "Intentos", "Dispositivo", "SO"]
            setup_sheet(ws, "Sudo fallidos", COLS, tab_color=RED_BRICK,
                        banner="Sudo / Su fallidos")
            for i, item in enumerate(sorted(all_sudo_failures, key=lambda x: x["attempts"], reverse=True)):
                add_row(ws, [item["ip"], item["attempts"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 10: Servicios con errores ==============
        if all_services:
            ws = wb.create_sheet()
            COLS = ["Servicio", "Errores", "Dispositivo", "SO"]
            setup_sheet(ws, "Servicios", COLS, tab_color="E6960B",
                        banner="Servicios con errores")
            for i, item in enumerate(sorted(all_services, key=lambda x: x["errors"], reverse=True)):
                add_row(ws, [item["service"], item["errors"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 11: Windows Defender ==============
        if all_defender:
            ws = wb.create_sheet()
            COLS = ["Tipo", "Mensaje", "Event ID", "Fecha", "Dispositivo"]
            setup_sheet(ws, "Windows Defender", COLS, tab_color=RED_BRICK)
            for i, item in enumerate(all_defender):
                add_row(ws, [item["type"], item["message"], item["event_id"],
                             item["date"], item["device"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 12: IPs Alto Riesgo ==============
        if all_high_risk:
            ws = wb.create_sheet()
            COLS = ["IP", "Dispositivo", "SO"]
            setup_sheet(ws, "IPs Alto Riesgo", COLS, tab_color=RED_BRICK)
            for i, item in enumerate(all_high_risk):
                add_row(ws, [item["ip"], item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 13: Puntuaciones de amenaza ==============
        if all_threat_scores:
            ws = wb.create_sheet()
            COLS = ["IP", "Puntuación", "Razones", "Dispositivo", "SO"]
            setup_sheet(ws, "Threat Scores", COLS, tab_color=RED_BRICK,
                        banner="Puntuaciones de Amenaza")
            for i, item in enumerate(sorted(all_threat_scores, key=lambda x: x["score"], reverse=True)):
                add_row(ws, [item["ip"], item["score"], item["reasons"],
                             item["device"], item["os"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 14: Vulnerabilidades CVE (pip-audit) ==============
        if all_cve_alerts:
            ws = wb.create_sheet()
            COLS = ["Paquete", "Versión instalada", "CVEs", "Versiones con fix", "Dispositivo", "Fecha"]
            setup_sheet(ws, "CVEs", COLS, tab_color=RED_BRICK,
                        banner="Vulnerabilidades CVE (pip-audit)")
            for i, item in enumerate(all_cve_alerts):
                add_row(ws, [item["package"], item["version"], item["cves"],
                             item["fix_versions"], item["device"], item["time"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 15: Alertas de recursos (resource_monitor) ==============
        if all_resource_alerts:
            ws = wb.create_sheet()
            COLS = ["Fecha", "Dispositivo", "SO", "Severidad", "Disco máx %", "RAM %", "Carga CPU", "Alertas"]
            setup_sheet(ws, "Recursos", COLS, tab_color="E6960B",
                        banner="Alertas de Recursos (disco / RAM / CPU)")
            for i, item in enumerate(all_resource_alerts):
                add_row(ws, [
                    item["time"], item["device"], item["os"], item["severity"].upper(),
                    item["disk_pct_max"], item["ram_pct"], item["cpu_load"], item["alerts"],
                ], row_fill=severity_fills.get(item["severity"]), row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 16: IPs baneadas (ssh_threat_manager) ==============
        if all_bans:
            ws = wb.create_sheet()
            COLS = ["IP", "Motivo del ban", "Dispositivo", "SO", "Fecha"]
            setup_sheet(ws, "IPs Baneadas", COLS, tab_color=RED_BRICK)
            for i, item in enumerate(all_bans):
                add_row(ws, [item["ip"], item["reason"], item["device"],
                             item["os"], item["time"]], row_num=i)
            finalize_sheet(ws, len(COLS))

        # ============== SHEET 17: Alertas generales (sin datos estructurados) ==============
        if all_standalone:
            ws = wb.create_sheet()
            COLS = ["Fecha", "Título", "Categoría", "Severidad", "Dispositivo", "SO"]
            setup_sheet(ws, "Alertas", COLS, tab_color="E6960B",
                        banner="Alertas generales")
            for i, item in enumerate(all_standalone):
                add_row(ws, [
                    item["time"], item["title"], item["category"],
                    item["severity"].upper(), item["device"], item["os"],
                ], row_fill=severity_fills.get(item["severity"]), row_num=i)
            finalize_sheet(ws, len(COLS))

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    def format_report_html(self, report_data: dict, categories: dict | None = None) -> str:
        """Convert report data to professional HTML email format."""
        include_network = categories.get("network_threats", True) if categories else True
        include_system = categories.get("system_threats", True) if categories else True
        include_summary = categories.get("general_summary", True) if categories else True

        e = html.escape
        generated = self._format_datetime(report_data["generated_at"])
        hours = report_data["period_hours"]

        # Pre-compute threat stats
        devices_with_threats = []
        devices_without_threats = []
        total_threat_events = 0

        for agent in report_data["agents"]:
            agent_threats = [ev for ev in agent.get("events", []) if self._has_real_threats(ev)]
            if agent_threats:
                agg = self._aggregate_threats(agent_threats)
                devices_with_threats.append((agent, agg))
                total_threat_events += len(agent_threats)
            else:
                devices_without_threats.append(agent)

        total_devices = len(report_data["agents"])
        num_with_threats = len(devices_with_threats)

        # Status indicator
        if num_with_threats == 0:
            status_color = "#28A745"
            status_icon = "&#10003;"
            status_text = "Sin amenazas detectadas"
        elif num_with_threats <= 2:
            status_color = "#E6960B"
            status_icon = "&#9888;"
            status_text = "Amenazas menores detectadas"
        else:
            status_color = "#B22222"
            status_icon = "&#9888;"
            status_text = "Atencion requerida"

        severity_styles = {
            "critical": ("background:#F8D7DA;color:#8B2500;", "CRITICO"),
            "high": ("background:#F8D7DA;color:#8B2500;", "ALTO"),
            "medium": ("background:#FFF3CD;color:#856404;", "MEDIO"),
            "low": ("background:#D1ECF1;color:#2C5F7C;", "BAJO"),
            "info": ("background:#DEE2E6;color:#383D41;", "INFO"),
        }

        parts = []

        # Outer wrapper
        parts.append(
            '<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F2F5;">'
            '<tr><td align="center" style="padding:20px 10px;">'
            '<table width="600" cellpadding="0" cellspacing="0" style="font-family:Arial,Helvetica,sans-serif;color:#333;line-height:1.6;">'
        )

        # Header banner
        parts.append(
            '<tr><td style="background:#2C5F7C;padding:24px 30px;text-align:center;border-radius:8px 8px 0 0;">'
            '<div style="font-size:22px;font-weight:700;color:#FFFFFF;letter-spacing:0.5px;">&#128737; PibiCyber</div>'
            '<div style="font-size:13px;color:#B0C4DE;margin-top:4px;">Informe Consolidado de Seguridad</div>'
            '</td></tr>'
        )

        # Date bar
        parts.append(
            f'<tr><td style="background:#FFFFFF;padding:12px 30px;border-bottom:1px solid #DEE2E6;font-size:12px;color:#6C757D;">'
            f'Generado: {e(generated)} &nbsp;|&nbsp; Periodo: ultimas {hours}h'
            f'</td></tr>'
        )

        # Executive summary
        if include_summary:
            parts.append(
                '<tr><td style="padding:20px 20px 10px;">'
                '<table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border-radius:8px;border:1px solid #DEE2E6;">'
                '<tr>'
                f'<td style="width:55px;vertical-align:top;padding:18px 0 18px 18px;">'
                f'<div style="width:40px;height:40px;border-radius:50%;background:{status_color};text-align:center;line-height:40px;color:#FFFFFF;font-size:18px;">'
                f'{status_icon}</div></td>'
                f'<td style="padding:18px 18px 18px 12px;">'
                f'<div style="font-size:16px;font-weight:700;color:#2C5F7C;margin-bottom:4px;">{e(status_text)}</div>'
                f'<div style="font-size:13px;color:#6C757D;">'
                f'{total_devices} equipos monitorizados &nbsp;|&nbsp; '
                f'{num_with_threats} con incidencias &nbsp;|&nbsp; '
                f'{total_threat_events} amenazas totales</div>'
                f'</td></tr></table>'
                '</td></tr>'
            )

        # Devices WITH threats
        for agent, agg in devices_with_threats:
            if not include_network and not include_system:
                continue

            hostname = e(agent.get("hostname", "?"))
            os_type = e(agent.get("os_type", "?"))
            agent_id = e(agent.get("agent_id", "?"))
            last_seen = self._format_datetime(agent.get("last_seen"))
            max_sev = agg["max_severity"]
            sev_style, sev_label = severity_styles.get(max_sev, severity_styles["info"])

            # Border color based on severity
            border_color = "#B22222" if max_sev in ("critical", "high") else "#E6960B" if max_sev == "medium" else "#4682B4"

            parts.append(
                f'<tr><td style="padding:10px 20px;">'
                f'<table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border-radius:8px;border:1px solid #DEE2E6;border-left:4px solid {border_color};">'
            )

            # Device header with severity badge
            parts.append(
                f'<tr><td style="padding:16px 20px;border-bottom:1px solid #DEE2E6;background:#F8F9FA;">'
                f'<table width="100%" cellpadding="0" cellspacing="0"><tr>'
                f'<td style="font-size:15px;font-weight:700;color:#2C5F7C;">{hostname}</td>'
                f'<td style="text-align:right;">'
                f'<span style="display:inline-block;padding:3px 10px;border-radius:10px;font-size:11px;font-weight:600;{sev_style}">'
                f'{sev_label}</span></td>'
                f'</tr></table>'
                f'<div style="font-size:11px;color:#6C757D;margin-top:4px;">'
                f'{os_type} &nbsp;|&nbsp; Ultima conexion: {e(last_seen)}</div>'
                f'</td></tr>'
            )

            has_network = bool(agg["ssh_failures"] or agg["nginx_suspicious"] or agg["firewall_blocked"] or agg["high_risk_ips"])
            has_system = bool(agg["sudo_failures"] or agg["service_failures"] or agg["defender_alerts"] or agg["defender_protection_disabled"])

            # Network threats section
            if include_network and has_network:
                parts.append(
                    '<tr><td style="padding:0;">'
                    '<table width="100%" cellpadding="0" cellspacing="0">'
                    '<tr><td style="padding:14px 20px 6px;font-size:13px;font-weight:700;color:#2C5F7C;'
                    'border-bottom:2px solid #B0C4DE;">'
                    '&#127760; Amenazas de Red</td></tr>'
                    '<tr><td style="padding:10px 20px 16px;">'
                )

                ssh = agg["ssh_failures"]
                if ssh:
                    parts.append(self._html_threat_table(
                        f"SSH fallidos ({len(ssh)} IPs)", ssh, "ip", "attempts", "intentos"))

                nginx = agg["nginx_suspicious"]
                if nginx:
                    parts.append(self._html_threat_table(
                        f"Nginx/Apache sospechosos ({len(nginx)} IPs)", nginx, "ip", "count", "peticiones"))

                fw = agg["firewall_blocked"]
                if fw:
                    parts.append(self._html_threat_table(
                        f"Firewall bloqueados ({len(fw)} IPs)", fw, "ip", "blocks", "bloqueos"))

                high_risk = agg["high_risk_ips"]
                if high_risk:
                    badges = "".join(
                        f'<span style="display:inline-block;background:#F8D7DA;color:#8B2500;padding:3px 10px;'
                        f'border-radius:4px;font-size:12px;font-family:Consolas,Monaco,monospace;font-weight:600;'
                        f'margin:3px 4px 3px 0;">{e(str(ip))}</span>'
                        for ip in high_risk[:10]
                    )
                    remaining = ""
                    if len(high_risk) > 10:
                        remaining = f'<span style="font-size:11px;color:#6C757D;"> +{len(high_risk) - 10} mas</span>'
                    parts.append(
                        f'<div style="margin:10px 0 4px;">'
                        f'<div style="font-size:12px;font-weight:600;color:#B22222;padding:6px 0 6px;">&#9888; IPs alto riesgo</div>'
                        f'<div>{badges}{remaining}</div></div>'
                    )

                parts.append('</td></tr></table></td></tr>')

            # System threats section
            if include_system and has_system:
                # Separator if both sections present
                separator = ''
                if include_network and has_network:
                    separator = 'border-top:1px solid #DEE2E6;'

                parts.append(
                    f'<tr><td style="padding:0;{separator}">'
                    '<table width="100%" cellpadding="0" cellspacing="0">'
                    '<tr><td style="padding:14px 20px 6px;font-size:13px;font-weight:700;color:#2C5F7C;'
                    'border-bottom:2px solid #B0C4DE;">'
                    '&#128187; Amenazas del Sistema</td></tr>'
                    '<tr><td style="padding:10px 20px 16px;">'
                )

                sudo = agg["sudo_failures"]
                if sudo:
                    parts.append(self._html_threat_table(
                        f"Sudo/Su fallidos ({len(sudo)} IPs)", sudo, "ip", "attempts", "intentos"))

                services = agg["service_failures"]
                if services:
                    parts.append(self._html_threat_table(
                        f"Servicios con errores ({len(services)})", services, "service", "error_count", "errores"))

                # Windows Defender
                if agg["defender_protection_disabled"]:
                    parts.append(
                        '<div style="margin:10px 0;padding:10px 14px;background:#F8D7DA;border:1px solid #F5C6CB;'
                        'border-radius:6px;font-size:13px;color:#8B2500;font-weight:600;">'
                        '&#9888; Windows Defender: Proteccion en tiempo real DESACTIVADA</div>'
                    )

                defender = agg["defender_alerts"]
                if defender:
                    parts.append(self._html_threat_table(
                        f"Windows Defender ({len(defender)} alertas)", defender, "message", "event_id", "ID"))

                parts.append('</td></tr></table></td></tr>')

            # Standalone alerts (high/critical without recognized extra_data)
            standalone = agg.get("standalone_alerts", [])
            if standalone:
                separator = ''
                if (include_network and has_network) or (include_system and has_system):
                    separator = 'border-top:1px solid #DEE2E6;'

                parts.append(
                    f'<tr><td style="padding:0;{separator}">'
                    '<table width="100%" cellpadding="0" cellspacing="0">'
                    '<tr><td style="padding:14px 20px 6px;font-size:13px;font-weight:700;color:#2C5F7C;'
                    'border-bottom:2px solid #B0C4DE;">'
                    '&#9888; Alertas</td></tr>'
                    '<tr><td style="padding:10px 20px 16px;">'
                )

                for alert in standalone:
                    alert_sev = alert.get("severity", "high")
                    alert_style, alert_label = severity_styles.get(alert_sev, severity_styles["info"])
                    alert_title = e(alert.get("title", "Alerta"))
                    alert_date = self._format_datetime(alert.get("occurred_at"))
                    parts.append(
                        f'<div style="margin:6px 0;padding:10px 14px;background:#F8F9FA;border-radius:6px;'
                        f'border-left:3px solid {"#B22222" if alert_sev == "critical" else "#E6960B"};">'
                        f'<span style="display:inline-block;padding:2px 8px;border-radius:8px;font-size:10px;'
                        f'font-weight:600;{alert_style}margin-right:8px;">{alert_label}</span>'
                        f'<span style="font-size:13px;font-weight:600;color:#333;">{alert_title}</span>'
                        f'<div style="font-size:11px;color:#6C757D;margin-top:4px;">{e(alert_date)}</div>'
                        f'</div>'
                    )

                parts.append('</td></tr></table></td></tr>')

            parts.append('</table></td></tr>')

        # Devices WITHOUT threats - compact summary
        if devices_without_threats and include_summary:
            hostnames = [e(a.get("hostname", "?")) for a in devices_without_threats]
            if len(hostnames) > 5:
                names_text = ", ".join(hostnames[:5]) + f" +{len(hostnames) - 5} mas"
            else:
                names_text = ", ".join(hostnames)

            parts.append(
                '<tr><td style="padding:10px 20px;">'
                '<table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border-radius:8px;border:1px solid #DEE2E6;border-left:4px solid #28A745;">'
                '<tr><td style="padding:14px 20px;">'
                f'<span style="color:#28A745;font-weight:700;font-size:15px;">&#10003;</span>'
                f'<span style="font-size:13px;font-weight:600;color:#333;margin-left:8px;">'
                f'{len(devices_without_threats)} equipos sin incidencias</span>'
                f'<div style="font-size:12px;color:#6C757D;margin-top:6px;">{names_text}</div>'
                '</td></tr></table></td></tr>'
            )

        # No devices at all
        if total_devices == 0 and include_summary:
            parts.append(
                '<tr><td style="padding:10px 20px;">'
                '<table width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border-radius:8px;border:1px solid #DEE2E6;">'
                '<tr><td style="padding:18px;text-align:center;font-size:13px;color:#6C757D;">'
                'No hay equipos registrados'
                '</td></tr></table></td></tr>'
            )

        # Footer
        parts.append(
            '<tr><td style="height:10px;"></td></tr>'
            '<tr><td style="background:#2C5F7C;padding:18px 30px;text-align:center;border-radius:0 0 8px 8px;">'
            f'<div style="color:#B0C4DE;font-size:11px;">Reporte generado automaticamente por PibiCyber</div>'
            f'<div style="color:#6A9BC3;font-size:10px;margin-top:4px;">{e(generated)} (Europe/Madrid)</div>'
            '</td></tr>'
        )

        # Close wrapper
        parts.append('</table></td></tr></table>')

        return "\n".join(parts)

    def _html_threat_table(self, title: str, items: list, key_field: str, value_field: str, value_label: str, max_items: int = 5) -> str:
        """Generate a compact HTML table for a threat category."""
        e = html.escape
        rows = ""
        for i, item in enumerate(items[:max_items]):
            key_val = e(str(item.get(key_field, "?")))
            num_val = item.get(value_field, 0)
            bg = "background:#FAFBFC;" if i % 2 == 0 else ""
            rows += (
                f'<tr style="{bg}">'
                f'<td style="padding:6px 10px;font-size:12px;font-family:Consolas,Monaco,monospace;color:#B22222;">{key_val}</td>'
                f'<td style="padding:6px 10px;font-size:12px;text-align:right;color:#333;font-weight:600;">{num_val} {e(value_label)}</td>'
                f'</tr>'
            )
        if len(items) > max_items:
            remaining = len(items) - max_items
            rows += (
                f'<tr><td colspan="2" style="padding:6px 10px;font-size:11px;color:#6C757D;font-style:italic;">'
                f'...y {remaining} mas</td></tr>'
            )

        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:8px 0 12px;">'
            f'<tr><td colspan="2" style="font-size:12px;font-weight:600;color:#4682B4;padding:8px 0 6px;">{e(title)}</td></tr>'
            f'<tr style="background:#F0F2F5;">'
            f'<td style="padding:6px 10px;font-size:11px;font-weight:600;color:#6C757D;border-bottom:1px solid #DEE2E6;">Origen</td>'
            f'<td style="padding:6px 10px;font-size:11px;font-weight:600;color:#6C757D;border-bottom:1px solid #DEE2E6;text-align:right;">Cantidad</td>'
            f'</tr>'
            f'{rows}'
            f'</table>'
        )

    async def send_daily_report(self, hours: int = 24) -> dict:
        """Generate and send personalized daily reports to all subscribed users."""
        if not self._is_configured():
            print("SMTP no configurado")
            return {"status": "skipped", "reason": "SMTP not configured"}

        report_data = await self.get_daily_report_data(hours)
        fecha = datetime.now().strftime("%Y-%m-%d")
        subject = f"[PibiCyber] Informe de Seguridad - {fecha}"

        # Generate Excel once for all recipients
        excel_bytes = self.generate_excel_report(report_data)
        excel_filename = f"PibiCyber_Informe_{fecha}.xlsx"
        excel_attachment = (excel_filename, excel_bytes)

        results = []

        # Get all users with email enabled
        user_repo = UserRepository(self.db)
        subscribers = await user_repo.get_email_enabled_users()

        for user in subscribers:
            to_email = user.notification_email or user.email
            categories = {
                "network_threats": user.notify_network_threats,
                "system_threats": user.notify_system_threats,
                "general_summary": user.notify_general_summary,
            }

            if not any(categories.values()):
                results.append({"user": user.username, "status": "skipped", "reason": "no categories"})
                continue

            report_html = self.format_report_html(report_data, categories)
            success = self.send_email(subject, report_html, to=to_email, content_type="html", attachment=excel_attachment)
            results.append({"user": user.username, "email": to_email, "status": "sent" if success else "failed"})

        # Fallback: if no subscribers, send to SMTP_TO (backward compat)
        if not subscribers and settings.SMTP_TO:
            report_html = self.format_report_html(report_data)
            success = self.send_email(subject, report_html, to=settings.SMTP_TO, content_type="html", attachment=excel_attachment)
            results.append({"user": "SMTP_TO_fallback", "email": settings.SMTP_TO, "status": "sent" if success else "failed"})

        return {"status": "completed", "results": results}
