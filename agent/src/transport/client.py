import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from agent.src.config import config

logger = logging.getLogger(__name__)


class APIClient:
    """HTTP client for API Cyber."""

    def __init__(self):
        self.base_url = config.api_url.rstrip("/")
        self.headers = {
            "X-API-Key": config.api_key,
            "Content-Type": "application/json",
        }

    async def heartbeat(self) -> dict[str, Any]:
        """Send heartbeat to the API."""
        payload = {
            "agent_id": config.agent_id,
            "hostname": config.hostname,
            "agent_type": "collector",
            "os_type": config.os_type,
            "os_version": config.os_version,
            "agent_version": config.agent_version,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/agents/heartbeat",
                json=payload,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def send_metrics(self, metrics: list[dict[str, Any]]) -> dict[str, Any]:
        """Send metrics batch to the API."""
        payload = {
            "agent_id": config.agent_id,
            "metrics": metrics,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/metrics/batch",
                json=payload,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def send_task_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Send task result to the API."""
        result["agent_id"] = config.agent_id

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/tasks/results",
                json=result,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def send_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Send event to the API."""
        event["agent_id"] = config.agent_id
        if "occurred_at" not in event:
            event["occurred_at"] = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/events/",
                json=event,
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
