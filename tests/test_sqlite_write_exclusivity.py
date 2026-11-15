"""Stage/Phase A exclusivity tests proving Rust SqliteDatabase is the sole writer to `database.db`.

Verifies:
1. Canonical path detection covers `None`, `""`, `"database.db"`, symlinks/relative paths,
   and `file:` SQLite URIs (`mode=rw`, `mode=rwc`, percent-encoding).
2. With `workers.common.db_guard` installed (and/or `JARVIS_DB_WRITE_OWNER=rust` without RPC),
   direct Python writes via `sqlite3.connect`, `sqlite3.Connection`, `?mode=rwc`, `ATTACH DATABASE`,
   `persistence.db.write_transaction`, `persistence.db.get_db_connection(read_only=False)`,
   `database.*`, and `RetrospectiveEngine` all FAIL CLOSED on canonical `database.db`.
3. Non-canonical SQLite databases (`state.db` for MissionWorker, `:memory:`, temp DBs) stay writable.
4. All 5 real production worker roles (`ai`, `study`, `knowledge`, `mission`, `voice`) install
   the canonical DB write guard at startup in live subprocesses and block bypass attempts.
5. Under `JARVIS_DB_WRITE_OWNER=rust` with an active stdio Reverse-RPC bridge, `database.*`,
   `RetrospectiveEngine`, and `RuntimeObserver` execute end-to-end via Reverse-RPC requests.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.model_harness.contracts import (  # noqa: E402
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    OutputFormat,
)
from persistence.db import ensure_rho_schema  # noqa: E402
from workers.common.db_guard import (  # noqa: E402
    DatabaseWritePermissionError,
    _reset_guard_for_tests,
    install_canonical_db_write_guard,
    is_canonical_db_target,
)


def _seed_legacy_core_schema(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                html_content TEXT,
                css_content TEXT,
                js_content TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS compounding_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_key TEXT UNIQUE,
                description TEXT,
                correction TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS architecture_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL UNIQUE,
                purpose TEXT,
                dependencies TEXT,
                constraints TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS engineering_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                impact TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS event_sourcing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            );
            """
        )
        ensure_rho_schema(conn)
        conn.commit()
    finally:
        conn.close()


class SqliteWriteExclusivityTests(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_guard_for_tests()
        os.environ.pop("JARVIS_DB_WRITE_OWNER", None)
        os.environ.pop("JARVIS_CANONICAL_DB_PATH", None)

    def test_canonical_target_detection_handles_aliases_and_uris(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canon = Path(tmp) / "database.db"
            other = Path(tmp) / "workspace" / "state.db"
            os.environ["JARVIS_CANONICAL_DB_PATH"] = str(canon)

            self.assertTrue(is_canonical_db_target(None))
            self.assertTrue(is_canonical_db_target(""))
            self.assertTrue(is_canonical_db_target("database.db"))
            self.assertTrue(is_canonical_db_target(canon))
            self.assertTrue(is_canonical_db_target(str(canon).upper()))
            self.assertTrue(
                is_canonical_db_target(f"file:{canon.as_posix()}?mode=rwc", uri=True)
            )
            self.assertTrue(
                is_canonical_db_target(f"{canon.as_uri()}?mode=ro", uri=True)
            )
            self.assertTrue(
                is_canonical_db_target(
                    f"file:///{canon.as_posix().lstrip('/').replace(' ', '%20')}?mode=rw",
                    uri=True,
                )
            )
            self.assertTrue(
                is_canonical_db_target(
                    f"file://localhost/{canon.as_posix().lstrip('/').replace(' ', '%20')}?mode=ro",
                    uri=True,
                )
            )
            self.assertTrue(
                is_canonical_db_target(f"file://{canon.as_posix().replace(' ', '%20')}?mode=ro", uri=True)
            )

            self.assertFalse(is_canonical_db_target(":memory:"))
            self.assertFalse(is_canonical_db_target("file::memory:?cache=shared", uri=True))
            self.assertFalse(is_canonical_db_target(other))
            self.assertFalse(is_canonical_db_target(Path(tmp) / "chroma.sqlite3"))

    def test_guard_blocks_all_direct_writes_and_bypass_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canon = Path(tmp) / "database.db"
            _seed_legacy_core_schema(canon)
            os.environ["JARVIS_CANONICAL_DB_PATH"] = str(canon)

            import database
            from backend.model_harness.rho import RetrospectiveEngine
            from persistence.db import get_db_connection, write_transaction

            old_db_file = database.DB_FILE
            database.DB_FILE = str(canon)
            try:
                install_canonical_db_write_guard()

                # 1. Explicit rw / rwc URIs fail closed immediately
                for mode in ("rw", "rwc"):
                    uri = f"file:{canon.as_posix()}?mode={mode}"
                    with self.assertRaises(DatabaseWritePermissionError):
                        sqlite3.connect(uri, uri=True)
                    with self.assertRaises(DatabaseWritePermissionError):
                        sqlite3.Connection(uri, uri=True)

                # 2. persistence.db write helpers fail closed immediately
                with self.assertRaises(DatabaseWritePermissionError):
                    get_db_connection(canon, read_only=False)
                with self.assertRaises(DatabaseWritePermissionError):
                    with write_transaction(canon):
                        pass

                # 3. database.py & RetrospectiveEngine fail closed without Rust Reverse-RPC
                with self.assertRaises(DatabaseWritePermissionError):
                    database.init_db()
                with self.assertRaises(DatabaseWritePermissionError):
                    database.add_compounding_rule("k1", "d1", "c1")
                with self.assertRaises(DatabaseWritePermissionError):
                    database.create_session("Blocked")
                rho = RetrospectiveEngine(canon)
                with self.assertRaises(DatabaseWritePermissionError):
                    rho.record_trajectory(
                        ModelRequest(
                            request_id="blocked",
                            task_profile="coder",
                            system_prompt="s",
                            user_prompt="u",
                        ),
                        ModelResponse(
                            request_id="blocked",
                            model="qwen",
                            status=ModelResponseStatus.VALIDATION_FAILED,
                            errors=({"message": "SCHEMA:bad"},),
                        ),
                    )
                os.environ["JARVIS_DB_WRITE_OWNER"] = "rust"
                try:
                    with self.assertRaises(DatabaseWritePermissionError):
                        RetrospectiveEngine(canon)
                finally:
                    os.environ.pop("JARVIS_DB_WRITE_OWNER", None)

                # 4. Raw sqlite3.connect / sqlite3.Connection force read-only + locked authorizer
                for opener in (sqlite3.connect, sqlite3.Connection):
                    conn = opener(str(canon))
                    try:
                        # SELECT still works when DB file exists
                        self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
                        for sql in (
                            "INSERT INTO sessions (name, status, created_at) VALUES ('x', 'idle', 'now')",
                            "CREATE TABLE bypass_tbl (id INTEGER)",
                            "PRAGMA journal_mode = WAL",
                            "PRAGMA query_only = OFF",
                        ):
                            with self.assertRaises(sqlite3.DatabaseError):
                                conn.execute(sql)
                        with self.assertRaises(DatabaseWritePermissionError):
                            conn.set_authorizer(None)
                    finally:
                        conn.close()

                # 5. ATTACH DATABASE escape from :memory: is blocked by authorizer
                mem = sqlite3.connect(":memory:")
                try:
                    with self.assertRaises(sqlite3.DatabaseError):
                        mem.execute(f"ATTACH DATABASE '{canon.as_posix()}' AS pwn")
                finally:
                    mem.close()

                # Confirm zero rows were inserted into sessions
                _reset_guard_for_tests()
                verify = sqlite3.connect(str(canon))
                try:
                    self.assertEqual(verify.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
                finally:
                    verify.close()
            finally:
                database.DB_FILE = old_db_file

    def test_non_canonical_state_db_and_temp_dbs_remain_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canon = Path(tmp) / "database.db"
            _seed_legacy_core_schema(canon)
            state_db = Path(tmp) / "workspace" / ".jarvis" / "projects" / "p1" / "missions" / "m1" / "state.db"
            state_db.parent.mkdir(parents=True, exist_ok=True)
            temp_db = Path(tmp) / "scratch.db"

            os.environ["JARVIS_CANONICAL_DB_PATH"] = str(canon)
            os.environ["JARVIS_DB_WRITE_OWNER"] = "rust"
            install_canonical_db_write_guard()

            from persistence.db import write_transaction

            # Mission state.db + temp DBs + :memory: stay completely writable
            with write_transaction(state_db) as conn:
                conn.execute("CREATE TABLE mission_state (id INTEGER PRIMARY KEY, status TEXT)")
                conn.execute("INSERT INTO mission_state (status) VALUES ('running')")

            raw = sqlite3.connect(str(temp_db))
            raw.execute("CREATE TABLE t (x INT)")
            raw.execute("INSERT INTO t (x) VALUES (7)")
            raw.commit()
            self.assertEqual(raw.execute("SELECT x FROM t").fetchone()[0], 7)
            raw.close()

            mem = sqlite3.connect(":memory:")
            mem.execute("CREATE TABLE m (v TEXT)")
            mem.execute("INSERT INTO m (v) VALUES ('ok')")
            self.assertEqual(mem.execute("SELECT v FROM m").fetchone()[0], "ok")
            mem.close()

    def test_all_five_workers_enforce_canonical_db_guard_in_live_subprocesses(self) -> None:
        """Boots all 5 worker roles through `worker_boot` initialization and verifies fails-closed DB writes."""
        with tempfile.TemporaryDirectory() as tmp:
            canon = Path(tmp) / "database.db"
            _seed_legacy_core_schema(canon)
            mission_state = Path(tmp) / "mission_state.db"

            probe_code = """
import io, os, sqlite3, sys
import workers.worker_boot as wb
from persistence.db import write_transaction
from workers.common.db_guard import DatabaseWritePermissionError
import database

role = sys.argv[1]
canon = os.environ["JARVIS_CANONICAL_DB_PATH"]
mission_state = os.environ["TEST_MISSION_STATE_DB"]

server = wb.build_worker_server(role, wb.ProtocolFrameWriter(io.StringIO()))
assert server.worker_type == role

for label, fn in (
    ("mode_rwc", lambda: sqlite3.connect(f"file:{canon}?mode=rwc", uri=True)),
    ("write_tx", lambda: write_transaction(canon).__enter__()),
    ("init_db", lambda: database.init_db()),
):
    try:
        fn()
        raise AssertionError(f"{role} failed to block {label}")
    except DatabaseWritePermissionError:
        pass

conn = sqlite3.connect(canon)
try:
    try:
        conn.execute("INSERT INTO sessions (name, status, created_at) VALUES ('hack', 'idle', 'now')")
        raise AssertionError(f"{role} allowed INSERT via raw sqlite3.connect")
    except sqlite3.DatabaseError:
        pass
finally:
    conn.close()

state_conn = sqlite3.connect(mission_state)
state_conn.execute("CREATE TABLE IF NOT EXISTS ok (role TEXT)")
state_conn.execute("INSERT INTO ok (role) VALUES (?)", (role,))
state_conn.commit()
state_conn.close()
print("GUARD_OK:" + role)
"""

            for role in ("ai", "study", "knowledge", "mission", "voice"):
                with self.subTest(role=role):
                    env = os.environ.copy()
                    env["JARVIS_CANONICAL_DB_PATH"] = str(canon)
                    env["JARVIS_DB_WRITE_OWNER"] = "rust"
                    env["TEST_MISSION_STATE_DB"] = str(mission_state)
                    env["PYTHONUNBUFFERED"] = "1"
                    proc = subprocess.run(
                        [sys.executable, "-c", probe_code, role],
                        cwd=str(REPO_ROOT),
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(
                        proc.returncode,
                        0,
                        msg=f"role={role} failed: stdout={proc.stdout!r}, stderr={proc.stderr!r}",
                    )
                    self.assertIn(f"GUARD_OK:{role}", proc.stderr + proc.stdout)

    def test_worker_writes_and_rho_route_via_sync_reverse_rpc_without_deadlock(self) -> None:
        """Runs a live WorkerRpcServer thread and proves `database.*` + `RetrospectiveEngine` + `RuntimeObserver` route through Reverse-RPC."""
        from workers.common.stdio_rpc import ProtocolFrameWriter, WorkerContext, WorkerRpcServer

        with tempfile.TemporaryDirectory() as tmp:
            canon = Path(tmp) / "database.db"
            _seed_legacy_core_schema(canon)

            # Separate owner-side connection BEFORE installing worker guard
            owner_conn = sqlite3.connect(str(canon), check_same_thread=False)
            in_r, in_w = os.pipe()
            out_r, out_w = os.pipe()
            in_reader = os.fdopen(in_r, "r", encoding="utf-8", buffering=1)
            in_writer = os.fdopen(in_w, "w", encoding="utf-8", buffering=1)
            out_reader = os.fdopen(out_r, "r", encoding="utf-8", buffering=1)
            out_writer = os.fdopen(out_w, "w", encoding="utf-8", buffering=1)

            writer = ProtocolFrameWriter(out_writer)
            server = WorkerRpcServer(
                worker_type="ai",
                capabilities=["reverse_rpc"],
                writer=writer,
                stdin_stream=in_reader,
            )

            import database
            from backend.model_harness.rho import RetrospectiveEngine
            from intelligence.runtime_observer import RuntimeObserver

            async def _run_sync_ops_on_loop(_ctx: WorkerContext, _params: dict[str, Any]) -> dict[str, Any]:
                # Deliberately call synchronous database + RHO APIs directly on the asyncio event loop thread!
                database.init_db()
                sess = database.create_session("RPC-Session")
                database.add_message(sess.id, "USER", "user", "Hello via RPC")
                database.save_project(sess.id, "Proj1", "Desc", "<h1>Hi</h1>", "", "")
                database.add_compounding_rule("RuleKey1", "Desc", "Validate JSON")
                rules = database.get_compounding_rules()
                database.add_architecture_memory("core.rpc", "Bridge", "tokio", "no direct db")
                arch = database.get_architecture_memory()
                database.add_engineering_decision("Rust SQLite Owner", "Exclusivity", "High")
                decisions = database.get_engineering_decisions()

                rho = RetrospectiveEngine()
                req1 = ModelRequest(
                    request_id="r1",
                    task_profile="coder",
                    system_prompt="s",
                    user_prompt="u",
                )
                req2 = ModelRequest(
                    request_id="r2",
                    task_profile="coder",
                    system_prompt="s",
                    user_prompt="u2",
                )
                fail_resp = ModelResponse(
                    request_id="r1",
                    model="qwen",
                    status=ModelResponseStatus.VALIDATION_FAILED,
                    errors=({"message": "SCHEMA:missing"},),
                )
                rho.record_trajectory(req1, fail_resp)
                rho.record_trajectory(req2, fail_resp)
                rho_rules = rho.get_compounding_rules("coder")
                metrics = RuntimeObserver().get_db_metrics()

                return {
                    "session_id": sess.id,
                    "rules": rules,
                    "arch": arch,
                    "decisions": decisions,
                    "rho_rules": rho_rules,
                    "metrics": metrics,
                }

            server.register("test.exercise_db", _run_sync_ops_on_loop)

            rpc_calls_observed: list[str] = []
            ready_event = threading.Event()
            responses: queue.Queue[dict[str, Any]] = queue.Queue()

            def _mock_rust_reverse_rpc_host() -> None:
                for raw in out_reader:
                    line = raw.strip()
                    if not line:
                        continue
                    frame = json.loads(line)
                    if frame.get("method") == "worker.ready":
                        ready_event.set()
                        continue
                    if frame.get("type") != "reverse_request":
                        if frame.get("id") == "quit":
                            break
                        if "id" in frame:
                            responses.put(frame)
                        continue
                    rev_id = frame["id"]
                    method = frame["method"]
                    params = frame.get("params") or {}
                    rpc_calls_observed.append(method)
                    result: Any = {"ok": True}
                    cur = owner_conn.cursor()
                    if method in ("sqlite.init_db", "sqlite.rho_ensure_schema"):
                        ensure_rho_schema(owner_conn)
                    elif method == "sqlite.create_session":
                        cur.execute(
                            "INSERT INTO sessions (name, status, created_at) VALUES (?, 'idle', 'now')",
                            (params["name"],),
                        )
                        owner_conn.commit()
                        result = {"id": cur.lastrowid, "name": params["name"], "status": "idle"}
                    elif method == "sqlite.add_message":
                        cur.execute(
                            "INSERT INTO messages (session_id, sender, role, content, timestamp) VALUES (?, 'CLIENTE', ?, ?, 'now')",
                            (params["session_id"], params["role"], params["content"]),
                        )
                        owner_conn.commit()
                        result = {"id": cur.lastrowid}
                    elif method == "sqlite.save_project":
                        cur.execute(
                            "INSERT INTO projects (session_id, name, description, html_content, css_content, js_content, created_at) VALUES (?, ?, ?, ?, ?, ?, 'now')",
                            (
                                params["session_id"],
                                params["name"],
                                params.get("description"),
                                params.get("html_content"),
                                params.get("css_content"),
                                params.get("js_content"),
                            ),
                        )
                        owner_conn.commit()
                        result = {"id": cur.lastrowid}
                    elif method == "sqlite.add_compounding_rule":
                        cur.execute(
                            "INSERT INTO compounding_memory (rule_key, description, correction, created_at) VALUES (?, ?, ?, 'now')",
                            (params["rule_key"], params["description"], params["correction"]),
                        )
                        owner_conn.commit()
                    elif method == "sqlite.get_compounding_rules":
                        result = [
                            {"rule_key": r[0], "description": r[1], "correction": r[2]}
                            for r in cur.execute("SELECT rule_key, description, correction FROM compounding_memory ORDER BY id DESC").fetchall()
                        ]
                    elif method == "sqlite.add_architecture_memory":
                        cur.execute(
                            "INSERT OR REPLACE INTO architecture_memory (module, purpose, dependencies, constraints, updated_at) VALUES (?, ?, ?, ?, 'now')",
                            (params["module"], params["purpose"], params["dependencies"], params["constraints"]),
                        )
                        owner_conn.commit()
                        result = {"module": params["module"]}
                    elif method == "sqlite.get_architecture_memory":
                        result = [
                            {"module": r[0], "purpose": r[1], "dependencies": r[2], "constraints": r[3], "updated_at": r[4]}
                            for r in cur.execute("SELECT module, purpose, dependencies, constraints, updated_at FROM architecture_memory").fetchall()
                        ]
                    elif method == "sqlite.add_engineering_decision":
                        cur.execute(
                            "INSERT INTO engineering_decisions (decision, reason, impact, created_at) VALUES (?, ?, ?, 'now')",
                            (params["decision"], params["reason"], params["impact"]),
                        )
                        owner_conn.commit()
                        result = {"id": cur.lastrowid}
                    elif method == "sqlite.get_engineering_decisions":
                        result = [
                            {"decision": r[0], "reason": r[1], "impact": r[2], "created_at": r[3]}
                            for r in cur.execute("SELECT decision, reason, impact, created_at FROM engineering_decisions").fetchall()
                        ]
                    elif method == "sqlite.rho_record_trajectory":
                        cur.execute(
                            "INSERT INTO model_trajectories (request_id, task_profile, fingerprint, status, attempts_count, failure_reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (
                                params["request_id"],
                                params["task_profile"],
                                params["fingerprint"],
                                params["status"],
                                params["attempts_count"],
                                params.get("failure_reason", ""),
                                time.time(),
                            ),
                        )
                        cnt = cur.execute(
                            "SELECT COUNT(*) FROM model_trajectories WHERE task_profile = ? AND failure_reason = ?",
                            (params["task_profile"], params.get("failure_reason", "")),
                        ).fetchone()[0]
                        if cnt >= 2:
                            cur.execute(
                                "INSERT INTO rho_compounding_rules (task_profile, rule_text, failure_trigger, created_at) VALUES (?, ?, ?, ?)",
                                (
                                    params["task_profile"],
                                    f"AUTO-RULE [RHO-{params['task_profile']}]: Evita falha {params.get('failure_reason', '')}.",
                                    params.get("failure_reason", ""),
                                    time.time(),
                                ),
                            )
                        owner_conn.commit()
                        result = {"trajectory_id": cur.lastrowid, "failure_count": cnt}
                    elif method == "sqlite.rho_get_compounding_rules":
                        result = [
                            r[0]
                            for r in cur.execute(
                                "SELECT rule_text FROM rho_compounding_rules WHERE task_profile = ? ORDER BY id DESC LIMIT 5",
                                (params["task_profile"],),
                            ).fetchall()
                        ]
                    elif method == "sqlite.runtime_db_metrics":
                        sess_cnt = cur.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                        evt_cnt = cur.execute("SELECT COUNT(*) FROM event_sourcing_log").fetchone()[0]
                        result = {
                            "sqlite_online": True,
                            "total_sessions": sess_cnt,
                            "total_events_in_log": evt_cnt,
                        }

                    resp = {"type": "reverse_response", "id": rev_id, "result": result}
                    in_writer.write(json.dumps(resp) + "\n")
                    in_writer.flush()

            host_thread = threading.Thread(target=_mock_rust_reverse_rpc_host, daemon=True)
            host_thread.start()

            old_db_file = database.DB_FILE
            database.DB_FILE = str(canon)
            os.environ["JARVIS_CANONICAL_DB_PATH"] = str(canon)
            os.environ["JARVIS_DB_WRITE_OWNER"] = "rust"
            install_canonical_db_write_guard()

            server_thread_err: list[BaseException] = []

            def _run_server() -> None:
                try:
                    asyncio.run(server.serve())
                except BaseException as exc:  # pragma: no cover
                    server_thread_err.append(exc)

            srv_thread = threading.Thread(target=_run_server, daemon=True)
            srv_thread.start()
            try:
                self.assertTrue(ready_event.wait(timeout=5.0), "worker ready timed out")

                in_writer.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": "req-db-test",
                            "method": "test.exercise_db",
                            "params": {},
                        }
                    )
                    + "\n"
                )
                in_writer.flush()

                reply = responses.get(timeout=10.0)
                self.assertEqual(reply.get("id"), "req-db-test")
                self.assertNotIn("error", reply, msg=f"RPC returned error: {reply}")
                res = reply["result"]
                self.assertEqual(res["session_id"], 1)
                self.assertEqual(len(res["rules"]), 1)
                self.assertEqual(res["rules"][0]["rule_key"], "RuleKey1")
                self.assertEqual(len(res["arch"]), 1)
                self.assertEqual(len(res["decisions"]), 1)
                self.assertEqual(len(res["rho_rules"]), 1)
                self.assertIn("AUTO-RULE [RHO-coder]", res["rho_rules"][0])
                self.assertTrue(res["metrics"]["sqlite_online"])
                self.assertEqual(res["metrics"]["total_sessions"], 1)
                self.assertEqual(
                    rpc_calls_observed,
                    [
                        "sqlite.init_db",
                        "sqlite.create_session",
                        "sqlite.add_message",
                        "sqlite.save_project",
                        "sqlite.add_compounding_rule",
                        "sqlite.get_compounding_rules",
                        "sqlite.add_architecture_memory",
                        "sqlite.get_architecture_memory",
                        "sqlite.add_engineering_decision",
                        "sqlite.get_engineering_decisions",
                        "sqlite.rho_ensure_schema",
                        "sqlite.rho_record_trajectory",
                        "sqlite.rho_record_trajectory",
                        "sqlite.rho_get_compounding_rules",
                        "sqlite.runtime_db_metrics",
                    ],
                )
            finally:
                database.DB_FILE = old_db_file
                try:
                    in_writer.write(json.dumps({"jsonrpc": "2.0", "id": "quit", "method": "worker.shutdown", "params": {}}) + "\n")
                    in_writer.flush()
                except Exception:
                    pass
                srv_thread.join(timeout=3.0)
                for h in (in_reader, in_writer, out_reader, out_writer):
                    try:
                        h.close()
                    except Exception:
                        pass
                host_thread.join(timeout=3.0)
                self.assertEqual(server_thread_err, [])
                owner_conn.close()
