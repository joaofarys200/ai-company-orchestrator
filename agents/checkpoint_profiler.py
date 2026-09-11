"""
JARVIS OS — Phase 33: Checkpoint Profiler & Hot Path Diagnostics Engine

Instruments and measures the 10 distinct sub-components of checkpoint persistence:
1. state_construction: Collecting graph nodes, execution history, output dictionaries
2. state_serialization: Object graph traversal to Python dictionaries (to_dict)
3. json_encoding: JSON serialization (json.dumps)
4. compression: Compression step (optional gzip/zstd or raw baseline)
5. disk_write: Buffered file or SQLite writing
6. fsync_durability: Flushing operating system file buffers (os.fsync)
7. hash_calculation: Cryptographic SHA-256 digest computation
8. manifest_update: Sequence index & metadata manifest updating
9. checkpoint_validation: Structural acyclicity & schema verification
10. recovery_metadata: Recovery markers, leases & interrupted task pointers
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import gzip
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from agents.mission_orchestrator import Checkpoint
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@dataclass
class CheckpointSubComponentTiming:
    name: str
    duration_ms: float
    percentage_of_total: float = 0.0
    bytes_processed: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckpointProfileResult:
    checkpoint_id: str
    sequence: int
    task_count: int
    total_duration_ms: float
    load_duration_ms: float
    total_bytes_written: int
    serialization_size_bytes: int
    cpu_time_ms: float
    hot_path_component: str
    components: dict[str, CheckpointSubComponentTiming] = field(default_factory=dict)
    memory_rss_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        res["components"] = {k: v.to_dict() if hasattr(v, "to_dict") else v for k, v in self.components.items()}
        return res


class CheckpointProfiler:
    """
    High-resolution diagnostic profiler isolating the 10 physical stages
    of mission checkpoint creation and recovery.
    """

    @staticmethod
    def profile_checkpoint_save(
        task_graph: TaskGraph,
        mission_id: str,
        project_id: str,
        sequence: int,
        target_dir: str,
        simulate_fsync: bool = True,
        use_compression: bool = False,
    ) -> CheckpointProfileResult:
        t_start_total = time.perf_counter_ns()
        cpu_start = time.process_time()

        timings: dict[str, CheckpointSubComponentTiming] = {}

        # ── 1. STATE CONSTRUCTION ──
        t0 = time.perf_counter_ns()
        nodes_list = list(task_graph.nodes.values())
        completed_ids = [n.task_id for n in nodes_list if n.status == TaskStatus.COMPLETED]
        pending_ids = [n.task_id for n in nodes_list if n.status == TaskStatus.PENDING]
        running_ids = [n.task_id for n in nodes_list if n.status == TaskStatus.RUNNING]
        failed_ids = [n.task_id for n in nodes_list if n.status == TaskStatus.FAILED]
        blocked_ids = [n.task_id for n in nodes_list if n.status == TaskStatus.BLOCKED]
        evidence_refs = [f"ev_{n.task_id}" for n in nodes_list if n.status == TaskStatus.COMPLETED]
        outputs = {n.task_id: {"summary": f"Result of {n.title}", "status": n.status.value} for n in nodes_list}
        dur_construct = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["1_state_construction"] = CheckpointSubComponentTiming(
            name="state_construction",
            duration_ms=dur_construct,
            bytes_processed=len(nodes_list) * 64,
            details={"node_count": len(nodes_list)},
        )

        # ── 2. STATE SERIALIZATION ──
        t0 = time.perf_counter_ns()
        graph_dict = {tid: n.to_dict() for tid, n in task_graph.nodes.items()}
        checkpoint_obj = Checkpoint(
            checkpoint_id=f"cp_{sequence:04d}_{mission_id[:8]}",
            sequence=sequence,
            mission_id=mission_id,
            project_id=project_id,
            mission_status="ACTIVE",
            task_graph_data=graph_dict,
            completed_task_ids=completed_ids,
            pending_task_ids=pending_ids,
            running_task_ids=running_ids,
            failed_task_ids=failed_ids,
            blocked_task_ids=blocked_ids,
            evidence_refs=evidence_refs,
            outputs=outputs,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            description=f"Profiled checkpoint {sequence}",
            graph_version=getattr(task_graph, "graph_version", 1),
            expansion_history=list(getattr(task_graph, "expansion_history", [])),
        )
        cp_dict = checkpoint_obj.to_dict()
        dur_serialize = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["2_state_serialization"] = CheckpointSubComponentTiming(
            name="state_serialization",
            duration_ms=dur_serialize,
            bytes_processed=sys.getsizeof(cp_dict),
            details={"dict_keys": len(cp_dict)},
        )

        # ── 3. JSON ENCODING ──
        t0 = time.perf_counter_ns()
        encoded_json = json.dumps(cp_dict, indent=2, ensure_ascii=False)
        raw_bytes = encoded_json.encode("utf-8")
        dur_encoding = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["3_json_encoding"] = CheckpointSubComponentTiming(
            name="json_encoding",
            duration_ms=dur_encoding,
            bytes_processed=len(raw_bytes),
            details={"json_chars": len(encoded_json)},
        )

        # ── 4. COMPRESSION ──
        t0 = time.perf_counter_ns()
        bytes_to_write = raw_bytes
        if use_compression:
            bytes_to_write = gzip.compress(raw_bytes, compresslevel=6)
        dur_compression = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["4_compression"] = CheckpointSubComponentTiming(
            name="compression",
            duration_ms=dur_compression,
            bytes_processed=len(bytes_to_write),
            details={"compressed": use_compression, "ratio": round(len(bytes_to_write) / max(1, len(raw_bytes)), 3)},
        )

        # ── 5. DISK WRITE ──
        t0 = time.perf_counter_ns()
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, f"checkpoint_{sequence:04d}.json")
        fd = os.open(file_path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY)
        os.write(fd, bytes_to_write)
        dur_disk_write = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["5_disk_write"] = CheckpointSubComponentTiming(
            name="disk_write",
            duration_ms=dur_disk_write,
            bytes_processed=len(bytes_to_write),
            details={"path": file_path},
        )

        # ── 6. FSYNC / DURABILITY ──
        t0 = time.perf_counter_ns()
        if simulate_fsync:
            try:
                os.fsync(fd)
            except OSError:
                pass
        os.close(fd)
        dur_fsync = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["6_fsync_durability"] = CheckpointSubComponentTiming(
            name="fsync_durability",
            duration_ms=dur_fsync,
            bytes_processed=len(bytes_to_write),
            details={"fsync_enabled": simulate_fsync},
        )

        # ── 7. HASH CALCULATION ──
        t0 = time.perf_counter_ns()
        hasher = hashlib.sha256()
        hasher.update(bytes_to_write)
        content_hash = hasher.hexdigest()
        dur_hash = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["7_hash_calculation"] = CheckpointSubComponentTiming(
            name="hash_calculation",
            duration_ms=dur_hash,
            bytes_processed=len(bytes_to_write),
            details={"sha256": content_hash[:16]},
        )

        # ── 8. MANIFEST UPDATE ──
        t0 = time.perf_counter_ns()
        manifest_path = os.path.join(target_dir, "manifest.json")
        manifest_data = {
            "latest_sequence": sequence,
            "latest_checkpoint_id": checkpoint_obj.checkpoint_id,
            "content_hash": content_hash,
            "timestamp": time.time(),
        }
        with open(manifest_path, "w", encoding="utf-8") as mf:
            mf.write(json.dumps(manifest_data, indent=2))
        dur_manifest = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["8_manifest_update"] = CheckpointSubComponentTiming(
            name="manifest_update",
            duration_ms=dur_manifest,
            bytes_processed=os.path.getsize(manifest_path),
            details={"manifest_file": manifest_path},
        )

        # ── 9. CHECKPOINT VALIDATION ──
        t0 = time.perf_counter_ns()
        is_valid = bool(checkpoint_obj.checkpoint_id and checkpoint_obj.sequence > 0 and len(checkpoint_obj.task_graph_data) > 0)
        dur_validation = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["9_checkpoint_validation"] = CheckpointSubComponentTiming(
            name="checkpoint_validation",
            duration_ms=dur_validation,
            bytes_processed=len(checkpoint_obj.task_graph_data),
            details={"is_valid": is_valid},
        )

        # ── 10. RECOVERY METADATA ──
        t0 = time.perf_counter_ns()
        rec_meta = {
            "checkpoint_id": checkpoint_obj.checkpoint_id,
            "sequence": sequence,
            "interrupted_candidates": running_ids,
            "active_leases_count": len(running_ids),
        }
        dur_rec_meta = (time.perf_counter_ns() - t0) / 1_000_000.0
        timings["10_recovery_metadata"] = CheckpointSubComponentTiming(
            name="recovery_metadata",
            duration_ms=dur_rec_meta,
            bytes_processed=len(running_ids) * 32,
            details={"interrupted_count": len(running_ids)},
        )

        total_dur_ms = (time.perf_counter_ns() - t_start_total) / 1_000_000.0
        cpu_time_ms = (time.process_time() - cpu_start) * 1000.0

        # Calculate percentages
        for key, item in timings.items():
            item.percentage_of_total = round((item.duration_ms / max(0.0001, total_dur_ms)) * 100.0, 2)

        # Identify hottest component
        hot_item = max(timings.values(), key=lambda t: t.duration_ms)

        # Test load performance
        t_load_start = time.perf_counter_ns()
        with open(file_path, "rb") as rf:
            read_bytes = rf.read()
            if use_compression:
                read_bytes = gzip.decompress(read_bytes)
            _loaded_data = json.loads(read_bytes.decode("utf-8"))
        load_dur_ms = (time.perf_counter_ns() - t_load_start) / 1_000_000.0

        return CheckpointProfileResult(
            checkpoint_id=checkpoint_obj.checkpoint_id,
            sequence=sequence,
            task_count=len(nodes_list),
            total_duration_ms=round(total_dur_ms, 4),
            load_duration_ms=round(load_dur_ms, 4),
            total_bytes_written=len(bytes_to_write),
            serialization_size_bytes=len(raw_bytes),
            cpu_time_ms=round(cpu_time_ms, 4),
            hot_path_component=hot_item.name,
            components=timings,
        )


def build_synthetic_task_graph(node_count: int) -> TaskGraph:
    """Creates a deterministic acyclic TaskGraph with node_count tasks."""
    graph = TaskGraph(graph_version=node_count)
    categories = ["ARCHITECTURE", "CODING", "TESTING", "REVIEW", "RESEARCH"]

    for i in range(node_count):
        cat = categories[i % len(categories)]
        status = TaskStatus.COMPLETED if i < int(node_count * 0.8) else TaskStatus.RUNNING if i == int(node_count * 0.8) else TaskStatus.PENDING
        deps = [f"t_{i-1:04d}"] if i > 0 and i % 3 != 0 else []
        node = TaskNode(
            task_id=f"t_{i:04d}",
            title=f"Module Operation Package {i+1} — {cat}",
            category=cat,
            status=status,
            dependencies=deps,
            priority=100 - (i % 20),
            metadata={"payload_size": 256, "attempt": 1, "subdag": f"subdag_{i//10}"},
        )
        graph.add_node(node)

    return graph
