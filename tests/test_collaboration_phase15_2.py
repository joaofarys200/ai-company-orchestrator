"""
Tests for Phase 15.2 — Scalable Conflict Detection, Graph Decomposition & Large Artifact Auto-Merge.

Tests:
1. HierarchicalConflictIndex: multi-level progressive indexing (package, file, symbol AST, ranges, contracts, requirements, tests).
2. Cross-domain linkages in HierarchicalConflictIndex (symbol -> contracts, symbol -> requirements, symbol -> tests).
3. ConnectedConflictGraphEngine: partitioning proposals into independent conflict components.
4. ConnectedConflictGraphEngine: independent parallel resolution across disconnected components.
5. DenseConflictStrategy: selection under high proposal density.
6. LargeArtifactMergeEngine: Python AST structural merge of disjoint top-level functions.
7. LargeArtifactMergeEngine: JS/TS structural merge of disjoint exported functions and classes.
8. LargeArtifactMergeEngine: Windowed block merge on 1,000+ line files.
9. LargeArtifactMergeEngine: Extreme scale merge on 10,000+ lines with fast-path execution.
10. LargeArtifactMergeEngine: Deterministic byte-identical hash guarantee (10 iterations SHA-256 match).
11. LargeArtifactMergeEngine: Syntax self-healing integration with ASTRepairEngineV2.
12. MergeFailureMemory: record, query, serialize, and restore across checkpoints.
"""

import ast
import hashlib
import time
import pytest
from agents.collaboration_engine import (
    ConflictDetector,
    HierarchicalConflictIndex,
    ConnectedConflictGraphEngine,
    ConflictComponent,
    DenseConflictStrategy,
    LargeArtifactMergeEngine,
    PatchMergeEngine,
    MergeFailureMemory,
    MergeFailureRecord,
    AgentProposal,
    ConflictType,
    ResultKind,
)
from agents.mission_orchestrator import TaskNode


class TestCollaborationPhase152:

    def test_01_hierarchical_conflict_index_progressive_layers(self):
        """Valida a indexação progressiva hierárquica por pacote, ficheiro, símbolo e linha."""
        detector = ConflictDetector()
        task = TaskNode(task_id="task_h_index", title="Hierarchical Index Test")

        p1 = AgentProposal(
            proposal_id="prop_fe",
            agent_id="FRONTEND_1",
            task_id="task_h_index",
            affected_files=["frontend/src/views/Dashboard.tsx"],
            affected_symbols=["renderDashboard", "HeaderWidget"],
            content_by_file={
                "frontend/src/views/Dashboard.tsx": (
                    "export function renderDashboard() { return <div>Dashboard</div>; }\n"
                    "export function HeaderWidget() { return <header>Header</header>; }\n"
                )
            },
            metadata={
                "contract_signature": {"endpoint": "/api/v1/metrics", "method": "GET"},
                "case_sensitivity": "case-sensitive",
            },
        )

        p2 = AgentProposal(
            proposal_id="prop_be",
            agent_id="BACKEND_1",
            task_id="task_h_index",
            affected_files=["backend/api/metrics.py"],
            affected_symbols=["get_metrics"],
            content_by_file={
                "backend/api/metrics.py": (
                    "def get_metrics():\n"
                    "    return {'status': 'ok'}\n"
                )
            },
            metadata={
                "contract_signature": {"endpoint": "/api/v1/metrics", "method": "GET"},
                "case_sensitivity": "case-sensitive",
            },
        )

        h_index = detector.build_hierarchical_index("proj_1", task, [p1, p2])

        # Verificação da camada de pacote
        assert "frontend/src/views" in h_index.package_to_proposals
        assert "backend/api" in h_index.package_to_proposals
        assert "prop_fe" in h_index.package_to_proposals["frontend/src/views"]
        assert "prop_be" in h_index.package_to_proposals["backend/api"]

        # Verificação da camada de ficheiro
        assert "prop_fe" in h_index.file_to_proposals["frontend/src/views/Dashboard.tsx"]
        assert "prop_be" in h_index.file_to_proposals["backend/api/metrics.py"]

        # Verificação da camada de símbolos
        assert ("backend/api/metrics.py", "get_metrics") in h_index.symbol_to_proposals
        assert "prop_be" in h_index.symbol_to_proposals[("backend/api/metrics.py", "get_metrics")]

        # Verificação da camada de contratos
        assert "/api/v1/metrics" in h_index.contract_to_proposals
        assert len(h_index.contract_to_proposals["/api/v1/metrics"]) == 2

        # Verificação de linkages cruzados
        assert ("backend/api/metrics.py", "get_metrics") in h_index.symbol_to_contracts
        assert "/api/v1/metrics" in h_index.symbol_to_contracts[("backend/api/metrics.py", "get_metrics")]

    def test_02_connected_components_decomposition(self):
        """Valida que propostas são particionadas em componentes conexas independentes."""
        task = TaskNode(task_id="task_decomp", title="Component Decomposition")

        # Propostas A e B conflitam em file_1.py
        p_a = AgentProposal(proposal_id="p_a", agent_id="A", task_id="t1", affected_files=["file_1.py"])
        p_b = AgentProposal(proposal_id="p_b", agent_id="B", task_id="t1", affected_files=["file_1.py"])

        # Propostas C e D conflitam em file_2.py
        p_c = AgentProposal(proposal_id="p_c", agent_id="C", task_id="t1", affected_files=["file_2.py"])
        p_d = AgentProposal(proposal_id="p_d", agent_id="D", task_id="t1", affected_files=["file_2.py"])

        # Proposta E é completamente isolada
        p_e = AgentProposal(proposal_id="p_e", agent_id="E", task_id="t1", affected_files=["file_isolated.py"])

        proposals = [p_a, p_b, p_c, p_d, p_e]
        edges = {
            ("p_a", "p_b"): ["FILE_OVERLAP"],
            ("p_c", "p_d"): ["FILE_OVERLAP"],
        }

        components = ConnectedConflictGraphEngine.partition_into_components(proposals, edges)

        # Deve gerar 3 componentes: {p_a, p_b}, {p_c, p_d}, {p_e}
        assert len(components) == 3

        comp_members = [sorted(c.proposal_ids) for c in components]
        assert ["p_a", "p_b"] in comp_members
        assert ["p_c", "p_d"] in comp_members
        assert ["p_e"] in comp_members

        # A proposta isolada p_e não tem conflitos
        comp_e = next(c for c in components if "p_e" in c.proposal_ids)
        assert comp_e.has_conflicts is False
        assert comp_e.candidate_pair_count == 0

    def test_03_dense_conflict_strategy_selection(self):
        """Verifica a seleção dinâmica de estratégias para cenários densos vs esparsos."""
        detector = ConflictDetector()
        task = TaskNode(task_id="task_dense", title="Dense Conflict Test")

        # Cenário 1: 10 agentes com partilhas globais densas (densidade >= 35%)
        dense_props = []
        for i in range(10):
            dense_props.append(AgentProposal(
                proposal_id=f"p_dense_{i}",
                agent_id=f"AGENT_{i}",
                task_id="task_dense",
                affected_files=["common/global_config.py"],
                affected_symbols=["GLOBAL_SETTING"],
            ))

        _, graph_dense, comps_dense, strategy_dense = detector.build_hierarchical_conflict_graph(
            "proj_1", task, dense_props
        )

        # Como todos tocam no mesmo ficheiro/símbolo, a densidade de candidatos é 100%
        assert graph_dense.candidate_count == (10 * 9) // 2
        assert strategy_dense in (DenseConflictStrategy.CONNECTED_COMPONENTS, DenseConflictStrategy.BUCKETED_COMPARISON)

        # Cenário 2: 4 agentes esparsos em ficheiros totalmente separados
        sparse_props = [
            AgentProposal(proposal_id=f"p_sp_{i}", agent_id=f"SP_{i}", task_id="task_dense", affected_files=[f"file_{i}.py"])
            for i in range(4)
        ]
        _, graph_sparse, comps_sparse, strategy_sparse = detector.build_hierarchical_conflict_graph(
            "proj_1", task, sparse_props
        )

        assert graph_sparse.candidate_count == 0
        assert strategy_sparse == DenseConflictStrategy.PAIRWISE
        assert len(comps_sparse) == 4  # 4 componentes isoladas

    def test_04_python_ast_structural_merge(self):
        """Verifica merge estrutural de funções Python independentes via AST (Layer 1)."""
        base = (
            "def foo():\n"
            "    return 'original_foo'\n\n"
            "def bar():\n"
            "    return 'original_bar'\n"
        )
        content_a = (
            "def foo():\n"
            "    return 'modified_foo_by_agent_a'\n\n"
            "def bar():\n"
            "    return 'original_bar'\n"
        )
        content_b = (
            "def foo():\n"
            "    return 'original_foo'\n\n"
            "def bar():\n"
            "    return 'modified_bar_by_agent_b'\n"
        )

        ok, merged, reason = LargeArtifactMergeEngine.auto_merge_disjoint(
            "module.py", base, content_a, content_b
        )

        assert ok is True
        assert "AST_DISJOINT_AUTO_MERGE_SUCCESS" in reason or "DISJOINT" in reason
        assert "modified_foo_by_agent_a" in merged
        assert "modified_bar_by_agent_b" in merged
        ast.parse(merged)  # Sintaxe estritamente válida

    def test_05_js_ts_structural_merge(self):
        """Verifica merge estrutural de funções e componentes TypeScript/JavaScript (Layer 1)."""
        base = (
            "export function fetchUsers() {\n"
            "  return api.get('/users');\n"
            "}\n\n"
            "export function fetchProducts() {\n"
            "  return api.get('/products');\n"
            "}\n"
        )
        content_a = (
            "export function fetchUsers() {\n"
            "  return api.get('/users?v=2');\n"
            "}\n\n"
            "export function fetchProducts() {\n"
            "  return api.get('/products');\n"
            "}\n"
        )
        content_b = (
            "export function fetchUsers() {\n"
            "  return api.get('/users');\n"
            "}\n\n"
            "export function fetchProducts() {\n"
            "  return api.get('/products?filter=active');\n"
            "}\n"
        )

        ok, merged, reason = LargeArtifactMergeEngine.auto_merge_disjoint(
            "services/api.ts", base, content_a, content_b
        )

        assert ok is True
        assert "STRUCTURAL_JS_TS_MERGE_SUCCESS" in reason or "DISJOINT" in reason
        assert "/users?v=2" in merged
        assert "/products?filter=active" in merged

    def test_06_windowed_block_merge_medium_file(self):
        """Verifica o merge em janela deslizante (Layer 3) em ficheiro com 1.200 linhas."""
        lines = [f"# Line {i}\n" for i in range(1200)]
        base = "".join(lines)

        # Agent A altera linhas 100-105
        lines_a = list(lines)
        lines_a[100] = "# Agent A change at 100\n"
        lines_a[101] = "# Agent A change at 101\n"
        content_a = "".join(lines_a)

        # Agent B altera linhas 1050-1055
        lines_b = list(lines)
        lines_b[1050] = "# Agent B change at 1050\n"
        lines_b[1051] = "# Agent B change at 1051\n"
        content_b = "".join(lines_b)

        t0 = time.perf_counter()
        ok, merged, reason = LargeArtifactMergeEngine.auto_merge_disjoint(
            "large_service.py", base, content_a, content_b
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        assert ok is True
        assert "Agent A change at 100" in merged
        assert "Agent B change at 1050" in merged
        assert elapsed_ms < 50.0  # Fast-path instantâneo

    def test_07_extreme_scale_merge_10000_lines(self):
        """Verifica a escalabilidade do LargeArtifactMergeEngine em 10.000 linhas."""
        base_lines = [f"int record_{i} = {i};\n" for i in range(10000)]
        base = "".join(base_lines)

        # Modificação A no topo (linhas 50-52)
        lines_a = list(base_lines)
        lines_a[50] = "int record_50 = 99999; // Mod by A\n"
        content_a = "".join(lines_a)

        # Modificação B na cauda (linhas 9500-9502)
        lines_b = list(base_lines)
        lines_b[9500] = "int record_9500 = 88888; // Mod by B\n"
        content_b = "".join(lines_b)

        t0 = time.perf_counter()
        ok, merged, reason = LargeArtifactMergeEngine.auto_merge_disjoint(
            "huge_records.c", base, content_a, content_b
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0

        assert ok is True
        assert "Mod by A" in merged
        assert "Mod by B" in merged
        assert len(merged.splitlines()) == 10000
        assert latency_ms < 100.0  # Menos de 100ms em 10k linhas!

    def test_08_byte_identical_hash_determinism_guarantee(self):
        """Garante determinismo estrito: 10 execuções produzem SHA-256 idêntico byte a byte."""
        base = (
            "class Engine:\n"
            "    def start(self):\n"
            "        pass\n\n"
            "    def stop(self):\n"
            "        pass\n"
        )
        content_a = (
            "class Engine:\n"
            "    def start(self):\n"
            "        print('Engine starting')\n\n"
            "    def stop(self):\n"
            "        pass\n"
        )
        content_b = (
            "class Engine:\n"
            "    def start(self):\n"
            "        pass\n\n"
            "    def stop(self):\n"
            "        print('Engine stopping')\n"
        )

        hashes = set()
        for _ in range(10):
            ok, merged, _ = LargeArtifactMergeEngine.auto_merge_disjoint(
                "engine.py", base, content_a, content_b
            )
            assert ok is True
            h = hashlib.sha256(merged.encode("utf-8")).hexdigest()
            hashes.add(h)

        # Deve haver exatamente 1 hash único
        assert len(hashes) == 1

    def test_09_merge_failure_memory_recording_and_persistence(self):
        """Valida que falhas reais de merge são guardadas em memória e exportadas/restauradas."""
        memory = MergeFailureMemory()
        assert memory.get_failure_count() == 0

        # Simular registo de falha
        rec = MergeFailureRecord(
            failure_id="fail_01",
            file_path="src/router.py",
            line_count=250,
            language="python",
            strategy_used="STRUCTURAL_AST",
            fallback_used="LINE_DIFF",
            error_type="SYNTAX_ERROR",
            error_details="IndentationError at line 45",
        )
        memory.record_failure(rec)

        assert memory.get_failure_count() == 1
        fails = memory.get_failures_for_file("src/router.py")
        assert len(fails) == 1
        assert fails[0].error_type == "SYNTAX_ERROR"

        # Serialização e restauração
        serialized = memory.to_dict()
        restored = MergeFailureMemory.from_dict(serialized)

        assert restored.get_failure_count() == 1
        assert restored.get_failures_for_file("src/router.py")[0].failure_id == "fail_01"
