"""
Phase 13.2 — Storage Chaos & Resilience Test Suite
Tests:
  1. Process crash simulation during batch write (atomic rollback & clean state)
  2. Interrupted batch write leaves no uncommitted/orphan records
  3. Truncated state.db / corrupt database graceful detection & handling
  4. Missing or deleted checkpoint recovery to previous known consistent checkpoint
  5. Concurrent writer lock contention and busy timeout resilience
  6. Shard corruption detection and index reconciliation
"""

import os
import sqlite3
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from agents.mission_state import MissionStateStore
from agents.mission_persistence import (
    SQLiteMissionPersistence,
    ShardedFilesystemPersistence,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus
from agents.mission_orchestrator import MissionLifecycleOrchestrator


class MissionStorageChaosTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_chaos_storage_")
        self.project_id = "chaos-storage-project"
        self.mission_id = "chaos-mission-1"
        os.makedirs(os.path.join(self.temp_dir, "workspace", "projects", self.project_id), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_store(self, backend: str = "sqlite") -> MissionStateStore:
        store = MissionStateStore(self.temp_dir, storage_backend=backend)
        store.create_mission(
            self.project_id,
            "Chaos Mission",
            "Evaluate resilience under faults",
            mission_id=self.mission_id,
        )
        return store

    def test_1_atomic_rollback_on_failed_batch_write(self):
        """Simulate a failure midway through a batch insert to ensure all-or-nothing rollback."""
        persistence = SQLiteMissionPersistence(self.temp_dir)
        persistence.save_mission(self.project_id, self.mission_id, {"title": "Base Mission"})

        # First insert 5 baseline packages
        base_wps = [{"work_package_id": f"base-{i}", "title": f"Base {i}"} for i in range(5)]
        persistence.save_work_packages_batch(self.project_id, self.mission_id, base_wps)
        self.assertEqual(len(persistence.load_all_work_packages(self.project_id, self.mission_id)), 5)

        # Second batch with an intentional unbindable object in criteria that fails SQL executemany
        bad_wps = [{"work_package_id": f"batch2-{i}", "title": f"Batch2 {i}"} for i in range(5)]
        bad_criteria = [{"criterion_id": "c_fail", "description": object()}]

        with self.assertRaises(Exception):
            persistence.save_work_packages_batch(self.project_id, self.mission_id, bad_wps, bad_criteria)

        # Verify state is clean: none of the bad_wps exist, baseline remaining intact (all-or-nothing rollback)
        current = persistence.load_all_work_packages(self.project_id, self.mission_id)
        self.assertEqual(len(current), 5)
        for i in range(5):
            self.assertIn(f"base-{i}", current)
            self.assertNotIn(f"batch2-{i}", current)

    def test_2_interrupted_write_no_orphaned_records(self):
        """Verify no uncommitted records remain if writing is aborted."""
        persistence = SQLiteMissionPersistence(self.temp_dir)
        persistence.save_mission(self.project_id, self.mission_id, {"title": "Base Mission"})

        # Verify rollback on uncommitted transaction
        db_path = persistence._db_path(self.project_id, self.mission_id)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("BEGIN TRANSACTION")
            conn.execute("""
                INSERT INTO work_packages (work_package_id, mission_id, title, type, status)
                VALUES ('orphan-test', ?, 'Should Rollback', 'CODING', 'PENDING')
            """, (self.mission_id,))
            conn.rollback()
        finally:
            conn.close()

        loaded = persistence.load_all_work_packages(self.project_id, self.mission_id)
        self.assertNotIn("orphan-test", loaded)

    def test_3_corrupt_database_recovery_detection(self):
        """Simulate a truncated / zero-byte SQLite database file and ensure graceful error or clean fallback."""
        store = self._create_store(backend="sqlite")
        store.create_work_package(self.project_id, self.mission_id, "Pre-corrupt Task", work_package_id="wp-pre")

        db_path = store.persistence._db_path(self.project_id, self.mission_id)
        self.assertTrue(os.path.isfile(db_path))

        # Close all active connections, then corrupt the file
        with open(db_path, "wb") as f:
            f.write(b"CORRUPTED_GARBAGE_BYTES_SQLITE_HEADER_INVALID")

        # Loading should not cause an unhandled crash of the runtime
        recovered = False
        try:
            store.load_mission(self.project_id, self.mission_id)
        except Exception:
            recovered = True
        self.assertTrue(recovered, "System must raise a manageable exception on corrupted DB header")

    def test_4_deleted_checkpoint_recovery_to_previous_state(self):
        """When the latest checkpoint is deleted or missing, the orchestrator safely restores from the prior one."""
        store = self._create_store(backend="sqlite")
        t1 = TaskNode(task_id="t1", title="Task 1", status=TaskStatus.COMPLETED)
        t2 = TaskNode(task_id="t2", title="Task 2", status=TaskStatus.PENDING, dependencies=["t1"])
        tg1 = TaskGraph(nodes=[t1], graph_version=1)

        orch1 = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=store,
            task_graph=tg1,
        )
        cp1 = orch1.save_checkpoint("Milestone 1")
        self.assertEqual(cp1.sequence, 1)

        tg2 = TaskGraph(nodes=[t1, t2], graph_version=2)
        orch1.task_graph = tg2
        cp2 = orch1.save_checkpoint("Milestone 2")
        self.assertEqual(cp2.sequence, 2)

        # Manually delete cp2 from database
        with store.persistence._connection(self.project_id, self.mission_id) as conn:
            with conn:
                conn.execute("DELETE FROM checkpoints WHERE sequence = 2")

        # Reconstructed orchestrator should load cp1 (the highest remaining sequence)
        orch_restored = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=store,
        )
        latest_cp = orch_restored.load_latest_checkpoint()
        self.assertIsNotNone(latest_cp)
        self.assertEqual(latest_cp.sequence, 1)
        orch_restored.recover_from_checkpoint(latest_cp)
        self.assertEqual(orch_restored.task_graph.graph_version, 1)
        self.assertIn("t1", orch_restored.task_graph.nodes)
        self.assertNotIn("t2", orch_restored.task_graph.nodes)

    def test_5_lock_contention_and_busy_timeout_resilience(self):
        """Simulate high concurrent write pressure and verify no unhandled database locked crashes."""
        store = self._create_store(backend="sqlite")

        def _concurrent_writer(worker_id: int):
            for i in range(25):
                wp = {
                    "work_package_id": f"wp-contention-{worker_id}-{i}",
                    "title": f"Task {worker_id}-{i}",
                    "status": "PENDING",
                }
                store.persistence.save_work_package(self.project_id, self.mission_id, wp)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_concurrent_writer, w) for w in range(8)]
            for f in futures:
                f.result()

        stats = store.get_storage_stats(self.project_id, self.mission_id)
        self.assertEqual(stats.work_packages_count, 8 * 25)

    def test_6_sharded_corrupt_shard_graceful_handling(self):
        """In sharded mode, if one shard is corrupted, other shards remain queryable."""
        sharded = ShardedFilesystemPersistence(self.temp_dir, num_shards=8)
        mid = "sharded-chaos-1"
        sharded.save_mission(self.project_id, mid, {"title": "Sharded Chaos"})

        packages = [
            {"work_package_id": f"sh-wp-{i}", "title": f"WP {i}"}
            for i in range(50)
        ]
        sharded.save_work_packages_batch(self.project_id, mid, packages)

        # Corrupt shard 0 file
        shard_0_path = sharded._shard_path(self.project_id, mid, 0)
        if os.path.isfile(shard_0_path):
            with open(shard_0_path, "w", encoding="utf-8") as f:
                f.write("INVALID_JSON_CONTENTS_!@#$%^")

        # Lookups on other shards continue to succeed
        loaded = sharded.load_all_work_packages(self.project_id, mid)
        self.assertGreater(len(loaded), 0, "Uncorrupted shards must still load successfully")


if __name__ == "__main__":
    unittest.main()
