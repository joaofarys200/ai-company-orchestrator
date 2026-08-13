from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator


MISSION_STATUSES = {"DRAFT", "READY", "ACTIVE", "BLOCKED", "COMPLETED", "FAILED", "CANCELLED"}
WORK_PACKAGE_TYPES = {"PROJECT_BUILD", "RESEARCH", "CODING", "DOCUMENT", "EXPERIMENT", "REVIEW", "GENERIC"}
WORK_PACKAGE_STATUSES = {
    "PENDING", "READY", "IN_PROGRESS", "BLOCKED", "VALIDATION_FAILED", "COMPLETED", "CANCELLED",
}
DELIVERABLE_STATUSES = {"PLANNED", "IN_PROGRESS", "READY_FOR_REVIEW", "ACCEPTED", "REJECTED"}
CRITERION_STATUSES = {"PENDING", "SATISFIED", "FAILED"}
MISSION_TRANSITIONS = {
    "DRAFT": {"READY", "CANCELLED"},
    "READY": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"BLOCKED", "COMPLETED", "FAILED", "CANCELLED"},
    "BLOCKED": {"ACTIVE", "CANCELLED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}
WORK_PACKAGE_TRANSITIONS = {
    "PENDING": {"READY", "BLOCKED", "CANCELLED"},
    "READY": {"IN_PROGRESS", "BLOCKED", "CANCELLED"},
    "IN_PROGRESS": {"READY", "BLOCKED", "VALIDATION_FAILED", "COMPLETED", "CANCELLED"},
    "BLOCKED": {"READY", "IN_PROGRESS", "CANCELLED"},
    "VALIDATION_FAILED": {"READY", "IN_PROGRESS", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
REFERENCE_PREFIXES = {
    "coding_session", "project_context", "obsidian", "file", "validation", "source", "experiment",
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class MissionStateError(Exception):
    pass


class StaleVersionError(MissionStateError):
    pass


@dataclass
class Mission:
    mission_id: str
    project_id: str
    title: str
    objective: str
    description: str = ""
    status: str = "DRAFT"
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    current_phase: str = ""
    progress: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1


@dataclass
class WorkPackage:
    work_package_id: str
    mission_id: str
    title: str
    description: str = ""
    type: str = "GENERIC"
    status: str = "PENDING"
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    required_deliverables: list[str] = field(default_factory=list)
    executor_kind: str = "MANUAL"
    executor_ref: str = ""
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    blocked_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    required: bool = True
    version: int = 1


@dataclass
class Deliverable:
    deliverable_id: str
    mission_id: str
    work_package_id: str
    name: str
    description: str = ""
    kind: str = "GENERIC"
    status: str = "PLANNED"
    artifact_refs: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    version: int = 1


@dataclass
class Evidence:
    evidence_id: str
    mission_id: str
    work_package_id: str
    deliverable_id: str | None
    kind: str
    source_ref: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    content_hash: str | None = None
    version: int = 1


@dataclass
class AcceptanceCriterion:
    criterion_id: str
    mission_id: str
    owner_type: str
    owner_id: str
    description: str
    status: str = "PENDING"
    required_evidence_kinds: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    validated_at: str | None = None
    validation_note: str = ""
    required: bool = True
    created_at: str = ""
    updated_at: str = ""
    version: int = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionStateStore:
    """Project-scoped Mission State. It persists state but never executes work."""

    def __init__(self, workspace_root: str = ".", lock_timeout_seconds: float = 5.0):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.projects_root = os.path.join(self.workspace_root, "workspace", "projects")
        self.metadata_root = os.path.join(self.workspace_root, "workspace", ".jarvis", "projects")
        self.lock_timeout_seconds = lock_timeout_seconds

    def create_mission(
        self,
        project_id: str,
        title: str,
        objective: str,
        description: str = "",
        current_phase: str = "",
        metadata: dict[str, Any] | None = None,
        mission_id: str | None = None,
    ) -> dict[str, Any]:
        project_id = self._validate_project(project_id)
        title = self._required_text(title, "title")
        objective = self._required_text(objective, "objective")
        mission_id = self._validate_id(mission_id or uuid.uuid4().hex, "mission_id")
        mission_dir = self._mission_dir(project_id, mission_id)
        if os.path.exists(mission_dir):
            raise MissionStateError(f"A missao '{mission_id}' ja existe.")
        os.makedirs(mission_dir, exist_ok=False)
        for name in ("work_packages", "deliverables", "evidence", "criteria", "executions"):
            os.makedirs(os.path.join(mission_dir, name), exist_ok=True)
        now = utc_now()
        mission = Mission(
            mission_id=mission_id,
            project_id=project_id,
            title=title,
            objective=objective,
            description=str(description or "").strip(),
            current_phase=str(current_phase or "").strip(),
            metadata=self._metadata(metadata),
            created_at=now,
            updated_at=now,
        )
        self._write_entity(self._mission_path(project_id, mission_id), mission)
        self._append_event(project_id, mission_id, "MISSION", mission_id, "MISSION_CREATED", 0, 1, {
            "title": title,
            "objective": objective,
        })
        return self.load_mission(project_id, mission_id)

    def list_missions(self, project_id: str) -> list[dict[str, Any]]:
        project_id = self._validate_project(project_id)
        root = self._missions_root(project_id)
        if not os.path.isdir(root):
            return []
        missions: list[dict[str, Any]] = []
        for entry in sorted(os.scandir(root), key=lambda item: item.name.lower()):
            if not entry.is_dir() or not ID_PATTERN.fullmatch(entry.name):
                continue
            try:
                mission = Mission(**self._read_json(os.path.join(entry.path, "mission.json")))
                missions.append(asdict(mission))
            except (MissionStateError, TypeError):
                continue
        return sorted(missions, key=lambda item: item.get("updated_at", ""), reverse=True)

    def load_mission(self, project_id: str, mission_id: str) -> dict[str, Any]:
        project_id = self._validate_project(project_id)
        mission_id = self._validate_id(mission_id, "mission_id")
        mission = Mission(**self._read_json(self._mission_path(project_id, mission_id)))
        if mission.project_id != project_id or mission.mission_id != mission_id:
            raise MissionStateError("A identidade persistida da missao nao corresponde ao caminho.")
        work_packages = self._load_entities(project_id, mission_id, "work_packages", WorkPackage)
        deliverables = self._load_entities(project_id, mission_id, "deliverables", Deliverable)
        evidence = self._load_entities(project_id, mission_id, "evidence", Evidence)
        criteria = self._load_entities(project_id, mission_id, "criteria", AcceptanceCriterion)
        executions = self._load_raw_entities(project_id, mission_id, "executions", "execution_id")
        self._validate_dag(work_packages)
        effective_packages = self._effective_work_packages(work_packages)
        progress = self._progress(effective_packages)
        mission_data = asdict(mission)
        mission_data["progress"] = progress
        eligible = [
            item["work_package_id"] for item in effective_packages.values()
            if item["status"] == "READY"
        ]
        return {
            "mission": mission_data,
            "work_packages": sorted(effective_packages.values(), key=lambda item: (-item["priority"], item["created_at"])),
            "deliverables": [asdict(item) for item in deliverables.values()],
            "evidence": [asdict(item) for item in evidence.values()],
            "acceptance_criteria": [asdict(item) for item in criteria.values()],
            "executions": list(executions.values()),
            "eligible_work_packages": eligible,
            "recent_events": self._read_events(project_id, mission_id, limit=50),
            "resumed_at": utc_now(),
            "read_only_execution": True,
            "autonomous_execution": False,
        }

    def update_mission(self, project_id: str, mission_id: str, expected_version: int, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {"title", "objective", "description", "current_phase", "metadata"}
        clean = {key: value for key, value in dict(changes or {}).items() if key in allowed}
        if not clean:
            raise MissionStateError("A atualizacao da missao nao contem campos permitidos.")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            self._expect_version(mission.version, expected_version)
            previous = mission.version
            if "title" in clean:
                mission.title = self._required_text(clean["title"], "title")
            if "objective" in clean:
                mission.objective = self._required_text(clean["objective"], "objective")
            if "description" in clean:
                mission.description = str(clean["description"] or "").strip()
            if "current_phase" in clean:
                mission.current_phase = str(clean["current_phase"] or "").strip()
            if "metadata" in clean:
                mission.metadata = self._metadata(clean["metadata"])
            self._touch(mission)
            self._write_entity(self._mission_path(project_id, mission_id), mission)
            self._append_event(project_id, mission_id, "MISSION", mission_id, "MISSION_UPDATED", previous, mission.version, {
                "fields": sorted(clean),
            })
        return self.load_mission(project_id, mission_id)

    def set_mission_status(self, project_id: str, mission_id: str, status: str, expected_version: int) -> dict[str, Any]:
        target = self._choice(status, MISSION_STATUSES, "status")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            self._expect_version(mission.version, expected_version)
            if target not in MISSION_TRANSITIONS[mission.status]:
                raise MissionStateError(f"Transicao de Mission invalida: {mission.status} -> {target}.")
            if target == "COMPLETED":
                self._assert_mission_completable(project_id, mission_id)
            previous_status = mission.status
            previous_version = mission.version
            mission.status = target
            now = utc_now()
            if target == "ACTIVE" and not mission.started_at:
                mission.started_at = now
            if target == "COMPLETED":
                mission.completed_at = now
                mission.progress = 100.0
            self._touch(mission, now)
            self._write_entity(self._mission_path(project_id, mission_id), mission)
            self._append_event(project_id, mission_id, "MISSION", mission_id, "MISSION_STATUS_CHANGED", previous_version, mission.version, {
                "previous_status": previous_status,
                "status": target,
            })
        return self.load_mission(project_id, mission_id)

    def create_work_package(
        self,
        project_id: str,
        mission_id: str,
        title: str,
        description: str = "",
        type: str = "GENERIC",
        priority: int = 0,
        dependencies: list[str] | None = None,
        executor_kind: str = "MANUAL",
        executor_ref: str = "",
        metadata: dict[str, Any] | None = None,
        required: bool = True,
        work_package_id: str | None = None,
    ) -> dict[str, Any]:
        work_package_id = self._validate_id(work_package_id or uuid.uuid4().hex, "work_package_id")
        dependencies = list(dict.fromkeys(self._validate_id(item, "dependency") for item in (dependencies or [])))
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            work_packages = self._load_entities(project_id, mission_id, "work_packages", WorkPackage)
            if work_package_id in work_packages:
                raise MissionStateError(f"O WorkPackage '{work_package_id}' ja existe.")
            for dependency in dependencies:
                if dependency not in work_packages:
                    raise MissionStateError(f"Dependencia inexistente: {dependency}.")
                if dependency == work_package_id:
                    raise MissionStateError("Um WorkPackage nao pode depender de si proprio.")
            now = utc_now()
            item = WorkPackage(
                work_package_id=work_package_id,
                mission_id=mission_id,
                title=self._required_text(title, "title"),
                description=str(description or "").strip(),
                type=self._choice(type, WORK_PACKAGE_TYPES, "type"),
                priority=int(priority),
                dependencies=dependencies,
                executor_kind=str(executor_kind or "MANUAL").strip() or "MANUAL",
                executor_ref=str(executor_ref or "").strip(),
                metadata=self._metadata(metadata),
                required=bool(required),
                created_at=now,
                updated_at=now,
            )
            candidate = dict(work_packages)
            candidate[work_package_id] = item
            self._validate_dag(candidate)
            self._write_entity(self._entity_path(project_id, mission_id, "work_packages", work_package_id), item)
            self._append_event(project_id, mission_id, "WORK_PACKAGE", work_package_id, "WORK_PACKAGE_CREATED", 0, 1, {
                "title": item.title,
                "type": item.type,
            })
            for dependency in dependencies:
                self._append_event(project_id, mission_id, "WORK_PACKAGE", work_package_id, "DEPENDENCY_ADDED", 0, 1, {
                    "dependency_id": dependency,
                })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def update_work_package(self, project_id: str, mission_id: str, work_package_id: str, expected_version: int, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {"title", "description", "type", "priority", "executor_kind", "executor_ref", "metadata", "required", "blocked_reason"}
        clean = {key: value for key, value in dict(changes or {}).items() if key in allowed}
        if not clean:
            raise MissionStateError("A atualizacao do WorkPackage nao contem campos permitidos.")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            item = self._load_work_package(project_id, mission_id, work_package_id)
            self._expect_version(item.version, expected_version)
            previous = item.version
            if "title" in clean:
                item.title = self._required_text(clean["title"], "title")
            if "description" in clean:
                item.description = str(clean["description"] or "").strip()
            if "type" in clean:
                item.type = self._choice(clean["type"], WORK_PACKAGE_TYPES, "type")
            if "priority" in clean:
                item.priority = int(clean["priority"])
            if "executor_kind" in clean:
                item.executor_kind = str(clean["executor_kind"] or "MANUAL").strip() or "MANUAL"
            if "executor_ref" in clean:
                item.executor_ref = str(clean["executor_ref"] or "").strip()
            if "metadata" in clean:
                item.metadata = self._metadata(clean["metadata"])
            if "required" in clean:
                item.required = bool(clean["required"])
            if "blocked_reason" in clean:
                item.blocked_reason = str(clean["blocked_reason"] or "").strip()
            self._touch(item)
            self._write_entity(self._entity_path(project_id, mission_id, "work_packages", work_package_id), item)
            self._append_event(project_id, mission_id, "WORK_PACKAGE", work_package_id, "WORK_PACKAGE_UPDATED", previous, item.version, {
                "fields": sorted(clean),
            })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def set_work_package_status(self, project_id: str, mission_id: str, work_package_id: str, status: str, expected_version: int, blocked_reason: str = "") -> dict[str, Any]:
        target = self._choice(status, WORK_PACKAGE_STATUSES, "status")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            item = self._load_work_package(project_id, mission_id, work_package_id)
            self._expect_version(item.version, expected_version)
            packages = self._load_entities(project_id, mission_id, "work_packages", WorkPackage)
            effective = self._effective_status(item, packages)
            current_for_transition = effective if item.status in {"PENDING", "READY"} else item.status
            if target == current_for_transition:
                raise MissionStateError(f"O WorkPackage ja esta no estado {target}.")
            if target == "IN_PROGRESS" and effective != "READY":
                raise MissionStateError("O WorkPackage nao pode iniciar enquanto as dependencias nao estiverem satisfeitas.")
            if target not in WORK_PACKAGE_TRANSITIONS[current_for_transition]:
                raise MissionStateError(f"Transicao de WorkPackage invalida: {current_for_transition} -> {target}.")
            if target == "COMPLETED":
                self._assert_work_package_completable(project_id, mission_id, item)
            previous_status = item.status
            previous = item.version
            item.status = target
            now = utc_now()
            if target == "IN_PROGRESS" and not item.started_at:
                item.started_at = now
            if target == "COMPLETED":
                item.completed_at = now
                item.blocked_reason = ""
            elif target == "BLOCKED":
                item.blocked_reason = str(blocked_reason or item.blocked_reason or "Bloqueio manual").strip()
            elif target in {"READY", "IN_PROGRESS"}:
                item.blocked_reason = ""
            self._touch(item, now)
            self._write_entity(self._entity_path(project_id, mission_id, "work_packages", work_package_id), item)
            self._append_event(project_id, mission_id, "WORK_PACKAGE", work_package_id, "WORK_PACKAGE_STATUS_CHANGED", previous, item.version, {
                "previous_status": previous_status,
                "status": target,
            })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def add_dependency(self, project_id: str, mission_id: str, work_package_id: str, dependency_id: str, expected_version: int) -> dict[str, Any]:
        dependency_id = self._validate_id(dependency_id, "dependency_id")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            packages = self._load_entities(project_id, mission_id, "work_packages", WorkPackage)
            if work_package_id not in packages:
                raise MissionStateError(f"WorkPackage inexistente: {work_package_id}.")
            if dependency_id not in packages:
                raise MissionStateError(f"Dependencia inexistente: {dependency_id}.")
            if work_package_id == dependency_id:
                raise MissionStateError("Um WorkPackage nao pode depender de si proprio.")
            item = packages[work_package_id]
            self._expect_version(item.version, expected_version)
            if dependency_id in item.dependencies:
                raise MissionStateError("A dependencia ja existe.")
            previous = item.version
            item.dependencies.append(dependency_id)
            self._validate_dag(packages)
            self._touch(item)
            self._write_entity(self._entity_path(project_id, mission_id, "work_packages", work_package_id), item)
            self._append_event(project_id, mission_id, "WORK_PACKAGE", work_package_id, "DEPENDENCY_ADDED", previous, item.version, {
                "dependency_id": dependency_id,
            })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def create_deliverable(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
        name: str,
        kind: str = "GENERIC",
        description: str = "",
        artifact_refs: list[str] | None = None,
        required: bool = False,
        expected_work_package_version: int | None = None,
        deliverable_id: str | None = None,
    ) -> dict[str, Any]:
        deliverable_id = self._validate_id(deliverable_id or uuid.uuid4().hex, "deliverable_id")
        refs = [self._validate_reference(ref) for ref in (artifact_refs or [])]
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            wp = self._load_work_package(project_id, mission_id, work_package_id)
            if expected_work_package_version is not None:
                self._expect_version(wp.version, expected_work_package_version)
            path = self._entity_path(project_id, mission_id, "deliverables", deliverable_id)
            if os.path.exists(path):
                raise MissionStateError(f"O Deliverable '{deliverable_id}' ja existe.")
            now = utc_now()
            item = Deliverable(
                deliverable_id=deliverable_id,
                mission_id=mission_id,
                work_package_id=work_package_id,
                name=self._required_text(name, "name"),
                description=str(description or "").strip(),
                kind=self._required_text(kind, "kind"),
                artifact_refs=refs,
                created_at=now,
                updated_at=now,
            )
            self._write_entity(path, item)
            self._append_event(project_id, mission_id, "DELIVERABLE", deliverable_id, "DELIVERABLE_CREATED", 0, 1, {
                "work_package_id": work_package_id,
                "kind": item.kind,
            })
            if required:
                previous = wp.version
                wp.required_deliverables.append(deliverable_id)
                self._touch(wp)
                self._write_entity(self._entity_path(project_id, mission_id, "work_packages", work_package_id), wp)
                self._append_event(project_id, mission_id, "WORK_PACKAGE", work_package_id, "REQUIRED_DELIVERABLE_ADDED", previous, wp.version, {
                    "deliverable_id": deliverable_id,
                })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def update_deliverable(self, project_id: str, mission_id: str, deliverable_id: str, expected_version: int, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "description", "kind", "artifact_refs"}
        clean = {key: value for key, value in dict(changes or {}).items() if key in allowed}
        if not clean:
            raise MissionStateError("A atualizacao do Deliverable nao contem campos permitidos.")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            item = self._load_deliverable(project_id, mission_id, deliverable_id)
            self._expect_version(item.version, expected_version)
            previous = item.version
            if "name" in clean:
                item.name = self._required_text(clean["name"], "name")
            if "description" in clean:
                item.description = str(clean["description"] or "").strip()
            if "kind" in clean:
                item.kind = self._required_text(clean["kind"], "kind")
            if "artifact_refs" in clean:
                item.artifact_refs = [self._validate_reference(ref) for ref in list(clean["artifact_refs"] or [])]
            self._touch(item)
            self._write_entity(self._entity_path(project_id, mission_id, "deliverables", deliverable_id), item)
            self._append_event(project_id, mission_id, "DELIVERABLE", deliverable_id, "DELIVERABLE_UPDATED", previous, item.version, {
                "fields": sorted(clean),
            })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def set_deliverable_status(self, project_id: str, mission_id: str, deliverable_id: str, status: str, expected_version: int) -> dict[str, Any]:
        target = self._choice(status, DELIVERABLE_STATUSES, "status")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            item = self._load_deliverable(project_id, mission_id, deliverable_id)
            self._expect_version(item.version, expected_version)
            if target == item.status:
                raise MissionStateError(f"O Deliverable ja esta no estado {target}.")
            if target == "ACCEPTED":
                self._assert_criteria_satisfied(project_id, mission_id, "DELIVERABLE", deliverable_id)
            previous_status = item.status
            previous = item.version
            item.status = target
            self._touch(item)
            self._write_entity(self._entity_path(project_id, mission_id, "deliverables", deliverable_id), item)
            self._append_event(project_id, mission_id, "DELIVERABLE", deliverable_id, "DELIVERABLE_STATUS_CHANGED", previous, item.version, {
                "previous_status": previous_status,
                "status": target,
            })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def attach_evidence(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
        kind: str,
        source_ref: str,
        description: str = "",
        deliverable_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        content_hash: str | None = None,
        evidence_id: str | None = None,
    ) -> dict[str, Any]:
        evidence_id = self._validate_id(evidence_id or uuid.uuid4().hex, "evidence_id")
        source_ref = self._validate_reference(source_ref)
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            self._load_work_package(project_id, mission_id, work_package_id)
            deliverable = None
            if deliverable_id:
                deliverable = self._load_deliverable(project_id, mission_id, deliverable_id)
                if deliverable.work_package_id != work_package_id:
                    raise MissionStateError("A Evidence e o Deliverable pertencem a WorkPackages diferentes.")
            path = self._entity_path(project_id, mission_id, "evidence", evidence_id)
            if os.path.exists(path):
                raise MissionStateError(f"A Evidence '{evidence_id}' ja existe.")
            if content_hash is not None and not re.fullmatch(r"[a-fA-F0-9]{64}", str(content_hash)):
                raise MissionStateError("content_hash deve ser um SHA-256 hexadecimal.")
            resolved_hash = str(content_hash).lower() if content_hash else self._optional_file_hash(source_ref)
            now = utc_now()
            item = Evidence(
                evidence_id=evidence_id,
                mission_id=mission_id,
                work_package_id=work_package_id,
                deliverable_id=deliverable_id,
                kind=self._required_text(kind, "kind"),
                source_ref=source_ref,
                description=str(description or "").strip(),
                metadata=self._metadata(metadata),
                created_at=now,
                content_hash=resolved_hash,
            )
            self._write_entity(path, item)
            if deliverable:
                previous = deliverable.version
                deliverable.evidence_refs.append(evidence_id)
                self._touch(deliverable)
                self._write_entity(self._entity_path(project_id, mission_id, "deliverables", deliverable_id), deliverable)
                self._append_event(project_id, mission_id, "DELIVERABLE", deliverable_id, "DELIVERABLE_EVIDENCE_LINKED", previous, deliverable.version, {
                    "evidence_id": evidence_id,
                })
            self._append_event(project_id, mission_id, "EVIDENCE", evidence_id, "EVIDENCE_ATTACHED", 0, 1, {
                "work_package_id": work_package_id,
                "deliverable_id": deliverable_id,
                "source_ref": source_ref,
            })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def create_criterion(
        self,
        project_id: str,
        mission_id: str,
        owner_type: str,
        owner_id: str,
        description: str,
        required_evidence_kinds: list[str] | None = None,
        required: bool = True,
        criterion_id: str | None = None,
    ) -> dict[str, Any]:
        criterion_id = self._validate_id(criterion_id or uuid.uuid4().hex, "criterion_id")
        owner_type = self._choice(owner_type, {"MISSION", "WORK_PACKAGE", "DELIVERABLE"}, "owner_type")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            owner: WorkPackage | Deliverable | Mission
            if owner_type == "MISSION":
                if owner_id != mission_id:
                    raise MissionStateError("owner_id da Mission deve ser o mission_id.")
                owner = mission
            elif owner_type == "WORK_PACKAGE":
                owner = self._load_work_package(project_id, mission_id, owner_id)
            else:
                owner = self._load_deliverable(project_id, mission_id, owner_id)
            path = self._entity_path(project_id, mission_id, "criteria", criterion_id)
            if os.path.exists(path):
                raise MissionStateError(f"O AcceptanceCriterion '{criterion_id}' ja existe.")
            now = utc_now()
            item = AcceptanceCriterion(
                criterion_id=criterion_id,
                mission_id=mission_id,
                owner_type=owner_type,
                owner_id=owner_id,
                description=self._required_text(description, "description"),
                required_evidence_kinds=[self._required_text(kind, "required_evidence_kind") for kind in (required_evidence_kinds or [])],
                required=bool(required),
                created_at=now,
                updated_at=now,
            )
            self._write_entity(path, item)
            if isinstance(owner, (WorkPackage, Deliverable)):
                previous = owner.version
                owner.acceptance_criteria.append(criterion_id)
                self._touch(owner)
                directory = "work_packages" if isinstance(owner, WorkPackage) else "deliverables"
                entity_id = owner.work_package_id if isinstance(owner, WorkPackage) else owner.deliverable_id
                self._write_entity(self._entity_path(project_id, mission_id, directory, entity_id), owner)
                self._append_event(project_id, mission_id, owner_type, owner_id, "CRITERION_LINKED", previous, owner.version, {
                    "criterion_id": criterion_id,
                })
            self._append_event(project_id, mission_id, "CRITERION", criterion_id, "CRITERION_CREATED", 0, 1, {
                "owner_type": owner_type,
                "owner_id": owner_id,
            })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def set_criterion_status(
        self,
        project_id: str,
        mission_id: str,
        criterion_id: str,
        status: str,
        expected_version: int,
        evidence_refs: list[str] | None = None,
        validation_note: str = "",
    ) -> dict[str, Any]:
        target = self._choice(status, CRITERION_STATUSES, "status")
        with self._locked_mission(project_id, mission_id):
            mission = self._load_mission_entity(project_id, mission_id)
            item = self._load_criterion(project_id, mission_id, criterion_id)
            self._expect_version(item.version, expected_version)
            refs = list(dict.fromkeys(self._validate_id(ref, "evidence_ref") for ref in (evidence_refs or [])))
            evidence = self._load_entities(project_id, mission_id, "evidence", Evidence)
            for ref in refs:
                if ref not in evidence:
                    raise MissionStateError(f"Evidence inexistente: {ref}.")
            if target == "SATISFIED":
                if not refs:
                    raise MissionStateError("SATISFIED exige pelo menos uma Evidence existente.")
                available_kinds = {evidence[ref].kind for ref in refs}
                missing_kinds = set(item.required_evidence_kinds) - available_kinds
                if missing_kinds:
                    raise MissionStateError(f"Faltam tipos de Evidence exigidos: {sorted(missing_kinds)}.")
            previous_status = item.status
            previous = item.version
            item.status = target
            item.evidence_refs = refs
            item.validation_note = str(validation_note or "").strip()
            item.validated_at = utc_now() if target in {"SATISFIED", "FAILED"} else None
            self._touch(item)
            self._write_entity(self._entity_path(project_id, mission_id, "criteria", criterion_id), item)
            self._append_event(project_id, mission_id, "CRITERION", criterion_id, "CRITERION_STATUS_CHANGED", previous, item.version, {
                "previous_status": previous_status,
                "status": target,
                "evidence_refs": refs,
            })
            self._touch_mission_after_child_change(project_id, mission)
        return self.load_mission(project_id, mission_id)

    def legacy_plan_to_mission_preview(self, path: str | None = None) -> dict[str, Any] | None:
        legacy_path = os.path.realpath(path or os.path.join(self.workspace_root, ".jarvis_plan.json"))
        if not os.path.isfile(legacy_path):
            return None
        data = self._read_json(legacy_path)
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        work_packages = []
        for index, step in enumerate(steps, start=1):
            raw_status = str(step.get("status") or "PENDING").upper() if isinstance(step, dict) else "PENDING"
            work_packages.append({
                "work_package_id": f"legacy-{index}",
                "title": str(step.get("action") or f"Passo {index}") if isinstance(step, dict) else f"Passo {index}",
                "type": "GENERIC",
                "status": "COMPLETED" if raw_status in {"DONE", "COMPLETED"} else "PENDING",
                "dependencies": [],
                "legacy_source": True,
            })
        return {
            "read_only": True,
            "source": os.path.relpath(legacy_path, self.workspace_root).replace(os.sep, "/"),
            "mission": {
                "mission_id": "legacy-preview",
                "project_id": None,
                "title": str(data.get("goal") or "Plano legado"),
                "objective": str(data.get("goal") or ""),
                "status": str(data.get("status") or "NONE").upper(),
                "version": 0,
            },
            "work_packages": work_packages,
            "migration_performed": False,
        }

    def _assert_work_package_completable(self, project_id: str, mission_id: str, item: WorkPackage) -> None:
        deliverables = self._load_entities(project_id, mission_id, "deliverables", Deliverable)
        missing = [
            deliverable_id for deliverable_id in item.required_deliverables
            if deliverable_id not in deliverables or deliverables[deliverable_id].status != "ACCEPTED"
        ]
        if missing:
            raise MissionStateError(f"Deliverables obrigatorios ainda nao aceites: {missing}.")
        self._assert_criteria_satisfied(
            project_id, mission_id, "WORK_PACKAGE", item.work_package_id, require_at_least_one=True
        )

    def _assert_mission_completable(self, project_id: str, mission_id: str) -> None:
        packages = self._load_entities(project_id, mission_id, "work_packages", WorkPackage)
        if not any(item.required for item in packages.values()):
            raise MissionStateError("A Mission precisa de pelo menos um WorkPackage obrigatorio antes de concluir.")
        incomplete = [item.work_package_id for item in packages.values() if item.required and item.status != "COMPLETED"]
        if incomplete:
            raise MissionStateError(f"WorkPackages obrigatorios ainda nao concluidos: {incomplete}.")
        deliverables = self._load_entities(project_id, mission_id, "deliverables", Deliverable)
        required_deliverables = {
            deliverable_id
            for item in packages.values() if item.required
            for deliverable_id in item.required_deliverables
        }
        unaccepted = [item for item in required_deliverables if item not in deliverables or deliverables[item].status != "ACCEPTED"]
        if unaccepted:
            raise MissionStateError(f"Deliverables obrigatorios ainda nao aceites: {unaccepted}.")
        criteria = self._load_entities(project_id, mission_id, "criteria", AcceptanceCriterion)
        pending = [item.criterion_id for item in criteria.values() if item.required and item.status != "SATISFIED"]
        if pending:
            raise MissionStateError(f"AcceptanceCriteria obrigatorios ainda nao satisfeitos: {pending}.")

    def _assert_criteria_satisfied(
        self,
        project_id: str,
        mission_id: str,
        owner_type: str,
        owner_id: str,
        require_at_least_one: bool = False,
    ) -> None:
        criteria = self._load_entities(project_id, mission_id, "criteria", AcceptanceCriterion)
        owned_required = [
            item for item in criteria.values()
            if item.owner_type == owner_type and item.owner_id == owner_id and item.required
        ]
        if require_at_least_one and not owned_required:
            raise MissionStateError("WorkPackage nao pode ser concluido sem AcceptanceCriterion obrigatorio e Evidence.")
        pending = [
            item.criterion_id for item in owned_required if item.status != "SATISFIED" or not item.evidence_refs
        ]
        if pending:
            raise MissionStateError(f"AcceptanceCriteria obrigatorios ainda nao satisfeitos: {pending}.")

    def _effective_work_packages(self, packages: dict[str, WorkPackage]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item_id, item in packages.items():
            data = asdict(item)
            data["stored_status"] = item.status
            data["status"] = self._effective_status(item, packages)
            result[item_id] = data
        return result

    @staticmethod
    def _effective_status(item: WorkPackage, packages: dict[str, WorkPackage]) -> str:
        if item.status in {"IN_PROGRESS", "VALIDATION_FAILED", "COMPLETED", "CANCELLED"}:
            return item.status
        if item.blocked_reason:
            return "BLOCKED"
        dependency_statuses = [packages[dependency].status for dependency in item.dependencies if dependency in packages]
        if any(status in {"CANCELLED", "VALIDATION_FAILED"} for status in dependency_statuses):
            return "BLOCKED"
        if any(status != "COMPLETED" for status in dependency_statuses):
            return "PENDING"
        return "READY"

    @staticmethod
    def _progress(packages: dict[str, dict[str, Any]]) -> float:
        required = [item for item in packages.values() if item.get("required", True)]
        if not required:
            return 0.0
        completed = sum(1 for item in required if item["status"] == "COMPLETED")
        return round(completed / len(required) * 100, 2)

    @staticmethod
    def _validate_dag(packages: dict[str, WorkPackage]) -> None:
        for item in packages.values():
            for dependency in item.dependencies:
                if dependency not in packages:
                    raise MissionStateError(f"Dependencia inexistente: {dependency}.")
                if dependency == item.work_package_id:
                    raise MissionStateError("Um WorkPackage nao pode depender de si proprio.")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise MissionStateError("A dependencia criaria um ciclo no DAG.")
            if node_id in visited:
                return
            visiting.add(node_id)
            for dependency in packages[node_id].dependencies:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in packages:
            visit(node_id)

    def _touch_mission_after_child_change(self, project_id: str, mission: Mission) -> None:
        packages = self._load_entities(project_id, mission.mission_id, "work_packages", WorkPackage)
        mission.progress = self._progress(self._effective_work_packages(packages))
        self._touch(mission)
        self._write_entity(self._mission_path(project_id, mission.mission_id), mission)

    def _load_mission_entity(self, project_id: str, mission_id: str) -> Mission:
        project_id = self._validate_project(project_id)
        mission_id = self._validate_id(mission_id, "mission_id")
        try:
            return Mission(**self._read_json(self._mission_path(project_id, mission_id)))
        except TypeError as exc:
            raise MissionStateError(f"mission.json invalido: {exc}") from exc

    def _load_work_package(self, project_id: str, mission_id: str, item_id: str) -> WorkPackage:
        return self._load_entity(project_id, mission_id, "work_packages", item_id, WorkPackage)

    def _load_deliverable(self, project_id: str, mission_id: str, item_id: str) -> Deliverable:
        return self._load_entity(project_id, mission_id, "deliverables", item_id, Deliverable)

    def _load_criterion(self, project_id: str, mission_id: str, item_id: str) -> AcceptanceCriterion:
        return self._load_entity(project_id, mission_id, "criteria", item_id, AcceptanceCriterion)

    def _load_entity(self, project_id: str, mission_id: str, directory: str, item_id: str, model):
        item_id = self._validate_id(item_id, f"{directory}_id")
        path = self._entity_path(project_id, mission_id, directory, item_id)
        try:
            return model(**self._read_json(path))
        except TypeError as exc:
            raise MissionStateError(f"Entidade invalida em {directory}/{item_id}: {exc}") from exc

    def _load_entities(self, project_id: str, mission_id: str, directory: str, model) -> dict[str, Any]:
        root = os.path.join(self._mission_dir(project_id, mission_id), directory)
        if not os.path.isdir(root):
            return {}
        result = {}
        for path in sorted(Path(root).glob("*.json")):
            try:
                item = model(**self._read_json(str(path)))
            except TypeError as exc:
                raise MissionStateError(f"Entidade invalida em {path.name}: {exc}") from exc
            key = getattr(item, {
                "work_packages": "work_package_id",
                "deliverables": "deliverable_id",
                "evidence": "evidence_id",
                "criteria": "criterion_id",
            }[directory])
            result[key] = item
        return result

    def _load_raw_entities(
        self,
        project_id: str,
        mission_id: str,
        directory: str,
        id_field: str,
    ) -> dict[str, dict[str, Any]]:
        root = os.path.join(self._mission_dir(project_id, mission_id), directory)
        if not os.path.isdir(root):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for path in sorted(Path(root).glob("*.json")):
            item = self._read_json(str(path))
            item_id = self._validate_id(item.get(id_field), id_field)
            result[item_id] = item
        return result

    def _validate_project(self, project_id: str) -> str:
        clean = str(project_id or "").strip()
        if not PROJECT_ID_PATTERN.fullmatch(clean):
            raise MissionStateError("project_id invalido.")
        if "obsidian" in clean.lower() or clean.lower() in {"sandbox", "sandbox_dir"}:
            raise MissionStateError("Este diretorio nao pode ser usado por Mission State.")
        root = os.path.realpath(os.path.join(self.projects_root, clean))
        try:
            inside = os.path.commonpath([self.projects_root, root]) == os.path.realpath(self.projects_root)
        except ValueError:
            inside = False
        if not inside or not os.path.isdir(root):
            raise MissionStateError(f"Projeto '{clean}' nao existe em workspace/projects.")
        return clean

    @staticmethod
    def _validate_id(value: Any, field_name: str) -> str:
        clean = str(value or "").strip()
        if not ID_PATTERN.fullmatch(clean):
            raise MissionStateError(f"{field_name} invalido.")
        return clean

    def _validate_reference(self, value: Any) -> str:
        clean = str(value or "").strip().replace("\\", "/")
        if ":" not in clean:
            raise MissionStateError("Referencia deve usar o formato kind:value.")
        prefix, target = clean.split(":", 1)
        if prefix not in REFERENCE_PREFIXES or not target.strip():
            raise MissionStateError(f"Referencia nao suportada: {clean}.")
        if prefix in {"file", "obsidian"}:
            path = PurePosixPath(target)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise MissionStateError("Referencia de path deve ser relativa e nao pode escapar do workspace.")
            if prefix == "file":
                resolved = os.path.realpath(os.path.join(self.workspace_root, *path.parts))
                try:
                    if os.path.commonpath([self.workspace_root, resolved]) != self.workspace_root:
                        raise MissionStateError("Referencia file fora do workspace.")
                except ValueError as exc:
                    raise MissionStateError("Referencia file fora do workspace.") from exc
        return f"{prefix}:{target}"

    def _optional_file_hash(self, source_ref: str) -> str | None:
        if not source_ref.startswith("file:"):
            return None
        path = PurePosixPath(source_ref.split(":", 1)[1])
        absolute = os.path.realpath(os.path.join(self.workspace_root, *path.parts))
        if not os.path.isfile(absolute):
            return None
        digest = hashlib.sha256()
        with open(absolute, "rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            raise MissionStateError(f"{field_name} e obrigatorio.")
        return clean

    @staticmethod
    def _choice(value: Any, choices: set[str], field_name: str) -> str:
        clean = str(value or "").strip().upper()
        if clean not in choices:
            raise MissionStateError(f"{field_name} invalido: {clean}.")
        return clean

    @staticmethod
    def _metadata(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise MissionStateError("metadata deve ser um objeto JSON.")
        return dict(value)

    @staticmethod
    def _expect_version(current: int, expected: int) -> None:
        try:
            expected_int = int(expected)
        except (TypeError, ValueError) as exc:
            raise MissionStateError("expected_version e obrigatorio e deve ser inteiro.") from exc
        if current != expected_int:
            raise StaleVersionError(f"Update stale rejeitado: expected_version={expected_int}, current_version={current}.")

    @staticmethod
    def _touch(entity: Any, timestamp: str | None = None) -> None:
        entity.version += 1
        entity.updated_at = timestamp or utc_now()

    def _missions_root(self, project_id: str) -> str:
        return os.path.join(self.metadata_root, project_id, "missions")

    def _mission_dir(self, project_id: str, mission_id: str) -> str:
        mission_id = self._validate_id(mission_id, "mission_id")
        root = os.path.realpath(os.path.join(self._missions_root(project_id), mission_id))
        missions_root = os.path.realpath(self._missions_root(project_id))
        try:
            if os.path.commonpath([missions_root, root]) != missions_root:
                raise MissionStateError("Caminho de missao fora da metadata do projeto.")
        except ValueError as exc:
            raise MissionStateError("Caminho de missao invalido.") from exc
        return root

    def _mission_path(self, project_id: str, mission_id: str) -> str:
        return os.path.join(self._mission_dir(project_id, mission_id), "mission.json")

    def _entity_path(self, project_id: str, mission_id: str, directory: str, entity_id: str) -> str:
        entity_id = self._validate_id(entity_id, "entity_id")
        return os.path.join(self._mission_dir(project_id, mission_id), directory, f"{entity_id}.json")

    @contextmanager
    def _locked_mission(self, project_id: str, mission_id: str) -> Iterator[None]:
        project_id = self._validate_project(project_id)
        mission_id = self._validate_id(mission_id, "mission_id")
        mission_dir = self._mission_dir(project_id, mission_id)
        if not os.path.isfile(os.path.join(mission_dir, "mission.json")):
            raise MissionStateError(f"Missao '{mission_id}' nao existe.")
        lock_path = os.path.join(mission_dir, ".mission.lock")
        deadline = time.monotonic() + self.lock_timeout_seconds
        handle = None
        while handle is None:
            try:
                handle = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(handle, f"{os.getpid()}\n".encode("ascii"))
                os.fsync(handle)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise MissionStateError("Timeout ao adquirir lock da missao.")
                time.sleep(0.02)
        try:
            yield
        finally:
            if handle is not None:
                os.close(handle)
            try:
                os.unlink(lock_path)
            except FileNotFoundError:
                pass

    @staticmethod
    def _read_json(path: str) -> dict[str, Any]:
        if not os.path.isfile(path):
            raise MissionStateError(f"Estado persistente nao encontrado: {path}.")
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MissionStateError(f"Estado persistente invalido em {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise MissionStateError(f"Estado persistente em {path} nao e um objeto JSON.")
        return data

    def _write_entity(self, path: str, entity: Any) -> None:
        self._atomic_write_json(path, asdict(entity))

    @staticmethod
    def _atomic_write_json(path: str, payload: dict[str, Any]) -> None:
        parent = os.path.dirname(path)
        os.makedirs(parent, exist_ok=True)
        temporary = os.path.join(parent, f".{os.path.basename(path)}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _append_event(
        self,
        project_id: str,
        mission_id: str,
        entity_type: str,
        entity_id: str,
        event_type: str,
        previous_version: int,
        new_version: int,
        payload: dict[str, Any],
    ) -> None:
        event = {
            "event_id": uuid.uuid4().hex,
            "mission_id": mission_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_type": event_type,
            "timestamp": utc_now(),
            "previous_version": previous_version,
            "new_version": new_version,
            "payload": payload,
        }
        path = os.path.join(self._mission_dir(project_id, mission_id), "events.jsonl")
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _read_events(self, project_id: str, mission_id: str, limit: int) -> list[dict[str, Any]]:
        path = os.path.join(self._mission_dir(project_id, mission_id), "events.jsonl")
        if not os.path.isfile(path):
            return []
        events = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return events[-limit:]
