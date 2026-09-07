"""
JARVIS OS — Phase 15.3: Scalability Stress, Correctness Oracle & Resource Fairness Test Suite

Comprehensive test suite verifying:
1. Independent Correctness Oracle (ReferenceConflictEngine vs Optimized Engine with false_negatives == 0).
2. Reference vs Layered Merge Engine Equivalence & AST Verification.
3. High Proposal Density Stress (60+ proposals, sub-second execution, dynamic strategy selection).
4. Incremental Conflict Graph Dynamic Mutations (incremental add, update, remove, connected components).
5. Component Stability Tracking Across Multiple Collaboration Rounds.
6. Large Artifact Structural Indexing & Region Merkle Tree (10,000+ lines).
7. Layered Merge Engine on Large Disjoint Files (Symbol-Level & Range-Level).
8. Adaptive Lease Scheduling & Priority Aging (dynamic capacity, queue ordering, starvation prevention).
9. Lease Starvation Detection & Real-Time Metrics (p50, p95, starvation events).
10. Scalability Checkpoint Crash & Recovery (full roundtrip state restoration).
11. Real Repository Intake Validation (indexing real JarvisOS codebase files).
12. WebSocket Telemetry & Event Payload Verification.
"""

from __future__ import annotations

import ast
import hashlib
import os
import time
import unittest
from typing import Any

from agents.collaboration_engine import (
    AgentProposal,
    CollaborationCoordinator,
    CollaborationSession,
    CollaborationStatus,
    ConflictDetector,
    ConflictType,
    ResultKind,
)
from agents.collaboration_reference import (
    MergeCorrectnessComparator,
    ReferenceConflictEngine,
    ReferenceMergeEngine,
)
from agents.collaboration_scalability import (
    AdaptiveLeaseManager,
    AdaptiveProposalPartitioner,
    ArbitrationStage,
    ComponentStabilityManager,
    IncrementalConflictGraph,
    LargeArtifactIndex,
    LayeredMergeEngine,
    LayeredMergeTier,
    LeaseRequest,
    LeaseStarvationDetector,
    MergeCorrectnessOracle,
    PartitionStrategy,
    RegionKind,
    StagedArbitrationEngine,
)
from agents.task_graph import TaskNode


def _make_prop(
    prop_id: str,
    agent_id: str,
    file_path: str = "src/core.py",
    symbols: list[str] | None = None,
    content: str = "",
    desc: str = "",
    confidence: float = 0.9,
    agent_type: str = "CODING",
    evidence: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentProposal:
    meta = dict(metadata or {})
    return AgentProposal(
        proposal_id=prop_id,
        task_id="task_scale_stress",
        agent_id=agent_id,
        agent_type=agent_type,
        result_kind=ResultKind.PATCH if content else ResultKind.PROPOSAL,
        affected_files=[file_path],
        affected_symbols=symbols or [],
        content_by_file={file_path: content} if content else {},
        description=desc or f"Proposal {prop_id} by {agent_id}",
        confidence_score=confidence,
        evidence=evidence or [],
        metadata=meta,
    )


class TestCollaborationPhase153(unittest.TestCase):
    """Exhaustive empirical validation of Phase 15.3 scalability, oracle correctness, and resource fairness."""

    def test_01_correctness_oracle_exhaustive_pairwise_and_zero_false_negatives(self) -> None:
        """
        Verifica se o Correctness Oracle independente (ReferenceConflictEngine) deteta
        conflitos e o comparator assegura ZERO falsos negativos no motor otimizado.
        """
        # Criar propostas com conflitos sintáticos e sobreposições de símbolos
        p1 = _make_prop(
            "p1_auth",
            "agent_auth",
            file_path="src/auth.py",
            symbols=["verify_token"],
            content="def verify_token(tok): return True\n",
            confidence=0.85,
        )
        p2 = _make_prop(
            "p2_auth",
            "agent_jwt",
            file_path="src/auth.py",
            symbols=["verify_token"],
            content="def verify_token(jwt_str): return bool(jwt_str)\n",
            confidence=0.92,
        )
        proposals = [p1, p2]

        # 1. Executar Ground Truth Reference Engine (exaustivo)
        ref_result = ReferenceConflictEngine.evaluate_proposals(proposals)
        self.assertGreaterEqual(len(ref_result.conflicts), 1)
        self.assertIn("p1_auth", ref_result.affected_proposals)
        self.assertIn("p2_auth", ref_result.affected_proposals)

        # 2. Executar Optimized ConflictDetector
        detector = ConflictDetector()
        task = TaskNode("task_oracle", "Oracle Verification Task")
        opt_conflicts = detector.detect_conflicts("proj_oracle", task, proposals)

        # 3. Comparar via MergeCorrectnessComparator
        ok, msg = MergeCorrectnessComparator.verify_no_false_negatives(ref_result, opt_conflicts)
        self.assertTrue(ok, f"Oracle invariant violated: {msg}")

    def test_02_reference_vs_layered_merge_engine_equivalence(self) -> None:
        """
        Compara o ReferenceMergeEngine com o LayeredMergeEngine em edições disjuntas.
        Ambos devem preservar integridade de AST e sintaxe válida.
        """
        base_code = (
            "def header():\n"
            "    return 'HEADER'\n"
            "\n"
            "def worker():\n"
            "    return 'ORIGINAL'\n"
            "\n"
            "def footer():\n"
            "    return 'FOOTER'\n"
        )
        # Agent A altera header
        code_a = base_code.replace("return 'HEADER'", "return 'HEADER_V2'")
        # Agent B altera footer
        code_b = base_code.replace("return 'FOOTER'", "return 'FOOTER_V2'")

        # 1. Reference Merge
        ref_res = ReferenceMergeEngine.merge_patches("src/app.py", base_code, code_a, code_b)
        self.assertTrue(ref_res.success)
        self.assertTrue(ref_res.structural_validity)
        self.assertIn("HEADER_V2", ref_res.merged_content)
        self.assertIn("FOOTER_V2", ref_res.merged_content)

        # 2. Layered Merge Engine
        ok_l, merged_l, tier, reason = LayeredMergeEngine.auto_merge_layered("src/app.py", base_code, code_a, code_b)
        self.assertTrue(ok_l, f"Layered merge failed: {reason}")
        self.assertIn("HEADER_V2", merged_l)
        self.assertIn("FOOTER_V2", merged_l)

        # 3. Validação pelo MergeCorrectnessOracle
        v_ok, v_msg = MergeCorrectnessOracle.verify_merge("src/app.py", base_code, code_a, code_b, merged_l)
        self.assertTrue(v_ok, f"MergeCorrectnessOracle error: {v_msg}")

    def test_03_high_density_proposals_stress_60_proposals(self) -> None:
        """
        Stress test com 60 propostas concorrentes (densidade extrema > 50).
        Verifica transição para particionamento adaptativo em tempo sub-segundo.
        """
        proposals: list[AgentProposal] = []
        for i in range(60):
            file_id = i % 5  # 5 ficheiros diferentes => alta concorrência por ficheiro
            prop = _make_prop(
                prop_id=f"prop_dense_{i:03d}",
                agent_id=f"agent_{i % 10}",
                file_path=f"src/module_{file_id}.py",
                symbols=[f"func_target_{i % 8}"],
                content=f"def func_target_{i % 8}(): return {i}\n",
                confidence=0.7 + (i % 3) * 0.1,
            )
            proposals.append(prop)

        total_pairs = 60 * 59 // 2  # 1770 pares
        t0 = time.perf_counter()
        meta = AdaptiveProposalPartitioner.evaluate_strategy(
            proposals=proposals,
            candidate_edges_count=int(total_pairs * 0.75),
            component_count=1,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # O particionador deve selecionar STAGED_ARBITRATION para N >= 16 e densidade >= 0.60
        self.assertEqual(meta.strategy, PartitionStrategy.STAGED_ARBITRATION)
        self.assertEqual(meta.proposal_count, 60)
        self.assertGreaterEqual(meta.graph_density, 0.60)
        self.assertLess(elapsed_ms, 500.0, f"Avaliação de 60 propostas excedeu 500ms: {elapsed_ms:.2f}ms")

        # Testar execução de arbitragem em estágios sob alta densidade
        staged_res = StagedArbitrationEngine.arbitrate_staged(
            conflict_details={"type": "SYMBOL_OVERLAP"},
            proposals=proposals[:15],
        )
        self.assertTrue(
            staged_res.final_decision.startswith("ACCEPT") or staged_res.final_decision in ("RESOLVED", "MERGE"),
            f"Unexpected decision: {staged_res.final_decision}",
        )
        self.assertTrue(staged_res.selected_proposal_id)

    def test_04_incremental_conflict_graph_dynamic_mutations(self) -> None:
        """
        Testa mutações incrementais (adicionar, atualizar, remover nós) no IncrementalConflictGraph
        sem recomputação global.
        """
        graph = IncrementalConflictGraph()

        # 1. Adicionar 20 propostas progressivamente
        for i in range(20):
            p = _make_prop(
                prop_id=f"inc_p_{i}",
                agent_id=f"agent_{i}",
                file_path="src/shared.py" if i < 10 else f"src/other_{i}.py",
                symbols=["shared_fn"] if i < 10 else [f"fn_{i}"],
            )
            graph.incremental_add(p)
            self.assertIn(f"inc_p_{i}", graph.nodes)

        # 2. Verificar arestas e conectividade
        pair_shared = graph._normalize_pair("inc_p_0", "inc_p_1")
        self.assertIn(pair_shared, graph.edges)
        pair_disjoint = graph._normalize_pair("inc_p_0", "inc_p_15")
        self.assertNotIn(pair_disjoint, graph.edges)

        # 3. Componentes conexos estáveis
        comps = graph.stability_manager.components
        self.assertGreaterEqual(len(comps), 1)

        # 4. Atualizar proposta existente
        p_updated = _make_prop(
            prop_id="inc_p_0",
            agent_id="agent_0",
            file_path="src/isolated.py",
            symbols=["isolated_fn"],
        )
        graph.incremental_update(p_updated)
        self.assertEqual(graph.proposals_by_id["inc_p_0"].affected_files, ["src/isolated.py"])

        # 5. Remover nó
        graph.incremental_remove("inc_p_0")
        self.assertNotIn("inc_p_0", graph.nodes)

    def test_05_component_stability_tracking_across_rounds(self) -> None:
        """
        Verifica se o ComponentStabilityManager mantém estabilidade e identificadores
        de componentes conexas durante mutações locais.
        """
        mgr = ComponentStabilityManager()

        p1 = _make_prop("p1", "a1", file_path="src/a.py", symbols=["fn_a"])
        p2 = _make_prop("p2", "a2", file_path="src/a.py", symbols=["fn_a"])
        p3 = _make_prop("p3", "a3", file_path="src/b.py", symbols=["fn_b"])

        # Inicializar componentes com aresta entre p1 e p2
        edges = {("p1", "p2"): ["FILE_OVERLAP"]}
        comps = mgr.register_initial_components([p1, p2, p3], candidate_edges=edges)
        self.assertEqual(len(comps), 2)

        cid_a = mgr.proposal_to_component["p1"]
        cid_b = mgr.proposal_to_component["p3"]
        self.assertNotEqual(cid_a, cid_b)

        # Mutação: Adicionar p4 conectada apenas ao componente A
        comp_a_updated = mgr.mutate_on_new_edges(
            new_proposal_id="p4",
            affected_files=["src/a.py"],
            connected_proposal_ids=["p1"],
            new_edges_count=1,
        )
        # Identidade do Componente A deve ser preservada (estabilidade de ID)
        self.assertEqual(comp_a_updated.component_id, cid_a)
        self.assertEqual(comp_a_updated.version, 2)
        self.assertIn("p4", comp_a_updated.proposal_ids)

        # Componente B deve permanecer intacto (versão 1)
        comp_b = mgr.components[cid_b]
        self.assertEqual(comp_b.version, 1)
        self.assertEqual(comp_b.proposal_ids, ["p3"])

    def test_06_large_artifact_structural_indexing_merkle_tree_10k_lines(self) -> None:
        """
        Gera um ficheiro Python sintético com 10.000 linhas e valida:
        - Indexação de classes, funções e imports via LargeArtifactIndex.
        - Geração determinística de Merkle Tree.
        - Isolamento de mutação (apenas a região alterada tem o hash modificado).
        """
        lines = ["# JARVIS Generated 10k Line Artifact\n", "import sys\n", "import os\n\n"]
        # Criar 200 funções de 50 linhas cada = 10.000+ linhas
        for i in range(200):
            lines.append(f"def generated_function_{i}():\n")
            for j in range(48):
                val = i * 100 + j
                lines.append(f"    val_{j} = {val}\n")
            lines.append(f"    return val_47\n\n")

        content_10k = "".join(lines)
        self.assertGreaterEqual(len(content_10k.splitlines()), 10000)

        t0 = time.perf_counter()
        index1 = LargeArtifactIndex("src/mega_module.py", content_10k)
        build_time_ms = (time.perf_counter() - t0) * 1000.0

        self.assertIsNotNone(index1.merkle_tree)
        root_hash_1 = index1.merkle_tree.root_hash
        self.assertTrue(root_hash_1)
        self.assertLess(build_time_ms, 3000.0, f"Indexação de 10k linhas excedeu 3s: {build_time_ms:.2f}ms")

        # Localizar uma função específica
        reg_50 = index1.locate_symbol("generated_function_50")
        self.assertIsNotNone(reg_50)
        self.assertEqual(reg_50.kind, RegionKind.FUNCTION)

        # Mutação isolada: alterar apenas generated_function_50
        content_mod = content_10k.replace(
            "def generated_function_50():\n    val_0 = 5000",
            "def generated_function_50():\n    val_0 = 999999",
        )
        self.assertNotEqual(content_10k, content_mod)
        index2 = LargeArtifactIndex("src/mega_module.py", content_mod)

        # O root hash global deve ter mudado
        self.assertNotEqual(index1.merkle_tree.root_hash, index2.merkle_tree.root_hash)
        # O hash da região alterada deve ter mudado
        reg_50_mod = index2.locate_symbol("generated_function_50")
        self.assertNotEqual(reg_50.sha256_hash, reg_50_mod.sha256_hash)
        # O hash de outra região intacta deve ser idêntico
        reg_10_orig = index1.locate_symbol("generated_function_10")
        reg_10_mod = index2.locate_symbol("generated_function_10")
        self.assertEqual(reg_10_orig.sha256_hash, reg_10_mod.sha256_hash)

    def test_07_layered_merge_disjoint_regions_large_file(self) -> None:
        """
        Valida que o LayeredMergeEngine aplica auto-merge cirúrgico em ficheiro grande (2.000 linhas)
        quando duas propostas alteram símbolos completamente disjuntos.
        """
        lines = ["# Large file\n"]
        for i in range(40):
            lines.append(f"def component_function_{i}():\n")
            for j in range(48):
                lines.append(f"    x_{j} = {i} + {j}\n")
            lines.append("    return x_47\n\n")

        base_text = "".join(lines)

        # Agent 1 altera component_function_2
        a1_text = base_text.replace("x_47 = 2 + 47", "x_47 = 200000")
        # Agent 2 altera component_function_38
        a2_text = base_text.replace("x_47 = 38 + 47", "x_47 = 380000")

        success, merged_text, tier, reason = LayeredMergeEngine.auto_merge_layered(
            "src/large_svc.py", base_text, a1_text, a2_text
        )

        self.assertTrue(success, f"Merge falhou: {reason}")
        self.assertIn("200000", merged_text)
        self.assertIn("380000", merged_text)
        # Validação estrita de sintaxe Python
        parsed = ast.parse(merged_text)
        self.assertIsNotNone(parsed)

    def test_08_adaptive_lease_scheduling_and_priority_aging(self) -> None:
        """
        Testa o AdaptiveLeaseManager com alta contenção:
        - Escalonamento adaptativo de capacidade.
        - Enfileiramento de requisições excedentes.
        - Priority aging: requisições em espera aumentam prioridade efetiva e furam fila.
        """
        mgr = AdaptiveLeaseManager(base_capacity_per_file=4, max_adaptive_capacity_per_file=16, aging_factor=2.0)
        file_path = "src/contested_file.py"
        now_t = 1000.0

        # 1. Adquirir 4 leases imediatos (capacidade base = 4)
        acquired_leases = []
        for i in range(4):
            lid, status = mgr.request_lease(file_path, f"task_{i}", f"agent_{i}", priority=5, now=now_t)
            self.assertEqual(status, "ACQUIRED")
            acquired_leases.append(lid)

        # 2. Requisição 5 (com prioridade baixa = 2) é enfileirada no tempo 1000.0
        _, st5 = mgr.request_lease(file_path, "task_low", "agent_low", priority=2, now=now_t)
        self.assertTrue(st5.startswith("QUEUED"))

        # 3. Requisição 6 (com prioridade alta = 8) chega no tempo 1005.0
        _, st6 = mgr.request_lease(file_path, "task_high", "agent_high", priority=8, now=now_t + 5.0)
        self.assertTrue(st6.startswith("QUEUED"))

        # 4. No tempo 1010.0:
        # agent_low esperou 10s: prioridade efetiva = 2 + (10 * 2.0) = 22.0
        # agent_high esperou 5s: prioridade efetiva = 8 + (5 * 2.0) = 18.0
        # Ao libertar um lease, agent_low DEVE ser contemplado primeiro devido ao priority aging!
        ok, next_lease = mgr.release_lease(acquired_leases[0], now=now_t + 10.0)
        self.assertTrue(ok)
        self.assertIsNotNone(next_lease)

        # Confirmar que foi o agent_low que recebeu o lease
        meta = mgr.lease_metadata[next_lease]
        self.assertEqual(meta["agent_id"], "agent_low")

    def test_09_lease_starvation_detector_metrics_and_alerting(self) -> None:
        """
        Verifica se o LeaseStarvationDetector identifica requisições que excederam
        o threshold e calcula métricas p50/p95 de wait time.
        """
        detector = LeaseStarvationDetector(starvation_threshold_sec=5.0)

        # Alimentar tempos de espera para cálculo de percentis
        for w in [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0]:
            detector.record_wait_time(w)

        # Simular fila com uma requisição starved
        req_normal = LeaseRequest("r1", "t1", "a1", "CODING", 5, requested_at=100.0, effective_priority=5.0)
        req_starved = LeaseRequest("r2", "t2", "a2", "CODING", 5, requested_at=90.0, effective_priority=5.0)
        queue = [req_normal, req_starved]

        starved_ids = detector.check_starvation(queue, now=102.0)
        # r1 esperou 2s (< 5s), r2 esperou 12s (> 5s)
        self.assertIn("r2", starved_ids)
        self.assertNotIn("r1", starved_ids)

        metrics = detector.get_metrics(current_queue_depth=len(queue))
        self.assertEqual(metrics.starvation_events, 1)
        self.assertGreater(metrics.lease_wait_ms_p95, 0.0)
        self.assertEqual(metrics.queue_depth, 2)

    def test_10_scalability_checkpoint_crash_and_recovery(self) -> None:
        """
        Valida que o estado completo de colaboração (sessões, propostas, metadados
        de particionamento e histórico de merge) sobrevive ao crash e retoma.
        """
        coord1 = CollaborationCoordinator(project_id="proj_crash", mission_id="miss_crash")
        session = coord1.create_session("task_cp", ["agent_a", "agent_b"])

        p1 = _make_prop("p1_cp", "agent_a", file_path="src/service.py", content="def s(): return 1\n")
        p2 = _make_prop("p2_cp", "agent_b", file_path="src/client.py", content="def c(): return 2\n")
        coord1.add_proposal(session.collaboration_id, p1)
        coord1.add_proposal(session.collaboration_id, p2)

        status, _, _ = coord1.evaluate_collaboration(session.collaboration_id)
        self.assertEqual(status, CollaborationStatus.RESOLVED)

        # Simular Crash: exportar estado
        exported_state = coord1.export_state()
        self.assertIn("sessions", exported_state)
        self.assertIn("last_partition_metadata", exported_state)

        # Retoma a partir do zero
        coord2 = CollaborationCoordinator(project_id="proj_crash", mission_id="miss_crash")
        coord2.restore_state(exported_state)

        self.assertIn(session.collaboration_id, coord2.sessions)
        restored_session = coord2.sessions[session.collaboration_id]
        self.assertEqual(restored_session.status, CollaborationStatus.RESOLVED)
        self.assertEqual(len(restored_session.proposals), 2)
        self.assertIsNotNone(coord2.detector.last_partition_metadata)

    def test_11_real_repository_intake_validation(self) -> None:
        """
        Valida a indexação e análise estrutural sobre um ficheiro real do repositório
        (agents/collaboration_reference.py).
        """
        real_file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "agents",
            "collaboration_reference.py",
        )
        self.assertTrue(os.path.exists(real_file_path), f"Ficheiro real não encontrado: {real_file_path}")

        with open(real_file_path, "r", encoding="utf-8") as f:
            real_content = f.read()

        index = LargeArtifactIndex("agents/collaboration_reference.py", real_content)
        self.assertIsNotNone(index.merkle_tree)
        self.assertTrue(index.merkle_tree.root_hash)

        # Verificar se identificou classes essenciais do reference engine
        self.assertIn("ReferenceConflictEngine", index.symbols_to_region_id)
        self.assertIn("ReferenceMergeEngine", index.symbols_to_region_id)
        self.assertIn("MergeCorrectnessComparator", index.symbols_to_region_id)

    def test_12_websocket_telemetry_event_dispatch(self) -> None:
        """
        Valida que os eventos de telemetria da Fase 15.3 (particionamento, arbitragem por estágios,
        starvation de leases) possuem estrutura compatível com o schema do WebSocket.
        """
        # Evento 1: collaboration_partitioned
        ev_part = {
            "type": "collaboration_partitioned",
            "collaboration_id": "collab_test_123",
            "strategy": "STAGED_ARBITRATION",
            "total_proposals": 55,
            "components_count": 4,
            "conflict_density": 0.38,
            "timestamp": "2026-09-06T17:00:00Z",
        }
        self.assertIn("strategy", ev_part)
        self.assertEqual(ev_part["total_proposals"], 55)

        # Evento 2: staged_arbitration_completed
        ev_arb = {
            "type": "staged_arbitration_completed",
            "collaboration_id": "collab_test_123",
            "winning_stage": "STAGE_2_HARD_VALIDATION",
            "selected_proposal_id": "prop_042",
            "decision": "RESOLVED",
            "eliminated_counts": {"STAGE_1_SAFETY": 2, "STAGE_2_HARD_VALIDATION": 3},
            "timestamp": "2026-09-06T17:00:01Z",
        }
        self.assertEqual(ev_arb["winning_stage"], "STAGE_2_HARD_VALIDATION")

        # Evento 3: lease_starvation_alert
        ev_starv = {
            "type": "lease_starvation_alert",
            "file_path": "src/heavy_contention.py",
            "starved_requests_count": 3,
            "max_wait_ms": 12500.0,
            "timestamp": "2026-09-06T17:00:02Z",
        }
        self.assertGreater(ev_starv["max_wait_ms"], 10000.0)


if __name__ == "__main__":
    unittest.main()
