# JARVIS OS — Autonomous Migration State

- **Last Updated (UTC):** `2026-11-13T01:33:00Z`
- **Current Phase:** `Phase 2 — Rust Core and Tauri IPC foundation (Increments 2.1, 2.2 COMPLETE; 2.3 Implemented — Validating on Windows CI)`
- **Current Increment:** `Increment 2.3 Implemented -> Pushing migration/tauri-rust-complete for Windows CI Validation before Phase 3`
- **Current Branch:** `migration/tauri-rust-complete`
- **Current Commit:** `148bef0` + Increment 2.3 changes (base `main`: `af11ae9095f4cfd8c8e01334704ffde282da9554`, untouched)

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
- **2.3 Rust Loopback HTTP (`127.0.0.1:0`), Isolated IDE Preview & Atomic FS (IMPLEMENTED LOCALLY — Validating on Windows CI):**
  - Added `tokio`, `tokio-util`, `axum`, `http`, `bytes`, `http-range-header`, `hmac`, `sha2`, `hex`, `rand`, `tempfile`, `url` to `src-tauri/Cargo.toml` and locked via `cargo fetch`.
  - Added `ensure_confined_existing_file`, `is_blocked_system_path`, and `is_safe_identifier` helpers to `src-tauri/src/permissions/path_jail.rs`.
  - Implemented `src-tauri/src/storage/atomic_fs.rs` (`atomic_write_bytes`, `atomic_write_string`, `read_bounded_bytes` + unit tests).
  - Implemented `src-tauri/src/protocol/{http_common,loopback}.rs` (ephemeral `127.0.0.1:0` Axum server, `OsRng` 64-hex Bearer token, constant-time HMAC comparison, 60s `doc_id`-scoped `?ticket=`, `Host`/`Origin`/`Sec-Fetch-Site` DNS-rebinding guards, `ReaderStream` HTTP `206 Partial Content`/`416`/`HEAD`, strict MIME + `X-Content-Type-Options: nosniff` + TCP wire integration tests).
  - Implemented `src-tauri/src/process/preview_server.rs` (isolated ephemeral `127.0.0.1:0` preview server with `Host` guard + symlink/traversal confinement + `X-Content-Type-Options: nosniff` + `Cache-Control: no-store` + TCP integration tests).
  - Exposed Tauri commands `get_loopback_config` and `get_media_ticket` via managed `RuntimeServices` in `src-tauri/src/commands/media.rs` + `src-tauri/src/lib.rs`, added `http://127.0.0.1:*` to `connect-src`/`worker-src` in `tauri.conf.json`, and added `sandbox="allow-scripts allow-forms"` to `WorkspaceViewer.tsx` preview `<iframe>` elements.

---

## 2. Remaining Work (Phases 2.3–5)

### Phase 2 — Rust Core and Tauri IPC Foundation (Remaining)
- **2.3 Rust Internal Loopback HTTP (`127.0.0.1:0`) & Isolated IDE Preview Server:**
  - Implement `storage/atomic_fs.rs`, `protocol/loopback.rs` (`axum` + `http-range-header`, Bearer + 60s `?ticket=`, `Host` DNS-rebinding guard, `Origin` check, Range `206`, strict MIME), `process/preview_server.rs` (`X-Content-Type-Options: nosniff`, sandboxed iframe), and `get_media_ticket` / `get_loopback_config` commands + full integration tests; push branch and validate cleanly on GitHub Actions `windows-latest`.

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
- **Python Post-2.3 Check (`venv\Scripts\python.exe -m pytest -q tests/test_sqlite_hardening.py tests/test_rho_migration_sandbox.py tests/test_documentation_integrity.py tests/test_transport_gateway.py tests/test_websocket_dispatcher_contract.py`):** `37 passed, 1 skipped, 276 subtests passed in 9.84s` (bare Python lightweight subset: `28 passed, 1 skipped in 9.33s`).
- **Frontend Transport (`npm --prefix frontend test`):** `14/14 passed (4 suites, 0 fail)` (`240ms`).
- **Frontend Build (`npm --prefix frontend run build`):** `3545 modules transformed, ✓ built in 3.70s` (`exit_code=0`).
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
  2. Fixed in 2.1: `StudyGeneratedDocumentView.tsx` uses `<iframe src="blob:...">` (allowed in `frame-src` + deferred `URL.revokeObjectURL`).
  3. Fixed in 2.1: `ChatPanel.tsx` plays TTS audio via `blob:` URLs + `--autoplay-policy=no-user-gesture-required`.
  4. Fixed in 2.2: `resolveDefaultHttpBaseUrl()` blocks `tauri.localhost`/`tauri://`; `TauriTransportAdapter` resolves `get_loopback_config` & `get_media_ticket` once 2.3 backend activates.
  5. Fixed in 2.2: All 12 UI components + `main.tsx` migrated onto transport-agnostic `AppSessionContext`.
  6. Remaining for Phase 3.4: `backend/websocket/handlers/missions.py` retains 33 unimplemented stub keys and 14 unregistered legacy branches.
- **Architectural Decisions Locked:** Preserve Q1–Q12 (`database.db` Rust single-writer in Phase 3, `state.db` permanent Python, `data/rho.db` permanent Python `ModelHarness` after safe migration tooling, `ModelExecutionService` & Python workers for PyMuPDF/OCR/FFmpeg/Whisper/ChromaDB/CrewAI/GeminiLive/Ollama, NDJSON JSON-RPC 2.0 + `os.dup(1)` + Win32 Job Objects, Rust Loopback HTTP `127.0.0.1:0` with Bearer + 60s `?ticket=`).
- **Git & Data Safety Rule:** User's local `data/` and `database.db*` remain untracked/unstaged and are NEVER committed, reset, or modified by migration tooling during automated runs (DB tests operate strictly on disposable copies / temp roots).

---

## 5. Next Executable Task

- **Validate Phase 2 Increment 2.3 on Windows CI (`migration/tauri-rust-complete`), verify full `cargo check`/`cargo test`/`tauri build --no-bundle` logs, fix any warnings/errors, mark Phase 2 Complete, and start Phase 3 — Increment 3.1 (Rust Worker Supervisor + NDJSON JSON-RPC 2.0 + Win32 Job Objects + `workers/worker_boot.py`).**

---

## 6. Outstanding External Dependencies

- Local machine cannot execute unsigned compiled Rust binaries due to Windows Smart App Control (`os error 4551`); remote GitHub Actions (`windows-latest`) serves as the active Windows Rust/Tauri/WebView2 CI runner.
- User approval will be requested only after Phase 5 completes cleanly before any merge into `main` (or if an interactive human Windows UI sign-off is required).

