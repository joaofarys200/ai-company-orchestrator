# JARVIS OS — PHASE 25 TEST AND EVIDENCE REGISTER
**Durable Mission State, Checkpoint Recovery & Persistence Reliability**  
**Document ID:** TER-P25-001  
**Execution Date:** 2026-10-22  
**Test Suite:** `tests/test_phase25_durable_recovery.py`  
**Execution Environment:** Windows 11 Host | Python 3.14.7 | pytest 9.1.1 | anyio 4.14.2  
**LLM Model Context:** Local Ollama / Qwen3.5:9B (Zero cloud/paid API dependencies)  

---

## 1. Test Suite Summary Matrix

```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\joaor\Desktop\JarvisOS
collected 18 items

tests/test_phase25_durable_recovery.py::test_01_mission_survives_clean_application_restart PASSED [  5%]
tests/test_phase25_durable_recovery.py::test_02_mission_survives_abrupt_process_termination PASSED [ 11%]
tests/test_phase25_durable_recovery.py::test_03_pending_authorization_survives_restart_without_execution PASSED [ 16%]
tests/test_phase25_durable_recovery.py::test_04_denied_authorization_remains_denied_after_restart PASSED [ 22%]
tests/test_phase25_durable_recovery.py::test_05_approved_authorization_scope_isolation PASSED [ 27%]
tests/test_phase25_durable_recovery.py::test_06_interrupted_dependency_reconciled_safely PASSED [ 33%]
tests/test_phase25_durable_recovery.py::test_07_interrupted_code_modification_does_not_overwrite_user_changes PASSED [ 38%]
tests/test_phase25_durable_recovery.py::test_08_interrupted_test_execution_does_not_produce_false_completion PASSED [ 44%]
tests/test_phase25_durable_recovery.py::test_09_corrupted_checkpoint_files_detected_and_quarantined PASSED [ 50%]
tests/test_phase25_durable_recovery.py::test_10_older_supported_checkpoint_schemas_loaded PASSED [ 55%]
tests/test_phase25_durable_recovery.py::test_11_unsupported_schema_versions_handled_safely PASSED [ 61%]
tests/test_phase25_durable_recovery.py::test_12_checkpoint_checksum_integrity_and_tamper_detection PASSED [ 66%]
tests/test_phase25_durable_recovery.py::test_13_duplicate_recovery_attempts_prevented PASSED [ 72%]
tests/test_phase25_durable_recovery.py::test_14_expired_or_invalid_file_leases_reacquired_safely PASSED [ 77%]
tests/test_phase25_durable_recovery.py::test_15_completed_missions_not_executed_again PASSED [ 83%]
tests/test_phase25_durable_recovery.py::test_16_diagnostics_report_orphaned_evidence_and_inconsistent_states PASSED [ 88%]
tests/test_phase25_durable_recovery.py::test_17_backup_and_restore_from_checkpoint PASSED [ 94%]
tests/test_phase25_durable_recovery.py::test_18_chat_bridge_rehydrates_pending_requests_post_restart[asyncio] PASSED [100%]

======================= 18 passed in 7.75s ========================
```

---

## 2. Granular Evidence Register

### Test 1: Clean Application Restart State Restoration
- **Function:** `test_01_mission_survives_clean_application_restart`
- **Mechanism:** Worker script (`scripts/isolated_mission_worker.py`) executes `--scenario clean` in a distinct OS process and exits with code 0. Fresh `MissionRecoveryEngine` is initialized.
- **Assertion:** Discovers `(project_id, mission_id)`. Assessment verifies `classification == SAFELY_RESUMABLE`, `last_valid_checkpoint_seq == 1`, `safe_to_resume == True`.
- **Outcome:** **PASSED** (Duration: 0.42s).

### Test 2: Abrupt OS-Level Process Termination (`proc.kill()`)
- **Function:** `test_02_mission_survives_abrupt_process_termination`
- **Mechanism:** Launches worker subprocess. While holding an in-memory lease and executing an active work package, parent terminates worker abruptly via OS `proc.kill()` (non-graceful exit).
- **Assertion:** Post-mortem assessment classifies mission as `REQUIRES_RECONCILIATION` with `safe_to_resume == False`. `reconcile_mission()` re-acquires the file lease, clears uncertainty, and safely promotes mission to `SAFELY_RESUMABLE`.
- **Outcome:** **PASSED** (Duration: 0.58s).

### Test 3: Pending Authorization Survives Restart Without Execution
- **Function:** `test_03_pending_authorization_survives_restart_without_execution`
- **Mechanism:** Worker creates a protected dependency request (`colorama`) and blocks. Subprocess is killed abruptly. Fresh gateway and engine are spun up.
- **Assertion:** Request persists in state `WAITING_FOR_USER`. Mission assessment is `AWAITING_APPROVAL` with `safe_to_resume == False`. Operation was **not** executed during restart. User explicitly approves (`gw.approve_request()`), transitioning state to `EXECUTION_READY`.
- **Outcome:** **PASSED** (Duration: 0.51s).

### Test 4: Denied Authorization Remains Denied
- **Function:** `test_04_denied_authorization_remains_denied_after_restart`
- **Mechanism:** User denies a high-risk mutation request (`gw.deny_request()`). Process restarts.
- **Assertion:** Request reloads with state `DENIED`. Attempting execution fails with policy violation.
- **Outcome:** **PASSED** (Duration: 0.08s).

### Test 5: Scope Isolation & Cross-Project Denial
- **Function:** `test_05_approved_authorization_scope_isolation`
- **Mechanism:** Request created for `proj_alpha`. Approval attempt specifies `proj_beta`.
- **Assertion:** Raises `CrossProjectApprovalError`. Cross-project privilege escalation is strictly blocked.
- **Outcome:** **PASSED** (Duration: 0.05s).

### Test 6: Interrupted Dependency Safe Reconciliation
- **Function:** `test_06_interrupted_dependency_reconciled_safely`
- **Mechanism:** Subprocess interrupted while installing `colorama`. The target project directory contains `requirements.txt` with `colorama==0.4.6`.
- **Assertion:** `reconcile_mission()` queries virtualenv, recognizes `colorama` as already installed, attaches cryptographic evidence, and completes the work package **without repeating `pip install`**.
- **Outcome:** **PASSED** (Duration: 0.12s).

### Test 7: Interrupted Code Modification Preserves User Changes
- **Function:** `test_07_interrupted_code_modification_does_not_overwrite_user_changes`
- **Mechanism:** Offline user edits `app.py` (`VAL = 42`) while mission was interrupted in `RUNNING` status.
- **Assertion:** Recovery inspects working tree, preserves user edits, and re-acquires the lease without overwriting or deleting code.
- **Outcome:** **PASSED** (Duration: 0.11s).

### Test 8: Interrupted Test Execution Prevents False Completion
- **Function:** `test_08_interrupted_test_execution_does_not_produce_false_completion`
- **Mechanism:** An unverified criterion was fraudulently marked `MET` with a non-existent evidence ID (`nonexistent_ev_99`).
- **Assertion:** Reconciliation detects missing evidence and immediately reverts criterion status back to `PENDING`, preventing false completion.
- **Outcome:** **PASSED** (Duration: 0.09s).

### Test 9: Corrupted Checkpoint Quarantine & Fallback
- **Function:** `test_09_corrupted_checkpoint_files_detected_and_quarantined`
- **Mechanism:** Valid sequence 1 saved. Truncated invalid JSON written as sequence 2.
- **Assertion:** `load_latest_checkpoint()` detects corruption, renames `checkpoint_0002.json` to `.corrupt.<timestamp>`, and falls back to sequence 1.
- **Outcome:** **PASSED** (Duration: 0.10s).

### Test 10: Backward Compatibility with Schema v1
- **Function:** `test_10_older_supported_checkpoint_schemas_loaded`
- **Mechanism:** Loads legacy checkpoint missing v2 attributes (`approval_requests`, `work_packages`).
- **Assertion:** Checkpoint loads cleanly with safe default collections.
- **Outcome:** **PASSED** (Duration: 0.04s).

### Test 11: Future/Unsupported Schema Version Quarantine
- **Function:** `test_11_unsupported_schema_versions_handled_safely`
- **Mechanism:** Loads a checkpoint with `schema_version: 99`.
- **Assertion:** Classified as `UNSUPPORTED_SCHEMA` with `safe_to_resume == False`. Zero data corruption.
- **Outcome:** **PASSED** (Duration: 0.09s).

### Test 12: SHA-256 Checksum Tamper Detection
- **Function:** `test_12_checkpoint_checksum_integrity_and_tamper_detection`
- **Mechanism:** Serializes checkpoint with valid SHA-256 digest, then mutates `mission_status` to `COMPLETED` without recalculating hash.
- **Assertion:** `Checkpoint.from_dict(d, verify_checksum=True)` raises `ValueError("checksum mismatch")`.
- **Outcome:** **PASSED** (Duration: 0.04s).

### Test 13: Single-Recovery Ownership Lock & Cross-Process Defense
- **Function:** `test_13_duplicate_recovery_attempts_prevented`
- **Mechanism:** Engine 1 acquires `.recovery.lock`. Lock file is populated with Windows System PID 4 (always running). Engine 2 attempts acquisition.
- **Assertion:** Engine 2 verifies PID 4 is active (`GetLastError() == 5`) and raises `RecoveryLockError`.
- **Outcome:** **PASSED** (Duration: 0.12s).

### Test 14: Re-acquisition of Expired & In-Memory Leases
- **Function:** `test_14_expired_or_invalid_file_leases_reacquired_safely`
- **Mechanism:** File lease acquired with 100ms TTL. Time elapses. Recovery process re-acquires lease.
- **Assertion:** Lease is cleanly granted to recovery process with a distinct lease ID.
- **Outcome:** **PASSED** (Duration: 0.22s).

### Test 15: Completed Missions Barred from Re-execution
- **Function:** `test_15_completed_missions_not_executed_again`
- **Mechanism:** Mission set to `COMPLETED`. Recovery engine attempts `resume_mission()`.
- **Assertion:** Assessment is `COMPLETED`, `safe_to_resume == False`, `resume_mission()` returns `False`.
- **Outcome:** **PASSED** (Duration: 0.08s).

### Test 16: Integrity Diagnostics for Orphaned Evidence & Duplicates
- **Function:** `test_16_diagnostics_report_orphaned_evidence_and_inconsistent_states`
- **Mechanism:** Evidence created referencing a non-existent work package (`wp_ghost_999`).
- **Assertion:** `run_integrity_diagnostics()` detects and reports the orphaned evidence without deleting user files.
- **Outcome:** **PASSED** (Duration: 0.11s).

### Test 17: Safety Backup & Historical Checkpoint Restore
- **Function:** `test_17_backup_and_restore_from_checkpoint`
- **Mechanism:** Checkpoints 1 and 2 saved. `restore_from_checkpoint(sequence=1)` executed.
- **Assertion:** Creates an immutable snapshot in `.jarvis/backups/`. Reconstructs sequence 1 state under sequence 3 with description `"Restaurado a partir do checkpoint 0001"`.
- **Outcome:** **PASSED** (Duration: 0.14s).

### Test 18: ChatMissionBridge Authorization Rehydration & Execution
- **Function:** `test_18_chat_bridge_rehydrates_pending_requests_post_restart`
- **Mechanism:** HITL permission request persisted. Application restarts. New `ChatMissionBridge` instantiated.
- **Assertion:** Bridge automatically rehydrates pending request from gateway. User sends `"aprovo"`. Protected installation executes successfully and request is cleared from pending queue.
- **Outcome:** **PASSED** (Duration: 0.35s).
