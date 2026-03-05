from typing import Any

import psutil

from agent.src.collectors.base import BaseCollector


class DiskCollector(BaseCollector):
    """Collect disk metrics."""

    @property
    def metric_type(self) -> str:
        return "disk"

    def collect(self) -> list[dict[str, Any]]:
        metrics = []

        # Disk partitions
        partitions = psutil.disk_partitions()
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                mount_name = partition.mountpoint.replace("/", "_").replace("\\", "_")
                if mount_name == "_":
                    mount_name = "root"

                metrics.extend([
                    {
                        "metric_type": self.metric_type,
                        "metric_name": f"{mount_name}_total_gb",
                        "value": round(usage.total / (1024 ** 3), 2),
                        "unit": "GB",
                        "extra_data": {"mountpoint": partition.mountpoint, "fstype": partition.fstype},
                    },
                    {
                        "metric_type": self.metric_type,
                        "metric_name": f"{mount_name}_used_gb",
                        "value": round(usage.used / (1024 ** 3), 2),
                        "unit": "GB",
                        "extra_data": {"mountpoint": partition.mountpoint},
                    },
                    {
                        "metric_type": self.metric_type,
                        "metric_name": f"{mount_name}_free_gb",
                        "value": round(usage.free / (1024 ** 3), 2),
                        "unit": "GB",
                        "extra_data": {"mountpoint": partition.mountpoint},
                    },
                    {
                        "metric_type": self.metric_type,
                        "metric_name": f"{mount_name}_usage_percent",
                        "value": usage.percent,
                        "unit": "%",
                        "extra_data": {"mountpoint": partition.mountpoint},
                    },
                ])
            except (PermissionError, OSError):
                continue

        # Disk I/O
        try:
            io = psutil.disk_io_counters()
            if io:
                metrics.extend([
                    {
                        "metric_type": self.metric_type,
                        "metric_name": "read_bytes_total",
                        "value": io.read_bytes,
                        "unit": "bytes",
                    },
                    {
                        "metric_type": self.metric_type,
                        "metric_name": "write_bytes_total",
                        "value": io.write_bytes,
                        "unit": "bytes",
                    },
                ])
        except Exception:
            pass

        return metrics
