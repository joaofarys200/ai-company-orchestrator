# ADR-003: Host Security Sentinel Watchdog (EDR) Architecture

## Context
As an autonomous agent system with desktop and terminal execution capabilities, JARVIS OS executes shell commands, runs preview servers, and modifies code. If an agent hallucinated a destructive script, or an external script attempted unauthorized persistence or listening sockets on the host OS, standard sandboxing alone might fail to alert the user or detect host-level anomalies.

## Decision
We implemented **Security Sentinel** (`security/sentinel/`), a real-time host Endpoint Detection and Response (EDR) watchdog:
1. **Windows Host Collectors**: Continuously gather process creation events, network listening ports, scheduled tasks, and filesystem writes.
2. **Known-Good Baseline (`baseline.py`)**: Establishes a clean baseline at startup; alerts on unexpected drift while allowing user-accepted whitelisting.
3. **Temporal Event Correlation (`correlation.py`)**: Merges telemetry in 60-second correlation windows to detect composite attack patterns (e.g. download + execute + persistence).
4. **Mandatory Human Approval Gate**: Any destructive or mutating mitigation action (`TERMINATE_PROCESS`, `QUARANTINE_FILE`, `DISABLE_SCHEDULED_TASK`) requires explicit confirmation in the UI.
5. **Deterministic Reversible Rollback**: All actions capture pre-state snapshots and support one-click rollback if marked as a false positive.

## Alternatives Considered
- *Full Read-Only Sandbox*: Restricts developers from running Node.js dev servers or installing npm dependencies.
- *Fully Automated Silent Mitigation*: Rejected due to risk of false positives terminating legitimate user processes without consent.

## Consequences
- **Positive**: Proactive defense against malicious or runaway background processes; complete audit trail in `sentinel/response_history.json`.
- **Negative**: Adds a lightweight background monitoring loop (negligible CPU footprint &lt;1%).

## Status
**ACCEPTED** (Implemented in `security/sentinel/`).
