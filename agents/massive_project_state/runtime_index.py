from __future__ import annotations

from typing import Dict, List, Optional, Set

from .index import BaseReverseIndex
from .models import RuntimeRecord


class RuntimeReverseIndex(BaseReverseIndex):
    """Reverse index connecting runtime services, endpoints, and deployment artifacts."""

    def __init__(self) -> None:
        super().__init__("RuntimeReverseIndex")
        self._runtimes: Dict[str, RuntimeRecord] = {}
        self._artifact_services: Dict[str, Set[str]] = {}

    def add_runtime(self, runtime: RuntimeRecord) -> None:
        self._runtimes[runtime.service_id] = runtime

        for art in runtime.artifacts:
            self._artifact_services.setdefault(art, set()).add(runtime.service_id)

        self.bump_revision()

    def remove_runtime(self, service_id: str) -> bool:
        runtime = self._runtimes.pop(service_id, None)
        if not runtime:
            return False

        for art in runtime.artifacts:
            if art in self._artifact_services:
                self._artifact_services[art].discard(service_id)

        self.bump_revision()
        return True

    def get_runtime(self, service_id: str) -> Optional[RuntimeRecord]:
        return self._runtimes.get(service_id)

    def get_services_for_artifact(self, artifact: str) -> List[str]:
        return sorted(list(self._artifact_services.get(artifact, set())))

    def list_runtimes() -> List[RuntimeRecord]:
        return list(self._runtimes.values())

    def clear(self) -> None:
        self._runtimes.clear()
        self._artifact_services.clear()
        self.bump_revision()

    def size(self) -> int:
        return len(self._runtimes)
