from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent


class WorkerStdioRpcSubprocessTests(unittest.TestCase):
    def _spawn_echo_worker(self) -> subprocess.Popen[str]:
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        return subprocess.Popen(
            [sys.executable, "-u", str(REPO_ROOT / "workers" / "worker_boot.py"), "--worker", "echo"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            cwd=str(REPO_ROOT),
            env=env,
        )

    def _read_frame(self, proc: subprocess.Popen[str], timeout_s: float = 5.0) -> dict:
        assert proc.stdout is not None
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if line:
                return json.loads(line)
        raise TimeoutError("Timed out reading NDJSON frame from worker stdout")

    def test_handshake_heartbeat_stdout_isolation_and_streaming(self) -> None:
        proc = self._spawn_echo_worker()
        try:
            assert proc.stdin is not None
            ready = self._read_frame(proc)
            self.assertEqual(ready["method"], "worker.ready")
            self.assertEqual(ready["params"]["worker_type"], "echo")

            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "init-1",
                        "method": "worker.init",
                        "params": {"log_level": "INFO"},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            init_resp = self._read_frame(proc)
            self.assertEqual(init_resp["id"], "init-1")
            self.assertEqual(init_resp["result"]["status"], "initialized")

            # Ping heartbeat returns pong cleanly
            proc.stdin.write(
                json.dumps({"jsonrpc": "2.0", "method": "system.ping", "params": {"sequence": 7}})
                + "\n"
            )
            proc.stdin.flush()
            pong = self._read_frame(proc)
            self.assertEqual(pong["method"], "system.pong")
            self.assertEqual(pong["params"]["sequence"], 7)

            # Call worker.echo with print() noise + streaming chunks
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "req-stream",
                        "method": "worker.echo",
                        "params": {"message": "ok", "stream": True, "tokens": ["a", "b", "c"]},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()

            frames = []
            while True:
                frame = self._read_frame(proc)
                frames.append(frame)
                if frame.get("id") == "req-stream":
                    break

            chunks = [f for f in frames if f.get("method") == "stream.chunk"]
            self.assertTrue(any(c["params"]["is_last"] for c in chunks))
            combined = "".join(c["params"]["delta"] for c in chunks)
            self.assertEqual(combined, "abc")

            proc.stdin.write(
                json.dumps({"jsonrpc": "2.0", "id": "bye", "method": "worker.shutdown", "params": {}})
                + "\n"
            )
            proc.stdin.flush()
            bye = self._read_frame(proc)
            self.assertEqual(bye["result"]["status"], "shutting_down")
            proc.wait(timeout=5)
            assert proc.stderr is not None
            stderr_output = proc.stderr.read()
            self.assertIn("[worker-echo-noise]", stderr_output)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)

    def test_reverse_rpc_does_not_deadlock_heartbeats_and_cancellation_works(self) -> None:
        proc = self._spawn_echo_worker()
        try:
            assert proc.stdin is not None
            self._read_frame(proc)  # worker.ready

            # Start Reverse RPC request awaiting UI approval
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "req-hitl",
                        "method": "worker.echo",
                        "params": {"require_approval": True, "action": "fs.delete_file"},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()

            rev_req = self._read_frame(proc)
            self.assertEqual(rev_req["type"], "reverse_request")
            self.assertEqual(rev_req["method"], "permission.request_approval")

            # Reader loop must STILL answer system.ping while coroutine awaits approval
            proc.stdin.write(
                json.dumps({"jsonrpc": "2.0", "method": "system.ping", "params": {"sequence": 99}})
                + "\n"
            )
            proc.stdin.flush()
            pong = self._read_frame(proc)
            self.assertEqual(pong["method"], "system.pong")
            self.assertEqual(pong["params"]["sequence"], 99)

            # Deliver reverse_response
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": rev_req["id"],
                        "type": "reverse_response",
                        "result": {"granted": True, "decided_by": "test"},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            hitl_done = self._read_frame(proc)
            self.assertEqual(hitl_done["id"], "req-hitl")
            self.assertEqual(hitl_done["result"]["status"], "completed")
            self.assertTrue(hitl_done["result"]["decision"]["granted"])

            # Start long sleeping task then cancel cooperatively
            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": "req-cancel",
                        "method": "worker.echo",
                        "params": {"sleep_ms": 5000},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            first_prog = self._read_frame(proc)
            self.assertEqual(first_prog["method"], "task.progress")

            proc.stdin.write(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "task.cancel",
                        "params": {"request_id": "req-cancel", "reason": "user_cancelled"},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()

            while True:
                msg = self._read_frame(proc)
                if msg.get("id") == "req-cancel":
                    self.assertEqual(msg["result"]["status"], "cancelled")
                    break

            proc.stdin.write(
                json.dumps({"jsonrpc": "2.0", "id": "bye2", "method": "worker.shutdown", "params": {}})
                + "\n"
            )
            proc.stdin.flush()
            proc.wait(timeout=5)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()

