from typing import Any

import psutil

from agent.src.collectors.base import BaseCollector


class CPUCollector(BaseCollector):
    """Collect CPU metrics."""

    @property
    def metric_type(self) -> str:
        return "cpu"

    def collect(self) -> list[dict[str, Any]]:
        metrics = []

        # Overall CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics.append({
            "metric_type": self.metric_type,
            "metric_name": "usage_percent",
            "value": cpu_percent,
            "unit": "%",
        })

        # Per-CPU usage
        per_cpu = psutil.cpu_percent(interval=0, percpu=True)
        for i, percent in enumerate(per_cpu):
            metrics.append({
                "metric_type": self.metric_type,
                "metric_name": f"core_{i}_usage",
                "value": percent,
                "unit": "%",
            })

        # CPU frequency
        try:
            freq = psutil.cpu_freq()
            if freq:
                metrics.append({
                    "metric_type": self.metric_type,
                    "metric_name": "frequency_mhz",
                    "value": freq.current,
                    "unit": "MHz",
                })
        except Exception:
            pass

        # Load average (Unix only)
        try:
            load = psutil.getloadavg()
            metrics.append({
                "metric_type": self.metric_type,
                "metric_name": "load_1m",
                "value": load[0],
                "unit": "",
            })
            metrics.append({
                "metric_type": self.metric_type,
                "metric_name": "load_5m",
                "value": load[1],
                "unit": "",
            })
            metrics.append({
                "metric_type": self.metric_type,
                "metric_name": "load_15m",
                "value": load[2],
                "unit": "",
            })
        except (AttributeError, OSError):
            pass

        return metrics
