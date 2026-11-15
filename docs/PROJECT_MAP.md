# JARVIS OS — Repository Project Map

An exhaustive architectural and structural guide to all physical directories, key modules, entry points, dependencies, and test suites across the JARVIS OS codebase.

---

## Directory Index

```
JARVIS OS (ai-company-orchestrator)
├── agents/                  # Multi-agent swarm (Clara, Alex, Devon, Quinn), mission executors, tools
├── backend/                 # Domain dispatcher, contracts, Model Harness, runtime_bridge, agents/ alias
├── config/                  # Global system configuration and runtime parameters
├── diagnostics/             # Environment diagnostic tools and system telemetry scripts
├── docs/                    # Architectural specifications, benchmark reports, diagrams, and ADRs
│   ├── decisions/           # Architecture Decision Records (ADR-001 to ADR-006)
│   └── diagrams/            # Standalone vector SVG architecture diagrams (01 to 10)
├── evidence/                # Verified test run evidence (screenshots, DOM dumps, event logs)
├── frontend/                # React 19 + Vite + Tailwind + Monaco Editor + JarvisTransport desktop HUD
├── intelligence/            # Coding Agent 2.0 (AST repair, repo graph, semantic resolver, build loop)
├── obsidian_vault/          # Plain-text Markdown Knowledge Vault and Cornell study guides
├── persistence/             # SQLite repositories for rules, decisions, projects and messages
├── schemas/                 # Canonical JSON Schemas (Draft-07) for core data contracts
├── security/                # Security Sentinel watchdog, EDR host monitors, safety classifier
├── sentinel/                # Sentinel quarantine store and response history audit log
├── services/                # Specialized background services (StudyService, Lecture recorder/synthesizer)
├── src-tauri/               # Tauri 2 + Rust Core native shell, SQLite writer, loopback HTTP, Win32 Job supervisor
├── tests/                   # Automated pytest test suites covering all subsystems & 5-worker E2E IPC
├── workers/                 # Role-isolated Python domain sidecar workers (`ai`, `study`, `knowledge`, `mission`, `voice`)
└── workspace/               # Isolated project code sandboxes and AST metadata (.jarvis/)
```

---

## Detailed Subsystem Breakdown

### 1. `agents/` — Multi-Agent Swarm &amp; Mission Execution
- **Purpose**: Autonomous coordination, specialized roles, tool execution, and mission state management.
- **Key Modules**:
  - `agent_profiles.py`: Persona definitions for **Clara** (Executive), **Alex** (Architecture), **Devon** (Coding), and **Quinn** (QA/Security).
  - `mission_state.py`: Deterministic state machines for `Mission`, `WorkPackage`, `Deliverable`, and `Criterion`.
  - `mission_executor.py`: Work package task runner with dependency DAG resolution and execution locks.
  - `mission_autonomy.py`: Autonomous execution loop coordinating agents across long-horizon goals.
  - `patch_engine.py`: Atomic code modification engine.
  - `tools.py` &amp; `tool_registry.py`: 30+ registered agent tools with schema validation.
  - `obsidian_tools.py`: Obsidian Knowledge Vault tools.
- **Test Suites**: `tests/test_mission_state.py`, `tests/test_mission_executor.py`, `tests/test_mission_autonomy.py`.

---

### 2. `backend/` & `workers/` — Domain Runtime, Dispatcher & Sidecar Workers
- **Purpose**: Domain dispatcher contracts, multi-provider Model Harness, `runtime_bridge`, canonical `agents/` alias loader, and stdio NDJSON JSON-RPC domain workers (`src-tauri/` hosts the Tauri 2 + Rust Core supervisor & native SQLite/loopback services).
- **Key Modules**:
  - `src-tauri/src/lib.rs` & `commands/dispatch.rs`: Tauri 2 native entry point, `RuntimeServices`, and IPC router.
  - `src-tauri/src/workers/{supervisor,rpc_client}.rs`: Win32 Job Object worker supervisor and JSON-RPC 2.0 pipe client.
  - `src-tauri/src/storage/{sqlite,study_store,atomic_fs}.rs`: Single-writer SQLite engine, `StudyStore`, and atomic file storage.
  - `workers/worker_boot.py` & `workers/common/{stdio_rpc,domain_bridge}.py`: Stdio FD-isolated JSON-RPC 2.0 runtime for `ai`, `study`, `knowledge`, `mission`, and `voice` roles.
  - `backend/runtime_bridge.py`: Decoupled bridge connecting `agents/` and legacy callers without circular `import server` cycles.
  - `backend/agents/__init__.py`: Dynamic alias finder/loader forwarding imports cleanly to canonical `agents/`.
  - `backend/websocket/{dispatcher,contracts}.py`: Message router and protocol contracts shared across Python workers and Rust IPC.
  - `backend/model_harness/{harness,router,validation,recovery}.py`: Multi-provider execution engine with profile routing and 7-stage validation.
- **Test Suites**: `tests/test_model_harness.py`, `tests/test_server_websocket_characterization.py`, `tests/test_worker_stdio_rpc.py`, `tests/test_domain_workers_phase3.py`, `tests/test_e2e_workers_all_roles.py`.

---

### 3. `intelligence/` — Coding Agent 2.0 Engine
- **Purpose**: Deep code comprehension, AST manipulation, cross-file type resolution, and self-repair.
- **Key Modules**:
  - `coding_session.py`: Interactive coding engine managing unified diff proposals and checkpoints.
  - `project_context.py`: AST parser extracting symbols, functions, classes, and language stacks.
  - `repository_graph.py`: Cross-repository dependency and monorepo structure graph.
  - `typed_semantic_resolver.py`: TypeScript and Python import path, interface, and type resolver.
  - `tsconfig_resolver.py`: TSConfig path mapping and alias resolution (`@/*`).
  - `cross_file_validator.py`: Multi-file contract alignment and signature verification.
  - `build_pipeline.py`: Compilation and linter verification (`py_compile`, `tsc`, `eslint`).
  - `autonomous_repair_loop.py`: Automatic feedback and AST repair loop on build/test failures.
  - `failure_memory.py`: Bank of broken patch patterns to prevent repeating buggy attempts.
- **Test Suites**: `tests/test_project_context.py`, `tests/test_coding_session.py`, `tests/test_repository_graph.py`.

---

### 4. `security/` — Security Sentinel EDR &amp; Host Watchdog
- **Purpose**: Real-time Windows host monitoring, baseline drift analysis, containment, and reversible rollback.
- **Key Modules**:
  - `security/sentinel/watchdog.py`: Continuous background monitoring loop.
  - `security/sentinel/baseline.py`: Host baseline capture and drift measurement.
  - `security/sentinel/correlation.py`: Temporal correlation engine clustering events in 60s windows.
  - `security/sentinel/collectors/`: Windows collectors for processes, listening ports, tasks, and filesystem.
  - `security/sentinel/response/`: Containment actions (`TERMINATE_PROCESS`, `QUARANTINE_FILE`, `DISABLE_SCHEDULED_TASK`).
  - `security/safety_classifier.py`: Real-time intent classification for dangerous command refusal.
- **Test Suites**: `tests/test_sentinel.py`, `tests/test_sentinel_response_actions.py`, `tests/test_sentinel_rollback.py`.

---

### 5. `frontend/` — React 19 + Vite + Tailwind + Tauri IPC Desktop HUD
- **Purpose**: User interface, Monaco code editor, Mission planner, Sentinel watchdog monitor, Study HUD, and Cornell lecture player.
- **Key Components**:
  - `src/transport/{JarvisTransport,TauriTransportAdapter}.ts`: Transport abstraction and pure Tauri IPC adapter (`jarvis:event` + native dialogs/drag-drop/media tickets).
  - `src/context/AppSessionContext.tsx`: React session context decoupling UI panels from transport implementation.
  - `src/features/workspace/WorkspaceViewer.tsx`: Main workspace HUD (Kanban, Code, Preview, Missions, Sentinel).
  - `src/features/workspace/CodeEditor.tsx`: Monaco Editor integration with file tree, diff, formatting, and delete modal.
  - `src/features/planner/MissionPlanner.tsx`: Interactive Kanban mission viewer and step runner.
  - `src/features/sentinel/SentinelDashboard.tsx`: Security Sentinel incident triage and approval UI.
  - `src/features/lectures/LecturesPanel.tsx`: Cornell study guide player and interactive quiz evaluator.

---

### 6. `obsidian_vault/` — Plain-Text Knowledge Substrate
- **Purpose**: 100+ interconnected markdown notes, Cornell study guides, and literature references.
- **Structure**:
  - `00 - MOC/`: Maps of Content for AI, Distributed Systems, Software Engineering.
  - `01 - Fleeting Notes/`: Quick conceptual captures and ideas.
  - `02 - Literature Notes/`: Academic paper summaries with arXiv citations.
  - `10 - Lectures/`: Cornell notes from recorded audio sessions with cues, summaries, and quizzes.

---

### 7. `schemas/` — Canonical JSON Schemas
- **Purpose**: Formal JSON Schema (Draft-07) specifications ensuring zero contract drift across all domains.
- **Index**: See [`schemas/README.md`](../schemas/README.md).
