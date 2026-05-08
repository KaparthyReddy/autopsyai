"""Base integration interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from autopsyai.core.tracer import Tracer


class BaseIntegration(ABC):
    """All integrations must subclass this."""

    integration_name: str

    def __init__(self, tracer: Tracer | None = None) -> None:
        self.tracer = tracer or Tracer()

    @abstractmethod
    def install(self, **kwargs: Any) -> None:
        """Patch or wrap the target library to start recording spans."""

    @abstractmethod
    def uninstall(self) -> None:
        """Remove patches and restore original behaviour."""
