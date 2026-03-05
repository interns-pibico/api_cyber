import subprocess
from typing import Any

import psutil

from agent.src.platform.base import BasePlatform


class WindowsPlatform(BasePlatform):
    """Windows-specific operations."""

    def get_system_info(self) -> dict[str, Any]:
        info = {
            "platform": "windows",
            "ip_address": self.get_ip_address(),
        }

        try:
            import platform
            info["version"] = platform.version()
            info["release"] = platform.release()
        except Exception:
            pass

        try:
            info["uptime_seconds"] = int(psutil.boot_time())
        except Exception:
            pass

        return info

    def get_services(self) -> list[dict[str, Any]]:
        services = []
        try:
            for service in psutil.win_service_iter():
                try:
                    svc_info = service.as_dict()
                    if svc_info["status"] == "running":
                        services.append({
                            "name": svc_info["name"],
                            "display_name": svc_info["display_name"],
                            "status": svc_info["status"],
                        })
                except Exception:
                    continue
        except Exception:
            pass
        return services[:50]

    def get_processes(self, top_n: int = 10) -> list[dict[str, Any]]:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                pinfo = proc.info
                processes.append({
                    "pid": pinfo["pid"],
                    "name": pinfo["name"],
                    "cpu_percent": pinfo["cpu_percent"] or 0,
                    "memory_percent": pinfo["memory_percent"] or 0,
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return processes[:top_n]
