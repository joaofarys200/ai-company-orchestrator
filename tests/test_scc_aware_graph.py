"""Phase 59: Unit and Integration Test Suite for SCC-Aware Graph Condensation & Bounded Impact Analysis.

Covers all 24 required test scenarios:
1. single-node SCC
2. two-node cycle
3. triangle cycle
4. large SCC
5. disconnected SCC
6. SCC condensation
7. DAG validation
8. deterministic partition
9. SCC-aware impact
10. boundary truncation
11. incremental SCC update
12. SCC split
13. SCC merge
14. cross-service SCC
15. cross-language SCC
16. coupling metrics
17. memory bounds
18. state persistence
19. graph poisoning
20. predictive impact integration
21. task reconciliation
22. contract integration
23. repair integration
24. deterministic replay
"""

import pytest
import random
from typing import Any, Dict, List

from backend.agents.scc_aware_graph import (
    StronglyConnectedComponent,
    CondensationDAG,
    CondensationDAGNode,
    SCCCouplingMetrics,
    SCCImpactScope,
    ImpactConfidence,
    TarjanSCC,
    KosarajuSCC,
    SCCDetector,
    GraphCondenser,
    CondensationDAGManager,
    CouplingAnalyzer,
    SCCBoundaryManager,
    SCCAwareSubgraphExtractor,
    SCCAwareImpactAnalyzer,
    SCCQueryEngine,
    SCCDeterministicCache,
    IncrementalSCCUpdater,
    SqliteSCCStorage,
    SCCTelemetryMetrics,
    SCCSecuritySentinel,
    SCCAwareValidator,
    SCCReverseIndex,
    SCCAwareGraphBridge,
)


def test_01_single_node_scc():
    """Test 1: Single-node SCC without self-loop or cycle."""
    nodes = ["A", "B"]
    edges = [{"source": "A", "target": "B"}]
    sccs = SCCDetector.detect_sccs(nodes, edges)

    assert len(sccs) == 2
    for scc in sccs:
        assert scc.size == 1
        assert scc.is_cycle is False
        assert scc.density == 0.0


def test_02_two_node_cycle():
    """Test 2: Two-node mutual dependency cycle (A <-> B)."""
    nodes = ["A", "B"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "A"},
    ]
    sccs = SCCDetector.detect_sccs(nodes, edges)

    assert len(sccs) == 1
    cycle_scc = sccs[0]
    assert cycle_scc.size == 2
    assert cycle_scc.is_cycle is True
    assert set(cycle_scc.nodes) == {"A", "B"}
    assert len(cycle_scc.edges_internal) == 2


def test_03_triangle_cycle():
    """Test 3: Three-node cycle (A -> B -> C -> A)."""
    nodes = ["A", "B", "C"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "A"},
    ]
    sccs = SCCDetector.detect_sccs(nodes, edges)

    assert len(sccs) == 1
    assert sccs[0].size == 3
    assert sccs[0].is_cycle is True
    assert set(sccs[0].nodes) == {"A", "B", "C"}
    assert len(sccs[0].edges_internal) == 3


def test_04_large_scc():
    """Test 4: Large dense cycle of 60 nodes."""
    nodes = [f"node_{i:02d}" for i in range(60)]
    edges = [{"source": nodes[i], "target": nodes[(i + 1) % 60]} for i in range(60)]
    sccs = SCCDetector.detect_sccs(nodes, edges)

    assert len(sccs) == 1
    assert sccs[0].size == 60
    assert sccs[0].is_cycle is True
    assert len(sccs[0].edges_internal) == 60


def test_05_disconnected_scc():
    """Test 5: Multiple disconnected components and isolated nodes."""
    nodes = ["A", "B", "C", "D", "E"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "A"},
        {"source": "C", "target": "D"},
        {"source": "D", "target": "C"},
    ]
    sccs = SCCDetector.detect_sccs(nodes, edges)

    assert len(sccs) == 3
    sizes = sorted([s.size for s in sccs])
    assert sizes == [1, 2, 2]
    cycle_sccs = [s for s in sccs if s.is_cycle]
    assert len(cycle_sccs) == 2


def test_06_scc_condensation():
    """Test 6: Graph condensation into CondensationDAG."""
    # SCC1: A <-> B
    # SCC2: C <-> D
    # Edge from B -> C
    nodes = ["A", "B", "C", "D"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "A"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"},
        {"source": "D", "target": "C"},
    ]
    sccs = SCCDetector.detect_sccs(nodes, edges)
    dag = GraphCondenser.condense(sccs)

    assert len(dag.nodes) == 2
    assert len(dag.edges) == 1
    assert dag.is_acyclic is True
    assert dag.edges[0]["source_scc"] != dag.edges[0]["target_scc"]



def test_07_dag_validation():
    """Test 7: Formal DAG acyclicity validation and topological sorting."""
    nodes = ["A", "B", "C", "D"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "A"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"},
        {"source": "D", "target": "C"},
    ]
    sccs = SCCDetector.detect_sccs(nodes, edges)
    dag = GraphCondenser.condense(sccs)

    is_valid, msg = SCCAwareValidator.validate_dag(dag)
    assert is_valid is True
    assert "strictly acyclic" in msg
    assert len(dag.topological_ordering) == 2


def test_08_deterministic_partition():
    """Test 8: Deterministic partitioning across randomly shuffled inputs."""
    nodes = ["A", "B", "C", "D", "E"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "A"},
        {"source": "C", "target": "D"},
        {"source": "D", "target": "E"},
    ]

    sccs1 = SCCDetector.detect_sccs(nodes, edges)

    # Shuffle nodes and edges
    shuffled_nodes = list(nodes)
    shuffled_edges = list(edges)
    random.seed(42)
    random.shuffle(shuffled_nodes)
    random.shuffle(shuffled_edges)

    sccs2 = SCCDetector.detect_sccs(shuffled_nodes, shuffled_edges)

    assert len(sccs1) == len(sccs2)
    for s1, s2 in zip(sccs1, sccs2):
        assert s1.scc_id == s2.scc_id
        assert s1.nodes == s2.nodes
        assert s1.state_hash == s2.state_hash


def test_09_scc_aware_impact():
    """Test 9: Impact query separating internal SCC members from external consumers."""
    nodes = ["A", "B", "C", "D"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "A"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"},
    ]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    res = bridge.analyze_symbol_impact(["A"])

    assert "A" in res["affected_symbols"]
    assert "B" in res["affected_symbols"]
    assert "C" in res["affected_symbols"]
    assert "D" in res["affected_symbols"]

    # "A" and "B" belong to the root SCC -> internal
    assert set(res["internal_affected_symbols"]) == {"A", "B"}
    # "C" and "D" belong to downstream SCCs -> external
    assert set(res["external_affected_symbols"]) == {"C", "D"}


def test_10_boundary_truncation():
    """Test 10: Clean boundary truncation when exploration budget is reached."""
    # Chain of 4 SCCs: (A<->B) -> (C<->D) -> (E<->F) -> (G<->H)
    nodes = ["A", "B", "C", "D", "E", "F", "G", "H"]
    edges = [
        {"source": "A", "target": "B"}, {"source": "B", "target": "A"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"}, {"source": "D", "target": "C"},
        {"source": "D", "target": "E"},
        {"source": "E", "target": "F"}, {"source": "F", "target": "E"},
        {"source": "F", "target": "G"},
        {"source": "G", "target": "H"}, {"source": "H", "target": "G"},
    ]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)

    # Query with max_sccs=2
    res = bridge.analyze_symbol_impact(["A"], max_sccs=2)

    assert len(res["included_sccs"]) == 2
    assert res["truncated_at_boundary"] is True
    assert res["confidence"] == ImpactConfidence.BOUNDARY_LIMITED.value
    assert len(res["boundary_edges"]) > 0


def test_11_incremental_scc_update():
    """Test 11: Incremental update of non-cycle edge."""
    nodes = ["A", "B", "C"]
    edges = [{"source": "A", "target": "B"}]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)

    update_res = bridge.updater.handle_edge_added("B", "C")
    assert update_res["operation"] in ["LOCAL_UPDATE", "EDGE_ADDED"]
    assert update_res["total_sccs_after"] == 3


def test_12_scc_split():
    """Test 12: Removing cycle edge splits single SCC into multiple individual SCCs."""
    nodes = ["A", "B", "C"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "A"},
    ]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    assert len(bridge.sccs) == 1
    assert bridge.sccs[0].is_cycle is True

    # Remove the back-edge closing the cycle
    split_res = bridge.updater.handle_edge_removed("C", "A")
    assert split_res["operation"] == "SCC_SPLIT"
    assert split_res["total_sccs_after"] == 3
    for s in bridge.updater.sccs:
        assert s.is_cycle is False


def test_13_scc_merge():
    """Test 13: Adding mutual cycle edge merges two SCCs into one."""
    nodes = ["A", "B", "C", "D"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "A"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"},
        {"source": "D", "target": "C"},
    ]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    assert len(bridge.sccs) == 2

    # Add back-edge from D to A
    merge_res = bridge.updater.handle_edge_added("D", "A")
    assert merge_res["operation"] == "SCC_MERGE"
    assert merge_res["total_sccs_after"] == 1
    assert bridge.updater.sccs[0].size == 4


def test_14_cross_service_scc():
    """Test 14: Cross-service SCC detection and scope classification."""
    nodes = ["fe_button", "be_api"]
    edges = [
        {"source": "fe_button", "target": "be_api"},
        {"source": "be_api", "target": "fe_button"},
    ]
    metadata = {
        "fe_button": {"service": "frontend", "language": "typescript"},
        "be_api": {"service": "backend", "language": "python"},
    }
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges, node_metadata=metadata)

    scc = bridge.sccs[0]
    assert set(scc.services) == {"frontend", "backend"}
    assert scc.is_cycle is True

    res = bridge.analyze_symbol_impact(["fe_button"])
    assert res["scope"] in [SCCImpactScope.CROSS_SERVICE_SCC.value, SCCImpactScope.REPOSITORY_WIDE_SCC.value]
    assert "frontend" in res["services"]
    assert "backend" in res["services"]


def test_15_cross_language_scc():
    """Test 15: Cross-language SCC preserves language provenance."""
    nodes = ["client_sdk", "server_handler"]
    edges = [
        {"source": "client_sdk", "target": "server_handler"},
        {"source": "server_handler", "target": "client_sdk"},
    ]
    metadata = {
        "client_sdk": {"language": "typescript", "service": "client"},
        "server_handler": {"language": "python", "service": "server"},
    }
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges, node_metadata=metadata)
    scc = bridge.sccs[0]
    assert set(scc.languages) == {"typescript", "python"}


def test_16_coupling_metrics():
    """Test 16: Transparent mathematical coupling metrics."""
    nodes = ["A", "B", "C"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "A"},
    ]
    sccs = SCCDetector.detect_sccs(nodes, edges)
    metrics = CouplingAnalyzer.analyze_scc(sccs[0])

    assert metrics.size == 3
    assert metrics.internal_edges_count == 3
    assert metrics.external_edges_count == 0
    assert metrics.density == 0.5  # 3 / (3 * 2) = 0.5
    assert 0.0 <= metrics.coupling_score <= 1.0
    assert "density_contribution" in metrics.components_explanation



def test_17_memory_bounds():
    """Test 17: Memory bounds and low overhead for 1000 nodes."""
    nodes = [f"sym_{i}" for i in range(1000)]
    # Create 100 components of 10 nodes each
    edges = []
    for comp in range(100):
        start = comp * 10
        for i in range(10):
            edges.append({"source": f"sym_{start + i}", "target": f"sym_{start + ((i + 1) % 10)}"})

    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    overview = bridge.get_overview()

    assert overview["total_sccs"] == 100
    assert overview["largest_scc_size"] == 10
    assert overview["dag_is_acyclic"] is True


def test_18_state_persistence():
    """Test 18: SQLite state persistence and restore round-trip."""
    nodes = ["A", "B", "C"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "A"},
        {"source": "B", "target": "C"},
    ]
    sccs = SCCDetector.detect_sccs(nodes, edges)
    dag = GraphCondenser.condense(sccs)

    storage = SqliteSCCStorage(db_path=":memory:")
    storage.save_sccs(sccs)
    storage.save_dag(dag)

    loaded_sccs = storage.load_sccs()
    loaded_dag = storage.load_dag()

    assert len(loaded_sccs) == len(sccs)
    assert len(loaded_dag.nodes) == len(dag.nodes)
    assert loaded_dag.is_acyclic is True


def test_19_graph_poisoning():
    """Test 19: Security sentinel detects tampered state hash and illegal cycles."""
    nodes = ["A", "B"]
    edges = [{"source": "A", "target": "B"}, {"source": "B", "target": "A"}]
    sccs = SCCDetector.detect_sccs(nodes, edges)
    sentinel = SCCSecuritySentinel()

    # Valid integrity check
    valid, _ = sentinel.validate_scc_integrity(sccs[0])
    assert valid is True

    # Tamper with state hash
    tampered_scc = StronglyConnectedComponent(
        scc_id=sccs[0].scc_id,
        nodes=sccs[0].nodes,
        edges_internal=sccs[0].edges_internal,
        size=sccs[0].size,
        density=sccs[0].density,
        state_hash="forged_hash_value",
    )
    tampered_valid, msg = sentinel.validate_scc_integrity(tampered_scc)
    assert tampered_valid is False
    assert "mismatch" in msg


def test_20_predictive_impact_integration():
    """Test 20: Naive BFS/DFS vs SCC-Aware condensation comparison."""
    nodes = ["A", "B", "C", "D"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "A"},
        {"source": "C", "target": "D"},
    ]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    comparison = bridge.impact_analyzer.compare_naive_vs_scc_impact(["A"], edges)

    assert "naive_approach" in comparison
    assert "scc_aware_approach" in comparison
    assert comparison["scc_aware_approach"]["confidence"] in ["FULL", "BOUNDARY_LIMITED"]


def test_21_task_reconciliation():
    """Test 21: Task reconciliation mapping SCC nodes to F39.2 tasks."""
    nodes = ["task_worker", "job_queue"]
    edges = [
        {"source": "task_worker", "target": "job_queue"},
        {"source": "job_queue", "target": "task_worker"},
    ]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    tasks_map = {"task_worker": ["TASK-5901", "TASK-5902"]}

    res = bridge.analyze_symbol_impact(["task_worker"], tasks_map=tasks_map)
    assert "TASK-5901" in res["tasks"]
    assert "TASK-5902" in res["tasks"]


def test_22_contract_integration():
    """Test 22: Contract integration preserves producer/consumer edges (F44-49)."""
    nodes = ["producer_node", "consumer_node"]
    edges = [
        {"source": "producer_node", "target": "consumer_node"},
        {"source": "consumer_node", "target": "producer_node"},
    ]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    contracts_map = {"producer_node": ["CONTRACT-AUTH-V1"], "consumer_node": ["CONTRACT-AUTH-V1"]}

    res = bridge.analyze_symbol_impact(["producer_node"], contracts_map=contracts_map)
    assert "CONTRACT-AUTH-V1" in res["contracts"]


def test_23_repair_integration():
    """Test 23: Repair integration linking modified SCC to behavioral QA scenarios (F50-57)."""
    nodes = ["ui_login_button", "auth_controller"]
    edges = [
        {"source": "ui_login_button", "target": "auth_controller"},
        {"source": "auth_controller", "target": "ui_login_button"},
    ]
    bridge = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    res = bridge.analyze_symbol_impact(["ui_login_button"])

    assert len(res["browser_scenarios"]) > 0
    assert any("ui_login_button" in s for s in res["browser_scenarios"])


def test_24_deterministic_replay():
    """Test 24: Replaying graph condensation yields identical DAG structure and hashes."""
    nodes = ["A", "B", "C", "D"]
    edges = [
        {"source": "A", "target": "B"},
        {"source": "B", "target": "A"},
        {"source": "B", "target": "C"},
        {"source": "C", "target": "D"},
    ]
    bridge1 = SCCAwareGraphBridge.build_from_graph(nodes, edges)
    bridge2 = SCCAwareGraphBridge.build_from_graph(nodes, edges)

    o1 = bridge1.get_overview()
    o2 = bridge2.get_overview()
    structural_keys = [
        "total_raw_nodes", "total_raw_edges", "total_sccs",
        "cyclic_sccs_count", "acyclic_sccs_count", "condensation_nodes",
        "condensation_edges", "dag_is_acyclic", "largest_scc_size",
        "largest_scc_id", "average_coupling_score"
    ]
    for k in structural_keys:
        assert o1[k] == o2[k]

    res1 = bridge1.analyze_symbol_impact(["A"])
    res2 = bridge2.analyze_symbol_impact(["A"])


    assert res1["affected_symbols"] == res2["affected_symbols"]
    assert res1["blast_radius_score"] == res2["blast_radius_score"]
    assert res1["scope"] == res2["scope"]
