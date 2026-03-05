#!/usr/bin/env python3
"""API Cyber Agent - Multi-OS monitoring agent."""
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone

from agent.src.config import config
from agent.src.collectors.cpu import CPUCollector
from agent.src.collectors.memory import MemoryCollector
from agent.src.collectors.disk import DiskCollector
from agent.src.collectors.network import NetworkCollector
from agent.src.transport.client import APIClient
from agent.src.platform import get_platform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api_cyber_agent")


class Agent:
    """Main agent class."""

    def __init__(self):
        self.client = APIClient()
        self.platform = get_platform()
        self.collectors = [
            CPUCollector(),
            MemoryCollector(),
            DiskCollector(),
            NetworkCollector(),
        ]
        self.running = True

    async def heartbeat_loop(self):
        """Send periodic heartbeats."""
        while self.running:
            try:
                response = await self.client.heartbeat()
                logger.info(f"Heartbeat sent: agent_id={response.get('agent_id')}")
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")

            await asyncio.sleep(config.heartbeat_interval)

    async def metrics_loop(self):
        """Collect and send metrics periodically."""
        while self.running:
            try:
                all_metrics = []
                for collector in self.collectors:
                    try:
                        metrics = collector.collect()
                        all_metrics.extend(metrics)
                    except Exception as e:
                        logger.error(f"Collector {collector.metric_type} failed: {e}")

                if all_metrics:
                    await self.client.send_metrics(all_metrics)
                    logger.info(f"Sent {len(all_metrics)} metrics")

            except Exception as e:
                logger.error(f"Metrics send failed: {e}")

            await asyncio.sleep(config.metrics_interval)

    async def startup_event(self):
        """Send startup event."""
        try:
            event = {
                "event_type": "info",
                "category": "system",
                "title": "Agent Started",
                "message": f"Agent {config.agent_id} started on {config.hostname}",
                "severity": "info",
                "extra_data": self.platform.get_system_info(),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.client.send_event(event)
            logger.info("Startup event sent")
        except Exception as e:
            logger.error(f"Startup event failed: {e}")

    async def shutdown_event(self):
        """Send shutdown event."""
        try:
            event = {
                "event_type": "info",
                "category": "system",
                "title": "Agent Stopped",
                "message": f"Agent {config.agent_id} stopped on {config.hostname}",
                "severity": "info",
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            }
            await self.client.send_event(event)
            logger.info("Shutdown event sent")
        except Exception as e:
            logger.error(f"Shutdown event failed: {e}")

    def stop(self):
        """Stop the agent."""
        self.running = False

    async def run(self):
        """Run the agent."""
        logger.info(f"Starting API Cyber Agent")
        logger.info(f"  Agent ID: {config.agent_id}")
        logger.info(f"  Hostname: {config.hostname}")
        logger.info(f"  OS: {config.os_type} {config.os_version}")
        logger.info(f"  API URL: {config.api_url}")

        # Register agent before collecting metrics
        try:
            response = await self.client.heartbeat()
            logger.info(f"Initial heartbeat OK: agent_id={response.get('agent_id')}")
        except Exception as e:
            logger.error(f"Initial heartbeat failed: {e}")

        await self.startup_event()

        tasks = [
            asyncio.create_task(self.heartbeat_loop()),
            asyncio.create_task(self.metrics_loop()),
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown_event()


def main():
    agent = Agent()

    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        agent.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        pass

    logger.info("Agent stopped")


if __name__ == "__main__":
    main()
