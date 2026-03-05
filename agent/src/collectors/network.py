from typing import Any

import psutil

from agent.src.collectors.base import BaseCollector


class NetworkCollector(BaseCollector):
    """Collect network metrics."""

    @property
    def metric_type(self) -> str:
        return "network"

    def collect(self) -> list[dict[str, Any]]:
        metrics = []

        # Network I/O
        io = psutil.net_io_counters()
        metrics.extend([
            {
                "metric_type": self.metric_type,
                "metric_name": "bytes_sent_total",
                "value": io.bytes_sent,
                "unit": "bytes",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "bytes_recv_total",
                "value": io.bytes_recv,
                "unit": "bytes",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "packets_sent_total",
                "value": io.packets_sent,
                "unit": "packets",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "packets_recv_total",
                "value": io.packets_recv,
                "unit": "packets",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "errors_in",
                "value": io.errin,
                "unit": "",
            },
            {
                "metric_type": self.metric_type,
                "metric_name": "errors_out",
                "value": io.errout,
                "unit": "",
            },
        ])

        # Per-interface stats
        try:
            per_nic = psutil.net_io_counters(pernic=True)
            for nic_name, nic_io in per_nic.items():
                if nic_name.startswith("lo") or nic_name == "lo0":
                    continue
                metrics.extend([
                    {
                        "metric_type": self.metric_type,
                        "metric_name": f"{nic_name}_bytes_sent",
                        "value": nic_io.bytes_sent,
                        "unit": "bytes",
                        "extra_data": {"interface": nic_name},
                    },
                    {
                        "metric_type": self.metric_type,
                        "metric_name": f"{nic_name}_bytes_recv",
                        "value": nic_io.bytes_recv,
                        "unit": "bytes",
                        "extra_data": {"interface": nic_name},
                    },
                ])
        except Exception:
            pass

        # Connection counts
        try:
            connections = psutil.net_connections(kind="inet")
            established = len([c for c in connections if c.status == "ESTABLISHED"])
            listening = len([c for c in connections if c.status == "LISTEN"])
            metrics.extend([
                {
                    "metric_type": self.metric_type,
                    "metric_name": "connections_established",
                    "value": established,
                    "unit": "",
                },
                {
                    "metric_type": self.metric_type,
                    "metric_name": "connections_listening",
                    "value": listening,
                    "unit": "",
                },
            ])
        except (psutil.AccessDenied, Exception):
            pass

        return metrics
