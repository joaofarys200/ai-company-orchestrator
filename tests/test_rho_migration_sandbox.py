from __future__ import annotations

from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from persistence.db import CANONICAL_DB_PATH, ensure_rho_schema, get_db_connection, write_transaction
from scripts.migrate_rho_db import (
    RHO_BUSY_TIMEOUT_MS,
    RULE_COLUMNS,
    TRAJECTORY_COLUMNS,
    RhoMigrationError,
    RhoMigrationSafetyError,
    assert_sandbox_target_path,
    compute_table_snapshot,
    migrate_rho_db,
)

EXPECTED_RHO_INDEXES = {
    "idx_model_trajectories_pattern",
    "idx_model_trajectories_request_id",
    "idx_model_trajectories_fingerprint",
    "idx_rho_rules_task_profile_id",
    "idx_rho_rules_trigger",
}


class RhoMigrationSandboxTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory(prefix="jarvis_rho_sandbox_")
        self.tmp_path = Path(self._tmp_dir.name)
        self.source_db = self.tmp_path / "source.db"
        self.target_db = self.tmp_path / "sandbox_rho.db"

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def _create_synthetic_source_db(self, path: Path) -> None:
        with write_transaction(path) as conn:
            ensure_rho_schema(conn)
            conn.executemany(
                """
                INSERT INTO model_trajectories (
                    id, request_id, task_profile, fingerprint, status,
                    attempts_count, failure_reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (1, "req-001", "CODING_AGENT", "fp-1", "SUCCESS", 1, None, 1700000001.5),
                    (2, "req-002", "STUDY_SYNTHESIS", "fp-2", "PROVIDER_FAILED", 2, "timeout —ação", 1700000002.5),
                    (5, "req-005", "STUDY_SYNTHESIS", "fp-5", "PROVIDER_FAILED", 1, "context_overflow", 1700000005.0),
                ],
            )
            conn.executemany(
                """
                INSERT INTO rho_compounding_rules (
                    id, task_profile, rule_text, failure_trigger, occurrences, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (10, "STUDY_SYNTHESIS", "Chunk notes ≤ 4000 chars", "context_overflow", 3, 1700000010.0),
                    (11, "STUDY_SYNTHESIS", "Keep timeout budget", "context_overflow", 2, 1700000011.0),
                ],
            )

    def _create_protected_sqlite_db(self, path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("CREATE TABLE protected_guard (id INTEGER PRIMARY KEY, marker TEXT NOT NULL)")
            conn.execute("INSERT INTO protected_guard (id, marker) VALUES (1, 'untouched-sentinel')")
            conn.commit()
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _assert_rejected_cli_and_python(
        self,
        target: Path | str,
        *,
        sandbox_root: Path | None = None,
    ) -> None:
        with self.assertRaises(RhoMigrationSafetyError):
            assert_sandbox_target_path(target, self.source_db, sandbox_root=sandbox_root)
        with self.assertRaises(RhoMigrationSafetyError):
            migrate_rho_db(self.source_db, target, sandbox_root=sandbox_root)
        if sandbox_root is None:
            python_exe = getattr(sys, "_base_executable", sys.executable)
            proc = subprocess.run(
                [
                    python_exe,
                    str(PROJECT_ROOT / "scripts" / "migrate_rho_db.py"),
                    "--source",
                    str(self.source_db),
                    "--target",
                    str(target),
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(proc.returncode, 0)

    def test_rejects_production_database_db(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        existed = CANONICAL_DB_PATH.exists()
        pre_stat = CANONICAL_DB_PATH.stat() if existed else None
        self._assert_rejected_cli_and_python(CANONICAL_DB_PATH)
        self.assertEqual(CANONICAL_DB_PATH.exists(), existed)
        if pre_stat is not None:
            post_stat = CANONICAL_DB_PATH.stat()
            self.assertEqual((post_stat.st_size, post_stat.st_mtime_ns), (pre_stat.st_size, pre_stat.st_mtime_ns))

    def test_rejects_production_backup_db(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        bak_path = PROJECT_ROOT / "database.db.pre-tauri.bak"
        existed = bak_path.exists()
        pre_sha = hashlib.sha256(bak_path.read_bytes()).hexdigest() if existed else None
        self._assert_rejected_cli_and_python(bak_path)
        self.assertEqual(bak_path.exists(), existed)
        if pre_sha is not None:
            self.assertEqual(hashlib.sha256(bak_path.read_bytes()).hexdigest(), pre_sha)

    def test_rejects_project_root_state_db(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        state_db = PROJECT_ROOT / "state.db"
        existed = state_db.exists()
        pre_sha = hashlib.sha256(state_db.read_bytes()).hexdigest() if existed else None
        self._assert_rejected_cli_and_python(state_db)
        self.assertEqual(state_db.exists(), existed)
        if pre_sha is not None:
            self.assertEqual(hashlib.sha256(state_db.read_bytes()).hexdigest(), pre_sha)

    def test_rejects_production_data_rho_db(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        prod_rho = PROJECT_ROOT / "data" / "rho.db"
        existed = prod_rho.exists()
        self._assert_rejected_cli_and_python(prod_rho)
        self.assertEqual(prod_rho.exists(), existed)

    def test_rejects_other_files_inside_data_dir(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        for rel in ("data/other_db.db", "data/obsidian/graph_diagnostics.json"):
            candidate = PROJECT_ROOT / rel
            existed = candidate.exists()
            pre_sha = hashlib.sha256(candidate.read_bytes()).hexdigest() if existed else None
            with self.subTest(target=str(candidate)):
                self._assert_rejected_cli_and_python(candidate)
                self.assertEqual(candidate.exists(), existed)
                if pre_sha is not None:
                    self.assertEqual(hashlib.sha256(candidate.read_bytes()).hexdigest(), pre_sha)

    def test_rejects_arbitrary_existing_sqlite_db_outside_sandbox(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        allowed_sandbox = self.tmp_path / "approved_sandbox"
        allowed_sandbox.mkdir()
        outside_db = self.tmp_path / "outside_area" / "arbitrary_existing.db"
        pre_sha = self._create_protected_sqlite_db(outside_db)

        self._assert_rejected_cli_and_python(outside_db, sandbox_root=allowed_sandbox)
        # Default allowlist (tempfile.gettempdir()) also blocks any arbitrary filename outside temp
        arbitrary_non_temp = PROJECT_ROOT / "arbitrary_non_sandbox.sqlite"
        self.assertFalse(arbitrary_non_temp.exists())
        self._assert_rejected_cli_and_python(arbitrary_non_temp)
        self.assertFalse(arbitrary_non_temp.exists())

        self.assertEqual(hashlib.sha256(outside_db.read_bytes()).hexdigest(), pre_sha)
        self.assertFalse(Path(f"{outside_db}-wal").exists())
        self.assertFalse(Path(f"{outside_db}-shm").exists())
        with closing(sqlite3.connect(outside_db)) as conn:
            self.assertEqual(
                conn.execute("SELECT id, marker FROM protected_guard").fetchall(),
                [(1, "untouched-sentinel")],
            )

    def test_rejects_sandbox_root_parent_traversal_and_equal_source(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        sandbox_root = Path(tempfile.gettempdir())
        allowed_sandbox = self.tmp_path / "approved_sandbox"
        allowed_sandbox.mkdir()
        self._assert_rejected_cli_and_python(
            allowed_sandbox / ".." / "outside_traversal.db",
            sandbox_root=allowed_sandbox,
        )
        traversal_outside = self.tmp_path / ".." / ".." / "outside_traversal.db"
        if not traversal_outside.resolve(strict=False).is_relative_to(sandbox_root.resolve(strict=False)):
            self._assert_rejected_cli_and_python(traversal_outside)
        self._assert_rejected_cli_and_python(sandbox_root)
        self._assert_rejected_cli_and_python(self.source_db)

    def test_rejects_symlink_pointing_to_protected_database(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        allowed_sandbox = self.tmp_path / "approved_sandbox"
        allowed_sandbox.mkdir()
        outside_db = self.tmp_path / "outside_area" / "protected_target.db"
        pre_sha = self._create_protected_sqlite_db(outside_db)

        symlink_target = allowed_sandbox / "symlink_to_protected.db"
        try:
            os.symlink(outside_db, symlink_target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"OS does not permit unprivileged symlinks in this environment: {exc}")

        self._assert_rejected_cli_and_python(symlink_target, sandbox_root=allowed_sandbox)
        self.assertEqual(hashlib.sha256(outside_db.read_bytes()).hexdigest(), pre_sha)
        with closing(sqlite3.connect(outside_db)) as conn:
            self.assertEqual(
                conn.execute("SELECT id, marker FROM protected_guard").fetchall(),
                [(1, "untouched-sentinel")],
            )

    def test_rejects_hardlink_to_protected_database(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        allowed_sandbox = self.tmp_path / "approved_sandbox"
        allowed_sandbox.mkdir()
        outside_db = self.tmp_path / "outside_area" / "protected_hardlink_target.db"
        pre_sha = self._create_protected_sqlite_db(outside_db)

        hardlink_target = allowed_sandbox / "hardlink_to_protected.db"
        try:
            os.link(outside_db, hardlink_target)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"OS/filesystem does not support hard links here: {exc}")

        self._assert_rejected_cli_and_python(hardlink_target, sandbox_root=allowed_sandbox)
        self.assertEqual(hashlib.sha256(outside_db.read_bytes()).hexdigest(), pre_sha)
        with closing(sqlite3.connect(outside_db)) as conn:
            self.assertEqual(
                conn.execute("SELECT id, marker FROM protected_guard").fetchall(),
                [(1, "untouched-sentinel")],
            )

    def test_synthetic_sandbox_migration_full_parity_indexes_and_rollback(self) -> None:
        self._create_synthetic_source_db(self.source_db)
        report = migrate_rho_db(self.source_db, self.target_db)

        self.assertTrue(report.integrity_ok)
        self.assertEqual(report.user_version, 1)
        self.assertEqual(report.source_trajectories, 3)
        self.assertEqual(report.target_trajectories, 3)
        self.assertEqual(report.source_rules, 2)
        self.assertEqual(report.target_rules, 2)
        self.assertEqual(report.source_trajectories_sha256, report.target_trajectories_sha256)
        self.assertEqual(report.source_rules_sha256, report.target_rules_sha256)
        self.assertTrue(EXPECTED_RHO_INDEXES.issubset(set(report.indexes)))

        # Persistent DB header settings survive raw reconnect
        with closing(sqlite3.connect(self.target_db)) as raw_conn:
            self.assertEqual(raw_conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(raw_conn.execute("PRAGMA user_version").fetchone()[0], 1)

        with closing(get_db_connection(self.target_db, busy_timeout_ms=RHO_BUSY_TIMEOUT_MS)) as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            self.assertEqual(conn.execute("PRAGMA synchronous").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA busy_timeout").fetchone()[0], 30_000)
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchall(), [("ok",)])

            # Verify covering pattern index & rule bank index query plans
            pattern_plan = " ".join(
                str(r)
                for r in conn.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT COUNT(*) FROM model_trajectories
                    WHERE task_profile = ? AND failure_reason = ? AND created_at > ?
                    """,
                    ("STUDY_SYNTHESIS", "context_overflow", 0.0),
                ).fetchall()
            )
            self.assertIn("idx_model_trajectories_pattern", pattern_plan)

            rule_plan = " ".join(
                str(r)
                for r in conn.execute(
                    """
                    EXPLAIN QUERY PLAN
                    SELECT rule_text FROM rho_compounding_rules
                    WHERE task_profile = ?
                    ORDER BY id DESC
                    LIMIT 10
                    """,
                    ("STUDY_SYNTHESIS",),
                ).fetchall()
            )
            self.assertIn("idx_rho_rules_task_profile_id", rule_plan)

            # Subsequent autoincrement insert must advance cleanly past max id (5)
            conn.execute(
                """
                INSERT INTO model_trajectories (
                    request_id, task_profile, fingerprint, status,
                    attempts_count, failure_reason, created_at
                ) VALUES ('req-006', 'GENERAL', 'fp-6', 'SUCCESS', 1, NULL, 1700000020.0)
                """
            )
            conn.commit()
            new_id = conn.execute(
                "SELECT id FROM model_trajectories WHERE request_id = 'req-006'"
            ).fetchone()[0]
            self.assertGreater(new_id, 5)

        # Case A: Fault on fresh target cleans up partial artifacts atomically
        faulty_fresh_target = self.tmp_path / "aborted_fresh_rho.db"

        def abort_after_trajectories(stage: str, _conn: sqlite3.Connection) -> None:
            if stage == "after_trajectories":
                raise RuntimeError("Simulated mid-migration disk/power failure")

        with self.assertRaisesRegex(RuntimeError, "Simulated mid-migration"):
            migrate_rho_db(
                self.source_db,
                faulty_fresh_target,
                fault_hook=abort_after_trajectories,
            )
        self.assertFalse(faulty_fresh_target.exists())

        # Case B: Fault on existing pre-seeded sandbox DB rolls back DDL + rows atomically
        existing_sandbox = self.tmp_path / "existing_sandbox.db"
        with closing(sqlite3.connect(existing_sandbox)) as conn:
            conn.execute("CREATE TABLE sentinel_marker (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
            conn.execute("INSERT INTO sentinel_marker (id, label) VALUES (1, 'keep-me')")
            conn.commit()

        def abort_before_commit(stage: str, _conn: sqlite3.Connection) -> None:
            if stage == "before_commit":
                raise RuntimeError("Simulated commit abort")

        with self.assertRaisesRegex(RuntimeError, "Simulated commit abort"):
            migrate_rho_db(
                self.source_db,
                existing_sandbox,
                fault_hook=abort_before_commit,
            )

        with closing(sqlite3.connect(existing_sandbox)) as conn:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            tables = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            self.assertEqual(tables, {"sentinel_marker"})
            self.assertEqual(conn.execute("SELECT id, label FROM sentinel_marker").fetchall(), [(1, "keep-me")])

        # Non-empty RHO target refuses overwrite cleanly
        with self.assertRaises(RhoMigrationError):
            migrate_rho_db(self.source_db, self.target_db)

    def test_production_copy_sandbox_migration_and_prod_untouched(self) -> None:
        if not CANONICAL_DB_PATH.exists():
            self.skipTest("Production database.db not present in environment")

        prod_rho = PROJECT_ROOT / "data" / "rho.db"
        self.assertFalse(prod_rho.exists(), "Stage 1 must NEVER create production data/rho.db")

        with closing(
            sqlite3.connect(f"{CANONICAL_DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
        ) as prod_conn:
            prod_traj_pre = compute_table_snapshot(prod_conn, "model_trajectories", TRAJECTORY_COLUMNS)
            prod_rule_pre = compute_table_snapshot(prod_conn, "rho_compounding_rules", RULE_COLUMNS)

        # Copy production database to isolated temp file and run CLI migration in sandbox
        isolated_src_copy = self.tmp_path / "prod_isolated_copy.db"
        with closing(sqlite3.connect(f"{CANONICAL_DB_PATH.resolve().as_uri()}?mode=ro", uri=True)) as src:
            with closing(sqlite3.connect(isolated_src_copy)) as dst:
                src.backup(dst)

        python_exe = getattr(sys, "_base_executable", sys.executable)
        proc = subprocess.run(
            [
                python_exe,
                str(PROJECT_ROOT / "scripts" / "migrate_rho_db.py"),
                "--source",
                str(isolated_src_copy),
                "--target",
                str(self.target_db),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(proc.returncode, 0, f"CLI migration failed: stderr={proc.stderr}")

        with closing(sqlite3.connect(self.target_db)) as tgt:
            self.assertEqual(tgt.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(tgt.execute("PRAGMA user_version").fetchone()[0], 1)
            tgt_indexes = {
                r[0] for r in tgt.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
            }
            self.assertTrue(EXPECTED_RHO_INDEXES.issubset(tgt_indexes))
            tgt_traj_snap = compute_table_snapshot(tgt, "model_trajectories", TRAJECTORY_COLUMNS)
            tgt_rule_snap = compute_table_snapshot(tgt, "rho_compounding_rules", RULE_COLUMNS)

        self.assertEqual(tgt_traj_snap, prod_traj_pre)
        self.assertEqual(tgt_rule_snap, prod_rule_pre)
        self.assertGreaterEqual(tgt_traj_snap[0], 1954)
        self.assertGreaterEqual(tgt_rule_snap[0], 430)

        # Re-verify production database.db RHO data and absence of data/rho.db remain intact
        self.assertFalse(prod_rho.exists())
        with closing(
            sqlite3.connect(f"{CANONICAL_DB_PATH.resolve().as_uri()}?mode=ro", uri=True)
        ) as prod_conn_after:
            self.assertEqual(
                compute_table_snapshot(prod_conn_after, "model_trajectories", TRAJECTORY_COLUMNS),
                prod_traj_pre,
            )
            self.assertEqual(
                compute_table_snapshot(prod_conn_after, "rho_compounding_rules", RULE_COLUMNS),
                prod_rule_pre,
            )


if __name__ == "__main__":
    unittest.main()
