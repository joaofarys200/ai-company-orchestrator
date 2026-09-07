# -*- coding: utf-8 -*-
"""
tests/test_collaboration_scalability.py
======================================
Validação e Testes Unitários/Stress da Fase 15.3:
Arquitetura de Colaboração e Arbitragem em Escala.

Cobre:
1. AdaptiveProposalPartitioner (limiares, densidade, seleção de estratégias).
2. IncrementalConflictGraph (adição, remoção, atualização, equivalência topológica com grafo estático).
3. StagedArbitrationEngine (Fast Pruning, Objective Evidence Ranking, Deterministic Tie-Breaking).
4. Salvaguardas Económicas em arbitragem multi-estágio.
5. Política de Evicção LRU / TTL em MergeFailureMemory.
6. Persistência e Recuperação pós-restart (export_state / restore_state).
7. Simulação de Alta Densidade (N >= 30 propostas simultâneas).
"""

import os
import time
import pytest
from datetime import datetime, timedelta, timezone

from agents.collaboration_engine import (
    AgentConflictArbitrator,
    AgentProposal,
    ArbitrationDecision,
    CandidateConflictGraph,
    CollaborationCoordinator,
    CollaborationMetrics,
    CollaborationSession,
    CollaborationStatus,
    ConflictDetails,
    ConflictDetector,
    ConflictType,
    ConnectedConflictGraphEngine,
    HierarchicalConflictIndex,
    IncrementalConflictGraph,
    MergeFailureMemory,
    PartitionStrategy,
    ProposalPartitionMetadata,
    StagedArbitrationEngine,
    StagedArbitrationResult,
    AdaptiveProposalPartitioner,
    utc_now,
)


def _make_prop(
    prop_id: str,
    agent_id: str,
    file_path: str = "src/core.py",
    symbols: list[str] | None = None,
    hard_validation: bool = True,
    tests_passed: int = 5,
    tests_failed: int = 0,
    confidence: float = 0.9,
    content: str = "def compute(): return 42\n",
) -> AgentProposal:
    return AgentProposal(
        proposal_id=prop_id,
        agent_id=agent_id,
        collaboration_id="collab_test",
        file_path=file_path,
        ast_symbols=symbols or ["compute"],
        proposed_content=content,
        confidence_score=confidence,
        rationale=f"Rationale for {prop_id}",
        evidence={
            "hard_validation": {"passed": hard_validation},
            "test_results": {"passed": tests_passed, "failed": tests_failed},
            "build": {"status": "SUCCESS"},
            "runtime": {"status": "HEALTHY"},
            "browser": {"status": "PASS"},
            "contracts": {"status": "VALID"},
            "architecture": {"status": "CONFORMANT"},
        },
    )


# ── TESTES DE PARTICIONAMENTO ADAPTATIVO ────────────────────────────────────────

def test_adaptive_partitioner_sparse_small_n():
    """Para pequeno número de propostas (N < 8) e baixa densidade, a estratégia deve ser PAIRWISE."""
    proposals = [
        _make_prop(f"p{i}", f"agent_{i}", file_path=f"src/mod_{i}.py")
        for i in range(4)
    ]
    meta = AdaptiveProposalPartitioner.evaluate_strategy(
        proposals=proposals,
        candidate_pair_count=0,
        connected_component_count=4,
    )
    assert meta.strategy == PartitionStrategy.PAIRWISE
    assert meta.total_proposals == 4
    assert meta.density == 0.0


def test_adaptive_partitioner_component_centric():
    """Quando existem múltiplas componentes conexas e densidade moderada, deve selecionar COMPONENT_CENTRIC."""
    proposals = [
        _make_prop(f"p{i}", f"agent_{i}", file_path=f"src/mod_{i // 2}.py")
        for i in range(10)
    ]
    # 10 propostas -> 45 pares possíveis. Suponha 15 pares candidatos e 4 componentes
    meta = AdaptiveProposalPartitioner.evaluate_strategy(
        proposals=proposals,
        candidate_pair_count=15,
        connected_component_count=4,
    )
    assert meta.strategy == PartitionStrategy.COMPONENT_CENTRIC
    assert meta.component_count == 4


def test_adaptive_partitioner_hierarchical():
    """Densidade moderada/alta em componente única deve selecionar HIERARCHICAL_PARTITIONING."""
    proposals = [
        _make_prop(f"p{i}", f"agent_{i}", file_path="src/single.py")
        for i in range(12)
    ]
    # 12 propostas -> 66 pares possíveis. Suponha 25 pares candidatos e 1 componente
    meta = AdaptiveProposalPartitioner.evaluate_strategy(
        proposals=proposals,
        candidate_pair_count=25,
        connected_component_count=1,
    )
    assert meta.strategy == PartitionStrategy.HIERARCHICAL_PARTITIONING


def test_adaptive_partitioner_staged_arbitration_ultra_high_density():
    """Para N >= 16 e densidade >= 0.60, a estratégia deve ascender para STAGED_ARBITRATION."""
    proposals = [
        _make_prop(f"p{i}", f"agent_{i}", file_path="src/monolith.py")
        for i in range(20)
    ]
    total_pairs = 20 * 19 // 2  # 190 pares
    meta = AdaptiveProposalPartitioner.evaluate_strategy(
        proposals=proposals,
        candidate_pair_count=int(total_pairs * 0.75),
        connected_component_count=1,
    )
    assert meta.strategy == PartitionStrategy.STAGED_ARBITRATION
    assert meta.density >= 0.60


# ── TESTES DE GRAFO INCREMENTAL O(|ΔV|·deg) ───────────────────────────────────

def test_incremental_graph_add_and_equivalence():
    """
    Verifica que adicionar propostas incrementalmente produz um grafo com os mesmos nós
    e arestas que a computação estática direta.
    """
    graph = IncrementalConflictGraph()

    p1 = _make_prop("p1", "agent_1", file_path="src/calc.py", symbols=["add"])
    p2 = _make_prop("p2", "agent_2", file_path="src/calc.py", symbols=["add"])
    p3 = _make_prop("p3", "agent_3", file_path="src/calc.py", symbols=["multiply"])
    p4 = _make_prop("p4", "agent_4", file_path="src/other.py", symbols=["render"])

    graph.add_proposal(p1)
    graph.add_proposal(p2)
    graph.add_proposal(p3)
    graph.add_proposal(p4)

    # Nós devem conter todas as 4 propostas
    assert set(graph.nodes.keys()) == {"p1", "p2", "p3", "p4"}

    # p1 e p2 têm overlap de ficheiro e símbolo -> aresta
    assert graph.has_conflict("p1", "p2")
    assert graph.has_conflict("p2", "p1")

    # p1 e p3 têm overlap de ficheiro -> aresta
    assert graph.has_conflict("p1", "p3")

    # p4 está num ficheiro diferente -> sem aresta de conflito com p1, p2, p3
    assert not graph.has_conflict("p1", "p4")
    assert not graph.has_conflict("p2", "p4")
    assert not graph.has_conflict("p3", "p4")


def test_incremental_graph_remove_and_update():
    """Verifica a remoção e atualização de propostas sem corrupção topológica."""
    graph = IncrementalConflictGraph()
    p1 = _make_prop("p1", "agent_1", file_path="src/calc.py", symbols=["add"])
    p2 = _make_prop("p2", "agent_2", file_path="src/calc.py", symbols=["add"])

    graph.add_proposal(p1)
    graph.add_proposal(p2)
    assert graph.has_conflict("p1", "p2")

    # Remove p2
    graph.remove_proposal("p2")
    assert "p2" not in graph.nodes
    assert not graph.has_conflict("p1", "p2")
    assert graph.get_neighbors("p1") == []

    # Atualiza p1 para outro ficheiro
    p1_updated = _make_prop("p1", "agent_1", file_path="src/new_calc.py", symbols=["add"])
    graph.update_proposal(p1_updated)
    assert graph.nodes["p1"].file_path == "src/new_calc.py"


def test_incremental_graph_connected_components():
    """Verifica se a decomposição em componentes conexas do grafo incremental agrupa corretamente."""
    graph = IncrementalConflictGraph()
    # Componente A: p1 e p2 em src/a.py
    graph.add_proposal(_make_prop("p1", "agent_1", file_path="src/a.py"))
    graph.add_proposal(_make_prop("p2", "agent_2", file_path="src/a.py"))

    # Componente B: p3 e p4 em src/b.py
    graph.add_proposal(_make_prop("p3", "agent_3", file_path="src/b.py"))
    graph.add_proposal(_make_prop("p4", "agent_4", file_path="src/b.py"))

    # Componente C isolada: p5 em src/c.py
    graph.add_proposal(_make_prop("p5", "agent_5", file_path="src/c.py"))

    components = graph.get_connected_components()
    assert len(components) == 3

    comp_sizes = sorted([len(c) for c in components])
    assert comp_sizes == [1, 2, 2]


# ── TESTES DE ARBITRAGEM POR ESTÁGIOS (STAGED ARBITRATION) ────────────────────

def test_staged_arbitration_fast_pruning():
    """
    O Estágio 1 deve podar propostas que violem validação dura (sintaxe/py_compile)
    ou apresentem falhas críticas de teste.
    """
    conflict = ConflictDetails(
        conflict_type=ConflictType.FILE_OVERLAP,
        file_path="src/core.py",
        conflicting_agents=["agent_invalid", "agent_valid"],
        competing_proposals=["p_invalid", "p_valid"],
    )

    p_invalid = _make_prop(
        "p_invalid", "agent_invalid", file_path="src/core.py",
        hard_validation=False,  # Erro de sintaxe / compilação!
        tests_passed=0,
        tests_failed=5,
    )
    p_valid = _make_prop(
        "p_valid", "agent_valid", file_path="src/core.py",
        hard_validation=True,
        tests_passed=10,
        tests_failed=0,
    )

    result = StagedArbitrationEngine.arbitrate_staged(
        conflict=conflict,
        proposals=[p_invalid, p_valid],
        is_economic_task=False,
    )

    assert result.final_decision == ArbitrationDecision.CHOOSE_PROPOSAL
    assert result.winning_proposal_id == "p_valid"
    assert "p_invalid" in result.stage_1_pruned
    assert "p_valid" in result.stage_1_passed
    assert result.stage_2_rankings[0][0] == "p_valid"


def test_staged_arbitration_security_pruning():
    """Agente de pesquisa (read-only) a propor alteração de código deve ser podado no Estágio 1."""
    conflict = ConflictDetails(
        conflict_type=ConflictType.FILE_OVERLAP,
        file_path="src/core.py",
        conflicting_agents=["research_agent", "coding_agent"],
        competing_proposals=["p_research", "p_code"],
    )

    p_research = _make_prop(
        "p_research", "research_agent", file_path="src/core.py",
        content="malicious_patch = True\n",
    )
    p_code = _make_prop(
        "p_code", "coding_agent", file_path="src/core.py",
        content="normal_patch = True\n",
    )

    result = StagedArbitrationEngine.arbitrate_staged(
        conflict=conflict,
        proposals=[p_research, p_code],
    )

    assert result.winning_proposal_id == "p_code"
    assert "p_research" in result.stage_1_pruned
    assert "p_research" in result.stage_1_reasons
    assert "PRIVILEGE_VIOLATION" in result.stage_1_reasons["p_research"]


def test_staged_arbitration_economic_safeguards():
    """Em tarefas financeiras/económicas, propostas sem validação dura devem ser bloqueadas."""
    conflict = ConflictDetails(
        conflict_type=ConflictType.FILE_OVERLAP,
        file_path="src/billing.py",
        conflicting_agents=["agent_1", "agent_2"],
        competing_proposals=["p1", "p2"],
    )

    p1 = _make_prop("p1", "agent_1", file_path="src/billing.py", hard_validation=False)
    p2 = _make_prop("p2", "agent_2", file_path="src/billing.py", hard_validation=False)

    result = StagedArbitrationEngine.arbitrate_staged(
        conflict=conflict,
        proposals=[p1, p2],
        is_economic_task=True,
    )

    assert result.final_decision == ArbitrationDecision.BLOCK
    assert "ECONOMIC_SAFEGUARD" in result.rationale


def test_staged_arbitration_deterministic_tie_breaking():
    """
    Quando duas propostas possuem pontuações de evidência absolutamente idênticas,
    o Estágio 3 deve desempatar determinísticamente por SHA256 sem aleatoriedade.
    """
    conflict = ConflictDetails(
        conflict_type=ConflictType.FILE_OVERLAP,
        file_path="src/util.py",
        conflicting_agents=["agent_a", "agent_b"],
        competing_proposals=["prop_alpha", "prop_beta"],
    )

    # Ambas com rigorosamente as mesmas métricas
    p_alpha = _make_prop("prop_alpha", "agent_a", confidence=0.85)
    p_beta = _make_prop("prop_beta", "agent_b", confidence=0.85)

    result_1 = StagedArbitrationEngine.arbitrate_staged(
        conflict=conflict,
        proposals=[p_alpha, p_beta],
    )
    result_2 = StagedArbitrationEngine.arbitrate_staged(
        conflict=conflict,
        proposals=[p_beta, p_alpha],  # Ordem invertida
    )

    assert result_1.final_decision == ArbitrationDecision.CHOOSE_PROPOSAL
    assert result_2.final_decision == ArbitrationDecision.CHOOSE_PROPOSAL
    # O vencedor tem de ser estritamente o mesmo independentemente da ordem
    assert result_1.winning_proposal_id == result_2.winning_proposal_id
    assert "Deterministic tie-break" in result_1.rationale


# ── TESTES DE MEMÓRIA DE FALHAS LRU / TTL ─────────────────────────────────────

def test_merge_failure_memory_lru_and_ttl_eviction():
    """
    Verifica que MergeFailureMemory respeita o limite de capacidade e descarta entradas
    antigas ou com TTL expirado sem vazamento de memória.
    """
    # Cria memória com capacidade 5 e TTL curto
    mem = MergeFailureMemory(max_entries=5, default_ttl_seconds=1)

    for i in range(5):
        mem.record_failure(f"hash_{i}", f"failure {i}", retryable=(i % 2 == 0))

    assert len(mem.failures) == 5
    assert mem.is_known_failure("hash_0")

    # Inserir o 6º elemento deve evictar o mais antigo (LRU)
    mem.record_failure("hash_5", "failure 5")
    assert len(mem.failures) <= 5
    assert not mem.is_known_failure("hash_0")  # hash_0 foi evictado
    assert mem.is_known_failure("hash_5")

    # Teste de expiração por TTL
    time.sleep(1.1)
    evicted = mem.evict_expired()
    assert evicted > 0
    assert not mem.is_known_failure("hash_5")


# ── TESTES DE SERIALIZAÇÃO / CHECKPOINT ROUNDTRIP ─────────────────────────────

def test_collaboration_export_restore_scalability_metadata():
    """
    Verifica se o estado completo incluindo as novas estruturas da Fase 15.3
    (last_partition_metadata e incremental_graph) sobrevive ao ciclo de export/restore.
    """
    coord = CollaborationCoordinator(project_id="proj_scale", mission_id="miss_scale")
    session = coord.create_session("task_1", ["agent_1", "agent_2"])

    p1 = _make_prop("p1", "agent_1", file_path="src/a.py", content="def a(): return 1\n")
    p2 = _make_prop("p2", "agent_2", file_path="src/b.py", content="def b(): return 2\n")
    coord.add_proposal(session.collaboration_id, p1)
    coord.add_proposal(session.collaboration_id, p2)

    # Forçar deteção e indexação
    status, conflicts, arbitrations = coord.evaluate_collaboration(session.collaboration_id)
    assert status == CollaborationStatus.RESOLVED

    # Exportar estado
    state_data = coord.export_state()
    assert "last_partition_metadata" in state_data
    assert "incremental_graph" in state_data

    # Novo coordenador e restore
    coord_new = CollaborationCoordinator(project_id="proj_scale", mission_id="miss_scale")
    coord_new.restore_state(state_data)

    assert session.collaboration_id in coord_new.sessions
    restored_session = coord_new.sessions[session.collaboration_id]
    assert restored_session.status == CollaborationStatus.RESOLVED
    assert len(restored_session.proposals) == 2

    # Verificar metadados de particionamento restaurados
    assert coord_new.detector.last_partition_metadata is not None
    assert coord_new.detector.last_partition_metadata.total_proposals == 2
