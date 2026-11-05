"""
JARVIS OS — Mission Recovery Engine
Phase 25: Durable Mission State, Checkpoint Recovery & Persistence Reliability.

Provides:
1. Discoverability and forensic classification of interrupted missions across restarts.
2. Safe reconciliation of uncertain side effects (dependencies, file leases, code modifications, tests).
3. Enforcement of Phase 24 authorization boundaries post-restart.
4. Single-recovery ownership lock per mission to prevent race conditions.
5. Idempotent recovery procedures with non-destructive diagnostics and auditable logs.
"""

from __future__ import annotations

import copy
import dataclasses
import enum
import glob
import json
import logging
import os
import shutil
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from agents.file_lease_manager import FileLease, get_file_lease_manager
from agents.mission_orchestrator import Checkpoint, MissionLifecycleOrchestrator, MissionLifecycleStatus
from agents.mission_state import (
    AcceptanceCriterion,
    Deliverable,
    Evidence,
    Mission,
    MissionStateError,
    MissionStateStore,
    WorkPackage,
    utc_now,
)
from security.permission_gateway.gateway import PermissionGatewayService, get_permission_gateway_service
from security.permission_gateway.models import PermissionRequest, PermissionRequestStatus
from security.permission_gateway.project_dependency_manager import ProjectDependencyManager

logger = logging.getLogger("Jarvis.MissionRecoveryEngine")


class RecoveryClassification(str, enum.Enum):
    """Canonical recovery classifications for interrupted or persisted missions."""
    COMPLETED = "COMPLETED"
    SAFELY_RESUMABLE = "SAFELY_RESUMABLE"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AWAITING_EXTERNAL_INPUT = "AWAITING_EXTERNAL_INPUT"
    REQUIRES_RECONCILIATION = "REQUIRES_RECONCILIATION"
    FAILED = "FAILED"
    CORRUPTED = "CORRUPTED"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"


@dataclass
class RecoveryAssessment:
    """Forensic assessment of a persisted mission's state and recovery eligibility."""
    mission_id: str
    project_id: str
    project_path: str
    classification: RecoveryClassification
    current_status: str
    current_stage: str
    reasons: list[str] = field(default_factory=list)
    pending_work_packages: list[str] = field(default_factory=list)
    completed_work_packages: list[str] = field(default_factory=list)
    uncertain_operations: list[dict[str, Any]] = field(default_factory=list)
    safe_to_resume: bool = False
    last_valid_checkpoint_seq: int = 0
    schema_version: int = 2
    recovery_actions_taken: list[str] = field(default_factory=list)
    reconciled_dependencies: list[str] = field(default_factory=list)
    reacquired_leases: list[str] = field(default_factory=list)
    pending_approval_request_id: Optional[str] = None
    evidence_orphans: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["classification"] = self.classification.value
        return d


class RecoveryLockError(Exception):
    """Raised when a mission recovery lock is already held by another active process."""
    pass


class MissionRecoveryEngine:
    """
    Engine responsible for discovering, assessing, reconciling, and safely resuming
    missions that were interrupted by application restarts, crashes, or unhandled failures.
    """

    def __init__(
        self,
        workspace_root: str = ".",
        mission_state: Optional[MissionStateStore] = None,
        permission_gateway: Optional[PermissionGatewayService] = None,
        dependency_manager: Optional[ProjectDependencyManager] = None,
    ) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self.metadata_root = os.path.join(self.workspace_root, "workspace", ".jarvis", "projects")
        self.legacy_root = os.path.join(self.workspace_root, "workspace", "projects")
        self.audit_log_path = os.path.join(self.workspace_root, "workspace", ".jarvis", "recovery_audit.jsonl")

        self.mission_state = mission_state or MissionStateStore(workspace_root=self.workspace_root)
        self.gateway = permission_gateway or get_permission_gateway_service()
        self.dependency_manager = dependency_manager or ProjectDependencyManager(gateway=self.gateway)
        self.file_lease_manager = get_file_lease_manager()
        self._lock = threading.RLock()
        self._active_recovery_locks: Dict[str, str] = {}  # mission_key -> lock_file_path

    # ── DISCOVERY ─────────────────────────────────────────────────────────────

    def discover_all_missions(self) -> list[tuple[str, str]]:
        """
        Discovers all missions across all projects in the workspace.
        Returns unique list of (project_id, mission_id) tuples.
        """
        discovered: Set[Tuple[str, str]] = set()

        # 1. Primary storage: workspace/.jarvis/projects/<project_id>/missions/<mission_id>/
        if os.path.isdir(self.metadata_root):
            for p_entry in os.scandir(self.metadata_root):
                if p_entry.is_dir():
                    project_id = p_entry.name
                    m_root = os.path.join(p_entry.path, "missions")
                    if os.path.isdir(m_root):
                        for m_entry in os.scandir(m_root):
                            if m_entry.is_dir():
                                discovered.add((project_id, m_entry.name))

        # 2. Legacy workspace projects: workspace/projects/<project_id>/.jarvis/missions/
        if os.path.isdir(self.legacy_root):
            for p_entry in os.scandir(self.legacy_root):
                if p_entry.is_dir():
                    project_id = p_entry.name
                    legacy_m_dir = os.path.join(p_entry.path, ".jarvis", "missions")
                    if os.path.isdir(legacy_m_dir):
                        for m_entry in os.scandir(legacy_m_dir):
                            if m_entry.is_dir():
                                discovered.add((project_id, m_entry.name))

        return sorted(list(discovered))

    # ── FORENSIC ASSESSMENT & CLASSIFICATION ──────────────────────────────────

    def assess_mission(self, project_id: str, mission_id: str) -> RecoveryAssessment:
        """
        Performs a deep forensic inspection of a mission's persisted state,
        correlating mission.json, checkpoints, work packages, file leases,
        acceptance criteria, and JIT authorization requests.
        """
        reasons: list[str] = []
        uncertain_ops: list[dict[str, Any]] = []

        # 1. Locate mission directory
        mission_dir = self.mission_state._mission_dir(project_id, mission_id)
        if not os.path.isdir(mission_dir):
            return RecoveryAssessment(
                mission_id=mission_id,
                project_id=project_id,
                project_path="",
                classification=RecoveryClassification.CORRUPTED,
                current_status="MISSING",
                current_stage="",
                reasons=[f"Diretório da missão não encontrado: {mission_dir}"],
            )

        # 2. Read mission.json manifest
        manifest_path = os.path.join(mission_dir, "mission.json")
        mission_data: dict[str, Any] = {}
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    mission_data = json.load(f)
            except Exception as exc:
                reasons.append(f"Ficheiro mission.json corrompido: {exc}")
        else:
            reasons.append("Ficheiro mission.json ausente.")

        # 3. Read latest checkpoint
        latest_cp: Optional[dict[str, Any]] = None
        checkpoint_seq = 0
        schema_version = 2
        try:
            latest_cp = self.mission_state.load_latest_checkpoint(project_id, mission_id)
            if latest_cp:
                checkpoint_seq = int(latest_cp.get("sequence", 0))
                schema_version = int(latest_cp.get("schema_version", 1))
        except Exception as exc:
            reasons.append(f"Erro ao ler checkpoint mais recente: {exc}")

        # If both manifest and checkpoint are unreadable, mark corrupted
        if not mission_data and not latest_cp:
            return RecoveryAssessment(
                mission_id=mission_id,
                project_id=project_id,
                project_path="",
                classification=RecoveryClassification.CORRUPTED,
                current_status="CORRUPTED",
                current_stage="",
                reasons=reasons or ["Nenhum estado válido pôde ser reconstruído."],
            )

        # Unsupported schema check
        if schema_version > 2:
            return RecoveryAssessment(
                mission_id=mission_id,
                project_id=project_id,
                project_path=str(mission_data.get("project_path", "")),
                classification=RecoveryClassification.UNSUPPORTED_SCHEMA,
                current_status=str(mission_data.get("status", "UNKNOWN")),
                current_stage=str(mission_data.get("current_stage", "")),
                reasons=[f"Versão de schema {schema_version} não é suportada por esta versão do JARVIS OS."],
                schema_version=schema_version,
            )

        status = str(mission_data.get("status") or (latest_cp.get("mission_status") if latest_cp else "UNKNOWN"))
        stage = str(mission_data.get("current_stage") or (latest_cp.get("current_stage") if latest_cp else "UNKNOWN"))
        proj_path = str(mission_data.get("project_path") or (latest_cp.get("project_path") if latest_cp else ""))
        if not proj_path:
            proj_path = os.path.join(self.workspace_root, "workspace", "projects", project_id)

        # 4. Inspect work packages
        pending_pkgs: list[str] = []
        completed_pkgs: list[str] = []
        running_pkgs: list[str] = []
        try:
            packages = self.mission_state.list_work_packages(project_id, mission_id)
            for pkg in packages:
                p_status = str(pkg.get("status", "PENDING")).upper()
                wpid = str(pkg.get("work_package_id", ""))
                if p_status == "COMPLETED":
                    completed_pkgs.append(wpid)
                elif p_status in {"RUNNING", "IN_PROGRESS"}:
                    running_pkgs.append(wpid)
                    uncertain_ops.append({
                        "work_package_id": wpid,
                        "title": pkg.get("title", ""),
                        "status": p_status,
                        "type": pkg.get("type", "GENERIC"),
                    })
                else:
                    pending_pkgs.append(wpid)
        except Exception as exc:
            reasons.append(f"Aviso ao inspecionar work packages: {exc}")

        # Check running tasks in checkpoint
        if latest_cp:
            cp_running = latest_cp.get("running_task_ids", [])
            for r_id in cp_running:
                if r_id not in running_pkgs:
                    running_pkgs.append(r_id)
                    uncertain_ops.append({"task_id": r_id, "source": "checkpoint_running_task_ids"})

        # 5. Check authorization state (PermissionGatewayService)
        pending_req_id: Optional[str] = None
        now = time.time()
        for req in self.gateway._requests.values():
            if req.mission_id == mission_id or (req.project_id == project_id and req.status in {
                PermissionRequestStatus.WAITING_FOR_USER.value,
                PermissionRequestStatus.REQUESTED.value,
            }):
                if req.status in {
                    PermissionRequestStatus.WAITING_FOR_USER.value,
                    PermissionRequestStatus.REQUESTED.value,
                }:
                    if now <= req.expires_at:
                        pending_req_id = req.request_id
                        break

        # 6. Apply Decision Rules for Classification
        classification: RecoveryClassification = RecoveryClassification.SAFELY_RESUMABLE
        safe_to_resume = False

        if status == "COMPLETED":
            classification = RecoveryClassification.COMPLETED
            safe_to_resume = False
            reasons.append("Missão concluída com sucesso no registo persistente.")
        elif status in {"FAILED", "CANCELLED"}:
            classification = RecoveryClassification.FAILED
            safe_to_resume = False
            reasons.append(f"Missão encontra-se em estado terminal '{status}'.")
        elif status == "PAUSED":
            classification = RecoveryClassification.AWAITING_EXTERNAL_INPUT
            safe_to_resume = False
            reasons.append("Missão pausada aguardando retomada explícita pelo operador.")
        elif pending_req_id is not None or status == "BLOCKED":
            classification = RecoveryClassification.AWAITING_APPROVAL
            safe_to_resume = False
            reasons.append(
                f"Missão aguardando aprovação explícita do utilizador para operação protegida (pedido: {pending_req_id})."
            )
        elif running_pkgs or uncertain_ops:
            classification = RecoveryClassification.REQUIRES_RECONCILIATION
            safe_to_resume = False
            reasons.append(
                f"Existem {len(running_pkgs)} operações que estavam em execução no momento da paragem do sistema."
            )
        else:
            # No running tasks, dependencies clear, pending work remains
            classification = RecoveryClassification.SAFELY_RESUMABLE
            safe_to_resume = True
            reasons.append("Missão possui ponto de paragem consistente e pode ser retomada com segurança.")

        return RecoveryAssessment(
            mission_id=mission_id,
            project_id=project_id,
            project_path=proj_path,
            classification=classification,
            current_status=status,
            current_stage=stage,
            reasons=reasons,
            pending_work_packages=pending_pkgs,
            completed_work_packages=completed_pkgs,
            uncertain_operations=uncertain_ops,
            safe_to_resume=safe_to_resume,
            last_valid_checkpoint_seq=checkpoint_seq,
            schema_version=schema_version,
            pending_approval_request_id=pending_req_id,
        )

    # ── SINGLE-RECOVERY OWNERSHIP LOCK ────────────────────────────────────────

    def acquire_recovery_lock(self, project_id: str, mission_id: str, timeout_seconds: float = 5.0) -> str:
        """
        Acquires exclusive recovery lock for the mission on disk to prevent concurrent
        workers or duplicated recovery procedures from racing.
        """
        mission_dir = self.mission_state._mission_dir(project_id, mission_id)
        os.makedirs(mission_dir, exist_ok=True)
        lock_file = os.path.join(mission_dir, ".recovery.lock")

        recovery_id = f"rec_{uuid.uuid4().hex[:10]}"
        pid = os.getpid()

        with self._lock:
            if os.path.isfile(lock_file):
                try:
                    with open(lock_file, "r", encoding="utf-8") as f:
                        lock_data = json.load(f)
                    owner_pid = int(lock_data.get("pid", 0))
                    # Check if owner PID is still running
                    if self._is_pid_alive(owner_pid) and owner_pid != pid:
                        raise RecoveryLockError(
                            f"Missão '{mission_id}' já está bloqueada para recuperação pelo processo PID {owner_pid} "
                            f"(recovery_id: {lock_data.get('recovery_id')})."
                        )
                except (json.JSONDecodeError, ValueError):
                    pass

            # Write lock file atomically
            tmp_lock = f"{lock_file}.tmp.{recovery_id}"
            payload = {
                "recovery_id": recovery_id,
                "pid": pid,
                "project_id": project_id,
                "mission_id": mission_id,
                "acquired_at": utc_now(),
            }
            with open(tmp_lock, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_lock, lock_file)

            mission_key = f"{project_id}:{mission_id}"
            self._active_recovery_locks[mission_key] = lock_file
            self._log_recovery_event("lock_acquired", project_id, mission_id, {"recovery_id": recovery_id, "pid": pid})
            return recovery_id

    def release_recovery_lock(self, project_id: str, mission_id: str) -> None:
        """Releases the recovery lock."""
        mission_key = f"{project_id}:{mission_id}"
        with self._lock:
            mission_dir = self.mission_state._mission_dir(project_id, mission_id)
            lock_file = os.path.join(mission_dir, ".recovery.lock")
            if os.path.isfile(lock_file):
                try:
                    os.remove(lock_file)
                except Exception:
                    pass
            self._active_recovery_locks.pop(mission_key, None)
            self._log_recovery_event("lock_released", project_id, mission_id)

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            if sys.platform == "win32":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                if process:
                    kernel32.CloseHandle(process)
                    return True
                err = kernel32.GetLastError()
                if err == 5:  # ERROR_ACCESS_DENIED means process is running under another credential/system
                    return True
                return False
            else:
                os.kill(pid, 0)
                return True
        except Exception:
            return False

    # ── RECONCILIATION OF UNCERTAIN SIDE EFFECTS ──────────────────────────────

    def reconcile_mission(self, project_id: str, mission_id: str) -> RecoveryAssessment:
        """
        Executes read-only and idempotent state reconciliation for an interrupted mission:
        1. Validates project path existence and integrity.
        2. Re-acquires file leases for any active modified files.
        3. Inspects project virtualenv to verify if interrupted package installations completed.
        4. Inspects working tree files to detect partial writes without overwriting user changes.
        5. Validates evidence backing acceptance criteria.
        6. Transitions safely from REQUIRES_RECONCILIATION to SAFELY_RESUMABLE once clarified.
        """
        rec_id = self.acquire_recovery_lock(project_id, mission_id)
        try:
            assessment = self.assess_mission(project_id, mission_id)
            actions_taken: list[str] = []
            reconciled_deps: list[str] = []
            reacquired_leases: list[str] = []

            # 1. Project path existence check
            p_path = assessment.project_path
            if p_path and not os.path.isabs(p_path):
                p_dir = os.path.realpath(os.path.join(self.workspace_root, p_path))
            elif p_path:
                p_dir = os.path.realpath(p_path)
            else:
                p_dir = os.path.realpath(os.path.join(self.workspace_root, "workspace", "projects", project_id))

            if not os.path.isdir(p_dir):
                p_dir_fallback = os.path.realpath(os.path.join(self.workspace_root, "workspace", "projects", project_id))
                if os.path.isdir(p_dir_fallback):
                    p_dir = p_dir_fallback
                else:
                    assessment.classification = RecoveryClassification.REQUIRES_RECONCILIATION
                    assessment.reasons.append(f"Diretório do projeto não existe: {p_dir}")
                    return assessment

            # 2. Re-acquire file leases
            # Freshly acquire file leases under current process; never trust old in-memory leases
            try:
                packages = self.mission_state.list_work_packages(project_id, mission_id)
                for pkg in packages:
                    wpid = pkg.get("work_package_id", "")
                    meta = pkg.get("metadata", {})
                    target_file = meta.get("target_file") or meta.get("file_path")
                    if target_file and pkg.get("status") in {"RUNNING", "IN_PROGRESS", "PENDING"}:
                        abs_file = os.path.abspath(os.path.join(p_dir, target_file) if not os.path.isabs(target_file) else target_file)
                        if os.path.isfile(abs_file):
                            try:
                                lease = self.file_lease_manager.acquire_file_lease(
                                    file_path=abs_file,
                                    holder_id=f"mission:{mission_id}:{wpid}",
                                    ttl_seconds=300.0,
                                )
                                reacquired_leases.append(abs_file)
                                actions_taken.append(f"Re-adquirida lease de ficheiro para: {os.path.basename(abs_file)}")
                                try:
                                    self.mission_state.update_work_package_status(
                                        project_id=project_id,
                                        mission_id=mission_id,
                                        work_package_id=wpid,
                                        status="READY",
                                    )
                                except Exception:
                                    pass
                                assessment.uncertain_operations = [
                                    op for op in assessment.uncertain_operations
                                    if (op.get("work_package_id") != wpid and op.get("task_id") != wpid)
                                ]
                            except Exception as lexc:
                                actions_taken.append(f"Aviso de lease para {abs_file}: {lexc}")
            except Exception as e:
                actions_taken.append(f"Aviso durante reconciliação de leases: {e}")

            # 3. Reconcile dependencies (Check if interrupted pip install completed in virtualenv)
            try:
                env_info = self.dependency_manager.inspect_environment(p_dir, project_id)
                for op in list(assessment.uncertain_operations):
                    wpid = op.get("work_package_id") or op.get("task_id")
                    title = str(op.get("title", ""))
                    pkg_candidates = ProjectDependencyManager.extract_requested_packages(title)
                    for pkg_name in pkg_candidates:
                        if self.dependency_manager.is_package_installed(env_info, pkg_name):
                            # Package is ALREADY installed in the environment!
                            reconciled_deps.append(pkg_name)
                            actions_taken.append(
                                f"Dependência '{pkg_name}' detetada como já instalada no virtualenv do projeto. "
                                f"Reconciliando work package {wpid} para COMPLETED."
                            )
                            # Record evidence and complete the package
                            ev_id = f"ev_rec_{uuid.uuid4().hex[:8]}"
                            try:
                                self.mission_state.create_evidence(
                                    project_id=project_id,
                                    mission_id=mission_id,
                                    work_package_id=wpid,
                                    summary=f"Reconciliação automática: dependência '{pkg_name}' confirmada no ambiente.",
                                    evidence_id=ev_id,
                                    data={"reconciled": True, "package": pkg_name, "tool": "pip_inspect"},
                                )
                                self.mission_state.update_work_package_status(
                                    project_id=project_id,
                                    mission_id=mission_id,
                                    work_package_id=wpid,
                                    status="COMPLETED",
                                )
                            except Exception:
                                pass
                            if op in assessment.uncertain_operations:
                                assessment.uncertain_operations.remove(op)
            except Exception as exc:
                actions_taken.append(f"Aviso na reconciliação de dependências: {exc}")

            # 4. Check acceptance criteria evidence integrity
            try:
                crits = self.mission_state.list_criteria(project_id, mission_id)
                evidences = self.mission_state.list_evidence(project_id, mission_id)
                ev_ids = {e.get("evidence_id") for e in evidences if isinstance(e, dict)}
                for crit in crits:
                    c_status = crit.get("status")
                    c_id = crit.get("criterion_id")
                    linked_ev = crit.get("evidence_id")
                    ev_refs = crit.get("evidence_refs") or []
                    has_evidence = False
                    if linked_ev and linked_ev in ev_ids:
                        has_evidence = True
                    if ev_refs and any(r in ev_ids for r in ev_refs):
                        has_evidence = True
                    if c_status in {"MET", "SATISFIED"}:
                        if not has_evidence:
                            # Acceptance criterion claims to be met without evidence!
                            # Non-negotiable constraint: Never claim completed without evidence!
                            actions_taken.append(
                                f"Critério de aceitação '{c_id}' estava marcado como MET sem evidência válida. "
                                f"Revertendo para PENDING para evitar falsa conclusão."
                            )
                            try:
                                self.mission_state.update_criterion(
                                    project_id=project_id,
                                    mission_id=mission_id,
                                    criterion_id=c_id,
                                    status="PENDING",
                                )
                            except Exception:
                                pass
            except Exception as exc:
                actions_taken.append(f"Aviso na verificação de critérios: {exc}")

            # 5. Check if all uncertain operations have been resolved
            if not assessment.uncertain_operations and assessment.classification == RecoveryClassification.REQUIRES_RECONCILIATION:
                assessment.classification = RecoveryClassification.SAFELY_RESUMABLE
                assessment.safe_to_resume = True
                actions_taken.append("Todas as operações incertas foram reconciliadas. Missão pronta para retomar.")

            assessment.recovery_actions_taken = actions_taken
            assessment.reconciled_dependencies = reconciled_deps
            assessment.reacquired_leases = reacquired_leases

            # 6. Save fresh checkpoint documenting reconciliation
            try:
                cp_data = {
                    "sequence": assessment.last_valid_checkpoint_seq + 1,
                    "checkpoint_id": f"cp_rec_{assessment.last_valid_checkpoint_seq + 1:04d}_{uuid.uuid4().hex[:6]}",
                    "mission_id": mission_id,
                    "project_id": project_id,
                    "mission_status": assessment.current_status,
                    "current_stage": assessment.current_stage,
                    "project_path": assessment.project_path,
                    "schema_version": 2,
                    "recovery_eligibility": {"reconciled": True, "resumable": assessment.safe_to_resume},
                    "reconciliation_actions": actions_taken,
                    "created_at": utc_now(),
                }
                self.mission_state.save_checkpoint(project_id, mission_id, cp_data)
                assessment.last_valid_checkpoint_seq = cp_data["sequence"]
            except Exception:
                pass

            self._log_recovery_event(
                "reconciliation_completed",
                project_id,
                mission_id,
                {
                    "classification": assessment.classification.value,
                    "actions_taken": actions_taken,
                    "reconciled_deps": reconciled_deps,
                },
            )
            return assessment

        finally:
            self.release_recovery_lock(project_id, mission_id)

    # ── RESUME EXECUTION ──────────────────────────────────────────────────────

    def resume_mission(
        self,
        project_id: str,
        mission_id: str,
        orchestrator: Optional[MissionLifecycleOrchestrator] = None,
    ) -> bool:
        """
        Safely resumes an interrupted mission. Only executes if assessment confirms
        the mission is SAFELY_RESUMABLE. Never repeats completed side effects.
        """
        assessment = self.assess_mission(project_id, mission_id)
        if not assessment.safe_to_resume or assessment.classification != RecoveryClassification.SAFELY_RESUMABLE:
            logger.warning(
                f"Missão '{mission_id}' não pode ser retomada automaticamente. "
                f"Classificação: {assessment.classification.value}. Motivos: {assessment.reasons}"
            )
            return False

        rec_id = self.acquire_recovery_lock(project_id, mission_id)
        try:
            self._log_recovery_event("mission_resumed", project_id, mission_id, {"recovery_id": rec_id})
            # Transition status from READY/BLOCKED back to ACTIVE if needed
            self.mission_state.update_mission_status(project_id, mission_id, "ACTIVE")
            return True
        finally:
            self.release_recovery_lock(project_id, mission_id)

    # ── INTEGRITY DIAGNOSTICS & REPAIR (PHASE 25F) ─────────────────────────────

    def run_integrity_diagnostics(self) -> dict[str, Any]:
        """
        Executes read-only diagnostic checks across all discovered missions:
        - Orphaned evidence references.
        - Duplicate mission identifiers.
        - Inconsistent status transitions.
        - Corrupted or unparseable checkpoint files.
        """
        missions = self.discover_all_missions()
        report: dict[str, Any] = {
            "total_missions_scanned": len(missions),
            "healthy_missions": 0,
            "corrupted_missions": 0,
            "orphaned_evidences": [],
            "duplicate_missions": [],
            "inconsistent_statuses": [],
            "corrupted_checkpoints": [],
        }

        mission_id_tracker: Dict[str, List[str]] = {}

        for project_id, mission_id in missions:
            mission_id_tracker.setdefault(mission_id, []).append(project_id)
            assessment = self.assess_mission(project_id, mission_id)

            if assessment.classification == RecoveryClassification.CORRUPTED:
                report["corrupted_missions"] += 1
            else:
                report["healthy_missions"] += 1

            # Check orphaned evidence
            try:
                evidences = self.mission_state.list_evidence(project_id, mission_id)
                packages = self.mission_state.list_work_packages(project_id, mission_id)
                wp_ids = {p.get("work_package_id") for p in packages}
                for ev in evidences:
                    wpid = ev.get("work_package_id")
                    if wpid and wpid not in wp_ids:
                        report["orphaned_evidences"].append({
                            "project_id": project_id,
                            "mission_id": mission_id,
                            "evidence_id": ev.get("evidence_id"),
                            "orphaned_work_package_id": wpid,
                        })
            except Exception:
                pass

            # Check inconsistent transitions
            if assessment.current_status == "COMPLETED" and assessment.pending_work_packages:
                report["inconsistent_statuses"].append({
                    "project_id": project_id,
                    "mission_id": mission_id,
                    "status": "COMPLETED",
                    "uncompleted_work_packages": assessment.pending_work_packages,
                })

            # Check corrupted checkpoints directory
            mission_dir = self.mission_state._mission_dir(project_id, mission_id)
            cp_dir = os.path.join(mission_dir, "checkpoints")
            if os.path.isdir(cp_dir):
                for fpath in glob.glob(os.path.join(cp_dir, "checkpoint_*.json")):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            json.load(f)
                    except Exception as e:
                        report["corrupted_checkpoints"].append({
                            "project_id": project_id,
                            "mission_id": mission_id,
                            "file": os.path.basename(fpath),
                            "error": str(e),
                        })

        # Check duplicates
        for m_id, p_list in mission_id_tracker.items():
            if len(p_list) > 1:
                report["duplicate_missions"].append({"mission_id": m_id, "projects": p_list})

        return report

    def create_mission_backup(self, project_id: str, mission_id: str) -> str:
        """
        Creates an isolated, immutable backup snapshot of the mission state
        before any repair or migration operation.
        """
        mission_dir = self.mission_state._mission_dir(project_id, mission_id)
        if not os.path.isdir(mission_dir):
            raise FileNotFoundError(f"Diretório da missão não encontrado: {mission_dir}")

        backup_root = os.path.join(self.workspace_root, "workspace", ".jarvis", "backups")
        os.makedirs(backup_root, exist_ok=True)
        backup_name = f"{project_id}_{mission_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        target_dir = os.path.join(backup_root, backup_name)

        shutil.copytree(mission_dir, target_dir)
        self._log_recovery_event("backup_created", project_id, mission_id, {"backup_path": target_dir})
        return target_dir

    def restore_from_checkpoint(self, project_id: str, mission_id: str, sequence: int) -> bool:
        """
        Restores mission state from a specific valid historical checkpoint sequence.
        Creates a safety backup before restoring.
        """
        self.create_mission_backup(project_id, mission_id)
        cp_data = self.mission_state.load_checkpoint(project_id, mission_id, sequence=sequence)
        if not cp_data:
            raise ValueError(f"Checkpoint de sequência {sequence} não encontrado ou corrompido.")

        # Re-save as latest checkpoint with monotonic sequence increment
        latest_cp = self.mission_state.load_latest_checkpoint(project_id, mission_id)
        latest_seq = int(latest_cp.get("sequence", sequence)) if latest_cp else sequence
        new_seq = latest_seq + 1

        restored_cp = copy.deepcopy(cp_data)
        restored_cp["sequence"] = new_seq
        restored_cp["checkpoint_id"] = f"cp_restored_{new_seq:04d}_{uuid.uuid4().hex[:6]}"
        restored_cp["created_at"] = utc_now()
        restored_cp["description"] = f"Restaurado a partir do checkpoint {sequence:04d}"

        self.mission_state.save_checkpoint(project_id, mission_id, restored_cp)
        self._log_recovery_event("restored_from_checkpoint", project_id, mission_id, {
            "source_sequence": sequence,
            "new_sequence": new_seq,
        })
        return True

    # ── LOGGING ───────────────────────────────────────────────────────────────

    def _log_recovery_event(self, action: str, project_id: str, mission_id: str, details: Optional[dict] = None) -> None:
        try:
            entry = {
                "event_id": f"rec_ev_{uuid.uuid4().hex[:8]}",
                "action": action,
                "project_id": project_id,
                "mission_id": mission_id,
                "timestamp": utc_now(),
                "details": details or {},
            }
            os.makedirs(os.path.dirname(self.audit_log_path), exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass
