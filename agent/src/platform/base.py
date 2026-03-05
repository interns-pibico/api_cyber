from abc import ABC, abstractmethod
from typing import Any
import socket


class BasePlatform(ABC):
    """Base class for platform-specific operations."""

    @abstractmethod
    def get_system_info(self) -> dict[str, Any]:
        """Get system-specific information."""
        pass

    @abstractmethod
    def get_services(self) -> list[dict[str, Any]]:
        """Get list of running services."""
        pass

    @abstractmethod
    def get_processes(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Get top N processes by resource usage."""
        pass

    def get_ip_address(self) -> str:
        """Get primary IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
