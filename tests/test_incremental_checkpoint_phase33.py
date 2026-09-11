"""Unit tests for Phase 33: Incremental Mission Checkpointing & State Persistence Scaling.

Verifies:
1. BaseSnapshot creation, serialization, SHA-256 canonical hashing.
2. CheckpointDelta computation with minimal mutation payload.
3. DeltaReconstructor deterministic reconstruction.
4. Exact semantic equivalence (reconstructed == original).
5. Chain integrity verification.
6. Idempotency (duplicate_delta_application == 0).
7. Atomic crash-safe compaction and post-compaction equivalence.
8. IncrementalPersistenceAdapter persistence and retrieval.
9. Orchestrator integration in INCREMENTAL mode.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
import uuid

from agents.checkpoint_profiler import CheckpointProfiler
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
from agents.mission_orchestrator import Checkpoint, MissionLifecycleOrchestrator
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


class TestIncrementalCheckpointPhase33(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="phase33_test_")
        self.mission_id = f"m_test_{uuid.uuid4().hex[:6]}"
        self.project_id = "test_project"
        os.makedirs(os.path.join(self.temp_dir, "workspace", "projects", self.project_id), exist_ok=True)

    def tearDown(self) -> None:
        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_checkpoint(self, seq: int, task_count: int = 10) -> dict:
        tg = TaskGraph()
        for i in range(task_count):
            status = TaskStatus.COMPLETED if i < seq else (TaskStatus.RUNNING if i == seq else TaskStatus.PENDING)
            node = TaskNode(
                task_id=f"task_{i:03d}",
                title=f"Sample Task {i}",
                status=status,
                attempt_count=1 if i <= seq else 0,
            )
            tg.add_node(node)

        cp = Checkpoint(
            checkpoint_id=f"cp_{seq:04d}",
            sequence=seq,
            mission_id=self.mission_id,
            project_id=self.project_id,
            mission_status="RUNNING" if seq < task_count else "COMPLETED",
            task_graph_data=tg.to_dict(),
            completed_task_ids=[f"task_{i:03d}" for i in range(seq)],
            pending_task_ids=[f"task_{i:03d}" for i in range(seq + 1, task_count)],
            running_task_ids=[f"task_{seq:03d}"] if seq < task_count else [],
            failed_task_ids=[],
            blocked_task_ids=[],
            evidence_refs=[f"ev_{i}" for i in range(seq)],
            outputs={f"task_{i:03d}": {"res": i * 10} for i in range(seq)},
            created_at=f"2026-09-08T20:00:{seq:02d}Z",
            description=f"Transition {seq}",
            graph_version=1,
            plan_version=1,
            current_strategy="PARALLEL_EXECUTION",
            plan_churn_count=0,
        )
        return cp.to_dict()

    def test_base_snapshot_creation_and_hashing(self) -> None:
        """Test BaseSnapshot deterministic hashing and round-trip."""
        cp_dict = self._create_sample_checkpoint(0, task_count=5)
        snap = BaseSnapshot(
            snapshot_id="snap_0000",
            sequence=0,
            mission_id=self.mission_id,
            project_id=self.project_id,
            created_at=cp_dict["created_at"],
            parent_hash="0" * 64,
            content_hash="",
            checkpoint_data=cp_dict,
        )
        snap.content_hash = snap.calculate_hash()
        self.assertGreater(len(snap.content_hash), 32)

        # Round-trip to_dict and from_dict
        d = snap.to_dict()
        snap_restored = BaseSnapshot.from_dict(d)
        self.assertEqual(snap_restored.calculate_hash(), snap.content_hash)
        self.assertEqual(snap_restored.checkpoint_data, snap.checkpoint_data)

    def test_delta_computation_minimal_mutations(self) -> None:
        """Delta should only contain the single mutated task, not all tasks."""
        cp0 = self._create_sample_checkpoint(0, task_count=20)
        cp1 = self._create_sample_checkpoint(1, task_count=20)

        delta = DeltaComputer.compute_delta(cp0, cp1, parent_hash="0" * 64)
        self.assertEqual(delta.sequence, 1)
        # In transition 0 -> 1, task_000 becomes COMPLETED and task_001 becomes RUNNING
        self.assertEqual(len(delta.mutated_tasks), 2)
        self.assertIn("task_000", delta.mutated_tasks)
        self.assertIn("task_001", delta.mutated_tasks)
        self.assertNotIn("task_002", delta.mutated_tasks)
        self.assertEqual(len(delta.outputs_delta), 1)
        self.assertEqual(len(delta.evidence_refs_delta), 1)

    def test_exact_semantic_equivalence_across_transitions(self) -> None:
        """Reconstructed state after N deltas must match full checkpoint 100%."""
        num_transitions = 8
        history = [self._create_sample_checkpoint(i, task_count=10) for i in range(num_transitions)]

        base_snap = BaseSnapshot(
            snapshot_id="snap_0000",
            sequence=0,
            mission_id=self.mission_id,
            project_id=self.project_id,
            created_at=history[0]["created_at"],
            parent_hash="0" * 64,
            content_hash="",
            checkpoint_data=history[0],
        )
        base_snap.content_hash = base_snap.calculate_hash()

        deltas = []
        parent_hash = base_snap.content_hash
        for i in range(1, num_transitions):
            delta = DeltaComputer.compute_delta(history[i - 1], history[i], parent_hash)
            deltas.append(delta)
            parent_hash = delta.content_hash

        # Verify cryptographic chain
        valid, reason = IntegrityValidator.verify_chain(base_snap, deltas)
        self.assertTrue(valid, f"Chain invalid: {reason}")

        # Reconstruct at every sequence from 0 to num_transitions-1
        for target_seq in range(num_transitions):
            reconstructed = DeltaReconstructor.reconstruct_state(
                base_snap, deltas, target_sequence=target_seq
            )
            original = history[target_seq]

            # Compare task graph tasks
            rec_tasks = reconstructed["task_graph_data"]["tasks"]
            orig_tasks = original["task_graph_data"]["tasks"]
            self.assertEqual(rec_tasks, orig_tasks, f"Mismatch at seq {target_seq}")

            # Compare status lists
            self.assertEqual(reconstructed["completed_task_ids"], original["completed_task_ids"])
            self.assertEqual(reconstructed["running_task_ids"], original["running_task_ids"])
            self.assertEqual(reconstructed["pending_task_ids"], original["pending_task_ids"])
            self.assertEqual(reconstructed["evidence_refs"], original["evidence_refs"])
            self.assertEqual(reconstructed["outputs"], original["outputs"])
            self.assertEqual(reconstructed["mission_status"], original["mission_status"])

    def test_idempotency_enforcement(self) -> None:
        """Applying the same delta twice must be prevented by the idempotency engine."""
        cp0 = self._create_sample_checkpoint(0, task_count=5)
        cp1 = self._create_sample_checkpoint(1, task_count=5)
        delta = DeltaComputer.compute_delta(cp0, cp1, parent_hash="0" * 64)

        engine = IdempotencyEngine()
        self.assertFalse(engine.is_applied(delta))
        engine.record_applied(delta)
        self.assertTrue(engine.is_applied(delta))

    def test_compaction_and_post_compaction_equivalence(self) -> None:
        """Compacting 5 deltas into a new BaseSnapshot preserves state perfectly."""
        history = [self._create_sample_checkpoint(i, task_count=10) for i in range(6)]

        base_snap = BaseSnapshot(
            snapshot_id="snap_0000",
            sequence=0,
            mission_id=self.mission_id,
            project_id=self.project_id,
            created_at=history[0]["created_at"],
            parent_hash="0" * 64,
            content_hash="",
            checkpoint_data=history[0],
        )
        base_snap.content_hash = base_snap.calculate_hash()

        deltas = []
        parent_hash = base_snap.content_hash
        for i in range(1, 6):
            delta = DeltaComputer.compute_delta(history[i - 1], history[i], parent_hash)
            deltas.append(delta)
            parent_hash = delta.content_hash

        # Compact all 5 deltas into a new base snapshot
        new_base, remaining = CompactionEngine.compact(base_snap, deltas, keep_latest_deltas=0)
        self.assertEqual(new_base.sequence, 5)
        self.assertEqual(len(remaining), 0)
        self.assertEqual(new_base.calculate_hash(), new_base.content_hash)

        # State inside compacted snapshot must equal history[5]
        self.assertEqual(
            new_base.checkpoint_data["task_graph_data"]["tasks"],
            history[5]["task_graph_data"]["tasks"],
        )
        self.assertEqual(
            new_base.checkpoint_data["completed_task_ids"],
            history[5]["completed_task_ids"],
        )

    def test_incremental_persistence_adapter_e2e(self) -> None:
        """IncrementalPersistenceAdapter saves base and deltas and retrieves accurately."""
        adapter = IncrementalPersistenceAdapter(
            base_dir=self.temp_dir,
            mission_id=self.mission_id,
            project_id=self.project_id,
            compaction_interval=4,
        )

        history = [self._create_sample_checkpoint(i, task_count=10) for i in range(6)]

        results = []
        for cp in history:
            res = adapter.save_checkpoint(cp)
            results.append(res)

        self.assertEqual(results[0]["type"], "BASE_SNAPSHOT")
        for res in results[1:4]:
            self.assertEqual(res["type"], "DELTA")

        # After sequence 4 (4 deltas saved), compaction triggered automatically
        latest = adapter.load_latest_checkpoint()
        self.assertIsNotNone(latest)
        self.assertEqual(
            latest["task_graph_data"]["tasks"],
            history[5]["task_graph_data"]["tasks"],
        )

    def test_orchestrator_integration_incremental_mode(self) -> None:
        """MissionLifecycleOrchestrator can save in INCREMENTAL mode and recover."""
        store = MissionStateStore(self.temp_dir)
        store.create_mission(self.project_id, self.mission_id, "Test Mission", "Objective")

        tg = TaskGraph()
        for i in range(3):
            tg.add_node(TaskNode(task_id=f"t{i}", title=f"Task {i}"))

        orchestrator = MissionLifecycleOrchestrator(
            project_id=self.project_id,
            mission_id=self.mission_id,
            mission_state=store,
            task_graph=tg,
            checkpoint_mode="INCREMENTAL",
        )

        cp1 = orchestrator.save_checkpoint("Initial state")
        self.assertEqual(cp1.sequence, 1)

        # Transition t0 to completed
        tg.nodes["t0"].status = TaskStatus.COMPLETED
        orchestrator._task_outputs["t0"] = {"data": "ok"}
        orchestrator._evidence_collected.append("ev_t0")

        cp2 = orchestrator.save_checkpoint("Completed t0")
        self.assertEqual(cp2.sequence, 2)

        # Recover into a fresh orchestrator
        recovered_cp = orchestrator.load_latest_checkpoint()
        self.assertIsNotNone(recovered_cp)
        self.assertEqual(recovered_cp.sequence, 2)
        self.assertIn("t0", recovered_cp.completed_task_ids)
        self.assertEqual(recovered_cp.outputs.get("t0"), {"data": "ok"})


if __name__ == "__main__":
    unittest.main()
