from __future__ import annotations

import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from typing import Dict

from backend.agents.symbol_fine_grained_graph.bridge import SymbolFineGrainedGraphBridge
from backend.agents.symbol_fine_grained_graph.cache import SymbolGraphCache
from backend.agents.symbol_fine_grained_graph.condensation import SymbolGraphCondenser
from backend.agents.symbol_fine_grained_graph.edges import SymbolEdgeBuilder
from backend.agents.symbol_fine_grained_graph.extractor import MultiLanguageSymbolExtractor
from backend.agents.symbol_fine_grained_graph.graph import SymbolDependencyGraph
from backend.agents.symbol_fine_grained_graph.impact import SymbolAwareImpactAnalyzer
from backend.agents.symbol_fine_grained_graph.invalidation import IncrementalSymbolUpdater
from backend.agents.symbol_fine_grained_graph.models import (
    BarrelClassification,
    ImpactConfidence,
    SymbolEdgeType,
    SymbolImpactScope,
    SymbolKind,
    SymbolNode,
)
from backend.agents.symbol_fine_grained_graph.reexports import BarrelAnalyzer
from backend.agents.symbol_fine_grained_graph.scc import SymbolSCCDetector
from backend.agents.symbol_fine_grained_graph.security import SymbolSecuritySentinel
from backend.agents.symbol_fine_grained_graph.storage import SymbolSQLiteStorage
from backend.agents.symbol_fine_grained_graph.symbols import SymbolManager


@pytest.fixture(autouse=True)
def reset_bridge():
    SymbolFineGrainedGraphBridge.reset_instance()
    yield
    SymbolFineGrainedGraphBridge.reset_instance()


def test_01_symbol_extraction():
    extractor = MultiLanguageSymbolExtractor()
    code = "def calculate_total(a: int, b: int) -> int:\n    return a + b\n"
    symbols, edges = extractor.extract_file("service/calc.py", code)
    assert any(s.name == "calculate_total" and s.kind == SymbolKind.FUNCTION for s in symbols)


def test_02_qualified_names():
    extractor = MultiLanguageSymbolExtractor()
    code = """
class OrderProcessor:
    def process_order(self, order_id: str) -> bool:
        return True
"""
    symbols, edges = extractor.extract_file("orders/processor.py", code)
    sym_map = {s.name: s for s in symbols}
    assert "OrderProcessor" in sym_map
    assert sym_map["OrderProcessor"].qualified_name == "OrderProcessor"
    assert "process_order" in sym_map
    assert sym_map["process_order"].qualified_name == "OrderProcessor.process_order"


def test_03_typescript_import():
    extractor = MultiLanguageSymbolExtractor()
    ts_code = "import { TaskRunner } from './runner';\n"
    symbols, edges = extractor.extract_file("tasks/index.ts", ts_code)
    import_sym = next(s for s in symbols if s.name == "TaskRunner")
    assert import_sym.imported is True
    assert any(e.edge_type == SymbolEdgeType.IMPORTS for e in edges)


def test_04_typescript_reexport():
    extractor = MultiLanguageSymbolExtractor()
    ts_code = "export { WorkerPool, WorkerConfig } from './pool';\n"
    symbols, edges = extractor.extract_file("workers/index.ts", ts_code)
    reexports = [e for e in edges if e.edge_type == SymbolEdgeType.REEXPORTS]
    assert len(reexports) == 2
    assert any("WorkerPool" in e.source_symbol for e in reexports)


def test_05_python_import():
    extractor = MultiLanguageSymbolExtractor()
    py_code = "from agents.core import AgentManager, Config\nimport os\n"
    symbols, edges = extractor.extract_file("agents/runner.py", py_code)
    names = {s.name for s in symbols}
    assert "AgentManager" in names
    assert "Config" in names
    assert any(e.edge_type == SymbolEdgeType.IMPORTS and "AgentManager" in e.target_symbol for e in edges)


def test_06_python_reexport():
    extractor = MultiLanguageSymbolExtractor()
    py_code = """
from .service import ServiceA, ServiceB
__all__ = ["ServiceA", "ServiceB"]
"""
    symbols, edges = extractor.extract_file("services/__init__.py", py_code)
    all_sym = next((s for s in symbols if s.name == "__all__"), None)
    assert all_sym is not None
    assert any(e.edge_type == SymbolEdgeType.REEXPORTS for e in edges)


def test_07_commonjs_require():
    extractor = MultiLanguageSymbolExtractor()
    js_code = "const { parse, stringify } = require('json-parser');\nconst logger = require('./logger');\n"
    symbols, edges = extractor.extract_file("lib/utils.js", js_code)
    names = {s.name for s in symbols}
    assert "parse" in names
    assert "stringify" in names
    assert "logger" in names
    assert any(e.edge_type == SymbolEdgeType.IMPORTS for e in edges)


def test_08_esm_export():
    extractor = MultiLanguageSymbolExtractor()
    js_code = "export function transform(x) { return x * 2; }\nexport const PI = 3.14159;\n"
    symbols, edges = extractor.extract_file("lib/math.js", js_code)
    trans = next(s for s in symbols if s.name == "transform")
    assert trans.exported is True
    pi = next(s for s in symbols if s.name == "PI")
    assert pi.exported is True


def test_09_aliases():
    extractor = MultiLanguageSymbolExtractor()
    py_code = "from utils.helper import compute_hash as get_hash\n"
    symbols, edges = extractor.extract_file("main.py", py_code)
    alias_sym = next(s for s in symbols if s.name == "get_hash")
    assert alias_sym.provenance.get("alias") is True
    assert alias_sym.provenance.get("original_name") == "compute_hash"


def test_10_type_only_dependency():
    extractor = MultiLanguageSymbolExtractor()
    ts_code = "import type { UserProfile } from './types';\n"
    symbols, edges = extractor.extract_file("user.ts", ts_code)
    type_edges = [e for e in edges if e.edge_type == SymbolEdgeType.TYPE_USES]
    assert len(type_edges) >= 1
    assert "UserProfile" in type_edges[0].target_symbol


def test_11_value_dependency():
    extractor = MultiLanguageSymbolExtractor()
    ts_code = "import { executePlan } from './planner';\n"
    symbols, edges = extractor.extract_file("workflow.ts", ts_code)
    val_edges = [e for e in edges if e.edge_type == SymbolEdgeType.IMPORTS]
    assert len(val_edges) >= 1


def test_12_calls_edge():
    builder = SymbolEdgeBuilder()
    edge = builder.build_calls_edge("service/a.py::caller", "service/b.py::callee")
    assert edge.edge_type == SymbolEdgeType.CALLS
    assert edge.source_symbol == "service/a.py::caller"
    assert edge.target_symbol == "service/b.py::callee"


def test_13_type_uses_edge():
    builder = SymbolEdgeBuilder()
    edge = builder.build_type_uses_edge("dto.ts::OrderDTO", "types.ts::BaseSchema")
    assert edge.edge_type == SymbolEdgeType.TYPE_USES
    assert edge.confidence == 1.0


def test_14_reexports_edge():
    builder = SymbolEdgeBuilder()
    edge = builder.build_reexports_edge("index.ts::API", "core.ts::RealAPI")
    assert edge.edge_type == SymbolEdgeType.REEXPORTS


def test_15_barrel_analysis():
    analyzer = BarrelAnalyzer()
    mgr = SymbolManager()
    sym_a = mgr.build_symbol("agents/__init__.py", "RunnerA", "RunnerA", SymbolKind.EXPORT, exported=True)
    sym_b = mgr.build_symbol("agents/__init__.py", "RunnerB", "RunnerB", SymbolKind.EXPORT, exported=True)
    builder = SymbolEdgeBuilder()
    edges = [
        builder.build_reexports_edge(sym_a.symbol_id, "agents/runner_a.py::RunnerA"),
        builder.build_reexports_edge(sym_b.symbol_id, "agents/runner_b.py::RunnerB"),
    ]
    target_counts = {"agents/runner_a.py": 15, "agents/runner_b.py": 20}
    res = analyzer.analyze_barrel("agents/__init__.py", [sym_a, sym_b], edges, target_counts)
    assert res.classification in (BarrelClassification.OVER_APPROXIMATED, BarrelClassification.EXACT)
    assert len(res.reexported_symbols) == 2
    assert "agents/runner_a.py::RunnerA" in res.resolution_map.values()


def test_16_file_vs_symbol_comparison():
    files = {
        "agents/__init__.py": "from .agent import Agent\n__all__ = ['Agent']\n",
        "agents/agent.py": "class Agent:\n    def run(self): pass\n",
        "agents/unused.py": "class Unused:\n    def idle(self): pass\n",
        "main.py": "from agents.agent import Agent\ndef start():\n    a = Agent()\n",
    }
    bridge = SymbolFineGrainedGraphBridge.get_instance()
    bridge.build_from_files(files)
    res = bridge.query_symbol_impact("main.py::start")
    comp = res["comparison"]
    assert "precision_gain" in comp
    assert "overapproximation_reduction" in comp
    assert comp["symbol_impact_count"] <= comp["file_impact_count"]


def test_17_symbol_scc():
    # Build cyclic symbols: SymA -> SymB -> SymC -> SymA
    graph = SymbolDependencyGraph()
    mgr = SymbolManager()
    s_a = mgr.build_symbol("cycle.py", "A", "A", SymbolKind.FUNCTION)
    s_b = mgr.build_symbol("cycle.py", "B", "B", SymbolKind.FUNCTION)
    s_c = mgr.build_symbol("cycle.py", "C", "C", SymbolKind.FUNCTION)
    for s in (s_a, s_b, s_c):
        graph.add_node(s)

    builder = SymbolEdgeBuilder()
    graph.add_edge(builder.build_calls_edge(s_a.symbol_id, s_b.symbol_id))
    graph.add_edge(builder.build_calls_edge(s_b.symbol_id, s_c.symbol_id))
    graph.add_edge(builder.build_calls_edge(s_c.symbol_id, s_a.symbol_id))

    detector = SymbolSCCDetector()
    sccs = detector.detect_sccs(graph)
    cyclic_scc = next(s for s in sccs if s.size == 3)
    assert cyclic_scc.is_cycle is True
    assert set(cyclic_scc.symbols) == {s_a.symbol_id, s_b.symbol_id, s_c.symbol_id}


def test_18_scc_split():
    # Break cycle: remove edge C -> A, expecting SCC size 3 to split into 3 SCCs of size 1
    graph = SymbolDependencyGraph()
    mgr = SymbolManager()
    s_a = mgr.build_symbol("cycle.py", "A", "A", SymbolKind.FUNCTION)
    s_b = mgr.build_symbol("cycle.py", "B", "B", SymbolKind.FUNCTION)
    s_c = mgr.build_symbol("cycle.py", "C", "C", SymbolKind.FUNCTION)
    for s in (s_a, s_b, s_c):
        graph.add_node(s)

    builder = SymbolEdgeBuilder()
    graph.add_edge(builder.build_calls_edge(s_a.symbol_id, s_b.symbol_id))
    graph.add_edge(builder.build_calls_edge(s_b.symbol_id, s_c.symbol_id))
    graph.add_edge(builder.build_calls_edge(s_c.symbol_id, s_a.symbol_id))

    detector = SymbolSCCDetector()
    old_sccs = detector.detect_sccs(graph)
    assert len(old_sccs) == 1

    updater = IncrementalSymbolUpdater(detector)
    new_sccs, new_dag, lineage = updater.handle_edge_removed(s_c.symbol_id, s_a.symbol_id, graph, old_sccs, revision=2)
    assert lineage["transition_type"] == "SCC_SPLIT"
    assert len(new_sccs) == 3


def test_19_scc_merge():
    # Merge two separate nodes into a cycle: add edge B -> A
    graph = SymbolDependencyGraph()
    mgr = SymbolManager()
    s_a = mgr.build_symbol("m.py", "A", "A", SymbolKind.FUNCTION)
    s_b = mgr.build_symbol("m.py", "B", "B", SymbolKind.FUNCTION)
    graph.add_node(s_a)
    graph.add_node(s_b)

    builder = SymbolEdgeBuilder()
    graph.add_edge(builder.build_calls_edge(s_a.symbol_id, s_b.symbol_id))

    detector = SymbolSCCDetector()
    old_sccs = detector.detect_sccs(graph)
    assert len(old_sccs) == 2

    updater = IncrementalSymbolUpdater(detector)
    merge_edge = builder.build_calls_edge(s_b.symbol_id, s_a.symbol_id)
    new_sccs, new_dag, lineage = updater.handle_edge_added(merge_edge, graph, old_sccs, revision=3)
    assert lineage["transition_type"] == "SCC_MERGE"
    assert len(new_sccs) == 1
    assert new_sccs[0].size == 2


def test_20_targeted_impact():
    files = {
        "core/base.py": "class BaseConfig:\n    pass\n",
        "core/app.py": "from core.base import BaseConfig\nclass App(BaseConfig):\n    pass\n",
        "entry.py": "from core.app import App\ndef main():\n    return App()\n",
    }
    bridge = SymbolFineGrainedGraphBridge.get_instance()
    bridge.build_from_files(files)
    res = bridge.query_symbol_impact("core/base.py::BaseConfig")
    impact = res["impact"]
    assert impact["scope"] in (
        SymbolImpactScope.MODULE.value,
        SymbolImpactScope.FILE_LOCAL.value,
        SymbolImpactScope.SERVICE.value,
        SymbolImpactScope.MODULE,
        SymbolImpactScope.FILE_LOCAL,
        SymbolImpactScope.SERVICE,
    )


def test_21_incremental_update():
    files = {
        "pkg/a.py": "def foo(): pass\n",
    }
    bridge = SymbolFineGrainedGraphBridge.get_instance()
    bridge.build_from_files(files)
    assert bridge.get_status()["symbol_count"] >= 1

    # Add a new symbol incrementally
    mgr = SymbolManager()
    new_sym = mgr.build_symbol("pkg/a.py", "bar", "bar", SymbolKind.FUNCTION)
    new_sccs, new_dag, lineage = bridge.updater.handle_symbol_added(
        new_sym, [], bridge.graph, bridge.sccs, revision=4
    )
    bridge.sccs = new_sccs
    bridge.dag = new_dag
    assert bridge.get_status()["symbol_count"] >= 2


def test_22_storage():
    db_path = ":memory:"
    storage = SymbolSQLiteStorage(db_path)
    mgr = SymbolManager()
    node = mgr.build_symbol("test.py", "TestClass", "TestClass", SymbolKind.CLASS, exported=True)
    graph = SymbolDependencyGraph()
    graph.add_node(node)
    detector = SymbolSCCDetector()
    sccs = detector.detect_sccs(graph)
    condenser = SymbolGraphCondenser()
    dag = condenser.condense(graph, sccs)

    storage.save_graph(graph, sccs, dag, revision=1)
    loaded = storage.load_symbol(node.symbol_id)
    assert loaded is not None
    assert loaded.name == "TestClass"
    assert loaded.kind == SymbolKind.CLASS
    storage.close()


def test_23_cache():
    cache = SymbolGraphCache(max_entries=100)
    key = cache.make_key(repo_rev="rev123", file_hash="abc", symbol_hash="def")
    cache.put(key, {"cached": True, "file_id": "test.py"})
    val = cache.get(key)
    assert val is not None
    assert val["cached"] is True
    assert cache.hits == 1

    # Invalidation
    removed = cache.invalidate_file("test.py")
    assert removed == 1
    assert cache.get(key) is None


def test_24_security_poisoning():
    sentinel = SymbolSecuritySentinel()
    mgr = SymbolManager()

    # 1. Path traversal attempt
    poisoned_sym = mgr.build_symbol("../../etc/passwd", "evil", "evil", SymbolKind.FUNCTION)
    assert sentinel.validate_symbol_node(poisoned_sym) is False

    # 2. Dangerous script injection
    xss_sym = mgr.build_symbol("lib/safe.py", "<script>alert(1)</script>", "<script>", SymbolKind.VARIABLE)
    assert sentinel.validate_symbol_node(xss_sym) is False

    # 3. Forged confidence
    builder = SymbolEdgeBuilder()
    bad_edge = builder.build_edge("a::foo", "b::bar", SymbolEdgeType.CALLS, confidence=999.0)
    assert sentinel.validate_symbol_edge(bad_edge) is False


def test_25_deterministic_replay():
    # Build graph twice from identical inputs and verify state hashes are byte-for-byte identical
    files = {
        "mod_a.py": "from mod_b import func_b\ndef func_a():\n    return func_b()\n",
        "mod_b.py": "from mod_a import func_a\ndef func_b():\n    return func_a()\n",
    }
    bridge1 = SymbolFineGrainedGraphBridge.get_instance(db_path=":memory:")
    stat1 = bridge1.build_from_files(files)
    hash1 = [s.state_hash for s in bridge1.sccs]

    SymbolFineGrainedGraphBridge.reset_instance()
    bridge2 = SymbolFineGrainedGraphBridge.get_instance(db_path=":memory:")
    stat2 = bridge2.build_from_files(files)
    hash2 = [s.state_hash for s in bridge2.sccs]

    assert stat1["scc_count"] == stat2["scc_count"]
    assert hash1 == hash2
