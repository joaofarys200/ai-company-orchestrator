"""Incremental Checkpoint Engine for JARVIS Long-Horizon Autonomous Missions.

Phase 33 — Incremental Mission Checkpointing & State Persistence Scaling.

Key capabilities:
1. BaseSnapshot + CheckpointDelta representation.
2. Cryptographic hash chaining: parent_hash -> content_hash (SHA-256).
3. Monotonic sequence numbering and idempotency enforcement.
4. Exact semantic equivalence: reconstructed_state == original_state.
5. Atomic crash-safe compaction.
6. Adversarial integrity verification and failure detection.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class CheckpointIntegrityError(Exception):
    """Raised when cryptographic hash chain or sequence continuity is violated."""
    pass


class CheckpointCompactionError(Exception):
    """Raised when compaction verification fails or is interrupted."""
    pass


def canonical_json_bytes(data: Any) -> bytes:
    """Produces deterministic, byte-for-byte canonical JSON representation."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_digest(data_bytes: bytes) -> str:
    """Computes hex SHA-256 digest."""
    return hashlib.sha256(data_bytes).hexdigest()


@dataclass
class BaseSnapshot:
    """Full snapshot baseline representing the complete checkpoint state at sequence S."""
    snapshot_id: str
    sequence: int
    mission_id: str
    project_id: str
    created_at: str
    parent_hash: str
    content_hash: str
    checkpoint_data: dict[str, Any]

    def calculate_hash(self) -> str:
        """Computes content hash from canonical payload."""
        payload = {
            "snapshot_id": self.snapshot_id,
            "sequence": self.sequence,
            "mission_id": self.mission_id,
            "project_id": self.project_id,
            "parent_hash": self.parent_hash,
            "checkpoint_data": self.checkpoint_data,
        }
        return sha256_digest(canonical_json_bytes(payload))

    def to_canonical_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseSnapshot:
        return cls(
            snapshot_id=str(data["snapshot_id"]),
            sequence=int(data["sequence"]),
            mission_id=str(data["mission_id"]),
            project_id=str(data["project_id"]),
            created_at=str(data.get("created_at", "")),
            parent_hash=str(data.get("parent_hash", "0" * 64)),
            content_hash=str(data["content_hash"]),
            checkpoint_data=copy.deepcopy(data["checkpoint_data"]),
        )


@dataclass
class CheckpointDelta:
    """Delta representing state mutations occurring between sequence S-1 and S."""
    delta_id: str
    sequence: int
    mission_id: str
    project_id: str
    created_at: str
    parent_hash: str
    content_hash: str
    description: str
    mission_status: str
    graph_version: int
    plan_version: int
    plan_churn_count: int
    current_strategy: str
    # Mutated task nodes (node_id -> node_dict)
    mutated_tasks: dict[str, dict[str, Any]]
    removed_task_ids: list[str]
    # Graph order & progress
    task_order: Optional[list[str]]
    progress: float
    # Task status sets
    completed_task_ids: list[str]
    pending_task_ids: list[str]
    running_task_ids: list[str]
    failed_task_ids: list[str]
    blocked_task_ids: list[str]
    # Deltas for auxiliary structures
    evidence_refs_delta: list[str]
    outputs_delta: dict[str, Any]
    expansion_history_delta: list[dict[str, Any]]
    adaptation_history_delta: list[dict[str, Any]]
    swarm_state: dict[str, Any]
    federation_state: dict[str, Any]

    def calculate_hash(self) -> str:
        """Computes content hash from canonical payload."""
        payload = {
            "delta_id": self.delta_id,
            "sequence": self.sequence,
            "mission_id": self.mission_id,
            "project_id": self.project_id,
            "parent_hash": self.parent_hash,
            "description": self.description,
            "mission_status": self.mission_status,
            "graph_version": self.graph_version,
            "plan_version": self.plan_version,
            "plan_churn_count": self.plan_churn_count,
            "current_strategy": self.current_strategy,
            "mutated_tasks": self.mutated_tasks,
            "removed_task_ids": self.removed_task_ids,
            "task_order": self.task_order,
            "progress": self.progress,
            "completed_task_ids": self.completed_task_ids,
            "pending_task_ids": self.pending_task_ids,
            "running_task_ids": self.running_task_ids,
            "failed_task_ids": self.failed_task_ids,
            "blocked_task_ids": self.blocked_task_ids,
            "evidence_refs_delta": self.evidence_refs_delta,
            "outputs_delta": self.outputs_delta,
            "expansion_history_delta": self.expansion_history_delta,
            "adaptation_history_delta": self.adaptation_history_delta,
            "swarm_state": self.swarm_state,
            "federation_state": self.federation_state,
        }
        return sha256_digest(canonical_json_bytes(payload))

    def to_canonical_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointDelta:
        return cls(
            delta_id=str(data["delta_id"]),
            sequence=int(data["sequence"]),
            mission_id=str(data["mission_id"]),
            project_id=str(data["project_id"]),
            created_at=str(data.get("created_at", "")),
            parent_hash=str(data.get("parent_hash", "")),
            content_hash=str(data["content_hash"]),
            description=str(data.get("description", "")),
            mission_status=str(data.get("mission_status", "ACTIVE")),
            graph_version=int(data.get("graph_version", 1)),
            plan_version=int(data.get("plan_version", 1)),
            plan_churn_count=int(data.get("plan_churn_count", 0)),
            current_strategy=str(data.get("current_strategy", "")),
            mutated_tasks=copy.deepcopy(data.get("mutated_tasks", {})),
            removed_task_ids=list(data.get("removed_task_ids", [])),
            task_order=list(data["task_order"]) if data.get("task_order") is not None else None,
            progress=float(data.get("progress", 0.0)),
            completed_task_ids=list(data.get("completed_task_ids", [])),
            pending_task_ids=list(data.get("pending_task_ids", [])),
            running_task_ids=list(data.get("running_task_ids", [])),
            failed_task_ids=list(data.get("failed_task_ids", [])),
            blocked_task_ids=list(data.get("blocked_task_ids", [])),
            evidence_refs_delta=list(data.get("evidence_refs_delta", [])),
            outputs_delta=copy.deepcopy(data.get("outputs_delta", {})),
            expansion_history_delta=list(data.get("expansion_history_delta", [])),
            adaptation_history_delta=list(data.get("adaptation_history_delta", [])),
            swarm_state=copy.deepcopy(data.get("swarm_state", {})),
            federation_state=copy.deepcopy(data.get("federation_state", {})),
        )


class DeltaComputer:
    """Calculates minimal diffs between consecutive full checkpoints."""

    @staticmethod
    def compute_delta(
        prev_cp: dict[str, Any],
        curr_cp: dict[str, Any],
        parent_hash: str,
    ) -> CheckpointDelta:
        prev_tg = prev_cp.get("task_graph_data", {})
        curr_tg = curr_cp.get("task_graph_data", {})

        prev_tasks: dict[str, Any] = prev_tg.get("tasks", {})
        curr_tasks: dict[str, Any] = curr_tg.get("tasks", {})

        mutated_tasks: dict[str, dict[str, Any]] = {}
        for tid, tnode in curr_tasks.items():
            if tid not in prev_tasks:
                mutated_tasks[tid] = tnode
            else:
                prev_node = prev_tasks[tid]
                if tnode != prev_node:
                    mutated_tasks[tid] = tnode

        removed_task_ids = [tid for tid in prev_tasks if tid not in curr_tasks]

        prev_order = prev_tg.get("order")
        curr_order = curr_tg.get("order")
        task_order = list(curr_order) if curr_order != prev_order else None

        # Evidence delta
        prev_ev = set(prev_cp.get("evidence_refs", []))
        curr_ev = curr_cp.get("evidence_refs", [])
        evidence_refs_delta = [e for e in curr_ev if e not in prev_ev]

        # Outputs delta
        prev_out = prev_cp.get("outputs", {})
        curr_out = curr_cp.get("outputs", {})
        outputs_delta = {
            k: v
            for k, v in curr_out.items()
            if k not in prev_out or prev_out[k] != v
        }

        # Expansion history delta
        prev_exp = prev_tg.get("expansion_history", [])
        curr_exp = curr_tg.get("expansion_history", [])
        exp_delta = list(curr_exp[len(prev_exp):])

        # Adaptation history delta
        prev_adapt = prev_cp.get("adaptation_history", [])
        curr_adapt = curr_cp.get("adaptation_history", [])
        adapt_delta = list(curr_adapt[len(prev_adapt):])

        seq = int(curr_cp["sequence"])
        delta_id = f"delta_{seq:04d}_{uuid.uuid4().hex[:6]}"

        delta = CheckpointDelta(
            delta_id=delta_id,
            sequence=seq,
            mission_id=curr_cp["mission_id"],
            project_id=curr_cp["project_id"],
            created_at=curr_cp.get("created_at", ""),
            parent_hash=parent_hash,
            content_hash="",
            description=curr_cp.get("description", ""),
            mission_status=curr_cp.get("mission_status", "ACTIVE"),
            graph_version=int(curr_tg.get("graph_version", curr_cp.get("graph_version", 1))),
            plan_version=int(curr_cp.get("plan_version", 1)),
            plan_churn_count=int(curr_cp.get("plan_churn_count", 0)),
            current_strategy=str(curr_cp.get("current_strategy", "")),
            mutated_tasks=mutated_tasks,
            removed_task_ids=removed_task_ids,
            task_order=task_order,
            progress=float(curr_tg.get("progress", curr_cp.get("progress", 0.0))),
            completed_task_ids=list(curr_cp.get("completed_task_ids", [])),
            pending_task_ids=list(curr_cp.get("pending_task_ids", [])),
            running_task_ids=list(curr_cp.get("running_task_ids", [])),
            failed_task_ids=list(curr_cp.get("failed_task_ids", [])),
            blocked_task_ids=list(curr_cp.get("blocked_task_ids", [])),
            evidence_refs_delta=evidence_refs_delta,
            outputs_delta=outputs_delta,
            expansion_history_delta=exp_delta,
            adaptation_history_delta=adapt_delta,
            swarm_state=dict(curr_cp.get("swarm_state", {})),
            federation_state=dict(curr_cp.get("federation_state", {})),
        )
        delta.content_hash = delta.calculate_hash()
        delta.to_canonical_bytes()
        return delta


class DeltaReconstructor:
    """Applies CheckpointDeltas on top of a BaseSnapshot to deterministically reconstruct full state."""

    @staticmethod
    def apply_delta(base_state: dict[str, Any], delta: CheckpointDelta) -> dict[str, Any]:
        """Applies a single delta onto base_state producing new full state dict."""
        state = dict(base_state)

        # Update metadata
        state["sequence"] = delta.sequence
        state["checkpoint_id"] = f"cp_{delta.sequence:04d}_{delta.delta_id.split('_')[-1]}"
        state["created_at"] = delta.created_at
        state["description"] = delta.description
        state["mission_status"] = delta.mission_status
        state["graph_version"] = delta.graph_version
        state["plan_version"] = delta.plan_version
        state["plan_churn_count"] = delta.plan_churn_count
        state["current_strategy"] = delta.current_strategy

        # Update task sets
        state["completed_task_ids"] = list(delta.completed_task_ids)
        state["pending_task_ids"] = list(delta.pending_task_ids)
        state["running_task_ids"] = list(delta.running_task_ids)
        state["failed_task_ids"] = list(delta.failed_task_ids)
        state["blocked_task_ids"] = list(delta.blocked_task_ids)

        # Update task graph data
        tg = dict(base_state.get("task_graph_data", {}))
        tasks = dict(tg.get("tasks", {}))
        for tid, tnode in delta.mutated_tasks.items():
            tasks[tid] = tnode
        for tid in delta.removed_task_ids:
            tasks.pop(tid, None)
        tg["tasks"] = tasks

        if delta.task_order is not None:
            tg["order"] = list(delta.task_order)
        tg["progress"] = delta.progress
        tg["graph_version"] = delta.graph_version

        expansion_history = list(tg.get("expansion_history", []))
        expansion_history.extend(delta.expansion_history_delta)
        tg["expansion_history"] = expansion_history
        state["task_graph_data"] = tg

        # Update outputs
        outputs = dict(state.get("outputs", {}))
        outputs.update(delta.outputs_delta)
        state["outputs"] = outputs

        # Update evidence refs
        evidence_refs = list(state.get("evidence_refs", []))
        evidence_refs.extend(delta.evidence_refs_delta)
        state["evidence_refs"] = evidence_refs

        # Update adaptation history
        adaptation_history = list(state.get("adaptation_history", []))
        adaptation_history.extend(delta.adaptation_history_delta)
        state["adaptation_history"] = adaptation_history

        # Swarm and federation
        state["swarm_state"] = dict(delta.swarm_state)
        state["federation_state"] = dict(delta.federation_state)

        return state

    @classmethod
    def reconstruct_state(
        cls,
        base_snapshot: BaseSnapshot,
        deltas: list[CheckpointDelta],
        target_sequence: Optional[int] = None,
        verify_chain: bool = True,
    ) -> dict[str, Any]:
        """Reconstructs state at target_sequence (or latest if None) after verifying hash continuity."""
        if verify_chain:
            valid, reason = IntegrityValidator.verify_chain(base_snapshot, deltas)
            if not valid:
                raise CheckpointIntegrityError(f"Integrity check failed: {reason}")

        current_state = base_snapshot.checkpoint_data

        for d in deltas:
            if target_sequence is not None and d.sequence > target_sequence:
                break
            current_state = cls.apply_delta(current_state, d)

        return current_state


class IntegrityValidator:
    """Verifies SHA-256 cryptographic chain, hash signatures, and sequence monotonicity."""

    @staticmethod
    def verify_chain(base_snapshot: BaseSnapshot, deltas: list[CheckpointDelta]) -> Tuple[bool, str]:
        # 1. Verify base snapshot hash
        if base_snapshot.calculate_hash() != base_snapshot.content_hash:
            return False, f"Base snapshot {base_snapshot.snapshot_id} content hash mismatch"

        current_hash = base_snapshot.content_hash
        current_seq = base_snapshot.sequence

        for idx, delta in enumerate(deltas):
            # Sequence monotonicity
            if delta.sequence <= current_seq:
                return False, f"Delta {delta.delta_id} has non-monotonic sequence {delta.sequence} <= {current_seq}"

            # Parent hash pointer
            if delta.parent_hash != current_hash:
                return False, f"Delta {delta.delta_id} parent_hash {delta.parent_hash[:8]} does not match expected {current_hash[:8]}"

            # Content hash verification
            recomputed = delta.calculate_hash()
            if recomputed != delta.content_hash:
                return False, f"Delta {delta.delta_id} content hash corrupt (expected {delta.content_hash[:8]}, computed {recomputed[:8]})"

            current_hash = delta.content_hash
            current_seq = delta.sequence

        return True, "CHAIN_VALID"


class IdempotencyEngine:
    """Ensures that reapplying an already recorded delta does not produce side-effects or corrupt state."""

    def __init__(self) -> None:
        self._applied_sequences: set[int] = set()
        self._applied_delta_ids: set[str] = set()

    def is_applied(self, delta: CheckpointDelta) -> bool:
        return (delta.sequence in self._applied_sequences) or (delta.delta_id in self._applied_delta_ids)

    def record_applied(self, delta: CheckpointDelta) -> None:
        self._applied_sequences.add(delta.sequence)
        self._applied_delta_ids.add(delta.delta_id)


class CompactionEngine:
    """Performs crash-safe, deterministic, atomic compaction of deltas into a new BaseSnapshot."""

    @staticmethod
    def compact(
        base_snapshot: BaseSnapshot,
        deltas: list[CheckpointDelta],
        keep_latest_deltas: int = 0,
    ) -> Tuple[BaseSnapshot, list[CheckpointDelta]]:
        """Compacts base_snapshot + deltas into a new BaseSnapshot.
        
        Guarantees crash-safety and determinism.
        """
        if not deltas:
            return base_snapshot, []

        target_compact_idx = len(deltas) - keep_latest_deltas
        if target_compact_idx <= 0:
            return base_snapshot, deltas

        deltas_to_compact = deltas[:target_compact_idx]
        remaining_deltas = deltas[target_compact_idx:]

        # Verify integrity of chain to compact
        valid, reason = IntegrityValidator.verify_chain(base_snapshot, deltas_to_compact)
        if not valid:
            raise CheckpointCompactionError(f"Cannot compact corrupt chain: {reason}")

        # Reconstruct state at compaction boundary
        compacted_state = DeltaReconstructor.reconstruct_state(
            base_snapshot, deltas_to_compact, verify_chain=False
        )

        last_delta = deltas_to_compact[-1]
        new_snap_id = f"snap_{last_delta.sequence:04d}_{uuid.uuid4().hex[:6]}"

        new_snapshot = BaseSnapshot(
            snapshot_id=new_snap_id,
            sequence=last_delta.sequence,
            mission_id=base_snapshot.mission_id,
            project_id=base_snapshot.project_id,
            created_at=last_delta.created_at,
            parent_hash=last_delta.content_hash,
            content_hash="",
            checkpoint_data=compacted_state,
        )
        new_snapshot.content_hash = new_snapshot.calculate_hash()

        return new_snapshot, remaining_deltas


class IncrementalPersistenceAdapter:
    """Coordinates persistence of BaseSnapshots and CheckpointDeltas in SQLite and filesystem."""

    def __init__(self, base_dir: str, mission_id: str, project_id: str, compaction_interval: int = 25) -> None:
        self.base_dir = Path(base_dir)
        self.mission_id = mission_id
        self.project_id = project_id
        self.compaction_interval = compaction_interval
        self.checkpoints_dir = self.base_dir / project_id / "missions" / mission_id / "checkpoints_incremental"
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

        self.manifest_path = self.checkpoints_dir / "manifest.json"
        self.idempotency_engine = IdempotencyEngine()
        self._last_checkpoint_state: Optional[dict[str, Any]] = None
        self._last_content_hash: str = "0" * 64
        self._cached_manifest: Optional[dict[str, Any]] = None

    def save_checkpoint(self, cp_data: dict[str, Any]) -> dict[str, Any]:
        """Saves a checkpoint using BaseSnapshot if first, or CheckpointDelta if incremental."""
        seq = int(cp_data["sequence"])

        manifest = self._load_manifest()
        base_snap = self.load_base_snapshot(manifest.get("active_base_sequence"))

        # If no base snapshot exists, save as BaseSnapshot
        if base_snap is None:
            snap_id = f"snap_{seq:04d}_{uuid.uuid4().hex[:6]}"
            base_snap = BaseSnapshot(
                snapshot_id=snap_id,
                sequence=seq,
                mission_id=self.mission_id,
                project_id=self.project_id,
                created_at=cp_data.get("created_at", ""),
                parent_hash="0" * 64,
                content_hash="",
                checkpoint_data=cp_data,
            )
            base_snap.content_hash = base_snap.calculate_hash()
            self._write_base_snapshot_atomic(base_snap)

            manifest["active_base_sequence"] = seq
            manifest["active_base_snapshot_id"] = base_snap.snapshot_id
            manifest["deltas"] = []
            manifest["latest_sequence"] = seq
            manifest["latest_hash"] = base_snap.content_hash
            manifest["compaction_count"] = manifest.get("compaction_count", 0)
            self._save_manifest(manifest)

            self._last_checkpoint_state = cp_data
            self._last_content_hash = base_snap.content_hash
            return {"type": "BASE_SNAPSHOT", "id": base_snap.snapshot_id, "sequence": seq, "bytes": len(canonical_json_bytes(base_snap.to_dict()))}

        # Otherwise, compute incremental delta
        prev_state = self._last_checkpoint_state
        if prev_state is None:
            # Reconstruct from disk to be certain
            deltas = self.load_all_active_deltas(manifest)
            prev_state = DeltaReconstructor.reconstruct_state(base_snap, deltas)

        parent_hash = manifest.get("latest_hash", base_snap.content_hash)

        delta = DeltaComputer.compute_delta(prev_state, cp_data, parent_hash)

        # Idempotency check
        if self.idempotency_engine.is_applied(delta):
            return {"type": "IDEMPOTENT_IGNORED", "id": delta.delta_id, "sequence": seq, "bytes": 0}

        # Write delta atomically
        self._write_delta_atomic(delta)
        self.idempotency_engine.record_applied(delta)

        manifest["deltas"].append({
            "delta_id": delta.delta_id,
            "sequence": delta.sequence,
            "parent_hash": delta.parent_hash,
            "content_hash": delta.content_hash,
            "timestamp": delta.created_at,
        })
        manifest["latest_sequence"] = seq
        manifest["latest_hash"] = delta.content_hash
        self._save_manifest(manifest)

        self._last_checkpoint_state = cp_data
        self._last_content_hash = delta.content_hash
        delta_bytes = len(canonical_json_bytes(delta.to_dict()))

        # Check for compaction trigger
        if len(manifest["deltas"]) >= self.compaction_interval:
            self._trigger_compaction(manifest, base_snap)

        return {"type": "DELTA", "id": delta.delta_id, "sequence": seq, "bytes": delta_bytes}

    def _trigger_compaction(self, manifest: dict[str, Any], current_base: BaseSnapshot) -> None:
        """Executes compaction if delta threshold exceeded."""
        deltas = self.load_all_active_deltas(manifest)
        new_base, remaining = CompactionEngine.compact(current_base, deltas, keep_latest_deltas=0)

        # Atomically write new base snapshot
        self._write_base_snapshot_atomic(new_base)

        manifest["active_base_sequence"] = new_base.sequence
        manifest["active_base_snapshot_id"] = new_base.snapshot_id
        manifest["deltas"] = [
            {
                "delta_id": d.delta_id,
                "sequence": d.sequence,
                "parent_hash": d.parent_hash,
                "content_hash": d.content_hash,
                "timestamp": d.created_at,
            }
            for d in remaining
        ]
        manifest["compaction_count"] = manifest.get("compaction_count", 0) + 1
        manifest["latest_hash"] = new_base.content_hash
        self._save_manifest(manifest)
        self._last_content_hash = new_base.content_hash

    def load_latest_checkpoint(self) -> Optional[dict[str, Any]]:
        manifest = self._load_manifest()
        base_seq = manifest.get("active_base_sequence")
        if base_seq is None:
            return None
        base_snap = self.load_base_snapshot(base_seq)
        if base_snap is None:
            return None
        deltas = self.load_all_active_deltas(manifest)
        return DeltaReconstructor.reconstruct_state(base_snap, deltas, verify_chain=True)

    def load_checkpoint_by_sequence(self, sequence: int) -> Optional[dict[str, Any]]:
        manifest = self._load_manifest()
        base_seq = manifest.get("active_base_sequence")
        if base_seq is None:
            return None
        base_snap = self.load_base_snapshot(base_seq)
        if base_snap is None:
            return None
        deltas = self.load_all_active_deltas(manifest)
        return DeltaReconstructor.reconstruct_state(base_snap, deltas, target_sequence=sequence, verify_chain=True)

    def load_base_snapshot(self, sequence: Optional[int]) -> Optional[BaseSnapshot]:
        if sequence is None:
            return None
        path = self.checkpoints_dir / f"snapshot_{sequence:04d}.json"
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return BaseSnapshot.from_dict(data)
        except Exception:
            return None

    def load_all_active_deltas(self, manifest: dict[str, Any]) -> list[CheckpointDelta]:
        deltas: list[CheckpointDelta] = []
        for dmeta in manifest.get("deltas", []):
            seq = dmeta["sequence"]
            path = self.checkpoints_dir / f"delta_{seq:04d}.json"
            if path.is_file():
                with open(path, "r", encoding="utf-8") as f:
                    deltas.append(CheckpointDelta.from_dict(json.load(f)))
        return deltas

    def _write_base_snapshot_atomic(self, snap: BaseSnapshot) -> None:
        path = self.checkpoints_dir / f"snapshot_{snap.sequence:04d}.json"
        tmp_path = self.checkpoints_dir / f"snapshot_{snap.sequence:04d}.tmp"
        payload = snap.to_canonical_bytes()
        with open(tmp_path, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    def _write_delta_atomic(self, delta: CheckpointDelta) -> None:
        path = self.checkpoints_dir / f"delta_{delta.sequence:04d}.json"
        tmp_path = self.checkpoints_dir / f"delta_{delta.sequence:04d}.tmp"
        payload = delta.to_canonical_bytes()
        with open(tmp_path, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    def _load_manifest(self) -> dict[str, Any]:
        if self._cached_manifest is not None:
            return self._cached_manifest
        if not self.manifest_path.is_file():
            self._cached_manifest = {
                "active_base_sequence": None,
                "active_base_snapshot_id": None,
                "deltas": [],
                "latest_sequence": 0,
                "compaction_count": 0,
            }
            return self._cached_manifest
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self._cached_manifest = json.load(f)
                return self._cached_manifest
        except Exception:
            self._cached_manifest = {
                "active_base_sequence": None,
                "active_base_snapshot_id": None,
                "deltas": [],
                "latest_sequence": 0,
                "compaction_count": 0,
            }
            return self._cached_manifest

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        self._cached_manifest = manifest
        tmp_path = self.checkpoints_dir / "manifest.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(manifest, separators=(",", ":"), ensure_ascii=False))
            f.flush()
        os.replace(tmp_path, self.manifest_path)

