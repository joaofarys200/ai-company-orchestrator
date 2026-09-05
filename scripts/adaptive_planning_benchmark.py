"""Empirical Benchmarking Script for Fase 13 Adaptive Planning."""

import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.adaptive_planning import (
    AdaptationBudget,
    AdaptationTrigger,
    AdaptivePlanningEngine,
    AdaptivePlanningValidator,
    MissionAdaptationProposal,
    PlanEvaluationDecision,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def run_benchmarks():
    print("=" * 70)
    print("EMPIRICAL BENCHMARKS — FASE 13 ADAPTIVE PLANNING & GRAPH INTELLIGENCE")
    print("=" * 70)

    # 1. Strategy Fingerprint Throughput
    prop = MissionAdaptationProposal(
        proposal_id="prop_bench",
        mission_id="m_bench",
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Benchmark strategy fingerprinting throughput",
        added_tasks=[
            {"task_id": f"t_{i}", "title": f"Bench Task {i}", "category": "CODING"}
            for i in range(10)
        ],
        changed_edges=[(f"t_{i}", f"t_{i+1}") for i in range(9)],
    )

    iterations = 5000
    start = time.perf_counter()
    for _ in range(iterations):
        _ = prop.compute_strategy_fingerprint()
    elapsed = time.perf_counter() - start
    fps_per_sec = iterations / elapsed
    print(f"1. Strategy Fingerprint Throughput: {fps_per_sec:,.0f} hashes/sec ({elapsed/iterations*1e6:.2f} µs/op)")

    # 2. Proposal Validation Latency on 50-node DAG
    validator = AdaptivePlanningValidator(budget=AdaptationBudget(max_graph_churn=50))
    nodes_50 = [
        TaskNode(task_id=f"node_{i}", title=f"Node {i}", dependencies=[f"node_{i-1}"] if i > 0 else [], status=TaskStatus.READY)
        for i in range(50)
    ]
    graph_50 = TaskGraph(nodes=nodes_50, graph_version=1)

    prop_val = MissionAdaptationProposal(
        proposal_id="prop_val",
        mission_id="m_val",
        base_graph_version=1,
        decision=PlanEvaluationDecision.ADAPT_PLAN,
        trigger=AdaptationTrigger.NEW_REQUIREMENT,
        reason="Inserção de 5 novas tarefas com dependências intermediárias.",
        added_tasks=[
            {"task_id": f"new_node_{i}", "title": f"New Node {i}", "dependencies": ["node_10"]}
            for i in range(5)
        ],
        changed_edges=[(f"new_node_{i}", "node_11") for i in range(5)],
    )

    val_iters = 500
    start = time.perf_counter()
    for _ in range(val_iters):
        ok, _, _ = validator.validate(prop_val, graph_50)
        assert ok is True
    val_elapsed = time.perf_counter() - start
    avg_val_ms = (val_elapsed / val_iters) * 1000
    print(f"2. Proposal Validation & Trial DAG Latency (50 nodes + 5 added): {avg_val_ms:.3f} ms/op")

    # 3. Replan DAG Rewiring Latency on 100-node DAG
    nodes_100 = [
        TaskNode(task_id=f"node_{i}", title=f"Node {i}", dependencies=[f"node_{i-1}"] if i > 0 else [], status=TaskStatus.COMPLETED if i < 30 else TaskStatus.READY)
        for i in range(100)
    ]
    graph_100 = TaskGraph(nodes=nodes_100, graph_version=1)

    # Replan purges incomplete nodes 30..99 and replaces with 20 new nodes
    prop_replan = MissionAdaptationProposal(
        proposal_id="prop_replan_scale",
        mission_id="m_replan",
        base_graph_version=1,
        decision=PlanEvaluationDecision.REPLAN,
        trigger=AdaptationTrigger.ARCHITECTURE_DISCOVERY,
        reason="Purga massiva de nós incompletos e substituição estrutural de estratégia.",
        removed_tasks=[f"node_{i}" for i in range(30, 100)],
        added_tasks=[
            {"task_id": f"replan_node_{i}", "title": f"Replan Node {i}", "dependencies": ["node_29" if i == 0 else f"replan_node_{i-1}"]}
            for i in range(20)
        ],
    )

    replan_validator = AdaptivePlanningValidator(budget=AdaptationBudget(max_graph_churn=200))
    replan_iters = 200
    start = time.perf_counter()
    for _ in range(replan_iters):
        ok, _, _ = replan_validator.validate(prop_replan, graph_100)
        assert ok is True
    replan_elapsed = time.perf_counter() - start
    avg_replan_ms = (replan_elapsed / replan_iters) * 1000
    print(f"3. Mass Replan Validation & Rewiring (100 nodes, 70 removed, 20 added): {avg_replan_ms:.3f} ms/op")

    # 4. Stress Scaling & FIRST_REAL_LIMIT Identification
    print("\n--> 4. Stress Scaling: Identificação do FIRST_REAL_LIMIT...")
    scale_limits = [200, 500, 800, 950, 1000, 1200]
    limit_reached = None
    for size in scale_limits:
        t0 = time.perf_counter()
        # Invert insertion order so DFS traverses the entire chain depth on the first call
        large_nodes = [
            TaskNode(task_id=f"n_{i}", title=f"Scale Node {i}", dependencies=[f"n_{i-1}"] if i > 0 else [])
            for i in reversed(range(size))
        ]
        try:
            large_graph = TaskGraph(nodes=large_nodes)
            large_prop = MissionAdaptationProposal(
                proposal_id="prop_scale",
                mission_id="m_scale",
                base_graph_version=1,
                decision=PlanEvaluationDecision.ADAPT_PLAN,
                trigger=AdaptationTrigger.NEW_REQUIREMENT,
                reason="Scale test proposal for limit discovery",
                added_tasks=[{"task_id": "probe_node", "title": "Probe Node", "dependencies": [f"n_{size-1}"]}]
            )
            v = AdaptivePlanningValidator(budget=AdaptationBudget(max_graph_churn=size+10))
            ok, msg, _ = v.validate(large_prop, large_graph)
            dt = (time.perf_counter() - t0) * 1000
            print(f"    Reverse Linear Chain Depth: {size:4d} nodes | Trial Build & Cycle DFS: {dt:6.2f} ms | Valid: {ok}")
            if not ok:
                limit_reached = f"Validation rejected: {msg}"
                break
        except RecursionError:
            limit_reached = f"RecursionError: Python recursive call stack limit exceeded (1000 frames) at reverse linear chain depth >= {size} nodes"
            print(f"    Reverse Linear Chain Depth: {size:4d} nodes | FAILED with RecursionError (Python call stack limit exceeded)")
            break
        except Exception as ex:
            limit_reached = f"{type(ex).__name__}: {ex}"
            break

    print(f"\n[OK] FIRST_REAL_LIMIT Identified: {limit_reached}")


if __name__ == "__main__":
    run_benchmarks()
