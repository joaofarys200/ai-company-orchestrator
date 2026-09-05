from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Sequence

from agents.mission_state import MissionStateError, MissionStateStore
from agents.task_graph import (
    FailureCategory,
    RetryConfig,
    TaskGraph,
    TaskNode,
    TaskStatus,
)
from backend.logging_config import get_logger, log_event

logger = get_logger(__name__)


@dataclass
class PlannedTaskSpec:
    title: str
    description: str = ""
    category: str = "GENERIC"  # CODING, RESEARCH, REVIEW, BUILD, EXPERIMENT, GENERIC
    dependencies: list[str] = field(default_factory=list)  # can be titles or ids
    priority: int = 0
    timeout_seconds: float = 60.0
    required: bool = True
    task_id: str | None = None
    acceptance_criteria: list[str] = field(default_factory=list)


@dataclass
class PlannedMissionSpec:
    title: str
    objective: str
    description: str = ""
    project_id: str = "default-project"
    tasks: list[PlannedTaskSpec] = field(default_factory=list)
    mission_id: str | None = None
    is_economic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class MissionPlanDecomposer:
    """Decomposes mission specifications into validated TaskGraphs and MissionStateStore entities."""

    def __init__(self, mission_state: MissionStateStore) -> None:
        self.mission_state = mission_state

    def decompose_and_persist(
        self,
        spec: PlannedMissionSpec,
    ) -> tuple[dict[str, Any], TaskGraph]:
        """Validates spec, creates MissionStateStore entities, and builds TaskGraph."""
        mission_id = spec.mission_id or f"m_{uuid.uuid4().hex[:10]}"
        project_id = spec.project_id

        # 0. Ensure project directory exists in workspace/projects
        proj_dir = os.path.join(self.mission_state.projects_root, project_id)
        if not os.path.isdir(proj_dir):
            os.makedirs(proj_dir, exist_ok=True)

        # 1. Normalize Task IDs and Dependencies
        task_id_map: dict[str, str] = {}  # title/alias -> task_id
        normalized_tasks: list[PlannedTaskSpec] = []

        for idx, task_spec in enumerate(spec.tasks, start=1):
            t_id = task_spec.task_id or f"task_{idx:02d}_{uuid.uuid4().hex[:4]}"
            task_id_map[task_spec.title.lower()] = t_id
            task_id_map[t_id] = t_id
            normalized_tasks.append(task_spec)

        # 2. Build TaskNodes for TaskGraph validation
        nodes: list[TaskNode] = []
        for idx, task_spec in enumerate(normalized_tasks, start=1):
            t_id = task_spec.task_id or f"task_{idx:02d}_{uuid.uuid4().hex[:4]}"
            
            # Resolve dependencies to canonical task_ids
            resolved_deps: list[str] = []
            for dep in task_spec.dependencies:
                dep_clean = dep.lower().strip()
                if dep_clean in task_id_map:
                    resolved_deps.append(task_id_map[dep_clean])
                elif dep in task_id_map.values():
                    resolved_deps.append(dep)
                else:
                    # Look up by prefix
                    matched = [tid for key, tid in task_id_map.items() if dep_clean in key]
                    if matched:
                        resolved_deps.append(matched[0])
                    else:
                        raise MissionStateError(
                            f"Dependência desconhecida '{dep}' na tarefa '{task_spec.title}'."
                        )

            node = TaskNode(
                task_id=t_id,
                title=task_spec.title,
                description=task_spec.description or task_spec.title,
                category=task_spec.category,
                dependencies=resolved_deps,
                status=TaskStatus.PENDING,
                priority=task_spec.priority,
                timeout_seconds=task_spec.timeout_seconds,
                required=task_spec.required,
            )
            nodes.append(node)

        # 3. Deterministically Validate DAG
        task_graph = TaskGraph(nodes)
        task_graph.validate()

        # 4. Persist to MissionStateStore
        # Create Mission (status: DRAFT)
        mission_meta = {
            **spec.metadata,
            "is_economic": spec.is_economic,
            "task_count": len(nodes),
            "graph_version": int(task_graph.graph_version),
        }
        self.mission_state.create_mission(
            project_id=project_id,
            title=spec.title,
            objective=spec.objective,
            description=spec.description,
            current_phase="READY",
            metadata=mission_meta,
            mission_id=mission_id,
        )

        # Create WorkPackages in topological order so dependencies exist
        topological_order = task_graph.topological_sort()
        node_map = {n.task_id: n for n in nodes}

        packages_batch: list[dict[str, Any]] = []
        criteria_batch: list[dict[str, Any]] = []

        for t_id in topological_order:
            node = node_map[t_id]
            # Map category to canonical WORK_PACKAGE_TYPES
            cat_map = {
                "CODING": "CODING",
                "RESEARCH": "RESEARCH",
                "REVIEW": "REVIEW",
                "BUILD": "PROJECT_BUILD",
                "PROJECT_BUILD": "PROJECT_BUILD",
                "EXPERIMENT": "EXPERIMENT",
                "DOCUMENT": "DOCUMENT",
            }
            wp_type = cat_map.get(node.category.upper(), "GENERIC")
            packages_batch.append({
                "work_package_id": node.task_id,
                "title": node.title,
                "description": node.description,
                "type": wp_type,
                "priority": node.priority,
                "dependencies": node.dependencies,
                "required": node.required,
            })
            criteria_batch.append({
                "criterion_id": f"crit_{node.task_id}",
                "owner_type": "WORK_PACKAGE",
                "owner_id": node.task_id,
                "description": f"Execução com sucesso e evidência válida para '{node.title}'",
                "required": node.required,
            })

        if hasattr(self.mission_state, "create_work_packages_batch"):
            self.mission_state.create_work_packages_batch(
                project_id=project_id,
                mission_id=mission_id,
                packages=packages_batch,
                criteria=criteria_batch,
            )
        else:
            for pkg, crit in zip(packages_batch, criteria_batch):
                self.mission_state.create_work_package(
                    project_id=project_id,
                    mission_id=mission_id,
                    **pkg,
                )
                self.mission_state.create_criterion(
                    project_id=project_id,
                    mission_id=mission_id,
                    **crit,
                )

        # 5. Transition Mission from DRAFT -> READY
        loaded = self.mission_state.load_mission(project_id, mission_id)
        self.mission_state.set_mission_status(
            project_id=project_id,
            mission_id=mission_id,
            status="READY",
            expected_version=loaded["mission"]["version"],
        )

        log_event(
            logger,
            "mission_planner.plan_decomposed",
            project_id=project_id,
            mission_id=mission_id,
            tasks_count=len(nodes),
        )

        return self.mission_state.load_mission(project_id, mission_id), task_graph

    @classmethod
    def parse_text_plan(
        cls,
        text: str,
        project_id: str = "default-project",
        default_title: str = "Missão Composta",
    ) -> PlannedMissionSpec:
        """Parses numbered or bulleted list of tasks into PlannedMissionSpec."""
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        tasks: list[PlannedTaskSpec] = []

        for idx, line in enumerate(lines, start=1):
            # Clean numbered list prefix
            cleaned = re.sub(r"^(\d+[\.\)]|\-|\*|\[\s*\])\s*", "", line).strip()
            if not cleaned:
                continue

            # Detect category
            clean_lower = cleaned.lower()
            category = "GENERIC"
            if any(k in clean_lower for k in ["cria", "implementa", "desenvolve", "código", "backend", "frontend"]):
                category = "CODING"
            elif any(k in clean_lower for k in ["pesquisa", "analisa", "investiga", "documenta"]):
                category = "RESEARCH"
            elif any(k in clean_lower for k in ["teste", "valida", "review", "verific"]):
                category = "REVIEW"

            # Implicit sequential dependency if multi-step
            deps = [f"task_{idx-1:02d}"] if idx > 1 else []

            tasks.append(
                PlannedTaskSpec(
                    title=cleaned,
                    category=category,
                    dependencies=deps,
                    task_id=f"task_{idx:02d}",
                )
            )

        return PlannedMissionSpec(
            title=default_title,
            objective=text,
            project_id=project_id,
            tasks=tasks,
        )
