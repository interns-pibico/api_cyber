from typing import Any

import psutil

from agent.src.collectors.base import BaseCollector


class MemoryCollector(BaseCollector):
    """Collect memory metrics."""

    @property
    def metric_type(self) -> str:
        return "memory"

    def collect(self) -> list[dict[str, Any]]:
        metrics = []

        # Virtual memory
        vm = psutil.virtual_memory()
        metrics.extend([
            {
                "metric_type": self.metric_type,
                "metric_name": "total_gb",
                "value": round(vm.total / (1024 ** 3), 2),
                "unit": "GB",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "available_gb",
                "value": round(vm.available / (1024 ** 3), 2),
                "unit": "GB",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "used_gb",
                "value": round(vm.used / (1024 ** 3), 2),
                "unit": "GB",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "usage_percent",
                "value": vm.percent,
                "unit": "%",
            },
        ])

        # Swap memory
        swap = psutil.swap_memory()
        metrics.extend([
            {
                "metric_type": self.metric_type,
                "metric_name": "swap_total_gb",
                "value": round(swap.total / (1024 ** 3), 2),
                "unit": "GB",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "swap_used_gb",
                "value": round(swap.used / (1024 ** 3), 2),
                "unit": "GB",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "swap_usage_percent",
                "value": swap.percent,
                "unit": "%",
            },
        ])

        return metrics
