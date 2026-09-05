"""Large Graph Scalability Benchmark for Fase 13.1.

Measures validation time, topological sort time, edge counts, and memory across:
- 100, 500, 900, 1000, 2000, 5000, 10000 nodes
- Topologies: chain, reverse insertion chain, branching, wide, dense, cycle, deep cycle.
"""

from __future__ import annotations

import os
import sys
import time
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.task_graph import (
    TaskGraph,
    TaskGraphCycleError,
    TaskNode,
)


def format_mem(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.2f} MB"


def benchmark_graph(name: str, nodes: list[TaskNode], expect_cycle: bool = False) -> dict:
    edge_count = sum(len(n.dependencies) for n in nodes)
    node_count = len(nodes)

    tracemalloc.start()
    t0 = time.perf_counter()
    has_cycle = False
    error_msg = ""
    graph = None

    try:
        graph = TaskGraph(nodes=nodes)
        val_time_ms = (time.perf_counter() - t0) * 1000
    except TaskGraphCycleError as ce:
        val_time_ms = (time.perf_counter() - t0) * 1000
        has_cycle = True
        error_msg = str(ce)

    # Topological sort benchmark (if valid DAG)
    topo_time_ms = 0.0
    if not has_cycle and graph is not None:
        t1 = time.perf_counter()
        order = graph.topological_sort()
        topo_time_ms = (time.perf_counter() - t1) * 1000
        assert len(order) == node_count

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    if expect_cycle:
        result_status = "PASS (Cycle Detected)" if has_cycle else "FAIL (Cycle Not Caught)"
    else:
        result_status = "PASS" if not has_cycle else f"FAIL (Unexpected Cycle: {error_msg})"

    return {
        "name": name,
        "nodes": node_count,
        "edges": edge_count,
        "validation_time_ms": val_time_ms,
        "topological_sort_time_ms": topo_time_ms,
        "peak_memory": peak_mem,
        "result": result_status,
    }


def run_all_benchmarks():
    print("=" * 95)
    print("JARVIS OS — FASE 13.1 LARGE GRAPH SCALABILITY BENCHMARK")
    print("=" * 95)

    scales = [100, 500, 900, 1000, 2000, 5000, 10000]
    results = []

    # 1. Linear Chains
    print("\n[BENCHMARK 1] Linear Chain (Normal Insertion)")
    for n in scales:
        nodes = [
            TaskNode(task_id=f"c_{i}", title=f"Chain {i}", dependencies=[f"c_{i-1}"] if i > 0 else [])
            for i in range(n)
        ]
        res = benchmark_graph(f"Linear Chain {n}", nodes)
        results.append(res)
        print(f"  Nodes: {res['nodes']:<6} | Edges: {res['edges']:<6} | Val: {res['validation_time_ms']:6.2f} ms | Topo: {res['topological_sort_time_ms']:6.2f} ms | Mem: {format_mem(res['peak_memory']):<9} | {res['result']}")

    # 2. Reverse Insertion Linear Chains (The Previous Failure Mode)
    print("\n[BENCHMARK 2] Reverse Insertion Linear Chain (Previous Failure Mode)")
    for n in scales:
        nodes = [
            TaskNode(task_id=f"r_{i}", title=f"Rev {i}", dependencies=[f"r_{i-1}"] if i > 0 else [])
            for i in reversed(range(n))
        ]
        res = benchmark_graph(f"Reverse Chain {n}", nodes)
        results.append(res)
        print(f"  Nodes: {res['nodes']:<6} | Edges: {res['edges']:<6} | Val: {res['validation_time_ms']:6.2f} ms | Topo: {res['topological_sort_time_ms']:6.2f} ms | Mem: {format_mem(res['peak_memory']):<9} | {res['result']}")

    # 3. Branching DAG (Binary Tree Fan-Out + Fan-In)
    print("\n[BENCHMARK 3] Branching Tree DAG (Binary Fan-out)")
    for n in [100, 500, 1000, 2000, 5000, 10000]:
        nodes = [TaskNode(task_id="b_0", title="Root")]
        for i in range(1, n):
            parent = f"b_{(i - 1) // 2}"
            nodes.append(TaskNode(task_id=f"b_{i}", title=f"B {i}", dependencies=[parent]))
        res = benchmark_graph(f"Branching Tree {n}", nodes)
        results.append(res)
        print(f"  Nodes: {res['nodes']:<6} | Edges: {res['edges']:<6} | Val: {res['validation_time_ms']:6.2f} ms | Topo: {res['topological_sort_time_ms']:6.2f} ms | Mem: {format_mem(res['peak_memory']):<9} | {res['result']}")

    # 4. Wide DAG (Single Root, N-2 Parallel Workers, Single Sink)
    print("\n[BENCHMARK 4] Wide Parallel DAG (1 Root -> N-2 Parallel -> 1 Sink)")
    for n in [100, 500, 1000, 2000, 5000, 10000]:
        nodes = [TaskNode(task_id="w_root", title="Root")]
        workers = [f"w_{i}" for i in range(1, n - 1)]
        for w in workers:
            nodes.append(TaskNode(task_id=w, title=w, dependencies=["w_root"]))
        nodes.append(TaskNode(task_id="w_sink", title="Sink", dependencies=workers))
        res = benchmark_graph(f"Wide DAG {n}", nodes)
        results.append(res)
        print(f"  Nodes: {res['nodes']:<6} | Edges: {res['edges']:<6} | Val: {res['validation_time_ms']:6.2f} ms | Topo: {res['topological_sort_time_ms']:6.2f} ms | Mem: {format_mem(res['peak_memory']):<9} | {res['result']}")

    # 5. Dense Multi-Layer DAG
    print("\n[BENCHMARK 5] Dense Multi-Layer DAG (Layer-by-Layer Interconnections)")
    for n in [100, 500, 1000, 2000, 5000]:
        layers = 10
        layer_size = n // layers
        nodes = []
        for l in range(layers):
            for idx in range(layer_size):
                tid = f"d_L{l}_{idx}"
                deps = []
                if l > 0:
                    # connect to up to 3 nodes from preceding layer
                    deps = [f"d_L{l-1}_{(idx + k) % layer_size}" for k in range(min(3, layer_size))]
                nodes.append(TaskNode(task_id=tid, title=tid, dependencies=deps))
        res = benchmark_graph(f"Dense DAG {len(nodes)}", nodes)
        results.append(res)
        print(f"  Nodes: {res['nodes']:<6} | Edges: {res['edges']:<6} | Val: {res['validation_time_ms']:6.2f} ms | Topo: {res['topological_sort_time_ms']:6.2f} ms | Mem: {format_mem(res['peak_memory']):<9} | {res['result']}")

    # 6. Cycle Graphs
    print("\n[BENCHMARK 6] Graphs with Cycle Detection")
    for n in [100, 1000, 5000]:
        nodes = [
            TaskNode(task_id=f"cyc_{i}", title=f"C {i}", dependencies=[f"cyc_{i-1}"] if i > 0 else [])
            for i in range(n)
        ]
        # Invert root to depend on leaf (Closing a global loop)
        nodes[0].dependencies.append(f"cyc_{n-1}")
        res = benchmark_graph(f"Global Cycle {n}", nodes, expect_cycle=True)
        results.append(res)
        print(f"  Nodes: {res['nodes']:<6} | Edges: {res['edges']:<6} | Val: {res['validation_time_ms']:6.2f} ms | Topo: {res['topological_sort_time_ms']:6.2f} ms | Mem: {format_mem(res['peak_memory']):<9} | {res['result']}")

    # 7. Deep Cycle in Large Graph
    print("\n[BENCHMARK 7] Deep Cycle in 5000-Node Graph")
    nodes_deep_cyc = [
        TaskNode(task_id=f"dc_{i}", title=f"DC {i}", dependencies=[f"dc_{i-1}"] if i > 0 else [])
        for i in range(5000)
    ]
    # Local loop deep inside: 3500 -> 3501 -> 3502 -> 3500
    nodes_deep_cyc[3500].dependencies.append("dc_3502")
    res = benchmark_graph("Deep Local Cycle 5000", nodes_deep_cyc, expect_cycle=True)
    results.append(res)
    print(f"  Nodes: {res['nodes']:<6} | Edges: {res['edges']:<6} | Val: {res['validation_time_ms']:6.2f} ms | Topo: {res['topological_sort_time_ms']:6.2f} ms | Mem: {format_mem(res['peak_memory']):<9} | {res['result']}")

    print("\n" + "=" * 95)
    print("EMPIRICAL BENCHMARK SUMMARY TABLE")
    print("=" * 95)
    print(f"{'TOPOLOGY':<32} | {'NODES':<6} | {'EDGES':<6} | {'VAL (ms)':<8} | {'TOPO (ms)':<9} | {'PEAK MEM':<10} | {'RESULT'}")
    print("-" * 95)
    for r in results:
        print(f"{r['name']:<32} | {r['nodes']:<6} | {r['edges']:<6} | {r['validation_time_ms']:<8.2f} | {r['topological_sort_time_ms']:<9.2f} | {format_mem(r['peak_memory']):<10} | {r['result']}")
    print("=" * 95)


if __name__ == "__main__":
    run_all_benchmarks()
