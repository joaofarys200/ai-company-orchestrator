from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents.mission_autonomy import MissionAutonomyController
    from agents.mission_executor import MissionExecutorService
    from backend.model_harness import ModelHarness
    from intelligence.coding_session import CodingSessionService
    from intelligence.project_context import ProjectContextService


@dataclass(slots=True)
class ApplicationServices:
    """Long-lived application services shared by transport handlers."""

    database: Any
    agents: Any
    sandbox: Any
    model_harness: "ModelHarness"
    project_context: "ProjectContextService"
    coding_sessions: "CodingSessionService"
    mission_planner: Any
    mission_executor: "MissionExecutorService"
    mission_autonomy: "MissionAutonomyController"

    def with_overrides(self, **changes: Any) -> "ApplicationServices":
        """Return a shallow service view without constructing new services."""

        return replace(self, **changes)


def create_application_services(
    project_root: str,
    *,
    database_module: Any,
    agents_module: Any,
    sandbox_module: Any,
) -> ApplicationServices:
    from agents.mission_autonomy import MissionAutonomyController
    from agents.mission_executor import MissionExecutorService
    from agents.planner_engine import PersistentPlanner
    from backend.model_harness import get_model_harness
    from intelligence.coding_session import CodingSessionService
    from intelligence.project_context import ProjectContextService

    project_context = ProjectContextService()
    coding_sessions = CodingSessionService(project_context)
    mission_planner = PersistentPlanner(project_root)
    mission_executor = MissionExecutorService(
        project_root,
        mission_state=mission_planner.mission_state,
        coding_service=coding_sessions,
    )
    mission_autonomy = MissionAutonomyController(
        project_root,
        mission_state=mission_planner.mission_state,
        executor_service=mission_executor,
    )
    return ApplicationServices(
        database=database_module,
        agents=agents_module,
        sandbox=sandbox_module,
        model_harness=get_model_harness(),
        project_context=project_context,
        coding_sessions=coding_sessions,
        mission_planner=mission_planner,
        mission_executor=mission_executor,
        mission_autonomy=mission_autonomy,
    )
