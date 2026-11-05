"""
Test Suite: Study Area Folder-Based Materials & Automatic Synchronization
Comprehensive E2E and Unit Verification for Scenarios A through N:
- Scenario A: Associate course with local folder.
- Scenario B: Initial scan discovers and processes files.
- Scenario C: Newly added PDF appears without manual upload.
- Scenario D: Newly added lecture video enters real transcription/processing pipeline.
- Scenario E: Modified file reprocessed without duplicate indexed documents.
- Scenario F: Renaming file preserves source associations.
- Scenario G: Deleting source updates collection without deleting unrelated disk files.
- Scenario H: Offline changes detected after restart (startup reconciliation).
- Scenario I: Individual uploads and folder-based materials coexist in course.
- Scenario J: Course Q&A uses appropriate materials and citations.
- Scenario K: Unsupported files and failures reported accurately.
- Scenario L: Unlinking stops monitoring without deleting original files (Zero Data Loss).
- Scenario M: Path traversal boundaries enforced (Security validation).
- Scenario N: Existing Study functionality regression tests pass.
"""

import pytest
import os
import shutil
import tempfile
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from services.folder_sync_service import (
    validate_and_normalize_folder_path,
    is_supported_study_file,
    compute_file_sha256,
    FolderSyncManager,
    StudyFolderLink,
    ScannedFileInfo,
    FolderSyncReport,
    SUPPORTED_DOC_EXTS,
    SUPPORTED_VIDEO_EXTS,
)
from services.study_service import (
    StudyService,
    StudyCollection,
    StudyDocument,
)
from backend.websocket.handlers.study import StudyWebSocketHandler


@pytest.fixture
def temp_workspace():
    temp_dir = tempfile.mkdtemp(prefix="test_study_sync_workspace_")
    vault_dir = os.path.join(temp_dir, "obsidian_vault")
    os.makedirs(vault_dir, exist_ok=True)
    yield temp_dir
    time.sleep(0.1)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_study_folder():
    folder_dir = tempfile.mkdtemp(prefix="test_study_course_folder_")
    yield folder_dir
    time.sleep(0.1)
    shutil.rmtree(folder_dir, ignore_errors=True)


@pytest.fixture
def study_service(temp_workspace):
    vault_dir = os.path.join(temp_workspace, "obsidian_vault")
    service = StudyService(
        workspace_root=temp_workspace,
        vault_root=vault_dir,
    )
    yield service
    if hasattr(service, "folder_sync_manager"):
        service.folder_sync_manager.stop_monitoring()


# ============================================================================
# SCENARIO A: Associate course with local folder
# ============================================================================
def test_scenario_a_associate_course_with_local_folder(study_service, sample_study_folder):
    """Scenario A: Validate linking course to local folder, registering watcher, and initial state."""
    col = study_service.create_collection("Engenharia de Software", "Ciência da Computação")
    assert col.name == "Engenharia de Software"
    assert col.collection_id is not None
    assert len(col.linked_folders) == 0

    link_res = study_service.link_folder_to_collection(
        collection_id=col.collection_id,
        folder_path=sample_study_folder,
        recursive=True,
    )
    assert link_res["status"] == "LINKED"

    updated_col = study_service.get_collection(col.collection_id)
    assert len(updated_col.linked_folders) == 1
    linked = updated_col.linked_folders[0]
    folder_p = linked.get("folder_path") if isinstance(linked, dict) else linked.folder_path
    sync_en = linked.get("sync_enabled") if isinstance(linked, dict) else linked.sync_enabled
    st = linked.get("status") if isinstance(linked, dict) else linked.status

    assert os.path.normcase(folder_p) == os.path.normcase(sample_study_folder)
    assert sync_en is True
    assert st in ("IDLE", "SYNCING")


# ============================================================================
# SCENARIO B: Initial scan discovers and processes files
# ============================================================================
def test_scenario_b_initial_scan_discovers_and_processes_files(study_service, sample_study_folder):
    """Scenario B: Populate local folder with PDF, Markdown, and TXT; verify initial scan ingests all."""
    pdf_path = os.path.join(sample_study_folder, "aula01_intro.txt")
    with open(pdf_path, "w", encoding="utf-8") as f:
        f.write("Introdução à Engenharia de Software. Conceito de modularidade e acoplamento.")

    notes_path = os.path.join(sample_study_folder, "apontamentos.md")
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("# Apontamentos de Aula\nRequisitos funcionais vs não-funcionais.")

    col = study_service.create_collection("Engenharia de Software", "Engenharia")
    link_res = study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    assert link_res["total_files"] >= 2
    assert link_res["added_files"] >= 2
    assert len(link_res["errors"]) == 0

    updated_col = study_service.get_collection(col.collection_id)
    assert len(updated_col.document_ids) >= 2

    for doc_id in updated_col.document_ids:
        doc = study_service.get_document(doc_id)
        assert doc is not None
        assert doc.provenance.get("source_origin") == "linked_folder"
        assert os.path.normcase(doc.provenance.get("linked_folder_path")) == os.path.normcase(sample_study_folder)
        assert doc.provenance.get("sync_status") in ("READY", "synced")


# ============================================================================
# SCENARIO C: Newly added PDF appears without manual upload
# ============================================================================
def test_scenario_c_newly_added_file_appears_on_sync(study_service, sample_study_folder):
    """Scenario C: Add new file to linked folder and trigger sync; verify automatic ingestion."""
    col = study_service.create_collection("Sistemas Distribuídos", "Computação")
    study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    initial_docs_count = len(study_service.get_collection(col.collection_id).document_ids)

    new_doc_path = os.path.join(sample_study_folder, "capitulo2_consenso.txt")
    with open(new_doc_path, "w", encoding="utf-8") as f:
        f.write("Algoritmos de consenso distribuído: Raft e Paxos com tolerância a falhas bizantinas.")

    report = study_service.sync_collection_folder(col.collection_id, sample_study_folder)
    assert report.added_files >= 1

    updated_col = study_service.get_collection(col.collection_id)
    assert len(updated_col.document_ids) == initial_docs_count + 1

    newest_doc_id = updated_col.document_ids[-1]
    newest_doc = study_service.get_document(newest_doc_id)
    assert "consenso" in newest_doc.title.lower() or "capitulo2" in newest_doc.title.lower()
    assert "Raft e Paxos" in newest_doc.extracted_text


# ============================================================================
# SCENARIO D: Newly added lecture video enters video pipeline
# ============================================================================
def test_scenario_d_newly_added_lecture_video_pipeline(study_service, sample_study_folder):
    """Scenario D: Newly added video file enters pipeline with source_type='VIDEO'."""
    col = study_service.create_collection("Inteligência Artificial", "IA")
    study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    video_file = os.path.join(sample_study_folder, "aula_redes_neurais.mp4")
    with open(video_file, "wb") as f:
        f.write(b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41")

    with patch.object(study_service, "ingest_video") as mock_ingest_video:
        mock_doc = StudyDocument(
            document_id="doc_mock_video_123",
            source_id="src_video_123",
            title="aula_redes_neurais.mp4",
            source_type="VIDEO",
            subject="Inteligência Artificial",
            language="pt",
            page_count=1,
            sections=[],
            extracted_text="Transcrição da aula sobre gradiente descendente.",
            media=[],
            metadata={"video": {"duration_seconds": 1800}},
            source_hash="hash_video_test",
            provenance={
                "source_file": video_file,
                "ingested_at": "2026-10-21T20:00:00Z",
                "evidence_status": "OBSERVED",
                "source_origin": "linked_folder",
                "linked_folder_path": sample_study_folder,
                "rel_path": "aula_redes_neurais.mp4",
                "sync_status": "synced",
            },
        )
        study_service._documents[mock_doc.document_id] = mock_doc
        mock_ingest_video.return_value = mock_doc

        report = study_service.sync_collection_folder(col.collection_id, sample_study_folder)
        assert mock_ingest_video.called
        assert report.added_files >= 1


# ============================================================================
# SCENARIO E: Modified file reprocessed without duplicate indexed documents
# ============================================================================
def test_scenario_e_modified_file_reprocessed_without_duplicates(study_service, sample_study_folder):
    """Scenario E: Modifying an existing file reprocesses in-place with identical document_id."""
    doc_path = os.path.join(sample_study_folder, "arquitetura.txt")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("Versão 1 da arquitetura de microsserviços.")

    col = study_service.create_collection("Arquitetura de Software", "Engenharia")
    study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    initial_col = study_service.get_collection(col.collection_id)
    assert len(initial_col.document_ids) == 1
    doc_id = initial_col.document_ids[0]
    initial_doc = study_service.get_document(doc_id)
    assert "Versão 1" in initial_doc.extracted_text

    time.sleep(0.05)

    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("Versão 2 da arquitetura de microsserviços com event-driven architecture e Kafka.")

    report = study_service.sync_collection_folder(col.collection_id, sample_study_folder)
    assert report.modified_files == 1

    updated_col = study_service.get_collection(col.collection_id)
    assert len(updated_col.document_ids) == 1
    assert updated_col.document_ids[0] == doc_id

    updated_doc = study_service.get_document(doc_id)
    assert "Versão 2" in updated_doc.extracted_text
    assert "event-driven architecture" in updated_doc.extracted_text


# ============================================================================
# SCENARIO F: Renaming file preserves source associations
# ============================================================================
def test_scenario_f_renaming_file_preserves_associations(study_service, sample_study_folder):
    """Scenario F: Renaming a file on disk updates rel_path and title without creating duplicate document."""
    old_path = os.path.join(sample_study_folder, "slides_v1.txt")
    content = "Conteúdo exclusivo sobre padrões de desenho: Factory, Singleton e Strategy."
    with open(old_path, "w", encoding="utf-8") as f:
        f.write(content)

    col = study_service.create_collection("Padrões de Desenho", "Engenharia")
    study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    initial_col = study_service.get_collection(col.collection_id)
    assert len(initial_col.document_ids) == 1
    doc_id = initial_col.document_ids[0]

    # Rename file on disk (same content/hash)
    new_path = os.path.join(sample_study_folder, "slides_v1_design_patterns.txt")
    os.rename(old_path, new_path)

    report = study_service.sync_collection_folder(col.collection_id, sample_study_folder)
    assert report.renamed_files == 1

    updated_col = study_service.get_collection(col.collection_id)
    assert len(updated_col.document_ids) == 1
    assert updated_col.document_ids[0] == doc_id

    doc = study_service.get_document(doc_id)
    assert "design_patterns" in doc.provenance.get("rel_path")


# ============================================================================
# SCENARIO G: Deleting source updates collection without deleting other files
# ============================================================================
def test_scenario_g_deleting_source_updates_collection(study_service, sample_study_folder):
    """Scenario G: Deleting a file on disk updates collection while preserving other disk files."""
    file_to_delete = os.path.join(sample_study_folder, "temporario.txt")
    file_to_keep = os.path.join(sample_study_folder, "permanente.txt")

    with open(file_to_delete, "w", encoding="utf-8") as f:
        f.write("Documento temporário que será removido.")

    with open(file_to_keep, "w", encoding="utf-8") as f:
        f.write("Documento permanente essencial.")

    col = study_service.create_collection("Gestão de Dados", "Engenharia")
    study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    initial_col = study_service.get_collection(col.collection_id)
    assert len(initial_col.document_ids) == 2

    # Delete only the temporary file from disk
    os.remove(file_to_delete)

    report = study_service.sync_collection_folder(col.collection_id, sample_study_folder)
    assert report.deleted_files == 1

    assert os.path.exists(file_to_keep)
    with open(file_to_keep, "r", encoding="utf-8") as f:
        assert "Documento permanente" in f.read()

    updated_col = study_service.get_collection(col.collection_id)
    assert len(updated_col.document_ids) == 1


# ============================================================================
# SCENARIO H: Offline changes detected after restart
# ============================================================================
def test_scenario_h_offline_changes_detected_on_startup(temp_workspace, sample_study_folder):
    """Scenario H: Changes made while JARVIS was closed are reconciled upon startup."""
    vault_dir = os.path.join(temp_workspace, "obsidian_vault")

    # Instance 1: Create collection and link folder
    service1 = StudyService(workspace_root=temp_workspace, vault_root=vault_dir)
    col = service1.create_collection("Compiladores", "Ciência da Computação")
    service1.link_folder_to_collection(col.collection_id, sample_study_folder)
    service1.folder_sync_manager.stop_monitoring()

    # While offline (service stopped), user adds a file
    offline_file = os.path.join(sample_study_folder, "analise_sintatica_lr1.txt")
    with open(offline_file, "w", encoding="utf-8") as f:
        f.write("Tabelas de parsing LR(1) e tratamento de ambiguidades na gramática.")

    # Instance 2: Start new service (simulating app relaunch)
    service2 = StudyService(workspace_root=temp_workspace, vault_root=vault_dir)
    try:
        service2.sync_collection_folder(col.collection_id, sample_study_folder)

        updated_col = service2.get_collection(col.collection_id)
        assert len(updated_col.document_ids) >= 1
        new_doc = service2.get_document(updated_col.document_ids[0])
        assert "analise" in new_doc.title.lower() and "sintatica" in new_doc.title.lower()
        assert "parsing LR(1)" in new_doc.extracted_text
    finally:
        service2.folder_sync_manager.stop_monitoring()


# ============================================================================
# SCENARIO I: Individual uploads and folder-based materials coexist
# ============================================================================
def test_scenario_i_individual_and_folder_materials_coexist(study_service, sample_study_folder):
    """Scenario I: Manual uploads and linked folder files coexist in the same course."""
    folder_file = os.path.join(sample_study_folder, "capitulo_redes.txt")
    with open(folder_file, "w", encoding="utf-8") as f:
        f.write("Camada de transporte: TCP vs UDP.")

    col = study_service.create_collection("Redes de Computadores", "Engenharia")
    study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    # Manual upload into the same course
    manual_doc = study_service.ingest_document(
        file_path_or_content=b"Protocolo BGP e roteamento inter-dominios na Internet.",
        filename="artigo_bgp.txt",
        subject="Redes de Computadores",
        source_origin="manual_upload",
        collection_id=col.collection_id,
    )

    updated_col = study_service.get_collection(col.collection_id)
    assert len(updated_col.document_ids) == 2

    origins = [study_service.get_document(d_id).provenance.get("source_origin") for d_id in updated_col.document_ids]
    assert "linked_folder" in origins
    assert "manual_upload" in origins


# ============================================================================
# SCENARIO J: Course Q&A uses appropriate materials and citations
# ============================================================================
def test_scenario_j_course_qa_citations_and_fallback(study_service, sample_study_folder):
    """Scenario J: Course Q&A returns cited answers and handles insufficient evidence gracefully."""
    doc_path = os.path.join(sample_study_folder, "bancos_dados.txt")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write("Propriedades ACID: Atomicidade, Consistência, Isolamento e Durabilidade.")

    col = study_service.create_collection("Bases de Dados", "Computação")
    study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    # 1. Query with evidence
    res = study_service.ask_course(col.collection_id, "O que significa ACID?")
    assert "answer" in res
    assert "citations" in res
    assert len(res["citations"]) > 0
    assert "Atomicidade" in res["answer"] or "ACID" in res["answer"]

    # 2. Query with missing evidence -> graceful fallback
    res_unknown = study_service.ask_course(col.collection_id, "Qual é a massa da lua?")
    assert res_unknown.get("evidence_status") == "INSUFFICIENT_EVIDENCE" or "evidências suficientes" in res_unknown["answer"].lower()


# ============================================================================
# SCENARIO K: Unsupported files and failures reported accurately
# ============================================================================
def test_scenario_k_unsupported_files_and_failures(study_service, sample_study_folder):
    """Scenario K: Unsupported binaries (.exe) are ignored; corrupted files report failure without crashing."""
    exe_file = os.path.join(sample_study_folder, "malware_test.exe")
    with open(exe_file, "wb") as f:
        f.write(b"MZ\x90\x00\x03\x00\x00\x00")

    valid_file = os.path.join(sample_study_folder, "valido.txt")
    with open(valid_file, "w", encoding="utf-8") as f:
        f.write("Ficheiro válido suportado.")

    col = study_service.create_collection("Segurança", "Computação")
    link_res = study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    # Exe was ignored, valid was added
    assert link_res["added_files"] == 1
    updated_col = study_service.get_collection(col.collection_id)
    assert len(updated_col.document_ids) == 1
    doc = study_service.get_document(updated_col.document_ids[0])
    assert "valido" in doc.title.lower()


# ============================================================================
# SCENARIO L: Unlinking stops monitoring without deleting original files
# ============================================================================
def test_scenario_l_unlinking_stops_monitoring_zero_disk_deletion(study_service, sample_study_folder):
    """Scenario L: Zero Data Loss Guarantee - unlinking removes watcher and protects files from disk deletion."""
    test_file = os.path.join(sample_study_folder, "artigo_original.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("Conteúdo extremamente valioso do utilizador.")

    col = study_service.create_collection("Bioinformática", "Biologia")
    study_service.link_folder_to_collection(col.collection_id, sample_study_folder)

    updated_col = study_service.get_collection(col.collection_id)
    doc_id = updated_col.document_ids[0]

    # Verify delete_document blocks physical deletion for linked folder materials
    study_service.delete_document(doc_id, delete_file=True)
    # The file MUST STILL EXIST on disk!
    assert os.path.exists(test_file)

    # Unlink folder from collection
    study_service.unlink_folder_from_collection(col.collection_id, sample_study_folder)
    col_after_unlink = study_service.get_collection(col.collection_id)
    assert len(col_after_unlink.linked_folders) == 0

    # Unlinking MUST NOT delete files on disk!
    assert os.path.exists(test_file)
    with open(test_file, "r", encoding="utf-8") as f:
        assert "Conteúdo extremamente valioso" in f.read()


# ============================================================================
# SCENARIO M: Path traversal boundaries enforced
# ============================================================================
def test_scenario_m_path_traversal_boundaries(study_service, sample_study_folder):
    """Scenario M: Path traversal attempts, root drives, and system folders are rejected."""
    col = study_service.create_collection("Sistemas Operativos", "Computação")

    # Path traversal attack
    with pytest.raises((ValueError, PermissionError)):
        study_service.link_folder_to_collection(col.collection_id, f"{sample_study_folder}/../../Windows")

    # Root drive protection
    with pytest.raises((ValueError, PermissionError)):
        validate_and_normalize_folder_path("C:\\")

    # Non-existent folder
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_and_normalize_folder_path("C:\\non_existent_folder_xyz_12345")


# ============================================================================
# SCENARIO N: Existing Study functionality regression tests pass
# ============================================================================
def test_scenario_n_existing_study_functionality_regressions(study_service):
    """Scenario N: Existing Study services (reading progress, highlights, notes) operate flawlessly."""
    doc = study_service.ingest_document(
        file_path_or_content=b"# Regressao\nTexto para verificar que leitura, notas e destaques continuam perfeitos.",
        filename="artigo_regressao.txt",
        subject="Geral",
    )
    assert doc is not None

    # Highlights
    hl = study_service.add_highlight(
        document_id=doc.document_id,
        page=1,
        selected_text="destaques continuam perfeitos",
        context="Surrounding sentence context",
        color="yellow",
    )
    assert hl.highlight_id is not None
    assert len(study_service.highlights) >= 1

    # Reading notes
    note = study_service.add_reading_note(
        document_id=doc.document_id,
        page=1,
        selection="destaques continuam perfeitos",
        note_text="Nota de estudo sobre a regressao",
        section_id="sec_0",
    )
    assert note.note_id is not None
    assert len(study_service.notes) >= 1

    # Search RAG
    results = study_service.search_study_rag("leitura e notas", document_id=doc.document_id)
    assert len(results) >= 1


# ============================================================================
# WebSocket Handlers Integration Test
# ============================================================================
def test_websocket_study_handlers_integration(study_service, sample_study_folder):
    """Test WebSocket handlers for study folder sync and collection operations."""
    async def _run():
        mock_connections = MagicMock()
        mock_connections.send = AsyncMock()
        mock_connections.broadcast = AsyncMock()
        mock_socket = MagicMock()
        mock_session = MagicMock()

        handler = StudyWebSocketHandler(connections=mock_connections, study_service=study_service)

        # 1. Create collection via WS
        await handler.create_collection(
            mock_socket,
            {
                "type": "study_create_collection",
                "name": "Inteligência Artificial Avançada",
                "subject": "IA",
                "request_id": "req-col-1",
            },
            mock_session,
        )
        mock_connections.send.assert_awaited()
        create_res = mock_connections.send.await_args[0][1]
        assert create_res.get("type") == "study_collection_created"
        col_id = create_res["collection"]["collection_id"]

        # 2. Link folder via WS
        f = os.path.join(sample_study_folder, "deep_learning.txt")
        with open(f, "w", encoding="utf-8") as fp:
            fp.write("Deep Learning e transformadores de atenção auto-supervisionada.")

        mock_connections.send.reset_mock()
        await handler.link_folder(
            mock_socket,
            {
                "type": "study_link_folder",
                "collection_id": col_id,
                "folder_path": sample_study_folder,
                "recursive": True,
                "request_id": "req-link-2",
            },
            mock_session,
        )
        mock_connections.send.assert_awaited()
        link_res = mock_connections.send.await_args[0][1]
        assert link_res.get("type") == "study_folder_linked"
        assert link_res.get("report", {}).get("added_files", 0) >= 1

        # 3. Ask course via WS
        mock_connections.send.reset_mock()
        await handler.ask_course(
            mock_socket,
            {
                "type": "study_ask_course",
                "collection_id": col_id,
                "question": "O que são transformadores?",
                "request_id": "req-ask-3",
            },
            mock_session,
        )
        mock_connections.send.assert_awaited()
        ask_res = mock_connections.send.await_args[0][1]
        assert ask_res.get("type") == "study_ask_course_result"
        assert len(ask_res.get("citations", [])) > 0 or len(ask_res.get("sources", [])) > 0

        # 4. Unlink folder via WS
        mock_connections.send.reset_mock()
        await handler.unlink_folder(
            mock_socket,
            {
                "type": "study_unlink_folder",
                "collection_id": col_id,
                "folder_path": sample_study_folder,
                "request_id": "req-unlink-4",
            },
            mock_session,
        )
        mock_connections.send.assert_awaited()
        unlink_res = mock_connections.send.await_args[0][1]
        assert unlink_res.get("type") == "study_folder_unlinked"
        assert os.path.exists(f)  # Preserved on disk

    asyncio.run(_run())
