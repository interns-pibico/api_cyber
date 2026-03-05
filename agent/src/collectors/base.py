from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


class BaseCollector(ABC):
    """Base class for metric collectors."""

    @property
    @abstractmethod
    def metric_type(self) -> str:
        """Return the type of metrics collected."""
        pass

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        """Collect and return metrics."""
        pass

    def get_timestamp(self) -> str:
        """Return current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()
