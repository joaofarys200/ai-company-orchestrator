# Runtime Validation Checklist

Phase 1 stabilization smoke checks:

- `python -c "import server; print('IMPORT_SERVER_OK')"`
- `python -c "import agents.swarm as s; print(type(s.local_llm).__name__)"`
- `python -c "import agents.orchestrator as o; import inspect; print(inspect.signature(o.spawn_specialist_agent))"`
- `npm run build --prefix frontend`
- `npm run lint --prefix frontend`

Manual runtime checks:

- Start backend with `VOICE_MODE=none` and confirm ports 8000, 8001 and 8080 start or report a clear port conflict.
- Connect the frontend and verify `ui`, `ui_action` and `ui_theme` messages do not get ignored.
- Trigger a simple `list_active_windows` or `capture_screen` tool call and confirm no `NameError` is raised.

Phase 2 operational security checks:

- Confirm the WebSocket starts on `127.0.0.1:8001`, not `0.0.0.0:8001`.
- Connect with `ws://127.0.0.1:8001/?token=<JARVIS_WS_TOKEN>` or the local fallback `local-dev-token`.
- Connect without a token and confirm the backend closes the WebSocket with policy violation code `1008`.
- Call `execute_command` with a safe command such as `python --version` and confirm it still runs inside the workspace.
- Call `execute_command` with `taskkill`, `Remove-Item`, `git reset --hard` or `../` and confirm it is blocked.
- Call `write_file`, `read_file` and `list_directory` with `../blocked.txt` and confirm access outside the workspace is blocked.
- Close the Electron app while another process owns port `8000` or `8001` and confirm the app does not kill that external process.

Phase 3 reproducible configuration checks:

- Confirm a clean Windows setup creates the virtualenv with `python -m venv venv`.
- Confirm the backend is always validated with `.\venv\Scripts\python.exe`, not the global `python`.
- Install backend dependencies with `.\venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Install Playwright browser assets with `.\venv\Scripts\python.exe -m playwright install chromium`.
- Confirm `.\venv\Scripts\python.exe -m pip check` passes, including the `composio-core` / `argparse` dependency.
- Confirm `.\venv\Scripts\python.exe -c "import server; print('IMPORT_SERVER_OK')"` passes.
- Confirm `.env.example` exists and contains no real API keys.
- Confirm `.gitignore` excludes `.env`, `venv/`, `node_modules/`, `frontend/dist/`, databases, logs, caches and generated runtime state.
- Install frontend dependencies with `npm install` and `npm install --prefix frontend`.
- Confirm `npm run build --prefix frontend` passes.
- Run `npm run lint --prefix frontend` and record remaining lint issues if any.

WebSocket contract checks:

- Confirm `websocket_schema.py` imports and normalizes `chat`, `state`, `file`, `kanban`, `project_output`, `rules_list`, `rules_updated`, `planner_state`, `ui`, `ui_action` and `ui_theme`.
- Confirm `frontend/src/types/websocket.ts` exports the equivalent `ServerMessage` and `ClientMessage` unions.
- Confirm `WebSocketContext.tsx` parses inbound data through `normalizeServerMessage` before switching on `msg.type`.
- Send an unknown server message type in a smoke test and confirm the frontend logs one controlled warning instead of failing silently.
- Connect to the WebSocket with the local token and confirm initial `system`, `template_changed`, `rules_list`, `architecture_list`, `decisions_list` and `notes_list` messages still render.
- Confirm `ui`, `ui_action` and `ui_theme` continue to trigger the same UI behavior as before.

Phase 5 minimum tests and lint checks:

- Run `.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"` and confirm smoke tests pass.
- Confirm backend import smoke validates `server.WS_HOST == "127.0.0.1"` and a non-empty WebSocket token.
- Confirm WebSocket smoke tests cover normalization for `chat`, `state`, `file`, `kanban`, `project_output`, `rules_list`, `planner_state`, `ui`, `ui_action`, `ui_theme` and unknown message types.
- Confirm WebSocket auth smoke accepts query/header tokens and rejects missing or invalid tokens.
- Confirm command policy smoke allows a safe command and blocks deletion, process termination, parent-directory traversal and external absolute paths.
- Confirm path policy smoke resolves workspace paths and blocks parent-directory traversal and external absolute paths.
- Confirm database smoke uses a temporary SQLite file and exercises session, message, project, compounding rules, architecture memory and engineering decision functions.
- Run `npm run lint --prefix frontend` and confirm it passes, including `WorkspaceViewer.tsx`.
- Run `npm run build --prefix frontend` and confirm it passes.
- Run `.\venv\Scripts\python.exe -m pip check` and confirm it passes.

Phase 7 local production hardening checks:

- Confirm `database.py` no longer uses `datetime.utcnow()` and stores timezone-aware UTC timestamps.
- Confirm backend logs are emitted through structured JSON logging for startup, WebSocket, health, sandbox and database events.
- Confirm `server.build_runtime_health()` reports `backend`, `websocket`, `sandbox` and `frontend_static` components.
- Confirm frontend static health is available at `http://127.0.0.1:8000/healthz` after backend startup.
- Confirm sandbox health is available at `http://127.0.0.1:8080/healthz` when the local fallback or static sandbox is serving.
- Confirm UI-visible backend errors are sanitized and do not include API keys, bearer tokens or local user home paths.
- Close the Electron app and confirm the Python backend receives a graceful stop attempt before any forced termination.
- Simulate an unexpected backend exit and confirm Electron restarts only its own tracked Python process, with a bounded restart count.
- Confirm Electron logs do not print full local Python paths or secret values.
- Run `node --check main.js` to validate Electron main-process syntax.
- Run `.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`.
- Run `.\venv\Scripts\python.exe -m pip check`.
- Run `npm run lint --prefix frontend`.
- Run `npm run build --prefix frontend`.
