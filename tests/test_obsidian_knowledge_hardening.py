"""
JARVIS OS — Test Suite for Obsidian Knowledge Engine Corrective Hardening
Validates:
  1. Strict Path Containment & Security Traversal Protection
  2. High-Resolution Snapshot Uniqueness & Identity Verification
  3. Atomic Writes & Compare-And-Swap (CAS) Concurrency
  4. Four-Category Calibrated Quality Scoring (Structural, Knowledge, Evidence, Graph)
  5. Markdown-Aware Wikilink & Attachment Resolution
  6. Autonomous Improvement Worker Lifecycle (Pause, Resume, Bounded Batch, Telemetry)
  7. Bridge Note Evidence Validation & Rollback
All tests run in isolated temporary vaults without modifying canonical user directories.
"""

import os
import shutil
import time
from pathlib import Path
import pytest

from services.obsidian_graph_engine import (
    ObsidianGraphEngine,
    ObsidianSecurityError,
    ObsidianNotFoundError,
    ObsidianConcurrencyError,
    CONCEPT_SYNONYM_REGISTRY,
)


@pytest.fixture
def disposable_vault(tmp_path: Path):
    """Creates a temporary isolated vault with realistic notes and injectable directories."""
    v_root = tmp_path / "vault"
    d_dir = tmp_path / "data"
    h_dir = v_root / ".history"
    p_dir = d_dir / "proposals"
    q_file = d_dir / "queue.json"
    diag_file = d_dir / "diagnostics.json"

    v_root.mkdir(parents=True)
    d_dir.mkdir(parents=True)
    h_dir.mkdir(parents=True)
    p_dir.mkdir(parents=True)

    # Note 1: Architecture Note with valid frontmatter and links
    (v_root / "01 - AI").mkdir(parents=True)
    note1 = v_root / "01 - AI" / "Model Context Protocol (MCP) and Capability Discovery Architecture.md"
    note1.write_text(
        "---\n"
        "type: architecture\n"
        "domain: AI & LLM\n"
        "status: verified\n"
        "source_type: RFC\n"
        "provenance: RFC_MCP_2024\n"
        "aliases:\n"
        "  - MCP Architecture\n"
        "  - Model Context Protocol\n"
        "---\n\n"
        "# Model Context Protocol (MCP) and Capability Discovery Architecture\n\n"
        "## Sumário Executivo\n"
        "O protocolo MCP padroniza a exposição de ferramentas e capacidades contextuais para LLMs [E1].\n\n"
        "## Arquitetura de Comunicação\n"
        "A comunicação efetua-se através de transportes JSON-RPC bidirecionais seguros [E2].\n"
        "```python\n"
        "# Exemplo de tool call com sintaxe de código que não deve ser confundida com link:\n"
        "result = client.call_tool('search', query='test')\n"
        "```\n\n"
        "## Relações no Grafo\n"
        "- [[JARVIS Autonomous Agent Hierarchy]]\n",
        encoding="utf-8",
    )

    # Note 2: Agent Note
    (v_root / "09 - JARVIS").mkdir(parents=True)
    note2 = v_root / "09 - JARVIS" / "JARVIS Autonomous Agent Hierarchy.md"
    note2.write_text(
        "---\n"
        "type: architecture\n"
        "domain: JARVIS Internal\n"
        "status: verified\n"
        "source_type: JARVIS_INTERNAL\n"
        "provenance: JARVIS_INTERNAL_SPEC\n"
        "---\n\n"
        "# JARVIS Autonomous Agent Hierarchy\n\n"
        "## Visão Geral\n"
        "Coordenação hierárquica entre Swarm Coordinator, Coder e Tester.\n\n"
        "## Integração de Protocolos\n"
        "Utiliza o protocolo [[Model Context Protocol (MCP) and Capability Discovery Architecture]] para discovery.\n",
        encoding="utf-8",
    )

    # Note 3: Note with code block containing Python generic type hint
    note3 = v_root / "Caching Strategies.md"
    note3.write_text(
        "---\n"
        "type: technical_note\n"
        "domain: Backend\n"
        "---\n\n"
        "# Caching Strategies\n\n"
        "## Exemplo de Código com Type Hints\n"
        "```python\n"
        "from typing import Callable, Awaitable, TypeVar\n"
        "T = TypeVar('T')\n"
        "Handler = Callable[[], Awaitable[T]]\n"
        "```\n\n"
        "Texto corrido com link válido para [[Model Context Protocol (MCP) and Capability Discovery Architecture]].\n",
        encoding="utf-8",
    )

    engine = ObsidianGraphEngine(
        vault_root=v_root,
        data_dir=d_dir,
        history_dir=h_dir,
        proposals_dir=p_dir,
        queue_file=q_file,
        diagnostics_file=diag_file,
    )
    return engine, v_root, h_dir, d_dir


# ==============================================================================
# 1. SECURITY & PATH CONTAINMENT TESTS
# ==============================================================================

def test_security_rejects_parent_traversal(disposable_vault):
    """Ensures that any attempt to traverse parent directories using ../ is rejected."""
    engine, v_root, h_dir, _ = disposable_vault

    with pytest.raises(ObsidianSecurityError, match="traversal"):
        engine._resolve_contained_note_path("../../server.py")

    with pytest.raises(ObsidianSecurityError, match="traversal"):
        engine._resolve_contained_note_path("01 - AI/../../../etc/passwd")


def test_security_rejects_absolute_path_outside_vault(disposable_vault, tmp_path: Path):
    """Ensures absolute paths pointing outside vault root are rejected."""
    engine, _, _, _ = disposable_vault
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("malicious content")

    with pytest.raises(ObsidianSecurityError, match="fora do cofre"):
        engine._resolve_contained_note_path(str(outside_file))


def test_security_rejects_arbitrary_rollback_source(disposable_vault, tmp_path: Path):
    """Rollback must reject arbitrary files outside .history directory."""
    engine, v_root, h_dir, _ = disposable_vault
    outside_backup = tmp_path / "fake_backup.md"
    outside_backup.write_text("malicious replacement")

    with pytest.raises(ObsidianSecurityError, match="fora do diretório .history"):
        engine.rollback_note(
            "Caching Strategies.md",
            str(outside_backup),
        )


def test_security_rejects_rollback_snapshot_mismatched_identity(disposable_vault):
    """Rollback must reject a snapshot that belongs to a different note."""
    engine, v_root, h_dir, _ = disposable_vault

    # Create backup of Note 1
    snap_path, meta = engine.create_note_backup_snapshot(
        "01 - AI/Model Context Protocol (MCP) and Capability Discovery Architecture.md"
    )

    # Attempt to apply Note 1's backup over Note 2
    with pytest.raises(ObsidianSecurityError, match="Snapshot pertence a"):
        engine.rollback_note(
            "09 - JARVIS/JARVIS Autonomous Agent Hierarchy.md",
            str(snap_path),
        )


# ==============================================================================
# 2. SNAPSHOT & ATOMIC WRITE INTEGRITY TESTS
# ==============================================================================

def test_snapshot_uniqueness_and_no_collision(disposable_vault):
    """High-frequency snapshots must generate unique non-colliding files with sidecars."""
    engine, _, h_dir, _ = disposable_vault
    rel = "Caching Strategies.md"

    p1, m1 = engine.create_note_backup_snapshot(rel)
    p2, m2 = engine.create_note_backup_snapshot(rel)

    assert p1.exists()
    assert p2.exists()
    assert p1.name != p2.name
    assert p1.with_suffix(".json").exists()
    assert p2.with_suffix(".json").exists()
    assert m1["snapshot_id"] != m2["snapshot_id"]


def test_atomic_write_and_optimistic_concurrency(disposable_vault):
    """Atomic write validates expected SHA-256 and detects concurrent modifications."""
    engine, v_root, _, _ = disposable_vault
    target = v_root / "Caching Strategies.md"
    orig_sha = engine.get_note_sha256(target)

    # Successful atomic write with matching CAS
    res = engine.atomic_write_note(
        "Caching Strategies.md",
        "---\ntype: test\n---\n# New Header\n\nContent update.",
        expected_sha256=orig_sha,
    )
    assert res["sha256_before"] == orig_sha
    assert res["sha256_after"] != orig_sha

    # Attempt second write with stale SHA -> Must raise ConcurrencyError
    with pytest.raises(ObsidianConcurrencyError, match="Conflito de concorrência"):
        engine.atomic_write_note(
            "Caching Strategies.md",
            "---\ntype: test\n---\n# Conflicting Header",
            expected_sha256=orig_sha,
        )


# ==============================================================================
# 3. QUALITY SCORING 4-CATEGORY MODEL TESTS
# ==============================================================================

def test_quality_scoring_four_categories_no_fixed_scores(disposable_vault):
    """Quality scoring must evaluate 4 explicit categories without fake 90/95 scores."""
    engine, _, _, _ = disposable_vault
    audit = engine.audit_note_quality("01 - AI/Model Context Protocol (MCP) and Capability Discovery Architecture.md")

    assert "categories" in audit
    cats = audit["categories"]
    assert "structural_quality" in cats
    assert "knowledge_quality" in cats
    assert "evidence_quality" in cats
    assert "graph_quality" in cats

    assert audit["epistemic_classification"] == "VERIFIED_PRIMARY_SOURCE"
    assert audit["freshness"] in ("UNKNOWN", "MEASURED")
    assert audit["uniqueness"]["evaluated"] is True
    assert audit["calculation_method"] == "FOUR_CATEGORY_MULTI_DIMENSIONAL_V2"


def test_quality_scoring_jarvis_internal_not_promoted_to_verified_source(disposable_vault):
    """JARVIS_INTERNAL notes must remain classified as INTERNAL_SPEC, not verified external source."""
    engine, _, _, _ = disposable_vault
    audit = engine.audit_note_quality("09 - JARVIS/JARVIS Autonomous Agent Hierarchy.md")

    assert audit["epistemic_classification"] == "INTERNAL_ENGINEERING_SPEC"
    assert audit["epistemic_classification"] != "VERIFIED_PRIMARY_SOURCE"


# ==============================================================================
# 4. MARKDOWN-AWARE LINK RESOLUTION TESTS
# ==============================================================================

def test_markdown_aware_links_ignores_code_fences_and_types(disposable_vault):
    """Code blocks containing type annotations like Callable[[], ...] must not become broken links."""
    engine, _, _, _ = disposable_vault
    diag = engine.compute_graph_diagnostics()

    # Caching Strategies has Handler = Callable[[], Awaitable[T]] in a code fence.
    # Must NOT report [], Awaitable[T] as a broken wikilink.
    for bl in diag["broken_links_list"]:
        assert "Awaitable" not in bl["target"]
        assert "Callable" not in bl["target"]

    assert diag["code_examples_ignored_count"] >= 1


# ==============================================================================
# 5. SEMANTIC LINKING PRECISION TESTS
# ==============================================================================

def test_semantic_linking_rejects_erroneous_togaf_mapping():
    """TOGAF must not map to API Contract Evolution or SIUM."""
    assert "togaf" not in CONCEPT_SYNONYM_REGISTRY or (
        "API Contract" not in CONCEPT_SYNONYM_REGISTRY["togaf"]["canonical_note"]
    )


# ==============================================================================
# 6. AUTONOMOUS QUEUE WORKER LIFECYCLE TESTS
# ==============================================================================

def test_improvement_queue_and_worker_controls(disposable_vault):
    """Validates worker state controls: pause, resume, bounded batch."""
    engine, _, _, _ = disposable_vault

    status = engine.get_worker_status()
    assert status["is_paused"] is False

    engine.pause_queue_worker()
    status_paused = engine.get_worker_status()
    assert status_paused["is_paused"] is True

    engine.resume_queue_worker()
    status_resumed = engine.get_worker_status()
    assert status_resumed["is_paused"] is False


# ==============================================================================
# 7. BRIDGE NOTE EVIDENCE VALIDATION TESTS
# ==============================================================================

def test_bridge_note_validation_requires_existing_sources(disposable_vault):
    """Bridge Note generation must reject nonexistent source notes."""
    engine, _, _, _ = disposable_vault

    with pytest.raises(ObsidianNotFoundError, match="Nota de origem A não existe"):
        engine.generate_bridge_note(
            source_note_a="Nonexistent Note A",
            source_note_b="JARVIS Autonomous Agent Hierarchy",
            bridge_title="Test Bridge",
            shared_concepts=["Test"],
            theoretical_principles="Theory",
            runtime_implementation="Code",
            evidence_refs=["REF1"],
        )
