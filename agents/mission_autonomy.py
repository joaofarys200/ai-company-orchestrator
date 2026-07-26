from __future__ import annotations

import json
import os
import socket
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from agents.executors import ExecutorNotFoundError, ExecutorRegistry
from agents.mission_executor import (
    ACTIVE_LOCK_STATUSES,
    ExecutorUnavailableError,
    MissionExecutorService,
)
from agents.mission_state import (
    MissionStateError,
    MissionStateStore,
    StaleVersionError,
    utc_now,
)
from backend.logging_config import get_logger, log_event


AUTONOMY_CYCLE_STATUSES = {
    "NO_ELIGIBLE_WORK",
    "EXECUTED_ONE",
    "WAITING_FOR_REVIEW",
    "EXECUTION_FAILED",
    "VALIDATION_FAILED",
    "BLOCKED",
    "EXECUTOR_UNAVAILABLE",
    "AUTONOMY_NOT_ALLOWED",
    "MISSION_NOT_ACTIVE",
    "MISSION_COMPLETED",
    "MAX_STEPS_REACHED",
    "NO_PROGRESS",
    "STALE_VERSION",
    "CANCELLED",
}
DEFAULT_MAX_WORK_PACKAGES = 1
HARD_MAX_WORK_PACKAGES = 3


class MissionAutonomyError(MissionStateError):
    pass


class AutonomyCycleLockedError(MissionAutonomyError):
    pass


@dataclass
class AutonomyCycleResult:
    project_id: str
    mission_id: str
    status: str
    selected_work_packages: list[str] = field(default_factory=list)
    execution_ids: list[str] = field(default_factory=list)
    stop_reason: str = ""
    snapshot_version: int | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    selected_work_package_id: str | None = None
    selection_reason: str = ""
    eligible_count: int = 0
    skipped_packages: list[dict[str, str]] = field(default_factory=list)
    cycle_id: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _Selection:
    work_package: dict[str, Any] | None
    status: str | None
    reason: str
    eligible_count: int
    skipped: list[dict[str, str]]


class MissionAutonomyController:
    """Bounded, explicit autonomy over MissionState eligible work packages."""

    def __init__(
        self,
        workspace_root: str = ".",
        *,
        mission_state: MissionStateStore | None = None,
        executor_service: MissionExecutorService | None = None,
        executor_registry: ExecutorRegistry | None = None,
        max_cycle_work_packages: int | None = None,
        stale_lock_min_age_seconds: float | None = None,
        owner_id: str | None = None,
    ):
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.mission_state = mission_state or (
            executor_service.mission_state
            if executor_service is not None
            else MissionStateStore(self.workspace_root)
        )
        self.executor_service = executor_service or MissionExecutorService(
            self.workspace_root,
            mission_state=self.mission_state,
            executor_registry=executor_registry,
        )
        service_registry = self.executor_service.executor_registry
        if executor_registry is not None and executor_registry is not service_registry:
            raise MissionAutonomyError(
                "O controlador e o MissionExecutorService devem usar o mesmo ExecutorRegistry."
            )
        self.executor_registry = service_registry
        configured_max = max_cycle_work_packages
        if configured_max is None:
            configured_max = self._env_int(
                "JARVIS_MISSION_AUTONOMY_MAX_STEPS",
                HARD_MAX_WORK_PACKAGES,
            )
        self.max_cycle_work_packages = min(
            HARD_MAX_WORK_PACKAGES,
            max(1, int(configured_max)),
        )
        configured_stale = stale_lock_min_age_seconds
        if configured_stale is None:
            configured_stale = self._env_float(
                "JARVIS_MISSION_AUTONOMY_STALE_LOCK_SECONDS",
                300.0,
            )
        self.stale_lock_min_age_seconds = max(1.0, float(configured_stale))
        self.owner_id = owner_id or (
            f"mission-autonomy:{os.getpid()}:{uuid.uuid4().hex[:12]}"
        )
        self.logger = get_logger(__name__)

    async def run_cycle(
        self,
        project_id: str,
        mission_id: str,
        expected_mission_version: int | None = None,
        max_work_packages: int = DEFAULT_MAX_WORK_PACKAGES,
        test_mode: bool = False,
    ) -> AutonomyCycleResult:
        requested_max = self._validate_max_work_packages(max_work_packages)
        if expected_mission_version is not None and (
            isinstance(expected_mission_version, bool)
            or not isinstance(expected_mission_version, int)
            or expected_mission_version < 1
        ):
            raise MissionAutonomyError(
                "expected_mission_version deve ser um inteiro positivo."
            )
        cycle_id = uuid.uuid4().hex
        started = time.perf_counter()
        result = AutonomyCycleResult(
            project_id=project_id,
            mission_id=mission_id,
            status="BLOCKED",
            cycle_id=cycle_id,
        )
        try:
            with self._cycle_lock(project_id, mission_id, cycle_id):
                snapshot = self.executor_service.load_snapshot(
                    project_id,
                    mission_id,
                )
                self._record_event(
                    result,
                    snapshot,
                    "AUTONOMY_CYCLE_STARTED",
                    status="RUNNING",
                    reason="explicit_confirmed_request",
                    cycle_step=0,
                )
                current_version = int(snapshot["mission"]["version"])
                if (
                    expected_mission_version is not None
                    and current_version != expected_mission_version
                ):
                    return self._stop(
                        result,
                        snapshot,
                        "STALE_VERSION",
                        (
                            "expected_mission_version="
                            f"{expected_mission_version}, current_version={current_version}"
                        ),
                        started,
                    )

                while len(result.selected_work_packages) < requested_max:
                    snapshot = self.executor_service.load_snapshot(
                        project_id,
                        mission_id,
                    )
                    mission_status = str(
                        snapshot["mission"].get("status") or ""
                    ).upper()
                    if mission_status == "COMPLETED":
                        return self._stop(
                            result,
                            snapshot,
                            "MISSION_COMPLETED",
                            "mission_completed",
                            started,
                        )
                    if mission_status != "ACTIVE":
                        return self._stop(
                            result,
                            snapshot,
                            "MISSION_NOT_ACTIVE",
                            f"mission_status_{mission_status.lower()}",
                            started,
                        )

                    active = self._active_executions(snapshot)
                    if active:
                        waiting = any(
                            item.get("status") == "WAITING_FOR_REVIEW"
                            or (
                                item.get("status") == "RUNNING"
                                and (
                                    item.get("output_summary") or {}
                                ).get("phase")
                                == "AWAITING_APPLY_APPROVAL"
                            )
                            for item in active
                        )
                        status = "WAITING_FOR_REVIEW" if waiting else "BLOCKED"
                        return self._stop(
                            result,
                            snapshot,
                            status,
                            "active_execution_requires_resolution",
                            started,
                        )

                    selection = self._select(snapshot)
                    if result.eligible_count == 0:
                        result.eligible_count = selection.eligible_count
                    result.skipped_packages.extend(selection.skipped)
                    if selection.work_package is None:
                        if selection.skipped:
                            skipped = selection.skipped[0]
                            self._record_event(
                                result,
                                snapshot,
                                "AUTONOMY_WORK_PACKAGE_SKIPPED",
                                work_package_id=skipped.get(
                                    "work_package_id"
                                ),
                                executor_kind=skipped.get("executor_kind"),
                                status=selection.status or "BLOCKED",
                                reason=selection.reason,
                                cycle_step=len(
                                    result.selected_work_packages
                                )
                                + 1,
                            )
                        if result.selected_work_packages:
                            return self._stop(
                                result,
                                snapshot,
                                "EXECUTED_ONE",
                                selection.reason,
                                started,
                            )
                        return self._stop(
                            result,
                            snapshot,
                            selection.status or "NO_ELIGIBLE_WORK",
                            selection.reason,
                            started,
                        )

                    work_package = selection.work_package
                    work_package_id = str(
                        work_package["work_package_id"]
                    )
                    executor_kind = self._executor_kind(work_package)
                    result.selected_work_package_id = work_package_id
                    result.selection_reason = selection.reason
                    result.selected_work_packages.append(work_package_id)
                    cycle_step = len(result.selected_work_packages)
                    self._record_event(
                        result,
                        snapshot,
                        "AUTONOMY_WORK_PACKAGE_SELECTED",
                        work_package_id=work_package_id,
                        executor_kind=executor_kind,
                        status="SELECTED",
                        reason=selection.reason,
                        cycle_step=cycle_step,
                    )
                    before_execution_ids = {
                        str(item.get("execution_id") or "")
                        for item in snapshot.get("executions") or []
                    }
                    self._record_event(
                        result,
                        snapshot,
                        "AUTONOMY_EXECUTION_STARTED",
                        work_package_id=work_package_id,
                        executor_kind=executor_kind,
                        status="RUNNING",
                        reason="delegated_to_mission_executor",
                        cycle_step=cycle_step,
                    )
                    try:
                        updated = (
                            await self.executor_service.execute_work_package(
                                project_id,
                                mission_id,
                                work_package_id,
                                int(snapshot["mission"]["version"]),
                                int(work_package["version"]),
                                test_mode=bool(test_mode),
                                autonomous=True,
                            )
                        )
                    except StaleVersionError as exc:
                        result.errors.append(self._error_dict(exc))
                        return self._stop(
                            result,
                            snapshot,
                            "STALE_VERSION",
                            "state_changed_before_execution",
                            started,
                        )
                    except ExecutorUnavailableError as exc:
                        result.errors.append(self._error_dict(exc))
                        return self._stop(
                            result,
                            snapshot,
                            "EXECUTOR_UNAVAILABLE",
                            "executor_became_unavailable",
                            started,
                        )
                    except MissionStateError as exc:
                        result.errors.append(self._error_dict(exc))
                        return self._stop(
                            result,
                            snapshot,
                            "EXECUTION_FAILED",
                            "mission_executor_rejected_execution",
                            started,
                        )

                    new_executions = [
                        item
                        for item in updated.get("executions") or []
                        if str(item.get("execution_id") or "")
                        not in before_execution_ids
                    ]
                    if not new_executions:
                        return self._stop(
                            result,
                            updated,
                            "NO_PROGRESS",
                            "mission_executor_created_no_execution",
                            started,
                        )
                    execution = sorted(
                        new_executions,
                        key=lambda item: (
                            str(item.get("updated_at") or ""),
                            str(item.get("execution_id") or ""),
                        ),
                    )[-1]
                    execution_id = str(execution["execution_id"])
                    result.execution_ids.append(execution_id)
                    execution_status = str(
                        execution.get("status") or "FAILED"
                    ).upper()
                    phase = str(
                        (execution.get("output_summary") or {}).get(
                            "phase"
                        )
                        or ""
                    ).upper()
                    self._record_event(
                        result,
                        updated,
                        "AUTONOMY_EXECUTION_FINISHED",
                        work_package_id=work_package_id,
                        execution_id=execution_id,
                        executor_kind=executor_kind,
                        status=execution_status,
                        reason=phase or execution_status.lower(),
                        cycle_step=cycle_step,
                    )

                    if (
                        execution_status == "WAITING_FOR_REVIEW"
                        or phase == "AWAITING_APPLY_APPROVAL"
                    ):
                        return self._stop(
                            result,
                            updated,
                            "WAITING_FOR_REVIEW",
                            (
                                "apply_approval_required"
                                if phase == "AWAITING_APPLY_APPROVAL"
                                else "manual_review_required"
                            ),
                            started,
                        )
                    if execution_status == "VALIDATION_FAILED":
                        return self._stop(
                            result,
                            updated,
                            "VALIDATION_FAILED",
                            "required_validation_failed",
                            started,
                        )
                    if execution_status == "FAILED":
                        return self._stop(
                            result,
                            updated,
                            "EXECUTION_FAILED",
                            "executor_failed",
                            started,
                        )
                    if execution_status == "CANCELLED":
                        return self._stop(
                            result,
                            updated,
                            "CANCELLED",
                            "execution_cancelled",
                            started,
                        )
                    if execution_status != "COMPLETED":
                        return self._stop(
                            result,
                            updated,
                            "NO_PROGRESS",
                            f"non_terminal_execution_{execution_status.lower()}",
                            started,
                        )
                    if (
                        str(updated["mission"].get("status") or "").upper()
                        == "COMPLETED"
                    ):
                        return self._stop(
                            result,
                            updated,
                            "MISSION_COMPLETED",
                            "mission_completed",
                            started,
                        )
                    if len(result.selected_work_packages) >= requested_max:
                        status = (
                            "EXECUTED_ONE"
                            if requested_max == 1
                            else "MAX_STEPS_REACHED"
                        )
                        return self._stop(
                            result,
                            updated,
                            status,
                            "configured_cycle_limit_reached",
                            started,
                        )

                return self._stop(
                    result,
                    snapshot,
                    "MAX_STEPS_REACHED",
                    "configured_cycle_limit_reached",
                    started,
                )
        except AutonomyCycleLockedError as exc:
            result.errors.append(self._error_dict(exc))
            try:
                snapshot = self.executor_service.load_snapshot(
                    project_id,
                    mission_id,
                )
            except MissionStateError:
                raise exc
            return self._stop(
                result,
                snapshot,
                "BLOCKED",
                "autonomy_cycle_lock_active",
                started,
                failed=True,
            )
        except MissionStateError:
            raise
        except Exception as exc:
            result.errors.append(self._error_dict(exc))
            snapshot = self.executor_service.load_snapshot(
                project_id,
                mission_id,
            )
            return self._stop(
                result,
                snapshot,
                "EXECUTION_FAILED",
                "autonomy_controller_failed",
                started,
                failed=True,
            )

    def _select(self, snapshot: dict[str, Any]) -> _Selection:
        eligible_ids = list(snapshot.get("eligible_work_packages") or [])
        packages = {
            str(item.get("work_package_id") or ""): item
            for item in snapshot.get("work_packages") or []
        }
        eligible = [
            packages[item_id]
            for item_id in eligible_ids
            if item_id in packages
        ]
        if len(eligible) != len(eligible_ids):
            return _Selection(
                None,
                "BLOCKED",
                "eligible_work_package_missing_from_snapshot",
                len(eligible_ids),
                [],
            )
        if not eligible:
            return _Selection(
                None,
                "NO_ELIGIBLE_WORK",
                "eligible_work_packages_is_empty",
                0,
                [],
            )
        eligible.sort(
            key=lambda item: (
                -int(item.get("priority") or 0),
                str(item.get("created_at") or ""),
                str(item.get("work_package_id") or ""),
            )
        )
        selected = eligible[0]
        work_package_id = str(selected["work_package_id"])
        executor_kind = self._executor_kind(selected)
        if str(selected.get("status") or "").upper() != "READY":
            skipped = [{
                "work_package_id": work_package_id,
                "executor_kind": executor_kind,
                "reason": "eligible_package_not_ready",
            }]
            return _Selection(
                None,
                "BLOCKED",
                "eligible_package_not_ready",
                len(eligible),
                skipped,
            )
        dependencies = list(selected.get("dependencies") or [])
        if any(
            dependency not in packages
            or str(packages[dependency].get("status") or "").upper()
            != "COMPLETED"
            for dependency in dependencies
        ):
            skipped = [{
                "work_package_id": work_package_id,
                "executor_kind": executor_kind,
                "reason": "dependency_inconsistent_with_eligibility",
            }]
            return _Selection(
                None,
                "BLOCKED",
                "dependency_inconsistent_with_eligibility",
                len(eligible),
                skipped,
            )
        try:
            descriptor = self.executor_registry.descriptor(executor_kind)
        except ExecutorNotFoundError:
            skipped = [{
                "work_package_id": work_package_id,
                "executor_kind": executor_kind,
                "reason": "executor_unknown",
            }]
            return _Selection(
                None,
                "EXECUTOR_UNAVAILABLE",
                "executor_unknown",
                len(eligible),
                skipped,
            )
        if not descriptor.supported:
            skipped = [{
                "work_package_id": work_package_id,
                "executor_kind": executor_kind,
                "reason": "executor_not_supported",
            }]
            return _Selection(
                None,
                "EXECUTOR_UNAVAILABLE",
                "executor_not_supported",
                len(eligible),
                skipped,
            )
        if not descriptor.autonomous_allowed:
            skipped = [{
                "work_package_id": work_package_id,
                "executor_kind": executor_kind,
                "reason": "executor_autonomy_disabled",
            }]
            return _Selection(
                None,
                "AUTONOMY_NOT_ALLOWED",
                "executor_autonomy_disabled",
                len(eligible),
                skipped,
            )
        return _Selection(
            selected,
            None,
            "highest_priority_then_oldest_created_at_then_work_package_id",
            len(eligible),
            [],
        )

    def _stop(
        self,
        result: AutonomyCycleResult,
        snapshot: dict[str, Any],
        status: str,
        reason: str,
        started: float,
        *,
        failed: bool = False,
    ) -> AutonomyCycleResult:
        if status not in AUTONOMY_CYCLE_STATUSES:
            raise MissionAutonomyError(
                f"Estado final de autonomia invalido: {status}."
            )
        result.status = status
        result.stop_reason = reason
        result.snapshot_version = int(snapshot["mission"]["version"])
        result.elapsed_ms = max(
            0,
            int((time.perf_counter() - started) * 1000),
        )
        self._record_event(
            result,
            snapshot,
            (
                "AUTONOMY_CYCLE_FAILED"
                if failed
                or status
                in {
                    "EXECUTION_FAILED",
                    "VALIDATION_FAILED",
                    "STALE_VERSION",
                }
                else "AUTONOMY_CYCLE_STOPPED"
            ),
            work_package_id=result.selected_work_package_id,
            execution_id=(
                result.execution_ids[-1]
                if result.execution_ids
                else None
            ),
            status=status,
            reason=reason,
            elapsed_ms=result.elapsed_ms,
            cycle_step=len(result.selected_work_packages),
        )
        return result

    def _record_event(
        self,
        result: AutonomyCycleResult,
        snapshot: dict[str, Any],
        event_type: str,
        *,
        work_package_id: str | None = None,
        execution_id: str | None = None,
        executor_kind: str | None = None,
        reason: str = "",
        status: str = "",
        elapsed_ms: int = 0,
        cycle_step: int = 0,
    ) -> None:
        payload = {
            "mission_id": result.mission_id,
            "work_package_id": work_package_id,
            "execution_id": execution_id,
            "executor_kind": executor_kind,
            "reason": reason,
            "status": status,
            "elapsed_ms": int(elapsed_ms),
            "cycle_step": int(cycle_step),
        }
        event = {"event_type": event_type, **payload}
        result.events.append(event)
        with self.mission_state._locked_mission(
            result.project_id,
            result.mission_id,
        ):
            mission = self.mission_state._load_mission_entity(
                result.project_id,
                result.mission_id,
            )
            self.mission_state._append_event(
                result.project_id,
                result.mission_id,
                "MISSION_AUTONOMY",
                result.cycle_id,
                event_type,
                mission.version,
                mission.version,
                payload,
            )
        log_event(
            self.logger,
            event_type.lower(),
            project_id=result.project_id,
            **payload,
        )

    @staticmethod
    def _active_executions(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            item
            for item in snapshot.get("executions") or []
            if str(item.get("status") or "").upper()
            in ACTIVE_LOCK_STATUSES
            and item.get("lock_owner")
        ]

    @staticmethod
    def _executor_kind(work_package: dict[str, Any]) -> str:
        declared = str(
            work_package.get("executor_kind") or ""
        ).strip().upper()
        if declared and declared != "MANUAL":
            return declared
        return str(
            work_package.get("type") or "GENERIC"
        ).strip().upper()

    def _validate_max_work_packages(self, value: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise MissionAutonomyError(
                "max_work_packages deve ser um inteiro."
            )
        if value < 1 or value > self.max_cycle_work_packages:
            raise MissionAutonomyError(
                "max_work_packages deve estar entre 1 e "
                f"{self.max_cycle_work_packages}."
            )
        return value

    @contextmanager
    def _cycle_lock(
        self,
        project_id: str,
        mission_id: str,
        cycle_id: str,
    ) -> Iterator[None]:
        project_id = self.mission_state._validate_project(project_id)
        mission_dir = self.mission_state._mission_dir(
            project_id,
            mission_id,
        )
        if not os.path.isfile(os.path.join(mission_dir, "mission.json")):
            raise MissionStateError(f"Missao '{mission_id}' nao existe.")
        path = os.path.join(mission_dir, ".autonomy.lock")
        token = uuid.uuid4().hex
        payload = {
            "token": token,
            "cycle_id": cycle_id,
            "owner_id": self.owner_id,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": utc_now(),
        }
        handle = None
        for attempt in range(2):
            try:
                handle = os.open(
                    path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                encoded = (
                    json.dumps(payload, separators=(",", ":")) + "\n"
                ).encode("utf-8")
                os.write(handle, encoded)
                os.fsync(handle)
                break
            except FileExistsError as exc:
                if attempt == 0 and self._reclaim_stale_lock(path):
                    continue
                raise AutonomyCycleLockedError(
                    "Ja existe um ciclo autonomo ativo para esta missao."
                ) from exc
        if handle is None:
            raise AutonomyCycleLockedError(
                "Nao foi possivel adquirir o lock do ciclo autonomo."
            )
        try:
            yield
        finally:
            os.close(handle)
            try:
                current = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                current = {}
            if current.get("token") == token:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

    def _reclaim_stale_lock(self, path: str) -> bool:
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        created_at = str(raw.get("created_at") or "")
        if self._age_seconds(created_at) < self.stale_lock_min_age_seconds:
            return False
        if str(raw.get("hostname") or "") != socket.gethostname():
            return False
        try:
            pid = int(raw.get("pid"))
        except (TypeError, ValueError):
            return False
        if self._pid_alive(pid):
            return False
        quarantine = f"{path}.{uuid.uuid4().hex}.stale"
        try:
            os.replace(path, quarantine)
        except (FileNotFoundError, OSError):
            return False
        try:
            os.unlink(quarantine)
        except FileNotFoundError:
            pass
        return True

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if pid == os.getpid():
            return True
        try:
            os.kill(pid, 0)
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def _age_seconds(timestamp: str) -> float:
        if not timestamp:
            return float("inf")
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            return float("inf")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(
            0.0,
            (
                datetime.now(timezone.utc) - parsed
            ).total_seconds(),
        )

    @staticmethod
    def _error_dict(error: Exception) -> dict[str, str]:
        return {
            "type": type(error).__name__,
            "message": str(error),
        }

    @staticmethod
    def _env_int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return float(os.getenv(name, str(default)))
        except ValueError:
            return default
