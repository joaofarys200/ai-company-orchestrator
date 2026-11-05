# JARVIS OS — MISSION EXECUTION FLOW
**Chat Entrypoint to Execution Engine Lifecycle**  
**Date:** 2026-10-21  
**Status:** IMPLEMENTED AND VERIFIED  

---

## 1. COMPARISON: BEFORE VS. AFTER PHASE 24

### Before Phase 24
```
Chat Input
  ↓
ChatRequestResolver (Keyword classification)
  ↓
MissionStateStore (Creates DRAFT -> READY)
  ↓
_execute_mission_work (Delegates directly to orchestration_service without file locks)
  ↓
No JIT dependency detection (Missing packages either crash or abort silently)
  ↓
Potential concurrent file conflicts (Multiple agents editing app.js concurrently)
  ↓
Completion without formal execution attribution
```

### After Phase 24
```
Chat Input
  ↓
1. ChatRequestResolver (Multi-intent classification: Chat, Analysis, Project Query, File Read, Directive)
  ↓
2. Pre-Execution Understanding & Decision Engine (Evaluates feasibility & intent)
  ↓
3. Mission Creation in MissionStateStore (DRAFT -> READY with WorkPackage & AcceptanceCriteria)
  ↓
4. JIT Dependency Analysis & Environment Inspection
  ├── If missing dependency: Transition to ACTIVE -> BLOCKED, request user JIT authorization
  │     ├── Approved -> Install in project venv, verify import, resume ACTIVE
  │     └── Denied -> Mission remains BLOCKED, honest reporting
  └── If dependencies satisfied: Proceed
  ↓
5. Mission Gate Evaluation (Permissions, Safety Policy, Resource Boundaries)
  ↓
6. Atomic File Lease Acquisition (FileLeaseManager locks target candidate files)
  ↓
7. Execution Routing with Explicit Attribution:
  ├── Route A: Formal Mission Orchestrator (DAG graph / subdag) [engine: formal_dag]
  ├── Route B: Project Builder [engine: assisted_builder]
  ├── Route C: Agent Orchestration Service [engine: orchestration_service, fallback: true]
  └── Route D: Mission Autonomy Controller [engine: mission_autonomy]
  ↓
8. Atomic File Lease Release (in finally block)
  ↓
9. Validation & Truth Enforcement:
  ├── Evidence Attachment (EXECUTION_LOG attached to WorkPackage)
  ├── Acceptance Criterion Satisfaction (SATISFIED with evidence refs)
  ├── Work Package Completion (COMPLETED)
  └── Mission Completion (COMPLETED in MissionStateStore)
  ↓
Chat & WebSocket State Update Broadcast
```

---

## 2. FORMAL MISSION PIPELINE INTEGRATION

### 2.1 Mission State Machine Invariants
Missions follow the canonical state transitions defined in `agents/mission_state.py`:
- `DRAFT` → `READY`
- `READY` → `ACTIVE`
- `ACTIVE` → `BLOCKED`, `COMPLETED`, `FAILED`, `CANCELLED`
- `BLOCKED` → `ACTIVE`, `CANCELLED`

In Phase 24, all transitions strictly obey these rules:
- When a missing dependency is detected, the mission transitions `READY` → `ACTIVE` → `BLOCKED`.
- When authorized, it transitions `BLOCKED` → `ACTIVE`.
- When an installation fails, it transitions `BLOCKED` → `ACTIVE` → `FAILED`.
- Missions cannot be marked `COMPLETED` unless all required work packages are `COMPLETED` and all acceptance criteria are `SATISFIED`.

### 2.2 File Lease Manager Integration
To prevent concurrent editing collisions when multiple agents or tasks operate in the workspace:
- `FileLeaseManager` acquires exclusive leases (`FileLease`) on candidate files (e.g., `main.py`, `app.js`, or any file explicitly named in the prompt).
- If another task or session holds a valid lease, `FileLeaseConflictError` is raised with the holder ID and remaining TTL.
- All leases are unconditionally released in a `finally` block upon completion, failure, or cancellation.

---

## 3. LEGACY FALLBACK & ENGINE ATTRIBUTION

The audit identified that `ChatMissionBridge` often used `orchestration_service` rather than a fully dynamic DAG orchestrator.

### Why the Assisted Development Path Exists:
The assisted development loop in `orchestration_service` was designed for direct human-in-the-loop interaction, where a user iteratively asks JARVIS to inspect, edit, or test code. Forcing simple single-file edits into complex multi-node DAG pipelines adds significant latency, multi-second Ollama generation overhead, and fragile state synchronization without tangible benefits for small modifications.

### Phase 24 Integration Solution:
Rather than abruptly deleting the assisted development loop or forcing every query into a heavy distributed DAG:
1. **Explicit Engine Tagging:** Every execution path explicitly reports its underlying engine in `BridgeExecutionResult.details`:
   - `{"execution_engine": "formal_dag", "orchestrator": "MissionLifecycleOrchestrator"}`
   - `{"execution_engine": "assisted_builder"}`
   - `{"execution_engine": "orchestration_service", "fallback": True}`
   - `{"execution_engine": "mission_autonomy"}`
2. **Non-Bypassable Governance:** The assisted path can NO LONGER bypass:
   - JIT dependency authorization.
   - Atomic file leases.
   - Safety classifier boundaries.
   - Work package and acceptance criteria evidence attachment.
   - Execution truth enforcement.
