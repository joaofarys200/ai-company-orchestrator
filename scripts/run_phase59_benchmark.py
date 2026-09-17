"""Phase 59 Benchmark Suite: Evaluates SCC Detection, Condensation, Incremental Updates,
Memory, Storage, and Naive DFS vs SCC Condensation across Synthetic Scales (100k - 10M LOC)
and Dense SCC Clusters (2 to 10,000 nodes).
"""

import gc
import json
import os
import sys
import time
from typing import Any, Dict, List, Tuple

# Ensure repository root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


from backend.agents.scc_aware_graph import (
    CouplingAnalyzer,
    GraphCondenser,
    IncrementalSCCUpdater,
    SCCAwareGraphBridge,
    SCCDetector,
    SqliteSCCStorage,
    TarjanSCC,
)


def generate_synthetic_scale_graph(scale_loc: int) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Generates synthetic scale dependency graph representing estimated LOC.
    Assumes ~100 LOC per symbol/function/file.
    100k LOC -> ~1,000 nodes
    500k LOC -> ~5,000 nodes
    1M LOC   -> ~10,000 nodes
    5M LOC   -> ~50,000 nodes
    10M LOC  -> ~100,000 nodes (sparse representation to avoid memory exhaust)
    """
    node_count = max(100, scale_loc // 100)
    nodes = [f"sym_{i}" for i in range(node_count)]
    edges: List[Dict[str, Any]] = []

    # Introduce realistic structure:
    # 80% acyclic DAG edges, 20% participating in cyclic SCC clusters of size 3 to 10
    cluster_size = 5
    cycle_nodes_count = int(node_count * 0.20)
    for c in range(0, cycle_nodes_count, cluster_size):
        for i in range(cluster_size):
            u = f"sym_{c + i}"
            v = f"sym_{c + ((i + 1) % cluster_size)}"
            edges.append({"source": u, "target": v, "edge_type": "cyclic_call"})

    # Connect clusters and acyclic nodes in downstream pipeline
    step = max(1, node_count // 500)
    for i in range(0, node_count - step, step):
        edges.append({"source": f"sym_{i}", "target": f"sym_{i + step}", "edge_type": "pipeline"})

    return nodes, edges


def benchmark_synthetic_scales() -> Dict[str, Any]:
    scales = [
        ("100k LOC", 100_000),
        ("500k LOC", 500_000),
        ("1M LOC", 1_000_000),
        ("5M LOC", 5_000_000),
        ("10M LOC", 10_000_000),
    ]

    results: Dict[str, Any] = {}

    for label, loc in scales:
        gc.collect()
        t0_gen = time.perf_counter()
        nodes, edges = generate_synthetic_scale_graph(loc)
        gen_time = time.perf_counter() - t0_gen

        # SCC Detection
        t0_detect = time.perf_counter()
        sccs = SCCDetector.detect_sccs(nodes, edges)
        detect_time = (time.perf_counter() - t0_detect) * 1000.0

        # Condensation
        t0_cond = time.perf_counter()
        dag = GraphCondenser.condense(sccs)
        cond_time = (time.perf_counter() - t0_cond) * 1000.0

        # Memory calculation approximate
        mem_kb = (sys.getsizeof(nodes) + sys.getsizeof(edges) + len(sccs) * 256) / 1024.0

        # Query Latency
        node_map = {n: s.scc_id for s in sccs for n in s.nodes}
        from backend.agents.scc_aware_graph.impact import SCCAwareImpactAnalyzer
        analyzer = SCCAwareImpactAnalyzer(dag, node_map)

        t0_query = time.perf_counter()
        impact_res = analyzer.analyze_impact([nodes[0]], max_sccs=15, max_nodes=250)
        query_time = (time.perf_counter() - t0_query) * 1000.0

        results[label] = {
            "loc": loc,
            "raw_nodes": len(nodes),
            "raw_edges": len(edges),
            "scc_count": len(sccs),
            "dag_nodes": len(dag.nodes),
            "dag_edges": len(dag.edges),
            "scc_detection_ms": round(detect_time, 3),
            "condensation_ms": round(cond_time, 3),
            "impact_query_ms": round(query_time, 3),
            "memory_kb": round(mem_kb, 2),
            "dag_is_acyclic": dag.is_acyclic,
        }
        print(f"  - Completed {label}: {len(nodes)} nodes, detect={detect_time:.1f}ms, condense={cond_time:.1f}ms", flush=True)


    return results


def benchmark_dense_clusters() -> Dict[str, Any]:
    cluster_sizes = [2, 3, 10, 100, 1_000, 10_000]
    dense_results: Dict[str, Any] = {}

    for size in cluster_sizes:
        gc.collect()
        nodes = [f"dense_{i}" for i in range(size)]
        edges = [{"source": nodes[i], "target": nodes[(i + 1) % size], "edge_type": "cycle"} for i in range(size)]
        # Add random cross-chords inside cluster for higher density
        if size <= 1000:
            for i in range(0, size, 5):
                edges.append({"source": nodes[i], "target": nodes[(i + 3) % size], "edge_type": "chord"})

        t0 = time.perf_counter()
        sccs = SCCDetector.detect_sccs(nodes, edges)
        elapsed_detect_ms = (time.perf_counter() - t0) * 1000.0

        dag = GraphCondenser.condense(sccs)
        coupling = CouplingAnalyzer.analyze_scc(sccs[0])

        dense_results[f"{size}_node_scc"] = {
            "cluster_size": size,
            "internal_edges": len(edges),
            "detected_sccs": len(sccs),
            "is_single_scc": (len(sccs) == 1),
            "detection_ms": round(elapsed_detect_ms, 3),
            "density": round(coupling.density, 4),
            "coupling_score": round(coupling.coupling_score, 4),
            "dag_acyclic": dag.is_acyclic,
        }

    return dense_results


def benchmark_naive_vs_scc() -> Dict[str, Any]:
    # Construct a cycle of 30 nodes with 5 downstream consumers
    cycle_nodes = [f"c_node_{i}" for i in range(30)]
    edges = [{"source": cycle_nodes[i], "target": cycle_nodes[(i + 1) % 30]} for i in range(30)]
    # Connect last node to downstream consumer chain
    consumers = [f"ext_consumer_{i}" for i in range(10)]
    edges.append({"source": cycle_nodes[15], "target": consumers[0]})
    for i in range(9):
        edges.append({"source": consumers[i], "target": consumers[i + 1]})

    all_nodes = cycle_nodes + consumers
    bridge = SCCAwareGraphBridge.build_from_graph(all_nodes, edges)
    comparison = bridge.impact_analyzer.compare_naive_vs_scc_impact([cycle_nodes[0]], edges, naive_max_depth=3, naive_max_nodes=15)

    return comparison


def main():
    print("=" * 60)
    print("FASE 59 BENCHMARK: SCC CONDENSATION & BOUNDED IMPACT ANALYSIS")
    print("=" * 60)

    print("\n1. Executing Synthetic Scale Benchmarks (100k - 10M LOC)...")
    scale_benchmarks = benchmark_synthetic_scales()
    for scale, metrics in scale_benchmarks.items():
        print(f"  - {scale:10s} | Nodes: {metrics['raw_nodes']:6d} | SCCs: {metrics['scc_count']:5d} | Detect: {metrics['scc_detection_ms']:7.2f}ms | Condense: {metrics['condensation_ms']:7.2f}ms | DAG Acyclic: {metrics['dag_is_acyclic']}")

    print("\n2. Executing Dense SCC Test Corpus (2 to 10,000 nodes)...")
    dense_benchmarks = benchmark_dense_clusters()
    for name, d in dense_benchmarks.items():
        print(f"  - {name:15s} | Edges: {d['internal_edges']:6d} | Detect: {d['detection_ms']:7.2f}ms | Density: {d['density']:6.3f} | Score: {d['coupling_score']:5.2f}")

    print("\n3. Comparing Naive DFS vs SCC-Aware Condensation...")
    comp = benchmark_naive_vs_scc()
    print(f"  - Naive Visited: {comp['naive_approach']['nodes_visited']} (Truncated mid-cycle: {comp['naive_approach']['truncated_arbitrarily']})")
    print(f"  - SCC Visited:   {comp['scc_aware_approach']['nodes_visited']} (Internal: {comp['scc_aware_approach']['internal_nodes']}, External: {comp['scc_aware_approach']['external_nodes']}, Boundaries Cut: {comp['scc_aware_approach']['boundary_edges']})")

    benchmark_output = {
        "scale_benchmarks": scale_benchmarks,
        "dense_benchmarks": dense_benchmarks,
        "naive_vs_scc_comparison": comp,
        "timestamp": time.time(),
        "epistemic_calibration": {
            "claim": "Validated on synthetic 100k-10M LOC and up to 10,000-node dense cycles.",
            "prohibited_claim": "Universal solution to all arbitrary cyclic graphs without depth budget.",
        },
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/phase59_performance.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_output, f, indent=2)

    print("\nBenchmark results saved to docs/phase59_performance.json")


if __name__ == "__main__":
    main()
