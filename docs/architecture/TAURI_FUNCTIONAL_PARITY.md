# JARVIS OS — 26-CAPABILITY FUNCTIONAL PARITY & REGRESSION MATRIX
**Document Version:** 1.0.0  
**Status:** Stage 0.1 Baseline Audit  
**Scope:** End-to-End Preservation of Functional Capabilities Across Electron -> Tauri 2 Migration

---

## 1. PURPOSE

This matrix ensures that migrating from Electron + Python/WebSockets to Tauri 2 + Rust Core + Python Workers achieves **100% functional parity** with zero feature regression. Every existing capability in the baseline commit (`fb1aeeda10652ed1662e7e5c24ed381d7635f8d0`) is mapped to its current implementation, target implementation, migration risk, and required verification gate.

---

## 2. CAPABILITY PARITY MATRIX (26 CORE CAPABILITIES)

| # | Capability Area | Current Baseline (Electron + Python WS) | Target Baseline (Tauri 2 + Rust + Python Worker) | Target Stage | Regression Risk | Verification Gate |
|---|---|---|---|---|---|---|
| **01** | **Chat & Conversation History** | React `WebSocketContext.tsx` -> WS `:8001` -> Python `server.py` -> `database.db` (`messages`, `sessions`) | UI (`JarvisTransport`) -> Tauri Invoke -> Rust SQLite (single writer) + Worker dispatch | Stage 3–4 | Medium | `test_redesign_consolidation_e2e.py` + Chat parity integration suite |
| **02** | **Model Execution & Ollama Harness** | Python `ModelExecutionService` & `ModelHarness` (12 self-healing subsystems, GPU semaphore, SHE/RHO) -> Ollama `:11434` | **Retained in Python** (`ModelExecutionService` + `ModelHarness`); no naive Rust rewrite | Stage 4 | Low (preserved) | `test_model_transport_architecture.py` (after fixing `obsidian_graph_engine.py:1495` violation) |
| **03** | **Token & Response Streaming** | Batch / pseudo-stream over WS `:8001` (UI currently awaits completed chunks or simple stream events) | Micro-batched NDJSON `stream.chunk` notifications -> Rust Tauri Event fanout -> UI | Stage 2–4 | Low | Streaming latency benchmark (< 16ms UI update jitter) |
| **04** | **Voice & Audio I/O** | Python audio capture / Whisper / TTS pipeline via WS | Python audio worker + WebView2 `MediaStream` or Rust CPAL/Pipe IPC for PCM buffers | Stage 5 | High | Microphone permission check in WebView2 + E2E latency test |
| **05** | **Autonomous Missions Engine** | `backend/websocket/handlers/missions.py` (`MISSION_HANDLERS`: 129 entries, 33 no-op gaps) | Cleaned `missions.py` inside Python Worker, reverse RPC for tool HITL | Stage 5 | High | Audit & resolution of the 33 unimplemented mission handlers |
| **06** | **Multi-Agent Swarm** | `backend/agents/` orchestrating specialist agents (30 dormant duplicates in `agents/`) | Pruned `backend/agents/` inside Python Worker; dead duplicates quarantined/removed | Stage 5 | Medium | Swarm coordination & delegation multi-agent suite |
| **07** | **Project Management & Discovery** | `ProjectsLandingView.tsx` + `database.db` (`projects`) + filesystem scanning | Rust Core reads/writes `projects` table & scans workspaces natively with Path Jail | Stage 3–4 | Low | Workspace scan benchmark (< 50ms) + Path traversal tests |
| **08** | **Integrated Code Editor** | Monaco Editor `0.56` in `WorkspaceViewer.tsx` + WS `fs_*` handlers | Monaco Editor `0.56` + Rust `tauri-plugin-fs` / custom Tauri commands with Path Jail | Stage 3 | Low | File load, save, rename, diff & undo integrity tests |
| **09** | **Preview Sandbox & Static Server** | Python `sandbox_service.py` binding `0.0.0.0:8080` with token verification | **Rust Loopback HTTP Server (`127.0.0.1:0`)** with ephemeral port & Range 206 support | Stage 3 | Medium | Fix `0.0.0.0` exposure; verify HMR/static iframe rendering in WebView2 |
| **10** | **Study Engine — Document Library** | `services/study_fs.py` (atomic temp+replace) + SQLite metadata | Rust Core / Python Worker coordinated via atomic FS & SQLite WAL (`busy_timeout=10000`) | Stage 4–5 | Medium | Concurrent ingestion + library listing stress test |
| **11** | **Study PDF Reader** | `pdfjs-dist` `6.3` in frontend fetching PDF via Python HTTP sandbox/WS | `pdfjs-dist` `6.3` fetching PDF via **Rust Loopback HTTP (`127.0.0.1:0`)** (`jarvis-media://` avoided due to worker origin bugs) | Stage 3 | Low | Large PDF (>100MB) render, `pdf.worker.min.mjs` execution, page jump |
| **12** | **Study Video Reader** | `StudyVideoReaderView.tsx` (imports `useWebSocket` directly for progress/notes) | Refactored to `JarvisTransport` + **Rust Loopback HTTP Range 206** for smooth MP4 scrubbing | Stage 1–3 | High | MP4 Range 206 seeking & scrubbing stress test without freezes |
| **13** | **OCR & Multi-Modal Extraction** | Python `PyMuPDF` `1.26.7`, Whisper, FFmpeg pipelines | **Retained in Python** specialized media/OCR worker via NDJSON progress frames | Stage 5 | Low | Frame extraction, OCR text accuracy, progress cancellation test |
| **14** | **Docgen & Synthesis (Qwen 3.5)** | `docgen` pipelines in Python (deterministic fallback vs generative `qwen3.5:9b`) | **Retained in Python** AI worker invoking `ModelExecutionService` | Stage 4–5 | Low | Validate fallback transparency & generative synthesis quality |
| **15** | **Active Learning Modes** | Cornell Notes, Flashcards, Quiz, Active Recall views via Study handlers | Preserved React views calling `JarvisTransport.study` -> Python Study Worker | Stage 5 | Low | Cornell export to Obsidian & quiz state persistence tests |
| **16** | **Obsidian Vault & Knowledge Graph** | `obsidian_graph_engine.py` + `knowledge.py` (`KNOWLEDGE_HANDLERS`) | Vault indexing in Rust/Python; fix direct Ollama bypass at `obsidian_graph_engine.py:1495` | Stage 4–5 | Medium | Graph traversal latency & direct HTTP call elimination verification |
| **17** | **Sentinel Watchdog & Response** | `security/sentinel/watchdog.py` (6 collectors, 5 executors, `shadow_mode=True`) | Rust system metrics collector + Python behavioral engine (`shadow_mode` configurable) | Stage 6 | Medium | Alert generation, history persistence (fixing `engine.py:73` non-atomic write) |
| **18** | **Permission Gateway & HITL** | `security/permission_gateway/gateway.py` (blocking WS prompt to UI) | Rust `PermissionGateService` + **Reverse RPC (`reverse_request`)** for Python tools | Stage 4 | Critical | Deadlock verification: concurrent UI permission modal + active agent execution |
| **19** | **Native File & Folder Dialogs** | `main.js` Electron `dialog.showOpenDialog` via `preload.js` `jarvisIPC` | Rust `tauri-plugin-dialog` invoked via `JarvisTransport.system` | Stage 2 | Low | Windows native file/folder picker filter parity check |
| **20** | **External URL & App Opening** | `main.js` `shell.openExternal` (with URL scheme checks) | Rust `tauri-plugin-opener` with strict `http://`, `https://` allowlist | Stage 2–6 | Low | Malicious URI scheme block (`ms-msdt:`, `file://`, `javascript:`) |
| **21** | **Frontend Local Storage & State** | WebView Chromium `localStorage` bound to `http://localhost:5173` / Electron origin | Tauri custom origin (`tauri://localhost` or `http://tauri.localhost`) + migration script | Stage 2 | Medium | One-time migration or explicit notice for Electron -> Tauri WebView2 storage origin |
| **22** | **SQLite Persistence & Trajectories** | `database.db` (`delete` mode, FK=0, 0 indices) + `state.db` (WAL, 12 tables) | **Approach C:** Harden Python (`WAL`, `busy_timeout`, `rho.db` split); Rust single-writer for `database.db` | Stage 1–4 | Critical | Zero `SQLITE_BUSY` under parallel load; composite index on `model_trajectories` |
| **23** | **Session & Crash Recovery** | `main.js` spawns Python up to 3 restarts (1500ms delay), 5000ms SIGINT timeout | Rust Watchdog monitors worker heartbeats (5s interval / 15s timeout), auto-restarts via Job Object | Stage 4 | Medium | `taskkill /F` worker recovery test without UI crash |
| **24** | **Telemetry, Audit & Logging** | Mixed `print()`, Python logging, Electron stdout parsing | `os.dup(1)` + `sys.stdout = sys.stderr` isolation -> Rust `tracing` rotating logs | Stage 2 | Low | Verify 3rd-party `print()` does not corrupt JSON-RPC framing |
| **25** | **App Startup & Graceful Shutdown** | `main.js` / `server.py` aggressive `freePortIfLocked` killing PIDs on `:8000` / `:8001` | **Eliminate port killing entirely**; use stdio pipes + ephemeral loopback `:0` + Windows Job Object (`KILL_ON_JOB_CLOSE`) | Stage 2–7 | High | Zero orphaned `python.exe` processes on crash/close; multi-instance isolation |
| **26** | **Transport & Message Protocol** | Monolithic `WebSocketContext.tsx` (4,302 lines, 101 client msgs, 20 missing TS types, 144 unhandled server msgs) | Modular `JarvisTransport` adapter (WS adapter -> Tauri IPC adapter) + strict Zod/TS contracts | Stage 1–2 | Critical | Contract sync tests enforcing 1:1 Client/Server union completeness |

---

## 3. HIGH-RISK PARITY REMEDIATION REQUIREMENTS

Before Stage 2 (Tauri Bootstrap) begins, the following parity hazards must be mitigated:
1. **Direct WebSocket Coupling (`StudyVideoReaderView.tsx`):** Currently imports `useWebSocket` directly rather than using a clean service boundary. Refactor to `JarvisTransport` in Stage 1.
2. **Media Seeking & Origin Isolation (`jarvis-media://` vs `127.0.0.1:0`):** WebView2 exhibits known defects with Range requests (`206 Partial Content`) and Web Worker initialization (`pdf.worker.min.mjs`) on custom protocols. **Decision:** Standardize both Study Video and Study PDF delivery on the **Rust Loopback HTTP server (`127.0.0.1:0`)** with bearer session tokens.
3. **Aggressive Port Killing (`_free_port_if_locked`):** Removing TCP ports `:8000` and `:8001` eliminates Electron startup race conditions and prevents killing unrelated system tools occupying port 8000/8001.
4. **Silent Handler Drift (33 Mission Handlers & 144 Unhandled UI Events):** The protocol consolidation in Stage 1 must reconcile orphaned handlers before building Rust IPC bindings, avoiding porting dead code.

