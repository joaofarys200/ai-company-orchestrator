"""
Tests for JARVIS OS — Obsidian Knowledge Graph Autonomous Evolution Engine
Tests execute against temporary/disposable copies of test vaults to ensure zero
destructive modifications to the canonical user vault.
"""

import shutil
import tempfile
from pathlib import Path
import pytest

from services.obsidian_graph_engine import ObsidianGraphEngine, CONCEPT_SYNONYM_REGISTRY


@pytest.fixture
def temp_vault(tmp_path):
    vault = tmp_path / "obsidian_vault"
    vault.mkdir()
    
    # Create sample notes
    moc_dir = vault / "00 - MOC"
    moc_dir.mkdir()
    (moc_dir / "00 - Knowledge Index.md").write_text("---\ntype: index\n---\n# Master Index\n- [[AI Index]]\n", encoding="utf-8")
    (moc_dir / "AI Index.md").write_text("---\ntype: moc\n---\n# AI Index\n- [[Agent Systems]]\n", encoding="utf-8")
    
    ai_dir = vault / "01 - AI"
    ai_dir.mkdir()
    (ai_dir / "Agent Systems.md").write_text("""---
title: Agent Systems Architecture
aliases:
  - Agent Swarm
  - Multi-Agent Orchestrator
tags:
  - ai
  - agents
source_type: PRIMARY_SOURCE
status: verified
---
# Agent Systems Architecture

## 1. Sumário Executivo
Explicação detalhada sobre agentes autónomos e comunicação inter-agente baseada em normas RFC e especificações de sistemas distribuídos.

## 2. Protocolo de Comunicação
```python
def dispatch_task(agent_id: str, payload: dict) -> bool:
    return True
```

## 3. Glossário e Takeaways
- **Swarm**: Grupo coordenado de subagentes com contexto isolado.
- Conexão conceitual com [[Post-Quantum Cryptography]].
""", encoding="utf-8")

    sec_dir = vault / "05 - Security"
    sec_dir.mkdir()
    (sec_dir / "Post-Quantum Cryptography.md").write_text("""---
title: Post-Quantum Cryptography
aliases:
  - PQC
  - ML-KEM
source_type: PRIMARY_SOURCE
---
# Post-Quantum Cryptography
FIPS 203 e ML-KEM para criptografia pós-quântica.
""", encoding="utf-8")

    # Orphan note
    lectures_dir = vault / "10 - Lectures"
    lectures_dir.mkdir()
    (lectures_dir / "Lecture - RAG and Agents.md").write_text("""# Aula de RAG e Agentes
Nesta aula discutimos retrieval-augmented generation e o uso de PQC para segurança.
""", encoding="utf-8")

    return vault


def test_01_layered_concept_resolution_title_alias_and_synonym(temp_vault):
    engine = ObsidianGraphEngine(vault_root=temp_vault)
    
    # 1. Exact canonical title
    res_title = engine.resolve_concept_link("Agent Systems", "Lecture - RAG and Agents")
    assert res_title is not None
    assert res_title["target_note"] == "Agent Systems"
    assert res_title["creation_method"] == "CANONICAL_TITLE_MATCH"

    # 2. YAML alias resolution
    res_alias = engine.resolve_concept_link("PQC", "Lecture - RAG and Agents")
    assert res_alias is not None
    assert res_alias["target_note"] == "Post-Quantum Cryptography"
    assert res_alias["creation_method"] == "YAML_ALIAS_MATCH"

    # 3. Common words rejection
    res_common = engine.resolve_concept_link("para", "Lecture - RAG and Agents")
    assert res_common is None


def test_02_typed_relationships_inference(temp_vault):
    engine = ObsidianGraphEngine(vault_root=temp_vault)
    
    # Context with prerequisite
    rel_type = engine._infer_relationship_type(
        "Lecture - Advanced RAG", "Agent Systems", "O estudo de Agent Systems é um pré-requisito essencial para o RAG."
    )
    assert rel_type == "PREREQUISITE_OF"

    # Context with contrast
    rel_type_contrast = engine._infer_relationship_type(
        "Vector Search", "BM25", "A busca vetorial contrasta com o BM25 lexical clássico."
    )
    assert rel_type_contrast == "CONTRASTS_WITH"


def test_03_note_quality_assessment_10_dimensions(temp_vault):
    engine = ObsidianGraphEngine(vault_root=temp_vault)
    
    # Audit well-formed note
    audit_ai = engine.audit_note_quality("01 - AI/Agent Systems.md")
    assert audit_ai["overall_score"] >= 70.0
    assert audit_ai["epistemic_classification"] in ("VERIFIED_SOURCE_CONTENT", "VERIFIED_PRIMARY_SOURCE")
    assert "provenance" in audit_ai["dimension_scores"]
    assert "factual_grounding" in audit_ai["dimension_scores"]
    assert "completeness" in audit_ai["dimension_scores"]
    assert "technical_depth" in audit_ai["dimension_scores"]

    # Audit unverified orphan note
    audit_orphan = engine.audit_note_quality("10 - Lectures/Lecture - RAG and Agents.md")
    assert audit_orphan["needs_improvement"] is True
    assert audit_orphan["epistemic_classification"] in ("UNVERIFIED", "UNVERIFIED_HEURISTIC")
    assert any(f["dimension"] == "Provenance" for f in audit_orphan["findings"])


def test_04_queue_population_and_priority_sorting(temp_vault):
    engine = ObsidianGraphEngine(vault_root=temp_vault)
    queue = engine.populate_improvement_queue()
    assert len(queue) >= 1
    # Note with lowest quality has highest priority score
    assert queue[0]["note_path"] == "10 - Lectures/Lecture - RAG and Agents.md"


def test_05_safe_enrichment_creates_backup_and_allows_rollback(temp_vault):
    engine = ObsidianGraphEngine(vault_root=temp_vault)
    target_rel = "10 - Lectures/Lecture - RAG and Agents.md"
    orig_content = (temp_vault / target_rel).read_text(encoding="utf-8")

    # Enrich
    proposal = engine.enrich_note_safely(target_rel, auto_apply=True)
    assert proposal["status"] == "APPLIED"
    assert Path(proposal["backup_path"]).exists()

    enriched_content = (temp_vault / target_rel).read_text(encoding="utf-8")
    assert "---" in enriched_content
    assert "type: atomic_note" in enriched_content
    # Original text preserved
    assert "Nesta aula discutimos retrieval-augmented generation" in enriched_content

    # Rollback
    rolled_back = engine.rollback_note(target_rel, proposal["backup_path"])
    assert rolled_back is True
    restored_content = (temp_vault / target_rel).read_text(encoding="utf-8")
    assert restored_content == orig_content


def test_06_bridge_note_generation(temp_vault):
    engine = ObsidianGraphEngine(vault_root=temp_vault)
    bridge_path = engine.generate_bridge_note(
        source_note_a="Agent Systems",
        source_note_b="Lecture - RAG and Agents",
        bridge_title="Agentes Autónomos e RAG no JARVIS",
        shared_concepts=["Retrieval-Augmented Generation", "Multi-Agent Swarm"],
        theoretical_principles="Decomposição de queries e orquestração de subagentes com contexto isolado.",
        runtime_implementation="Implementado no JARVIS via SwarmOrchestrator e ModelExecutionService.",
    )
    assert bridge_path.exists()
    content = bridge_path.read_text(encoding="utf-8")
    assert "type: bridge_note" in content
    assert "[[Agent Systems]]" in content
    assert "[[Lecture - RAG and Agents]]" in content
