import subprocess
from typing import Any

import psutil

from agent.src.platform.base import BasePlatform


class LinuxPlatform(BasePlatform):
    """Linux-specific operations."""

    def get_system_info(self) -> dict[str, Any]:
        info = {
            "platform": "linux",
            "ip_address": self.get_ip_address(),
        }

        # Get distribution info
        try:
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        info["distribution"] = line.split("=")[1].strip().strip('"')
                        break
        except Exception:
            pass

        # Get kernel version
        try:
            result = subprocess.run(["uname", "-r"], capture_output=True, text=True)
            info["kernel"] = result.stdout.strip()
        except Exception:
            pass

        # Get uptime
        try:
            info["uptime_seconds"] = int(psutil.boot_time())
        except Exception:
            pass

        return info

    def get_services(self) -> list[dict[str, Any]]:
        services = []
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--plain"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.strip().split("\n")[1:]:
                parts = line.split()
                if len(parts) >= 4:
                    services.append({
                        "name": parts[0].replace(".service", ""),
                        "status": "running",
                    })
        except Exception:
            pass
        return services[:50]  # Limit to 50 services

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

        # Sort by CPU usage
        processes.sort(key=lambda x: x["cpu_percent"], reverse=True)
        return processes[:top_n]
