"""
JARVIS OS — Phase 53: Preflight and Recovery Performance Benchmarks
Measures microbenchmarks and mission-level recovery latencies across preflight,
diagnostics, repair planning, atomic patch application, and healthcheck probes.
Outputs results to docs/phase53_performance.json.
"""

import json
import os
import sys
import tempfile
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.project_preflight import (
    DiagnosticErrorClass,
    HealthcheckEngine,
    JavaScriptPreflightAnalyzer,
    PreflightPolicy,
    ProjectPreflightBridge,
    ProjectProfileDetector,
    RuntimeDiagnosticEngine,
    SafeRepairPlanner,
)


def run_benchmark():
    bridge = ProjectPreflightBridge()
    runs = []

    print("[Phase 53 Benchmark] Initiating Preflight & Auto-Recovery performance benchmark...")

    for i in range(50):
        with tempfile.TemporaryDirectory() as tmp:
            app_file = os.path.join(tmp, "app.js")
            pkg_file = os.path.join(tmp, "package.json")
            with open(pkg_file, "w", encoding="utf-8") as f:
                json.dump({"name": f"bench_{i}", "main": "app.js"}, f)
            with open(app_file, "w", encoding="utf-8") as f:
                f.write("app.get('/health', (req, res) => res.send('ok'));\n")

            # 1. Preflight Latency
            t0 = time.perf_counter()
            pre_res = bridge.run_preflight(tmp, f"bench_{i}")
            pre_ms = (time.perf_counter() - t0) * 1000.0

            # 2. Diagnostic Latency
            log = "ReferenceError: app is not defined\n    at Object.<anonymous> (app.js:1:1)"
            t1 = time.perf_counter()
            diag = bridge.diagnose_failure(log, tmp, f"bench_{i}")
            diag_ms = (time.perf_counter() - t1) * 1000.0

            # 3. Recovery Planning & Application
            t2 = time.perf_counter()
            if diag:
                rec_run = bridge.plan_and_apply_recovery(diag, tmp, f"bench_{i}", PreflightPolicy.STANDARD)
            rec_ms = (time.perf_counter() - t2) * 1000.0

            runs.append({
                "iteration": i,
                "preflight_ms": pre_ms,
                "diagnostic_ms": diag_ms,
                "recovery_ms": rec_ms,
            })

    # Aggregates
    benchmarks = bridge.telemetry.compute_benchmarks(runs)

    output_data = {
        "phase": 53,
        "title": "Universal Project Preflight & Runtime Failure Auto-Recovery Benchmark",
        "total_benchmark_runs": len(runs),
        "latencies": benchmarks,
        "raw_samples_summary": {
            "min_preflight_ms": round(min(r["preflight_ms"] for r in runs), 2),
            "max_preflight_ms": round(max(r["preflight_ms"] for r in runs), 2),
            "min_diagnostic_ms": round(min(r["diagnostic_ms"] for r in runs), 2),
            "max_diagnostic_ms": round(max(r["diagnostic_ms"] for r in runs), 2),
            "min_recovery_ms": round(min(r["recovery_ms"] for r in runs), 2),
            "max_recovery_ms": round(max(r["recovery_ms"] for r in runs), 2),
        },
        "timestamp": time.time(),
        "status": "COMPLETED",
    }

    out_path = os.path.join("docs", "phase53_performance.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"[Phase 53 Benchmark] Saved performance metrics to {out_path}:")
    print(f"  • Avg Preflight Latency: {benchmarks['avg_preflight_ms']} ms")
    print(f"  • Avg Diagnostic Latency: {benchmarks['avg_diagnostic_ms']} ms")
    print(f"  • Avg Recovery Latency: {benchmarks['avg_recovery_ms']} ms")
    print(f"  • Time to First Diagnosis: {benchmarks['time_to_first_diagnosis']} ms")


if __name__ == "__main__":
    run_benchmark()
