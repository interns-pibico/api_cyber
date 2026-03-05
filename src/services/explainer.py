"""Auto-explanation engine for events.

Uses intelligent rules to generate contextual explanations.
Prepared for future Ollama (local LLM) integration when server RAM is upgraded.
"""

from datetime import datetime

from src.core.config import settings


def generate_explanation(event_data: dict) -> str | None:
    """Generate explanation for an event. Uses rules or LLM based on config."""
    if settings.LLM_ENABLED and settings.LLM_PROVIDER == "ollama":
        return _call_ollama(event_data)
    return _rules_explanation(event_data)


def _call_ollama(event_data: dict) -> str | None:
    """Future: call Ollama for LLM-based explanation."""
    # Placeholder for future Ollama integration
    # When server RAM is upgraded (>8GB), install Ollama and enable LLM_ENABLED=true
    return _rules_explanation(event_data)


def _rules_explanation(event_data: dict) -> str | None:
    """Generate explanation using intelligent rules that analyze event data."""
    event_type = event_data.get("event_type", "")
    category = event_data.get("category", "")
    severity = event_data.get("severity", "info")
    extra = event_data.get("extra_data") or {}

    # Dispatch to specific generators
    if event_type == "login_audit":
        return _explain_login_audit(extra, severity)

    if event_type == "alert" and category == "security" and extra.get("analysis_period_hours"):
        return _explain_security_summary(extra, severity)

    # Generic fallback
    return _explain_generic(severity, category)


def _explain_login_audit(extra: dict, severity: str) -> str:
    """Generate explanation for login audit events."""
    anomalies = extra.get("anomalies", [])
    summary = extra.get("summary", {})
    total_success = summary.get("total_success", 0)
    total_failed = summary.get("total_failed", 0)
    unique_ips_success = summary.get("unique_ips_success", 0)
    unique_ips_failed = summary.get("unique_ips_failed", 0)
    period = extra.get("period_hours", 1)

    parts = []

    # Process anomalies first (most important)
    for anomaly in anomalies:
        atype = anomaly.get("type", "")
        detail = anomaly.get("detail", "")

        if atype == "brute_force":
            ip = anomaly.get("ip", "desconocida")
            count = anomaly.get("count", 0)
            parts.append(
                f"Ataque de fuerza bruta detectado: {ip} realizó {count} intentos "
                f"fallidos en {period}h. El firewall debería bloquear esta IP."
            )
        elif atype == "success_after_fail":
            ip = anomaly.get("ip", "desconocida")
            fail_count = anomaly.get("fail_count", 0)
            parts.append(
                f"ALERTA: {ip} logró acceso tras {fail_count} intentos fallidos — "
                f"verificar que el login es legítimo y cambiar credenciales si no lo es."
            )
        elif atype == "root_external":
            ip = anomaly.get("ip", "desconocida")
            parts.append(
                f"Login de root desde IP externa {ip} — esto es inusual y debe "
                f"verificarse inmediatamente."
            )
        elif atype == "unusual_hour":
            user = anomaly.get("user", "desconocido")
            hour = anomaly.get("hour", "??:??")
            ip = anomaly.get("ip", "desconocida")
            parts.append(
                f"Login de {user} a las {hour} desde {ip} — fuera del horario "
                f"habitual, confirmar con el usuario."
            )

    # If no anomalies, provide context about normal activity
    if not anomalies:
        if total_success > 0 and total_failed < 10:
            parts.append(
                f"{total_success} accesos exitosos desde {unique_ips_success} IPs conocidas, "
                f"sin anomalías. Actividad normal."
            )
        elif total_failed < 10:
            parts.append(
                f"Algunos intentos fallidos ({total_failed}) desde {unique_ips_failed} IPs — "
                f"ruido habitual, no indica un ataque dirigido."
            )

    # High volume warning
    if total_failed > 50 and not any(a.get("type") == "brute_force" for a in anomalies):
        parts.append(
            f"Volumen inusualmente alto de intentos fallidos ({total_failed}). "
            f"Aunque ninguno tuvo éxito, considerar reforzar fail2ban o rate limiting."
        )

    return " ".join(parts) if parts else None


def _explain_security_summary(extra: dict, severity: str) -> str:
    """Generate explanation for daily security summary events."""
    parts = []
    period = extra.get("analysis_period_hours", 24)

    ssh = extra.get("ssh_failures", [])
    if ssh:
        total_attempts = sum(item.get("attempts", 0) for item in ssh)
        top_ip = max(ssh, key=lambda x: x.get("attempts", 0)) if ssh else None
        top_info = ""
        if top_ip:
            pct = round(top_ip.get("attempts", 0) / max(total_attempts, 1) * 100)
            top_info = f", el {pct}% concentrado en {top_ip['ip']}"
        parts.append(
            f"{total_attempts} intentos fallidos SSH desde {len(ssh)} IPs{top_info} "
            f"— {'ataque de fuerza bruta activo' if total_attempts > 30 else 'escaneo habitual de bots'}."
        )

    high_risk = extra.get("high_risk_ips", [])
    scores = extra.get("threat_scores", {})
    if high_risk:
        max_score = max((scores.get(ip, 0) for ip in high_risk), default=0)
        parts.append(
            f"{len(high_risk)} IPs superan el umbral de riesgo (score máximo: {max_score})."
        )

    fw = extra.get("firewall_blocked", [])
    if fw:
        total_blocks = sum(item.get("blocks", 0) for item in fw)
        parts.append(f"Firewall bloqueó {total_blocks} conexiones de {len(fw)} IPs.")

    services = extra.get("service_failures", [])
    if services:
        names = ", ".join(s.get("service", "?") for s in services[:3])
        parts.append(f"Servicios con errores: {names}.")

    if not parts:
        parts.append(f"Sin incidencias de seguridad en las últimas {period}h. Actividad normal.")

    return " ".join(parts)


def _explain_generic(severity: str, category: str) -> str:
    """Generic fallback explanation based on severity and category."""
    if severity == "critical" and category == "security":
        return "Evento de seguridad crítico que requiere atención inmediata. Revisar los detalles y tomar acción."
    if severity == "high" and category == "security":
        return "Incidencia de seguridad relevante. Revisar los datos adjuntos para evaluar el impacto."
    if severity == "critical" and category == "system":
        return "Fallo crítico del sistema. Verificar que los servicios afectados están operativos."
    if severity == "high" and category == "system":
        return "Incidencia del sistema relevante. Verificar los servicios afectados."
    return "Evento registrado. Consultar los datos adicionales para más contexto."
