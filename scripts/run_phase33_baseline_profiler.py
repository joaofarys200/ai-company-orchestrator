"""
JARVIS OS — Phase 33: Baseline Checkpoint Profiling & Hot Path Diagnostics Runner

Executes 7 transition scaling levels (20, 50, 100, 150, 200, 250, 300) x 5 runs = 35 runs.
Measures the existing FULL_CHECKPOINT architecture across 10 distinct sub-components:
1. state construction
2. state serialization
3. JSON encoding
4. compression
5. disk write
6. fsync / durability
7. hash calculation
8. manifest update
9. checkpoint validation
10. recovery metadata

Generates:
- docs/phase33_baseline.json
- docs/phase33_checkpoint_profile.json
Identifies:
- FIRST_CHECKPOINT_HOT_PATH
"""

import json
import math
import os
import shutil
import statistics
import sys
import tempfile
import time
from typing import Any, Dict, List

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.checkpoint_profiler import CheckpointProfiler, build_synthetic_task_graph


def calc_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    mean_val = statistics.mean(values)
    med_val = statistics.median(values)
    std_val = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "mean": round(mean_val, 4),
        "median": round(med_val, 4),
        "std": round(std_val, 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def run_baseline_profiler(num_runs_per_level: int = 5):
    print("=" * 80)
    print("PHASE 33 — FULL CHECKPOINT BASELINE PROFILER & HOT PATH ANALYSIS")
    print("Zero optimization before measurement. Profiling 10 sub-components.")
    print("=" * 80)

    transition_levels = [20, 50, 100, 150, 200, 250, 300]
    temp_scratch = tempfile.mkdtemp(prefix="phase33_baseline_scratch_")

    raw_results_by_level: dict[int, list[dict[str, Any]]] = {}
    component_aggregates_by_level: dict[int, dict[str, list[float]]] = {}

    all_component_names = [
        "1_state_construction",
        "2_state_serialization",
        "3_json_encoding",
        "4_compression",
        "5_disk_write",
        "6_fsync_durability",
        "7_hash_calculation",
        "8_manifest_update",
        "9_checkpoint_validation",
        "10_recovery_metadata",
    ]

    total_runs = len(transition_levels) * num_runs_per_level
    current_run = 0

    for level in transition_levels:
        raw_results_by_level[level] = []
        component_aggregates_by_level[level] = {c: [] for c in all_component_names}
        print(f"\n[LEVEL] Profiling transition horizon: {level} tasks ({num_runs_per_level} runs)...")

        graph = build_synthetic_task_graph(level)

        for r_idx in range(1, num_runs_per_level + 1):
            current_run += 1
            run_dir = os.path.join(temp_scratch, f"level_{level}_run_{r_idx}")

            prof_result = CheckpointProfiler.profile_checkpoint_save(
                task_graph=graph,
                mission_id=f"mission_lh_{level}",
                project_id=f"project_lh_{level}",
                sequence=r_idx,
                target_dir=run_dir,
                simulate_fsync=True,
                use_compression=False,
            )

            res_dict = prof_result.to_dict()
            raw_results_by_level[level].append(res_dict)

            for comp_key in all_component_names:
                dur = prof_result.components[comp_key].duration_ms
                component_aggregates_by_level[level][comp_key].append(dur)

            print(
                f"  Run {r_idx}/{num_runs_per_level} [{current_run:02d}/{total_runs:02d}]: "
                f"Total: {prof_result.total_duration_ms:.3f}ms | "
                f"Load: {prof_result.load_duration_ms:.3f}ms | "
                f"Size: {prof_result.total_bytes_written} B | "
                f"Hot Path: {prof_result.hot_path_component}"
            )

    # ── COMPUTE BASELINE SUMMARY & CURVES ──
    baseline_summary: dict[str, Any] = {}
    hot_path_counts: dict[str, int] = {}
    global_component_times: dict[str, list[float]] = {c: [] for c in all_component_names}

    for level in transition_levels:
        runs = raw_results_by_level[level]
        total_latencies = [r["total_duration_ms"] for r in runs]
        load_latencies = [r["load_duration_ms"] for r in runs]
        sizes = [float(r["total_bytes_written"]) for r in runs]
        cpu_times = [r["cpu_time_ms"] for r in runs]

        comp_stats = {}
        for c in all_component_names:
            c_times = component_aggregates_by_level[level][c]
            comp_stats[c] = calc_stats(c_times)
            global_component_times[c].extend(c_times)

        # Identify level hot path
        level_hot = max(all_component_names, key=lambda c: comp_stats[c]["mean"])
        hot_path_counts[level_hot] = hot_path_counts.get(level_hot, 0) + 1

        baseline_summary[str(level)] = {
            "task_transitions": level,
            "sample_size": len(runs),
            "checkpoint_save_duration_ms": calc_stats(total_latencies),
            "checkpoint_load_duration_ms": calc_stats(load_latencies),
            "serialization_size_bytes": calc_stats(sizes),
            "cpu_time_ms": calc_stats(cpu_times),
            "level_hot_path": level_hot,
            "subcomponents": comp_stats,
        }

    # Identify global first hot path
    global_hot_component = max(all_component_names, key=lambda c: statistics.mean(global_component_times[c]))

    # ── GENERATE DOCUMENTS ──
    docs_dir = os.path.abspath("docs")
    os.makedirs(docs_dir, exist_ok=True)

    baseline_doc = {
        "report_id": "phase33_baseline",
        "timestamp": time.time(),
        "total_executions": total_runs,
        "strategy": "FULL_CHECKPOINT",
        "tested_horizons": transition_levels,
        "first_checkpoint_hot_path": global_hot_component,
        "scaling_summary": baseline_summary,
        "full_checkpoint_latency_curve": [
            {
                "transitions": lvl,
                "save_latency_ms": baseline_summary[str(lvl)]["checkpoint_save_duration_ms"]["mean"],
                "load_latency_ms": baseline_summary[str(lvl)]["checkpoint_load_duration_ms"]["mean"],
                "size_bytes": baseline_summary[str(lvl)]["serialization_size_bytes"]["mean"],
            }
            for lvl in transition_levels
        ],
    }

    # Detailed 10-subcomponent profile doc
    profile_doc = {
        "report_id": "phase33_checkpoint_profile",
        "timestamp": time.time(),
        "total_runs": total_runs,
        "first_checkpoint_hot_path": global_hot_component,
        "component_breakdown_overall": {
            comp: {
                "stats": calc_stats(times),
                "mean_percentage": round(
                    (statistics.mean(times) / max(0.001, sum(statistics.mean(global_component_times[c]) for c in all_component_names))) * 100.0,
                    2,
                ),
            }
            for comp, times in global_component_times.items()
        },
        "raw_runs": raw_results_by_level,
    }

    with open(os.path.join(docs_dir, "phase33_baseline.json"), "w", encoding="utf-8") as f:
        json.dump(baseline_doc, f, indent=2, ensure_ascii=False)

    with open(os.path.join(docs_dir, "phase33_checkpoint_profile.json"), "w", encoding="utf-8") as f:
        json.dump(profile_doc, f, indent=2, ensure_ascii=False)

    shutil.rmtree(temp_scratch, ignore_errors=True)

    print("\n" + "=" * 80)
    print("PHASE 33 BASELINE PROFILER COMPLETE")
    print("=" * 80)
    print(f"Total Runs:                 {total_runs} (7 levels x {num_runs_per_level} runs)")
    print(f"FIRST_CHECKPOINT_HOT_PATH:  {global_hot_component}")
    print("\nScaling Curve (Save Latency & Size):")
    for lvl in transition_levels:
        s = baseline_summary[str(lvl)]
        print(f"  {lvl:3d} transitions -> Latency: {s['checkpoint_save_duration_ms']['mean']:6.3f}ms (load: {s['checkpoint_load_duration_ms']['mean']:6.3f}ms) | Size: {s['serialization_size_bytes']['mean']:8.1f} bytes | Hot: {s['level_hot_path']}")

    print("\n10-Component Relative Weight:")
    for comp in all_component_names:
        p = profile_doc["component_breakdown_overall"][comp]
        print(f"  {comp:25s}: {p['stats']['mean']:6.3f}ms ({p['mean_percentage']:5.1f}%)")

    print(f"\nArtifacts saved: docs/phase33_baseline.json, docs/phase33_checkpoint_profile.json")
    print("=" * 80)

    return baseline_doc


if __name__ == "__main__":
    run_baseline_profiler(num_runs_per_level=5)
