import platform

from agent.src.platform.base import BasePlatform
from agent.src.platform.linux import LinuxPlatform
from agent.src.platform.windows import WindowsPlatform
from agent.src.platform.macos import MacOSPlatform


def get_platform() -> BasePlatform:
    """Get the appropriate platform handler."""
    system = platform.system().lower()
    if system == "linux":
        return LinuxPlatform()
    elif system == "windows":
        return WindowsPlatform()
    elif system == "darwin":
        return MacOSPlatform()
    else:
        return LinuxPlatform()  # Default to Linux


__all__ = ["get_platform", "BasePlatform"]
