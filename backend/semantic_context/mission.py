from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agents.mission_state import MissionStateStore
from backend.semantic_context.contracts import (
    BuilderConfiguration,
    MissionContext,
    sha256_json,
)


class MissionContextReader:
    """Read a bounded, deterministic projection of persisted MissionState."""

    _EXECUTION_FIELDS = (
        "execution_id",
        "work_package_id",
        "executor_kind",
        "status",
        "started_at",
        "completed_at",
        "error_code",
    )

    def __init__(self, store: MissionStateStore):
        self.store = store

    def read(self, configuration: BuilderConfiguration) -> MissionContext:
        snapshot = self.store.load_mission(
            configuration.project_id,
            configuration.mission_id,
        )
        mission = _mapping(snapshot.get("mission"))
        limit = configuration.max_mission_records
        work_packages = _bounded_records(
            snapshot.get("work_packages"),
            limit,
            ("work_package_id",),
        )
        deliverables = _bounded_records(
            snapshot.get("deliverables"),
            limit,
            ("deliverable_id",),
        )
        evidence = _bounded_records(
            snapshot.get("evidence"),
            limit,
            ("evidence_id",),
        )
        criteria = _bounded_records(
            snapshot.get("acceptance_criteria"),
            limit,
            ("criterion_id",),
        )
        executions = tuple(
            {
                field: item.get(field)
                for field in self._EXECUTION_FIELDS
                if field in item
            }
            for item in _bounded_records(
                snapshot.get("executions"),
                limit,
                ("execution_id",),
            )
        )
        recent_events = _bounded_records(
            snapshot.get("recent_events"),
            min(limit, 50),
            ("sequence", "timestamp", "event_id"),
        )
        eligible = tuple(
            sorted(
                str(item)
                for item in snapshot.get("eligible_work_packages") or ()
            )
        )
        source_payload = {
            "mission": mission,
            "work_packages": work_packages,
            "deliverables": deliverables,
            "evidence": evidence,
            "acceptance_criteria": criteria,
            "executions": executions,
            "eligible_work_packages": eligible,
            "recent_events": recent_events,
            "read_only_execution": bool(
                snapshot.get("read_only_execution", True)
            ),
            "autonomous_execution": bool(
                snapshot.get("autonomous_execution", False)
            ),
        }
        return MissionContext(
            project_id=str(mission.get("project_id") or ""),
            mission_id=str(mission.get("mission_id") or ""),
            title=str(mission.get("title") or ""),
            objective=str(mission.get("objective") or ""),
            description=str(mission.get("description") or ""),
            status=str(mission.get("status") or ""),
            current_phase=str(mission.get("current_phase") or ""),
            progress=float(mission.get("progress") or 0.0),
            work_packages=work_packages,
            deliverables=deliverables,
            evidence=evidence,
            acceptance_criteria=criteria,
            executions=executions,
            eligible_work_packages=eligible,
            recent_events=recent_events,
            updated_at=str(mission.get("updated_at") or ""),
            source_sha256=sha256_json(source_payload),
        )


def _bounded_records(
    value: Any,
    limit: int,
    sort_fields: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    records = [
        dict(item)
        for item in value or ()
        if isinstance(item, Mapping)
    ]
    records.sort(
        key=lambda item: tuple(str(item.get(field) or "") for field in sort_fields)
    )
    return tuple(records[:limit])


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
