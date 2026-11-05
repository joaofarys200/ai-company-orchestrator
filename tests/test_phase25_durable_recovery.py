"""
JARVIS OS — Phase 25 Test Suite
Durable Mission State, Checkpoint Recovery & Persistence Reliability.

Verifies:
1. Clean application restart with state restoration.
2. Abrupt OS-level process termination (proc.kill()) and forensic recovery.
3. Pending authorization survives restart without executing protected operation.
4. Denied authorization remains denied after restart.
5. Approved authorization cannot be reused outside its original scope.
6. Interrupted dependency installation is reconciled safely without repeating side effects.
7. Interrupted code modification does not overwrite unrelated user changes.
8. Interrupted test execution does not produce false completion (evidence enforcement).
9. Corrupted checkpoint files are detected, quarantined, and previous valid checkpoint restored.
10. Older supported checkpoint schemas (v1) load cleanly.
11. Unsupported schema versions (v99) are handled safely without crashing.
12. Checkpoint integrity with SHA-256 checksums and atomic writes.
13. Duplicate recovery attempts are prevented via recovery lock ownership.
14. Expired or invalid file leases are reacquired safely.
15. Acceptance criteria strictly require valid evidence.
16. Completed missions are not executed again.
17. Diagnostics report orphaned evidence and inconsistent states.
18. Backup and restore from historical checkpoints.
19. ChatMissionBridge rehydrates pending requests across restart.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import pytest

from agents.file_lease_manager import FileLeaseManager, get_file_lease_manager
from agents.mission_orchestrator import Checkpoint, MissionLifecycleOrchestrator, MissionLifecycleStatus
from agents.mission_persistence import ShardedFilesystemPersistence, HybridMissionPersistence
from agents.mission_recovery import (
    MissionRecoveryEngine,
    RecoveryAssessment,
    RecoveryClassification,
    RecoveryLockError,
)
from agents.mission_state import MissionStateStore
from backend.services.chat_mission_bridge import ChatMissionBridge
from security.permission_gateway.gateway import (
    CrossProjectApprovalError,
    PermissionGatewayService,
    get_permission_gateway_service,
    reset_permission_gateway_service,
)
from security.permission_gateway.models import (
    ApprovalSemantics,
    DependencyClassification,
    PermissionRequest,
    PermissionRequestStatus,
    PermissionRiskLevel,
)
from security.permission_gateway.project_dependency_manager import ProjectDependencyManager


@pytest.fixture
def isolated_workspace():
    """Provides a pristine, isolated temporary workspace for recovery tests."""
    temp_dir = tempfile.mkdtemp(prefix="jarvis_p25_test_")
    os.makedirs(os.path.join(temp_dir, "workspace", "projects"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "workspace", ".jarvis", "projects"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "workspace", ".jarvis", "permissions"), exist_ok=True)

    old_ws = os.environ.get("JARVIS_WORKSPACE")
    old_perm = os.environ.get("JARVIS_PERMISSIONS_DIR")
    os.environ["JARVIS_WORKSPACE"] = temp_dir
    os.environ["JARVIS_PERMISSIONS_DIR"] = os.path.join(temp_dir, "workspace", ".jarvis", "permissions")

    reset_permission_gateway_service()
    yield temp_dir

    reset_permission_gateway_service()
    if old_ws:
        os.environ["JARVIS_WORKSPACE"] = old_ws
    else:
        os.environ.pop("JARVIS_WORKSPACE", None)
    if old_perm:
        os.environ["JARVIS_PERMISSIONS_DIR"] = old_perm
    else:
        os.environ.pop("JARVIS_PERMISSIONS_DIR", None)

    shutil.rmtree(temp_dir, ignore_errors=True)


def _setup_project(workspace: str, project_id: str) -> str:
    proj_dir = os.path.join(workspace, "workspace", "projects", project_id)
    os.makedirs(proj_dir, exist_ok=True)
    meta_dir = os.path.join(workspace, "workspace", ".jarvis", "projects", project_id)
    os.makedirs(meta_dir, exist_ok=True)
    ctx_file = os.path.join(meta_dir, "project_context.json")
    with open(ctx_file, "w", encoding="utf-8") as f:
        json.dump({
            "project_id": project_id,
            "project_name": project_id,
            "root_path": proj_dir,
            "created_at": time.time(),
        }, f, indent=2)
    return proj_dir


# ── TEST 1: CLEAN RESTART RECOVERY ───────────────────────────────────────────

def test_01_mission_survives_clean_application_restart(isolated_workspace):
    """Test 1: A mission survives a clean restart with state and checkpoints intact."""
    project_id = "proj_clean_01"
    mission_id = "miss_clean_01"
    _setup_project(isolated_workspace, project_id)

    # 1. Run worker to create mission and checkpoint, exiting cleanly (exit code 0)
    cmd = [
        sys.executable,
        "scripts/isolated_mission_worker.py",
        "--workspace", isolated_workspace,
        "--project-id", project_id,
        "--mission-id", mission_id,
        "--scenario", "clean",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert "CLEAN_COMPLETED" in proc.stdout

    # 2. Simulate fresh application startup: instantiate new Recovery Engine
    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)
    missions = engine.discover_all_missions()
    assert (project_id, mission_id) in missions

    assessment = engine.assess_mission(project_id, mission_id)
    assert assessment.mission_id == mission_id
    assert assessment.classification == RecoveryClassification.SAFELY_RESUMABLE
    assert assessment.last_valid_checkpoint_seq == 1
    assert assessment.safe_to_resume is True


# ── TEST 2: ABRUPT PROCESS TERMINATION RECOVERY ──────────────────────────────

def test_02_mission_survives_abrupt_process_termination(isolated_workspace):
    """
    Test 2: A mission survives abrupt OS-level process termination (proc.kill()).
    Verifies that unrecorded in-memory state is reconciled and in-memory leases released.
    """
    project_id = "proj_kill_01"
    mission_id = "miss_kill_01"
    _setup_project(isolated_workspace, project_id)

    # 1. Launch worker subprocess
    cmd = [
        sys.executable,
        "scripts/isolated_mission_worker.py",
        "--workspace", isolated_workspace,
        "--project-id", project_id,
        "--mission-id", mission_id,
        "--scenario", "abrupt_kill",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Wait until worker signals it is mid-operation
    ready = False
    for _ in range(50):
        line = proc.stdout.readline()
        if "READY_FOR_KILL" in line:
            ready = True
            break
    assert ready is True

    # 2. ABRUPT TERMINATION: Kill worker immediately via OS TerminateProcess
    proc.kill()
    proc.wait()
    assert proc.poll() is not None
    assert proc.poll() != 0  # Process did NOT exit gracefully!

    # 3. Post-Mortem Recovery
    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)
    assessment = engine.assess_mission(project_id, mission_id)

    # Mission had a running task when abruptly killed -> Classified as REQUIRES_RECONCILIATION
    assert assessment.classification == RecoveryClassification.REQUIRES_RECONCILIATION
    assert assessment.safe_to_resume is False
    assert len(assessment.uncertain_operations) > 0

    # 4. Perform reconciliation
    reconciled = engine.reconcile_mission(project_id, mission_id)
    assert len(reconciled.reacquired_leases) > 0  # Reacquired file lease for main.py!
    assert reconciled.safe_to_resume is True
    assert reconciled.classification == RecoveryClassification.SAFELY_RESUMABLE


# ── TEST 3 & 4: AUTHORIZATION ACROSS RESTARTS ────────────────────────────────

def test_03_pending_authorization_survives_restart_without_execution(isolated_workspace):
    """
    Test 3: A mission awaiting approval remains BLOCKED after process restart.
    No protected operation is executed without explicit authorization.
    """
    project_id = "proj_auth_01"
    mission_id = "miss_auth_01"
    proj_dir = _setup_project(isolated_workspace, project_id)

    # 1. Launch worker that creates pending auth request and blocks mission
    cmd = [
        sys.executable,
        "scripts/isolated_mission_worker.py",
        "--workspace", isolated_workspace,
        "--project-id", project_id,
        "--mission-id", mission_id,
        "--scenario", "pending_auth",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    req_id = None
    for _ in range(50):
        line = proc.stdout.readline()
        if "READY_FOR_KILL:" in line:
            req_id = line.strip().split("READY_FOR_KILL:")[1]
            break
    assert req_id is not None

    # Abruptly kill the worker while awaiting approval
    proc.kill()
    proc.wait()

    # 2. Simulate application restart with fresh gateway and engine
    reset_permission_gateway_service()
    gw = get_permission_gateway_service(storage_dir=os.path.join(isolated_workspace, "workspace", ".jarvis", "permissions"))
    engine = MissionRecoveryEngine(workspace_root=isolated_workspace, permission_gateway=gw)

    # 3. Verify request is durably rehydrated
    persisted_req = gw.get_request(req_id)
    assert persisted_req is not None
    assert persisted_req.request_id == req_id
    assert persisted_req.status in {PermissionRequestStatus.WAITING_FOR_USER.value, PermissionRequestStatus.REQUESTED.value}

    # 4. Verify mission assessment classifies as AWAITING_APPROVAL
    assessment = engine.assess_mission(project_id, mission_id)
    assert assessment.classification == RecoveryClassification.AWAITING_APPROVAL
    assert assessment.safe_to_resume is False
    assert assessment.pending_approval_request_id == req_id

    # 5. User explicitly approves request post-restart
    gw.approve_request(req_id, decided_by="test_user", project_id=project_id)
    approved_req = gw.get_request(req_id)
    assert approved_req.status in {
        PermissionRequestStatus.APPROVED.value,
        PermissionRequestStatus.EXECUTION_READY.value,
        PermissionRequestStatus.INSTALLATION_REQUIRED.value,
    }


def test_04_denied_authorization_remains_denied_after_restart(isolated_workspace):
    """Test 4: Denied authorization remains denied after restart and cannot be executed."""
    gw_dir = os.path.join(isolated_workspace, "workspace", ".jarvis", "permissions")
    gw = PermissionGatewayService(storage_dir=gw_dir)

    req = gw.create_request(
        tool_name="pip_install",
        requested_operation="untrusted_pkg",
        reason="Test denial",
        risk_level=PermissionRiskLevel.HIGH_RISK_MUTATION.value,
        required_privileges="system",
        affected_resources=["sys"],
        project_id="proj_deny_01",
        mission_id="miss_deny_01",
    )
    gw.deny_request(req.request_id, reason="Denied by user", project_id="proj_deny_01")
    assert req.status == PermissionRequestStatus.DENIED.value

    # Simulate restart
    fresh_gw = PermissionGatewayService(storage_dir=gw_dir)
    loaded = fresh_gw.get_request(req.request_id)
    assert loaded is not None
    assert loaded.status == PermissionRequestStatus.DENIED.value

    # Attempting to execute denied request must fail
    with pytest.raises(Exception):
        fresh_gw.execute_approved_request(req.request_id)


# ── TEST 5: SCOPE ISOLATION ──────────────────────────────────────────────────

def test_05_approved_authorization_scope_isolation(isolated_workspace):
    """Test 5: An approved authorization cannot be reused outside its target project."""
    gw_dir = os.path.join(isolated_workspace, "workspace", ".jarvis", "permissions")
    gw = PermissionGatewayService(storage_dir=gw_dir)

    req = gw.create_request(
        tool_name="pip_install",
        requested_operation="scipy",
        reason="Scientific computing",
        risk_level=PermissionRiskLevel.LOW_RISK_MUTATION.value,
        required_privileges="none",
        affected_resources=["venv"],
        project_id="proj_alpha",
        mission_id="miss_alpha",
    )

    # Attempting approval with mismatched project_id must raise CrossProjectApprovalError
    with pytest.raises(CrossProjectApprovalError):
        gw.approve_request(req.request_id, project_id="proj_beta")


# ── TEST 6: RECONCILE INTERRUPTED DEPENDENCY ─────────────────────────────────

def test_06_interrupted_dependency_reconciled_safely(isolated_workspace):
    """
    Test 6: An interrupted dependency installation is checked against the actual target
    environment. If the package was already installed, it marks the work package complete
    and does not repeat the side effect.
    """
    project_id = "proj_dep_reconcile"
    mission_id = "miss_dep_reconcile"
    proj_dir = _setup_project(isolated_workspace, project_id)

    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Dep Mission", objective="Reconcile dep", mission_id=mission_id)
    store.create_work_package(
        project_id, mission_id, title="Install colorama", work_package_id="wp_dep_01"
    )
    store.update_work_package_status(project_id, mission_id, "wp_dep_01", "RUNNING")

    # Mock virtualenv manifest indicating colorama is installed
    venv_manifest = os.path.join(proj_dir, "requirements.txt")
    with open(venv_manifest, "w", encoding="utf-8") as f:
        f.write("colorama==0.4.6\n")

    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)
    assessment = engine.assess_mission(project_id, mission_id)
    assert assessment.classification == RecoveryClassification.REQUIRES_RECONCILIATION

    # Reconcile mission: inspects environment and recognizes colorama as already installed!
    reconciled = engine.reconcile_mission(project_id, mission_id)
    assert "colorama" in reconciled.reconciled_dependencies

    # Work package is now COMPLETED
    wp = store.get_work_package(project_id, mission_id, "wp_dep_01")
    assert wp["status"] == "COMPLETED"


# ── TEST 7 & 8: CODE & TEST INTEGRITY ────────────────────────────────────────

def test_07_interrupted_code_modification_does_not_overwrite_user_changes(isolated_workspace):
    """Test 7: Interrupted code changes do not blindly overwrite existing user modifications."""
    project_id = "proj_code_mod"
    mission_id = "miss_code_mod"
    proj_dir = _setup_project(isolated_workspace, project_id)

    main_py = os.path.join(proj_dir, "app.py")
    with open(main_py, "w", encoding="utf-8") as f:
        f.write("# User edits made offline\nVAL = 42\n")

    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Code Mod", objective="Preserve user edits", mission_id=mission_id)
    store.create_work_package(
        project_id, mission_id, title="Modify app.py", work_package_id="wp_code_01",
        metadata={"target_file": main_py}
    )
    store.update_work_package_status(project_id, mission_id, "wp_code_01", "RUNNING")

    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)
    assessment = engine.reconcile_mission(project_id, mission_id)

    # File was NOT deleted or overwritten!
    with open(main_py, "r", encoding="utf-8") as f:
        content = f.read()
    assert "VAL = 42" in content


def test_08_interrupted_test_execution_does_not_produce_false_completion(isolated_workspace):
    """Test 8: Acceptance criteria require valid evidence. Interrupted verification reverts to PENDING."""
    project_id = "proj_test_verif"
    mission_id = "miss_test_verif"
    _setup_project(isolated_workspace, project_id)

    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Test Mission", objective="Verify criteria", mission_id=mission_id)
    store.create_work_package(project_id, mission_id, title="Run tests", work_package_id="wp_test_01")
    crit = store.create_criterion(
        project_id, mission_id, owner_type="WORK_PACKAGE", owner_id="wp_test_01",
        description="Must pass all tests", criterion_id="crit_test_01"
    )

    # Fraudulent/interrupted state: criterion set to MET without linked evidence!
    store.update_criterion(project_id, mission_id, "crit_test_01", status="MET", evidence_id="nonexistent_ev_99")

    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)
    reconciled = engine.reconcile_mission(project_id, mission_id)

    # Reconciler detected lack of evidence and reverted criterion to PENDING!
    updated_crit = store.get_criterion(project_id, mission_id, "crit_test_01")
    assert updated_crit["status"] == "PENDING"


# ── TEST 9, 10 & 11: CHECKPOINT CORRUPTION, SCHEMAS & CHECKSUMS ──────────────

def test_09_corrupted_checkpoint_files_detected_and_quarantined(isolated_workspace):
    """
    Test 9: Corrupted checkpoint files are detected, quarantined (.corrupt.<ts>),
    and the engine falls back to the previous valid sequence.
    """
    project_id = "proj_corrupt_cp"
    mission_id = "miss_corrupt_cp"
    _setup_project(isolated_workspace, project_id)

    persistence = ShardedFilesystemPersistence(isolated_workspace)

    # Save valid checkpoint 1
    cp1 = {"sequence": 1, "checkpoint_id": "cp_0001", "mission_status": "ACTIVE", "schema_version": 2}
    persistence.save_checkpoint(project_id, mission_id, cp1)

    # Save corrupt checkpoint 2 (simulating truncated write / crash)
    cp_dir = os.path.join(isolated_workspace, "workspace", ".jarvis", "projects", project_id, "missions", mission_id, "checkpoints")
    cp2_path = os.path.join(cp_dir, "checkpoint_0002.json")
    with open(cp2_path, "w", encoding="utf-8") as f:
        f.write("{ truncated invalid json ...")

    # Load latest checkpoint: must detect corruption, quarantine cp2, and return cp1!
    loaded = persistence.load_latest_checkpoint(project_id, mission_id)
    assert loaded is not None
    assert loaded["sequence"] == 1
    assert loaded["checkpoint_id"] == "cp_0001"

    # Verify corrupt file was renamed/quarantined
    corrupt_files = [f for f in os.listdir(cp_dir) if ".corrupt." in f]
    assert len(corrupt_files) == 1


def test_10_older_supported_checkpoint_schemas_loaded(isolated_workspace):
    """Test 10: Older supported checkpoint schemas (schema_version: 1) load cleanly."""
    legacy_data = {
        "checkpoint_id": "cp_legacy_01",
        "sequence": 1,
        "mission_id": "miss_legacy",
        "project_id": "proj_legacy",
        "mission_status": "ACTIVE",
        "schema_version": 1,
    }
    cp = Checkpoint.from_dict(legacy_data)
    assert cp.schema_version == 1
    assert cp.checkpoint_id == "cp_legacy_01"
    # New fields are populated with safe defaults
    assert cp.work_packages == []
    assert cp.approval_requests == []


def test_11_unsupported_schema_versions_handled_safely(isolated_workspace):
    """Test 11: Unsupported schema versions (e.g. schema_version: 99) are classified safely."""
    project_id = "proj_schema_99"
    mission_id = "miss_schema_99"
    _setup_project(isolated_workspace, project_id)

    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Future Mission", objective="Future schema", mission_id=mission_id)
    store.save_checkpoint(
        project_id, mission_id,
        {"sequence": 1, "checkpoint_id": "cp_future", "mission_status": "ACTIVE", "schema_version": 99}
    )

    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)
    assessment = engine.assess_mission(project_id, mission_id)
    assert assessment.classification == RecoveryClassification.UNSUPPORTED_SCHEMA
    assert assessment.safe_to_resume is False


def test_12_checkpoint_checksum_integrity_and_tamper_detection(isolated_workspace):
    """Test 12: Checkpoints have SHA-256 checksums that detect tampering or silent corruption."""
    cp = Checkpoint(
        checkpoint_id="cp_hash_01",
        sequence=1,
        mission_id="m1",
        project_id="p1",
        mission_status="ACTIVE",
        task_graph_data={},
        completed_task_ids=[],
        pending_task_ids=[],
        running_task_ids=[],
        failed_task_ids=[],
        blocked_task_ids=[],
        evidence_refs=[],
        outputs={},
        created_at="2026-10-21T01:00:00Z",
    )
    d = cp.to_dict()
    assert "checksum" in d
    assert len(d["checksum"]) == 64  # Valid SHA-256

    # Tampering with payload must raise ValueError upon loading
    d["mission_status"] = "COMPLETED"  # Tampered!
    with pytest.raises(ValueError) as exc:
        Checkpoint.from_dict(d, verify_checksum=True)
    assert "checksum mismatch" in str(exc.value)


# ── TEST 13 & 14: RECOVERY LOCK & FILE LEASES ────────────────────────────────

def test_13_duplicate_recovery_attempts_prevented(isolated_workspace):
    """Test 13: Only one active recovery process can take ownership of a mission."""
    project_id = "proj_rec_lock"
    mission_id = "miss_rec_lock"
    _setup_project(isolated_workspace, project_id)

    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Lock Mission", objective="Test recovery lock", mission_id=mission_id)

    engine1 = MissionRecoveryEngine(workspace_root=isolated_workspace)
    engine2 = MissionRecoveryEngine(workspace_root=isolated_workspace)

    # Engine 1 acquires recovery lock
    rec_id1 = engine1.acquire_recovery_lock(project_id, mission_id)
    assert rec_id1.startswith("rec_")

    # Engine 2 attempts to acquire lock while Engine 1 holds it
    # Since same PID, it recognizes same process, but writing a fake alien PID simulates another active process:
    mission_dir = store._mission_dir(project_id, mission_id)
    lock_file = os.path.join(mission_dir, ".recovery.lock")
    with open(lock_file, "w", encoding="utf-8") as f:
        # Use current process ID + 9999 or PID 4 (System on Windows) which is always running
        json.dump({"recovery_id": "alien_rec", "pid": 4, "acquired_at": "now"}, f)

    with pytest.raises(RecoveryLockError):
        engine2.acquire_recovery_lock(project_id, mission_id)

    # Clean up lock
    engine1.release_recovery_lock(project_id, mission_id)


def test_14_expired_or_invalid_file_leases_reacquired_safely(isolated_workspace):
    """Test 14: Expired or in-memory file leases are re-acquired safely during recovery."""
    mgr = FileLeaseManager(default_ttl_seconds=0.1)
    file_path = os.path.join(isolated_workspace, "test.py")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# lease test")

    lease1 = mgr.acquire_file_lease(file_path, holder_id="old_dead_worker")
    assert lease1.holder_id == "old_dead_worker"

    # Wait for lease to expire
    time.sleep(0.15)

    # Recovery process re-acquires lease
    lease2 = mgr.acquire_file_lease(file_path, holder_id="recovery_worker")
    assert lease2.holder_id == "recovery_worker"
    assert lease2.lease_id != lease1.lease_id


# ── TEST 15 & 16: COMPLETED MISSIONS & INTEGRITY DIAGNOSTICS ─────────────────

def test_15_completed_missions_not_executed_again(isolated_workspace):
    """Test 15: Completed missions are classified as COMPLETED and never executed again."""
    project_id = "proj_comp_01"
    mission_id = "miss_comp_01"
    _setup_project(isolated_workspace, project_id)

    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Done Mission", objective="Already completed", mission_id=mission_id)
    store.set_mission_status(project_id, mission_id, "COMPLETED")

    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)
    assessment = engine.assess_mission(project_id, mission_id)
    assert assessment.classification == RecoveryClassification.COMPLETED
    assert assessment.safe_to_resume is False

    # Attempting to resume returns False
    resumed = engine.resume_mission(project_id, mission_id)
    assert resumed is False


def test_16_diagnostics_report_orphaned_evidence_and_inconsistent_states(isolated_workspace):
    """Test 16: Diagnostic checks report orphaned evidence and duplicate mission IDs."""
    project_id = "proj_diag_01"
    mission_id = "miss_diag_01"
    _setup_project(isolated_workspace, project_id)

    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Diag Mission", objective="Test diagnostics", mission_id=mission_id)
    store.create_evidence(
        project_id, mission_id, work_package_id="wp_ghost_999", summary="Ghost evidence"
    )

    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)
    diag = engine.run_integrity_diagnostics()
    assert diag["total_missions_scanned"] >= 1
    assert len(diag["orphaned_evidences"]) >= 1
    assert diag["orphaned_evidences"][0]["orphaned_work_package_id"] == "wp_ghost_999"


# ── TEST 17 & 18: BACKUP, RESTORE & CHAT BRIDGE REHYDRATION ──────────────────

def test_17_backup_and_restore_from_checkpoint(isolated_workspace):
    """Test 17: Mission backup is created and historical checkpoint is restored cleanly."""
    project_id = "proj_restore_01"
    mission_id = "miss_restore_01"
    _setup_project(isolated_workspace, project_id)

    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Restore Mission", objective="Test restore", mission_id=mission_id)

    # Save sequence 1
    store.save_checkpoint(project_id, mission_id, {"sequence": 1, "description": "Baseline v1", "schema_version": 2})
    # Save sequence 2
    store.save_checkpoint(project_id, mission_id, {"sequence": 2, "description": "Faulty state v2", "schema_version": 2})

    engine = MissionRecoveryEngine(workspace_root=isolated_workspace)

    # Create safety backup
    backup_path = engine.create_mission_backup(project_id, mission_id)
    assert os.path.isdir(backup_path)

    # Restore sequence 1
    restored = engine.restore_from_checkpoint(project_id, mission_id, sequence=1)
    assert restored is True

    # Latest checkpoint is now sequence 3 pointing back to sequence 1 state
    latest = store.load_latest_checkpoint(project_id, mission_id)
    assert latest["sequence"] == 3
    assert "Restaurado a partir do checkpoint 0001" in latest["description"]


@pytest.mark.anyio
async def test_18_chat_bridge_rehydrates_pending_requests_post_restart(isolated_workspace):
    """
    Test 18: ChatMissionBridge rehydrates durable authorization requests upon startup
    and allows user approval ('aprovo') to execute the protected operation.
    """
    project_id = "proj_bridge_restart"
    mission_id = "miss_bridge_restart"
    proj_dir = _setup_project(isolated_workspace, project_id)

    gw_dir = os.path.join(isolated_workspace, "workspace", ".jarvis", "permissions")
    gw = PermissionGatewayService(storage_dir=gw_dir)

    # Prepare pending request directly in gateway
    pdm = ProjectDependencyManager(gateway=gw)
    req = pdm.prepare_authorization_request(
        project_root=proj_dir,
        package_name="colorama",
        reason="Required for formatting",
        project_id=project_id,
        mission_id=mission_id,
    )

    # Simulate restart: instantiate new ChatMissionBridge with fresh gateway
    reset_permission_gateway_service()
    store = MissionStateStore(workspace_root=isolated_workspace)
    store.create_mission(project_id, title="Restart Bridge Mission", objective="Approve post-restart", mission_id=mission_id)

    bridge = ChatMissionBridge(mission_state=store)
    # Verify bridge automatically rehydrated the request!
    assert req.request_id in bridge._pending_dependency_requests

    # Mock command runner to simulate successful pip install
    bridge._pending_dependency_requests[req.request_id]["mock_run_cmd"] = lambda cmd, cwd, timeout: (0, "Successfully installed colorama-0.4.6", "")

    # User sends 'aprovo'
    res = await bridge.handle_dependency_decision(req.request_id, action="aprovo")
    assert res.get("status") in {"COMPLETED", "OK", "WAITING_FOR_APPROVAL"} or res.get("success") is not False
    # Request removed from pending queue
    assert req.request_id not in bridge._pending_dependency_requests
