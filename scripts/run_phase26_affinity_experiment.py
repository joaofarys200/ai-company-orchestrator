"""
JARVIS OS — Phase 26: Core Saturation Experiment (Affinity Only)
Tests 1 core, 2 cores, 4 cores, 8 cores, and all 16 logical CPUs.
Uses process affinity only without modifying the datapath.
"""

import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

import psutil

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(WORKSPACE_ROOT, "docs")
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport import RioSocket

AFFINITY_CONFIGS = {
    "1_core": [0],
    "2_cores": [0, 1],
    "4_cores": [0, 1, 2, 3],
    "8_cores": [0, 1, 2, 3, 4, 5, 6, 7],
    "all_16_cores": list(range(psutil.cpu_count(logical=True) or 16)),
}

TEST_TARGETS_MB = [300, 450, 475, 500, 600]
REPLICATES = 3
CHUNK_SIZE = 1200


def run_affinity_test_point(affinity_mask: List[int], target_mb: int) -> Dict[str, Any]:
    """Runs a single test point with the process pinned to affinity_mask."""
    proc = psutil.Process()
    orig_affinity = proc.cpu_affinity()
    proc.cpu_affinity(affinity_mask)

    receiver = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=8 * 1024 * 1024, queue_depth=1024)
    sender = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=8 * 1024 * 1024, queue_depth=1024)
    sender.connect("127.0.0.1", receiver.bind_port)

    burst_duration_sec = 0.10
    target_bytes = int(target_mb * 1024 * 1024 * burst_duration_sec)
    num_pkts = max(1, target_bytes // CHUNK_SIZE)
    batch_size = 32
    num_batches = max(1, num_pkts // batch_size)
    payload = b"AFFINITY_EXP_PAYLOAD_" * 55  # 1200 bytes
    batch_payload = [payload] * batch_size

    # CPU before
    t0 = time.perf_counter()
    cpu_before = psutil.cpu_times()
    proc_before = proc.cpu_times()

    sent_pkts = 0
    drops = 0
    batch_latencies = []

    for _ in range(num_batches):
        tb0 = time.perf_counter()
        sent = sender.send_batch(batch_payload)
        tb1 = time.perf_counter()
        sent_pkts += sent
        if sent < batch_size:
            drops += (batch_size - sent)
        batch_latencies.append(((tb1 - tb0) * 1000.0) / batch_size)

    dur = max(time.perf_counter() - t0, 0.0001)
    cpu_after = psutil.cpu_times()
    proc_after = proc.cpu_times()

    sender.close()
    receiver.close()

    # Restore original affinity
    proc.cpu_affinity(orig_affinity)

    achieved_mb_s = round((sent_pkts * CHUNK_SIZE) / (1024 * 1024 * dur), 2)
    pkt_rate = round(sent_pkts / dur, 1)

    user_dur = max(0.0, proc_after.user - proc_before.user)
    sys_dur = max(0.0, proc_after.system - proc_before.system)
    user_pct = round((user_dur / dur) * 100.0, 2)
    sys_pct = round((sys_dur / dur) * 100.0, 2)
    dpc_delta = max(0.0, getattr(cpu_after, "dpc", 0.0) - getattr(cpu_before, "dpc", 0.0))

    sorted_lats = sorted(batch_latencies)
    p95 = round(sorted_lats[int(len(sorted_lats) * 0.95)], 4) if sorted_lats else 0.0

    return {
        "target_mb_s": target_mb,
        "achieved_mb_s": achieved_mb_s,
        "packet_rate": pkt_rate,
        "packet_loss": drops,
        "user_cpu_pct": user_pct,
        "kernel_cpu_pct": sys_pct,
        "dpc_delta_sec": round(dpc_delta, 4),
        "latency_p95_ms": p95,
    }


def main():
    print("=" * 80)
    print("JARVIS OS — PHASE 26: CORE SATURATION EXPERIMENT (AFFINITY ONLY)")
    print("=" * 80)

    affinity_results = {}

    for config_name, mask in AFFINITY_CONFIGS.items():
        print(f"\n--- Testing Affinity: {config_name} (CPUs: {mask}) ---")
        config_data = {}
        for target in TEST_TARGETS_MB:
            runs = []
            for _ in range(REPLICATES):
                runs.append(run_affinity_test_point(mask, target))
                time.sleep(0.01)

            mean_tp = round(statistics.mean(r["achieved_mb_s"] for r in runs), 2)
            std_tp = round(statistics.stdev(r["achieved_mb_s"] for r in runs), 2) if len(runs) > 1 else 0.0
            mean_user = round(statistics.mean(r["user_cpu_pct"] for r in runs), 2)
            mean_sys = round(statistics.mean(r["kernel_cpu_pct"] for r in runs), 2)
            mean_dpc = round(statistics.mean(r["dpc_delta_sec"] for r in runs), 4)

            config_data[str(target)] = {
                "target_mb_s": target,
                "achieved_mean_mb_s": mean_tp,
                "achieved_stdev_mb_s": std_tp,
                "user_cpu_pct": mean_user,
                "kernel_cpu_pct": mean_sys,
                "dpc_delta_sec": mean_dpc,
                "runs": runs,
            }
            print(f"  Target {target:3d} MB/s -> Achieved: {mean_tp:6.2f} MB/s (std: {std_tp:4.2f}) | User: {mean_user:5.1f}% | Kernel: {mean_sys:5.1f}% | DPC: {mean_dpc:.4f}s")

        # Peak plateau achieved under this affinity
        plateau_candidates = [
            config_data[str(t)]["achieved_mean_mb_s"]
            for t in [475, 500, 600]
        ]
        peak_plateau = round(statistics.mean(plateau_candidates), 2)
        affinity_results[config_name] = {
            "affinity_mask": mask,
            "core_count": len(mask),
            "peak_plateau_mb_s": peak_plateau,
            "targets": config_data,
        }

    # Analyze scaling:
    p_1 = affinity_results["1_core"]["peak_plateau_mb_s"]
    p_2 = affinity_results["2_cores"]["peak_plateau_mb_s"]
    p_4 = affinity_results["4_cores"]["peak_plateau_mb_s"]
    p_8 = affinity_results["8_cores"]["peak_plateau_mb_s"]
    p_all = affinity_results["all_16_cores"]["peak_plateau_mb_s"]

    # Scaling ratio from 1 core to all cores
    scaling_ratio = round(p_all / max(p_1, 1.0), 2)

    if scaling_ratio >= 2.0:
        scaling_conclusion = "STRONG_CPU_AFFINITY_BOTTLENECK: Plateau scales significantly with more cores."
    elif scaling_ratio >= 1.25:
        scaling_conclusion = "MODERATE_AFFINITY_EFFECT: Plateau shows modest scaling, partially bound by core allocation."
    else:
        scaling_conclusion = "CORE_INDEPENDENT_SERIALIZATION: Plateau does NOT scale proportionally with cores. Kernel dispatch serialization (AFD/NDIS) dominates independent of available logical cores."

    print("\n" + "=" * 80)
    print("AFFINITY SATURATION SCALING SUMMARY:")
    print(f"  1 Core:       {p_1:6.2f} MB/s")
    print(f"  2 Cores:      {p_2:6.2f} MB/s")
    print(f"  4 Cores:      {p_4:6.2f} MB/s")
    print(f"  8 Cores:      {p_8:6.2f} MB/s")
    print(f"  All 16 Cores: {p_all:6.2f} MB/s")
    print(f"  Scaling Ratio (All / 1-Core): {scaling_ratio}x")
    print(f"  Causal Finding: {scaling_conclusion}")
    print("=" * 80)

    output_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scaling_summary": {
            "1_core_mb_s": p_1,
            "2_cores_mb_s": p_2,
            "4_cores_mb_s": p_4,
            "8_cores_mb_s": p_8,
            "all_16_cores_mb_s": p_all,
            "scaling_ratio": scaling_ratio,
            "conclusion": scaling_conclusion,
        },
        "configs": affinity_results,
    }

    out_file = os.path.join(DOCS_DIR, "phase26_affinity_experiment.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)
    print(f"Saved affinity experiment results to: {out_file}")


if __name__ == "__main__":
    main()
