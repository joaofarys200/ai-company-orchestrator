# JARVIS OS — ARCHITECTURAL DECISIONS
**Phase 24 Architecture Decision Records (ADR)**  
**Date:** 2026-10-21  
**Status:** APPROVED  

---

## ADR 24-01: Swarm Federation Architecture Decision

### Context
The Phase 23 Audit reported that `SwarmFederation` constitutes a large body of code supporting sharded and distributed agents across multiple processes, but is disconnected from the main chat directive pipeline where personas execute sequentially. Phase 24 required an evidence-based decision among three options:
- Option A: Integrate federation into the active mission pipeline.
- Option B: Keep federation isolated but document explicit status and activation criteria.
- Option C: Recommend later refactoring or removal.

### Evidence & Analysis
1. **Execution Model:** Real-world developer assistance directives (e.g. creating endpoints, editing components, inspecting projects) are inherently stateful and sequential. They require rapid single-thread reasoning rather than distributed consensus across hundreds of agents.
2. **Resource Measurements:** Profiling `SwarmFederation` with 512 agents across 4 worker processes using genuine Windows `psutil` measured **229.26 MB RSS** and multi-second IPC overhead. On local machines with constrained RAM and single-GPU VRAM running `qwen3.5:9b`, launching hundreds of federated worker agents produces severe memory pressure and GPU inference queue contention.
3. **Existing Capability:** The active Crew/Persona system (`agents/orchestrator`) already provides adequate role specialization (Planner, Coder, Reviewer) without multi-process overhead.

### Decision: Option B (Keep Isolated with Explicit Activation Criteria)
- `SwarmFederation` is retained in its isolated modules for experimental research and high-concurrency benchmarks.
- It is **NOT** enabled as the default execution engine for chat directives.
- **Activation Criteria for Future Enablement:**
  - Deployment on multi-node or multi-GPU environments with dedicated inference endpoints.
  - Asynchronous background simulation or automated penetration testing tasks with decoupled, non-blocking DAG nodes.
  - Strict VRAM and process telemetry gating ensuring host memory does not thrash.

---

## ADR 24-02: Persistence Architecture Decision

### Context
The audit noted that while SQLite schemas exist in `backend/database`, active mission entities (missions, work packages, criteria, evidence) are persisted as structured JSON documents under `workspace/projects/<project_id>/missions/`. Some SQLite tables were observed to be empty.

### Analysis & Constraints
1. **Data Integrity:** User workspaces and project mission histories already rely on the JSON store in `MissionStateStore`. Performing a hasty SQLite migration without an enterprise-grade schema migration engine risks silent data loss, version incompatibility, or state corruption.
2. **Auditability:** JSON files in the workspace are human-readable, easily inspectable, and can be committed to Git alongside project artifacts.
3. **Current Invariants:** `MissionStateStore` provides optimistic concurrency control via integer version locks (`expected_version`), atomic file writes, and an event append log.

### Decision: Maintain JSON as Authoritative Mission Store; Document SQLite Debt
- For Phase 24, JSON files in `workspace/projects/<project_id>/missions/` remain the **authoritative store** for missions, work packages, acceptance criteria, and evidence.
- Empty SQLite tables are documented as architectural technical debt resulting from earlier exploratory relational prototypes.
- Any future transition to SQLite must be non-destructive, accompanied by bidirectional data sync and verified database migrations.

---

## ADR 24-03: Authorization Boundary Design Decision

### Context
Development tasks frequently need dependencies that may not be pre-installed in the user's environment. Previous versions either failed unconditionally or risked unconstrained execution.

### Decision: Just-In-Time Scoped Authorization with Backend Enforcement
- **Separation of Concerns:**
  - *Classification:* Determines whether an operation involves mutations, installs, or security risks.
  - *Permission:* Determines if an authorized token exists for that specific operation in that specific project.
  - *Environment Management:* Discovers and operates within the isolated project virtualenv.
- **Backend Boundary Enforcement:** Authorization checks must occur immediately prior to subprocess execution in `ProjectDependencyManager.enforce_backend_authorization`. No frontend flag or conversational statement can bypass this check.
- **Strict Scope Isolation:** An approved token is irrevocably bound to `(project_id, requested_operation)`. Cross-project reuse or operation escalation is prohibited.

---

## ADR 24-04: Deferred Work and Rationale

1. **Relational Database Migration:**
   - *Deferred to:* Phase 25+
   - *Rationale:* JSON persistence is stable and active. Migrating to SQLite requires extensive schema stabilization and zero data loss validation.
2. **Automated Multi-Node Swarm Scheduling:**
   - *Deferred to:* Phase 26+
   - *Rationale:* Single-node local execution on `qwen3.5:9b` is the core product requirement. Multi-node distributed scheduling adds unnecessary complexity for desktop developer workflows.
