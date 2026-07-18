from __future__ import annotations

import json
import os

from agents.mission_state import MissionStateStore


class PersistentPlanner:
    """Single planner facade for legacy reads and persistent Mission State."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.plan_path = os.path.join(self.workspace_root, ".jarvis_plan.json")
        self.mission_state = MissionStateStore(self.workspace_root)

    def load_plan(self) -> dict:
        """Read the legacy global plan without migrating or mutating it."""
        if os.path.exists(self.plan_path):
            with open(self.plan_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        return {"goal": "", "steps": [], "status": "NONE"}

    def save_plan(self, _plan_data) -> None:
        raise RuntimeError(
            "O planner legado e apenas de leitura. Novas missoes devem usar create_mission()."
        )

    def create_plan(self, _goal: str) -> dict:
        raise RuntimeError(
            "O planner legado e apenas de leitura. Novas missoes devem usar create_mission()."
        )

    def execute_next_step(self) -> str:
        raise RuntimeError("A execucao autonoma de Mission State nao esta disponivel nesta fase.")

    # Mission State is persistence-only. These methods never invoke an LLM,
    # a tool, a CodingSession or a command.
    def create_mission(self, *args, **kwargs):
        return self.mission_state.create_mission(*args, **kwargs)

    def list_missions(self, *args, **kwargs):
        return self.mission_state.list_missions(*args, **kwargs)

    def load_mission(self, *args, **kwargs):
        return self.mission_state.load_mission(*args, **kwargs)

    def update_mission(self, *args, **kwargs):
        return self.mission_state.update_mission(*args, **kwargs)

    def set_mission_status(self, *args, **kwargs):
        return self.mission_state.set_mission_status(*args, **kwargs)

    def create_work_package(self, *args, **kwargs):
        return self.mission_state.create_work_package(*args, **kwargs)

    def update_work_package(self, *args, **kwargs):
        return self.mission_state.update_work_package(*args, **kwargs)

    def set_work_package_status(self, *args, **kwargs):
        return self.mission_state.set_work_package_status(*args, **kwargs)

    def add_dependency(self, *args, **kwargs):
        return self.mission_state.add_dependency(*args, **kwargs)

    def create_deliverable(self, *args, **kwargs):
        return self.mission_state.create_deliverable(*args, **kwargs)

    def update_deliverable(self, *args, **kwargs):
        return self.mission_state.update_deliverable(*args, **kwargs)

    def set_deliverable_status(self, *args, **kwargs):
        return self.mission_state.set_deliverable_status(*args, **kwargs)

    def attach_evidence(self, *args, **kwargs):
        return self.mission_state.attach_evidence(*args, **kwargs)

    def create_criterion(self, *args, **kwargs):
        return self.mission_state.create_criterion(*args, **kwargs)

    def set_criterion_status(self, *args, **kwargs):
        return self.mission_state.set_criterion_status(*args, **kwargs)

    def legacy_plan_to_mission_preview(self, path: str | None = None):
        return self.mission_state.legacy_plan_to_mission_preview(path or self.plan_path)
