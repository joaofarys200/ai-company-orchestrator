"""
JARVIS OS — Study Engine Phase 7: Integration & Orchestration Test Suite
Testa de forma determinística e com LLM mockado todos os requisitos da Secção 16:
  16.1 Intent understanding + follow-ups + desambiguação
  16.2 StudyCapabilityRouter + reutilização dos serviços Fases 2–6 + validação
  16.3 Agent & Tool integration (ToolRegistry, profiles, action_validator, StudyToolBridge)
  16.4 Multi-turn context continuity & strict document isolation + persistência após reinício
  16.5 WebSocket contract sync + ChatWebSocketHandler -> OrchestrationService -> ChatMissionBridge -> StudyService
  16.6 Operações assíncronas (IDs, progresso honesto, desduplicação, cancelamento cooperativo, recuperação INTERRUPTED)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from agents.agent_profiles import create_default_agent_profile_registry
from agents.orchestrator.action_validator import classify_tool, validate_next_tool_decision
from agents.orchestrator.task_state import CONTROLLED_STOP, INVALID_WITH_CORRECTION, VALID, TaskState
from agents.study_tools import STUDY_TOOL_NAMES, execute_study_tool, validate_study_tool_arguments
from agents.tools import get_tool_registry
from backend.services.chat_mission_bridge import ChatIntentType, ChatMissionBridge, ChatRequestResolver
from backend.services.orchestration_runtime import OrchestrationCallbacks, OrchestrationService
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import EXPECTED_MESSAGE_TYPES
from backend.websocket.handlers.chat import ChatWebSocketHandler
from backend.websocket.handlers.study import StudyWebSocketHandler
from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ConceptItem,
    CriticalAnalysis,
    CrossSectionSynthesis,
    DocumentCoreAnalysis,
    EpistemicStatus,
    EvidenceRef,
    MethodologyAnalysis,
    ResultItem,
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
    EditorialConceptRelationship,
    EditorialOverview,
    EditorialPlanMetadata,
    EditorialQAReport,
    EditorialSection,
    EditorialStudyPlan,
    PedagogicalExplanationSpec,
)
from services.study_integration import (
    StudyCapabilityRequest,
    StudyCapabilityRouter,
    StudyCapabilityType,
    StudyContextManager,
    StudyOperationManager,
    StudyOrchestrationCoordinator,
)
from services.study_modes_engine import (
    ActiveRecallDeck,
    ActiveRecallPrompt,
    AdaptiveFlashcard,
    FlashcardType,
    ReviewLearningState,
    ReviewSchedulingState,
    StudyDeck,
)
from services.study_service import StudyDocument, StudyService
from websocket_schema import CLIENT_MESSAGE_TYPES, SERVER_MESSAGE_TYPES, normalize_ws_message, validate_client_message


class DummyConnections:
    def __init__(self) -> None:
        self.broadcasts: List[Dict[str, Any]] = []
        self.direct: List[Dict[str, Any]] = []

    async def broadcast(self, msg: Dict[str, Any]) -> None:
        self.broadcasts.append(dict(msg))

    async def send(self, _ws: Any, msg: Dict[str, Any]) -> None:
        self.direct.append(dict(msg))


class DummyMissionStore:
    def __init__(self, root: Path) -> None:
        self.projects_root = str(root / "workspace" / "projects")
        Path(self.projects_root).mkdir(parents=True, exist_ok=True)

    def list_missions(self, _pid: str) -> List[Dict[str, Any]]:
        return []


def _seed_document(
    svc: StudyService,
    *,
    doc_id: str,
    title: str,
    subject: str,
    sec1_text: str,
    sec2_text: str,
    concept_a: str,
    concept_b: str,
) -> StudyDocument:
    doc_dir = svc.storage_dir / "documents" / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    doc = StudyDocument(
        document_id=doc_id,
        source_id=f"src_{doc_id}",
        title=title,
        subject=subject,
        source_type="PDF",
        language="pt",
        page_count=4,
        sections=[
            {
                "section_id": "sec_01",
                "title": "1. Fundamentos Conceptuais",
                "paragraphs": [{"paragraph_id": "p_01", "page_number": 1, "text": sec1_text}],
            },
            {
                "section_id": "sec_02",
                "title": "2. Metodologia Experimental",
                "paragraphs": [{"paragraph_id": "p_02", "page_number": 2, "text": sec2_text}],
            },
        ],
        metadata={"filename": f"{doc_id}.pdf", "sync_status": "READY"},
    )
    svc.documents[doc_id] = doc
    svc._save_documents()

    ast = AcademicDocumentAST(
        document_id=doc_id,
        source_sha256=f"sha_{doc_id}",
        filename=f"{doc_id}.pdf",
        metadata=DocumentMetadata(title=title, abstract=sec1_text),
        pages=[PageInfo(page_number=1, width=595.0, height=842.0), PageInfo(page_number=2, width=595.0, height=842.0)],
        sections=[
            ASTSection(section_id="sec_01", title="1. Fundamentos Conceptuais", level=1, page_start=1, page_end=1, element_refs=[{"kind": "paragraph", "id": "p_01"}]),
            ASTSection(section_id="sec_02", title="2. Metodologia Experimental", level=1, page_start=2, page_end=2, element_refs=[{"kind": "paragraph", "id": "p_02"}]),
        ],
        paragraphs=[
            ASTParagraph(paragraph_id="p_01", section_id="sec_01", text=sec1_text, page_number=1, page_end=1, order=1),
            ASTParagraph(paragraph_id="p_02", section_id="sec_02", text=sec2_text, page_number=2, page_end=2, order=2),
        ],
    )
    (doc_dir / "ast.json").write_text(json.dumps(ast.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    dossier = AcademicReasoningDossier(
        dossier_id=f"dossier_{doc_id}",
        document_id=doc_id,
        source_sha256=f"sha_{doc_id}",
        document_analysis=DocumentCoreAnalysis(
            document_id=doc_id,
            title=title,
            central_thesis=sec1_text,
            global_objective=f"Analisar {concept_a} e {concept_b}.",
        ),
        section_analyses=[
            SectionAnalysis(
                section_id="sec_01",
                title="1. Fundamentos Conceptuais",
                in_depth_synthesis=sec1_text,
                core_ideas=[concept_a],
                source_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, excerpt=sec1_text[:60], status=EpistemicStatus.SOURCE_FACT.value)],
            ),
            SectionAnalysis(
                section_id="sec_02",
                title="2. Metodologia Experimental",
                in_depth_synthesis=sec2_text,
                core_ideas=[concept_b],
                source_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_02", page_number=2, excerpt=sec2_text[:60], status=EpistemicStatus.SOURCE_FACT.value)],
            ),
        ],
        conceptual_analysis=[
            ConceptItem(
                concept_id="c_01",
                name=concept_a,
                definition=sec1_text,
                explanation=sec1_text,
                relationships=["c_02"],
                evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, excerpt=sec1_text[:50], status=EpistemicStatus.SOURCE_FACT.value)],
            ),
            ConceptItem(
                concept_id="c_02",
                name=concept_b,
                definition=sec2_text,
                explanation=sec2_text,
                relationships=["c_01"],
                evidence_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_02", page_number=2, excerpt=sec2_text[:50], status=EpistemicStatus.SOURCE_FACT.value)],
            ),
        ],
        methodology_analysis=MethodologyAnalysis(
            is_applicable=True,
            research_type="Estudo Experimental",
            methodological_design="Comparação controlada",
            methods_used=["k-fold k=10"],
            sample_or_participants="1500 amostras",
            evidence_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_02", page_number=2, excerpt=sec2_text[:50], status=EpistemicStatus.SOURCE_FACT.value)],
        ),
        results_and_evidence=[
            ResultItem(
                statement=f"{concept_b} reduziu erros em 28%.",
                evidence_data="28%",
                evidence_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_02", page_number=2, excerpt=sec2_text[:50], status=EpistemicStatus.SOURCE_FACT.value)],
            )
        ],
        cross_section_synthesis=CrossSectionSynthesis(
            conceptual_relationships=[{"source": "c_01", "target": "c_02", "type": "supports", "description": f"{concept_a} -> {concept_b}"}],
            global_synthesis=f"{concept_a} e {concept_b} estruturam {title}.",
        ),
        critical_analysis=CriticalAnalysis(),
    )
    (doc_dir / "reasoning_dossier.json").write_text(json.dumps(dossier.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    plan = EditorialStudyPlan(
        metadata=EditorialPlanMetadata(
            plan_id=f"plan_{doc_id}",
            document_id=doc_id,
            source_sha256=f"sha_{doc_id}",
            ast_version="1.0",
            dossier_id=f"dossier_{doc_id}",
            plan_version=1,
            created_at="2026-11-11T10:00:00",
            status="COMPLETED",
        ),
        overview=EditorialOverview(
            central_theme=f"{concept_a} & {concept_b}",
            central_theme_status="SOURCE_FACT",
            learning_objectives=[
                {"objective_id": "obj_01", "description": f"Compreender {concept_a}", "epistemic_status": "SOURCE_FACT", "source_section_ids": ["sec_01"]},
                {"objective_id": "obj_02", "description": f"Aplicar {concept_b}", "epistemic_status": "SOURCE_FACT", "source_section_ids": ["sec_02"]},
            ],
            core_contents=["sec_01", "sec_02"],
        ),
        chapters=[
            EditorialChapter(
                chapter_id="chap_01",
                title=f"Capítulo 1: {concept_a}",
                pedagogical_objective=f"Dominar {concept_a}",
                key_concept_ids=["c_01"],
                original_section_ids=["sec_01"],
                sections=[
                    EditorialSection(
                        section_id="sec_01",
                        chapter_id="chap_01",
                        title=concept_a,
                        order=1,
                        associated_concept_ids=["c_01"],
                        original_section_ids=["sec_01"],
                        pedagogical_treatments=[PedagogicalExplanationSpec(target_topic_or_concept=concept_a, concept_id="c_01", depth_level="FOUNDATIONAL", epistemic_status="SOURCE_FACT")],
                    )
                ],
            ),
            EditorialChapter(
                chapter_id="chap_02",
                title="Capítulo 2: Metodologia Experimental e Resultados",
                pedagogical_objective=f"Avaliar {concept_b}",
                key_concept_ids=["c_02"],
                original_section_ids=["sec_02"],
                sections=[
                    EditorialSection(
                        section_id="sec_02",
                        chapter_id="chap_02",
                        title="Metodologia Experimental",
                        order=1,
                        associated_concept_ids=["c_02"],
                        original_section_ids=["sec_02"],
                        pedagogical_treatments=[PedagogicalExplanationSpec(target_topic_or_concept=concept_b, concept_id="c_02", depth_level="IN_DEPTH", epistemic_status="SOURCE_FACT")],
                    )
                ],
            ),
        ],
        conceptual_relationships=[
            EditorialConceptRelationship(
                relationship_id="rel_01",
                source_concept_id="c_01",
                source_concept_name=concept_a,
                target_concept_id="c_02",
                target_concept_name=concept_b,
                relation_type="complementa",
                pedagogical_dependency=f"Estudar {concept_a} primeiro.",
            )
        ],
        qa_report=EditorialQAReport(validation_status="APPROVED"),
    )
    (doc_dir / "editorial_study_plan.json").write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    # Seed Phase 6 deck + active recall prompts + SRS via real engines
    fc1 = AdaptiveFlashcard(
        card_id=f"fc_{doc_id}_1",
        document_id=doc_id,
        chapter_id="chap_01",
        section_id="sec_01",
        front=f"O que define {concept_a}?",
        back=sec1_text,
        card_type=FlashcardType.CONCEPTUAL_UNDERSTANDING.value,
        topic=concept_a,
        question_difficulty="MEDIUM",
    )
    fc2 = AdaptiveFlashcard(
        card_id=f"fc_{doc_id}_2",
        document_id=doc_id,
        chapter_id="chap_02",
        section_id="sec_02",
        front=f"Como atua {concept_b} na metodologia?",
        back=sec2_text,
        card_type=FlashcardType.APPLICATION.value,
        topic="Metodologia Experimental",
        question_difficulty="HARD",
    )
    deck = StudyDeck(deck_id=f"deck_{doc_id}", document_id=doc_id, title=f"Deck — {title}", cards=[fc1, fc2])
    svc.study_modes.flashcards.save_deck(deck)

    ar1 = ActiveRecallPrompt(
        prompt_id=f"ar_{doc_id}_1",
        document_id=doc_id,
        chapter_id="chap_02",
        section_id="sec_02",
        prompt_text=f"Explica por palavras tuas a relevância de {concept_b}.",
        grounded_reference_answer=sec2_text,
        topic="Metodologia Experimental",
        key_points_expected=[concept_b],
    )
    recall_deck = ActiveRecallDeck(document_id=doc_id, prompts=[ar1])
    svc.study_modes.active_recall.save_deck(recall_deck)

    svc.study_modes.srs.register_items([
        ReviewSchedulingState(
            item_id=fc1.card_id,
            item_type="flashcard",
            document_id=doc_id,
            chapter_id="chap_01",
            section_id="sec_01",
            topic=concept_a,
            next_review_ts=0.0,
            learning_state=ReviewLearningState.DUE.value,
        ),
        ReviewSchedulingState(
            item_id=fc2.card_id,
            item_type="flashcard",
            document_id=doc_id,
            chapter_id="chap_02",
            section_id="sec_02",
            topic="Metodologia Experimental",
            next_review_ts=time.time() - 100.0,
            learning_state=ReviewLearningState.DUE.value,
        ),
        ReviewSchedulingState(
            item_id=ar1.prompt_id,
            item_type="active_recall",
            document_id=doc_id,
            chapter_id="chap_02",
            section_id="sec_02",
            topic="Metodologia Experimental",
            next_review_ts=0.0,
            learning_state=ReviewLearningState.DUE.value,
        ),
    ])
    return doc


def _fake_explain_llm(**kwargs: Any) -> Dict[str, Any]:
    return {
        "answer_intro": "Síntese fundamentada com base nas passagens verificadas do documento.",
        "claims": [
            {
                "statement": "A passagem descreve exatamente o mecanismo citado na secção analisada.",
                "epistemic_status": "SOURCE_FACT",
                "citations": ["p. 1, § 1. Fundamentos Conceptuais", "p. 2, § 2. Metodologia Experimental"],
            },
            {
                "statement": "Inferência pedagógica: convém rever os fundamentos antes dos ensaios.",
                "epistemic_status": "MODEL_INFERENCE",
                "citations": ["p. 2, § 2. Metodologia Experimental"],
            },
            {
                "statement": "Citação inventada que deve ser rebaixada pelo validador epistémico.",
                "epistemic_status": "SOURCE_FACT",
                "citations": ["p. 999, § Secção Fantasma"],
            },
        ],
        "missing_information": "Custos financeiros detalhados não constam na fonte.",
        "concepts": ["Raft Consensus", "Validação Cruzada"],
    }


def _fake_phase6_llm(*, operation: str, system_prompt: str = "", user_prompt: str = "", **_kwargs: Any) -> Dict[str, Any]:
    op = operation.lower()
    if "phase6_assessment" in op:
        q_templates = [
            ("Qual o mecanismo de eleição em Raft Consensus?", "MULTIPLE_CHOICE", "sec_01", "Raft Consensus"),
            ("Verdadeiro ou Falso: A validação cruzada mede tolerância abaixo de 72ms.", "TRUE_FALSE", "sec_02", "Metodologia Experimental"),
            ("Explica a importância da validação cruzada k-fold no protocolo experimental.", "CONCEPT_EXPLANATION", "sec_02", "Metodologia Experimental"),
            ("Como compara a abordagem de líder único com tolerância a falhas controlada?", "COMPARISON", "sec_02", "Metodologia Experimental"),
            ("Como aplicarias eleição de líder por mandato num cluster distribuído?", "APPLICATION_SCENARIO", "sec_01", "Raft Consensus"),
            ("Analisa os impactos da latência inferior a 72ms nos resultados obtidos.", "ANALYTICAL", "sec_02", "Metodologia Experimental"),
        ]
        return {
            "ok": True,
            "parsed": {
                "questions": [
                    {
                        "question_text": qtxt,
                        "question_type": qtype,
                        "question_difficulty": "HARD",
                        "section_id": sec_id,
                        "topic": qtopic,
                        "concept_ids": ["c_02" if sec_id == "sec_02" else "c_01"],
                        "options": (
                            ["Verdadeiro", "Falso"]
                            if qtype == "TRUE_FALSE"
                            else [
                                "Validação cruzada k-fold mede tolerância a falhas abaixo de 72ms",
                                "Armazenamento local em ficheiro único sem replicação",
                                "Execução aleatória sem controlo de amostras",
                                "Nenhum protocolo experimental foi aplicado",
                            ]
                            if qtype == "MULTIPLE_CHOICE"
                            else []
                        ),
                        "correct_index": 0,
                        "correct_answer": "Verdadeiro" if qtype == "TRUE_FALSE" else "Validação cruzada k-fold garante tolerância a falhas e coerência abaixo de 72ms.",
                        "explanation": "Registado diretamente nas páginas 1 e 2 da fonte.",
                        "epistemic_status": "SOURCE_FACT",
                        "evidence_refs": [{"section_id": sec_id, "paragraph_id": "p_02" if sec_id == "sec_02" else "p_01", "page_number": 2 if sec_id == "sec_02" else 1, "status": "SOURCE_FACT"}],
                    }
                    for qtxt, qtype, sec_id, qtopic in q_templates
                ]
            },
            "prompt_tokens": 100,
            "completion_tokens": 150,
        }
    if "phase6_cornell" in op:
        return {
            "ok": True,
            "parsed": {
                "sections": [
                    {
                        "section_id": "sec_01",
                        "main_concepts": [{"name": "Raft Consensus", "note": "Coerência replicada por líder"}],
                        "explanations": ["Raft elege um líder único por mandato."],
                        "supporting_details": ["Coerência replicada garantida."],
                        "cue_column": [{"cue_prompt": "Como garante Raft coerência?", "cue_type": "PORQUÊ", "answer_hint": "Líder único por mandato.", "epistemic_status": "SOURCE_FACT", "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}]}],
                        "summary_section": "Fundamentos de Raft.",
                        "epistemic_status": "SOURCE_FACT",
                        "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}],
                    },
                    {
                        "section_id": "sec_02",
                        "main_concepts": [{"name": "Validação Cruzada", "note": "k-fold < 72ms"}],
                        "explanations": ["Mede tolerância a falhas abaixo de 72ms."],
                        "supporting_details": ["1500 amostras em comparação controlada."],
                        "cue_column": [{"cue_prompt": "O que mede k-fold?", "cue_type": "METODOLOGIA", "answer_hint": "Tolerância a falhas abaixo de 72ms.", "epistemic_status": "SOURCE_FACT", "evidence_refs": [{"section_id": "sec_02", "paragraph_id": "p_02", "page_number": 2, "status": "SOURCE_FACT"}]}],
                        "summary_section": "Metodologia experimental.",
                        "epistemic_status": "SOURCE_FACT",
                        "evidence_refs": [{"section_id": "sec_02", "paragraph_id": "p_02", "page_number": 2, "status": "SOURCE_FACT"}],
                    },
                ]
            },
            "prompt_tokens": 100,
            "completion_tokens": 120,
        }
    return {"ok": True, "parsed": {"cards": [], "prompts": []}, "prompt_tokens": 20, "completion_tokens": 20}


def _build_study_service(tmp_path: Path) -> StudyService:
    study_dir = tmp_path / "study_data"
    vault_dir = tmp_path / "obsidian_vault"
    svc = StudyService(storage_dir=str(study_dir), vault_root=str(vault_dir), workspace_root=str(tmp_path))
    svc.study_modes.llm_caller = _fake_phase6_llm
    _seed_document(
        svc,
        doc_id="doc_raft",
        title="Consenso Distribuído com Raft",
        subject="Sistemas Distribuídos",
        sec1_text="Raft Consensus garante coerência replicada elegendo um líder único por mandato.",
        sec2_text="Validação Cruzada k-fold mede tolerância a falhas com latência inferior a 72ms.",
        concept_a="Raft Consensus",
        concept_b="Validação Cruzada",
    )
    _seed_document(
        svc,
        doc_id="doc_vision",
        title="Arquiteturas de Visão Computacional",
        subject="Visão Por Computador",
        sec1_text="Transformers Visuais dividem imagens em patches lineares.",
        sec2_text="Atenção multi-cabeça melhora deteção de objetos pequenos.",
        concept_a="Vision Transformer",
        concept_b="Multi-Head Attention",
    )
    return svc


# ---------------------------------------------------------------------------
# 16.1 & 16.2 Intent, Routing, Validation & Epistemic Rigor
# ---------------------------------------------------------------------------

def test_resolver_distinguishes_study_and_coding_directives():
    resolver = ChatRequestResolver()

    study_prompts = [
        "Analisa este PDF e prepara o material de estudo.",
        "Explica-me o segundo capítulo.",
        "Cria flashcards sobre a metodologia.",
        "Faz-me um teste sobre os resultados.",
        "Quero rever os cartões que tenho pendentes.",
        "Mostra-me os assuntos em que tenho mais dificuldades.",
        "Continua a sessão de estudo que deixei ontem.",
        "Cria Cornell Notes para este capítulo.",
    ]
    for p in study_prompts:
        res = resolver.resolve_request(p)
        assert res.intent == ChatIntentType.STUDY_OPERATION, f"Falhou deteção Study em: {p}"

    coding_prompts = [
        "Executa pytest no projeto task-app",
        "Corrige o ficheiro app.js no projeto dina",
        "Cria um endpoint FastAPI com autenticação JWT no backend",
    ]
    for cp in coding_prompts:
        res = resolver.resolve_request(cp)
        assert res.intent != ChatIntentType.STUDY_OPERATION, f"Coding prompt sequestrado por Study: {cp}"


def test_capability_router_validation_errors_and_reuse(tmp_path: Path):
    asyncio.run(_test_capability_router_validation_errors_and_reuse(tmp_path))


async def _test_capability_router_validation_errors_and_reuse(tmp_path: Path):
    svc = _build_study_service(tmp_path)
    coord = StudyOrchestrationCoordinator(svc, explain_llm_caller=_fake_explain_llm)
    router = coord.router

    # Invalid count rejected explicitly
    bad_req = StudyCapabilityRequest(
        capability=StudyCapabilityType.CREATE_ASSESSMENT,
        document_id="doc_raft",
        question_count=99,
    )
    bad_res = await router.execute(bad_req, allow_background=False)
    assert bad_res.status == "FAILED"
    assert bad_res.error_code == "INVALID_ARGUMENTS"

    # Nonexistent chapter rejected without hallucinating content
    bad_chap = StudyCapabilityRequest(
        capability=StudyCapabilityType.EXPLAIN_CONCEPT_OR_CHAPTER,
        document_id="doc_raft",
        chapter_ref="capítulo 99",
        raw_prompt="Explica o capítulo 99",
    )
    bad_chap_res = await router.execute(bad_chap, allow_background=False)
    assert bad_chap_res.status == "FAILED"
    assert bad_chap_res.error_code == "INVALID_CHAPTER_OR_SECTION"

    # Processing guard
    svc.documents["doc_raft"].metadata["sync_status"] = "PROCESSING"
    proc_res = await router.execute(
        StudyCapabilityRequest(capability=StudyCapabilityType.GENERATE_FLASHCARDS, document_id="doc_raft"),
        allow_background=False,
    )
    assert proc_res.error_code == "DOCUMENT_PROCESSING"
    svc.documents["doc_raft"].metadata["sync_status"] = "READY"

    # Outside workspace path traversal rejected
    trav_res = await router.execute(
        StudyCapabilityRequest(capability=StudyCapabilityType.INGEST_DOCUMENT, file_path="../../../etc/passwd"),
        allow_background=False,
    )
    assert trav_res.status == "FAILED"
    assert trav_res.error_code == "PATH_OUTSIDE_BOUNDARY"

    # Existing dossier reused cleanly without wasteful recompute
    reuse_res = await router.execute(
        StudyCapabilityRequest(capability=StudyCapabilityType.ANALYSE_DOCUMENT, document_id="doc_raft"),
        allow_background=False,
    )
    assert reuse_res.status == "COMPLETED"
    assert reuse_res.result_ref.get("reused_cached") is True

    # Epistemic rigor: fabricated citation on phantom page must be downgraded (never kept as SOURCE_FACT)
    exp_res = await router.execute(
        StudyCapabilityRequest(
            capability=StudyCapabilityType.EXPLAIN_CONCEPT_OR_CHAPTER,
            document_id="doc_raft",
            chapter_ref="capítulo 2",
            question="Explica a metodologia experimental.",
            raw_prompt="Explica o capítulo 2",
        ),
        allow_background=False,
    )
    assert exp_res.status == "COMPLETED"
    claims = exp_res.epistemic_breakdown["claims"]
    phantom_claim = [c for c in claims if "fantasma" in c["statement"].lower() or "inventada" in c["statement"].lower()][0]
    assert phantom_claim["epistemic_status"] != "SOURCE_FACT"
    assert phantom_claim["citations"] == []

    # Topic absent from document must honestly return NOT_FOUND without hallucination
    not_found_res = await router.execute(
        StudyCapabilityRequest(
            capability=StudyCapabilityType.EXPLAIN_CONCEPT_OR_CHAPTER,
            document_id="doc_raft",
            question="Qual a receita de bacalhau à Brás na termodinâmica quântica?",
            raw_prompt="Explica termodinâmica quântica e bacalhau",
        ),
        allow_background=False,
    )
    assert not_found_res.epistemic_breakdown["primary_status"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# 16.3 Agent & Tool Integration
# ---------------------------------------------------------------------------

def test_agent_tools_registry_permissions_and_execution(tmp_path: Path):
    asyncio.run(_test_agent_tools_registry_permissions_and_execution(tmp_path))


async def _test_agent_tools_registry_permissions_and_execution(tmp_path: Path):
    svc = _build_study_service(tmp_path)
    registry = get_tool_registry()
    for name in STUDY_TOOL_NAMES:
        meta = registry.get(name)
        assert "study" in meta.permissions

    profiles = create_default_agent_profile_registry()
    alex = profiles.get("alex")
    devon = profiles.get("devon")
    assert "study_list_documents" in alex.allowed_tools
    assert "study_list_documents" not in devon.allowed_tools

    # Orchestrator action_validator enforces Study schemas cleanly
    assert classify_tool("study_list_documents") == "estudo"
    ts = TaskState(objective_declared=True, objective="Analisar progresso")
    assert validate_next_tool_decision("Listar docs", ts, "study_list_documents", {}).status == VALID
    bad_dec = validate_next_tool_decision("Quiz", ts, "study_create_assessment", {"document_id": "doc_raft", "question_count": 999})
    assert bad_dec.status == INVALID_WITH_CORRECTION

    # Argument injection & unknown tools are rejected
    with pytest.raises(ValueError):
        validate_study_tool_arguments("study_unknown_exec", {"cmd": "rm -rf /"})
    with pytest.raises(ValueError):
        validate_study_tool_arguments("study_get_document_status", {"document_id": "../secret"})

    out = json.loads(
        await execute_study_tool(
            "study_create_assessment",
            {"document_id": "doc_raft", "topic": "Metodologia Experimental", "question_count": 4, "difficulty": "HARD"},
            study_service=svc,
        )
    )
    assert out["status"] == "COMPLETED"
    assert out["document_id"] == "doc_raft"
    assert out["result_ref"]["question_count"] == 4


# ---------------------------------------------------------------------------
# 16.4 Multi-turn Context Continuity, Disambiguation & Isolation
# ---------------------------------------------------------------------------

def test_multiturn_study_continuity_isolation_and_restart_persistence(tmp_path: Path):
    asyncio.run(_test_multiturn_study_continuity_isolation_and_restart_persistence(tmp_path))


async def _test_multiturn_study_continuity_isolation_and_restart_persistence(tmp_path: Path):
    svc = _build_study_service(tmp_path)
    coord = StudyOrchestrationCoordinator(svc, explain_llm_caller=_fake_explain_llm)
    chat_sid = "conv_phase7_continuity"

    # Ambiguous request with 2 documents and no active doc bound must clarify rather than guess
    amb = await coord.handle_directive(
        prompt="Cria flashcards sobre este documento.",
        chat_session_id=chat_sid,
        allow_background=False,
    )
    assert amb.status == "NEEDS_CLARIFICATION"
    assert len(amb.clarification_options) == 2

    # 1. Select Doc A explicitly (via UI context or title)
    step1 = await coord.handle_directive(
        prompt='Quero estudar o documento "Consenso Distribuído com Raft"',
        chat_session_id=chat_sid,
        allow_background=False,
    )
    assert step1.status == "COMPLETED"
    assert step1.document_id == "doc_raft"

    # 2. Request flashcards on active document
    step2 = await coord.handle_directive(
        prompt="Cria flashcards sobre este documento.",
        chat_session_id=chat_sid,
        allow_background=False,
    )
    assert step2.status == "COMPLETED"
    assert step2.document_id == "doc_raft"

    # 3. Restrict to methodology in follow-up ("Agora faz o mesmo, mas apenas sobre a metodologia")
    step3 = await coord.handle_directive(
        prompt="Agora faz o mesmo, mas apenas sobre a metodologia.",
        chat_session_id=chat_sid,
        allow_background=False,
    )
    assert step3.status == "COMPLETED"
    assert step3.document_id == "doc_raft"
    assert step3.result_ref.get("matching_cards", 0) >= 1

    # 4. Ask for harder questions ("Quero algo mais difícil" / "Faz mais cinco perguntas")
    step4 = await coord.handle_directive(
        prompt="Agora faz mais cinco perguntas mais difíceis.",
        chat_session_id=chat_sid,
        allow_background=False,
    )
    assert step4.status == "COMPLETED"
    assert step4.document_id == "doc_raft"
    assert step4.result_ref.get("question_count") == 5
    assert step4.result_ref.get("difficulty") == "HARD"

    # 5. Start daily review session and verify mixed items
    step5 = await coord.handle_directive(
        prompt="Quero rever os cartões que tenho pendentes.",
        chat_session_id=chat_sid,
        allow_background=False,
    )
    assert step5.status == "COMPLETED"
    assert step5.document_id == "doc_raft"
    session_id = step5.study_session_id
    assert session_id
    svc.pause_study_session(session_id)

    # Simulate application restart by reconstructing ContextManager + Coordinator from disk!
    coord_restarted = StudyOrchestrationCoordinator(svc, explain_llm_caller=_fake_explain_llm)
    step6 = await coord_restarted.handle_directive(
        prompt="Continua a sessão de estudo que deixei ontem.",
        chat_session_id=chat_sid,
        allow_background=False,
    )
    assert step6.status == "COMPLETED"
    assert step6.study_session_id == session_id
    assert step6.document_id == "doc_raft"
    assert step6.navigation is not None
    assert step6.auto_navigate is True

    # Isolation check: asking explicitly about Doc B switches context cleanly and drops old session/topic
    step_doc_b = await coord_restarted.handle_directive(
        prompt='Mostra-me o meu progresso no documento "Arquiteturas de Visão Computacional"',
        chat_session_id=chat_sid,
        allow_background=False,
    )
    assert step_doc_b.status == "COMPLETED"
    assert step_doc_b.document_id == "doc_vision"
    new_ctx = coord_restarted.context_manager.get_context(chat_sid)
    assert new_ctx.active_document_id == "doc_vision"
    assert new_ctx.active_study_session_id is None


# ---------------------------------------------------------------------------
# 16.5 & 16.6 Full ChatWebSocket -> OrchestrationService -> Bridge & Async Ops
# ---------------------------------------------------------------------------

def test_websocket_schema_and_end_to_end_chat_pipeline(tmp_path: Path):
    asyncio.run(_test_websocket_schema_and_end_to_end_chat_pipeline(tmp_path))


async def _test_websocket_schema_and_end_to_end_chat_pipeline(tmp_path: Path):
    # Contract invariant: CLIENT_MESSAGE_TYPES == EXPECTED_MESSAGE_TYPES
    assert frozenset(CLIENT_MESSAGE_TYPES) == EXPECTED_MESSAGE_TYPES
    assert "study_cancel_operation" in CLIENT_MESSAGE_TYPES
    assert "study_operation_status" in SERVER_MESSAGE_TYPES
    assert "study_navigate" in SERVER_MESSAGE_TYPES

    validated_cancel = validate_client_message({"type": "study_cancel_operation", "operation_id": "studyop_123"})
    assert validated_cancel["operation_id"] == "studyop_123"

    normalized_chat = normalize_ws_message({
        "type": "chat",
        "sender": "JARVIS",
        "role": "Tutor Académico",
        "content": "Resumo pronto",
        "study_card": {"operation_id": "op_1", "capability": "LIST_DOCUMENTS", "status": "COMPLETED"},
    })
    assert normalized_chat["study_card"]["operation_id"] == "op_1"

    svc = _build_study_service(tmp_path)
    conns = DummyConnections()
    history: List[Dict[str, Any]] = []
    coord = StudyOrchestrationCoordinator(svc, explain_llm_caller=_fake_explain_llm)
    setattr(svc, "_study_coordinator", coord)

    fake_app_services = SimpleNamespace(
        database=SimpleNamespace(create_session=lambda prompt: SimpleNamespace(id=42)),
        agents=None,
        sandbox=None,
        model_harness=None,
        project_context=None,
        coding_sessions=None,
        mission_planner=SimpleNamespace(mission_state=DummyMissionStore(tmp_path)),
        mission_executor=None,
        mission_autonomy=None,
        sentinel_watchdog=None,
        study_service=svc,
    )
    orch = OrchestrationService(
        services=fake_app_services,
        models=SimpleNamespace(),
        connections=conns,
        callbacks=OrchestrationCallbacks(
            broadcast_state=lambda v: conns.broadcast({"type": "state", "value": v}),
            open_local_application=lambda *_: None,
            run_in_main_loop=lambda *_: None,
            on_agent_message=lambda *_: None,
            on_file_update=lambda *_: None,
            on_kanban_update=lambda *_: None,
            build_template_payload=lambda t: {},
        ),
        conversation_history=history,
        logger=__import__("logging").getLogger("test_phase7_orch"),
    )

    chat_handler = ChatWebSocketHandler(
        connections=conns,
        database=fake_app_services.database,
        agents=None,
        callbacks=SimpleNamespace(
            conversation_history=history,
            handle_slash_command=lambda *a, **k: None,
            parse_file_context=lambda p: p,
            broadcast_state=lambda v: conns.broadcast({"type": "state", "value": v}),
            run_orchestration_task=lambda prompt, sid, project_id=None, correlation_id=None, study_context=None: orch.run_task(
                prompt, sid, project_id=project_id, correlation_id=correlation_id, study_context=study_context
            ),
        ),
        logger=__import__("logging").getLogger("test_phase7_ws"),
    )

    ws_client = object()
    await chat_handler.directive(
        ws_client,
        {
            "type": "directive",
            "text": "Quero rever os cartões que tenho pendentes.",
            "correlation_id": "corr_ws_01",
            "study_context": {"document_id": "doc_raft", "tab": "reader", "chat_session_id": "ws_thread_1"},
        },
        WebSocketSessionState(),
    )
    # Await spawned background asyncio task from handler.directive
    await asyncio.sleep(0.2)

    chat_msgs = [b for b in conns.broadcasts if b.get("type") == "chat"]
    nav_msgs = [b for b in conns.broadcasts if b.get("type") == "study_navigate"]
    assert any(m.get("study_card", {}).get("capability") == "START_DAILY_REVIEW" for m in chat_msgs)
    assert any(m.get("navigation", {}).get("document_id") == "doc_raft" for m in nav_msgs)


def test_async_operation_dedup_cancellation_and_interrupted_recovery(tmp_path: Path):
    asyncio.run(_test_async_operation_dedup_cancellation_and_interrupted_recovery(tmp_path))


async def _test_async_operation_dedup_cancellation_and_interrupted_recovery(tmp_path: Path):
    storage_dir = tmp_path / "op_mgr"
    mgr = StudyOperationManager(storage_dir=storage_dir)
    events: List[Dict[str, Any]] = []
    release_ev = threading.Event()
    calls = 0

    def slow_worker(emit_prog, cancel_ev):
        nonlocal calls
        calls += 1
        emit_prog("EXTRACTING", 0.25, "Passo 1")
        while not release_ev.is_set() and not cancel_ev.is_set():
            time.sleep(0.02)
        if cancel_ev.is_set():
            return {"cancelled": True}
        return {"summary_markdown": "Pronto", "result_ref": {"ok": True}}

    async def on_evt(rec):
        events.append(rec.to_dict())

    rec1, dedup1 = await mgr.submit_operation(
        capability="CREATE_ASSESSMENT",
        document_id="doc_raft",
        chat_session_id="s1",
        correlation_id="c1",
        dedup_key="CREATE_ASSESSMENT:doc_raft:1",
        worker_fn=slow_worker,
        on_status_event=on_evt,
    )
    assert not dedup1
    rec2, dedup2 = await mgr.submit_operation(
        capability="CREATE_ASSESSMENT",
        document_id="doc_raft",
        chat_session_id="s1",
        correlation_id="c2",
        dedup_key="CREATE_ASSESSMENT:doc_raft:1",
        worker_fn=slow_worker,
        on_status_event=on_evt,
    )
    assert dedup2 is True
    assert rec2.operation_id == rec1.operation_id

    # Cancellation through StudyWebSocketHandler
    conns = DummyConnections()
    svc = _build_study_service(tmp_path)
    coord = StudyOrchestrationCoordinator(svc)
    coord.operation_manager = mgr
    setattr(svc, "_study_coordinator", coord)
    ws_study = StudyWebSocketHandler(connections=conns, study_service=svc)

    await ws_study.cancel_operation(object(), {"operation_id": rec1.operation_id, "request_id": "r_cancel"}, WebSocketSessionState())
    # Honest intermediate status: CANCELLING before worker finishes unwind
    assert conns.direct[0]["operation"]["stage"] in {"CANCELLING", "CANCELLED"}
    await asyncio.sleep(0.15)
    final = mgr.get_operation(rec1.operation_id)
    assert final is not None and final.status == "CANCELLED"
    assert calls == 1

    # Restart recovery marks in-flight RUNNING ops as INTERRUPTED
    raw_ops = json.loads((storage_dir / "study_operations.json").read_text(encoding="utf-8"))
    raw_ops.append({
        "operation_id": "studyop_orphan",
        "correlation_id": "c_orphan",
        "chat_session_id": "s1",
        "capability": "ANALYSE_DOCUMENT",
        "document_id": "doc_raft",
        "status": "RUNNING",
        "stage": "REASONING",
    })
    (storage_dir / "study_operations.json").write_text(json.dumps(raw_ops), encoding="utf-8")

    mgr_restarted = StudyOperationManager(storage_dir=storage_dir)
    recovered = mgr_restarted.get_operation("studyop_orphan")
    assert recovered is not None
    assert recovered.status == "INTERRUPTED"


def test_ollama_unavailable_reports_honest_failure(tmp_path: Path):
    asyncio.run(_test_ollama_unavailable_reports_honest_failure(tmp_path))


async def _test_ollama_unavailable_reports_honest_failure(tmp_path: Path):
    svc = _build_study_service(tmp_path)

    class OfflineModels:
        async def execute(self, **_kwargs):
            raise ConnectionError("Ollama connection refused")

    coord = StudyOrchestrationCoordinator(svc, model_service=OfflineModels())
    res = await coord.handle_directive(
        prompt='Explica o segundo capítulo do documento "Consenso Distribuído com Raft"',
        chat_session_id="offline_test",
        allow_background=False,
    )
    assert res.status == "FAILED"
    assert res.error_code == "OLLAMA_UNAVAILABLE"


def test_llm_intent_extraction_cornell_recall_compare_and_ui_sync(tmp_path: Path):
    asyncio.run(_test_llm_intent_extraction_cornell_recall_compare_and_ui_sync(tmp_path))


async def _test_llm_intent_extraction_cornell_recall_compare_and_ui_sync(tmp_path: Path):
    svc = _build_study_service(tmp_path)

    # 1. Free-form intent via mocked local qwen3.5 JSON caller
    def fake_intent_llm(**_kwargs: Any) -> Dict[str, Any]:
        return {
            "capability": "GENERATE_CORNELL_NOTES",
            "document_query": "Consenso Distribuído com Raft",
            "topic": "Metodologia",
        }

    coord = StudyOrchestrationCoordinator(
        svc,
        intent_llm_caller=fake_intent_llm,
        explain_llm_caller=_fake_explain_llm,
    )
    res_cornell = await coord.handle_directive(
        prompt="Organiza o material em síntese de duas colunas com pistas laterais para estudar.",
        chat_session_id="s_llm_intent",
        allow_background=False,
    )
    assert res_cornell.status == "COMPLETED"
    assert res_cornell.capability == "GENERATE_CORNELL_NOTES"
    assert res_cornell.document_id == "doc_raft"
    assert res_cornell.navigation and res_cornell.navigation.tab == "notes"

    # Reject unknown/invented capability returned by malformed LLM output
    coord_bad_llm = StudyOrchestrationCoordinator(
        svc,
        intent_llm_caller=lambda **_: {"capability": "RUN_ARBITRARY_SHELL_CMD", "cmd": "whoami"},
    )
    bad_llm_res = await coord_bad_llm.handle_directive(
        prompt="Algo ambíguo fora das capacidades",
        chat_session_id="s_bad_llm",
        allow_background=False,
    )
    assert bad_llm_res.status == "FAILED"
    assert bad_llm_res.error_code == "INTENT_EXTRACTION_FAILED"

    # 2. Concept explanation populates recent_concepts -> enables "Explica a diferença entre estes dois conceitos"
    exp = await coord.handle_directive(
        prompt='Explica o segundo capítulo do documento "Consenso Distribuído com Raft"',
        chat_session_id="s_llm_intent",
        allow_background=False,
    )
    assert exp.status == "COMPLETED"
    comp = await coord.handle_directive(
        prompt="Explica a diferença entre estes dois conceitos.",
        chat_session_id="s_llm_intent",
        allow_background=False,
    )
    assert comp.status == "COMPLETED"
    assert comp.capability == "COMPARE_CONCEPTS"
    assert comp.document_id == "doc_raft"

    # 3. Active Recall cycle: prompt -> submit response -> reveal answer -> check knowledge gaps
    ar_start = await coord.handle_directive(
        prompt="Faz-me perguntas para testar se realmente compreendi este tema.",
        chat_session_id="s_llm_intent",
        allow_background=False,
    )
    assert ar_start.status == "COMPLETED"
    assert ar_start.capability == "START_ACTIVE_RECALL"
    assert ar_start.result_ref.get("prompt_id") == "ar_doc_raft_1"

    ar_submit = await coord.handle_directive(
        prompt="A validação cruzada k-fold mede a tolerância a falhas e garante latência inferior a 72ms.",
        chat_session_id="s_llm_intent",
        allow_background=False,
    )
    assert ar_submit.status == "COMPLETED"
    assert ar_submit.capability == "SUBMIT_ACTIVE_RECALL"

    ar_reveal = await coord.handle_directive(
        prompt="Mostra-me a resposta.",
        chat_session_id="s_llm_intent",
        allow_background=False,
    )
    assert ar_reveal.status == "COMPLETED"
    assert ar_reveal.result_ref.get("revealed") is True

    gaps_res = await coord.handle_directive(
        prompt="Mostra-me os assuntos em que tenho mais dificuldades.",
        chat_session_id="s_llm_intent",
        allow_background=False,
    )
    assert gaps_res.status == "COMPLETED"
    assert gaps_res.capability == "GET_KNOWLEDGE_GAPS"
    assert gaps_res.navigation and gaps_res.navigation.tab == "adaptive"

    # 4. UI study context pins document cleanly without overriding doc_raft in another thread
    ui_res = await coord.handle_directive(
        prompt="Cria flashcards sobre isto.",
        chat_session_id="s_ui_pinned",
        ui_study_context={"document_id": "doc_vision", "tab": "reader"},
        allow_background=False,
    )
    assert ui_res.status == "COMPLETED"
    assert ui_res.document_id == "doc_vision"
    assert coord.context_manager.get_context("s_llm_intent").active_document_id == "doc_raft"

