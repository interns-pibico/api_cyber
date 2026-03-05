import subprocess
from typing import Any

import psutil

from agent.src.platform.base import BasePlatform


class MacOSPlatform(BasePlatform):
    """macOS-specific operations."""

    def get_system_info(self) -> dict[str, Any]:
        info = {
            "platform": "macos",
            "ip_address": self.get_ip_address(),
        }

        try:
            result = subprocess.run(["sw_vers", "-productVersion"], capture_output=True, text=True)
            info["version"] = result.stdout.strip()
        except Exception:
            pass

        try:
            result = subprocess.run(["uname", "-r"], capture_output=True, text=True)
            info["kernel"] = result.stdout.strip()
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
            result = subprocess.run(
                ["launchctl", "list"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split("\t")
                if len(parts) >= 3 and parts[0] != "-":
                    services.append({
                        "name": parts[2],
                        "pid": parts[0],
                        "status": "running" if parts[0] != "-" else "stopped",
                    })
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
