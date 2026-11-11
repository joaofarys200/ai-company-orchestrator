"""
JARVIS OS — Study Engine Phase 7: Live Local Ollama (qwen3.5:9b) Integration Test
Valida em tempo real o fluxo completo via Ollama local (qwen3.5:9b), sem mocks LLM.
Requer serviço Ollama ativo em localhost:11434 com modelo qwen3.5:9b.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import urllib.request

import pytest

from backend.model_harness.runtime import create_runtime_model_harness
from backend.services.model_service import ModelExecutionService
from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ConceptItem,
    CriticalAnalysis,
    CrossSectionSynthesis,
    DocumentCoreAnalysis,
    EpistemicStatus,
    EvidenceRef,
    SectionAnalysis,
)
from services.document_intelligence import (
    ASTParagraph,
    ASTSection,
    AcademicDocumentAST,
    DocumentMetadata,
    PageInfo,
)
from services.editorial_intelligence_engine import (
    EditorialChapter,
    EditorialOverview,
    EditorialPlanMetadata,
    EditorialQAReport,
    EditorialSection,
    EditorialStudyPlan,
)
from services.study_integration import StudyOrchestrationCoordinator
from services.study_service import StudyDocument, StudyService


def _is_ollama_qwen_ready() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in (data.get("models") or [])]
            return any("qwen3.5:9b" in name for name in models)
    except Exception:
        return False


@pytest.mark.skipif(not _is_ollama_qwen_ready(), reason="Ollama local com qwen3.5:9b não acessível em localhost:11434.")
def test_live_ollama_qwen35_study_orchestration_e2e(tmp_path: Path):
    asyncio.run(_run_live_ollama_e2e(tmp_path))


async def _run_live_ollama_e2e(tmp_path: Path):
    svc = StudyService(
        storage_dir=str(tmp_path / "study_data"),
        vault_root=str(tmp_path / "vault"),
        workspace_root=str(tmp_path),
    )
    doc_id = "doc_live_raft"
    doc_dir = svc.storage_dir / "documents" / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    p1 = "No algoritmo Raft, todos os nós iniciam como Follower e um Candidate pede votos quando expira o election timeout."
    p2 = "Quando um Candidate recebe maioria dos votos dos servidores do cluster, torna-se Leader e passa a emitir AppendEntries."
    doc = StudyDocument(
        document_id=doc_id,
        source_id=f"src_{doc_id}",
        title="Algoritmo de Consenso Raft",
        subject="Sistemas Distribuídos",
        source_type="PDF",
        language="pt",
        page_count=2,
        sections=[{"section_id": "sec_01", "title": "1. Eleição de Líder em Raft", "paragraphs": [{"paragraph_id": "p1", "page_number": 1, "text": p1}, {"paragraph_id": "p2", "page_number": 2, "text": p2}]}],
        metadata={"filename": "raft.pdf", "sync_status": "READY"},
    )
    svc.documents[doc_id] = doc
    svc._save_documents()

    ast = AcademicDocumentAST(
        document_id=doc_id,
        source_sha256="sha_live",
        filename="raft.pdf",
        metadata=DocumentMetadata(title="Algoritmo de Consenso Raft"),
        pages=[PageInfo(page_number=1, width=595.0, height=842.0), PageInfo(page_number=2, width=595.0, height=842.0)],
        sections=[ASTSection(section_id="sec_01", title="1. Eleição de Líder em Raft", level=1, page_start=1, page_end=2)],
        paragraphs=[
            ASTParagraph(paragraph_id="p1", section_id="sec_01", text=p1, page_number=1, page_end=1, order=1),
            ASTParagraph(paragraph_id="p2", section_id="sec_01", text=p2, page_number=2, page_end=2, order=2),
        ],
    )
    (doc_dir / "ast.json").write_text(json.dumps(ast.to_dict(), ensure_ascii=False), encoding="utf-8")

    dossier = AcademicReasoningDossier(
        dossier_id="dos_live",
        document_id=doc_id,
        source_sha256="sha_live",
        document_analysis=DocumentCoreAnalysis(document_id=doc_id, title="Algoritmo de Consenso Raft", central_thesis=p1),
        section_analyses=[SectionAnalysis(section_id="sec_01", title="1. Eleição de Líder em Raft", in_depth_synthesis=f"{p1} {p2}", source_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p1", page_number=1, status=EpistemicStatus.SOURCE_FACT.value)])],
        conceptual_analysis=[ConceptItem(concept_id="c1", name="Eleição de Líder Raft", definition=p2)],
        cross_section_synthesis=CrossSectionSynthesis(global_synthesis=p1),
        critical_analysis=CriticalAnalysis(),
    )
    (doc_dir / "reasoning_dossier.json").write_text(json.dumps(dossier.to_dict(), ensure_ascii=False), encoding="utf-8")

    plan = EditorialStudyPlan(
        metadata=EditorialPlanMetadata(plan_id="pl_live", document_id=doc_id, source_sha256="sha_live", ast_version="1.0", dossier_id="dos_live", status="COMPLETED"),
        overview=EditorialOverview(central_theme="Consenso Raft", core_contents=["sec_01"]),
        chapters=[EditorialChapter(chapter_id="ch1", title="Capítulo 1: Eleição de Líder", original_section_ids=["sec_01"], sections=[EditorialSection(section_id="sec_01", chapter_id="ch1", title="1. Eleição", original_section_ids=["sec_01"])])],
        qa_report=EditorialQAReport(validation_status="APPROVED"),
    )
    (doc_dir / "editorial_study_plan.json").write_text(json.dumps(plan.to_dict(), ensure_ascii=False), encoding="utf-8")

    harness = create_runtime_model_harness()
    model_service = ModelExecutionService(harness)
    coord = StudyOrchestrationCoordinator(svc, model_service=model_service)

    # Livre expressão natural que requer entendimento via qwen3.5:9b + explicação fundamentada via qwen3.5:9b
    res = await coord.handle_directive(
        prompt="No algoritmo Raft, como funciona a passagem de um candidato até se tornar líder?",
        chat_session_id="live_ollama_session",
        allow_background=False,
    )
    assert res.status == "COMPLETED"
    assert res.document_id == doc_id
    assert res.epistemic_breakdown is not None
    assert len(res.citations) >= 1
    assert "líder" in res.summary_markdown.lower() or "leader" in res.summary_markdown.lower() or "raft" in res.summary_markdown.lower()
