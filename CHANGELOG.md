# Changelog

All notable changes to **JARVIS OS** are documented in this file in adherence to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
