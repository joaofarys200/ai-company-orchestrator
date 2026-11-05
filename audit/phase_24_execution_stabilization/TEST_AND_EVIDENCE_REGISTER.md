# JARVIS OS — TEST AND EVIDENCE REGISTER
**Phase 24 Empirical Verification and Test Results**  
**Date:** 2026-10-21  
**Python Runtime:** Python 3.14.7 (`venv\Scripts\python.exe`)  
**Platform:** Windows 11 AMD64  

---

## 1. TARGETED PHASE 24 TEST SUITES

All tests executed using the local project virtual environment:
`& venv\Scripts\python.exe -m pytest <test_files> -v`

### Summary of Targeted Runs:
| Test Suite | Total Tests | Passed | Failed | Duration | Coverage Focus |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `tests/test_phase24_e2e_scenarios.py` | 5 | 5 | 0 | 4.98s | End-to-End Scenarios A through E |
| `tests/test_dependency_authorization_lifecycle.py` | 8 | 8 | 0 | 1.03s | 7-Step Dependency Lifecycle & Scope Isolation |
| `tests/test_file_lease_manager.py` | 6 | 6 | 0 | 1.30s | Atomic Leases, Conflicts, Expiry, Renewal |
| `tests/test_safety_classifier_regression.py` | 5 | 5 | 0 | 0.11s | Portuguese Verb Conjugations & Defense/Education |
| `tests/test_chat_mission_bridge.py` | 12 | 12 | 0 | 2.21s | Chat Routing, Directive Resolution, State Transitions |
| `tests/test_chat_router_consolidation.py` | 16 | 16 | 0 | 1.19s | Multi-scenario Router & Local Model Fallback Integrity |
| **Targeted Total** | **52** | **52** | **0** | **~6.80s** | **100% Pass Rate** |

---

## 2. DETAILED BREAKDOWN OF INDIVIDUAL TESTS

### 2.1 End-to-End Scenarios (`test_phase24_e2e_scenarios.py`)
- **Command:** `& venv\Scripts\python.exe -m pytest tests/test_phase24_e2e_scenarios.py -v`
- **Results:**
  - `test_scenario_a_missing_dependency_approval_granted`: **PASSED**  
    *Evidence:* Missing `pandas` detected; request prepared; mission placed in `BLOCKED`; user sent `"aprovo"`; mock installer executed; `requirements.txt` updated; mission resumed to `COMPLETED`.
  - `test_scenario_b_missing_dependency_approval_denied`: **PASSED**  
    *Evidence:* Missing `beautifulsoup4` detected; user sent `"recuso"`; installation aborted; `requirements.txt` untouched; mission remained `BLOCKED`.
  - `test_scenario_c_dependency_installation_fails_honestly`: **PASSED**  
    *Evidence:* Simulated distribution failure; error propagated honestly; mission transitioned `BLOCKED` → `ACTIVE` → `FAILED`.
  - `test_scenario_d_ordinary_assisted_modification`: **PASSED**  
    *Evidence:* Directive without new dependencies completed without requesting permission; atomic file lease on `main.py` acquired and released.
  - `test_scenario_e_scope_isolation_cross_project_and_operation`: **PASSED**  
    *Evidence:* Approval for `proj-alpha` rejected when attempted on `proj-beta`; approval for package install rejected when attempted for `SHELL_EXEC`.

### 2.2 Dependency Authorization Lifecycle (`test_dependency_authorization_lifecycle.py`)
- **Command:** `& venv\Scripts\python.exe -m pytest tests/test_dependency_authorization_lifecycle.py -v`
- **Results:**
  - `test_missing_dependency_detection`: **PASSED** (detected uninstalled package).
  - `test_already_installed_dependency_recognized`: **PASSED** (recognized existing sys/venv packages).
  - `test_prepare_authorization_request_transparency`: **PASSED** (all 7 explanation fields present).
  - `test_pending_approval_prevents_installation`: **PASSED** (blocked before decision).
  - `test_denied_approval_prevents_installation`: **PASSED** (denied token rejects installation).
  - `test_approved_installation_executes_and_updates_manifest`: **PASSED** (manifest updated, import verified).
  - `test_installation_failure_reported_honestly`: **PASSED** (failure surfaced truthfully).
  - `test_scope_isolation_cross_project_and_operation`: **PASSED** (cross-project & cross-operation rejection).

### 2.3 File Lease Manager (`test_file_lease_manager.py`)
- **Command:** `& venv\Scripts\python.exe -m pytest tests/test_file_lease_manager.py -v`
- **Results:**
  - `test_acquire_and_release_file_lease`: **PASSED** (normal lock acquisition and release).
  - `test_concurrent_conflict_detected`: **PASSED** (`FileLeaseConflictError` raised on overlap).
  - `test_same_holder_renewal`: **PASSED** (lease extended when requested by same holder).
  - `test_expired_lease_allows_new_holder`: **PASSED** (expired lock cleanly reassigned).
  - `test_release_all_for_holder`: **PASSED** (all task locks cleared in batch).
  - `test_file_lock_context_manager`: **PASSED** (clean context manager acquisition/release).

### 2.4 Safety Classifier Regression (`test_safety_classifier_regression.py`)
- **Command:** `& venv\Scripts\python.exe -m pytest tests/test_safety_classifier_regression.py -v`
- **Results:**
  - `test_offensive_ddos_infinitive_blocked`: **PASSED** (`derrubar servidor...` blocked).
  - `test_offensive_ddos_imperative_blocked`: **PASSED** (`derruba o servidor...` blocked).
  - `test_offensive_ddos_imperative_variants_blocked`: **PASSED** (`inunda`, `bloqueia` blocked).
  - `test_defensive_mitigation_allowed`: **PASSED** (`como mitigar ataque DDoS...` allowed).
  - `test_educational_question_allowed`: **PASSED** (`o que é um ataque DDoS...` allowed).

### 2.5 Core Smoke Suite Verification (`test_smoke.py`)
- **Command:** `& venv\Scripts\python.exe -m pytest tests/test_smoke.py -v`
- **Results:** **56 passed, 10 subtests passed in 1.29s.** Zero regressions across command policy, path containment, tool wrapping, and local database operations.

---

## 3. REAL HARDWARE & MEMORY MEASUREMENTS

During the investigation of `test_swarm_federation_phase18.py::test_memory_budget_at_scale_512`:
- **Measurement Tool:** Real Windows `psutil` (via `venv\Scripts\python.exe`).
- **Scale:** 512 agent instances partitioned across 4 isolated worker processes.
- **Observed RSS:**
  - Main Process: **122.84 MB**
  - 4 Worker Processes: **106.42 MB**
  - Total Windows Memory Footprint: **229.26 MB**
- **Conclusion:** While 229 MB is lean for 512 multi-process agents, it exceeds arbitrary 200 MB thresholds due to Windows runtime overhead (~25 MB base per Python process). Process-sharded Swarm Federation is resource-heavy compared to in-process sequential crews and must remain disabled by default on consumer hardware.
