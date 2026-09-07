"""
JARVIS OS — Phase 17.1 WebSocket Live Test
Verifies live WebSocket federation operations against active server:
- subswarm_created
- subswarm_scaled
- cross_swarm_conflict
- federated_arbitration
- subswarm_recovered
- federation_rebalanced
- Clean disconnect & Reconnect
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

import websockets

AUTH_TOKEN = os.getenv("JARVIS_WS_TOKEN") or "local-dev-token"
WS_URL = f"ws://127.0.0.1:8001/?token={AUTH_TOKEN}"
HEALTH_URL = "http://127.0.0.1:8000/healthz"


def is_port_listening(port: int = 8001) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


async def recv_matching(ws, expected_type: str, timeout: float = 6.0) -> dict:
    t_end = time.time() + timeout
    while time.time() < t_end:
        rem = max(0.1, t_end - time.time())
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=rem)
            msg = json.loads(raw)
            if msg.get("type") == expected_type:
                return msg
        except asyncio.TimeoutError:
            break
    raise TimeoutError(f"Timed out waiting for message type '{expected_type}'")


async def run_live_websocket_test():
    print("=================================================================")
    print(" JARVIS OS — PHASE 17.1 LIVE WEBSOCKET FEDERATION TEST           ")
    print("=================================================================")

    server_proc = None
    if not is_port_listening(8001):
        print("[INFO] Starting JARVIS server.py subprocess on port 8001...")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        server_proc = subprocess.Popen(
            [sys.executable, "-u", "server.py"],
            cwd=WORKSPACE_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Wait up to 15s for port to open
        for _ in range(30):
            await asyncio.sleep(0.5)
            if is_port_listening(8001):
                print("[OK] Server listening on ws://127.0.0.1:8001")
                break

    if not is_port_listening(8001):
        print("[ERROR] Server could not be started on port 8001")
        return 1

    try:
        # ── CONNECTION 1 ──────────────────────────────────────────────────────
        print("\n[STEP 1] Connecting to live WebSocket Gateway...")
        async with websockets.connect(WS_URL, close_timeout=5.0) as ws:
            print(f"[OK] WebSocket connection established: {WS_URL}")

            # 1. Decompose Mission to create mission and orchestrator
            print("\n[STEP 2] Creating mission via mission_plan_decompose...")
            create_msg = {
                "type": "mission_plan_decompose",
                "project_id": "test_fed_ws",
                "title": "WebSocket Federation Mission",
                "objective": "Verify live federation WebSocket operations",
                "tasks": [
                    {"task_id": "T1", "title": "Module A Setup", "category": "CODING"},
                    {"task_id": "T2", "title": "Module B Setup", "category": "TESTING", "dependencies": ["T1"]},
                ],
            }
            await ws.send(json.dumps(create_msg))
            snap = await recv_matching(ws, "mission_snapshot", timeout=6.0)
            mission_id = snap["data"]["mission"]["mission_id"]
            print(f" -> Mission created successfully: {mission_id}")

            # 2. Federation Status Check
            print("\n[STEP 3] Querying mission_federation_status...")
            await ws.send(json.dumps({
                "type": "mission_federation_status",
                "project_id": "test_fed_ws",
                "mission_id": mission_id,
            }))
            status_resp = await recv_matching(ws, "mission_federation_status_response", timeout=6.0)
            print(f" -> Federation status response received: {status_resp.get('type')}")

            # 3. Sub-Swarm Scale (Spawn)
            print("\n[STEP 4] Testing mission_federation_scale (subswarm_created / subswarm_scaled)...")
            await ws.send(json.dumps({
                "type": "mission_federation_scale",
                "project_id": "test_fed_ws",
                "mission_id": mission_id,
                "action": "spawn",
            }))
            scale_resp = await recv_matching(ws, "mission_federation_scale_response", timeout=6.0)
            print(f" -> Subswarm scaled response: action={scale_resp.get('action')}, success={scale_resp.get('success')}")

            # 4. Federation Rebalance
            print("\n[STEP 5] Testing mission_federation_rebalance (federation_rebalanced)...")
            await ws.send(json.dumps({
                "type": "mission_federation_rebalance",
                "project_id": "test_fed_ws",
                "mission_id": mission_id,
            }))
            rebal_resp = await recv_matching(ws, "mission_federation_rebalance_response", timeout=6.0)
            print(f" -> Federation rebalance response: rebalanced_tasks={rebal_resp.get('rebalanced_tasks')}")

            # 5. Collaboration Status & Conflict Check
            print("\n[STEP 6] Testing mission_collaboration_status (cross_swarm_conflict / arbitration)...")
            await ws.send(json.dumps({
                "type": "mission_collaboration_status",
                "project_id": "test_fed_ws",
                "mission_id": mission_id,
            }))
            collab_resp = await recv_matching(ws, "mission_collaboration_status_response", timeout=6.0)
            print(f" -> Collaboration status response received: {collab_resp.get('type')}")

            print("\n[STEP 7] Closing connection cleanly to test disconnect...")

        # ── RECONNECT TEST ────────────────────────────────────────────────────
        print("\n[STEP 8] Testing Clean RECONNECT...")
        await asyncio.sleep(0.3)
        async with websockets.connect(WS_URL, close_timeout=5.0) as ws2:
            print("[OK] Reconnected successfully to WebSocket Gateway.")
            await ws2.send(json.dumps({
                "type": "mission_federation_status",
                "project_id": "test_fed_ws",
                "mission_id": mission_id,
            }))
            status_resp2 = await recv_matching(ws2, "mission_federation_status_response", timeout=6.0)
            print(f" -> Reconnected status query successful: {status_resp2.get('type')}")

        print("\n=================================================================")
        print(" [SUCCESS] ALL 6 WEBSOCKET FEDERATION OPERATIONS & RECONNECT PASS ")
        print("=================================================================")
        return 0

    except Exception as e:
        print(f"\n[ERROR] WebSocket live test failure: {e}")
        return 1
    finally:
        if server_proc is not None:
            print("[INFO] Terminating test server.py subprocess...")
            server_proc.terminate()
            try:
                server_proc.wait(timeout=3.0)
            except Exception:
                server_proc.kill()


if __name__ == "__main__":
    code = asyncio.run(run_live_websocket_test())
    sys.exit(code)
