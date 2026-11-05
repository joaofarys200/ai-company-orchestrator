from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.application_services import ApplicationServices


@dataclass(slots=True)
class ApplicationLifecycle:
    services: ApplicationServices
    initialize_voice: Callable[[], Any]
    get_voice_service: Callable[[], Any]
    start_frontend: Callable[[], Any]
    frontend_handle: Any = None
    started: bool = False

    def startup(self) -> None:
        if self.started:
            return
        self.services.database.init_db()
        self.initialize_voice()
        self.frontend_handle = self.start_frontend()
        self.services.sandbox.start_docker_sandbox()

        # Phase 25: Discover and reconcile interrupted missions on application startup
        try:
            from agents.mission_recovery import MissionRecoveryEngine
            recovery_engine = MissionRecoveryEngine(workspace_root=".")
            missions = recovery_engine.discover_all_missions()
            for project_id, mission_id in missions:
                assessment = recovery_engine.assess_mission(project_id, mission_id)
                if assessment.classification.value == "REQUIRES_RECONCILIATION":
                    recovery_engine.reconcile_mission(project_id, mission_id)
        except Exception:
            pass

        self.started = True

    def shutdown(self) -> None:
        if not self.started:
            return
        voice_service = self.get_voice_service()
        if voice_service is not None:
            voice_service.stop()
        self.services.sandbox.stop_custom_project()
        self.services.sandbox.stop_docker_sandbox()
        if self.frontend_handle is not None:
            self.frontend_handle.stop()
            self.frontend_handle = None
        self.started = False
