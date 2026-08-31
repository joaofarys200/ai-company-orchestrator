# Security Policy &amp; Architecture

JARVIS OS is designed from the ground up with defensive, fail-safe cybersecurity invariants to ensure that autonomous agent execution cannot compromise the host operating system or leak private user data.

---

## 1. Security Architecture &amp; Defensive Layers

### A. Security Sentinel EDR Watchdog (`security/sentinel/`)
JARVIS OS includes an integrated host monitoring engine that continuously observes:
1. **Process Tree Activity**: Identifies newly spawned subprocesses, anomalous shell invocations, and unauthorized execution chains.
2. **Network Listening Ports**: Monitors active TCP/UDP listening sockets and alerts if an untrusted process opens a public port.
3. **Persistence Mechanisms**: Audits Windows Task Scheduler and Registry startup keys for unauthorized modifications.
4. **Filesystem Integrity**: Tracks writes to critical system paths and prevents arbitrary file mutations outside approved workspace sandboxes.

### B. Mandatory Human Approval Gate
No destructive, high-risk, or mutating remediation action (`TERMINATE_PROCESS`, `QUARANTINE_FILE`, `DISABLE_SCHEDULED_TASK`) is ever executed without explicit confirmation by the human operator via the Workspace HUD.

### C. Reversible Actions &amp; One-Click Rollback
All containment actions capture full pre-state snapshots. If an action is marked as a false positive, the user can restore quarantined files or re-enable tasks with a single click.

### D. Workspace Isolation Boundary
Agent file read and write operations are strictly jailed to `workspace/projects/<project_id>/` and `obsidian_vault/`. The path resolver rejects directory traversal sequences (e.g. `../../Windows/`) with explicit `ProjectContextError` exceptions.

---

## 2. Secrets &amp; Environment Management

- **Zero Hardcoded Secrets**: All API keys (`OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `FIRECRAWL_API_KEY`) must be configured exclusively via `.env`.
- **Git Ignore Enforcement**: `.env`, `.env.*`, `database.db`, `workspace/projects/*` (except public templates), and `.jarvis/` metadata are strictly ignored in `.gitignore`.
- **Local Private Mode**: When running with local Ollama (`qwen3.5:9b`), zero prompt tokens or project files leave the local machine.

---

## 3. Reporting a Vulnerability

We take the security and integrity of JARVIS OS seriously. If you discover a security vulnerability, potential bypass, or sandbox escape:

1. **Do NOT file a public issue.**
2. Send a detailed report describing the vulnerability, proof of concept, and affected versions to the repository maintainer.
3. Please allow a reasonable disclosure window for triage, reproduction, and patching before public disclosure.

---

## 4. Supported Versions

| Version | Supported | Security Maintenance |
|---|---|---|
| 1.0.x (Current `main`) | :white_check_mark: | Active Security Updates &amp; Sentinel Fixes |
| &lt; 1.0.0 | :x: | Deprecated |
