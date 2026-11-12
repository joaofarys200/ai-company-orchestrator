from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database
from backend.model_harness.contracts import ModelRequest, ModelResponse, ModelResponseStatus
from backend.model_harness.rho import RetrospectiveEngine
from intelligence.runtime_observer import RuntimeObserver
from persistence.db import (
    CANONICAL_DB_PATH,
    ensure_rho_schema,
    get_db_connection,
    resolve_db_path,
    write_transaction,
)


class SQLiteHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_db_file = database.DB_FILE
        self._temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._temp_dir.name)
        self.test_db = self.tmp_path / "hardened_test.db"

    def tearDown(self) -> None:
        database.DB_FILE = self._orig_db_file
        try:
            self._temp_dir.cleanup()
        except OSError:
            pass

    def _init_temp_db(self, db_path: Path) -> None:
        database.DB_FILE = str(db_path)
        database.init_db()

    def test_canonical_path_anchored_regardless_of_cwd_and_pragmas_enforced(self) -> None:
        self.assertEqual(CANONICAL_DB_PATH, PROJECT_ROOT / "database.db")
        self.assertEqual(Path(resolve_db_path("database.db")), CANONICAL_DB_PATH)
        self.assertEqual(resolve_db_path(":memory:"), ":memory:")

        old_cwd = Path.cwd()
        alt_cwd = self.tmp_path / "other_cwd"
        alt_cwd.mkdir()
        try:
            os.chdir(alt_cwd)
            self.assertEqual(Path(resolve_db_path("database.db")), CANONICAL_DB_PATH)
            self.assertFalse((alt_cwd / "database.db").exists())
            observer = RuntimeObserver()
            self.assertEqual(Path(observer.db_path), CANONICAL_DB_PATH)
        finally:
            os.chdir(old_cwd)

        with closing(get_db_connection(self.test_db)) as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 10_000)
            self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

        # Foreign keys actively enforced on inserts
        self._init_temp_db(self.test_db)
        with self.assertRaises(sqlite3.IntegrityError):
            with write_transaction(self.test_db) as conn:
                conn.execute(
                    "INSERT INTO messages (session_id, sender, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (999999, "JARVIS", "Assistant", "orphan", "2026-11-12T00:00:00Z"),
                )

    def test_model_trajectories_composite_index_and_covering_query_plan(self) -> None:
        self._init_temp_db(self.test_db)
        with closing(get_db_connection(self.test_db)) as conn:
            ensure_rho_schema(conn)
            plan = conn.execute(
                "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM model_trajectories WHERE task_profile = ? AND failure_reason = ? AND created_at > ?",
                ("CODING", "TIMEOUT", 0.0),
            ).fetchall()
        plan_text = " ".join(str(row) for row in plan)
        self.assertIn("idx_model_trajectories_pattern", plan_text)
        self.assertNotIn("SCAN model_trajectories", plan_text)

    def test_wal_ten_parallel_readers_with_active_writer(self) -> None:
        self._init_temp_db(self.test_db)
        rho = RetrospectiveEngine(db_path=self.test_db)
        # Seed baseline row
        req0 = ModelRequest(task_profile="TEST_PROFILE", system_prompt="s", user_prompt="u0")
        resp0 = ModelResponse(request_id=req0.request_id, status=ModelResponseStatus.SUCCEEDED, raw_text="ok")
        rho.record_trajectory(req0, resp0)

        stop_event = threading.Event()
        errors: list[str] = []
        read_counts = [0] * 10
        write_count = 0

        def reader_worker(idx: int) -> None:
            try:
                with closing(get_db_connection(self.test_db, check_same_thread=False)) as conn:
                    while not stop_event.is_set():
                        cnt = conn.execute("SELECT COUNT(*) FROM model_trajectories").fetchone()[0]
                        if cnt < 1:
                            errors.append(f"reader {idx} observed unexpected count {cnt}")
                            break
                        _ = conn.execute(
                            "SELECT COUNT(*) FROM model_trajectories WHERE task_profile = ? AND failure_reason = ? AND created_at > ?",
                            ("TEST_PROFILE", "", 0.0),
                        ).fetchone()[0]
                        read_counts[idx] += 1
            except Exception as exc:
                errors.append(f"reader {idx} failed: {exc!r}")

        def writer_worker() -> None:
            nonlocal write_count
            try:
                for i in range(60):
                    req = ModelRequest(task_profile="TEST_PROFILE", system_prompt="s", user_prompt=f"u{i}")
                    resp = ModelResponse(
                        request_id=req.request_id,
                        status=ModelResponseStatus.PROVIDER_FAILED,
                        errors=[{"message": f"err_{i % 3}"}],
                    )
                    rho.record_trajectory(req, resp)
                    write_count += 1
                    time.sleep(0.005)
            except Exception as exc:
                errors.append(f"writer failed: {exc!r}")
            finally:
                stop_event.set()

        readers = [threading.Thread(target=reader_worker, args=(i,)) for i in range(10)]
        writer = threading.Thread(target=writer_worker)
        for t in readers:
            t.start()
        writer.start()

        writer.join(timeout=20.0)
        stop_event.set()
        for t in readers:
            t.join(timeout=10.0)

        self.assertEqual(errors, [], f"Concurrent WAL readers/writer hit errors: {errors}")
        self.assertEqual(write_count, 60)
        self.assertTrue(all(c > 0 for c in read_counts), f"All 10 readers must complete queries: {read_counts}")

    def test_long_write_transaction_readers_unblocked_and_writer_waits_within_busy_timeout(self) -> None:
        self._init_temp_db(self.test_db)
        with write_transaction(self.test_db) as conn:
            conn.execute(
                "INSERT INTO sessions (name, status, created_at) VALUES (?, ?, ?)",
                ("seed", "idle", "2026-11-12T00:00:00Z"),
            )

        holder_script = (
            "import sys, time\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, sys.argv[2])\n"
            "from persistence.db import write_transaction\n"
            "with write_transaction(Path(sys.argv[1])) as conn:\n"
            "    conn.execute(\"INSERT INTO sessions (name, status, created_at) VALUES ('holder', 'idle', '2026-11-12T00:00:01Z')\")\n"
            "    print('LOCKED', flush=True)\n"
            "    time.sleep(6.0)\n"
            "print('RELEASED', flush=True)\n"
        )
        python_exe = getattr(sys, "_base_executable", sys.executable)
        proc = subprocess.Popen(
            [python_exe, "-c", holder_script, str(self.test_db), str(PROJECT_ROOT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            line = proc.stdout.readline().strip() if proc.stdout else ""
            if line != "LOCKED":
                err = proc.stderr.read() if proc.stderr else ""
                self.fail(f"Subprocess failed to acquire write lock ({line!r}); stderr={err}")

            # Reader must NOT block during the 6.0s write lock
            read_start = time.monotonic()
            with closing(get_db_connection(self.test_db)) as rconn:
                rows_seen = rconn.execute("SELECT id, name FROM sessions ORDER BY id").fetchall()
                row_count = len(rows_seen)
            read_elapsed = time.monotonic() - read_start
            self.assertEqual(row_count, 1)
            self.assertLess(read_elapsed, 1.5, f"WAL reader blocked during active write: {read_elapsed:.2f}s")

            # Second writer enters BEGIN IMMEDIATE ~0.2s in and must wait ~5.8s (< 10s busy_timeout) then succeed
            write_start = time.monotonic()
            with write_transaction(self.test_db) as wconn:
                wconn.execute(
                    "INSERT INTO sessions (name, status, created_at) VALUES (?, ?, ?)",
                    ("queued_writer", "idle", "2026-11-12T00:00:02Z"),
                )
            write_elapsed = time.monotonic() - write_start
            self.assertGreaterEqual(write_elapsed, 4.0, "Second writer should have queued behind 6.0s write tx")
            self.assertLess(write_elapsed, 9.5, "Second writer should succeed well within 10s busy_timeout")

            proc.wait(timeout=5.0)
            self.assertEqual(proc.returncode, 0)
            with closing(get_db_connection(self.test_db)) as vconn:
                names = [r[0] for r in vconn.execute("SELECT name FROM sessions ORDER BY id ASC").fetchall()]
            self.assertEqual(names, ["seed", "holder", "queued_writer"])
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5.0)
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

    def test_crash_recovery_after_forced_subprocess_kill(self) -> None:
        self._init_temp_db(self.test_db)

        crash_script = (
            "import os, sys, time\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, sys.argv[2])\n"
            "from persistence.db import get_db_connection, write_transaction\n"
            "db = Path(sys.argv[1])\n"
            "with write_transaction(db) as conn:\n"
            "    conn.execute(\"INSERT INTO sessions (name, status, created_at) VALUES ('committed_before_crash', 'idle', '2026-11-12T00:00:00Z')\")\n"
            "conn = get_db_connection(db)\n"
            "conn.execute('BEGIN IMMEDIATE')\n"
            "conn.execute(\"INSERT INTO sessions (name, status, created_at) VALUES ('uncommitted_inflight', 'idle', '2026-11-12T00:00:01Z')\")\n"
            "print(f'INFLIGHT_ACTIVE:{os.getpid()}', flush=True)\n"
            "time.sleep(30.0)\n"
        )
        python_exe = getattr(sys, "_base_executable", sys.executable)
        proc = subprocess.Popen(
            [python_exe, "-c", crash_script, str(self.test_db), str(PROJECT_ROOT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        child_pid: int | None = None
        try:
            line = proc.stdout.readline().strip() if proc.stdout else ""
            if not line.startswith("INFLIGHT_ACTIVE:"):
                err = proc.stderr.read() if proc.stderr else ""
                self.fail(f"Subprocess failed before crash simulation ({line!r}); stderr={err}")
            child_pid = int(line.split(":", 1)[1])
            # Abrupt OS termination (TerminateProcess on Windows / SIGKILL on POSIX) mid-transaction
            proc.kill()
            proc.wait(timeout=5.0)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5.0)
            if child_pid is not None and child_pid != proc.pid:
                try:
                    os.kill(child_pid, 9)
                except OSError:
                    pass
            if proc.stdout:
                proc.stdout.close()
            if proc.stderr:
                proc.stderr.close()

        # Reopen after forced termination: WAL must recover cleanly without corruption
        with closing(get_db_connection(self.test_db)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            names = [r[0] for r in conn.execute("SELECT name FROM sessions ORDER BY id ASC").fetchall()]
            self.assertEqual(names, ["committed_before_crash"])

    def test_temp_copy_of_production_db_preserves_integrity_and_data_counts(self) -> None:
        if not CANONICAL_DB_PATH.exists():
            self.skipTest("Production database.db not present in environment")

        copy_db = self.tmp_path / "prod_copy.db"
        with closing(get_db_connection(CANONICAL_DB_PATH, read_only=True)) as src:
            self.assertEqual(src.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(src.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            idx_names = {
                r[0]
                for r in src.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
            }
            self.assertIn("idx_model_trajectories_pattern", idx_names)
            with closing(sqlite3.connect(copy_db)) as dst:
                src.backup(dst)

        # Applying init_db + RetrospectiveEngine on copy must preserve 100% of historical counts
        self._init_temp_db(copy_db)
        RetrospectiveEngine(db_path=copy_db)

        with closing(get_db_connection(copy_db)) as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 10_000)
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM model_trajectories").fetchone()[0], 1954)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM rho_compounding_rules").fetchone()[0], 430)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 317)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 69)


if __name__ == "__main__":
    unittest.main()
