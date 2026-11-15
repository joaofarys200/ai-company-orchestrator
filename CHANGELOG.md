# Changelog

All notable changes to **JARVIS OS** are documented in this file in adherence to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0-tauri] - Tauri 2 + Rust Core Migration

### Added
- **Tauri 2 Native Shell & Rust Core (`src-tauri/`)**: Added Rust Core runtime with Win32 Job Object worker supervision, single-writer SQLite engine (`rusqlite`), `StudyStore`, `PathJail`, `PermissionGateway`, `CommandGuard`, and `UrlSsrfGuard`.
- **Authenticated Loopback Media & Preview Servers (`127.0.0.1:0`)**: Added Axum range-request media server (`Host`/`Origin`/`Sec-Fetch-Site` guards, `OsRng` bearer token, `doc_id`-scoped HMAC tickets) and sandboxed IDE preview server.
- **Frontend Transport Abstraction (`frontend/src/transport/`)**: Added `JarvisTransport`, `TauriTransportAdapter`, shared correlation registry, native dialog/drag-drop integration, and pure Tauri IPC default routing.
- **Specialized Python Domain Workers (`workers/`)**: Added `ai`, `study`, `knowledge`, `mission`, and `voice` workers over stdio NDJSON JSON-RPC 2.0 with stdout fd isolation, cooperative `task.cancel`, Reverse-RPC HITL approvals, and Windows `PeekNamedPipe` reader safety.
- **Mission Governance Resolution & Runtime Bridge**: Resolved all 33 mission governance dispatch paths via `backend/mission_governance_dispatch.py` and broke circular `agents -> server` coupling with `backend/runtime_bridge.py`.

### Changed
- **Canonical Agent Package Consolidation**: Consolidated 596 duplicate files from `backend/agents/` into `agents/` with a dynamic `backend/agents/__init__.py` alias loader for backwards import compatibility.
- **Loopback Sandbox Binding**: Restricted `sandbox.py` server binding exclusively to `127.0.0.1`.
- **CI Validation Pipeline**: Upgraded `.github/workflows/tauri-windows-validation.yml` for Windows build, Rust `cargo test --locked`, Python contract + E2E worker tests, and `jarvis-os.exe` smoke boot validation.

### Removed
- **Electron Shell & Legacy WebSocket/HTTP Daemons**: Removed `main.js`, `preload.js`, `electron`/`concurrently` npm dependencies, `:8001`/`:8000` startup in `server.py`, and transitional localhost WebSocket CSP exemptions in `tauri.conf.json`.

---

## [1.0.0] - 2026-08-31

### Added
- **Project &amp; File Management**: Implemented `delete_project` and `delete_project_file` backend services and WebSocket handlers with interactive safety confirmation dialogs in the Monaco Editor and project picker dropdown.
- **Coding Agent 2.0 Pipeline**: Integrated AST Symbol Graph, Repository Graph, and Typed Semantic Resolver for atomic, multi-file code modifications without full-file rewrites.
- **Autonomous Self-Repair Loop**: Added `autonomous_repair_loop.py` and `failure_memory.py` to automatically diagnose and recover from compilation and test errors.
- **Model Harness &amp; Dual-Model Router**: Multi-provider execution engine supporting local Ollama (`qwen3.5:9b`), OpenRouter Free Tier (`openrouter/free`, `nemotron`), and commercial cloud providers with 7-stage deterministic schema validation.
- **Security Sentinel (EDR Watchdog)**: Real-time host telemetry collectors for Windows processes, listening sockets, scheduled tasks, and filesystem integrity with human approval gates and one-click rollback.
- **Cornell Lecture Synthesis &amp; Quiz Engine**: Audio lecture recording via microphone, Whisper transcription, Cornell note formatting, and interactive multiple-choice quiz evaluation.
- **Bi-Directional Obsidian RAG**: Knowledge vault integration connecting markdown notes, epistemic backlink graphs, and hybrid semantic search.
- **Canonical JSON Schemas**: Formalized 11 JSON Schemas (Draft-07) in `schemas/` covering missions, model requests, tool calls, WebSocket envelopes, and Sentinel events.
- **Architecture Collection**: 10 standalone SVG architecture diagrams in `docs/diagrams/`.
- **Documentation Integrity Test Suite**: Added `tests/test_documentation_integrity.py` to validate links, schema adherence, and SVG assets on every build.

### Changed
- Refactored `server.py` and `main.js` to support clean child process termination on Windows (`taskkill /F /T`) to prevent port `3000`/`8000` collisions.
- Enhanced `WebSocketDispatcher` with strict protocol assertions ensuring zero drift between Python message catalogs and TypeScript interfaces.
- Standardized economic mission classification into a strict 4-tier taxonomy (`SYNTHETIC_BENCHMARK`, `EXTERNAL_OBSERVED`, `EXTERNAL_VERIFIED`, `FINANCIAL_TRANSACTION_VERIFIED`).

### Fixed
- Fixed unhandled restart timer exceptions in Electron lifecycle (`main.js`).
- Resolved port reuse conflicts during local sandbox preview server restarts.
- Fixed symbol replacement edge cases for JavaScript verbatim syntax blocks.

### Security
- Enforced strict directory traversal protection (`_safe_project_path`) across all agent file operations.
- Added host watchdog containment actions with mandatory human confirmation for process termination, task disabling, and file quarantine.
