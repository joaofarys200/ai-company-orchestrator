"""
Stage 1 regression tests:
1. StudyService.generate_flashcards never fabricates dummy cards on empty documents.
2. StudyService.retry_document preserves collection_id across re-ingestion.
3. ObsidianGraphEngine.compute_graph_diagnostics returns graph_nodes and graph_edges.
"""

from pathlib import Path

import pytest

from intelligence.project_context import ProjectContextError, ProjectContextService
from services.obsidian_graph_engine import ObsidianGraphEngine
from services.study_service import StudyDocument, StudyService


def test_generate_flashcards_refuses_dummy_card_on_empty_text(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDY_DISABLE_LIVE_LLM", "1")
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    svc = StudyService(workspace_root=str(tmp_path), storage_dir=str(tmp_path / "study"), vault_root=str(vault_dir))

    empty_doc = StudyDocument(
        document_id="doc_empty_vid",
        source_id="src_empty",
        title="Empty Video",
        source_type="VIDEO",
        subject="Gestão",
        language="en",
        page_count=1,
        sections=[],
        extracted_text="",
        media=[],
        metadata={"generation_mode": "INSUFFICIENT_CONTENT"},
        source_hash="hash_empty",
        provenance={},
        reading_progress={},
    )
    svc.documents[empty_doc.document_id] = empty_doc
    svc._save_documents()

    cards = svc.generate_flashcards("doc_empty_vid")
    assert cards == []


def test_retry_document_preserves_owning_collection(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDY_DISABLE_LIVE_LLM", "1")
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    svc = StudyService(workspace_root=str(tmp_path), storage_dir=str(tmp_path / "study"), vault_root=str(vault_dir))

    col = svc.create_collection("Gestão de Projetos", "Gestão")
    src_file = tmp_path / "aula.txt"
    src_file.write_text(
        "A gestão do valor ganho (EVM) relaciona âmbito, prazo e custo através de PV, EV e AC.",
        encoding="utf-8",
    )
    doc = svc.ingest_document(str(src_file), "aula.txt", subject="Gestão", collection_id=col.collection_id)
    assert doc.document_id in svc.collections[col.collection_id].document_ids

    retried = svc.retry_document(doc.document_id)
    assert retried.document_id == doc.document_id
    assert retried.document_id in svc.collections[col.collection_id].document_ids


def test_obsidian_graph_diagnostics_exports_nodes_and_edges(tmp_path):
    vault = tmp_path / "vault"
    data_dir = tmp_path / "obs_data"
    vault.mkdir(parents=True, exist_ok=True)
    (vault / "Alpha.md").write_text("# Alpha\nRelacionado com [[Beta]].\n", encoding="utf-8")
    (vault / "Beta.md").write_text("# Beta\nConceito ligado ao [[Alpha]].\n", encoding="utf-8")
    (vault / "Orphan.md").write_text("# Orphan\nNota isolada sem ligações.\n", encoding="utf-8")

    engine = ObsidianGraphEngine(vault_root=Path(vault), data_dir=Path(data_dir))
    diag = engine.compute_graph_diagnostics()

    assert diag["total_notes"] == 3
    assert "graph_nodes" in diag and "graph_edges" in diag
    node_ids = {n["id"] for n in diag["graph_nodes"]}
    assert {"Alpha.md", "Beta.md", "Orphan.md"}.issubset(node_ids)
    edges = {(e["source"], e["target"]) for e in diag["graph_edges"]}
    assert ("Alpha.md", "Beta.md") in edges
    assert ("Beta.md", "Alpha.md") in edges
    orphan_node = next(n for n in diag["graph_nodes"] if n["id"] == "Orphan.md")
    assert orphan_node["is_orphan"] is True


def test_project_context_create_and_rename_confined(tmp_path):
    svc = ProjectContextService(workspace_root=str(tmp_path), projects_root_rel="projects")
    proj_dir = tmp_path / "projects" / "demo_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "README.md").write_text("# Demo\n", encoding="utf-8")

    created = svc.create_project_file("demo_proj", "src/app.py", "print('ok')\n")
    assert created["filename"] == "src/app.py"
    assert (proj_dir / "src" / "app.py").read_text(encoding="utf-8") == "print('ok')\n"

    renamed = svc.rename_project_file("demo_proj", "src/app.py", "src/main.py")
    assert renamed["new_filename"] == "src/main.py"
    assert not (proj_dir / "src" / "app.py").exists()
    assert (proj_dir / "src" / "main.py").exists()

    with pytest.raises(ProjectContextError):
        svc.create_project_file("demo_proj", "../escape.py", "x")

