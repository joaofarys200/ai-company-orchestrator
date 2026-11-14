# JARVIS OS — Autonomous Migration State

- **Last Updated (UTC):** `2026-11-14T00:50:45Z`
- **Current Phase:** `Phase 3 — Functional Migration from Python to Rust (Increment 3.4 Implemented -> Validating on Windows CI)`
- **Current Increment:** `Increment 3.4 (33 Mission Governance Dispatchers, 5 Domain Workers, Rust IPC Router & DB/FS Commands, Pure Tauri Default Transport)`
- **Current Branch:** `migration/tauri-rust-complete`
- **Current Commit:** Pending Increment 3.4 commit & CI validation (prior CI green: `bfb585f`, base `main`: `af11ae9095f4cfd8c8e01334704ffde282da9554`, untouched)

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

### Phase 2 — Rust Core and Tauri IPC Foundation (IN PROGRESS)
- **2.1 CSP, Polyfills, Plugins, Capabilities & Shell Commands (COMPLETE — `868f9fc`):**
  - Created `frontend/src/polyfills.ts`; removed inline `<script>` from `frontend/index.html`, removed duplicate hoisted polyfills from `main.tsx` and `StudyReaderView.tsx`; externalized `frontend/public/direct_pdf_test.{css,js}`.
  - Configured `frontend/vite.config.ts` (`127.0.0.1:5173`, `strictPort: true`, `clearScreen: false`).
  - Converted `ChatPanel.tsx` TTS audio playback to `blob:` URLs (`URL.createObjectURL` + cleanup) and deferred `URL.revokeObjectURL` in `StudyGeneratedDocumentView.tsx`.
  - Installed `@tauri-apps/plugin-dialog` & `@tauri-apps/plugin-opener`; locked Rust dependencies (`tauri-plugin-dialog`, `tauri-plugin-opener`, `dunce`) in `src-tauri/Cargo.lock`.
  - Implemented `src-tauri/src/{error,lib}.rs`, `permissions/path_jail.rs`, `commands/system.rs` (`system_ping`, `system_info`, `system_open_path`), WebView2 `--autoplay-policy=no-user-gesture-required`, strict CSP, and least-privilege `main-window.json` / `preview-sandbox.json` capabilities.
- **2.2 Frontend `TauriTransportAdapter` + Platform Detection + Transport Unification (COMPLETE — `148bef0`):**
  - Added `isTauriRuntime()`, `isVirtualDesktopOrigin()`, and hardened `resolveDefaultHttpBaseUrl()` in `JarvisTransport.ts` so `http://tauri.localhost` / `tauri://` never resolve as API hosts.
  - Extracted shared `TransportCorrelationRegistry` (`TransportCorrelation.ts`) used by both `WebSocketTransportAdapter` and `TauriTransportAdapter`.
  - Implemented `TauriTransportAdapter.ts` supporting pure `tauri-ipc` and Phase 2 `tauri-hybrid` coexistence, native `selectFolder` / `selectFile`, `openPath`, WebView2 `onDragDropEvent` path mapping, `get_loopback_config` & `get_media_ticket` caching (`resolveMediaUrlAsync` / `getMediaCandidateUrlsAsync`), and `createDefaultTransport()`.
  - Updated `StudyContainer.tsx`, `StudyLibraryView.tsx`, `StudyReaderView.tsx`, and `StudyVideoReaderView.tsx` (extracted shared `uploadHelpers.ts`) for native Tauri dialogs, native file drop paths, and ticketed media URLs.
  - Decoupled `main.tsx` and all 12 UI components from `useWebSocket` onto `AppSessionContext` (`useAppSession` / `AppSessionProvider`).
  - Added `frontend/src/transport/__tests__/tauriTransport.test.ts` (`14/14` passing).
- **2.3 Rust Loopback HTTP (`127.0.0.1:0`), Isolated IDE Preview & Atomic FS (COMPLETE — `2e478a2`, CI fix `c195ce4`, verified CI Run `#43346899364`):**
  - Added `tokio`, `tokio-util`, `axum`, `http`, `bytes`, `http-range-header`, `hmac`, `sha2`, `hex`, `rand`, `tempfile`, `url` to `src-tauri/Cargo.toml` and locked via `cargo fetch`.
  - Added `ensure_confined_existing_file`, `is_blocked_system_path`, and `is_safe_identifier` helpers to `src-tauri/src/permissions/path_jail.rs`.
  - Implemented `src-tauri/src/storage/atomic_fs.rs` (`atomic_write_bytes`, `atomic_write_string`, `read_bounded_bytes` + unit tests).
  - Implemented `src-tauri/src/protocol/{http_common,loopback}.rs` (ephemeral `127.0.0.1:0` Axum server, `OsRng` 64-hex Bearer token, constant-time HMAC comparison, 60s `doc_id`-scoped `?ticket=`, `Host`/`Origin`/`Sec-Fetch-Site` DNS-rebinding guards, `ReaderStream` HTTP `206 Partial Content`/`416`/`HEAD`, strict MIME + `X-Content-Type-Options: nosniff` + TCP wire integration tests).
  - Implemented `src-tauri/src/process/preview_server.rs` (isolated ephemeral `127.0.0.1:0` preview server with `Host` guard + symlink/traversal confinement + `X-Content-Type-Options: nosniff` + `Cache-Control: no-store` + TCP integration tests).
  - Exposed Tauri commands `get_loopback_config` and `get_media_ticket` via managed `RuntimeServices` in `src-tauri/src/commands/media.rs` + `src-tauri/src/lib.rs`, added `http://127.0.0.1:*` to `connect-src`/`worker-src` in `tauri.conf.json`, and added `sandbox="allow-scripts allow-forms"` to `WorkspaceViewer.tsx` preview `<iframe>` elements.

### Phase 3 — Functional Migration from Python to Rust (COMPLETE pending CI)
- **3.1 Rust Worker Supervisor + Win32 Job Objects + NDJSON JSON-RPC 2.0 + `workers/worker_boot.py` (COMPLETE — `d5e46cd`, verified CI Run `#43348340070`):**
  - Implemented Python worker runtime `workers/{__init__,worker_boot}.py` and `workers/common/{__init__,stdio_rpc}.py` isolating `os.dup(1)` + redirecting `sys.stdout = sys.stderr` prior to imports, with 16 MiB frame limit, `StreamChunkBatcher` (16 ms / 3 chunks), `system.ping`/`system.pong`, `task.cancel`, and non-blocking `reverse_request`/`reverse_response` HITL approval + `tests/test_worker_stdio_rpc.py`.
  - Added `windows-sys` (`Win32_Foundation`, `Win32_Security`, `Win32_System_JobObjects`, `Win32_System_Threading`), `uuid`, `chrono`, and `tokio` `"process"` feature to `src-tauri/Cargo.toml` and locked `Cargo.lock`.
  - Implemented `src-tauri/src/process/job_object.rs` (RAII `JobObject` with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION` + `CREATE_NO_WINDOW` + child termination test).
  - Implemented `src-tauri/src/workers/{mod,rpc_client,supervisor}.rs` (`WorkerRpcClient` with bounded `mpsc(1024)` queue, 5s/15s heartbeat, async `ReverseRpcHandler`, and `WorkerSupervisor` managing `Echo`/`Ai`/`Study`/`Knowledge`/`Mission`/`Voice` roles with backoff auto-restart + 3 live Rust-to-Python integration tests).
  - Exposed `get_worker_health`, `restart_worker_role`, `worker_system_health` in `src-tauri/src/commands/workers.rs` and wired `RuntimeServices.workers` shutdown on `RunEvent::Exit` in `src-tauri/src/lib.rs`.
- **3.2 & 3.3 Rust SQLite Single Writer, StudyStore & Security Hardening (COMPLETE — `bfb585f`, verified CI Run `#43534493463`):**
  - Added `rusqlite` (`0.38`, `features = ["bundled"]`) and `windows-sys` (`ToolHelp` + `SystemInformation`) locked in `src-tauri/Cargo.lock`.
  - Implemented `src-tauri/src/storage/migrations.rs`, `src-tauri/src/storage/sqlite.rs`, and `src-tauri/src/storage/study_store.rs`.
  - Implemented `src-tauri/src/process/command_guard.rs`, `src-tauri/src/protocol/ssrf_guard.rs`, `src-tauri/src/permissions/{policy,gateway}.rs`, `src-tauri/src/sentinel/{mod,collectors_win,scheduler}.rs`, `src-tauri/src/commands/security.rs`, `backend/atomic_io.py`, `services/url_ssrf_guard.py`, and `tests/test_security_hardening_phase3.py`.
  - CI Run `#43534493463` passed all 20 steps cleanly (`frontend test`, `frontend build`, `python-contract-tests`, `cargo check --locked --all-targets`, `cargo test --locked`, `tauri build --no-bundle`).
- **3.4 Governance Resolution, Python Domain Workers & Unified Rust IPC Router (IMPLEMENTED — Validating on Windows CI):**
  - Resolved all 33 previously stubbed mission governance operations via lazy dispatch table `backend/mission_governance_dispatch.py` + fixed `agents/mission_control_engine.py:2754` `LoopDecisionType` import; registered all 14 legacy mission branches in `backend/websocket/handlers/missions.py` (`143` handlers, `0` stubs, `0` unregistered legacy branches); synchronized `backend/websocket/contracts.py`, `websocket_schema.py`, and `tests/test_protocol_contracts.py`.
  - Created `workers/common/domain_bridge.py` (`DomainWorkerRuntime` + `_WorkerEventStreamClient`) and the 5 specialized role workers `workers/{ai,study,knowledge,mission,voice}_worker.py` registered in `workers/worker_boot.py` + `tests/test_domain_workers_phase3.py`.
  - Wired `SqliteDatabase` & `StudyStore` into `RuntimeServices` (`src-tauri/src/commands/media.rs`, `src-tauri/src/lib.rs`), added `permission_record_to_frontend_json` + `"jarvis:event"` Reverse-RPC bridge, fixed `PingResponse` (`ok: true`, `runtime: "tauri-rust"`), and implemented `src-tauri/src/commands/{storage,study,projects,dispatch}.rs` (`dispatch_client_message`, `cancel_client_request`, `trigger_initial_sync`, native fast-paths, confined file IO, and async streaming worker forwarder).
  - Updated `frontend/src/transport/createDefaultTransport.ts` (default `preferHybridFallback: false` in Tauri runtime) and added `cancelNativeRequest` + unit tests in `frontend/src/transport/TauriTransportAdapter.ts` & `frontend/src/transport/__tests__/tauriTransport.test.ts`.
  - Extended `.github/workflows/tauri-windows-validation.yml` to run `tests/test_domain_workers_phase3.py` and `tests/test_protocol_contracts.py`.

---

## 2. Remaining Work (Phases 4–5)

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
- **Python Post-3.3 Local Suite (`venv\Scripts\python.exe -m pytest -q tests/test_security_hardening_phase3.py tests/test_smoke.py tests/test_video_intelligence.py tests/test_study_phase8_qa_e2e.py tests/test_worker_stdio_rpc.py tests/test_sqlite_hardening.py tests/test_rho_migration_sandbox.py tests/test_documentation_integrity.py tests/test_transport_gateway.py`):** `147 passed, 3 skipped, 2 warnings, 12 subtests passed in 13.58s` (`exit_code=0`).
- **Frontend Transport (`npm --prefix frontend test`):** `14/14 passed (4 suites, 0 fail)` (`243.85ms`).
- **Frontend Build (`npm --prefix frontend run build`):** `3545 modules transformed, ✓ built in 3.72s` (`exit_code=0`).
- **3.2 & 3.3 Post-CI Verification (Run `#43534493463` on `migration/tauri-rust-complete` @ `bfb585f`, `conclusion=success`):** All 20 build and test steps (`frontend-test`, `frontend-build`, `python-contract-tests`, `cargo check --locked --all-targets`, `cargo test --locked`, `tauri build --no-bundle`) passed.

---

## 4. Known Issues & Architectural Decisions

- **Local OS Code Integrity Blocker:** Windows **Smart App Control** (`SmartAppControlState: On`, `os error 4551`) blocks local execution of unsigned Rust build scripts/binaries (`cargo check`, `cargo test`, `tauri:dev`). Mitigation: never weaken/bypass local OS security; execute Rust compilation, `cargo test`, `tauri build`, and headless WebView2 CDP E2E tests in GitHub Actions `windows-latest`. Any final **manual interactive visual desktop test** on the user's PC requires an environment without Smart App Control blocking unsigned local binaries or signed artifacts (kept non-blocking for `main` because `main` stays untouched at `af11ae9`).
- **Static Frontend/CSP Gaps Found in Phase 1 Audit:**
  1. `frontend/index.html` L7–111 inline `<script>` & `direct_pdf_test.html` inline `<script>`/`<style>` blocked by `script-src 'self' 'wasm-unsafe-eval'`; `main.tsx` / `StudyReaderView.tsx` polyfills evaluated after static ESM imports due to JS module hoisting.
  2. Fixed in 2.1: `StudyGeneratedDocumentView.tsx` uses `<iframe src="blob:...">` (allowed in `frame-src` + deferred `URL.revokeObjectURL`).
  3. Fixed in 2.1: `ChatPanel.tsx` plays TTS audio via `blob:` URLs + `--autoplay-policy=no-user-gesture-required`.
  4. Fixed in 2.2: `resolveDefaultHttpBaseUrl()` blocks `tauri.localhost`/`tauri://`; `TauriTransportAdapter` resolves `get_loopback_config` & `get_media_ticket`.
  5. Fixed in 2.2: All 12 UI components + `main.tsx` migrated onto transport-agnostic `AppSessionContext`.
  6. Fixed in 3.4: Resolved all 33 stubbed mission governance operations and 14 unregistered legacy mission branches via `backend/mission_governance_dispatch.py`.
- **Architectural Decisions Locked:** Preserve Q1–Q12 (`database.db` Rust single-writer, `state.db` permanent Python, `data/rho.db` permanent Python `ModelHarness`, `ModelExecutionService` & Python workers for PyMuPDF/OCR/FFmpeg/Whisper/ChromaDB/CrewAI/GeminiLive/Ollama, NDJSON JSON-RPC 2.0 + `os.dup(1)` + Win32 Job Objects, Rust Loopback HTTP `127.0.0.1:0` with Bearer + 60s `?ticket=`).
- **Git & Data Safety Rule:** User's local `data/` and `database.db*` remain untracked/unstaged and are NEVER committed, reset, or modified by migration tooling during automated runs (DB tests operate strictly on disposable copies / temp roots).

---

## 5. Next Executable Task

- **Verify Windows CI green for Increment 3.4 (`bfb585f -> HEAD`), then execute Phase 4 (Legacy Infrastructure Removal: consolidate `agents/` vs `backend/agents/`, remove legacy `:8001` WS / `:8000` stdlib HTTP / `:8080` server / `transport_gateway.py`, tighten CSP, and retire Electron files/dependencies on `migration/tauri-rust-complete`).**

---

## 6. Outstanding External Dependencies

- Local machine cannot execute unsigned compiled Rust binaries due to Windows Smart App Control (`os error 4551`); remote GitHub Actions (`windows-latest`) serves as the active Windows Rust/Tauri/WebView2 CI runner.
- User approval will be requested only after Phase 5 completes cleanly before any merge into `main` (or if an interactive human Windows UI sign-off is required).

