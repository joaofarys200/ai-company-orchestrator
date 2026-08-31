# JARVIS OS — JSON Schemas Index

This directory contains the canonical JSON Schemas defining the data contracts, operational envelopes, and telemetry models across JARVIS OS.

All schemas follow the **JSON Schema Draft-07** specification and are validated automatically by automated test suites.

---

## Schema Catalog

| Schema File | Version ($id) | Purpose &amp; Domain | Primary Source / Model | Consumer Subsystems |
|---|---|---|---|---|
| [`mission.schema.json`](./mission.schema.json) | `jarvis/mission/v1` | Autonomous multi-agent missions and state machines | `agents/mission_state.py::Mission` | Mission Planner, Autonomy Loop, Workspace HUD |
| [`model-request.schema.json`](./model-request.schema.json) | `jarvis/model-request/v1` | Request contract for multi-provider Model Harness | `backend/model_harness/contracts.py` | Model Router, Agent Swarm, Tool Invocations |
| [`model-response.schema.json`](./model-response.schema.json) | `jarvis/model-response/v1` | Structured output and telemetry from model execution | `backend/model_harness/contracts.py` | Model Harness, Telemetry Logger, Recovery Engine |
| [`tool-call.schema.json`](./tool-call.schema.json) | `jarvis/tool-call/v1` | Tool dispatch contracts and arguments envelope | `agents/tools.py` &amp; `agents/tool_registry.py` | Agent Swarm, Sandbox Execution, Sentinel Guard |
| [`websocket-message.schema.json`](./websocket-message.schema.json) | `jarvis/websocket-message/v1` | Duplex communication envelope for client/server | `websocket_schema.py` | WebSocket Gateway, React Client, Dispatcher |
| [`security-event.schema.json`](./security-event.schema.json) | `jarvis/security-event/v1` | Host security telemetry collected from OS | `security/sentinel/contracts.py` | Sentinel Watchdog, Collectors, Correlation Engine |
| [`security-incident.schema.json`](./security-incident.schema.json) | `jarvis/security-incident/v1` | Correlated security incidents and severity scores | `security/sentinel/contracts.py` | Incident Manager, Sentinel UI, Alert Broadcast |
| [`security-response-action.schema.json`](./security-response-action.schema.json) | `jarvis/security-response-action/v1` | Containment actions with human approval &amp; rollback | `security/sentinel/contracts.py` | Response Engine, Approval Modal, Rollback Manager |
| [`economic-mission.schema.json`](./economic-mission.schema.json) | `jarvis/economic-mission/v1` | Economic tasks categorized by 4 factuality tiers | `agents/controlled_real_world_value_agent.py` | Economic Layer, Evidence Auditor, Clara |
| [`evidence.schema.json`](./evidence.schema.json) | `jarvis/evidence/v1` | Cryptographic evidence records (SHA256 digests, DOM) | `agents/mission_state.py` | Browser QA, Deliverable Verifier, Audit Logs |
| [`document-provenance.schema.json`](./document-provenance.schema.json) | `jarvis/document-provenance/v1` | Provenance trail for generated code, notes &amp; docs | `intelligence/artifact_inference.py` | Coding Agent 2.0, Obsidian Vault, PDF Engine |

---

## Schema Invariants &amp; Integrity

1. **Versioned Identifiers**: Every schema defines a unique, versioned `$id` (e.g. `jarvis/mission/v1`).
2. **Strict Property Typing**: Types, formats (`date-time`, `regex`), and enums match the runtime Python dataclasses and TypeScript definitions.
3. **No Drift Policy**: The automated test [`tests/test_documentation_integrity.py`](../tests/test_documentation_integrity.py) validates all schemas in this directory against Draft-07 meta-schemas on every CI build.
