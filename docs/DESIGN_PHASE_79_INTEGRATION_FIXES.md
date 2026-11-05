# Phase 79 System Design: Product Integration Fixes

**Phase**: 79  
**Title**: JARVIS Product Reality & End-to-End Capability Integration  
**Date**: 2026-10-25  
**Author**: Antigravity Assistant (Google DeepMind)  
**Target Repository**: `JARVIS OS`  

---

## 1. Problem Statement & Scope

The Phase 79 Product Reality Audit documented that Phases 65–78 are technically complete in isolated packages, but are largely unreachable by real users. The goal of this phase is **not** to create another intelligence subsystem, but to surgically connect existing capabilities into the primary production execution path:

$$\text{User Directive (Chat)} \longrightarrow \text{ChatMissionBridge} \longrightarrow \text{Capability Bridges} \longrightarrow \text{Empirical Verification} \longrightarrow \text{UI Feedback}$$

---

## 2. Surgical Integration Fixes

### Fix 1: Diagnostic & Root-Cause Routing via CausalDiagnosisBridge (Phase 78)
- **Target File**: [`backend/services/chat_mission_bridge.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/services/chat_mission_bridge.py)
- **Problem**: When a user asks *"diagnostica a causa da falha"* or *"qual é a causa raiz do erro"*, `ChatRequestResolver` routes to `PROJECT_INSPECTION`, which outputs a raw markdown directory listing (`"- app.js\n- package.json"`). Phase 78 is never invoked.
- **Fix**:
  1. Add a dedicated `ChatIntentType.ROOT_CAUSE_DIAGNOSIS` to `ChatRequestResolver`.
  2. Detect diagnostic prompts matching:
     `r"\b(causa\s+raiz|diagnostica\s+a\s+falha|diagnosticar\s+o\s+erro|analisa\s+o\s+erro|porque\s+falhou|investiga\s+o\s+crash|root\s+cause|diagnose\s+failure)\b"`.
  3. In `ChatMissionBridge.handle_directive`: Instantiate and execute `CausalDiagnosisBridge` on the target workspace, build the causal DAG, perform structural interventions, and return the verifiable root cause with counterfactual evidence.

### Fix 2: Real Repository & Workspace Context Fallback
- **Target File**: [`backend/services/chat_mission_bridge.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/services/chat_mission_bridge.py)
- **Problem**: When a user asks *"explica a arquitetura e identifica os ficheiros relevantes"*, `target_proj` defaults to `"default-project"`. Because `workspace/projects/default-project` does not exist, JARVIS immediately outputs: *"Procurei pelo projeto default-project... mas a pasta ainda não existe."*
- **Fix**:
  1. If `target_proj` is unset or points to `"default-project"`, seamlessly fall back to the active workspace root (`WORKSPACE_ROOT` / `.`).
  2. Inspect the real files in the workspace root or project context.
  3. Ground architecture explanations in actual repository modules (`backend/`, `agents/`, `frontend/`, `server.py`).

### Fix 3: Evidence-Governed Mission Completion (Phase 77 Integration)
- **Target File**: [`backend/services/chat_mission_bridge.py`](file:///c:/Users/joaor/Desktop/JarvisOS/backend/services/chat_mission_bridge.py)
- **Problem**: `_execute_mission_work` wraps arbitrary model text in `BridgeExecutionResult(success=True)`. The bridge immediately attaches synthetic evidence (`"validation:chat_pipeline"`) and marks the mission `COMPLETED` and criteria `SATISFIED` even when no tests were executed and no code was verified.
- **Fix**:
  1. Require verifiable evidence for code modifications or test execution requests.
  2. Check if a test command or validation was actually executed (`execute_command` or test verification).
  3. If code was modified without test verification, mark the status accurately as `PARTIALLY_COMPLETED` or `AWAITING_VERIFICATION` rather than falsely claiming 100% verified completion.
  4. Attach evidence with real execution provenance hashes from Phase 77 (`EvidenceGovernanceBridge`).

### Fix 4: Expose Real Diagnostic & Governance Tools in `JARVIS_TOOLS`
- **Target Files**:
  - [`agents/tools.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/tools.py)
  - [`agents/orchestrator/__init__.py`](file:///c:/Users/joaor/Desktop/JarvisOS/agents/orchestrator/__init__.py)
- **Problem**: OpenClaw's prompt tells the LLM it is an autonomous COO, but its tool list (`jarvis_tools`) only has basic file read/write and PowerShell execution. It has no tool to run causal diagnosis or verify claims.
- **Fix**:
  1. Add `diagnosticar_causa_raiz`:
     ```python
     {
         "name": "diagnosticar_causa_raiz",
         "description": "Executa diagnóstico causal avançado (Phase 78) para identificar a causa raiz de uma falha de testes, erro de compilação ou anomalia de execução.",
         "input_schema": {
             "type": "object",
             "properties": {
                 "failure_description": {"type": "string"},
                 "target_component": {"type": "string"},
                 "traceback": {"type": "string"}
             },
             "required": ["failure_description"]
         }
     }
     ```
  2. Add `verificar_evidencias_entrega`:
     ```python
     {
         "name": "verificar_evidencias_entrega",
         "description": "Executa governança e verificação formal de evidências (Phase 77) para auditar se uma alteração possui provas empíricas e testes reprodutíveis.",
         "input_schema": {
             "type": "object",
             "properties": {
                 "claim_id": {"type": "string"},
                 "artifact_path": {"type": "string"}
             },
             "required": ["claim_id"]
         }
     }
     ```
  3. Wire execution handlers in `agents/orchestrator/__init__.py` to delegate to `CausalDiagnosisBridge` and `EvidenceGovernanceBridge`.

---

## 3. End-to-End Scenarios for Validation

| Scenario | Workflow | Success Criterion |
|---|---|---|
| **Scenario A** | Project understanding on workspace without explicit sub-project name | Grounded in actual repository files; no missing "default-project" error. |
| **Scenario B** | Autonomous engineering task | Real code modification accompanied by test verification; no false completion. |
| **Scenario C** | Failure diagnosis & RCA | Real invocation of `CausalDiagnosisBridge`, constructing causal DAG and isolating root cause. |
| **Scenario D** | Interrupted mission recovery | Resumes without duplicate execution; validates durable checkpointing. |
| **Scenario E** | Evidence-based completion | Verifies claims with Phase 77; rejects self-asserted completion without test evidence. |

---

## 4. Safety & Compatibility Guarantees
- Zero cloud dependencies: 100% local execution.
- Command blocklist remains active: no destructive shell commands permitted.
- Existing tests and historical regression suite (Phases 40–78) remain completely untouched and passing ($\Delta = 0$).
