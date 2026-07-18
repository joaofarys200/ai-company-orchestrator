from __future__ import annotations

import asyncio
import os
import traceback
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from agents.mission_state import (
    AcceptanceCriterion,
    Deliverable,
    Evidence,
    MissionStateError,
    MissionStateStore,
    StaleVersionError,
    WorkPackage,
    utc_now,
)
from agents.orchestrator.project_builder import ProjectBuildResult, build_project
from intelligence.coding_session import CodingSession, CodingSessionService
from intelligence.project_context import ProjectContextService


EXECUTION_STATUSES = {
    "PENDING",
    "RUNNING",
    "WAITING_FOR_REVIEW",
    "VALIDATION_FAILED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "ROLLED_BACK",
}
ACTIVE_LOCK_STATUSES = {"PENDING", "RUNNING", "WAITING_FOR_REVIEW"}
RETRYABLE_STATUSES = {"FAILED", "VALIDATION_FAILED", "CANCELLED"}
SUPPORTED_EXECUTORS = {"CODING", "PROJECT_BUILD"}
UNSUPPORTED_EXECUTORS = {"RESEARCH", "DOCUMENT", "EXPERIMENT", "REVIEW", "GENERIC"}


class MissionExecutionError(MissionStateError):
    pass


class ExecutorUnavailableError(MissionExecutionError):
    pass


@dataclass
class MissionExecution:
    execution_id: str
    mission_id: str
    work_package_id: str
    executor_kind: str
    executor_ref: str = ""
    status: str = "PENDING"
    started_at: str | None = None
    updated_at: str = ""
    completed_at: str | None = None
    attempt: int = 1
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    artifact_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    validation_refs: list[str] = field(default_factory=list)
    primary_error: dict[str, str] | None = None
    rollback_error: dict[str, str] | None = None
    lock_owner: str | None = None
    lock_acquired_at: str | None = None
    heartbeat_at: str | None = None
    version: int = 1
    review_note: str = ""
    previous_execution_id: str | None = None


ProjectBuilderRunner = Callable[[str], Awaitable[ProjectBuildResult] | ProjectBuildResult]


class MissionExecutorService:
    """Manual, single-WorkPackage execution over persistent Mission State."""

    def __init__(
        self,
        workspace_root: str = ".",
        mission_state: MissionStateStore | None = None,
        coding_service: CodingSessionService | None = None,
        project_builder_runner: ProjectBuilderRunner | None = None,
        stale_lock_min_age_seconds: float | None = None,
        owner_id: str | None = None,
    ):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.mission_state = mission_state or MissionStateStore(self.workspace_root)
        if coding_service is None:
            project_service = ProjectContextService(workspace_root=self.workspace_root)
            coding_service = CodingSessionService(project_service)
        self.coding_service = coding_service
        self.project_builder_runner = project_builder_runner or build_project
        configured_age = stale_lock_min_age_seconds
        if configured_age is None:
            try:
                configured_age = float(os.getenv("JARVIS_MISSION_STALE_LOCK_SECONDS", "300"))
            except ValueError:
                configured_age = 300.0
        self.stale_lock_min_age_seconds = max(1.0, float(configured_age))
        self.owner_id = owner_id or f"mission-executor:{os.getpid()}:{uuid.uuid4().hex[:12]}"

    @staticmethod
    def registry() -> dict[str, dict[str, Any]]:
        return {
            "CODING": {
                "supported": True,
                "executor": "CodingSession",
                "requires_apply_approval": True,
            },
            "PROJECT_BUILD": {
                "supported": True,
                "executor": "ProjectBuilder",
                "requires_apply_approval": False,
            },
            "RESEARCH": {"supported": False, "executor": None},
            "DOCUMENT": {"supported": False, "executor": None},
            "EXPERIMENT": {"supported": False, "executor": None},
            "REVIEW": {"supported": False, "executor": None},
            "GENERIC": {"supported": False, "executor": None},
        }

    def load_snapshot(self, project_id: str, mission_id: str) -> dict[str, Any]:
        snapshot = self.mission_state.load_mission(project_id, mission_id)
        snapshot["executions"] = sorted(
            snapshot.get("executions") or [],
            key=lambda item: (str(item.get("updated_at") or ""), str(item.get("execution_id") or "")),
        )
        snapshot["executor_registry"] = self.registry()
        snapshot["read_only_execution"] = False
        snapshot["controlled_execution"] = True
        snapshot["autonomous_execution"] = False
        return snapshot

    async def execute_work_package(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
        expected_mission_version: int,
        expected_work_package_version: int,
        test_mode: bool = False,
    ) -> dict[str, Any]:
        execution = self._begin_execution(
            project_id,
            mission_id,
            work_package_id,
            expected_mission_version,
            expected_work_package_version,
        )
        return await self._run_started_execution(project_id, execution, test_mode=test_mode)

    def apply_execution(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        expected_execution_version: int,
        confirmed: bool,
    ) -> dict[str, Any]:
        if not confirmed:
            raise MissionExecutionError("A aplicacao da CodingSession exige confirmacao explicita.")
        with self.mission_state._locked_mission(project_id, mission_id):
            execution = self._load_execution(project_id, mission_id, execution_id)
            self._expect_execution_version(execution, expected_execution_version)
            if execution.executor_kind != "CODING":
                raise MissionExecutionError("A aprovacao de patch so se aplica ao executor CODING.")
            if execution.status != "RUNNING" or execution.output_summary.get("phase") != "AWAITING_APPLY_APPROVAL":
                raise MissionExecutionError("A execucao nao esta a aguardar aprovacao para aplicar o patch.")
            if not execution.executor_ref:
                raise MissionExecutionError("A execucao CODING nao tem CodingSession associada.")
            previous = execution.version
            execution.output_summary["phase"] = "APPLYING"
            self._heartbeat(execution)
            self._save_execution(project_id, execution)
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution_id,
                "MISSION_EXECUTION_STARTED", previous, execution.version,
                {"phase": "APPLYING", "confirmed": True},
            )

        try:
            session = self.coding_service.apply_session(project_id, execution.executor_ref)
        except Exception as exc:
            return self._fail_execution(project_id, mission_id, execution_id, exc, validation_failed=False)

        session_data = session.to_dict()
        if session.status == "SUCCEEDED":
            evidence_refs, artifact_refs, validation_refs = self._create_coding_evidence(
                project_id, mission_id, execution_id, session
            )
            with self.mission_state._locked_mission(project_id, mission_id):
                current = self._load_execution(project_id, mission_id, execution_id)
                if current.status == "CANCELLED":
                    return self.load_snapshot(project_id, mission_id)
                previous = current.version
                current.output_summary = {
                    **current.output_summary,
                    "phase": "TECHNICAL_SUCCESS",
                    "coding_session": session_data,
                    "change_plan": session.change_plan,
                    "proposed_changes": session.proposed_changes,
                    "validation_results": session.validation_results,
                }
                current.artifact_refs = artifact_refs
                current.evidence_refs = evidence_refs
                current.validation_refs = validation_refs
                current.status = "WAITING_FOR_REVIEW"
                self._heartbeat(current)
                self._save_execution(project_id, current)
                self.mission_state._append_event(
                    project_id, mission_id, "MISSION_EXECUTION", execution_id,
                    "MISSION_EXECUTION_WAITING_REVIEW", previous, current.version,
                    {"coding_session_id": session.session_id, "evidence_refs": evidence_refs},
                )
            return self.load_snapshot(project_id, mission_id)

        validation_failed = session.status == "VALIDATION_FAILED"
        error = MissionExecutionError(
            f"CodingSession terminou em {session.status}: "
            f"{'; '.join(session.errors) if session.errors else 'resultado tecnico sem sucesso'}"
        )
        return self._fail_execution(
            project_id,
            mission_id,
            execution_id,
            error,
            validation_failed=validation_failed,
            output={"coding_session": session_data, "validation_results": session.validation_results},
            rollback_error=session.rollback_error,
        )

    def review_execution(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        decision: str,
        review_note: str,
        accepted_evidence_refs: list[str],
        expected_execution_version: int,
        validation_failed: bool = False,
    ) -> dict[str, Any]:
        clean_decision = str(decision or "").strip().upper()
        if clean_decision not in {"ACCEPT", "REJECT"}:
            raise MissionExecutionError("decision deve ser ACCEPT ou REJECT.")
        if clean_decision == "REJECT":
            return self._reject_execution(
                project_id,
                mission_id,
                execution_id,
                expected_execution_version,
                review_note,
                validation_failed,
            )
        return self._accept_execution(
            project_id,
            mission_id,
            execution_id,
            expected_execution_version,
            review_note,
            accepted_evidence_refs,
        )

    async def retry_execution(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        expected_execution_version: int,
        test_mode: bool = False,
    ) -> dict[str, Any]:
        execution = self._begin_retry(
            project_id, mission_id, execution_id, expected_execution_version
        )
        return await self._run_started_execution(project_id, execution, test_mode=test_mode)

    def cancel_execution(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        expected_execution_version: int,
        confirmed: bool,
    ) -> dict[str, Any]:
        if not confirmed:
            raise MissionExecutionError("O cancelamento exige confirmacao explicita.")
        with self.mission_state._locked_mission(project_id, mission_id):
            execution = self._load_execution(project_id, mission_id, execution_id)
            self._expect_execution_version(execution, expected_execution_version)
            if execution.status not in {"RUNNING", "WAITING_FOR_REVIEW"}:
                raise MissionExecutionError("So e possivel cancelar uma execucao RUNNING ou WAITING_FOR_REVIEW.")
            previous = execution.version
            execution.status = "CANCELLED"
            execution.completed_at = utc_now()
            execution.review_note = "Cancelamento manual confirmado."
            self._release_execution_lock(execution)
            self._save_execution(project_id, execution)
            self._reset_work_package_after_execution(project_id, mission_id, execution.work_package_id)
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution_id,
                "MISSION_EXECUTION_CANCELLED", previous, execution.version,
                {"confirmed": True},
            )
            self.mission_state._append_event(
                project_id, mission_id, "WORK_PACKAGE", execution.work_package_id,
                "WORK_PACKAGE_LOCK_RELEASED", previous, execution.version,
                {"execution_id": execution_id, "reason": "cancelled"},
            )
            mission = self.mission_state._load_mission_entity(project_id, mission_id)
            self.mission_state._touch_mission_after_child_change(project_id, mission)
        return self.load_snapshot(project_id, mission_id)

    def release_stale_lock(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        expected_execution_version: int,
        confirmed: bool,
        minimum_age_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not confirmed:
            raise MissionExecutionError("A libertacao de lock abandonado exige confirmacao explicita.")
        minimum_age = self.stale_lock_min_age_seconds
        if minimum_age_seconds is not None:
            minimum_age = max(minimum_age, float(minimum_age_seconds))
        with self.mission_state._locked_mission(project_id, mission_id):
            execution = self._load_execution(project_id, mission_id, execution_id)
            self._expect_execution_version(execution, expected_execution_version)
            if execution.status not in ACTIVE_LOCK_STATUSES or not execution.lock_owner:
                raise MissionExecutionError("A execucao nao possui um lock ativo.")
            reference = execution.heartbeat_at or execution.lock_acquired_at
            age = self._age_seconds(reference)
            if age < minimum_age:
                raise MissionExecutionError(
                    f"O lock tem {age:.1f}s; a idade minima configurada e {minimum_age:.1f}s."
                )
            previous = execution.version
            execution.status = "FAILED"
            execution.completed_at = utc_now()
            execution.primary_error = {
                "type": "StaleExecutionLock",
                "message": "Lock abandonado libertado manualmente.",
                "traceback": "",
            }
            self._release_execution_lock(execution)
            self._save_execution(project_id, execution)
            self._reset_work_package_after_execution(project_id, mission_id, execution.work_package_id)
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution_id,
                "STALE_LOCK_RELEASED", previous, execution.version,
                {"age_seconds": age, "confirmed": True},
            )
            self.mission_state._append_event(
                project_id, mission_id, "WORK_PACKAGE", execution.work_package_id,
                "WORK_PACKAGE_LOCK_RELEASED", previous, execution.version,
                {"execution_id": execution_id, "reason": "stale"},
            )
            mission = self.mission_state._load_mission_entity(project_id, mission_id)
            self.mission_state._touch_mission_after_child_change(project_id, mission)
        return self.load_snapshot(project_id, mission_id)

    def _begin_execution(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
        expected_mission_version: int,
        expected_work_package_version: int,
    ) -> MissionExecution:
        with self.mission_state._locked_mission(project_id, mission_id):
            mission = self.mission_state._load_mission_entity(project_id, mission_id)
            self.mission_state._expect_version(mission.version, expected_mission_version)
            work_package = self.mission_state._load_work_package(project_id, mission_id, work_package_id)
            self.mission_state._expect_version(work_package.version, expected_work_package_version)
            return self._create_started_execution_locked(project_id, mission, work_package, attempt=1)

    def _begin_retry(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        expected_execution_version: int,
    ) -> MissionExecution:
        with self.mission_state._locked_mission(project_id, mission_id):
            previous_execution = self._load_execution(project_id, mission_id, execution_id)
            self._expect_execution_version(previous_execution, expected_execution_version)
            if previous_execution.status not in RETRYABLE_STATUSES:
                raise MissionExecutionError("Retry so e permitido para FAILED, VALIDATION_FAILED ou CANCELLED.")
            mission = self.mission_state._load_mission_entity(project_id, mission_id)
            work_package = self.mission_state._load_work_package(
                project_id, mission_id, previous_execution.work_package_id
            )
            execution = self._create_started_execution_locked(
                project_id,
                mission,
                work_package,
                attempt=previous_execution.attempt + 1,
                previous_execution_id=previous_execution.execution_id,
            )
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution.execution_id,
                "MISSION_EXECUTION_RETRIED", previous_execution.version, execution.version,
                {"previous_execution_id": previous_execution.execution_id, "attempt": execution.attempt},
            )
            return execution

    def _create_started_execution_locked(
        self,
        project_id: str,
        mission: Any,
        work_package: WorkPackage,
        attempt: int,
        previous_execution_id: str | None = None,
    ) -> MissionExecution:
        if mission.status != "ACTIVE":
            raise MissionExecutionError("A Mission deve estar ACTIVE para executar um WorkPackage.")
        packages = self.mission_state._load_entities(
            project_id, mission.mission_id, "work_packages", WorkPackage
        )
        effective = self.mission_state._effective_status(work_package, packages)
        if attempt == 1 and effective != "READY":
            raise MissionExecutionError(f"O WorkPackage deve estar READY; estado atual: {effective}.")
        if attempt > 1 and not self._dependencies_satisfied(work_package, packages):
            raise MissionExecutionError("O WorkPackage deixou de ser elegivel para retry.")
        executor_kind = self._executor_kind(work_package)
        if executor_kind not in SUPPORTED_EXECUTORS:
            raise ExecutorUnavailableError(
                f"Executor indisponivel para {executor_kind}; o WorkPackage permanece READY."
            )
        if executor_kind == "CODING":
            self._assert_coding_input(project_id, mission.mission_id, work_package)
        self._assert_no_active_execution(project_id, mission.mission_id, work_package.work_package_id)

        execution_id = uuid.uuid4().hex
        now = utc_now()
        criteria = self.mission_state._load_entities(
            project_id, mission.mission_id, "criteria", AcceptanceCriterion
        )
        deliverables = self.mission_state._load_entities(
            project_id, mission.mission_id, "deliverables", Deliverable
        )
        input_snapshot = {
            "project_id": project_id,
            "mission": asdict(mission),
            "work_package": asdict(work_package),
            "acceptance_criteria": [
                asdict(item) for item in criteria.values()
                if item.owner_type == "WORK_PACKAGE" and item.owner_id == work_package.work_package_id
            ],
            "deliverables": [
                asdict(item) for item in deliverables.values()
                if item.work_package_id == work_package.work_package_id
            ],
            "previous_execution_id": previous_execution_id,
        }
        execution = MissionExecution(
            execution_id=execution_id,
            mission_id=mission.mission_id,
            work_package_id=work_package.work_package_id,
            executor_kind=executor_kind,
            status="PENDING",
            started_at=now,
            updated_at=now,
            attempt=attempt,
            input_snapshot=input_snapshot,
            lock_owner=f"{self.owner_id}:{execution_id}",
            lock_acquired_at=now,
            heartbeat_at=now,
            previous_execution_id=previous_execution_id,
        )
        self._save_execution(project_id, execution)
        self.mission_state._append_event(
            project_id, mission.mission_id, "MISSION_EXECUTION", execution_id,
            "MISSION_EXECUTION_CREATED", 0, execution.version,
            {"work_package_id": work_package.work_package_id, "executor_kind": executor_kind, "attempt": attempt},
        )
        self.mission_state._append_event(
            project_id, mission.mission_id, "WORK_PACKAGE", work_package.work_package_id,
            "WORK_PACKAGE_LOCK_ACQUIRED", 0, execution.version,
            {"execution_id": execution_id, "lock_owner": execution.lock_owner},
        )

        previous_execution_version = execution.version
        execution.status = "RUNNING"
        self._touch_execution(execution, now)
        self._save_execution(project_id, execution)
        previous_work_package_version = work_package.version
        work_package.status = "IN_PROGRESS"
        work_package.blocked_reason = ""
        if not work_package.started_at:
            work_package.started_at = now
        self.mission_state._touch(work_package, now)
        self.mission_state._write_entity(
            self.mission_state._entity_path(
                project_id, mission.mission_id, "work_packages", work_package.work_package_id
            ),
            work_package,
        )
        self.mission_state._append_event(
            project_id, mission.mission_id, "MISSION_EXECUTION", execution_id,
            "MISSION_EXECUTION_STARTED", previous_execution_version, execution.version,
            {"executor_kind": executor_kind},
        )
        self.mission_state._append_event(
            project_id, mission.mission_id, "WORK_PACKAGE", work_package.work_package_id,
            "WORK_PACKAGE_STATUS_CHANGED", previous_work_package_version, work_package.version,
            {"previous_status": effective, "status": "IN_PROGRESS", "execution_id": execution_id},
        )
        self.mission_state._touch_mission_after_child_change(project_id, mission)
        return execution

    async def _run_started_execution(
        self,
        project_id: str,
        execution: MissionExecution,
        test_mode: bool,
    ) -> dict[str, Any]:
        try:
            if execution.executor_kind == "CODING":
                snapshot = await self._prepare_coding_execution(project_id, execution)
                if test_mode:
                    current = self._execution_from_snapshot(snapshot, execution.execution_id)
                    return await asyncio.to_thread(
                        self.apply_execution,
                        project_id,
                        execution.mission_id,
                        execution.execution_id,
                        current.version,
                        True,
                    )
                return snapshot
            if execution.executor_kind == "PROJECT_BUILD":
                return await self._run_project_builder(project_id, execution)
            raise ExecutorUnavailableError(f"Executor indisponivel: {execution.executor_kind}.")
        except Exception as exc:
            return self._fail_execution(
                project_id, execution.mission_id, execution.execution_id, exc, validation_failed=False
            )

    async def _prepare_coding_execution(
        self,
        project_id: str,
        execution: MissionExecution,
    ) -> dict[str, Any]:
        work_package = execution.input_snapshot["work_package"]
        objective = self._execution_objective(work_package)
        session = await self.coding_service.create_assisted_session(project_id, objective)
        with self.mission_state._locked_mission(project_id, execution.mission_id):
            current = self._load_execution(project_id, execution.mission_id, execution.execution_id)
            if current.status == "CANCELLED":
                return self.load_snapshot(project_id, execution.mission_id)
            if current.status != "RUNNING":
                raise MissionExecutionError(f"Execucao CODING terminou inesperadamente em {current.status}.")
            current.executor_ref = session.session_id
            current.input_snapshot["project_context"] = session.project_context_snapshot
            current.output_summary = {
                "phase": "AWAITING_APPLY_APPROVAL",
                "coding_session_id": session.session_id,
                "change_plan": session.change_plan,
                "proposed_changes": session.proposed_changes,
            }
            current.artifact_refs = self._coding_artifact_refs(project_id, session)
            self._heartbeat(current)
            self._save_execution(project_id, current)
        return self.load_snapshot(project_id, execution.mission_id)

    async def _run_project_builder(
        self,
        project_id: str,
        execution: MissionExecution,
    ) -> dict[str, Any]:
        objective = self._execution_objective(execution.input_snapshot["work_package"])
        result = self.project_builder_runner(objective)
        if asyncio.iscoroutine(result):
            result = await result
        result_data = asdict(result) if is_dataclass(result) else dict(result)
        commands = list(result_data.get("commands_executed") or [])
        preview_started = bool(result_data.get("preview_started"))
        technical_success = (bool(commands) and all(bool(item.get("ok")) for item in commands)) or preview_started
        artifact_refs = [f"file:{path}" for path in result_data.get("files_created") or []]
        validation_refs = [f"validation:{execution.execution_id}"] if commands or preview_started else []
        if not technical_success:
            return self._fail_execution(
                project_id,
                execution.mission_id,
                execution.execution_id,
                MissionExecutionError("ProjectBuilder nao produziu validacao ou preview tecnico com sucesso."),
                validation_failed=True,
                output={"project_builder": result_data},
                artifact_refs=artifact_refs,
                validation_refs=validation_refs,
            )
        evidence_refs = self._create_builder_evidence(
            project_id,
            execution.mission_id,
            execution.execution_id,
            result_data,
            artifact_refs,
        )
        with self.mission_state._locked_mission(project_id, execution.mission_id):
            current = self._load_execution(project_id, execution.mission_id, execution.execution_id)
            if current.status == "CANCELLED":
                return self.load_snapshot(project_id, execution.mission_id)
            previous = current.version
            current.executor_ref = execution.execution_id
            current.output_summary = {
                "phase": "TECHNICAL_SUCCESS",
                "project_builder": result_data,
                "validation_results": commands,
            }
            current.artifact_refs = artifact_refs
            current.evidence_refs = evidence_refs
            current.validation_refs = validation_refs
            current.status = "WAITING_FOR_REVIEW"
            self._heartbeat(current)
            self._save_execution(project_id, current)
            self.mission_state._append_event(
                project_id, execution.mission_id, "MISSION_EXECUTION", execution.execution_id,
                "MISSION_EXECUTION_WAITING_REVIEW", previous, current.version,
                {"project_id": self._built_project_id(result_data), "evidence_refs": evidence_refs},
            )
        return self.load_snapshot(project_id, execution.mission_id)

    def _accept_execution(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        expected_execution_version: int,
        review_note: str,
        accepted_evidence_refs: list[str],
    ) -> dict[str, Any]:
        refs = list(dict.fromkeys(str(ref or "").strip() for ref in accepted_evidence_refs if str(ref or "").strip()))
        if not refs:
            raise MissionExecutionError("ACCEPT exige Evidence valida selecionada pelo revisor.")
        with self.mission_state._locked_mission(project_id, mission_id):
            execution = self._load_execution(project_id, mission_id, execution_id)
            self._expect_execution_version(execution, expected_execution_version)
            if execution.status != "WAITING_FOR_REVIEW":
                raise MissionExecutionError("Apenas execucoes WAITING_FOR_REVIEW podem ser aceites.")
            if any(ref not in execution.evidence_refs for ref in refs):
                raise MissionExecutionError("A revisao referencia Evidence que nao pertence a esta execucao.")
            evidence = self.mission_state._load_entities(project_id, mission_id, "evidence", Evidence)
            selected = []
            for ref in refs:
                item = evidence.get(ref)
                if not item or item.work_package_id != execution.work_package_id:
                    raise MissionExecutionError(f"Evidence invalida para esta execucao: {ref}.")
                selected.append(item)
            criteria = self.mission_state._load_entities(
                project_id, mission_id, "criteria", AcceptanceCriterion
            )
            deliverables = self.mission_state._load_entities(
                project_id, mission_id, "deliverables", Deliverable
            )
            work_package = self.mission_state._load_work_package(
                project_id, mission_id, execution.work_package_id
            )
            owned_deliverables = {
                item.deliverable_id: item for item in deliverables.values()
                if item.work_package_id == work_package.work_package_id
            }
            required_criteria = [
                item for item in criteria.values()
                if item.required and (
                    (item.owner_type == "WORK_PACKAGE" and item.owner_id == work_package.work_package_id)
                    or (item.owner_type == "DELIVERABLE" and item.owner_id in owned_deliverables)
                )
            ]
            if not any(
                item.owner_type == "WORK_PACKAGE" and item.owner_id == work_package.work_package_id
                for item in required_criteria
            ):
                raise MissionExecutionError(
                    "ACCEPT bloqueado: o WorkPackage nao tem AcceptanceCriterion obrigatorio."
                )
            criterion_evidence: dict[str, list[str]] = {}
            for criterion in required_criteria:
                matching = [
                    item.evidence_id for item in selected
                    if not criterion.required_evidence_kinds or item.kind in criterion.required_evidence_kinds
                ]
                available_kinds = {item.kind for item in selected}
                missing = set(criterion.required_evidence_kinds) - available_kinds
                if not matching or missing:
                    raise MissionExecutionError(
                        f"Evidence insuficiente para o criterio {criterion.criterion_id}; faltam {sorted(missing)}."
                    )
                criterion_evidence[criterion.criterion_id] = matching
            missing_deliverables = [
                item_id for item_id in work_package.required_deliverables
                if item_id not in owned_deliverables
            ]
            if missing_deliverables:
                raise MissionExecutionError(f"Deliverables obrigatorios inexistentes: {missing_deliverables}.")

            for criterion in required_criteria:
                previous = criterion.version
                criterion.status = "SATISFIED"
                criterion.evidence_refs = criterion_evidence[criterion.criterion_id]
                criterion.validation_note = str(review_note or "Aceite em revisao manual.").strip()
                criterion.validated_at = utc_now()
                self.mission_state._touch(criterion)
                self.mission_state._write_entity(
                    self.mission_state._entity_path(
                        project_id, mission_id, "criteria", criterion.criterion_id
                    ),
                    criterion,
                )
                self.mission_state._append_event(
                    project_id, mission_id, "CRITERION", criterion.criterion_id,
                    "CRITERION_STATUS_CHANGED", previous, criterion.version,
                    {"previous_status": "PENDING", "status": "SATISFIED", "evidence_refs": criterion.evidence_refs},
                )
            for deliverable_id in work_package.required_deliverables:
                deliverable = owned_deliverables[deliverable_id]
                previous = deliverable.version
                deliverable.evidence_refs = list(dict.fromkeys(deliverable.evidence_refs + refs))
                deliverable.status = "ACCEPTED"
                self.mission_state._touch(deliverable)
                self.mission_state._write_entity(
                    self.mission_state._entity_path(
                        project_id, mission_id, "deliverables", deliverable.deliverable_id
                    ),
                    deliverable,
                )
                self.mission_state._append_event(
                    project_id, mission_id, "DELIVERABLE", deliverable.deliverable_id,
                    "DELIVERABLE_STATUS_CHANGED", previous, deliverable.version,
                    {"status": "ACCEPTED", "execution_id": execution_id},
                )

            previous_work_package = work_package.version
            work_package.status = "COMPLETED"
            work_package.completed_at = utc_now()
            work_package.blocked_reason = ""
            self.mission_state._touch(work_package)
            self.mission_state._write_entity(
                self.mission_state._entity_path(
                    project_id, mission_id, "work_packages", work_package.work_package_id
                ),
                work_package,
            )
            previous_execution = execution.version
            execution.status = "COMPLETED"
            execution.completed_at = utc_now()
            execution.review_note = str(review_note or "").strip()
            self._release_execution_lock(execution)
            self._save_execution(project_id, execution)
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution_id,
                "MISSION_EXECUTION_REVIEWED", previous_execution, execution.version,
                {"decision": "ACCEPT", "evidence_refs": refs, "review_note": execution.review_note},
            )
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution_id,
                "MISSION_EXECUTION_COMPLETED", previous_execution, execution.version,
                {"work_package_id": work_package.work_package_id},
            )
            self.mission_state._append_event(
                project_id, mission_id, "WORK_PACKAGE", work_package.work_package_id,
                "WORK_PACKAGE_STATUS_CHANGED", previous_work_package, work_package.version,
                {"status": "COMPLETED", "execution_id": execution_id},
            )
            self.mission_state._append_event(
                project_id, mission_id, "WORK_PACKAGE", work_package.work_package_id,
                "WORK_PACKAGE_LOCK_RELEASED", previous_execution, execution.version,
                {"execution_id": execution_id, "reason": "accepted"},
            )
            mission = self.mission_state._load_mission_entity(project_id, mission_id)
            self.mission_state._touch_mission_after_child_change(project_id, mission)
        return self.load_snapshot(project_id, mission_id)

    def _reject_execution(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        expected_execution_version: int,
        review_note: str,
        validation_failed: bool,
    ) -> dict[str, Any]:
        with self.mission_state._locked_mission(project_id, mission_id):
            execution = self._load_execution(project_id, mission_id, execution_id)
            self._expect_execution_version(execution, expected_execution_version)
            if execution.status != "WAITING_FOR_REVIEW":
                raise MissionExecutionError("Apenas execucoes WAITING_FOR_REVIEW podem ser rejeitadas.")
            previous = execution.version
            execution.status = "VALIDATION_FAILED" if validation_failed else "FAILED"
            execution.completed_at = utc_now()
            execution.review_note = str(review_note or "Rejeitado em revisao manual.").strip()
            self._release_execution_lock(execution)
            self._save_execution(project_id, execution)
            self._reset_work_package_after_execution(project_id, mission_id, execution.work_package_id)
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution_id,
                "MISSION_EXECUTION_REVIEWED", previous, execution.version,
                {"decision": "REJECT", "review_note": execution.review_note},
            )
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution_id,
                "MISSION_EXECUTION_FAILED", previous, execution.version,
                {"validation_failed": validation_failed},
            )
            self.mission_state._append_event(
                project_id, mission_id, "WORK_PACKAGE", execution.work_package_id,
                "WORK_PACKAGE_LOCK_RELEASED", previous, execution.version,
                {"execution_id": execution_id, "reason": "rejected"},
            )
            mission = self.mission_state._load_mission_entity(project_id, mission_id)
            self.mission_state._touch_mission_after_child_change(project_id, mission)
        return self.load_snapshot(project_id, mission_id)

    def _fail_execution(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        error: Exception,
        validation_failed: bool,
        output: dict[str, Any] | None = None,
        rollback_error: dict[str, str] | None = None,
        artifact_refs: list[str] | None = None,
        validation_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        with self.mission_state._locked_mission(project_id, mission_id):
            execution = self._load_execution(project_id, mission_id, execution_id)
            if execution.status == "CANCELLED":
                return self.load_snapshot(project_id, mission_id)
            previous = execution.version
            execution.status = "VALIDATION_FAILED" if validation_failed else "FAILED"
            execution.completed_at = utc_now()
            execution.primary_error = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            }
            execution.rollback_error = rollback_error
            if output:
                execution.output_summary = {**execution.output_summary, **output}
            if artifact_refs is not None:
                execution.artifact_refs = artifact_refs
            if validation_refs is not None:
                execution.validation_refs = validation_refs
            self._release_execution_lock(execution)
            self._save_execution(project_id, execution)
            work_package = self.mission_state._load_work_package(
                project_id, mission_id, execution.work_package_id
            )
            previous_work_package = work_package.version
            work_package.status = "VALIDATION_FAILED" if validation_failed else "READY"
            work_package.blocked_reason = ""
            self.mission_state._touch(work_package)
            self.mission_state._write_entity(
                self.mission_state._entity_path(
                    project_id, mission_id, "work_packages", work_package.work_package_id
                ),
                work_package,
            )
            self.mission_state._append_event(
                project_id, mission_id, "MISSION_EXECUTION", execution_id,
                "MISSION_EXECUTION_FAILED", previous, execution.version,
                {"validation_failed": validation_failed, "error": str(error)},
            )
            self.mission_state._append_event(
                project_id, mission_id, "WORK_PACKAGE", work_package.work_package_id,
                "WORK_PACKAGE_STATUS_CHANGED", previous_work_package, work_package.version,
                {"status": work_package.status, "execution_id": execution_id},
            )
            self.mission_state._append_event(
                project_id, mission_id, "WORK_PACKAGE", work_package.work_package_id,
                "WORK_PACKAGE_LOCK_RELEASED", previous, execution.version,
                {"execution_id": execution_id, "reason": "failed"},
            )
            mission = self.mission_state._load_mission_entity(project_id, mission_id)
            self.mission_state._touch_mission_after_child_change(project_id, mission)
        return self.load_snapshot(project_id, mission_id)

    def _create_coding_evidence(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        session: CodingSession,
    ) -> tuple[list[str], list[str], list[str]]:
        evidence_ids: list[str] = []
        coding_id = f"{execution_id}-coding"
        self.mission_state.attach_evidence(
            project_id,
            mission_id,
            self._load_execution(project_id, mission_id, execution_id).work_package_id,
            "CODING_SESSION",
            f"coding_session:{session.session_id}",
            "CodingSession executada pelo Mission Executor.",
            evidence_id=coding_id,
        )
        evidence_ids.append(coding_id)
        validation_id = f"{execution_id}-validation"
        self.mission_state.attach_evidence(
            project_id,
            mission_id,
            self._load_execution(project_id, mission_id, execution_id).work_package_id,
            "VALIDATION",
            f"validation:{session.session_id}",
            "Resultados das validacoes obrigatorias da CodingSession.",
            metadata={"results": session.validation_results},
            evidence_id=validation_id,
        )
        evidence_ids.append(validation_id)
        artifact_refs = self._coding_artifact_refs(project_id, session)
        for index, source_ref in enumerate(artifact_refs, start=1):
            evidence_id = f"{execution_id}-file-{index}"
            self.mission_state.attach_evidence(
                project_id,
                mission_id,
                self._load_execution(project_id, mission_id, execution_id).work_package_id,
                "ARTIFACT",
                source_ref,
                "Ficheiro alterado pela CodingSession.",
                evidence_id=evidence_id,
            )
            evidence_ids.append(evidence_id)
        return evidence_ids, artifact_refs, [f"validation:{session.session_id}"]

    def _create_builder_evidence(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
        result: dict[str, Any],
        artifact_refs: list[str],
    ) -> list[str]:
        work_package_id = self._load_execution(project_id, mission_id, execution_id).work_package_id
        evidence_ids: list[str] = []
        built_project_id = self._built_project_id(result)
        context_id = f"{execution_id}-project"
        self.mission_state.attach_evidence(
            project_id,
            mission_id,
            work_package_id,
            "PROJECT_CONTEXT",
            f"project_context:{built_project_id}",
            "Projeto isolado criado pelo ProjectBuilder.",
            evidence_id=context_id,
        )
        evidence_ids.append(context_id)
        validation_id = f"{execution_id}-validation"
        self.mission_state.attach_evidence(
            project_id,
            mission_id,
            work_package_id,
            "VALIDATION",
            f"validation:{execution_id}",
            "Validacao tecnica do ProjectBuilder.",
            metadata={
                "commands": result.get("commands_executed") or [],
                "preview_url": result.get("preview_url") or "",
            },
            evidence_id=validation_id,
        )
        evidence_ids.append(validation_id)
        for index, source_ref in enumerate(artifact_refs, start=1):
            evidence_id = f"{execution_id}-file-{index}"
            self.mission_state.attach_evidence(
                project_id,
                mission_id,
                work_package_id,
                "ARTIFACT",
                source_ref,
                "Artefacto criado pelo ProjectBuilder.",
                evidence_id=evidence_id,
            )
            evidence_ids.append(evidence_id)
        return evidence_ids

    def _assert_coding_input(
        self,
        project_id: str,
        mission_id: str,
        work_package: WorkPackage,
    ) -> None:
        if not work_package.description.strip():
            raise MissionExecutionError("CODING exige uma descricao objetiva e verificavel.")
        criteria = self.mission_state._load_entities(
            project_id, mission_id, "criteria", AcceptanceCriterion
        )
        owned = [
            item for item in criteria.values()
            if item.owner_type == "WORK_PACKAGE"
            and item.owner_id == work_package.work_package_id
            and item.required
            and item.description.strip()
        ]
        if not owned:
            raise MissionExecutionError("CODING exige pelo menos um AcceptanceCriterion obrigatorio e claro.")

    def _assert_no_active_execution(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
    ) -> None:
        executions = self.mission_state._load_raw_entities(
            project_id, mission_id, "executions", "execution_id"
        )
        for raw in executions.values():
            if raw.get("work_package_id") == work_package_id and raw.get("status") in ACTIVE_LOCK_STATUSES:
                raise MissionExecutionError(
                    f"O WorkPackage ja possui uma execucao ativa: {raw.get('execution_id')}."
                )

    @staticmethod
    def _dependencies_satisfied(
        work_package: WorkPackage,
        packages: dict[str, WorkPackage],
    ) -> bool:
        return all(
            dependency in packages and packages[dependency].status == "COMPLETED"
            for dependency in work_package.dependencies
        )

    def _reset_work_package_after_execution(
        self,
        project_id: str,
        mission_id: str,
        work_package_id: str,
    ) -> None:
        work_package = self.mission_state._load_work_package(
            project_id, mission_id, work_package_id
        )
        packages = self.mission_state._load_entities(
            project_id, mission_id, "work_packages", WorkPackage
        )
        dependencies_ready = self._dependencies_satisfied(work_package, packages)
        previous = work_package.version
        work_package.status = "READY" if dependencies_ready else "BLOCKED"
        work_package.blocked_reason = "" if dependencies_ready else "Dependencias deixaram de estar satisfeitas."
        self.mission_state._touch(work_package)
        self.mission_state._write_entity(
            self.mission_state._entity_path(
                project_id, mission_id, "work_packages", work_package_id
            ),
            work_package,
        )
        self.mission_state._append_event(
            project_id, mission_id, "WORK_PACKAGE", work_package_id,
            "WORK_PACKAGE_STATUS_CHANGED", previous, work_package.version,
            {"status": work_package.status, "reason": "execution_finished_without_acceptance"},
        )

    @staticmethod
    def _executor_kind(work_package: WorkPackage) -> str:
        declared = str(work_package.executor_kind or "").strip().upper()
        if declared and declared != "MANUAL":
            return declared
        return str(work_package.type or "GENERIC").strip().upper()

    @staticmethod
    def _execution_objective(work_package: dict[str, Any]) -> str:
        title = str(work_package.get("title") or "").strip()
        description = str(work_package.get("description") or "").strip()
        return f"{title}\n\n{description}".strip()

    @staticmethod
    def _coding_artifact_refs(project_id: str, session: CodingSession) -> list[str]:
        return [
            f"file:workspace/projects/{project_id}/{path}".replace("\\", "/")
            for path in session.affected_files
        ]

    @staticmethod
    def _built_project_id(result: dict[str, Any]) -> str:
        relative = str(result.get("project_rel_dir") or "").replace("\\", "/").rstrip("/")
        project_id = relative.rsplit("/", 1)[-1]
        if not project_id:
            raise MissionExecutionError("ProjectBuilder nao devolveu o project_id criado.")
        return project_id

    def _load_execution(
        self,
        project_id: str,
        mission_id: str,
        execution_id: str,
    ) -> MissionExecution:
        execution_id = self.mission_state._validate_id(execution_id, "execution_id")
        path = self.mission_state._entity_path(
            project_id, mission_id, "executions", execution_id
        )
        try:
            execution = MissionExecution(**self.mission_state._read_json(path))
        except TypeError as exc:
            raise MissionExecutionError(f"MissionExecution invalida: {exc}") from exc
        if execution.mission_id != mission_id:
            raise MissionExecutionError("MissionExecution pertence a outra Mission.")
        return execution

    def _save_execution(self, project_id: str, execution: MissionExecution) -> None:
        if execution.status not in EXECUTION_STATUSES:
            raise MissionExecutionError(f"Estado de MissionExecution invalido: {execution.status}.")
        path = self.mission_state._entity_path(
            project_id, execution.mission_id, "executions", execution.execution_id
        )
        self.mission_state._write_entity(path, execution)

    @staticmethod
    def _expect_execution_version(execution: MissionExecution, expected_version: int) -> None:
        try:
            expected = int(expected_version)
        except (TypeError, ValueError) as exc:
            raise MissionExecutionError("expected_execution_version deve ser inteiro.") from exc
        if execution.version != expected:
            raise StaleVersionError(
                f"Update stale rejeitado: expected_version={expected}, current_version={execution.version}."
            )

    @staticmethod
    def _touch_execution(execution: MissionExecution, timestamp: str | None = None) -> None:
        execution.version += 1
        execution.updated_at = timestamp or utc_now()

    def _heartbeat(self, execution: MissionExecution) -> None:
        now = utc_now()
        execution.heartbeat_at = now
        self._touch_execution(execution, now)

    def _release_execution_lock(self, execution: MissionExecution) -> None:
        execution.lock_owner = None
        self._touch_execution(execution)

    @staticmethod
    def _age_seconds(timestamp: str | None) -> float:
        if not timestamp:
            return float("inf")
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())

    @staticmethod
    def _execution_from_snapshot(snapshot: dict[str, Any], execution_id: str) -> MissionExecution:
        raw = next(
            item for item in snapshot.get("executions") or []
            if item.get("execution_id") == execution_id
        )
        return MissionExecution(**raw)
