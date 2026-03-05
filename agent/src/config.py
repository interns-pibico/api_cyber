import os
import platform
import uuid
from dataclasses import dataclass


@dataclass
class AgentConfig:
    api_url: str = os.getenv("API_CYBER_URL", "https://raquel.pibico.es/cyber")
    api_key: str = os.getenv("API_CYBER_KEY", "your-agent-api-key")
    agent_id: str = os.getenv("API_CYBER_AGENT_ID", str(uuid.uuid4()))
    hostname: str = platform.node()
    os_type: str = platform.system().lower()
    os_version: str = platform.release()
    agent_version: str = "1.0.0"
    heartbeat_interval: int = int(os.getenv("HEARTBEAT_INTERVAL", "60"))
    metrics_interval: int = int(os.getenv("METRICS_INTERVAL", "30"))


config = AgentConfig()
