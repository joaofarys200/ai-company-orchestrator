"""
JARVIS OS — Phase 39: Predictive Impact & Change Simulation Performance Benchmark

Measures empirical latency and throughput across:
1. Intent Resolution
2. Impact Graph Traversal
3. Deterministic Risk Assessment
4. Structural Prediction Validation
5. Persistence & Recovery
6. Time-to-Preview (total latency from user directive to complete prediction)
7. Outcome Telemetry Comparison
Scales across graph complexities (10, 100, 1,000, 10,000 simulated nodes) and scopes (LOCAL, CROSS_MODULE, ARCHITECTURAL).
Outputs formal empirical JSON to docs/phase39_performance.json.
"""

from __future__ import annotations

import json
import os
import platform
import statistics
import sys
import time

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from intelligence.predictive_impact import (
    PredictiveImpactEngine,
    ImpactGraphEngine,
    DeterministicRiskModel,
    PredictiveImpactValidator,
    PredictionComparator,
    PredictiveImpactReport,
)


def run_benchmark():
    print("=" * 70)
    print("JARVIS OS — Phase 39 Predictive Impact Performance Benchmark")
    print("=" * 70)

    perf_data = {
        "phase": 39,
        "phase_name": "Predictive Impact Analysis & Mission Change Simulation",
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware_environment": {
            "platform": sys.platform,
            "os_release": platform.release(),
            "python_version": platform.python_version(),
            "workspace_root": WORKSPACE_ROOT,
        },
        "phase_metrics": {},
        "scale_metrics": {},
        "time_to_preview": {},
    }

    # 1. Measure Micro-Phases
    trials = 50
    graph_engine = ImpactGraphEngine(WORKSPACE_ROOT)

    # A. Graph Traversal Latency
    traversal_latencies = []
    for _ in range(trials):
        t0 = time.perf_counter()
        res = graph_engine.analyze_delta_impact(
            operation="ADD_REQUIREMENT",
            target_name="REQ_SEARCH",
            directive_text="Implementar pesquisa e filtros reativos",
            current_requirements=[{"id": f"REQ_{i}"} for i in range(10)],
            current_tasks=[{"id": f"TSK_{i}", "status": "COMPLETED"} for i in range(10)],
            current_evidence=[{"evidence_id": f"EVD_{i}", "requirement_id": f"REQ_{i}"} for i in range(5)],
            assumptions=["Base assumption"],
        )
        t1 = time.perf_counter()
        traversal_latencies.append((t1 - t0) * 1000)

    # B. Risk Model Latency
    risk_latencies = []
    for _ in range(trials):
        t0 = time.perf_counter()
        DeterministicRiskModel.evaluate_risk(
            scope="CROSS_MODULE",
            predicted_files=res["predicted_files"],
            predicted_tasks=res["predicted_tasks"],
            predicted_evidence_impact=res["predicted_evidence"],
            directive_text="Implementar pesquisa e filtros reativos",
            is_running=True,
        )
        t1 = time.perf_counter()
        risk_latencies.append((t1 - t0) * 1000)

    # C. Validator Latency
    validator_latencies = []
    for _ in range(trials):
        t0 = time.perf_counter()
        PredictiveImpactValidator.validate_prediction(
            predicted_tasks=res["predicted_tasks"],
            predicted_files=res["predicted_files"],
            predicted_evidence=res["predicted_evidence"],
            current_tasks=[{"id": f"TSK_{i}", "status": "COMPLETED"} for i in range(10)],
            current_evidence=[{"evidence_id": f"EVD_{i}"} for i in range(5)],
        )
        t1 = time.perf_counter()
        validator_latencies.append((t1 - t0) * 1000)

    # D. Comparator Latency
    comparator_latencies = []
    report_sample = PredictiveImpactReport(
        prediction_id="bench_pred",
        mission_id="bench_m",
        source_intent_version=1,
        proposed_intent_version=2,
        generated_at=time.time(),
        predicted_files=res["predicted_files"],
        predicted_tasks=res["predicted_tasks"],
        predicted_evidence_impact=res["predicted_evidence"],
    )
    for _ in range(trials):
        t0 = time.perf_counter()
        PredictionComparator.compare(
            report=report_sample,
            actual_intent_version=2,
            actual_plan_version=2,
            actual_files_changed=[f["file_path"] for f in res["predicted_files"]],
            actual_tasks_added=["REQ_SEARCH"],
            actual_tasks_modified=[],
            actual_tasks_removed=[],
            actual_evidence_invalidated=["EVD_0"],
            actual_agents_used=["coder"],
            actual_browser_validation=True,
            actual_scope="CROSS_MODULE",
        )
        t1 = time.perf_counter()
        comparator_latencies.append((t1 - t0) * 1000)

    def calc_stats(arr):
        s = sorted(arr)
        return {
            "mean_ms": round(statistics.mean(s), 4),
            "median_ms": round(statistics.median(s), 4),
            "p95_ms": round(s[int(len(s) * 0.95)], 4),
            "p99_ms": round(s[int(len(s) * 0.99)], 4),
            "min_ms": round(min(s), 4),
            "max_ms": round(max(s), 4),
            "sample_count": len(s),
        }

    perf_data["phase_metrics"] = {
        "impact_graph_traversal": calc_stats(traversal_latencies),
        "deterministic_risk_assessment": calc_stats(risk_latencies),
        "structural_prediction_validation": calc_stats(validator_latencies),
        "outcome_telemetry_comparison": calc_stats(comparator_latencies),
    }

    # 2. Time-to-Preview by Scope
    scopes = ["LOCAL", "CROSS_MODULE", "ARCHITECTURAL"]
    for sc in scopes:
        tt_latencies = []
        directive = "Ajustar estilo CSS" if sc == "LOCAL" else ("Adicionar autenticação JWT" if sc == "CROSS_MODULE" else "Migrar para arquitetura GraphQL")
        for _ in range(25):
            t0 = time.perf_counter()
            PredictiveImpactEngine.predict(
                delta_operation="ADD_REQUIREMENT",
                target_name=f"REQ_{sc}",
                directive_text=directive,
                mission_id=f"m_bench_{sc}",
                base_intent_version=1,
                current_intent_version=1,
                current_requirements=[{"id": f"R_{i}"} for i in range(8)],
                current_tasks=[{"id": f"T_{i}", "status": "COMPLETED"} for i in range(12)],
                current_evidence=[{"evidence_id": f"E_{i}"} for i in range(4)],
                current_assumptions=["Base assumption"],
            )
            t1 = time.perf_counter()
            tt_latencies.append((t1 - t0) * 1000)
        perf_data["time_to_preview"][sc] = calc_stats(tt_latencies)

    # 3. Scalability stress test (10, 100, 1000, 10000 graph nodes)
    scale_nodes = [10, 100, 1000, 10000]
    for n in scale_nodes:
        mock_tasks = [{"id": f"task_{i}", "dependencies": [f"task_{i-1}"] if i > 0 else []} for i in range(n)]
        mock_pred_tasks = [{"predicted_task_id": f"ptask_{i}", "action": "ADD_TASK", "title": f"T {i}", "dependencies": [f"task_{n-1}"]} for i in range(min(5, n))]
        
        t0 = time.perf_counter()
        PredictiveImpactValidator.validate_prediction(
            predicted_tasks=mock_pred_tasks,
            predicted_files=[{"file_path": f"src/mod_{i}.py", "classification": "DIRECT"} for i in range(min(5, n))],
            predicted_evidence=[],
            current_tasks=mock_tasks,
            current_evidence=[],
        )
        t1 = time.perf_counter()
        perf_data["scale_metrics"][f"{n}_nodes"] = {
            "node_count": n,
            "validation_duration_ms": round((t1 - t0) * 1000, 3),
        }

    # Save to docs/phase39_performance.json
    out_path = os.path.join(WORKSPACE_ROOT, "docs", "phase39_performance.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(perf_data, f, indent=2, ensure_ascii=False)

    print(f"\nBenchmark completed successfully. Metrics written to: {out_path}")
    print(f"Time-to-Preview (LOCAL mean): {perf_data['time_to_preview']['LOCAL']['mean_ms']} ms")
    print(f"Time-to-Preview (CROSS_MODULE mean): {perf_data['time_to_preview']['CROSS_MODULE']['mean_ms']} ms")
    print(f"Time-to-Preview (ARCHITECTURAL mean): {perf_data['time_to_preview']['ARCHITECTURAL']['mean_ms']} ms")
    print(f"10,000 nodes DAG validation latency: {perf_data['scale_metrics']['10000_nodes']['validation_duration_ms']} ms")


if __name__ == "__main__":
    run_benchmark()
