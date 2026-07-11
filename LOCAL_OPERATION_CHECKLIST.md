# Local Production Operation Checklist

Before starting:

- Confirm `.env` exists locally and does not get committed.
- Confirm backend dependencies were installed with `.\venv\Scripts\python.exe -m pip install -r requirements.txt`.
- Confirm frontend dependencies were installed with `npm install --prefix frontend`.
- Confirm `npm run build --prefix frontend` has produced `frontend/dist/index.html`.

Startup:

- Start the Electron app with the normal local command.
- Confirm structured backend logs show `frontend_static.started`, `runtime.health` and `websocket.server.starting`.
- Confirm the WebSocket host is `127.0.0.1:8001`.
- Confirm frontend static health responds at `http://127.0.0.1:8000/healthz`.
- Confirm sandbox health responds at `http://127.0.0.1:8080/healthz` when the sandbox server is active.

Daily validation:

- Run `.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`.
- Run `.\venv\Scripts\python.exe -m pip check`.
- Run `npm run lint --prefix frontend`.
- Run `npm run build --prefix frontend`.
- Run `node --check main.js`.

Shutdown:

- Close the Electron window normally.
- Confirm logs show `backend.stopping` followed by `backend.closed`.
- Confirm no external process is killed by port ownership.
- If forced shutdown is needed, confirm it targets only the tracked Python backend PID.

Operational cautions:

- Do not paste API keys, bearer tokens or passwords into prompts intended for logs.
- Treat `database.db`, `chroma_db/`, `.env`, logs and generated runtime state as local-only artifacts.
- If health status is `degraded`, inspect the affected component before continuing daily use.
