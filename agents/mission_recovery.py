from __future__ import annotations

import os
import time
from typing import Any

from agents.mission_state import (
    MissionStateStore,
    MissionStateError,
    utc_now,
)
from backend.logging_config import get_logger, log_event

logger = get_logger(__name__)


class MissionRecoveryWatchdog:
    """Detects interrupted/crashed missions and recovers orphan IN_PROGRESS work packages safely."""

    def __init__(self, store: MissionStateStore | None = None):
        self.store = store or MissionStateStore()

    def scan_and_recover_project(self, project_id: str) -> list[dict[str, Any]]:
        """Scans all missions for a project and recovers interrupted work packages."""
        recovered_actions: list[dict[str, Any]] = []
        missions = self.store.list_missions(project_id)

        for m_summary in missions:
            mission_id = m_summary["mission_id"]
            try:
                mission_data = self.store.load_mission(project_id, mission_id)
                work_packages = mission_data.get("work_packages", [])

                for wp in work_packages:
                    # Detect work package that was left IN_PROGRESS during a previous crashed session
                    if wp.get("status") == "IN_PROGRESS" or wp.get("stored_status") == "IN_PROGRESS":
                        wp_id = wp["work_package_id"]
                        current_version = wp.get("version", 1)

                        # Recover back to READY using set_work_package_status
                        self.store.set_work_package_status(
                            project_id=project_id,
                            mission_id=mission_id,
                            work_package_id=wp_id,
                            status="READY",
                            expected_version=current_version,
                        )

                        log_event(
                            logger,
                            "mission_watchdog.recovered_package",
                            project_id=project_id,
                            mission_id=mission_id,
                            work_package_id=wp_id,
                        )

                        recovered_actions.append({
                            "project_id": project_id,
                            "mission_id": mission_id,
                            "work_package_id": wp_id,
                            "action": "REVERTED_TO_READY",
                            "timestamp": time.time(),
                        })
            except Exception as exc:
                log_event(
                    logger,
                    "mission_watchdog.scan_error",
                    level="error",
                    project_id=project_id,
                    mission_id=mission_id,
                    error=str(exc),
                )

        return recovered_actions

    def recover_all(self, workspace_root: str | None = None) -> list[dict[str, Any]]:
        """Scans workspace/.jarvis/missions/ across all projects."""
        base_dir = workspace_root or self.store.base_dir
        missions_root = os.path.join(base_dir, ".jarvis", "missions")
        if not os.path.isdir(missions_root):
            return []

        all_recovered = []
        for project_entry in os.scandir(missions_root):
            if project_entry.is_dir():
                project_id = project_entry.name
                recovered = self.scan_and_recover_project(project_id)
                all_recovered.extend(recovered)

        return all_recovered


__all__ = ["MissionRecoveryWatchdog"]
