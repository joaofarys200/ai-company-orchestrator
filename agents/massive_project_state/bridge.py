from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import ChangePlan, TargetedSubgraph
from .state import ProjectStateFabric


class MassiveProjectStateBridge:
    """Bridge interface connecting Modular Project State Fabric to Mission Control and WebSockets."""

    _instances: Dict[str, ProjectStateFabric] = {}

    @classmethod
    def get_fabric(cls, project_id: str = "default") -> ProjectStateFabric:
        if project_id not in cls._instances:
            cls._instances[project_id] = ProjectStateFabric()
        return cls._instances[project_id]

    @classmethod
    def reset_fabric(cls, project_id: str = "default") -> None:
        if project_id in cls._instances:
            del cls._instances[project_id]

    @classmethod
    def plan_mission_change(
        cls,
        objective: str,
        changed_files: List[str],
        project_id: str = "default",
        risk: str = "LOW",
    ) -> Dict[str, Any]:
        fabric = cls.get_fabric(project_id)
        plan: ChangePlan = fabric.plan_repository_change(
            objective=objective,
            changed_files=changed_files,
            risk=risk,
        )
        return plan.to_dict()

    @classmethod
    def query_targeted_subgraph(
        cls,
        root_symbols: List[str],
        project_id: str = "default",
        max_depth: int = 3,
    ) -> Dict[str, Any]:
        fabric = cls.get_fabric(project_id)
        subgraph: TargetedSubgraph = fabric.extract_targeted_subgraph(
            root_symbols=root_symbols,
            max_depth=max_depth,
        )
        return subgraph.to_dict()

    @classmethod
    def get_state_status(cls, project_id: str = "default") -> Dict[str, Any]:
        fabric = cls.get_fabric(project_id)
        return fabric.get_state_overview()
