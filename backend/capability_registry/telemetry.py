from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class CapabilityRegistryTelemetryRecord:
    timestamp: str
    event: str
    registry_version: str
    snapshot_version: str = ""
    model: str = ""
    benchmark: str = ""
    configuration_hash: str = ""
    selection_reason: str = ""
    rejected_capabilities: tuple[str, ...] = ()
    compatibility_failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityRegistryTelemetry:
    def __init__(self):
        self._records: list[CapabilityRegistryTelemetryRecord] = []

    def record(
        self,
        *,
        event: str,
        registry_version: str,
        snapshot_version: str = "",
        model: str = "",
        benchmark: str = "",
        configuration_hash: str = "",
        selection_reason: str = "",
        rejected_capabilities: tuple[str, ...] = (),
        compatibility_failures: tuple[str, ...] = (),
    ) -> CapabilityRegistryTelemetryRecord:
        record = CapabilityRegistryTelemetryRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event=str(event),
            registry_version=str(registry_version),
            snapshot_version=str(snapshot_version),
            model=str(model),
            benchmark=str(benchmark),
            configuration_hash=str(configuration_hash),
            selection_reason=str(selection_reason),
            rejected_capabilities=tuple(rejected_capabilities),
            compatibility_failures=tuple(compatibility_failures),
        )
        self._records.append(record)
        return record

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(record.to_dict() for record in self._records)
