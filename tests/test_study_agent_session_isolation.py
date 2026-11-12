"""
Regression tests for Agent Session Context Isolation (Phase 7 corrective pass).
Exercises the real WebSocket -> OrchestrationService -> run_jarvis_orchestration ->
spawn_specialist_agent -> execute_study_tool -> StudyCapabilityRouter execution paths.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock

import pytest

import agents.orchestrator as orch_mod
from agents.study_tools import execute_study_tool
from backend.services.chat_command_service import ChatCommandCallbacks, ChatCommandService
from backend.services.chat_mission_bridge import ChatMissionBridge
from backend.services.orchestration_runtime import OrchestrationCallbacks, OrchestrationService
from backend.websocket.context import WebSocketSessionState
from backend.websocket.handlers.chat import ChatWebSocketHandler
import server as server_mod
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


class _DummyConnections:
    def __init__(self) -> None:
        self.broadcasts: List[Dict[str, Any]] = []
        self.direct: List[Dict[str, Any]] = []

    async def broadcast(self, msg: Dict[str, Any]) -> None:
        self.broadcasts.append(dict(msg))

    async def send(self, _ws: Any, msg: Dict[str, Any]) -> None:
        self.direct.append(dict(msg))


class _DummyMissionStore:
    def __init__(self, root: Path) -> None:
        self.projects_root = str(root)

    def load_mission(self, *_args: Any, **_kwargs: Any) -> Dict[str, Any]:
        return {}


def _session_dict(svc: StudyService, study_session_id: str) -> Dict[str, Any]:
    for item in svc.list_study_sessions():
        if item.get("session_id") == study_session_id:
            return item
    return {}


def _build_isolated_study_service(
    tmp_path: Path,
    *,
    include_second_doc: bool = True,
) -> tuple[StudyService, StudyOrchestrationCoordinator, List[StudyCapabilityRequest]]:
    svc = StudyService(storage_dir=tmp_path / "study_data")
    docs_spec = [
        (
            "doc_raft",
            "Consenso Distribuído com Raft",
            "Sistemas Distribuídos",
            "Eleição de Líder",
            "Validação Cruzada k-fold",
        ),
    ]
    if include_second_doc:
        docs_spec.append(
            (
                "doc_vision",
                "Arquiteturas de Visão Computacional",
                "Visão por Computador",
                "ConvNeXt",
                "Atenção Espacial",
            )
        )

    for doc_id, title, subject, concept_a, concept_b in docs_spec:
        doc_dir = svc.storage_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        sec1_text = f"{concept_a} garante consenso em {title}."
        sec2_text = f"{concept_b} avalia tolerância a falhas e latência 3.5ms em {title}."

        svc.documents[doc_id] = StudyDocument(
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

        ev1 = EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, excerpt=sec1_text[:60], status=EpistemicStatus.SOURCE_FACT.value)
        ev2 = EvidenceRef(section_id="sec_02", paragraph_id="p_02", page_number=2, excerpt=sec2_text[:60], status=EpistemicStatus.SOURCE_FACT.value)
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
                SectionAnalysis(section_id="sec_01", title="1. Fundamentos Conceptuais", in_depth_synthesis=sec1_text, core_ideas=[concept_a], source_refs=[ev1]),
                SectionAnalysis(section_id="sec_02", title="2. Metodologia Experimental", in_depth_synthesis=sec2_text, core_ideas=[concept_b], source_refs=[ev2]),
            ],
            conceptual_analysis=[
                ConceptItem(concept_id="c_01", name=concept_a, definition=sec1_text, explanation=sec1_text, relationships=["c_02"], evidence_refs=[ev1]),
                ConceptItem(concept_id="c_02", name=concept_b, definition=sec2_text, explanation=sec2_text, relationships=["c_01"], evidence_refs=[ev2]),
            ],
            methodology_analysis=MethodologyAnalysis(
                is_applicable=True,
                research_type="Estudo Experimental",
                methodological_design="Comparação controlada",
                methods_used=["k-fold k=10"],
                sample_or_participants="1500 amostras",
                evidence_refs=[ev2],
            ),
            results_and_evidence=[ResultItem(statement=f"{concept_b} reduziu erros em 28%.", evidence_data="28%", evidence_refs=[ev2])],
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

        fc1 = AdaptiveFlashcard(
            card_id=f"fc_{doc_id}_1",
            document_id=doc_id,
            chapter_id="chap_02",
            section_id="sec_02",
            front=f"O que define {concept_b}?",
            back=sec2_text,
            card_type=FlashcardType.CONCEPTUAL_UNDERSTANDING.value,
            topic="Metodologia Experimental",
            question_difficulty="MEDIUM",
        )
        svc.study_modes.flashcards.save_deck(
            StudyDeck(deck_id=f"deck_{doc_id}", document_id=doc_id, title=f"Deck — {title}", cards=[fc1])
        )
        ar1 = ActiveRecallPrompt(
            prompt_id=f"ar_{doc_id}_1",
            document_id=doc_id,
            chapter_id="chap_01",
            section_id="sec_01",
            prompt_text=f"Explica a base de {concept_a}.",
            grounded_reference_answer=sec1_text,
            topic=concept_a,
            key_points_expected=[concept_a],
        )
        ar2 = ActiveRecallPrompt(
            prompt_id=f"ar_{doc_id}_2",
            document_id=doc_id,
            chapter_id="chap_02",
            section_id="sec_02",
            prompt_text=f"Detalha o papel do Quórum e {concept_b}.",
            grounded_reference_answer=sec2_text,
            topic="Quórum",
            key_points_expected=[concept_b],
        )
        svc.study_modes.active_recall.save_deck(ActiveRecallDeck(document_id=doc_id, prompts=[ar1, ar2]))
        svc.study_modes.srs.register_items([
            ReviewSchedulingState(
                item_id=fc1.card_id,
                item_type="flashcard",
                document_id=doc_id,
                chapter_id="chap_02",
                section_id="sec_02",
                topic="Metodologia Experimental",
                next_review_ts=0.0,
                learning_state=ReviewLearningState.DUE.value,
            ),
            ReviewSchedulingState(
                item_id=ar1.prompt_id,
                item_type="active_recall",
                document_id=doc_id,
                chapter_id="chap_01",
                section_id="sec_01",
                topic=concept_a,
                next_review_ts=time.time() - 100.0,
                learning_state=ReviewLearningState.DUE.value,
            ),
        ])

    coord = StudyOrchestrationCoordinator(
        svc,
        explain_llm_caller=lambda **_: {
            "intuition": "Explicação fundamentada no capítulo.",
            "claims": [
                {
                    "statement": "O método usa eleição de líder.",
                    "epistemic_status": "SOURCE_FACT",
                    "citations": [{"page_number": 2, "section_id": "sec_2", "excerpt": "Eleição de líder"}],
                }
            ],
            "notes": "",
        },
    )

    recorded_requests: List[StudyCapabilityRequest] = []
    orig_execute = coord.router.execute

    async def spy_execute(
        request: StudyCapabilityRequest,
        *,
        ui_context: Optional[Dict[str, Any]] = None,
        on_status_event: Any = None,
        on_async_complete: Any = None,
        allow_background: bool = True,
    ):
        recorded_requests.append(request)
        return await orig_execute(
            request,
            ui_context=ui_context,
            on_status_event=on_status_event,
            on_async_complete=on_async_complete,
            allow_background=allow_background,
        )

    coord.router.execute = spy_execute  # type: ignore[method-assign]
    setattr(svc, "_study_coordinator", coord)
    return svc, coord, recorded_requests


def _patch_agent_runtime(
    monkeypatch: pytest.MonkeyPatch,
    svc: StudyService,
    tool_script_fn: Any,
) -> None:
    monkeypatch.setattr(orch_mod.glb, "is_gemini_valid", False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(orch_mod.obs_tools, "buscar_contexto_obsidian", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(orch_mod, "classify_task_complexity", AsyncMock(return_value="SIMPLE"))
    monkeypatch.setattr(
        server_mod,
        "_current_application_services",
        lambda: SimpleNamespace(study_service=svc),
    )
    monkeypatch.setattr(orch_mod, "query_ollama_with_tools", tool_script_fn)


def test_specialist_agent_propagates_session_a_and_isolates_session_b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    svc, coord, recorded = _build_isolated_study_service(tmp_path)

    async def fake_llm(model_name, messages, tools, system_prompt):
        has_result = any(m.get("role") == "tool_result" for m in messages)
        user_msg = str(messages[0].get("content") or "")
        if has_result:
            return {"message": {"content": f"Concluído para {user_msg}", "tool_calls": []}}
        if "TAREFA_A_EXPLAIN" in user_msg:
            return {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc_a1",
                            "function": {
                                "name": "study_explain_topic",
                                "arguments": {
                                    "document_id": "doc_raft",
                                    "chapter_ref": "capítulo 2",
                                    "question": "Explica a metodologia experimental",
                                },
                            },
                        }
                    ],
                }
            }
        if "TAREFA_A_RECALL" in user_msg:
            return {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc_a2",
                            "function": {
                                "name": "study_start_active_recall",
                                "arguments": {"document_id": "doc_raft", "topic": "Quórum"},
                            },
                        }
                    ],
                }
            }
        if "TAREFA_A_REVIEW" in user_msg:
            return {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "tc_a3",
                            "function": {
                                "name": "study_start_daily_review",
                                "arguments": {"document_id": "doc_raft"},
                            },
                        }
                    ],
                }
            }
        return {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc_b1",
                        "function": {
                            "name": "study_get_learning_progress",
                            "arguments": {"document_id": "doc_vision"},
                        },
                    }
                ],
            }
        }

    _patch_agent_runtime(monkeypatch, svc, fake_llm)

    async def _run():
        await orch_mod.spawn_specialist_agent(
            nome="TutorA",
            especialidade="Estudo",
            backstory="Especialista académico",
            tarefa="TAREFA_A_EXPLAIN",
            contexto_projeto="",
            on_msg=lambda *_: None,
            chat_session_id="session_A",
        )
        await orch_mod.spawn_specialist_agent(
            nome="TutorA",
            especialidade="Estudo",
            backstory="Especialista académico",
            tarefa="TAREFA_A_RECALL",
            contexto_projeto="",
            on_msg=lambda *_: None,
            chat_session_id="session_A",
        )
        await orch_mod.spawn_specialist_agent(
            nome="TutorA",
            especialidade="Estudo",
            backstory="Especialista académico",
            tarefa="TAREFA_A_REVIEW",
            contexto_projeto="",
            on_msg=lambda *_: None,
            chat_session_id="session_A",
        )

        # Sessão B consulta outro contexto após sessão A acumular doc, capítulo, recall e sessão de estudo
        await orch_mod.spawn_specialist_agent(
            nome="TutorB",
            especialidade="Estudo",
            backstory="Especialista académico",
            tarefa="TAREFA_B_PROGRESS",
            contexto_projeto="",
            on_msg=lambda *_: None,
            chat_session_id="session_B",
        )

    asyncio.run(_run())

    assert [r.chat_session_id for r in recorded[:3]] == ["session_A", "session_A", "session_A"]
    assert recorded[3].chat_session_id == "session_B"

    ctx_a = coord.context_manager.get_context("session_A")
    ctx_b = coord.context_manager.get_context("session_B")
    assert ctx_a.active_document_id == "doc_raft"
    assert ctx_a.active_chapter_id == "chap_02"
    assert ctx_a.last_active_recall_prompt_id == "ar_doc_raft_2"
    assert ctx_a.active_study_session_id is not None

    assert ctx_b.active_document_id == "doc_vision"
    assert ctx_b.active_chapter_id is None
    assert ctx_b.last_active_recall_prompt_id is None
    assert ctx_b.active_study_session_id is None
    assert "global" not in coord.context_manager._contexts


def test_specialist_agent_resume_isolation_implicit_vs_explicit_and_missing_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    # Apenas 1 documento na biblioteca torna o teste ainda mais exigente (step 6 de resolve_document não pode fugar)
    svc_single, coord_single, recorded_single = _build_isolated_study_service(
        tmp_path / "single",
        include_second_doc=False,
    )

    tool_results_log: List[str] = []

    def capture_msg(_nome: str, _esp: str, txt: str) -> None:
        if txt.startswith("[Resultado de "):
            tool_results_log.append(txt)

    next_tool_call: Dict[str, Any] = {"name": "study_start_daily_review", "arguments": {"document_id": "doc_raft"}}

    async def script_llm(model_name, messages, tools, system_prompt):
        if any(m.get("role") == "tool_result" for m in messages):
            return {"message": {"content": "OK", "tool_calls": []}}
        return {
            "message": {
                "content": "",
                "tool_calls": [{"id": "tc_1", "function": dict(next_tool_call)}],
            }
        }

    _patch_agent_runtime(monkeypatch, svc_single, script_llm)

    async def _run():
        # 1. Sessão A cria e pausa uma sessão de estudo
        await orch_mod.spawn_specialist_agent(
            "TutorA", "Estudo", "", "Iniciar revisão", "", capture_msg, chat_session_id="session_A"
        )
        sess_a_id = coord_single.context_manager.get_context("session_A").active_study_session_id
        assert sess_a_id
        svc_single.pause_study_session(sess_a_id)

        # 2. Sessão B tenta study_resume_session({}) sem IDs explícitos -> NÃO pode retomar sessão de A
        tool_results_log.clear()
        next_tool_call["name"] = "study_resume_session"
        next_tool_call["arguments"] = {}
        await orch_mod.spawn_specialist_agent(
            "TutorB", "Estudo", "", "Retomar implícito", "", capture_msg, chat_session_id="session_B"
        )
        assert recorded_single[-1].chat_session_id == "session_B"
        assert _session_dict(svc_single, sess_a_id)["status"] == "PAUSED"
        assert any("NEEDS_CLARIFICATION" in entry for entry in tool_results_log)

        # 3. Mesmo passando document_id sem study_session_id, sessão B não pode apropriar-se de sessão pertencente a A
        tool_results_log.clear()
        next_tool_call["name"] = "study_resume_session"
        next_tool_call["arguments"] = {"document_id": "doc_raft"}
        await orch_mod.spawn_specialist_agent(
            "TutorB", "Estudo", "", "Retomar por doc sem ID", "", capture_msg, chat_session_id="session_B"
        )
        assert _session_dict(svc_single, sess_a_id)["status"] == "PAUSED"
        assert any("FAILED" in entry and "Nenhuma sessão de estudo" in entry for entry in tool_results_log)

        # 4. Invocar specialist-agent SEM conversation ID (None e "global") -> falha de forma segura / clarifica sem usar "global"
        for missing_sid in (None, "", "global"):
            tool_results_log.clear()
            count_before = len(recorded_single)
            next_tool_call["name"] = "study_resume_session"
            next_tool_call["arguments"] = {}
            await orch_mod.spawn_specialist_agent(
                "TutorAnon", "Estudo", "", "Sem sessão", "", capture_msg, chat_session_id=missing_sid
            )
            assert len(recorded_single) == count_before  # bloqueado antes de sequer tocar em StudyCapabilityRouter como global
            assert any("MISSING_CHAT_SESSION" in entry and "NEEDS_CLARIFICATION" in entry for entry in tool_results_log)
            assert "global" not in coord_single.context_manager._contexts

        # 5. Invocar study_resume_session com explicit study_session_id válido -> retoma com sucesso
        tool_results_log.clear()
        next_tool_call["name"] = "study_resume_session"
        next_tool_call["arguments"] = {"study_session_id": sess_a_id}
        await orch_mod.spawn_specialist_agent(
            "TutorA", "Estudo", "", "Retomar explícito", "", capture_msg, chat_session_id="session_A"
        )
        assert _session_dict(svc_single, sess_a_id)["status"] == "IN_PROGRESS"
        assert any('"status": "COMPLETED"' in entry and sess_a_id in entry for entry in tool_results_log)

    asyncio.run(_run())


def test_explicit_document_and_study_session_id_mismatch_rejected(tmp_path: Path):
    svc, coord, _ = _build_isolated_study_service(tmp_path)

    async def _run():
        res_start = await coord.router.execute(
            StudyCapabilityRequest(
                capability=StudyCapabilityType.START_DAILY_REVIEW,
                chat_session_id="session_A",
                document_id="doc_raft",
            ),
            allow_background=False,
        )
        assert res_start.status == "COMPLETED"
        sess_a_id = res_start.study_session_id
        assert sess_a_id
        svc.pause_study_session(sess_a_id)

        raw = await execute_study_tool(
            "study_resume_session",
            {"document_id": "doc_vision", "study_session_id": sess_a_id},
            study_service=svc,
            chat_session_id="session_A",
            require_chat_session=True,
        )
        payload = json.loads(raw)
        assert payload["status"] == "FAILED"
        assert payload["error_code"] == "SESSION_DOCUMENT_MISMATCH"
        assert _session_dict(svc, sess_a_id)["status"] == "PAUSED"

    asyncio.run(_run())


def test_normal_orchestration_and_websocket_pipeline_propagate_chat_session_to_specialist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    svc, coord, recorded = _build_isolated_study_service(tmp_path)

    call_phase: List[str] = []

    async def orchestrated_llm(model_name, messages, tools, system_prompt):
        is_specialist = any("subagente" in str(m.get("content") or "").lower() or "specialist_req" in str(m.get("content") or "") for m in messages)
        has_result = any(m.get("role") == "tool_result" for m in messages)
        if is_specialist:
            if has_result:
                return {"message": {"content": "Especialista concluído.", "tool_calls": []}}
            call_phase.append("specialist_study_tool")
            return {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "sp_call_1",
                            "function": {
                                "name": "study_get_learning_progress",
                                "arguments": {"document_id": "doc_raft"},
                            },
                        }
                    ],
                }
            }

        executed_tools = [m.get("tool_name") for m in messages if m.get("role") == "tool_result"]
        if "study_explain_topic" not in executed_tools:
            call_phase.append("orch_study_tool")
            return {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "orch_call_1",
                            "function": {
                                "name": "study_explain_topic",
                                "arguments": {
                                    "document_id": "doc_raft",
                                    "question": "Explica a metodologia",
                                    "chapter_ref": "capítulo 2",
                                },
                            },
                        }
                    ],
                }
            }
        if "criar_agente_especialista" not in executed_tools:
            call_phase.append("orch_spawn_specialist")
            return {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "orch_call_2",
                            "function": {
                                "name": "criar_agente_especialista",
                                "arguments": {
                                    "nome": "Analista",
                                    "especialidade": "Progresso",
                                    "backstory": "Analisa progresso e coordena agentes de estudo sobre o tópico Raft.",
                                    "tarefa": "specialist_req analisa progresso e coordena agentes sobre este tópico de Raft",
                                    "contexto_projeto": "Estudo sobre Raft",
                                },
                            },
                        }
                    ],
                }
            }
        return {"message": {"content": "Orquestração finalizada com sucesso.", "tool_calls": []}}

    _patch_agent_runtime(monkeypatch, svc, orchestrated_llm)

    async def _run():
        # 1. Caminho direto run_jarvis_orchestration com chat_session_id explícito
        await orch_mod.run_jarvis_orchestration(
            "Analisa progresso de Raft",
            session_id=999,
            on_msg=lambda *_: None,
            on_file=lambda *_: None,
            on_kanban=lambda *_: None,
            chat_session_id="ws_conv_alpha",
        )
        assert len(recorded) == 2
        assert all(r.chat_session_id == "ws_conv_alpha" for r in recorded)
        assert call_phase == ["orch_study_tool", "orch_spawn_specialist", "specialist_study_tool"]

        # 2. Caminho completo ChatWebSocketHandler -> OrchestrationService -> run_jarvis_orchestration -> spawn_specialist_agent
        recorded.clear()
        call_phase.clear()
        conns = _DummyConnections()
        history: List[Dict[str, Any]] = []
        fake_agents = SimpleNamespace(
            active_template_name="builder_swarm",
            run_jarvis_orchestration=orch_mod.run_jarvis_orchestration,
            spawn_specialist_agent=orch_mod.spawn_specialist_agent,
        )
        fake_services = SimpleNamespace(
            database=SimpleNamespace(create_session=lambda _prompt: SimpleNamespace(id=505)),
            agents=fake_agents,
            sandbox=None,
            model_harness=None,
            project_context=None,
            coding_sessions=None,
            mission_planner=SimpleNamespace(mission_state=_DummyMissionStore(tmp_path)),
            mission_executor=None,
            mission_autonomy=None,
            sentinel_watchdog=None,
            study_service=svc,
        )
        orch_svc = OrchestrationService(
            services=fake_services,
            models=SimpleNamespace(),
            connections=conns,
            callbacks=OrchestrationCallbacks(
                broadcast_state=lambda v: conns.broadcast({"type": "state", "value": v}),
                open_local_application=lambda *_: None,
                run_in_main_loop=lambda *_: None,
                on_agent_message=lambda *_: None,
                on_file_update=lambda *_: None,
                on_kanban_update=lambda *_: None,
                build_template_payload=lambda t: {"type": "template_changed", "template_name": t},
            ),
            conversation_history=history,
            logger=__import__("logging").getLogger("test_isolation_orch"),
        )
        orch_svc.classify_intent = AsyncMock(return_value="TASK")  # type: ignore[method-assign]
        orch_svc.bridge = SimpleNamespace(handle_directive=AsyncMock(return_value={"status": "IGNORED"}))  # type: ignore[assignment]

        chat_handler = ChatWebSocketHandler(
            agents=fake_agents,
            database=fake_services.database,
            connections=conns,
            callbacks=SimpleNamespace(
                conversation_history=history,
                handle_slash_command=lambda *a, **k: None,
                parse_file_context=lambda p: p,
                broadcast_state=lambda v: conns.broadcast({"type": "state", "value": v}),
                run_orchestration_task=lambda prompt, sid, project_id=None, correlation_id=None, study_context=None: orch_svc.run_task(
                    prompt, sid, project_id=project_id, correlation_id=correlation_id, study_context=study_context
                ),
            ),
            logger=__import__("logging").getLogger("test_isolation_ws"),
        )

        await chat_handler.directive(
            object(),
            {
                "type": "directive",
                "text": "Coordena agentes sobre este tópico",
                "project_id": "proj_do_not_use",
                "correlation_id": "corr_do_not_use",
                "study_context": {"chat_session_id": "ws_thread_beta"},
            },
            WebSocketSessionState(),
        )
        await asyncio.sleep(0.2)
        assert len(recorded) == 2
        assert all(r.chat_session_id == "ws_thread_beta" for r in recorded)

        # 3. Caminho /spawn via ChatWebSocketHandler -> ChatCommandService._spawn -> spawn_specialist_agent
        recorded.clear()
        cmd_svc = ChatCommandService(
            services=fake_services,
            models=SimpleNamespace(),
            connections=conns,
            callbacks=ChatCommandCallbacks(
                broadcast_state=lambda v: conns.broadcast({"type": "state", "value": v}),
                on_agent_message=lambda *_: None,
                on_file_update=lambda *_: None,
            ),
            logger=__import__("logging").getLogger("test_isolation_cmd"),
        )
        chat_handler_cmd = ChatWebSocketHandler(
            agents=fake_agents,
            database=fake_services.database,
            connections=conns,
            callbacks=SimpleNamespace(
                conversation_history=history,
                handle_slash_command=cmd_svc.handle,
                parse_file_context=lambda p: p,
                broadcast_state=lambda v: conns.broadcast({"type": "state", "value": v}),
                run_orchestration_task=AsyncMock(),
            ),
            logger=__import__("logging").getLogger("test_isolation_ws_cmd"),
        )
        await chat_handler_cmd.directive(
            object(),
            {
                "type": "directive",
                "text": "/spawn Analista | Estudo | specialist_req verificar progresso",
                "study_context": {"chat_session_id": "slash_thread_gamma"},
            },
            WebSocketSessionState(),
        )
        assert len(recorded) == 1
        assert recorded[0].chat_session_id == "slash_thread_gamma"

        # 4. Directive sem study_context.chat_session_id não fabrica ID a partir de project_id/correlation_id/session_id=505
        recorded.clear()
        call_phase.clear()
        await chat_handler.directive(
            object(),
            {
                "type": "directive",
                "text": "Sem conversa identificada",
                "project_id": "proj_should_not_leak",
                "correlation_id": "corr_should_not_leak",
            },
            WebSocketSessionState(),
        )
        await asyncio.sleep(0.2)
        assert "orch_study_tool" in call_phase
        assert recorded == []
        assert "global" not in coord.context_manager._contexts

        # 5. Compatibilidade legacy de run_jarvis_orchestration com session_id inteiro positivo (> 0) sem chat_session_id
        recorded.clear()
        call_phase.clear()
        await orch_mod.run_jarvis_orchestration(
            "Analisa progresso de Raft",
            session_id=707,
            on_msg=lambda *_: None,
            on_file=lambda *_: None,
            on_kanban=lambda *_: None,
        )
        assert len(recorded) == 2
        assert all(r.chat_session_id == "707" for r in recorded)

        # 6. run_jarvis_orchestration sem chat_session_id e session_id=0 falha de forma segura (sem "global")
        recorded.clear()
        call_phase.clear()
        await orch_mod.run_jarvis_orchestration(
            "Analisa progresso de Raft",
            session_id=0,
            on_msg=lambda *_: None,
            on_file=lambda *_: None,
            on_kanban=lambda *_: None,
        )
        assert "orch_study_tool" in call_phase
        assert recorded == []
        assert "global" not in coord.context_manager._contexts

    asyncio.run(_run())


def test_two_sessions_on_same_document_and_switching_documents_stay_isolated(tmp_path: Path):
    svc, coord, _ = _build_isolated_study_service(tmp_path)

    async def _run():
        # Sessão A e Sessão B estudam doc_raft independentemente
        s_a = await coord.handle_directive(
            prompt='Quero rever os cartões pendentes de "Consenso Distribuído com Raft"',
            chat_session_id="sess_A",
            allow_background=False,
        )
        s_b = await coord.handle_directive(
            prompt='Quero rever os cartões pendentes de "Consenso Distribuído com Raft"',
            chat_session_id="sess_B",
            allow_background=False,
        )
        assert s_a.status == "COMPLETED" and s_b.status == "COMPLETED"
        assert s_a.study_session_id != s_b.study_session_id
        svc.pause_study_session(s_a.study_session_id)
        svc.pause_study_session(s_b.study_session_id)

        # Sessão A muda para doc_vision: limpa apenas sub-referências de A
        sw_a = await coord.handle_directive(
            prompt='Mostra-me o meu progresso em "Arquiteturas de Visão Computacional"',
            chat_session_id="sess_A",
            allow_background=False,
        )
        assert sw_a.document_id == "doc_vision"
        ctx_a = coord.context_manager.get_context("sess_A")
        ctx_b = coord.context_manager.get_context("sess_B")
        assert ctx_a.active_document_id == "doc_vision"
        assert ctx_a.active_study_session_id is None
        assert ctx_b.active_document_id == "doc_raft"
        assert ctx_b.active_study_session_id == s_b.study_session_id

        # Sessão A não consegue retomar sess_A (de Raft) implicitamente depois de mudar para Visão
        res_a_after_switch = await coord.handle_directive(
            prompt="Continua a sessão de estudo",
            chat_session_id="sess_A",
            allow_background=False,
        )
        assert res_a_after_switch.status == "NEEDS_CLARIFICATION"

        # Sessão B continua a retomar exclusivamente a SUA própria sessão s_b
        res_b = await coord.handle_directive(
            prompt="Continua a sessão de estudo",
            chat_session_id="sess_B",
            allow_background=False,
        )
        assert res_b.status == "COMPLETED"
        assert res_b.study_session_id == s_b.study_session_id
        assert _session_dict(svc, s_a.study_session_id)["status"] == "PAUSED"

    asyncio.run(_run())


def test_chat_mission_bridge_never_uses_default_study_chat_shared_context(tmp_path: Path):
    svc, coord, _ = _build_isolated_study_service(tmp_path, include_second_doc=True)
    conns = _DummyConnections()
    bridge = ChatMissionBridge(
        mission_planner=SimpleNamespace(mission_state=_DummyMissionStore(tmp_path)),
        mission_state=_DummyMissionStore(tmp_path),
        connections=conns,
        study_service=svc,
    )
    coord.context_manager.update_context("default_study_chat", document_id="doc_raft", study_session_id="sess_evil")
    assert "default_study_chat" not in coord.context_manager._contexts

    async def _run():
        # Pedido sem chat_session_id cai no resolver sem ler contexto partilhado
        res = await bridge.handle_directive(
            "Cria flashcards sobre este documento",
            session_id=77,
            study_context=None,
        )
        assert res["status"] == "NEEDS_CLARIFICATION"

    asyncio.run(_run())
