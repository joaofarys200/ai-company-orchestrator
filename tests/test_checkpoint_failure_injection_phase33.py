"""Failure Injection & Adversarial Integrity Test Suite for Phase 33.

Verifies system behavior under 12 critical failure modes:
1. Crash during delta write (partial/truncated file).
2. Crash during compaction (interrupted manifest swap / temporary file).
3. Incomplete delta (missing mandatory keys).
4. Corrupted delta payload (tampered content / hash mismatch).
5. Missing delta in chain (sequence discontinuity: 1, 3 without 2).
6. Duplicated delta injection (replaying sequence 2).
7. Reordered delta application (violating parent_hash linkage).
8. Corrupted base snapshot (tampered base state).
9. Interrupted fsync / atomic rename simulation.
10. Permission error / read-only filesystem detection.
11. Disk full / write exhaustion simulation.
12. Process termination / sudden recovery validation.

Invariant: System MUST DETECT and either RECOVER or BLOCK; NEVER silently reconstruct corrupted state.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from agents.incremental_checkpoint_engine import (
    BaseSnapshot,
    CheckpointCompactionError,
    CheckpointDelta,
    CheckpointIntegrityError,
    CompactionEngine,
    DeltaComputer,
    DeltaReconstructor,
    IdempotencyEngine,
    IncrementalPersistenceAdapter,
    IntegrityValidator,
    canonical_json_bytes,
)
from agents.mission_orchestrator import Checkpoint
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


class TestCheckpointFailureInjectionPhase33(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="phase33_fail_test_")
        self.mission_id = f"m_fail_{uuid.uuid4().hex[:6]}"
        self.project_id = "test_project"
        os.makedirs(os.path.join(self.temp_dir, "workspace", "projects", self.project_id), exist_ok=True)
        self.adapter = IncrementalPersistenceAdapter(
            base_dir=self.temp_dir,
            mission_id=self.mission_id,
            project_id=self.project_id,
            compaction_interval=5,
        )

    def tearDown(self) -> None:
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_cp(self, seq: int) -> dict:
        tg = TaskGraph()
        for i in range(5):
            status = TaskStatus.COMPLETED if i < seq else TaskStatus.PENDING
            tg.add_node(TaskNode(task_id=f"t{i}", title=f"Task {i}", status=status))

        cp = Checkpoint(
            checkpoint_id=f"cp_{seq:04d}",
            sequence=seq,
            mission_id=self.mission_id,
            project_id=self.project_id,
            mission_status="RUNNING" if seq < 5 else "COMPLETED",
            task_graph_data=tg.to_dict(),
            completed_task_ids=[f"t{i}" for i in range(seq)],
            pending_task_ids=[f"t{i}" for i in range(seq, 5)],
            running_task_ids=[],
            failed_task_ids=[],
            blocked_task_ids=[],
            evidence_refs=[f"ev_{i}" for i in range(seq)],
            outputs={f"t{i}": i for i in range(seq)},
            created_at=f"2026-09-08T20:00:{seq:02d}Z",
            description=f"Seq {seq}",
        )
        return cp.to_dict()

    def test_failure_01_crash_during_delta_write_truncated_file(self) -> None:
        """Truncated delta file must be detected and not cause silent corruption."""
        self.adapter.save_checkpoint(self._make_cp(0))
        self.adapter.save_checkpoint(self._make_cp(1))

        delta_path = self.adapter.checkpoints_dir / "delta_0001.json"
        self.assertTrue(delta_path.is_file())

        # Simulate sudden process crash / half-written file
        with open(delta_path, "w") as f:
            f.write('{"delta_id": "delta_0001", "sequence": 1, "parent_hash": "abc", "trunca')

        # Loading must either raise or detect truncation, never silently reconstruct invalid state
        with self.assertRaises(Exception):
            self.adapter.load_latest_checkpoint()

    def test_failure_02_crash_during_compaction_tmp_cleanup(self) -> None:
        """Simulating a crash during compaction leaves existing valid snapshots and deltas intact."""
        for seq in range(4):
            self.adapter.save_checkpoint(self._make_cp(seq))

        # Simulate left-over .tmp file from aborted compaction
        tmp_snap = self.adapter.checkpoints_dir / "snapshot_0003.tmp"
        with open(tmp_snap, "w") as f:
            f.write('{"half_written_compaction": true}')

        # Reconstructed state must succeed using verified active base snapshot + deltas
        state = self.adapter.load_latest_checkpoint()
        self.assertIsNotNone(state)
        self.assertEqual(state["sequence"], 3)

    def test_failure_03_incomplete_delta_missing_keys(self) -> None:
        """Delta missing mandatory fields fails reconstruction validation."""
        cp0 = self._make_cp(0)
        snap = BaseSnapshot("s0", 0, self.mission_id, self.project_id, cp0["created_at"], "0" * 64, "", cp0)
        snap.content_hash = snap.calculate_hash()

        # Incomplete delta
        incomplete_dict = {
            "delta_id": "d1",
            "sequence": 1,
            "mission_id": self.mission_id,
            # missing parent_hash and content_hash
        }
        with self.assertRaises(KeyError):
            CheckpointDelta.from_dict(incomplete_dict)

    def test_failure_04_corrupted_delta_content_hash_mismatch(self) -> None:
        """Tampered delta payload must be flagged immediately by IntegrityValidator."""
        cp0 = self._make_cp(0)
        cp1 = self._make_cp(1)
        snap = BaseSnapshot("s0", 0, self.mission_id, self.project_id, cp0["created_at"], "0" * 64, "", cp0)
        snap.content_hash = snap.calculate_hash()

        delta = DeltaComputer.compute_delta(cp0, cp1, snap.content_hash)
        # Tamper payload: change task status without updating hash
        delta.mutated_tasks["t0"]["status"] = "FAILED"

        valid, reason = IntegrityValidator.verify_chain(snap, [delta])
        self.assertFalse(valid)
        self.assertIn("content hash corrupt", reason)

        with self.assertRaises(CheckpointIntegrityError):
            DeltaReconstructor.reconstruct_state(snap, [delta], verify_chain=True)

    def test_failure_05_missing_delta_in_chain_gap(self) -> None:
        """Missing delta (gap in sequence) must fail chain verification."""
        cp0 = self._make_cp(0)
        cp1 = self._make_cp(1)
        cp2 = self._make_cp(2)

        snap = BaseSnapshot("s0", 0, self.mission_id, self.project_id, cp0["created_at"], "0" * 64, "", cp0)
        snap.content_hash = snap.calculate_hash()

        d1 = DeltaComputer.compute_delta(cp0, cp1, snap.content_hash)
        d2 = DeltaComputer.compute_delta(cp1, cp2, d1.content_hash)

        # Gap: passing [d2] without [d1]
        valid, reason = IntegrityValidator.verify_chain(snap, [d2])
        self.assertFalse(valid)
        self.assertIn("parent_hash", reason)

    def test_failure_06_duplicated_delta_reapplication(self) -> None:
        """Replaying an already processed delta sequence is detected and blocked."""
        idempotency = IdempotencyEngine()
        cp0 = self._make_cp(0)
        cp1 = self._make_cp(1)
        d1 = DeltaComputer.compute_delta(cp0, cp1, "0" * 64)

        self.assertFalse(idempotency.is_applied(d1))
        idempotency.record_applied(d1)
        self.assertTrue(idempotency.is_applied(d1))

        # Second submission of same sequence is recognized
        d1_dup = copy.deepcopy(d1)
        self.assertTrue(idempotency.is_applied(d1_dup))

    def test_failure_07_reordered_delta_application(self) -> None:
        """Deltas applied out of sequence fail parent_hash verification."""
        cp0 = self._make_cp(0)
        cp1 = self._make_cp(1)
        cp2 = self._make_cp(2)

        snap = BaseSnapshot("s0", 0, self.mission_id, self.project_id, cp0["created_at"], "0" * 64, "", cp0)
        snap.content_hash = snap.calculate_hash()

        d1 = DeltaComputer.compute_delta(cp0, cp1, snap.content_hash)
        d2 = DeltaComputer.compute_delta(cp1, cp2, d1.content_hash)

        # Reordered: [d2, d1]
        valid, reason = IntegrityValidator.verify_chain(snap, [d2, d1])
        self.assertFalse(valid)
        self.assertIn("parent_hash", reason)

    def test_failure_08_corrupted_base_snapshot(self) -> None:
        """Corrupted base snapshot must fail validation immediately."""
        cp0 = self._make_cp(0)
        snap = BaseSnapshot("s0", 0, self.mission_id, self.project_id, cp0["created_at"], "0" * 64, "", cp0)
        snap.content_hash = snap.calculate_hash()

        # Tamper base snapshot
        snap.checkpoint_data["mission_status"] = "CORRUPT"

        valid, reason = IntegrityValidator.verify_chain(snap, [])
        self.assertFalse(valid)
        self.assertIn("Base snapshot", reason)

    def test_failure_09_atomic_rename_safety(self) -> None:
        """Atomic write ensures that destination file is never in partially written state."""
        delta = DeltaComputer.compute_delta(self._make_cp(0), self._make_cp(1), "0" * 64)
        self.adapter._write_delta_atomic(delta)
        delta_path = self.adapter.checkpoints_dir / f"delta_{delta.sequence:04d}.json"
        tmp_path = self.adapter.checkpoints_dir / f"delta_{delta.sequence:04d}.tmp"

        self.assertTrue(delta_path.is_file())
        self.assertFalse(tmp_path.is_file())

    def test_failure_10_permission_error_graceful_handling(self) -> None:
        """Permission error during delta write raises cleanly without corruption."""
        with patch("builtins.open", side_effect=PermissionError("EACCES: Permission denied")):
            with self.assertRaises(PermissionError):
                self.adapter._write_delta_atomic(
                    DeltaComputer.compute_delta(self._make_cp(0), self._make_cp(1), "0" * 64)
                )

    def test_failure_11_disk_full_error_handling(self) -> None:
        """Disk full (ENOSPC / OSError) is cleanly raised."""
        with patch("os.fsync", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(OSError):
                self.adapter._write_delta_atomic(
                    DeltaComputer.compute_delta(self._make_cp(0), self._make_cp(1), "0" * 64)
                )

    def test_failure_12_process_termination_recovery_continuity(self) -> None:
        """A new process adapter successfully recovers and continues sequence without breakage."""
        for seq in range(3):
            self.adapter.save_checkpoint(self._make_cp(seq))

        # Simulate brand new process launching and attaching to existing directory
        new_process_adapter = IncrementalPersistenceAdapter(
            base_dir=self.temp_dir,
            mission_id=self.mission_id,
            project_id=self.project_id,
            compaction_interval=5,
        )

        recovered = new_process_adapter.load_latest_checkpoint()
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["sequence"], 2)

        # New process writes sequence 3 smoothly
        res = new_process_adapter.save_checkpoint(self._make_cp(3))
        self.assertEqual(res["type"], "DELTA")
        self.assertEqual(res["sequence"], 3)

        latest = new_process_adapter.load_latest_checkpoint()
        self.assertEqual(latest["sequence"], 3)


if __name__ == "__main__":
    unittest.main()
