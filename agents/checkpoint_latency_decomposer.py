"""Diagnostic Latency Decomposer for JARVIS OS Checkpointing.

Phase 33.1 — Incremental Checkpoint Latency Decomposition & Overhead Elimination.

Instruments and measures all 14 sub-components of incremental persistence:
1. mutation_detection
2. changed_node_discovery
3. delta_construction
4. delta_serialization
5. json_struct_encoding
6. sha256_content_hash
7. merkle_parent_calculation
8. delta_file_creation
9. disk_write
10. fsync
11. manifest_update
12. atomic_replace
13. validation
14. checkpoint_bookkeeping

Also decomposes Full Checkpoint persistence across its corresponding sub-components.
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
from typing import Any, Dict, List, Optional, Tuple

from agents.incremental_checkpoint_engine import (
    BaseSnapshot,
    CheckpointDelta,
    DeltaComputer,
    DeltaReconstructor,
    IdempotencyEngine,
    IntegrityValidator,
    canonical_json_bytes,
    sha256_digest,
)
from agents.mission_orchestrator import Checkpoint, utc_now
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@dataclass
class IncrementalSubComponentTiming:
    mutation_detection_ms: float = 0.0
    changed_node_discovery_ms: float = 0.0
    delta_construction_ms: float = 0.0
    delta_serialization_ms: float = 0.0
    json_struct_encoding_ms: float = 0.0
    sha256_content_hash_ms: float = 0.0
    merkle_parent_calculation_ms: float = 0.0
    delta_file_creation_ms: float = 0.0
    disk_write_ms: float = 0.0
    fsync_ms: float = 0.0
    manifest_update_ms: float = 0.0
    atomic_replace_ms: float = 0.0
    validation_ms: float = 0.0
    checkpoint_bookkeeping_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        return sum([
            self.mutation_detection_ms,
            self.changed_node_discovery_ms,
            self.delta_construction_ms,
            self.delta_serialization_ms,
            self.json_struct_encoding_ms,
            self.sha256_content_hash_ms,
            self.merkle_parent_calculation_ms,
            self.delta_file_creation_ms,
            self.disk_write_ms,
            self.fsync_ms,
            self.manifest_update_ms,
            self.atomic_replace_ms,
            self.validation_ms,
            self.checkpoint_bookkeeping_ms,
        ])

    def to_dict(self) -> dict[str, float]:
        d = asdict(self)
        d["total_ms"] = round(self.total_ms, 4)
        for k in d:
            d[k] = round(d[k], 4)
        return d


@dataclass
class FullSubComponentTiming:
    state_construction_ms: float = 0.0
    serialization_ms: float = 0.0
    json_encoding_ms: float = 0.0
    hash_calculation_ms: float = 0.0
    file_creation_ms: float = 0.0
    disk_write_ms: float = 0.0
    fsync_ms: float = 0.0
    manifest_bookkeeping_ms: float = 0.0
    validation_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        return sum([
            self.state_construction_ms,
            self.serialization_ms,
            self.json_encoding_ms,
            self.hash_calculation_ms,
            self.file_creation_ms,
            self.disk_write_ms,
            self.fsync_ms,
            self.manifest_bookkeeping_ms,
            self.validation_ms,
        ])

    def to_dict(self) -> dict[str, float]:
        d = asdict(self)
        d["total_ms"] = round(self.total_ms, 4)
        for k in d:
            d[k] = round(d[k], 4)
        return d


class CheckpointLatencyDecomposer:
    """Isolates and profiles each of the 14 sub-components individually."""

    @staticmethod
    def profile_incremental_save(
        prev_cp: dict[str, Any],
        curr_cp: dict[str, Any],
        target_dir: str,
        parent_hash: str,
        enable_fsync: bool = True,
        manifest_data: Optional[dict[str, Any]] = None,
        idempotency_engine: Optional[IdempotencyEngine] = None,
    ) -> Tuple[IncrementalSubComponentTiming, CheckpointDelta, int]:
        timing = IncrementalSubComponentTiming()
        idem = idempotency_engine or IdempotencyEngine()
        man = manifest_data if manifest_data is not None else {
            "active_base_sequence": 0,
            "deltas": [],
            "latest_sequence": 0,
            "latest_hash": parent_hash,
            "compaction_count": 0,
        }

        os.makedirs(target_dir, exist_ok=True)
        manifest_path = os.path.join(target_dir, "manifest.json")
        if not os.path.isfile(manifest_path):
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(man, f)

        # 1. mutation_detection
        t0 = time.perf_counter_ns()
        prev_tg = prev_cp.get("task_graph_data", {})
        curr_tg = curr_cp.get("task_graph_data", {})
        prev_tasks = prev_tg.get("tasks", {})
        curr_tasks = curr_tg.get("tasks", {})
        has_mutations = (
            len(curr_tasks) != len(prev_tasks)
            or curr_cp.get("mission_status") != prev_cp.get("mission_status")
            or curr_cp.get("sequence") != prev_cp.get("sequence")
        )
        t1 = time.perf_counter_ns()
        timing.mutation_detection_ms = (t1 - t0) / 1_000_000.0

        # 2. changed_node_discovery
        t0 = time.perf_counter_ns()
        mutated_tasks: dict[str, dict[str, Any]] = {}
        for tid, tnode in curr_tasks.items():
            if tid not in prev_tasks:
                mutated_tasks[tid] = tnode
            else:
                prev_node = prev_tasks[tid]
                if tnode != prev_node:
                    mutated_tasks[tid] = tnode
        removed_task_ids = [tid for tid in prev_tasks if tid not in curr_tasks]
        t1 = time.perf_counter_ns()
        timing.changed_node_discovery_ms = (t1 - t0) / 1_000_000.0

        # 3. delta_construction
        t0 = time.perf_counter_ns()
        prev_ev = set(prev_cp.get("evidence_refs", []))
        curr_ev = curr_cp.get("evidence_refs", [])
        evidence_refs_delta = [e for e in curr_ev if e not in prev_ev]

        prev_out = prev_cp.get("outputs", {})
        curr_out = curr_cp.get("outputs", {})
        outputs_delta = {k: v for k, v in curr_out.items() if k not in prev_out or prev_out[k] != v}

        prev_exp = prev_tg.get("expansion_history", [])
        curr_exp = curr_tg.get("expansion_history", [])
        exp_delta = list(curr_exp[len(prev_exp):])

        prev_adapt = prev_cp.get("adaptation_history", [])
        curr_adapt = curr_cp.get("adaptation_history", [])
        adapt_delta = list(curr_adapt[len(prev_adapt):])

        seq = int(curr_cp["sequence"])
        delta_id = f"delta_{seq:04d}_{uuid.uuid4().hex[:6]}"

        prev_order = prev_tg.get("order")
        curr_order = curr_tg.get("order")
        task_order = list(curr_order) if curr_order != prev_order else None

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
        t1 = time.perf_counter_ns()
        timing.delta_construction_ms = (t1 - t0) / 1_000_000.0

        # 4. delta_serialization
        t0 = time.perf_counter_ns()
        delta_dict = delta.to_dict()
        t1 = time.perf_counter_ns()
        timing.delta_serialization_ms = (t1 - t0) / 1_000_000.0

        # 5. json_struct_encoding
        t0 = time.perf_counter_ns()
        encoded_bytes = json.dumps(delta_dict, indent=2, ensure_ascii=False).encode("utf-8")
        t1 = time.perf_counter_ns()
        timing.json_struct_encoding_ms = (t1 - t0) / 1_000_000.0

        # 6. sha256_content_hash
        t0 = time.perf_counter_ns()
        delta.content_hash = delta.calculate_hash()
        delta_dict["content_hash"] = delta.content_hash
        # re-encode with content hash
        final_bytes = json.dumps(delta_dict, indent=2, ensure_ascii=False).encode("utf-8")
        t1 = time.perf_counter_ns()
        timing.sha256_content_hash_ms = (t1 - t0) / 1_000_000.0

        # 7. merkle_parent_calculation
        t0 = time.perf_counter_ns()
        expected_parent = man.get("latest_hash", parent_hash)
        assert delta.parent_hash == expected_parent
        t1 = time.perf_counter_ns()
        timing.merkle_parent_calculation_ms = (t1 - t0) / 1_000_000.0

        # 8. delta_file_creation
        tmp_delta_path = os.path.join(target_dir, f"delta_{seq:04d}.tmp")
        final_delta_path = os.path.join(target_dir, f"delta_{seq:04d}.json")
        t0 = time.perf_counter_ns()
        f = open(tmp_delta_path, "wb")
        t1 = time.perf_counter_ns()
        timing.delta_file_creation_ms = (t1 - t0) / 1_000_000.0

        # 9. disk_write
        t0 = time.perf_counter_ns()
        f.write(final_bytes)
        f.flush()
        t1 = time.perf_counter_ns()
        timing.disk_write_ms = (t1 - t0) / 1_000_000.0

        # 10. fsync
        t0 = time.perf_counter_ns()
        if enable_fsync:
            os.fsync(f.fileno())
        f.close()
        t1 = time.perf_counter_ns()
        timing.fsync_ms = (t1 - t0) / 1_000_000.0

        # 11. manifest_update
        t0 = time.perf_counter_ns()
        man["deltas"].append({
            "delta_id": delta.delta_id,
            "sequence": delta.sequence,
            "parent_hash": delta.parent_hash,
            "content_hash": delta.content_hash,
            "timestamp": delta.created_at,
        })
        man["latest_sequence"] = seq
        man["latest_hash"] = delta.content_hash
        tmp_man_path = os.path.join(target_dir, "manifest.tmp")
        with open(tmp_man_path, "w", encoding="utf-8") as mf:
            mf.write(json.dumps(man, indent=2, ensure_ascii=False))
            mf.flush()
            if enable_fsync:
                pass  # Optimized in 33 to omit redundant fsync
        t1 = time.perf_counter_ns()
        timing.manifest_update_ms = (t1 - t0) / 1_000_000.0

        # 12. atomic_replace
        t0 = time.perf_counter_ns()
        os.replace(tmp_delta_path, final_delta_path)
        os.replace(tmp_man_path, manifest_path)
        t1 = time.perf_counter_ns()
        timing.atomic_replace_ms = (t1 - t0) / 1_000_000.0

        # 13. validation
        t0 = time.perf_counter_ns()
        is_dup = idem.is_applied(delta)
        idem.record_applied(delta)
        assert not is_dup
        t1 = time.perf_counter_ns()
        timing.validation_ms = (t1 - t0) / 1_000_000.0

        # 14. checkpoint_bookkeeping
        t0 = time.perf_counter_ns()
        needs_compaction = len(man["deltas"]) >= 25
        t1 = time.perf_counter_ns()
        timing.checkpoint_bookkeeping_ms = (t1 - t0) / 1_000_000.0

        return timing, delta, len(final_bytes)

    @staticmethod
    def profile_full_save(
        cp_data: dict[str, Any],
        target_dir: str,
        enable_fsync: bool = True,
    ) -> Tuple[FullSubComponentTiming, int]:
        timing = FullSubComponentTiming()
        os.makedirs(target_dir, exist_ok=True)
        seq = int(cp_data["sequence"])
        final_path = os.path.join(target_dir, f"checkpoint_{seq:04d}.json")
        tmp_path = os.path.join(target_dir, f"checkpoint_{seq:04d}.tmp")

        # 1. state_construction
        t0 = time.perf_counter_ns()
        _ = cp_data.get("task_graph_data", {})
        t1 = time.perf_counter_ns()
        timing.state_construction_ms = (t1 - t0) / 1_000_000.0

        # 2. serialization
        t0 = time.perf_counter_ns()
        # Full serialization of tasks
        tasks = cp_data.get("task_graph_data", {}).get("tasks", {})
        serialized_tasks = {k: dict(v) for k, v in tasks.items()}
        t1 = time.perf_counter_ns()
        timing.serialization_ms = (t1 - t0) / 1_000_000.0

        # 3. json_encoding
        t0 = time.perf_counter_ns()
        payload_bytes = json.dumps(cp_data, indent=2, ensure_ascii=False).encode("utf-8")
        t1 = time.perf_counter_ns()
        timing.json_encoding_ms = (t1 - t0) / 1_000_000.0

        # 4. hash_calculation
        t0 = time.perf_counter_ns()
        h = hashlib.sha256(payload_bytes).hexdigest()
        t1 = time.perf_counter_ns()
        timing.hash_calculation_ms = (t1 - t0) / 1_000_000.0

        # 5. file_creation
        t0 = time.perf_counter_ns()
        f = open(tmp_path, "wb")
        t1 = time.perf_counter_ns()
        timing.file_creation_ms = (t1 - t0) / 1_000_000.0

        # 6. disk_write
        t0 = time.perf_counter_ns()
        f.write(payload_bytes)
        f.flush()
        t1 = time.perf_counter_ns()
        timing.disk_write_ms = (t1 - t0) / 1_000_000.0

        # 7. fsync
        t0 = time.perf_counter_ns()
        if enable_fsync:
            os.fsync(f.fileno())
        f.close()
        t1 = time.perf_counter_ns()
        timing.fsync_ms = (t1 - t0) / 1_000_000.0

        # 8. manifest_bookkeeping
        t0 = time.perf_counter_ns()
        os.replace(tmp_path, final_path)
        t1 = time.perf_counter_ns()
        timing.manifest_bookkeeping_ms = (t1 - t0) / 1_000_000.0

        # 9. validation
        t0 = time.perf_counter_ns()
        assert os.path.isfile(final_path)
        t1 = time.perf_counter_ns()
        timing.validation_ms = (t1 - t0) / 1_000_000.0

        return timing, len(payload_bytes)
