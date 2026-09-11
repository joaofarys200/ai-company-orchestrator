"""Phase 33.1 — Incremental Checkpoint Latency Decomposition & Overhead Profiler

Executes:
1. Workload A: Accumulated multi-node state (jumping horizons: 20, 50, 100, 150, 200, 250, 300, 500, 750, 1000).
2. Workload B: One mutated node per transition (consecutive cadence: 20, 50, 100, 150, 200, 250, 300, 500, 750, 1000).
3. 14 Sub-component profiling for incremental save and corresponding profiling for full save.
4. 7 Controlled Isolation Studies:
   - Delta size vs latency (1, 2, 5, 10, 25, 50, 100 mutated nodes) -> fixed vs variable cost.
   - Hash overhead (1 KB, 10 KB, 100 KB, 1 MB).
   - Manifest overhead (read, modify, serialize, atomic replace across history size).
   - Fsync isolation (sync enabled vs sync disabled) -> FSYNC_CONTRIBUTION.
   - File creation / inode overhead (open, create, write, close, rename).
   - Compaction amortized cost.
   - Storage backend matrix (Hybrid vs SQLite vs ShardedFilesystem).
5. Identification of FIRST_INCREMENTAL_HOT_PATH.
6. Emits:
   - docs/phase33_1_latency_profile.json
   - docs/phase33_1_component_benchmark.json
   - docs/phase33_1_workload_comparison.json

Discipline: START -> RUN -> WAIT -> COLLECT -> EXIT -> RECORD -> FINISHED.
SIMULATED = 0. All metrics measured from physical disk I/O and CPU timings.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import psutil
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.checkpoint_latency_decomposer import (
    CheckpointLatencyDecomposer,
    FullSubComponentTiming,
    IncrementalSubComponentTiming,
)
from agents.incremental_checkpoint_engine import (
    BaseSnapshot,
    CheckpointDelta,
    CompactionEngine,
    DeltaComputer,
    DeltaReconstructor,
    IdempotencyEngine,
    IncrementalPersistenceAdapter,
    IntegrityValidator,
    canonical_json_bytes,
    sha256_digest,
)
from agents.mission_orchestrator import Checkpoint, utc_now
from agents.mission_persistence import (
    HybridMissionPersistence,
    SQLiteMissionPersistence,
    ShardedFilesystemPersistence,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def calc_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "p50": 0.0, "p95": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    sorted_v = sorted(values)
    p50_idx = int(len(sorted_v) * 0.50)
    p95_idx = int(len(sorted_v) * 0.95)
    p50_val = sorted_v[min(p50_idx, len(sorted_v) - 1)]
    p95_val = sorted_v[min(p95_idx, len(sorted_v) - 1)]
    return {
        "mean": round(statistics.mean(values), 4),
        "median": round(statistics.median(values), 4),
        "p50": round(p50_val, 4),
        "p95": round(p95_val, 4),
        "std": round(statistics.stdev(values) if len(values) > 1 else 0.0, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def generate_mission_checkpoint(seq: int, total_tasks: int, project_id: str, mission_id: str) -> dict[str, Any]:
    tg = TaskGraph()
    for i in range(total_tasks):
        if i < seq:
            st = TaskStatus.COMPLETED
        elif i == seq:
            st = TaskStatus.RUNNING
        else:
            st = TaskStatus.PENDING
        node = TaskNode(
            task_id=f"wp_{i:04d}",
            title=f"Work Package {i} Implementation",
            status=st,
            attempt_count=1 if i <= seq else 0,
            dependencies=[f"wp_{i-1:04d}"] if i > 0 else [],
        )
        tg.add_node(node)

    cp = Checkpoint(
        checkpoint_id=f"cp_{seq:04d}",
        sequence=seq,
        mission_id=mission_id,
        project_id=project_id,
        mission_status="RUNNING" if seq < total_tasks else "COMPLETED",
        task_graph_data=tg.to_dict(),
        completed_task_ids=[f"wp_{i:04d}" for i in range(seq)],
        pending_task_ids=[f"wp_{i:04d}" for i in range(seq + 1, total_tasks)],
        running_task_ids=[f"wp_{seq:04d}"] if seq < total_tasks else [],
        failed_task_ids=[],
        blocked_task_ids=[],
        evidence_refs=[f"ev_{i:04d}" for i in range(seq)],
        outputs={f"wp_{i:04d}": {"exit_code": 0, "hash": f"h_{i:04d}"} for i in range(seq)},
        created_at=utc_now(),
        description=f"Transition step {seq}/{total_tasks}",
        graph_version=1,
        plan_version=1,
        current_strategy="CHAINED_INCREMENTAL",
        plan_churn_count=0,
    )
    return cp.to_dict()


def profile_workload(
    workload_type: str,
    horizons: list[int],
    num_runs: int,
    scratch_dir: str,
) -> dict[str, Any]:
    """Profiles Full vs Incremental checkpoint latency decomposition across given horizons."""
    print(f"\n=======================================================")
    print(f"PROFILING {workload_type} (Horizons: {horizons}, Runs: {num_runs})")
    print(f"=======================================================")

    results_by_horizon: dict[str, Any] = {}

    for horizon in horizons:
        print(f"\n--- Horizon: {horizon} tasks ({workload_type}) ---")
        full_timings_all: list[FullSubComponentTiming] = []
        incr_timings_all: list[IncrementalSubComponentTiming] = []
        full_bytes_all: list[int] = []
        incr_bytes_all: list[int] = []

        # Determine transition steps based on workload
        if workload_type == "WORKLOAD_A_ACCUMULATED":
            # Jumped multi-node accumulation (e.g. 20%, 50%, 80%, 100%)
            step_points = sorted(list({max(1, int(horizon * p)) for p in [0.2, 0.5, 0.8, 1.0]}))
        else:
            # WORKLOAD_B_SINGLE_MUTATION: 10 consecutive single-node mutation steps around the tail
            start_step = max(1, horizon - 10)
            step_points = list(range(start_step, horizon + 1))

        for run_idx in range(num_runs):
            h_dir = os.path.join(scratch_dir, f"{workload_type}_{horizon}_run_{run_idx}")
            os.makedirs(h_dir, exist_ok=True)
            full_dir = os.path.join(h_dir, "full")
            incr_dir = os.path.join(h_dir, "incr")
            os.makedirs(full_dir, exist_ok=True)
            os.makedirs(incr_dir, exist_ok=True)

            # 1. Base snapshot setup for incremental
            base_cp = generate_mission_checkpoint(0, horizon, "prof_proj", f"prof_m_{horizon}")
            base_snap = BaseSnapshot(
                snapshot_id=f"snap_0000_{uuid.uuid4().hex[:6]}",
                sequence=0,
                mission_id=f"prof_m_{horizon}",
                project_id="prof_proj",
                created_at=base_cp["created_at"],
                parent_hash="0" * 64,
                content_hash="",
                checkpoint_data=base_cp,
            )
            base_snap.content_hash = base_snap.calculate_hash()
            snap_path = os.path.join(incr_dir, "snapshot_0000.json")
            with open(snap_path, "w", encoding="utf-8") as f:
                json.dump(base_snap.to_dict(), f, indent=2)

            manifest_data: dict[str, Any] = {
                "active_base_sequence": 0,
                "active_base_snapshot_id": base_snap.snapshot_id,
                "deltas": [],
                "latest_sequence": 0,
                "latest_hash": base_snap.content_hash,
                "compaction_count": 0,
            }
            with open(os.path.join(incr_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)

            idem = IdempotencyEngine()
            prev_cp = base_cp
            current_parent_hash = base_snap.content_hash

            # Run transitions
            for seq in step_points:
                curr_cp = generate_mission_checkpoint(seq, horizon, "prof_proj", f"prof_m_{horizon}")

                # Profile Full save
                f_timing, f_bytes = CheckpointLatencyDecomposer.profile_full_save(
                    curr_cp, full_dir, enable_fsync=True
                )
                full_timings_all.append(f_timing)
                full_bytes_all.append(f_bytes)

                # Profile Incremental save
                i_timing, delta, i_bytes = CheckpointLatencyDecomposer.profile_incremental_save(
                    prev_cp=prev_cp,
                    curr_cp=curr_cp,
                    target_dir=incr_dir,
                    parent_hash=current_parent_hash,
                    enable_fsync=True,
                    manifest_data=manifest_data,
                    idempotency_engine=idem,
                )
                incr_timings_all.append(i_timing)
                incr_bytes_all.append(i_bytes)
                current_parent_hash = delta.content_hash
                prev_cp = curr_cp

        # Aggregate statistics
        full_totals = [t.total_ms for t in full_timings_all]
        incr_totals = [t.total_ms for t in incr_timings_all]

        sub_incr: dict[str, Any] = {}
        for field_name in [
            "mutation_detection_ms", "changed_node_discovery_ms", "delta_construction_ms",
            "delta_serialization_ms", "json_struct_encoding_ms", "sha256_content_hash_ms",
            "merkle_parent_calculation_ms", "delta_file_creation_ms", "disk_write_ms",
            "fsync_ms", "manifest_update_ms", "atomic_replace_ms", "validation_ms",
            "checkpoint_bookkeeping_ms"
        ]:
            vals = [getattr(t, field_name) for t in incr_timings_all]
            sub_incr[field_name.replace("_ms", "")] = calc_stats(vals)

        sub_full: dict[str, Any] = {}
        for field_name in [
            "state_construction_ms", "serialization_ms", "json_encoding_ms",
            "hash_calculation_ms", "file_creation_ms", "disk_write_ms",
            "fsync_ms", "manifest_bookkeeping_ms", "validation_ms"
        ]:
            vals = [getattr(t, field_name) for t in full_timings_all]
            sub_full[field_name.replace("_ms", "")] = calc_stats(vals)

        mean_full = statistics.mean(full_totals)
        mean_incr = statistics.mean(incr_totals)
        mean_f_bytes = statistics.mean(full_bytes_all)
        mean_i_bytes = statistics.mean(incr_bytes_all)
        byte_reduction = (1.0 - (mean_i_bytes / max(1.0, mean_f_bytes))) * 100.0

        print(f"  Full Total: {mean_full:.3f} ms | Incremental Total: {mean_incr:.3f} ms")
        print(f"  Bytes Written: Full={mean_f_bytes:,.0f} B vs Incr={mean_i_bytes:,.0f} B ({byte_reduction:.1f}% reduction)")

        results_by_horizon[str(horizon)] = {
            "horizon": horizon,
            "samples_count": len(full_timings_all),
            "full_total_ms": calc_stats(full_totals),
            "incremental_total_ms": calc_stats(incr_totals),
            "full_bytes": calc_stats([float(b) for b in full_bytes_all]),
            "incremental_bytes": calc_stats([float(b) for b in incr_bytes_all]),
            "byte_reduction_percentage": round(byte_reduction, 2),
            "incremental_subcomponents": sub_incr,
            "full_subcomponents": sub_full,
        }

    return results_by_horizon


def run_isolation_study_delta_size(scratch_dir: str) -> dict[str, Any]:
    """Study 1: Delta size vs Latency across varying number of mutated nodes."""
    print("\n--- Isolation Study 1: Delta Size vs Latency ---")
    mutated_counts = [1, 2, 5, 10, 25, 50, 100]
    study_dir = os.path.join(scratch_dir, "study_delta_size")
    os.makedirs(study_dir, exist_ok=True)

    results = []
    base_horizon = 200
    base_cp = generate_mission_checkpoint(50, base_horizon, "study_proj", "m_study")

    for mc in mutated_counts:
        # Create modified checkpoint with exactly mc mutated tasks
        mod_cp = copy.deepcopy(base_cp)
        tg_data = mod_cp["task_graph_data"]
        for i in range(mc):
            tid = f"wp_{50 + i:04d}"
            if tid in tg_data["tasks"]:
                tg_data["tasks"][tid]["status"] = "COMPLETED"
                tg_data["tasks"][tid]["attempt_count"] += 1
                mod_cp["completed_task_ids"].append(tid)
                if tid in mod_cp["pending_task_ids"]:
                    mod_cp["pending_task_ids"].remove(tid)
        mod_cp["sequence"] = 50 + mc

        durations = []
        delta_bytes_list = []
        sub_timings = []

        for _ in range(5):
            t_dir = os.path.join(study_dir, f"mc_{mc}_{uuid.uuid4().hex[:4]}")
            timing, delta, d_bytes = CheckpointLatencyDecomposer.profile_incremental_save(
                prev_cp=base_cp,
                curr_cp=mod_cp,
                target_dir=t_dir,
                parent_hash="0" * 64,
                enable_fsync=True,
            )
            durations.append(timing.total_ms)
            delta_bytes_list.append(d_bytes)
            sub_timings.append(timing)

        mean_dur = statistics.mean(durations)
        mean_bytes = statistics.mean(delta_bytes_list)
        print(f"  Mutated Nodes: {mc:3d} -> Delta Bytes: {mean_bytes:6.0f} B | Latency: {mean_dur:.3f} ms")
        results.append({
            "mutated_nodes": mc,
            "mean_bytes": round(mean_bytes, 1),
            "latency_ms": calc_stats(durations),
            "discovery_ms": calc_stats([t.changed_node_discovery_ms for t in sub_timings]),
            "serialization_ms": calc_stats([t.delta_serialization_ms for t in sub_timings]),
            "fsync_ms": calc_stats([t.fsync_ms for t in sub_timings]),
        })

    # Linear regression estimation of fixed vs variable cost: Latency = C_fixed + k * delta_bytes
    x = [r["mean_bytes"] for r in results]
    y = [r["latency_ms"]["mean"] for r in results]
    n = len(x)
    sum_x, sum_y = sum(x), sum(y)
    sum_xx = sum(xi * xi for xi in x)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    slope = (n * sum_xy - sum_x * sum_y) / max(1e-9, (n * sum_xx - sum_x * sum_x))
    intercept = (sum_y - slope * sum_x) / n

    return {
        "data": results,
        "fixed_cost_ms": round(max(0.0, intercept), 4),
        "variable_cost_per_kb_ms": round(slope * 1024.0, 6),
        "correlation_formula": f"latency_ms = {intercept:.4f} + {slope:.6f} * delta_bytes",
    }


def run_isolation_study_hash_overhead() -> dict[str, Any]:
    """Study 2: Hash overhead across varying payload sizes (1 KB, 10 KB, 100 KB, 1 MB)."""
    print("\n--- Isolation Study 2: Hash Overhead ---")
    sizes = [1_024, 10_240, 102_400, 1_048_576]
    results = []

    for sz in sizes:
        raw_payload = os.urandom(sz)
        sha_times = []
        merkle_times = []

        for _ in range(50):
            # SHA-256 content hashing
            t0 = time.perf_counter_ns()
            h1 = hashlib.sha256(raw_payload).hexdigest()
            t1 = time.perf_counter_ns()
            sha_times.append((t1 - t0) / 1_000_000.0)

            # Merkle parent chaining hash: sha256(parent_hash + content_hash)
            t0 = time.perf_counter_ns()
            combined = (h1 + "0" * 64).encode("ascii")
            _ = hashlib.sha256(combined).hexdigest()
            t1 = time.perf_counter_ns()
            merkle_times.append((t1 - t0) / 1_000_000.0)

        sha_stats = calc_stats(sha_times)
        merkle_stats = calc_stats(merkle_times)
        label = f"{sz // 1024} KB" if sz < 1_048_576 else f"{sz // 1_048_576} MB"
        print(f"  Payload: {label:7s} -> SHA-256: {sha_stats['mean']:.4f} ms | Merkle Parent: {merkle_stats['mean']:.4f} ms")
        results.append({
            "size_bytes": sz,
            "label": label,
            "sha256_ms": sha_stats,
            "merkle_parent_ms": merkle_stats,
            "throughput_mb_s": round((sz / (1024 * 1024)) / (max(1e-6, sha_stats['mean'] / 1000.0)), 2),
        })

    return {"data": results}


def run_isolation_study_manifest_overhead(scratch_dir: str) -> dict[str, Any]:
    """Study 3: Manifest overhead (read, modify, serialize, hash, atomic replace) as history grows."""
    print("\n--- Isolation Study 3: Manifest Overhead Scaling ---")
    m_dir = os.path.join(scratch_dir, "study_manifest")
    os.makedirs(m_dir, exist_ok=True)
    manifest_path = os.path.join(m_dir, "manifest.json")
    tmp_path = os.path.join(m_dir, "manifest.tmp")

    history_sizes = [1, 5, 10, 25, 50, 75, 100]
    results = []

    for h_size in history_sizes:
        manifest = {
            "active_base_sequence": 0,
            "active_base_snapshot_id": "snap_0000_abc",
            "deltas": [
                {
                    "delta_id": f"delta_{i:04d}",
                    "sequence": i,
                    "parent_hash": f"parent_h_{i:04d}",
                    "content_hash": f"content_h_{i:04d}",
                    "timestamp": utc_now(),
                }
                for i in range(h_size)
            ],
            "latest_sequence": h_size,
            "latest_hash": f"content_h_{h_size:04d}",
            "compaction_count": 0,
        }

        read_times, mod_times, ser_times, replace_times = [], [], [], []

        for _ in range(10):
            # Save base manifest
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f)

            # 1. Read
            t0 = time.perf_counter_ns()
            with open(manifest_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            t1 = time.perf_counter_ns()
            read_times.append((t1 - t0) / 1_000_000.0)

            # 2. Modify
            t0 = time.perf_counter_ns()
            loaded["deltas"].append({
                "delta_id": f"delta_{h_size + 1:04d}",
                "sequence": h_size + 1,
                "parent_hash": loaded["latest_hash"],
                "content_hash": "hash_new",
                "timestamp": utc_now(),
            })
            loaded["latest_sequence"] = h_size + 1
            t1 = time.perf_counter_ns()
            mod_times.append((t1 - t0) / 1_000_000.0)

            # 3. Serialize & Write
            t0 = time.perf_counter_ns()
            content = json.dumps(loaded, indent=2, ensure_ascii=False)
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
            t1 = time.perf_counter_ns()
            ser_times.append((t1 - t0) / 1_000_000.0)

            # 4. Atomic replace
            t0 = time.perf_counter_ns()
            os.replace(tmp_path, manifest_path)
            t1 = time.perf_counter_ns()
            replace_times.append((t1 - t0) / 1_000_000.0)

        read_stats = calc_stats(read_times)
        mod_stats = calc_stats(mod_times)
        ser_stats = calc_stats(ser_times)
        rep_stats = calc_stats(replace_times)
        total_m_ms = read_stats["mean"] + mod_stats["mean"] + ser_stats["mean"] + rep_stats["mean"]

        print(f"  History Size: {h_size:3d} deltas -> Total: {total_m_ms:.4f} ms (read={read_stats['mean']:.3f}, ser/write={ser_stats['mean']:.3f}, replace={rep_stats['mean']:.3f})")
        results.append({
            "history_size": h_size,
            "manifest_bytes": len(json.dumps(manifest).encode("utf-8")),
            "read_ms": read_stats,
            "modify_ms": mod_stats,
            "serialize_write_ms": ser_stats,
            "atomic_replace_ms": rep_stats,
            "total_ms": round(total_m_ms, 4),
        })

    return {"data": results}


def run_isolation_study_fsync(scratch_dir: str) -> dict[str, Any]:
    """Study 4: Controlled Fsync Isolation (Sync Enabled vs Sync Disabled).

    Measures FSYNC_CONTRIBUTION without altering production durability invariants.
    """
    print("\n--- Isolation Study 4: Fsync Isolation ---")
    horizons = [50, 100, 250, 500, 1000]
    results = []

    for h in horizons:
        sync_dir = os.path.join(scratch_dir, f"fsync_study_{h}")
        os.makedirs(sync_dir, exist_ok=True)
        prev_cp = generate_mission_checkpoint(max(1, h - 1), h, "fsync_proj", f"m_{h}")
        curr_cp = generate_mission_checkpoint(h, h, "fsync_proj", f"m_{h}")

        with_fsync_times = []
        without_fsync_times = []

        # Enabled fsync
        for _ in range(5):
            t_dir = os.path.join(sync_dir, f"with_sync_{uuid.uuid4().hex[:4]}")
            timing, _, _ = CheckpointLatencyDecomposer.profile_incremental_save(
                prev_cp=prev_cp, curr_cp=curr_cp, target_dir=t_dir, parent_hash="0" * 64, enable_fsync=True
            )
            with_fsync_times.append(timing.total_ms)

        # Disabled fsync (Controlled profiling only)
        for _ in range(5):
            t_dir = os.path.join(sync_dir, f"no_sync_{uuid.uuid4().hex[:4]}")
            timing, _, _ = CheckpointLatencyDecomposer.profile_incremental_save(
                prev_cp=prev_cp, curr_cp=curr_cp, target_dir=t_dir, parent_hash="0" * 64, enable_fsync=False
            )
            without_fsync_times.append(timing.total_ms)

        with_mean = statistics.mean(with_fsync_times)
        without_mean = statistics.mean(without_fsync_times)
        fsync_cost = max(0.0, with_mean - without_mean)
        fsync_contrib_pct = (fsync_cost / max(1e-6, with_mean)) * 100.0

        print(f"  Horizon {h:4d} -> With Fsync: {with_mean:.3f} ms | Without Fsync: {without_mean:.3f} ms | Fsync Cost: {fsync_cost:.3f} ms ({fsync_contrib_pct:.1f}%)")
        results.append({
            "horizon": h,
            "with_fsync_ms": calc_stats(with_fsync_times),
            "without_fsync_ms": calc_stats(without_fsync_times),
            "fsync_cost_ms": round(fsync_cost, 4),
            "fsync_contribution_percentage": round(fsync_contrib_pct, 2),
        })

    avg_contrib = statistics.mean([r["fsync_contribution_percentage"] for r in results])
    return {
        "data": results,
        "FSYNC_CONTRIBUTION_AVG_PERCENT": round(avg_contrib, 2),
    }


def run_isolation_study_file_creation(scratch_dir: str) -> dict[str, Any]:
    """Study 5: File creation and NTFS metadata overhead (open, create, write, close, rename)."""
    print("\n--- Isolation Study 5: File Creation & Inode/NTFS Metadata Overhead ---")
    fc_dir = os.path.join(scratch_dir, "study_file_creation")
    os.makedirs(fc_dir, exist_ok=True)

    payload_small = b"{\"delta\": 1, \"content\": \"small_incremental_delta\"}"
    payload_large = b"{\"checkpoint\": 1, \"content\": \"" + (b"x" * 250_000) + b"\"}"

    # Profile single large file vs 25 small delta files
    def profile_file_ops(payload: bytes, count: int) -> dict[str, Any]:
        open_create_times, write_times, close_times, rename_times = [], [], [], []
        for i in range(count):
            tmp_p = os.path.join(fc_dir, f"test_{i:04d}_{uuid.uuid4().hex[:4]}.tmp")
            final_p = os.path.join(fc_dir, f"test_{i:04d}_{uuid.uuid4().hex[:4]}.dat")

            # 1. Open/create
            t0 = time.perf_counter_ns()
            f = open(tmp_p, "wb")
            t1 = time.perf_counter_ns()
            open_create_times.append((t1 - t0) / 1_000_000.0)

            # 2. Write
            t0 = time.perf_counter_ns()
            f.write(payload)
            f.flush()
            t1 = time.perf_counter_ns()
            write_times.append((t1 - t0) / 1_000_000.0)

            # 3. Close
            t0 = time.perf_counter_ns()
            f.close()
            t1 = time.perf_counter_ns()
            close_times.append((t1 - t0) / 1_000_000.0)

            # 4. Rename
            t0 = time.perf_counter_ns()
            os.replace(tmp_p, final_p)
            t1 = time.perf_counter_ns()
            rename_times.append((t1 - t0) / 1_000_000.0)

        return {
            "open_create_ms": calc_stats(open_create_times),
            "write_ms": calc_stats(write_times),
            "close_ms": calc_stats(close_times),
            "rename_ms": calc_stats(rename_times),
            "total_per_file_ms": round(
                statistics.mean(open_create_times) + statistics.mean(write_times) +
                statistics.mean(close_times) + statistics.mean(rename_times), 4
            ),
        }

    stats_one_full = profile_file_ops(payload_large, 10)
    stats_many_deltas = profile_file_ops(payload_small, 25)

    print(f"  Full File (250KB): Open={stats_one_full['open_create_ms']['mean']:.3f} ms, Rename={stats_one_full['rename_ms']['mean']:.3f} ms, Total={stats_one_full['total_per_file_ms']:.3f} ms")
    print(f"  Delta File (1KB):  Open={stats_many_deltas['open_create_ms']['mean']:.3f} ms, Rename={stats_many_deltas['rename_ms']['mean']:.3f} ms, Total={stats_many_deltas['total_per_file_ms']:.3f} ms")

    return {
        "one_large_file": stats_one_full,
        "twenty_five_small_deltas": stats_many_deltas,
        "cumulative_rename_cost_25_deltas_ms": round(stats_many_deltas["rename_ms"]["mean"] * 25.0, 4),
    }


def run_isolation_study_compaction(scratch_dir: str) -> dict[str, Any]:
    """Study 6: Delta Compaction Overhead (normal vs pre-compaction vs compaction itself)."""
    print("\n--- Isolation Study 6: Delta Compaction Overhead ---")
    c_dir = os.path.join(scratch_dir, "study_compaction")
    os.makedirs(c_dir, exist_ok=True)

    adapter = IncrementalPersistenceAdapter(
        base_dir=c_dir,
        mission_id="m_compact_study",
        project_id="c_proj",
        compaction_interval=25,
    )

    normal_latencies = []
    pre_compact_latencies = []
    compaction_event_durations = []

    for seq in range(55):
        cp = generate_mission_checkpoint(seq, 200, "c_proj", "m_compact_study")
        t0 = time.perf_counter()
        res = adapter.save_checkpoint(cp)
        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0

        if seq % 25 == 24:
            # Step right before compaction trigger
            pre_compact_latencies.append(latency_ms)
        elif seq % 25 == 0 and seq > 0:
            # Compaction execution occurred inside save_checkpoint
            compaction_event_durations.append(latency_ms)
        else:
            normal_latencies.append(latency_ms)

    mean_normal = statistics.mean(normal_latencies) if normal_latencies else 0.0
    mean_pre = statistics.mean(pre_compact_latencies) if pre_compact_latencies else 0.0
    mean_compact = statistics.mean(compaction_event_durations) if compaction_event_durations else 0.0
    amortized_cost = (mean_compact - mean_normal) / 25.0

    print(f"  Normal Checkpoint Mean: {mean_normal:.3f} ms")
    print(f"  Pre-Compaction (24 deltas): {mean_pre:.3f} ms")
    print(f"  Compaction Event Mean: {mean_compact:.3f} ms")
    print(f"  Amortized Compaction Cost per Delta: {amortized_cost:.4f} ms")

    return {
        "normal_checkpoint_ms": calc_stats(normal_latencies),
        "pre_compaction_checkpoint_ms": calc_stats(pre_compact_latencies),
        "compaction_event_ms": calc_stats(compaction_event_durations),
        "COMPACTION_AMORTIZED_COST_PER_DELTA_MS": round(amortized_cost, 4),
    }


def run_isolation_study_storage_matrix(scratch_dir: str) -> dict[str, Any]:
    """Study 7: Storage Backend Matrix (Hybrid vs SQLite vs ShardedFilesystem)."""
    print("\n--- Isolation Study 7: Storage Backend Matrix ---")
    backends = ["Hybrid", "SQLite", "ShardedFilesystem"]
    results = {}

    horizon = 100
    cp_data = generate_mission_checkpoint(horizon, horizon, "mat_proj", "m_matrix")

    for backend_name in backends:
        b_dir = os.path.join(scratch_dir, f"matrix_{backend_name}")
        os.makedirs(b_dir, exist_ok=True)

        if backend_name == "Hybrid":
            backend = HybridMissionPersistence(workspace_root=b_dir)
        elif backend_name == "SQLite":
            backend = SQLiteMissionPersistence(workspace_root=b_dir)
        else:
            backend = ShardedFilesystemPersistence(workspace_root=b_dir)

        # Full persistence profiling
        full_save_times, full_load_times = [], []
        for _ in range(5):
            t0 = time.perf_counter()
            backend.save_checkpoint("mat_proj", "m_matrix", cp_data)
            t1 = time.perf_counter()
            full_save_times.append((t1 - t0) * 1000.0)

            t0 = time.perf_counter()
            loaded = backend.load_latest_checkpoint("mat_proj", "m_matrix")
            t1 = time.perf_counter()
            full_load_times.append((t1 - t0) * 1000.0)
            assert loaded is not None

        # Incremental delta profiling
        incr_times = []
        for seq in range(1, 11):
            if hasattr(backend, "save_checkpoint_delta"):
                delta_data = {
                    "delta_id": f"delta_{seq:04d}",
                    "sequence": seq,
                    "parent_hash": "0" * 64,
                    "content_hash": f"h_{seq:04d}",
                    "delta_json": json.dumps({"mutated_task": f"wp_{seq:04d}"}),
                    "created_at": utc_now(),
                }
                t0 = time.perf_counter()
                backend.save_checkpoint_delta("mat_proj", "m_matrix", delta_data)
                t1 = time.perf_counter()
            else:
                mutated_node = {
                    "work_package_id": f"wp_{seq:04d}",
                    "title": f"Task {seq}",
                    "status": "COMPLETED",
                    "type": "CODE",
                    "attempt_count": 2,
                }
                t0 = time.perf_counter()
                backend.save_work_package("mat_proj", "m_matrix", mutated_node)
                t1 = time.perf_counter()
            incr_times.append((t1 - t0) * 1000.0)

        f_save_mean = statistics.mean(full_save_times)
        f_load_mean = statistics.mean(full_load_times)
        incr_mean = statistics.mean(incr_times)

        print(f"  {backend_name:18s} -> Full Save: {f_save_mean:6.3f} ms | Full Load: {f_load_mean:6.3f} ms | Incr Save: {incr_mean:6.3f} ms")
        results[backend_name] = {
            "backend": backend_name,
            "full_save_ms": calc_stats(full_save_times),
            "full_load_ms": calc_stats(full_load_times),
            "incremental_save_ms": calc_stats(incr_times),
        }

    return results


def main() -> None:
    print("======================================================================")
    print("JARVIS OS — Phase 33.1 Checkpoint Latency Decomposition & Profiler")
    print("======================================================================")
    start_time = time.time()

    scratch_base = tempfile.mkdtemp(prefix="phase33_1_scratch_")
    horizons = [20, 50, 100, 150, 200, 250, 300, 500, 750, 1000]
    num_runs = 5

    try:
        # 1. Profile Workload A (Accumulated multi-node mutations)
        profile_workload_a = profile_workload(
            workload_type="WORKLOAD_A_ACCUMULATED",
            horizons=horizons,
            num_runs=num_runs,
            scratch_dir=scratch_base,
        )

        # 2. Profile Workload B (Single mutated node per transition)
        profile_workload_b = profile_workload(
            workload_type="WORKLOAD_B_SINGLE_MUTATION",
            horizons=horizons,
            num_runs=num_runs,
            scratch_dir=scratch_base,
        )

        # 3. 7 Controlled Isolation Studies
        study_delta_size = run_isolation_study_delta_size(scratch_base)
        study_hash = run_isolation_study_hash_overhead()
        study_manifest = run_isolation_study_manifest_overhead(scratch_base)
        study_fsync = run_isolation_study_fsync(scratch_base)
        study_file_creation = run_isolation_study_file_creation(scratch_base)
        study_compaction = run_isolation_study_compaction(scratch_base)
        study_storage_matrix = run_isolation_study_storage_matrix(scratch_base)

        # 4. Decompose and compare components at peak horizon (1000 tasks)
        peak_a = profile_workload_a["1000"]
        peak_b = profile_workload_b["1000"]

        # Component direct comparison table for Workload A
        comparison_table_a = []
        incr_subs_a = peak_a["incremental_subcomponents"]
        full_subs_a = peak_a["full_subcomponents"]

        # Map comparable components
        comp_pairs = [
            ("state_detection_discovery", full_subs_a["state_construction"]["mean"], incr_subs_a["mutation_detection"]["mean"] + incr_subs_a["changed_node_discovery"]["mean"] + incr_subs_a["delta_construction"]["mean"]),
            ("serialization", full_subs_a["serialization"]["mean"] + full_subs_a["json_encoding"]["mean"], incr_subs_a["delta_serialization"]["mean"] + incr_subs_a["json_struct_encoding"]["mean"]),
            ("hashing", full_subs_a["hash_calculation"]["mean"], incr_subs_a["sha256_content_hash"]["mean"] + incr_subs_a["merkle_parent_calculation"]["mean"]),
            ("file_creation_and_open", full_subs_a["file_creation"]["mean"], incr_subs_a["delta_file_creation"]["mean"]),
            ("disk_write", full_subs_a["disk_write"]["mean"], incr_subs_a["disk_write"]["mean"]),
            ("fsync", full_subs_a["fsync"]["mean"], incr_subs_a["fsync"]["mean"]),
            ("manifest_and_replace", full_subs_a["manifest_bookkeeping"]["mean"], incr_subs_a["manifest_update"]["mean"] + incr_subs_a["atomic_replace"]["mean"]),
            ("validation_and_bookkeeping", full_subs_a["validation"]["mean"], incr_subs_a["validation"]["mean"] + incr_subs_a["checkpoint_bookkeeping"]["mean"]),
        ]

        print("\n=========================================================================================")
        print("DIRECT COMPONENT COMPARISON TABLE (Workload A, Horizon 1000)")
        print(f"{'Component':<28} | {'Full (ms)':<10} | {'Incr (ms)':<10} | {'Delta (ms)':<10} | {'Diff (%)':<10}")
        print("-----------------------------------------------------------------------------------------")
        for name, f_ms, i_ms in comp_pairs:
            diff_ms = i_ms - f_ms
            pct = (diff_ms / max(1e-6, f_ms)) * 100.0
            comparison_table_a.append({
                "component": name,
                "full_ms": round(f_ms, 4),
                "incremental_ms": round(i_ms, 4),
                "delta_ms": round(diff_ms, 4),
                "difference_percentage": round(pct, 2),
            })
            print(f"{name:<28} | {f_ms:<10.4f} | {i_ms:<10.4f} | {diff_ms:<+10.4f} | {pct:<+10.2f}%")
        print("=========================================================================================\n")

        # 5. Identify TRUE HOT PATH for incremental persistence
        # Rank the 14 sub-components by latency
        ranked_subcomponents = sorted(
            [(k, v["mean"]) for k, v in incr_subs_a.items()],
            key=lambda item: item[1],
            reverse=True
        )
        first_hot_path_component = ranked_subcomponents[0][0]
        first_hot_path_cost_ms = ranked_subcomponents[0][1]

        second_hot_path_component = ranked_subcomponents[1][0]
        second_hot_path_cost_ms = ranked_subcomponents[1][1]

        print(f">>> FIRST_INCREMENTAL_HOT_PATH: {first_hot_path_component.upper()} ({first_hot_path_cost_ms:.4f} ms)")
        print(f">>> SECOND_INCREMENTAL_HOT_PATH: {second_hot_path_component.upper()} ({second_hot_path_cost_ms:.4f} ms)")

        # Compile JSON artifacts
        latency_profile_doc = {
            "metadata": {
                "phase": "33.1",
                "timestamp": utc_now(),
                "simulated": 0,
                "os": "windows",
                "filesystem": "NTFS",
                "num_runs": num_runs,
                "horizons": horizons,
            },
            "workload_a": profile_workload_a,
            "workload_b": profile_workload_b,
            "isolation_studies": {
                "study_1_delta_size_vs_latency": study_delta_size,
                "study_2_hash_overhead": study_hash,
                "study_3_manifest_overhead": study_manifest,
                "study_4_fsync_isolation": study_fsync,
                "study_5_file_creation_overhead": study_file_creation,
                "study_6_compaction_overhead": study_compaction,
                "study_7_storage_backend_matrix": study_storage_matrix,
            },
        }

        component_benchmark_doc = {
            "metadata": {
                "phase": "33.1",
                "timestamp": utc_now(),
                "simulated": 0,
                "first_incremental_hot_path": first_hot_path_component.upper(),
                "first_incremental_hot_path_ms": round(first_hot_path_cost_ms, 4),
                "second_incremental_hot_path": second_hot_path_component.upper(),
                "second_incremental_hot_path_ms": round(second_hot_path_cost_ms, 4),
            },
            "comparison_table_workload_a_1000": comparison_table_a,
            "ranked_subcomponents_workload_a": [
                {"rank": i + 1, "component": k, "mean_ms": round(v, 4)}
                for i, (k, v) in enumerate(ranked_subcomponents)
            ],
            "ranked_subcomponents_workload_b": [
                {"rank": i + 1, "component": k, "mean_ms": round(v["mean"], 4)}
                for i, (k, v) in enumerate(
                    sorted(peak_b["incremental_subcomponents"].items(), key=lambda x: x[1]["mean"], reverse=True)
                )
            ],
        }

        workload_comparison_doc = {
            "metadata": {
                "phase": "33.1",
                "timestamp": utc_now(),
                "simulated": 0,
            },
            "horizons": horizons,
            "comparison": [
                {
                    "horizon": h,
                    "workload_a_full_ms": profile_workload_a[str(h)]["full_total_ms"]["mean"],
                    "workload_a_incr_ms": profile_workload_a[str(h)]["incremental_total_ms"]["mean"],
                    "workload_a_byte_reduction_pct": profile_workload_a[str(h)]["byte_reduction_percentage"],
                    "workload_b_full_ms": profile_workload_b[str(h)]["full_total_ms"]["mean"],
                    "workload_b_incr_ms": profile_workload_b[str(h)]["incremental_total_ms"]["mean"],
                    "workload_b_byte_reduction_pct": profile_workload_b[str(h)]["byte_reduction_percentage"],
                }
                for h in horizons
            ],
        }

        # Write output files
        docs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
        os.makedirs(docs_dir, exist_ok=True)

        p1 = os.path.join(docs_dir, "phase33_1_latency_profile.json")
        with open(p1, "w", encoding="utf-8") as f:
            json.dump(latency_profile_doc, f, indent=2)
        print(f"Recorded: {p1}")

        p2 = os.path.join(docs_dir, "phase33_1_component_benchmark.json")
        with open(p2, "w", encoding="utf-8") as f:
            json.dump(component_benchmark_doc, f, indent=2)
        print(f"Recorded: {p2}")

        p3 = os.path.join(docs_dir, "phase33_1_workload_comparison.json")
        with open(p3, "w", encoding="utf-8") as f:
            json.dump(workload_comparison_doc, f, indent=2)
        print(f"Recorded: {p3}")

        elapsed = time.time() - start_time
        print(f"\nPhase 33.1 Profiling Completed Successfully in {elapsed:.2f}s.")

    finally:
        shutil.rmtree(scratch_base, ignore_errors=True)


if __name__ == "__main__":
    main()
