"""
JARVIS OS — Phase 18.2: Adaptive Worker Pool, Benchmark Calibration & Single-Host Scaling
Benchmark Suite & Verification Engine.

Generates:
1. docs/phase18_2_benchmark_results.json

Evaluates:
- CanonicalWorkload determinism and provenance hash
- Throughput Sanity Check: completed + failed + deferred <= created
- Cold vs Warm worker pool profiling (spawn, init, queue_wait, send, recv, dispatch, exec, result, shutdown)
- Optimal Worker Count Matrix (1, 2, 4, 8, 16, 32)
- Batch Size Matrix (1, 2, 4, 8, 16, 32, 64, 128, 256)
- Multi-scale empirical evaluation at N=32, 64, 128, 256, 512, 1024, 2048 with 10 independent replicates
- A/B comparison: Phase 18 static process vs Phase 18.1 adaptive vs Phase 18.2 optimized adaptive
- Cost model accuracy: predicted vs measured cost
- Worker utilization and straggler detection
- Memory and OS handle scaling (process handles, threads, parent RSS, worker RSS, peak RSS)
- Scale exploration up to 4096 (empirical limit probe)
- Telemetry ON vs OFF overhead
"""

from __future__ import annotations

import asyncio
import copy
import gc
import hashlib
import json
import logging
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

sys.stdout.reconfigure(line_buffering=True)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

import psutil

# Suppress debug logs
logging.getLogger("agents.swarm_coordinator").setLevel(logging.WARNING)
logging.getLogger("agents.swarm_federation").setLevel(logging.WARNING)

from agents.swarm_coordinator import (
    AgentCapability,
    AgentCategory,
    AgentInstance,
    ResourceClass,
)
from agents.swarm_federation import (
    AdaptiveBackend,
    AdaptiveWorkerDecision,
    AdaptiveWorkerPolicy,
    CanonicalWorkload,
    CostHistoryRecord,
    DeterministicSubSwarmPartitioner,
    ExecutionCostHistory,
    InProcessBackend,
    ProcessBackend,
    SubSwarmWorkerJob,
    SubSwarmWorkerPool,
    SubSwarmWorkerResult,
    SwarmFederation,
    SwarmIsolationMode,
    ThreadBackend,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def get_git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=WORKSPACE_ROOT)
        return out.decode().strip()
    except Exception:
        return "phase18_2_local"


def get_process_handle_stats() -> dict[str, int]:
    try:
        p = psutil.Process(os.getpid())
        num_handles = p.num_handles() if hasattr(p, "num_handles") else 0
        num_threads = p.num_threads()
        return {"handles": num_handles, "threads": num_threads}
    except Exception:
        return {"handles": 0, "threads": 0}


def get_memory_breakdown_mb(worker_pids: set[int] | None = None) -> dict[str, float]:
    try:
        p = psutil.Process(os.getpid())
        parent_rss = p.memory_info().rss / (1024.0 * 1024.0)
        worker_rss = 0.0
        if worker_pids:
            for pid in worker_pids:
                try:
                    wp = psutil.Process(pid)
                    if wp.is_running():
                        worker_rss += wp.memory_info().rss / (1024.0 * 1024.0)
                except Exception:
                    pass
        return {
            "parent_rss_mb": round(parent_rss, 2),
            "worker_rss_mb": round(worker_rss, 2),
            "total_rss_mb": round(parent_rss + worker_rss, 2),
        }
    except Exception:
        return {"parent_rss_mb": 0.0, "worker_rss_mb": 0.0, "total_rss_mb": 0.0}


def compute_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
    s = sorted(values)
    n = len(s)
    mean = sum(s) / n
    variance = sum((x - mean) ** 2 for x in s) / (n - 1) if n > 1 else 0.0
    stddev = math.sqrt(variance)

    def percentile(p: float) -> float:
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return s[int(k)]
        return s[int(f)] * (c - k) + s[int(c)] * (k - f)

    return {
        "mean": round(mean, 2),
        "median": round(percentile(0.50), 2),
        "stddev": round(stddev, 2),
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
        "p50": round(percentile(0.50), 2),
        "p95": round(percentile(0.95), 2),
        "p99": round(percentile(0.99), 2),
    }


def make_agents(n: int) -> list[AgentInstance]:
    agents = []
    for i in range(n):
        cat = AgentCategory.CODING if i % 2 == 0 else AgentCategory.TESTING
        cap = AgentCapability(
            agent_type=cat.value,
            categories=[cat],
            concurrency_limit=2,
            resource_classes=[ResourceClass.CPU],
        )
        agents.append(AgentInstance(
            agent_id=f"ag_{i:04d}",
            agent_type=cat.value,
            capability=cap,
        ))
    return agents


async def profile_worker_lifecycle() -> dict[str, Any]:
    print("\n--- 1. Worker Pool Profiling (Cold vs Warm) ---")
    cw = CanonicalWorkload.generate(task_count=64, n_modules=4, seed="lifecycle_prof")
    agents = make_agents(32)

    # 1. Cold Spawn & Initialization
    t0 = time.perf_counter()
    pool_cold = SubSwarmWorkerPool(max_workers=2)
    _ = pool_cold.get_executor()
    spawn_ms = pool_cold._spawn_latency_ms
    init_ms = (time.perf_counter() - t0) * 1000.0

    job1 = SubSwarmWorkerJob(
        subswarm_id="subswarm_00",
        project_id="p_prof",
        mission_id="m_prof",
        tasks=list(cw.task_graph.nodes.values())[:8],
        agents=agents[:8],
        batch_size=8,
    )
    t_sub = time.perf_counter()
    res1 = await pool_cold.execute_jobs([job1])
    cold_dur_ms = (time.perf_counter() - t_sub) * 1000.0

    r1: SubSwarmWorkerResult = res1[0]  # type: ignore

    # 2. Warm Execution
    job2 = SubSwarmWorkerJob(
        subswarm_id="subswarm_00",
        project_id="p_prof",
        mission_id="m_prof",
        tasks=list(cw.task_graph.nodes.values())[8:16],
        agents=agents[:8],
        batch_size=8,
    )
    t_warm = time.perf_counter()
    res2 = await pool_cold.execute_jobs([job2])
    warm_dur_ms = (time.perf_counter() - t_warm) * 1000.0
    r2: SubSwarmWorkerResult = res2[0]  # type: ignore

    t_shut0 = time.perf_counter()
    pool_cold.shutdown()
    shutdown_ms = (time.perf_counter() - t_shut0) * 1000.0

    data = {
        "cold": {
            "worker_spawn_ms": round(spawn_ms, 2),
            "worker_initialization_ms": round(init_ms, 2),
            "job_queue_wait_ms": round(r1.queue_wait_ms, 2),
            "ipc_send_ms": round(r1.pipe_send_ms, 2),
            "worker_dispatch_ms": round(r1.worker_dispatch_ms, 2),
            "worker_execution_ms": round(r1.worker_execution_ms, 2),
            "ipc_receive_ms": round(r1.pipe_receive_ms, 2),
            "worker_result_ms": round(r1.result_deserialization_ms, 2),
            "total_latency_ms": round(cold_dur_ms, 2),
        },
        "warm": {
            "worker_spawn_ms": 0.0,
            "worker_initialization_ms": 0.0,
            "job_queue_wait_ms": round(r2.queue_wait_ms, 2),
            "ipc_send_ms": round(r2.pipe_send_ms, 2),
            "worker_dispatch_ms": round(r2.worker_dispatch_ms, 2),
            "worker_execution_ms": round(r2.worker_execution_ms, 2),
            "ipc_receive_ms": round(r2.pipe_receive_ms, 2),
            "worker_result_ms": round(r2.result_deserialization_ms, 2),
            "total_latency_ms": round(warm_dur_ms, 2),
        },
        "worker_shutdown_ms": round(shutdown_ms, 2),
        "warm_speedup": round(cold_dur_ms / max(0.001, warm_dur_ms), 2),
    }
    print(f"Cold spawn: {spawn_ms:.2f}ms, Cold total: {cold_dur_ms:.2f}ms | Warm total: {warm_dur_ms:.2f}ms (Speedup: {data['warm_speedup']}x)")
    return data


async def evaluate_worker_count_matrix() -> dict[str, Any]:
    print("\n--- 2. Optimal Worker Count Matrix (Workers 1, 2, 4, 8 for N=128..2048) ---")
    scales = [128, 256, 512, 1024, 2048]
    worker_options = [1, 2, 4, 8, 16]
    results: dict[str, dict[str, Any]] = {}

    for n_agents in scales:
        results[str(n_agents)] = {}
        task_cnt = min(512, n_agents)
        subswarms = min(16, max(1, n_agents // 32))

        for w in worker_options:
            if w > subswarms and w > 4:
                continue
            cw = CanonicalWorkload.generate(task_count=task_cnt, n_modules=subswarms, seed=f"opt_w_{n_agents}_{w}")
            agents = make_agents(n_agents)

            fed = SwarmFederation(
                project_id=f"p_w_{n_agents}_{w}",
                mission_id=f"m_w_{n_agents}_{w}",
                task_graph=cw.task_graph,
                max_agents_per_subswarm=32,
                isolation_mode=SwarmIsolationMode.PROCESS,
                max_workers=w,
            )
            try:
                fed.initialize_federation(agents, max_subswarms=subswarms)
                t0 = time.perf_counter()
                res = await fed.execute_workload_isolated(max_rounds=20, batch_size=16)
                wall_s = max(0.0001, time.perf_counter() - t0)
                comp = res["completed_tasks"]
                tp = comp / wall_s

                snap = fed.get_telemetry_snapshot()
                total_rss = snap.get("handle_stats", {}).get("total_rss_mb", 0.0)
                results[str(n_agents)][str(w)] = {
                    "throughput": round(tp, 2),
                    "wall_clock_s": round(wall_s, 4),
                    "completed_tasks": comp,
                    "worker_count": w,
                    "worker_utilization": snap.get("worker_utilizations", {}),
                    "total_rss_mb": total_rss,
                }
                print(f"N={n_agents:4d} | Workers={w:2d} -> Throughput: {tp:8.2f} t/s | RSS: {total_rss:.1f} MB")
            finally:
                fed.shutdown_worker_pool()

    return results


async def evaluate_batch_size_matrix() -> dict[str, Any]:
    print("\n--- 3. Batch Size Matrix (Batch 1..256 for N=128..2048) ---")
    scales = [128, 256, 512, 1024, 2048]
    batch_options = [1, 2, 4, 8, 16, 32, 64, 128, 256]
    results: dict[str, dict[str, Any]] = {}

    for n_agents in scales:
        results[str(n_agents)] = {}
        task_cnt = min(512, n_agents)
        subswarms = min(8, max(1, n_agents // 32))

        for b in batch_options:
            if b > task_cnt:
                continue
            cw = CanonicalWorkload.generate(task_count=task_cnt, n_modules=subswarms, seed=f"batch_{n_agents}_{b}")
            agents = make_agents(n_agents)

            fed = SwarmFederation(
                project_id=f"p_b_{n_agents}_{b}",
                mission_id=f"m_b_{n_agents}_{b}",
                task_graph=cw.task_graph,
                max_agents_per_subswarm=32,
                isolation_mode=SwarmIsolationMode.PROCESS,
                max_workers=4,
            )
            try:
                fed.initialize_federation(agents, max_subswarms=subswarms)
                t0 = time.perf_counter()
                res = await fed.execute_workload_isolated(max_rounds=30, batch_size=b)
                wall_s = max(0.0001, time.perf_counter() - t0)
                comp = res["completed_tasks"]
                tp = comp / wall_s
                results[str(n_agents)][str(b)] = {
                    "throughput": round(tp, 2),
                    "wall_clock_s": round(wall_s, 4),
                    "batch_size": b,
                    "completed_tasks": comp,
                }
            finally:
                fed.shutdown_worker_pool()
        best_b = max(results[str(n_agents)].keys(), key=lambda k: results[str(n_agents)][k]["throughput"])
        print(f"N={n_agents:4d} | Optimal Batch Size: {best_b} -> {results[str(n_agents)][best_b]['throughput']} t/s")

    return results


async def evaluate_multi_scale_empirical() -> dict[str, Any]:
    print("\n--- 4. Multi-Scale Benchmark (N=32..2048, 10 Replicates) & A/B Comparison ---")
    scales = [32, 64, 128, 256, 512, 1024, 2048]
    replicates_count = 10
    policy = AdaptiveWorkerPolicy()
    history = ExecutionCostHistory()

    results: dict[str, Any] = {
        "phase18_static_process": {},
        "phase18_1_adaptive": {},
        "phase18_2_optimized_adaptive": {},
        "cost_model_validation": {},
    }

    for n_agents in scales:
        subswarms = min(16, max(1, n_agents // 32))
        task_cnt = min(256, n_agents)
        cw = CanonicalWorkload.generate(task_count=task_cnt, n_modules=subswarms, seed=f"canonical_eval_{n_agents}")

        print(f"\n[Benchmarking N={n_agents} Agents | Tasks={task_cnt} | Subswarms={subswarms}]")

        # 1. Phase 18 Static Process (fixed M=4, batch=8)
        p18_tps = []
        for rep in range(replicates_count):
            fed_p18 = SwarmFederation(
                project_id=f"p18_{n_agents}_{rep}",
                mission_id=f"m18_{n_agents}_{rep}",
                task_graph=copy.deepcopy(cw.task_graph),
                max_agents_per_subswarm=32,
                isolation_mode=SwarmIsolationMode.PROCESS,
                max_workers=min(4, subswarms),
            )
            try:
                fed_p18.initialize_federation(make_agents(n_agents), max_subswarms=subswarms)
                t0 = time.perf_counter()
                res = await fed_p18.execute_workload_isolated(max_rounds=25, batch_size=8)
                wall_s = max(0.0001, time.perf_counter() - t0)
                tp = res["completed_tasks"] / wall_s
                p18_tps.append(tp)
            finally:
                fed_p18.shutdown_worker_pool()

        # 2. Phase 18.1 Adaptive (hardcoded threshold: N>=128 -> PROCESS with batch=8)
        p18_1_tps = []
        for rep in range(replicates_count):
            mode_18_1 = SwarmIsolationMode.INPROCESS if n_agents < 96 else SwarmIsolationMode.PROCESS
            fed_p18_1 = SwarmFederation(
                project_id=f"p18_1_{n_agents}_{rep}",
                mission_id=f"m18_1_{n_agents}_{rep}",
                task_graph=copy.deepcopy(cw.task_graph),
                max_agents_per_subswarm=32,
                isolation_mode=mode_18_1,
                max_workers=min(4, subswarms),
            )
            try:
                fed_p18_1.initialize_federation(make_agents(n_agents), max_subswarms=subswarms)
                t0 = time.perf_counter()
                res = await fed_p18_1.execute_workload_isolated(max_rounds=25, batch_size=8)
                wall_s = max(0.0001, time.perf_counter() - t0)
                tp = res["completed_tasks"] / wall_s
                p18_1_tps.append(tp)
            finally:
                fed_p18_1.shutdown_worker_pool()

        # 3. Phase 18.2 Optimized Adaptive (AdaptiveWorkerPolicy + Dynamic Batching)
        p18_2_tps = []
        dec = policy.evaluate(
            agent_count=n_agents,
            subswarms_count=subswarms,
            task_count=task_cnt,
            queue_depth=task_cnt,
            estimated_task_duration_ms=0.5,
            history=history,
        )

        for rep in range(replicates_count):
            fed_p18_2 = SwarmFederation(
                project_id=f"p18_2_{n_agents}_{rep}",
                mission_id=f"m18_2_{n_agents}_{rep}",
                task_graph=copy.deepcopy(cw.task_graph),
                max_agents_per_subswarm=32,
                isolation_mode=dec.execution_mode,
                max_workers=dec.worker_count,
            )
            try:
                fed_p18_2.initialize_federation(make_agents(n_agents), max_subswarms=subswarms)
                t0 = time.perf_counter()
                res = await fed_p18_2.execute_workload_isolated(max_rounds=25, batch_size=dec.batch_size, dynamic_batching=True)
                wall_s = max(0.0001, time.perf_counter() - t0)
                tp = res["completed_tasks"] / wall_s
                p18_2_tps.append(tp)

                # Throughput sanity check verification
                assert fed_p18_2.tasks_completed + fed_p18_2.tasks_failed + fed_p18_2.tasks_deferred <= fed_p18_2.tasks_created
            finally:
                fed_p18_2.shutdown_worker_pool()

        s_p18 = compute_stats(p18_tps)
        s_p18_1 = compute_stats(p18_1_tps)
        s_p18_2 = compute_stats(p18_2_tps)

        results["phase18_static_process"][str(n_agents)] = s_p18
        results["phase18_1_adaptive"][str(n_agents)] = s_p18_1
        results["phase18_2_optimized_adaptive"][str(n_agents)] = {
            **s_p18_2,
            "selected_mode": dec.execution_mode.value,
            "selected_workers": dec.worker_count,
            "selected_batch": dec.batch_size,
            "speedup_vs_phase18": round(s_p18_2["mean"] / max(1.0, s_p18["mean"]), 2),
            "speedup_vs_phase18_1": round(s_p18_2["mean"] / max(1.0, s_p18_1["mean"]), 2),
        }

        # Cost model validation
        pred_cost = dec.metrics.get("cost_process" if dec.execution_mode == SwarmIsolationMode.PROCESS else "cost_inprocess", 1.0)
        measured_cost = 1000.0 / max(1.0, s_p18_2["mean"])
        abs_err = abs(pred_cost - measured_cost)
        rel_err = abs_err / max(0.001, measured_cost)

        results["cost_model_validation"][str(n_agents)] = {
            "predicted_cost": round(pred_cost, 4),
            "measured_cost": round(measured_cost, 4),
            "absolute_error": round(abs_err, 4),
            "relative_error": round(rel_err, 4),
        }

        # Record into history
        history.record(CostHistoryRecord(
            workload_sha256=cw.workload_sha256,
            agent_count=n_agents,
            task_count=task_cnt,
            task_duration_ms=0.5,
            execution_mode=dec.execution_mode.value,
            worker_count=dec.worker_count,
            batch_size=dec.batch_size,
            observed_throughput=s_p18_2["mean"],
            observed_latency_ms=measured_cost,
        ))

        print(f"P18 Static: {s_p18['mean']:8.2f} t/s | P18.1 Adaptive: {s_p18_1['mean']:8.2f} t/s | P18.2 Optimized: {s_p18_2['mean']:8.2f} t/s [{dec.execution_mode.value} W={dec.worker_count} B={dec.batch_size}] (Speedup: {results['phase18_2_optimized_adaptive'][str(n_agents)]['speedup_vs_phase18_1']}x)")

    return results


async def evaluate_memory_and_handle_scaling() -> dict[str, Any]:
    print("\n--- 5. Resource & OS Handle Scaling (Scales 512, 1024, 1536, 2048, 3072, 4096) ---")
    probe_scales = [512, 1024, 1536, 2048, 3072, 4096]
    results: dict[str, Any] = {}

    for n in probe_scales:
        subswarms = min(16, max(1, n // 32))
        cw = CanonicalWorkload.generate(task_count=128, n_modules=subswarms, seed=f"mem_probe_{n}")
        agents = make_agents(n)

        fed = SwarmFederation(
            project_id=f"p_probe_{n}",
            mission_id=f"m_probe_{n}",
            task_graph=cw.task_graph,
            max_agents_per_subswarm=32,
            isolation_mode=SwarmIsolationMode.PROCESS,
            max_workers=4,
        )
        try:
            fed.initialize_federation(agents, max_subswarms=subswarms)
            res = await fed.execute_workload_isolated(max_rounds=5, batch_size=16)

            backend = fed.get_or_create_backend()
            worker_pids = set(backend.pool._worker_pids) if isinstance(backend, ProcessBackend) else set()
            mem_breakdown = get_memory_breakdown_mb(worker_pids)
            h_stats = get_process_handle_stats()

            results[str(n)] = {
                "status": "PASS" if res["completed_tasks"] > 0 else "FAIL",
                "completed_tasks": res["completed_tasks"],
                "parent_rss_mb": mem_breakdown["parent_rss_mb"],
                "worker_rss_mb": mem_breakdown["worker_rss_mb"],
                "total_rss_mb": mem_breakdown["total_rss_mb"],
                "handles": h_stats["handles"],
                "threads": h_stats["threads"],
                "worker_pids_count": len(worker_pids),
            }
            print(f"Scale N={n:4d} | Total RSS: {mem_breakdown['total_rss_mb']:6.1f} MB (Parent: {mem_breakdown['parent_rss_mb']:.1f}, Workers: {mem_breakdown['worker_rss_mb']:.1f}) | Handles: {h_stats['handles']:4d} | Threads: {h_stats['threads']:3d}")
        except Exception as ex:
            results[str(n)] = {
                "status": "FAIL",
                "error": str(ex),
                "error_type": type(ex).__name__,
            }
            print(f"Scale N={n:4d} | FAILED: {ex}")
            break
        finally:
            fed.shutdown_worker_pool()

    return results


async def evaluate_telemetry_overhead() -> dict[str, Any]:
    print("\n--- 6. Telemetry Overhead Evaluation ---")
    cw = CanonicalWorkload.generate(task_count=128, n_modules=4, seed="telem_eval")
    agents = make_agents(128)

    # 1. Telemetry ON (event callbacks active)
    t_on_runs = []
    for _ in range(5):
        fed_on = SwarmFederation(
            project_id="p_tel_on",
            mission_id="m_tel_on",
            task_graph=copy.deepcopy(cw.task_graph),
            max_agents_per_subswarm=32,
            isolation_mode=SwarmIsolationMode.INPROCESS,
            max_workers=2,
            emit_callback=lambda et, d: None,
        )
        try:
            fed_on.initialize_federation(agents, max_subswarms=4)
            t0 = time.perf_counter()
            _ = await fed_on.execute_workload_isolated(max_rounds=15, batch_size=8)
            t_on_runs.append(time.perf_counter() - t0)
        finally:
            fed_on.shutdown_worker_pool()

    # 2. Telemetry OFF
    t_off_runs = []
    for _ in range(5):
        fed_off = SwarmFederation(
            project_id="p_tel_off",
            mission_id="m_tel_off",
            task_graph=copy.deepcopy(cw.task_graph),
            max_agents_per_subswarm=32,
            isolation_mode=SwarmIsolationMode.INPROCESS,
            max_workers=2,
            emit_callback=None,
        )
        try:
            fed_off.initialize_federation(agents, max_subswarms=4)
            t0 = time.perf_counter()
            _ = await fed_off.execute_workload_isolated(max_rounds=15, batch_size=8)
            t_off_runs.append(time.perf_counter() - t0)
        finally:
            fed_off.shutdown_worker_pool()

    mean_on = sum(t_on_runs) / len(t_on_runs)
    mean_off = sum(t_off_runs) / len(t_off_runs)
    overhead_pct = ((mean_on - mean_off) / mean_off) * 100.0 if mean_off > 0 else 0.0

    print(f"Telemetry ON: {mean_on * 1000:.2f}ms | Telemetry OFF: {mean_off * 1000:.2f}ms | Overhead: {overhead_pct:.2f}%")
    return {
        "telemetry_on_ms": round(mean_on * 1000.0, 2),
        "telemetry_off_ms": round(mean_off * 1000.0, 2),
        "overhead_percent": round(overhead_pct, 3),
        "within_1_percent": overhead_pct <= 1.0,
    }


async def main():
    print("================================================================================")
    print("JARVIS OS — Phase 18.2 Benchmark & Verification Execution")
    print("================================================================================")
    t_start = time.perf_counter()

    canonical_sample = CanonicalWorkload.generate(task_count=128, n_modules=4, seed="canonical_sha")

    provenance = {
        "commit_sha": get_git_commit(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": "Windows 11 / PowerShell",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu": f"{os.cpu_count()} cores",
        "memory": f"{round(psutil.virtual_memory().total / (1024**3), 1)} GB",
        "workload_sha256": canonical_sample.workload_sha256,
    }
    print(f"Commit: {provenance['commit_sha']} | Python: {provenance['python_version']} | SHA: {provenance['workload_sha256'][:16]}...")

    lifecycle_profile = await profile_worker_lifecycle()
    worker_matrix = await evaluate_worker_count_matrix()
    batch_matrix = await evaluate_batch_size_matrix()
    multi_scale = await evaluate_multi_scale_empirical()
    memory_handles = await evaluate_memory_and_handle_scaling()
    telemetry_data = await evaluate_telemetry_overhead()

    final_payload = {
        "provenance": provenance,
        "worker_lifecycle_profile": lifecycle_profile,
        "worker_count_matrix": worker_matrix,
        "batch_size_matrix": batch_matrix,
        "multi_scale_empirical_10_runs": multi_scale,
        "memory_and_handle_scaling": memory_handles,
        "telemetry_overhead": telemetry_data,
        "total_benchmark_duration_s": round(time.perf_counter() - t_start, 2),
    }

    out_path = os.path.join(WORKSPACE_ROOT, "docs", "phase18_2_benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)

    print(f"\nBenchmark completed successfully! Results written to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
