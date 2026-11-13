# JARVIS OS — Autonomous Migration State

- **Last Updated (UTC):** `2026-11-13T01:07:00Z`
- **Current Phase:** `Phase 1 — Architecture audit and migration planning (COMPLETE) -> Advancing immediately to Phase 2 — Rust Core and Tauri IPC foundation`
- **Current Increment:** `Phase 1 Checkpoint -> Starting Phase 2.1 (CSP fixes, Tauri capabilities/plugins, WebView2 shell hardening, system IPC commands)`
- **Current Branch:** `migration/tauri-rust-complete`
- **Current Commit:** `e6ad1922e1926eeb0b77d98367d19fe4fb1112b2` (parent: `d5a43e2`; base `main`: `af11ae9095f4cfd8c8e01334704ffde282da9554`, untouched)

---

## 1. Completed Work

### Phase 1 — Architecture Audit & Migration Planning (VERIFIED)
- **Architectural Baseline & ADRs Consolidated (`docs/architecture/`):** Verified all 9 architectural documents (`TAURI_ARCHITECTURAL_DECISIONS.md` Q1–Q12, `TAURI_COMMUNICATION_MATRIX.md`, `TAURI_FUNCTIONAL_PARITY.md`, `TAURI_MIGRATION_AUDIT.md`, `TAURI_MIGRATION_ROADMAP.md`, `TAURI_PERSISTENCE_OWNERSHIP.md`, `TAURI_SECURITY_MODEL.md`, `TAURI_TARGET_ARCHITECTURE.md`, `TAURI_WORKER_PROTOCOL.md`).
- **Stage 1 Baseline Verified on Branch:**
  - `frontend/src/transport/` (`JarvisTransport`, `WebSocketTransportAdapter`, `TransportProvider`, `TransportTypes`, `TransportContext`, `index.ts`) + `frontend/src/transport/__tests__/transport.test.ts` (9 `node:test` specs).
  - Protocol schema alignment: 263 `CLIENT_MESSAGE_TYPES` / 326 `SERVER_MESSAGE_TYPES` (`websocket_schema.py`, `backend/websocket/contracts.py`, `frontend/src/protocol/websocket.ts`).
  - SQLite hardening (`persistence/db.py`, `database.py`, `backend/model_harness/rho.py`, `intelligence/runtime_observer.py`): `WAL`, `busy_timeout=10000`, `foreign_keys=ON`, canonical `PROJECT_ROOT / "database.db"`, composite RHO index, and sandbox-guarded `scripts/migrate_rho_db.py`.
  - `ModelExecutionService` compliance (`ObsidianGraphEngine` and `coding.py` routed away from direct HTTP calls to Ollama).
- **Stage 2 & 2.1 Base Committed on `migration/tauri-rust-complete`:**
  - `d5a43e2`: Isolated `.github/workflows/tauri-windows-validation.yml`.
  - `e6ad192`: Base Tauri 2 shell scaffold (`src-tauri/`, `.gitignore`, `package.json`, `package-lock.json`, `frontend/package.json`, `frontend/package-lock.json`).
  - Remote Windows CI proof (`stage2.1/tauri-windows-ci` run `#43338081076`): `frontend build`, `cargo check`, `cargo test` (`1 passed`), `tauri build --no-bundle` (`jarvis-os.exe`), and unsigned MSI/NSIS bundles all succeeded on `windows-latest` (WebView2 `156.0.4314.58`, `rustc 1.100.0`).
- **4-Domain Deep Audit Executed:** Mapped every Electron IPC call (`main.js`, `preload.js`), frontend `fetch`/media/iframe/worker surface, Python WS/HTTP/SQLite/dependency inventory (confirming no FastAPI/Uvicorn at runtime; `websockets==16.0` on `:8001` + stdlib HTTP `:8000` + `sandbox.py`), and static WebView2/CSP incompatibilities.

---

## 2. Remaining Work (Phases 2–5)

### Phase 2 — Rust Core and Tauri IPC Foundation
- **2.1 CSP, Polyfills, Plugins, Capabilities & Shell Commands:**
  - Externalize inline `<script>` polyfill in `frontend/index.html` and fix ESM import hoisting in `main.tsx` / `StudyReaderView.tsx`; clean inline `<script>`/`<style>` in `frontend/public/direct_pdf_test.html`.
  - Configure `frontend/vite.config.ts` (`port: 5173`, `strictPort: true`, `clearScreen: false`).
  - Add `tauri-plugin-dialog` + `tauri-plugin-opener` + `capabilities/preview-sandbox.json` + scoped `main-window.json` (`core:default`, `dialog:allow-open`, `opener:deny-default`, custom command permissions).
  - Add WebView2 autoplay policy switch & Rust commands `system_ping`, `system_info`, `system_open_path` (with `path_jail` & scheme allowlist) + unit tests.
  - Tighten `tauri.conf.json` (`127.0.0.1:5173`, CSP `blob:` in `frame-src` only where needed, fix `ChatPanel.tsx` audio `data:` -> `blob:` URL).
- **2.2 Frontend `TauriTransportAdapter` + Component Unification:**
  - Implement `frontend/src/transport/TauriTransportAdapter.ts` (`invoke`, `listen`, `Channel<T>`, native dialog, drag-drop paths, `openPath`, loopback URL + `?ticket=`).
  - Update `TransportProvider.tsx` & `JarvisTransport.ts` (`resolveDefaultHttpBaseUrl()` safe under `http://tauri.localhost`).
  - Migrate the remaining 12 components + `main.tsx` off direct `useWebSocket` coupling to unified `useTransport()`.
  - Add `npm test` script in `frontend/package.json` and expand `transport.test.ts` to cover `TauriTransportAdapter`.
- **2.3 Rust Internal Loopback HTTP (`127.0.0.1:0`) & Isolated IDE Preview Server:**
  - Implement `permissions/path_jail.rs`, `storage/atomic_fs.rs`, `protocol/loopback.rs` (`axum` + `http-range-header`, Bearer + 60s `?ticket=`, `Host` DNS-rebinding guard, `Origin` check, Range `206`, strict MIME), `process/preview_server.rs` (`X-Content-Type-Options: nosniff`, sandboxed iframe), and `get_media_ticket` / `get_loopback_config` commands + full integration tests.

### Phase 3 — Functional Migration from Python to Rust
- **3.1 Rust Worker Supervisor + NDJSON JSON-RPC 2.0 + Win32 Job Objects + `workers/worker_boot.py`:**
  - `process/job_object.rs` (`CREATE_SUSPENDED` + `AssignProcessToJobObject(KILL_ON_JOB_CLOSE)`), `workers/{supervisor,rpc_client,pools}.rs`, 5s/15s heartbeat, bounded `mpsc(1024)` backpressure, 16ms `stream.chunk` micro-batching, `task.cancel`, Reverse RPC HITL (`reverse_request`/`reverse_response`), and Python `workers/common/{stdio_rpc,health}.py` with `os.dup(1)` + `sys.stdout = sys.stderr`.
- **3.2 Rust SQLite Core (`database.db` Single Writer) + Study Catalog Store:**
  - `storage/{sqlite,migrations,study_store}.rs` (`rusqlite` bundled WAL actor, `user_version` migrations preserving existing rows, `documents.json`/`collections.json` atomic store), cross-checking RHO cutover safety (`data/rho.db` tested on disposable/CI copies; `state.db` retained permanently in Python).
- **3.3 Security Hardening in Rust Core:**
  - `process/command_guard.rs` (lexer + closed allowlist replacing `workspace_policy.py` & PowerShell `& { ... }`), `permissions/{gateway,policy}.rs` (fail-closed 300s TTL HITL via Reverse RPC), SSRF DNS+IP pinning guard (`video_intelligence_service.py` + Rust), `atomic_write` across all 22 non-atomic write sites, `sentinel/{scheduler,collectors_win}.rs` (`shadow_mode=True` default, dynamic PID tree allowlist), secret isolation in Rust Core.
- **3.4 Domain IPC Commands & Specialized Python Workers:**
  - `commands/{chat,projects,permissions,study,knowledge,sentinel,missions,voice,system}.rs`, Rust FS/runner in `projects.rs`, Python workers (`workers/{ai_worker,study_worker,knowledge_worker,mission_worker,voice_swarm_worker}.py`), resolve 33 `missions.py` stubs & 14 dead branches (`mission_governance_dispatch`).

### Phase 4 — Legacy Infrastructure Removal (on `migration/tauri-rust-complete`)
- Consolidate `agents/` vs `backend/agents/` via `sys.modules` shim + AST codemods verified by `pytest`, prune dead `agents/` / telemetry.
- Remove legacy WS server (`:8001`), stdlib HTTP server (`:8000`), `0.0.0.0:8080` server, `backend/transport_gateway.py`, and `_free_port_if_locked`.
- Remove transitional `:8000`/`:8001`/`localhost` entries from `tauri.conf.json` CSP & retire Electron shell (`main.js`, `preload.js`, `electron` deps/scripts) cleanly on migration branch.

### Phase 5 — Stabilization, Regression Validation & Documentation
- Run full Rust `cargo test`, Python `pytest`, frontend `vite build` + `node --test`, and headless WebView2 CDP E2E + startup/RSS/orphan verification on `windows-latest`.
- Update core documentation (`ARCHITECTURE.md`, `SECURITY.md`, `README.md`, `CHANGELOG.md`, `docs/PROJECT_MAP.md`, `docs/decisions/`) and pass `tests/test_documentation_integrity.py`.
- Deliver consolidated final migration report.

---

## 3. Baseline Test Results (Observed)

- **Python Stage 1 / Contract Baseline (`venv\Scripts\python.exe -m pytest -q tests/test_sqlite_hardening.py tests/test_rho_migration_sandbox.py tests/test_protocol_contracts.py tests/test_model_service_compliance.py tests/test_model_transport_architecture.py tests/test_websocket_dispatcher_contract.py tests/test_server_websocket_characterization.py tests/test_transport_gateway.py tests/test_documentation_integrity.py`):**
  - **Result:** `58 passed, 1 skipped, 2 warnings, 281 subtests passed in 32.89s` (`exit_code=0`).
- **Frontend Transport (`npx tsc -p frontend/tsconfig.test.json --noEmit` + `node --experimental-strip-types --test src/transport/__tests__/transport.test.ts`):**
  - **Result:** `9/9 passed (1 suite, 0 fail, 164.1ms)` (`exit_code=0`).
- **Frontend Build (`npm --prefix frontend run build`):**
  - **Result:** `3531 modules transformed, ✓ built in 3.63s` (local) / `7.01s` (CI) (`exit_code=0`).
- **CI Rust Baseline (Run `#43338081076` on `stage2.1/tauri-windows-ci` @ `732383e`):**
  - `cargo check --locked --all-targets`: passed (`1m 58s`).
  - `cargo test --locked`: passed (`1 passed; 0 failed` — `shell_constants_match_stage2_identity`).
  - `tauri build --no-bundle`: passed (`jarvis-os.exe`, `12,956,160` B).
  - `tauri build`: passed (`MSI` `6.84 MiB`, `NSIS` `5.89 MiB`).

---

## 4. Known Issues & Architectural Decisions

- **Local OS Code Integrity Blocker:** Windows **Smart App Control** (`SmartAppControlState: On`, `os error 4551`) blocks local execution of unsigned Rust build scripts/binaries (`cargo check`, `cargo test`, `tauri:dev`). Mitigation: never weaken/bypass local OS security; execute Rust compilation, `cargo test`, `tauri build`, and headless WebView2 CDP E2E tests in GitHub Actions `windows-latest`. Any final **manual interactive visual desktop test** on the user's PC requires an environment without Smart App Control blocking unsigned local binaries or signed artifacts (kept non-blocking for `main` because `main` stays untouched at `af11ae9`).
- **Static Frontend/CSP Gaps Found in Phase 1 Audit:**
  1. `frontend/index.html` L7–111 inline `<script>` & `direct_pdf_test.html` inline `<script>`/`<style>` blocked by `script-src 'self' 'wasm-unsafe-eval'`; `main.tsx` / `StudyReaderView.tsx` polyfills evaluated after static ESM imports due to JS module hoisting.
  2. `StudyGeneratedDocumentView.tsx` uses `<iframe src="blob:...">` (blocked unless `blob:` is in `frame-src` or served cleanly) and synchronous `URL.revokeObjectURL` right after `.click()`.
  3. `ChatPanel.tsx` plays `new Audio('data:audio/mp3;base64,...')` (`media-src` lacks `data:` -> convert cleanly to `blob:` URL, already permitted by `media-src 'self' blob:`) and needs WebView2 autoplay policy switch.
  4. `resolveDefaultHttpBaseUrl()` in `JarvisTransport.ts` returns `http://tauri.localhost` in Tauri builds, breaking `/api/study/...` requests until wired to Rust Loopback HTTP (`127.0.0.1:0`) + `?ticket=`.
  5. Remaining 12 UI files still import `useWebSocket` rather than `useTransport`.
  6. `backend/websocket/handlers/missions.py` retains 33 unimplemented stub keys and 14 unregistered legacy branches.
- **Architectural Decisions Locked:** Preserve Q1–Q12 (`database.db` Rust single-writer in Phase 3, `state.db` permanent Python, `data/rho.db` permanent Python `ModelHarness` after safe migration tooling, `ModelExecutionService` & Python workers for PyMuPDF/OCR/FFmpeg/Whisper/ChromaDB/CrewAI/GeminiLive/Ollama, NDJSON JSON-RPC 2.0 + `os.dup(1)` + Win32 Job Objects, Rust Loopback HTTP `127.0.0.1:0` with Bearer + 60s `?ticket=`).
- **Git & Data Safety Rule:** User's local `data/` and `database.db*` remain untracked/unstaged and are NEVER committed, reset, or modified by migration tooling during automated runs (DB tests operate strictly on disposable copies / temp roots).

---

## 5. Next Executable Task

- **Begin Phase 2 — Increment 2.1:**
  1. Update `.github/workflows/tauri-windows-validation.yml` to run on `migration/**`, add `Swatinem/rust-cache@v2`, add frontend `node --test` and Python contract `pytest` jobs so CI validates Rust + Python + Frontend on every push cleanly.
  2. Fix `frontend/index.html`, `frontend/src/polyfills.ts`, `frontend/src/main.tsx`, `frontend/src/features/study/StudyReaderView.tsx`, `frontend/public/direct_pdf_test.html`, `frontend/vite.config.ts`, `frontend/src/features/chat/ChatPanel.tsx` (`blob:` TTS URL), and `frontend/src/features/study/StudyGeneratedDocumentView.tsx` (deferred `revokeObjectURL`) for strict Tauri CSP compliance.
  3. Configure `src-tauri/` Phase 2.1 foundation (`Cargo.toml` plugins `dialog`/`opener`, `capabilities/main-window.json`, `capabilities/preview-sandbox.json`, `tauri.conf.json` tightened CSP + `127.0.0.1:5173`, `src-tauri/src/lib.rs` WebView2 autoplay arg + `system_ping`, `system_info`, `system_open_path` with `path_jail` + unit tests).

---

## 6. Outstanding External Dependencies

- Local machine cannot execute unsigned compiled Rust binaries due to Windows Smart App Control (`os error 4551`); remote GitHub Actions (`windows-latest`) serves as the active Windows Rust/Tauri/WebView2 CI runner.
- User approval will be requested only after Phase 5 completes cleanly before any merge into `main` (or if an interactive human Windows UI sign-off is required).
