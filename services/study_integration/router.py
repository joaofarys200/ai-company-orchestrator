"""
JARVIS OS — Study Engine Phase 7: Study Capability Router
Traduz pedidos estruturados e validados em invocações diretas aos serviços
autoritativos do Study Engine (Fases 2–6), sem duplicar lógica de domínio.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional

from services.study_integration.context_manager import (
    ChapterResolutionResult,
    StudyContextManager,
    normalize_match_text,
)
from services.study_integration.contracts import (
    ASYNC_HEAVY_CAPABILITIES,
    StudyCapabilityRequest,
    StudyCapabilityResult,
    StudyCapabilityType,
    StudyNavigationTarget,
    normalize_chat_session_id,
)
from services.study_integration.explainer import (
    OllamaUnavailableError,
    StudyAcademicExplainer,
)
from services.study_integration.operation_manager import StudyOperationManager


class StudyCapabilityRouter:
    """Roteador único e validado para capacidades académicas do Study Engine."""

    def __init__(
        self,
        study_service: Any,
        *,
        context_manager: Optional[StudyContextManager] = None,
        operation_manager: Optional[StudyOperationManager] = None,
        explainer: Optional[StudyAcademicExplainer] = None,
        allowed_ingest_roots: Optional[List[Path]] = None,
    ) -> None:
        self.study_service = study_service
        storage_dir = getattr(study_service, "storage_dir", Path("data/study"))
        self.context_manager = context_manager or StudyContextManager(storage_dir=storage_dir)
        self.operation_manager = operation_manager or StudyOperationManager(storage_dir=storage_dir)
        self.explainer = explainer or StudyAcademicExplainer()
        workspace_root = Path(getattr(study_service, "workspace_root", ".")).resolve()
        self.allowed_ingest_roots = allowed_ingest_roots or [
            workspace_root,
            workspace_root / "sandbox_dir",
            workspace_root / "data",
            Path(storage_dir).resolve(),
        ]

    async def execute(
        self,
        request: StudyCapabilityRequest,
        *,
        ui_context: Optional[Dict[str, Any]] = None,
        on_status_event: Optional[Callable[[Any], Any]] = None,
        on_async_complete: Optional[Callable[[StudyCapabilityResult], Any]] = None,
        allow_background: bool = True,
    ) -> StudyCapabilityResult:
        """Valida parâmetros, resolve contexto e executa a capacidade pedida."""
        if not isinstance(request.capability, StudyCapabilityType):
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=str(request.capability),
                status="FAILED",
                summary_markdown="Capacidade de estudo desconhecida ou não registada.",
                error_code="UNKNOWN_CAPABILITY",
                error_message=f"Capacidade inválida: {request.capability}",
            )

        try:
            request.validate_bounds()
        except ValueError as val_err:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                summary_markdown=f"Parâmetros inválidos: {val_err}",
                error_code="INVALID_ARGUMENTS",
                error_message=str(val_err),
            )

        req_chat_sid = normalize_chat_session_id(request.chat_session_id)
        ctx = await asyncio.to_thread(
            self.context_manager.sync_ui_context,
            req_chat_sid,
            self.study_service,
            ui_context,
        )

        # Capacidades globais / independentes de um único documento
        if request.capability == StudyCapabilityType.LIST_DOCUMENTS:
            return await asyncio.to_thread(self._handle_list_documents, request)

        if request.capability == StudyCapabilityType.CANCEL_STUDY_OPERATION:
            return await asyncio.to_thread(self._handle_cancel_operation, request, ctx.active_document_id)

        if request.capability == StudyCapabilityType.INGEST_DOCUMENT:
            return await asyncio.to_thread(self._handle_ingest_document, request)

        if (
            request.capability == StudyCapabilityType.MANAGE_STUDY_SESSION
            and not request.document_id
            and not request.document_query
            and (request.session_action in {"resume", "pause", "complete", "list"} or request.study_session_id)
        ):
            resumed = await asyncio.to_thread(self._try_session_without_explicit_doc, request, ctx)
            if resumed is not None:
                return resumed

        # Resolver documento alvo com desambiguação e isolamento estrito
        doc_res = await asyncio.to_thread(
            self.context_manager.resolve_document,
            self.study_service,
            chat_session_id=req_chat_sid or "",
            explicit_document_id=request.document_id,
            document_query=request.document_query,
            prompt=request.raw_prompt,
            ui_context=ui_context,
        )
        if doc_res.status == "AMBIGUOUS":
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="NEEDS_CLARIFICATION",
                summary_markdown=doc_res.message,
                clarification_options=doc_res.candidates,
                error_code="AMBIGUOUS_DOCUMENT",
            )
        if doc_res.status != "RESOLVED" or doc_res.document is None:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                summary_markdown=doc_res.message or "Documento não encontrado.",
                error_code="DOCUMENT_NOT_FOUND",
                error_message=doc_res.message or "Documento não encontrado.",
                navigation=StudyNavigationTarget(tab="library", label="Abrir Biblioteca"),
            )

        doc = doc_res.document
        doc_id = doc.document_id
        doc_title = getattr(doc, "title", doc_id)
        doc_meta = getattr(doc, "metadata", {}) or {}
        doc_status = str(
            getattr(doc, "status", None) or doc_meta.get("sync_status") or "READY"
        ).upper()

        if doc_status in {"PROCESSING", "EXTRACTING", "QUEUED"} and request.capability not in {
            StudyCapabilityType.GET_DOCUMENT_STATUS,
            StudyCapabilityType.OPEN_STUDY_WORKSPACE,
            StudyCapabilityType.LIST_DOCUMENTS,
            StudyCapabilityType.CANCEL_STUDY_OPERATION,
        }:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=(
                    f"O documento **{doc_title}** ainda está a ser processado (`{doc_status}`). "
                    "Aguarda a conclusão antes de gerar materiais ou explicar secções."
                ),
                error_code="DOCUMENT_PROCESSING",
                error_message=f"Documento em processamento ({doc_status}).",
                navigation=StudyNavigationTarget(document_id=doc_id, tab="library", label="Ver Estado"),
            )

        if request.study_session_id and hasattr(self.study_service, "list_study_sessions"):
            sessions_list = await asyncio.to_thread(self.study_service.list_study_sessions)
            explicit_sess = next(
                (
                    s
                    for s in (sessions_list or [])
                    if s.get("session_id") == request.study_session_id
                ),
                None,
            )
            if explicit_sess is None and request.capability == StudyCapabilityType.MANAGE_STUDY_SESSION:
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="FAILED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=f"Sessão de estudo '{request.study_session_id}' não encontrada.",
                    error_code="SESSION_NOT_FOUND",
                    error_message=f"Sessão '{request.study_session_id}' não encontrada.",
                )
            if explicit_sess is not None and explicit_sess.get("document_id") != doc_id:
                actual_doc_id = str(explicit_sess.get("document_id") or "")
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="FAILED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=(
                        f"A sessão de estudo '{request.study_session_id}' pertence ao documento "
                        f"`{actual_doc_id}`, e não a **{doc_title}** (`{doc_id}`)."
                    ),
                    error_code="SESSION_DOCUMENT_MISMATCH",
                    error_message=f"Sessão '{request.study_session_id}' pertence a '{actual_doc_id}', não a '{doc_id}'.",
                )

        # Resolver capítulo / secção estritamente dentro deste documento
        chap_res = await asyncio.to_thread(
            self.context_manager.resolve_chapter_or_section,
            self.study_service,
            doc_id,
            chapter_id=request.chapter_id,
            chapter_ref=request.chapter_ref,
            section_id=request.section_id,
            section_ref=request.section_ref,
            prompt=request.raw_prompt,
            active_chapter_id=ctx.active_chapter_id if ctx.active_document_id == doc_id else None,
            active_section_id=ctx.active_section_id if ctx.active_document_id == doc_id else None,
        )
        if chap_res.status == "NOT_FOUND":
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=chap_res.message,
                error_code="INVALID_CHAPTER_OR_SECTION",
                error_message=chap_res.message,
                navigation=StudyNavigationTarget(document_id=doc_id, tab="reader", label="Abrir Leitor"),
            )

        effective_chapter_id = chap_res.chapter_id or (
            ctx.active_chapter_id if ctx.active_document_id == doc_id and request.chapter_id else None
        )
        effective_section_id = chap_res.section_id or (
            chap_res.source_section_ids[0] if len(chap_res.source_section_ids) == 1 else None
        )
        effective_topic = request.topic or chap_res.chapter_title or chap_res.section_title

        # Operações síncronas / rápidas ou explicação local LLM
        if request.capability == StudyCapabilityType.GET_DOCUMENT_STATUS:
            res = await asyncio.to_thread(self._handle_document_status, request, doc)
        elif request.capability == StudyCapabilityType.OPEN_STUDY_WORKSPACE:
            res = await asyncio.to_thread(
                self._handle_open_workspace,
                request,
                doc,
                effective_chapter_id,
                effective_section_id,
                effective_topic,
                ctx,
            )
        elif request.capability == StudyCapabilityType.EXPLAIN_CONCEPT_OR_CHAPTER:
            res = await self._handle_explain(
                request,
                doc,
                chap_res=chap_res,
                effective_topic=effective_topic,
                recent_concepts=ctx.recent_concepts if ctx.active_document_id == doc_id else [],
            )
        elif request.capability == StudyCapabilityType.COMPARE_CONCEPTS:
            res = await self._handle_compare(
                request,
                doc,
                recent_concepts=ctx.recent_concepts if ctx.active_document_id == doc_id else [],
            )
        elif request.capability == StudyCapabilityType.START_ACTIVE_RECALL:
            res = await asyncio.to_thread(self._handle_start_active_recall, request, doc)
        elif request.capability == StudyCapabilityType.SUBMIT_ACTIVE_RECALL:
            res = await asyncio.to_thread(self._handle_submit_active_recall, request, doc, ctx)
        elif request.capability == StudyCapabilityType.START_DAILY_REVIEW:
            res = await asyncio.to_thread(self._handle_start_daily_review, request, doc)
        elif request.capability in {
            StudyCapabilityType.GET_LEARNING_PROGRESS,
            StudyCapabilityType.GET_KNOWLEDGE_GAPS,
        }:
            res = await asyncio.to_thread(self._handle_learning_progress, request, doc)
        elif request.capability == StudyCapabilityType.MANAGE_STUDY_SESSION:
            res = await asyncio.to_thread(self._handle_manage_session, request, doc, ctx)
        elif request.capability in ASYNC_HEAVY_CAPABILITIES:
            res = await self._dispatch_heavy_capability(
                request,
                doc,
                chap_res=chap_res,
                effective_topic=effective_topic,
                allow_background=allow_background,
                on_status_event=on_status_event,
                on_async_complete=on_async_complete,
            )
        else:
            res = StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown="Capacidade não suportada.",
                error_code="UNSUPPORTED_CAPABILITY",
            )

        # Atualizar contexto conversacional apenas em resultados bem-sucedidos / em curso
        if res.status in {"COMPLETED", "RUNNING"} and res.document_id and req_chat_sid:
            concepts = list((res.result_ref or {}).get("concepts_used") or [])
            await asyncio.to_thread(
                self.context_manager.update_context,
                req_chat_sid,
                document_id=res.document_id,
                document_title=res.document_title or doc_title,
                chapter_id=res.chapter_id or effective_chapter_id,
                section_id=res.section_id or effective_section_id,
                activity=res.navigation.tab if res.navigation else self._activity_for_capability(request.capability),
                study_session_id=res.study_session_id,
                last_assessment_id=(res.result_ref or {}).get("assessment_id"),
                last_active_recall_prompt_id=(res.result_ref or {}).get("prompt_id"),
                operation_id=res.operation_id,
                operation_type=request.capability.value,
                topic=effective_topic or request.topic,
                difficulty=request.difficulty,
                question_count=request.question_count,
                concepts=concepts,
            )

        return res

    @staticmethod
    def _extract_cards(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        if isinstance(payload.get("cards"), list):
            return list(payload["cards"])
        deck = payload.get("deck")
        if isinstance(deck, dict) and isinstance(deck.get("cards"), list):
            return list(deck["cards"])
        return []

    @staticmethod
    def _extract_prompts(payload: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        if isinstance(payload.get("prompts"), list):
            return list(payload["prompts"])
        deck = payload.get("deck")
        if isinstance(deck, dict) and isinstance(deck.get("prompts"), list):
            return list(deck["prompts"])
        return []

    @staticmethod
    def _activity_for_capability(cap: StudyCapabilityType) -> str:
        mapping = {
            StudyCapabilityType.ANALYSE_DOCUMENT: "summary",
            StudyCapabilityType.PREPARE_STUDY_MATERIAL: "summary",
            StudyCapabilityType.GENERATE_STUDY_DOCUMENT: "summary",
            StudyCapabilityType.EXPLAIN_CONCEPT_OR_CHAPTER: "reader",
            StudyCapabilityType.COMPARE_CONCEPTS: "reader",
            StudyCapabilityType.GENERATE_FLASHCARDS: "flashcards",
            StudyCapabilityType.GENERATE_CORNELL_NOTES: "notes",
            StudyCapabilityType.CREATE_ASSESSMENT: "quiz",
            StudyCapabilityType.START_ACTIVE_RECALL: "active_recall",
            StudyCapabilityType.SUBMIT_ACTIVE_RECALL: "active_recall",
            StudyCapabilityType.START_DAILY_REVIEW: "adaptive",
            StudyCapabilityType.GET_LEARNING_PROGRESS: "adaptive",
            StudyCapabilityType.GET_KNOWLEDGE_GAPS: "adaptive",
        }
        return mapping.get(cap, "library")

    # ------------------------------------------------------------------
    # Handlers específicos — Delegam estritamente para StudyService
    # ------------------------------------------------------------------

    def _handle_list_documents(self, request: StudyCapabilityRequest) -> StudyCapabilityResult:
        docs = list(self.study_service.list_documents() or [])
        docs.sort(key=lambda d: getattr(d, "updated_at", ""), reverse=True)
        if not docs:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="COMPLETED",
                summary_markdown="A Biblioteca de Estudo ainda não tem documentos importados.",
                result_ref={"count": 0, "documents": []},
                navigation=StudyNavigationTarget(tab="library", label="Abrir Biblioteca"),
            )

        items: List[Dict[str, Any]] = []
        lines: List[str] = [f"Encontrei **{len(docs)} documento(s)** na Biblioteca de Estudo:\n"]
        for d in docs[:12]:
            readiness = (
                self.study_service.get_study_mode_readiness(d.document_id)
                if hasattr(self.study_service, "get_study_mode_readiness")
                else {}
            )
            items.append(
                {
                    "document_id": d.document_id,
                    "title": d.title,
                    "subject": getattr(d, "subject", "Geral"),
                    "source_type": getattr(d, "source_type", "PDF"),
                    "status": getattr(d, "status", "READY"),
                    "is_ready": bool(readiness.get("is_ready")),
                }
            )
            ready_label = "Pronto p/ Estudo" if readiness.get("is_ready") else str(getattr(d, "status", "READY"))
            lines.append(f"- **{d.title}** (`{d.document_id}`) — {getattr(d, 'subject', 'Geral')} [{ready_label}]")

        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            summary_markdown="\n".join(lines),
            result_ref={"count": len(docs), "documents": items},
            navigation=StudyNavigationTarget(
                document_id=docs[0].document_id,
                tab="library",
                label="Abrir Biblioteca",
            ),
        )

    def _handle_cancel_operation(
        self,
        request: StudyCapabilityRequest,
        active_doc_id: Optional[str],
    ) -> StudyCapabilityResult:
        res = self.operation_manager.request_cancel(
            operation_id=request.target_operation_id,
            document_id=request.document_id or active_doc_id,
        )
        if not res.get("found"):
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                summary_markdown=res.get("message", "Nenhuma operação encontrada."),
                error_code="OPERATION_NOT_FOUND",
                error_message=res.get("message"),
            )
        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            summary_markdown=res.get("message", "Cancelamento solicitado."),
            result_ref=res,
        )

    def _handle_ingest_document(self, request: StudyCapabilityRequest) -> StudyCapabilityResult:
        if request.video_url:
            try:
                doc = self.study_service.ingest_video_url(request.video_url)
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="COMPLETED",
                    document_id=doc.document_id,
                    document_title=doc.title,
                    summary_markdown=f"Vídeo importado para a Biblioteca de Estudo: **{doc.title}** (`{doc.document_id}`).",
                    result_ref={"document_id": doc.document_id, "title": doc.title},
                    navigation=StudyNavigationTarget(document_id=doc.document_id, tab="reader", label="Abrir Vídeo"),
                )
            except Exception as exc:
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="FAILED",
                    summary_markdown=f"Não foi possível importar o URL de vídeo: {exc}",
                    error_code="INGEST_FAILED",
                    error_message=str(exc),
                )

        if not request.file_path:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="NEEDS_CLARIFICATION",
                summary_markdown=(
                    "Para importar um documento, anexa o ficheiro no chat, indica o caminho dentro do workspace, "
                    "ou carrega-o diretamente na Biblioteca de Estudo."
                ),
                navigation=StudyNavigationTarget(tab="library", label="Abrir Biblioteca"),
            )

        raw_path = Path(request.file_path)
        if not raw_path.is_absolute():
            raw_path = Path(getattr(self.study_service, "workspace_root", ".")) / raw_path
        resolved = raw_path.resolve()

        in_allowed_root = any(
            resolved == root.resolve() or root.resolve() in resolved.parents
            for root in self.allowed_ingest_roots
        )
        if not in_allowed_root:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                summary_markdown=f"Caminho fora das pastas autorizadas para importação: `{request.file_path}`.",
                error_code="PATH_OUTSIDE_BOUNDARY",
                error_message="Caminho fora das raízes autorizadas.",
            )
        if not resolved.is_file():
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                summary_markdown=f"Ficheiro não encontrado: `{request.file_path}`.",
                error_code="FILE_NOT_FOUND",
                error_message="Ficheiro não encontrado.",
            )

        try:
            doc = self.study_service.ingest_document(str(resolved), resolved.name)
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="COMPLETED",
                document_id=doc.document_id,
                document_title=doc.title,
                summary_markdown=f"Documento importado com sucesso: **{doc.title}** (`{doc.document_id}`).",
                result_ref={"document_id": doc.document_id, "title": doc.title, "status": doc.status},
                navigation=StudyNavigationTarget(document_id=doc.document_id, tab="reader", label="Abrir no Leitor"),
            )
        except Exception as exc:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                summary_markdown=f"Falha ao ingerir `{resolved.name}`: {exc}",
                error_code="INGEST_FAILED",
                error_message=str(exc),
            )

    def _handle_document_status(self, request: StudyCapabilityRequest, doc: Any) -> StudyCapabilityResult:
        doc_id = doc.document_id
        ast_exists = bool(self.study_service.get_document_ast(doc_id))
        dossier = self.study_service.get_academic_reasoning_dossier(doc_id)
        plan_status = self.study_service.get_editorial_plan_status(doc_id)
        docgen_status = self.study_service.get_study_document_generation_status(doc_id)
        readiness = self.study_service.get_study_mode_readiness(doc_id)
        flash_payload = self.study_service.get_adaptive_flashcards(doc_id)
        cornell = self.study_service.get_phase6_cornell(doc_id)
        assessments = self.study_service.get_phase6_assessments(doc_id)
        recall = self.study_service.get_active_recall_prompts(doc_id)
        ops = self.operation_manager.list_operations(document_id=doc_id)
        interrupted = [o for o in ops if o.get("status") == "INTERRUPTED"]

        fc_count = len(self._extract_cards(flash_payload))
        ass_count = len((assessments or {}).get("assessments") or [])
        rec_count = len(self._extract_prompts(recall))
        plan_chapters = len(((self.study_service.get_editorial_study_plan(doc_id) or {}).get("chapters") or []))

        lines = [
            f"### Estado Académico: **{doc.title}** (`{doc_id}`)",
            f"- **Extração / AST (Fase 2):** {'Disponível' if ast_exists else 'Pendente'} (estado: `{getattr(doc, 'status', 'READY')}`)",
            f"- **Raciocínio Académico (Fase 3):** {'Disponível' if dossier else 'Não gerado'}",
            f"- **Plano Editorial (Fase 4):** {'Disponível (' + str(plan_chapters) + ' capítulos)' if plan_status.get('has_plan') else 'Não gerado'}",
            f"- **Documento de Estudo PDF/DOCX (Fase 5):** {'Gerado (v' + str(docgen_status.get('active_version') or 1) + ')' if docgen_status.get('has_pdf') else 'Não gerado'}",
            f"- **Modos Interativos (Fase 6):** {fc_count} flashcards | Cornell: {'Sim' if cornell else 'Não'} | {ass_count} teste(s) | {rec_count} questões Active Recall",
        ]
        if interrupted:
            lines.append(
                f"- ⚠️ **Operação interrompida anteriormente:** `{interrupted[0]['capability']}` (`{interrupted[0]['operation_id']}`). Podes pedir para retomar/gerar novamente."
            )

        actions = [
            StudyNavigationTarget(document_id=doc_id, tab="reader", label="Abrir Leitor"),
            StudyNavigationTarget(document_id=doc_id, tab="summary", label="Plano & Documento"),
        ]
        if fc_count > 0:
            actions.append(StudyNavigationTarget(document_id=doc_id, tab="flashcards", label="Abrir Flashcards"))
        if ass_count > 0:
            actions.append(StudyNavigationTarget(document_id=doc_id, tab="quiz", label="Abrir Testes"))

        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc_id,
            document_title=doc.title,
            summary_markdown="\n".join(lines),
            result_ref={
                "has_ast": ast_exists,
                "has_dossier": bool(dossier),
                "has_plan": bool(plan_status.get("has_plan")),
                "has_study_document": bool(docgen_status.get("has_pdf")),
                "readiness": readiness,
                "flashcards_count": fc_count,
                "assessments_count": ass_count,
                "active_recall_count": rec_count,
                "interrupted_operations": interrupted[:3],
            },
            navigation=actions[0],
            navigation_actions=actions,
        )

    def _handle_open_workspace(
        self,
        request: StudyCapabilityRequest,
        doc: Any,
        chapter_id: Optional[str],
        section_id: Optional[str],
        topic: Optional[str],
        ctx: Any,
    ) -> StudyCapabilityResult:
        target_tab = request.target_tab or ctx.active_activity or "reader"
        nav = StudyNavigationTarget(
            document_id=doc.document_id,
            tab=target_tab,
            chapter_id=chapter_id,
            section_id=section_id,
            topic=topic,
            label=f"Abrir {target_tab}",
        )
        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc.document_id,
            document_title=doc.title,
            chapter_id=chapter_id,
            section_id=section_id,
            summary_markdown=f"A abrir **{doc.title}** no separador `{target_tab}`.",
            navigation=nav,
            auto_navigate=True,
        )

    async def _handle_explain(
        self,
        request: StudyCapabilityRequest,
        doc: Any,
        *,
        chap_res: ChapterResolutionResult,
        effective_topic: Optional[str],
        recent_concepts: List[str],
    ) -> StudyCapabilityResult:
        question = request.question or request.raw_prompt
        try:
            explained = await self.explainer.explain(
                self.study_service,
                document_id=doc.document_id,
                question=question,
                chapter_id=chap_res.chapter_id,
                section_id=chap_res.section_id,
                topic=effective_topic,
                recent_concepts=recent_concepts,
            )
        except OllamaUnavailableError as err:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc.document_id,
                document_title=doc.title,
                summary_markdown=f"Não consegui gerar a explicação académica porque o modelo local Ollama (`qwen3.5:9b`) está indisponível: {err}",
                error_code="OLLAMA_UNAVAILABLE",
                error_message=str(err),
            )
        except Exception as exc:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc.document_id,
                document_title=doc.title,
                summary_markdown=f"Erro ao gerar explicação fundamentada: {exc}",
                error_code="EXPLAIN_FAILED",
                error_message=str(exc),
            )

        nav = StudyNavigationTarget(
            document_id=doc.document_id,
            tab="reader",
            chapter_id=chap_res.chapter_id,
            section_id=chap_res.section_id,
            topic=effective_topic,
            label="Abrir Secção no Leitor",
        )
        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc.document_id,
            document_title=doc.title,
            chapter_id=chap_res.chapter_id,
            section_id=chap_res.section_id,
            summary_markdown=explained["summary_markdown"],
            citations=explained.get("citations") or [],
            epistemic_breakdown=explained.get("epistemic_breakdown"),
            result_ref={"concepts_used": explained.get("concepts_used") or []},
            navigation=nav,
        )

    async def _handle_compare(
        self,
        request: StudyCapabilityRequest,
        doc: Any,
        *,
        recent_concepts: Optional[List[str]] = None,
    ) -> StudyCapabilityResult:
        concept_a = (request.concept_a or "").strip()
        concept_b = (request.concept_b or "").strip()
        if (not concept_a or not concept_b) and recent_concepts and len(recent_concepts) >= 2:
            concept_a = concept_a or str(recent_concepts[0]).strip()
            concept_b = concept_b or str(recent_concepts[1]).strip()
        if not concept_a or not concept_b:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="NEEDS_CLARIFICATION",
                document_id=doc.document_id,
                document_title=doc.title,
                summary_markdown="Indica claramente os dois conceitos que pretendes comparar neste documento.",
                error_code="MISSING_COMPARISON_CONCEPTS",
            )
        try:
            compared = await self.explainer.compare_concepts(
                self.study_service,
                document_id=doc.document_id,
                concept_a=concept_a,
                concept_b=concept_b,
                question=request.question or request.raw_prompt,
            )
        except OllamaUnavailableError as err:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc.document_id,
                document_title=doc.title,
                summary_markdown=f"Modelo local Ollama (`qwen3.5:9b`) indisponível para comparar conceitos: {err}",
                error_code="OLLAMA_UNAVAILABLE",
                error_message=str(err),
            )
        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc.document_id,
            document_title=doc.title,
            summary_markdown=compared["summary_markdown"],
            citations=compared.get("citations") or [],
            epistemic_breakdown=compared.get("epistemic_breakdown"),
            result_ref={"concepts_used": compared.get("concepts_used") or []},
            navigation=StudyNavigationTarget(document_id=doc.document_id, tab="summary", label="Ver Mapa Conceptual"),
        )

    def _ensure_phase6_prerequisites(
        self,
        doc_id: str,
        on_progress: Callable[[str, Optional[float], str], None],
        cancel_ev: threading.Event,
    ) -> None:
        readiness = self.study_service.get_study_mode_readiness(doc_id)
        if readiness.get("is_ready"):
            return
        if not readiness.get("has_dossier"):
            if cancel_ev.is_set():
                return
            on_progress("REASONING", None, "A gerar Dossier de Raciocínio Académico (Fase 3)...")
            dossier = self.study_service.generate_academic_reasoning(
                doc_id,
                on_progress=lambda st, p, m: on_progress(st, p, m),
                cancellation_check=cancel_ev.is_set,
            )
            if not dossier:
                raise RuntimeError(f"Não foi possível gerar Raciocínio Académico para '{doc_id}'.")
        if not readiness.get("has_plan"):
            if cancel_ev.is_set():
                return
            on_progress("EDITORIAL_PLAN", None, "A gerar Plano Editorial (Fase 4)...")
            plan = self.study_service.generate_editorial_study_plan(
                doc_id,
                auto_generate_dossier=True,
                on_progress=lambda st, p, m: on_progress(st, p, m),
                cancellation_check=cancel_ev.is_set,
            )
            if not plan:
                raise RuntimeError(f"Não foi possível gerar Plano Editorial para '{doc_id}'.")

    async def _dispatch_heavy_capability(
        self,
        request: StudyCapabilityRequest,
        doc: Any,
        *,
        chap_res: ChapterResolutionResult,
        effective_topic: Optional[str],
        allow_background: bool,
        on_status_event: Optional[Callable[[Any], Any]],
        on_async_complete: Optional[Callable[[StudyCapabilityResult], Any]],
    ) -> StudyCapabilityResult:
        doc_id = doc.document_id
        doc_title = getattr(doc, "title", doc_id)
        scope_sig = f"{chap_res.chapter_id or ''}:{effective_topic or ''}:{request.difficulty or ''}:{request.question_count or ''}:{request.card_count or ''}:{int(request.force_recompute)}"
        dedup_key = f"{request.capability.value}:{doc_id}:{scope_sig}"

        # Se artefacto válido já existe e não foi pedido force_recompute nem filtro novo, reutilizar imediatamente
        fast_cached = self._try_reuse_cached_heavy(request, doc, chap_res, effective_topic)
        if fast_cached is not None:
            return fast_cached

        def worker(
            emit_progress: Callable[[str, Optional[float], str], None],
            cancel_ev: threading.Event,
        ) -> Dict[str, Any]:
            if request.capability == StudyCapabilityType.ANALYSE_DOCUMENT:
                emit_progress("REASONING", None, f"A analisar '{doc_title}' (Fase 3)...")
                dossier = self.study_service.generate_academic_reasoning(
                    doc_id,
                    force_recompute=request.force_recompute,
                    on_progress=emit_progress,
                    cancellation_check=cancel_ev.is_set,
                )
                if cancel_ev.is_set():
                    return {"cancelled": True}
                if not dossier:
                    raise RuntimeError("Não foi possível concluir o Dossier de Raciocínio Académico (AST em falta?).")
                concepts_raw = dossier.get("conceptual_analysis") or dossier.get("concepts") or []
                concepts = [c.get("name") for c in concepts_raw[:6] if isinstance(c, dict)]
                return {
                    "summary_markdown": (
                        f"Análise académica concluída para **{doc_title}**: "
                        f"{len(concepts_raw)} conceitos identificados e "
                        f"{len(dossier.get('section_analyses') or [])} secções analisadas."
                    ),
                    "result_ref": {
                        "has_dossier": True,
                        "concepts_count": len(concepts_raw),
                        "concepts_used": concepts,
                    },
                    "navigation": StudyNavigationTarget(document_id=doc_id, tab="summary", label="Ver Análise").to_dict(),
                }

            if request.capability in {
                StudyCapabilityType.PREPARE_STUDY_MATERIAL,
                StudyCapabilityType.GENERATE_STUDY_DOCUMENT,
            }:
                emit_progress("PLANNING", None, f"A preparar plano e documento de estudo de '{doc_title}'...")
                plan = self.study_service.get_editorial_study_plan(doc_id)
                if not plan or request.force_recompute:
                    plan = self.study_service.generate_editorial_study_plan(
                        doc_id,
                        force_recompute=request.force_recompute,
                        auto_generate_dossier=True,
                        on_progress=emit_progress,
                        cancellation_check=cancel_ev.is_set,
                    )
                if cancel_ev.is_set():
                    return {"cancelled": True}
                if not plan:
                    raise RuntimeError("Plano editorial não pôde ser gerado.")
                gen_res = self.study_service.generate_study_document(
                    doc_id,
                    force_recompute=request.force_recompute,
                    auto_generate_plan=False,
                    on_progress=emit_progress,
                    cancellation_check=cancel_ev.is_set,
                )
                if cancel_ev.is_set():
                    return {"cancelled": True}
                if not gen_res:
                    raise RuntimeError("Geração documental da Fase 5 não produziu resultado.")
                return {
                    "summary_markdown": f"Material e documento de estudo gerados para **{doc_title}** (Fases 3–5 concluídas).",
                    "result_ref": {
                        "has_study_document": True,
                        "pdf_path": gen_res.get("pdf_path"),
                        "version": gen_res.get("version"),
                    },
                    "navigation": StudyNavigationTarget(document_id=doc_id, tab="summary", label="Abrir Documento de Estudo").to_dict(),
                }

            self._ensure_phase6_prerequisites(doc_id, emit_progress, cancel_ev)
            if cancel_ev.is_set():
                return {"cancelled": True}

            if request.capability == StudyCapabilityType.GENERATE_FLASHCARDS:
                target_cards = int(request.card_count or 12)
                emit_progress("FLASHCARDS", None, f"A gerar flashcards para '{doc_title}'...")
                payload = self.study_service.generate_adaptive_flashcards(
                    doc_id,
                    force_regenerate=request.force_recompute,
                    target_cards=target_cards,
                    on_progress=emit_progress,
                    cancellation_check=cancel_ev.is_set,
                )
                if cancel_ev.is_set():
                    return {"cancelled": True}
                cards = self._extract_cards(payload)
                matched_cards = self._filter_cards_by_scope(cards, chap_res, effective_topic)
                scope_note = f" (âmbito: *{effective_topic}* — {len(matched_cards)} cartões correspondentes)" if effective_topic else ""
                return {
                    "summary_markdown": f"Flashcards preparados para **{doc_title}**: **{len(cards)}** cartões no baralho{scope_note}.",
                    "result_ref": {
                        "total_cards": len(cards),
                        "matching_cards": len(matched_cards),
                        "topic": effective_topic,
                    },
                    "navigation": StudyNavigationTarget(
                        document_id=doc_id,
                        tab="flashcards",
                        chapter_id=chap_res.chapter_id,
                        section_id=chap_res.section_id,
                        topic=effective_topic,
                        label="Abrir Flashcards",
                    ).to_dict(),
                }

            if request.capability == StudyCapabilityType.GENERATE_CORNELL_NOTES:
                emit_progress("CORNELL", None, f"A gerar Cornell Notes para '{doc_title}'...")
                cornell = self.study_service.generate_phase6_cornell(
                    doc_id,
                    force_regenerate=request.force_recompute,
                    on_progress=emit_progress,
                    cancellation_check=cancel_ev.is_set,
                )
                if cancel_ev.is_set():
                    return {"cancelled": True}
                entries = list((cornell or {}).get("entries") or [])
                return {
                    "summary_markdown": f"Cornell Notes estruturadas geradas para **{doc_title}** ({len(entries)} secções).",
                    "result_ref": {"entries_count": len(entries), "topic": effective_topic},
                    "navigation": StudyNavigationTarget(
                        document_id=doc_id,
                        tab="notes",
                        chapter_id=chap_res.chapter_id,
                        section_id=chap_res.section_id,
                        topic=effective_topic,
                        label="Abrir Cornell Notes",
                    ).to_dict(),
                }

            if request.capability == StudyCapabilityType.CREATE_ASSESSMENT:
                emit_progress("ASSESSMENT", None, f"A criar teste para '{doc_title}'...")
                cfg: Dict[str, Any] = {
                    "question_count": int(request.question_count or 6),
                    "difficulty": request.difficulty or "MIXED",
                }
                if chap_res.chapter_id:
                    cfg["chapter_ids"] = [chap_res.chapter_id]
                if effective_topic:
                    cfg["topics"] = [effective_topic]
                assessment = self.study_service.generate_phase6_assessment(
                    doc_id,
                    cfg,
                    on_progress=emit_progress,
                    cancellation_check=cancel_ev.is_set,
                )
                if cancel_ev.is_set():
                    return {"cancelled": True}
                qs = list((assessment or {}).get("questions") or [])
                ass_id = str((assessment or {}).get("assessment_id") or "")
                return {
                    "summary_markdown": (
                        f"Teste criado para **{doc_title}** com **{len(qs)} pergunta(s)** "
                        f"(dificuldade: `{cfg['difficulty']}`"
                        + (f", foco: *{effective_topic}*" if effective_topic else "")
                        + ")."
                    ),
                    "result_ref": {
                        "assessment_id": ass_id,
                        "question_count": len(qs),
                        "difficulty": cfg["difficulty"],
                        "topic": effective_topic,
                    },
                    "navigation": StudyNavigationTarget(
                        document_id=doc_id,
                        tab="quiz",
                        chapter_id=chap_res.chapter_id,
                        assessment_id=ass_id,
                        topic=effective_topic,
                        label="Iniciar Teste",
                    ).to_dict(),
                }

            return {"summary_markdown": "Concluído.", "result_ref": {}}

        if not allow_background:
            # Execução direta awaitable (útil para chamadas de tools de agentes)
            record, dedup = await self.operation_manager.submit_operation(
                capability=request.capability.value,
                document_id=doc_id,
                chat_session_id=normalize_chat_session_id(request.chat_session_id) or "",
                correlation_id=request.correlation_id or request.operation_id,
                dedup_key=dedup_key,
                worker_fn=worker,
                on_status_event=on_status_event,
            )
            # Aguardar conclusão da tarefa registada
            task = self.operation_manager._tasks.get(record.operation_id)
            if task is not None:
                await task
            final_rec = self.operation_manager.get_operation(record.operation_id) or record
            if final_rec.status == "FAILED":
                return StudyCapabilityResult(
                    operation_id=final_rec.operation_id,
                    capability=request.capability.value,
                    status="FAILED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=final_rec.message or "Erro na operação.",
                    error_code="OPERATION_FAILED",
                    error_message=final_rec.error,
                )
            if final_rec.status == "CANCELLED":
                return StudyCapabilityResult(
                    operation_id=final_rec.operation_id,
                    capability=request.capability.value,
                    status="CANCELLED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=final_rec.message,
                )
            target_tab = self._activity_for_capability(request.capability)
            return StudyCapabilityResult(
                operation_id=final_rec.operation_id,
                capability=request.capability.value,
                status="COMPLETED",
                document_id=doc_id,
                document_title=doc_title,
                chapter_id=chap_res.chapter_id,
                section_id=chap_res.section_id,
                summary_markdown=final_rec.message,
                result_ref=final_rec.result_summary,
                navigation=StudyNavigationTarget(
                    document_id=doc_id,
                    tab=target_tab,
                    chapter_id=chap_res.chapter_id,
                    assessment_id=final_rec.result_summary.get("assessment_id"),
                    topic=effective_topic,
                    label=f"Abrir {target_tab}",
                ),
            )

        async def _notify_done(final_rec: Any, outcome: Dict[str, Any]) -> None:
            if on_async_complete is None:
                return
            nav_dict = outcome.get("navigation") or {}
            nav = StudyNavigationTarget(
                document_id=nav_dict.get("document_id") or doc_id,
                tab=nav_dict.get("tab") or self._activity_for_capability(request.capability),
                chapter_id=nav_dict.get("chapter_id"),
                section_id=nav_dict.get("section_id"),
                assessment_id=nav_dict.get("assessment_id"),
                topic=nav_dict.get("topic"),
                label=nav_dict.get("label"),
            )
            done_res = StudyCapabilityResult(
                operation_id=final_rec.operation_id,
                capability=request.capability.value,
                status=final_rec.status,
                document_id=doc_id,
                document_title=doc_title,
                chapter_id=chap_res.chapter_id,
                section_id=chap_res.section_id,
                summary_markdown=str(outcome.get("summary_markdown") or final_rec.message),
                result_ref=dict(outcome.get("result_ref") or final_rec.result_summary),
                navigation=nav,
            )
            cb_res = on_async_complete(done_res)
            if hasattr(cb_res, "__await__"):
                await cb_res

        rec, deduplicated = await self.operation_manager.submit_operation(
            capability=request.capability.value,
            document_id=doc_id,
            chat_session_id=normalize_chat_session_id(request.chat_session_id) or "",
            correlation_id=request.correlation_id or request.operation_id,
            dedup_key=dedup_key,
            worker_fn=worker,
            on_status_event=on_status_event,
            on_complete_callback=_notify_done,
        )
        msg = (
            f"Já existe uma operação em curso para **{doc_title}** (`{rec.operation_id}`). "
            "A acompanhar o progresso existente sem duplicar processamento."
            if deduplicated
            else f"Iniciei **{request.capability.value}** para **{doc_title}** (`{rec.operation_id}`). "
            "Podes continuar a conversar enquanto concluo."
        )
        return StudyCapabilityResult(
            operation_id=rec.operation_id,
            capability=request.capability.value,
            status="RUNNING",
            document_id=doc_id,
            document_title=doc_title,
            chapter_id=chap_res.chapter_id,
            section_id=chap_res.section_id,
            summary_markdown=msg,
            result_ref={"deduplicated": deduplicated, "operation_id": rec.operation_id},
            progress={"stage": rec.stage, "percent": rec.progress_percent, "message": rec.message},
            navigation=StudyNavigationTarget(
                document_id=doc_id,
                tab=self._activity_for_capability(request.capability),
                topic=effective_topic,
                label=f"Abrir {self._activity_for_capability(request.capability)}",
            ),
        )

    def _try_reuse_cached_heavy(
        self,
        request: StudyCapabilityRequest,
        doc: Any,
        chap_res: ChapterResolutionResult,
        effective_topic: Optional[str],
    ) -> Optional[StudyCapabilityResult]:
        if request.force_recompute:
            return None
        doc_id = doc.document_id
        doc_title = getattr(doc, "title", doc_id)

        if request.capability == StudyCapabilityType.ANALYSE_DOCUMENT:
            dossier = self.study_service.get_academic_reasoning_dossier(doc_id)
            if dossier:
                concepts_raw = dossier.get("conceptual_analysis") or dossier.get("concepts") or []
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="COMPLETED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=(
                        f"Reutilizei a análise académica já existente de **{doc_title}**: "
                        f"{len(concepts_raw)} conceitos identificados."
                    ),
                    result_ref={"reused_cached": True, "concepts_count": len(concepts_raw)},
                    navigation=StudyNavigationTarget(document_id=doc_id, tab="summary", label="Ver Análise"),
                )

        if request.capability == StudyCapabilityType.GENERATE_STUDY_DOCUMENT:
            st = self.study_service.get_study_document_generation_status(doc_id)
            if st.get("has_pdf") and not st.get("is_stale"):
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="COMPLETED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=f"O documento de estudo de **{doc_title}** já se encontra atualizado e disponível.",
                    result_ref={"reused_cached": True, **st},
                    navigation=StudyNavigationTarget(document_id=doc_id, tab="summary", label="Abrir Documento de Estudo"),
                )

        if request.capability == StudyCapabilityType.GENERATE_FLASHCARDS and not effective_topic and not request.card_count:
            payload = self.study_service.get_adaptive_flashcards(doc_id)
            cards = self._extract_cards(payload)
            if cards:
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="COMPLETED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=f"O baralho de flashcards de **{doc_title}** já existe com **{len(cards)}** cartões prontos.",
                    result_ref={"reused_cached": True, "total_cards": len(cards)},
                    navigation=StudyNavigationTarget(
                        document_id=doc_id,
                        tab="flashcards",
                        chapter_id=chap_res.chapter_id,
                        label="Abrir Flashcards",
                    ),
                )

        if request.capability == StudyCapabilityType.GENERATE_CORNELL_NOTES and not effective_topic:
            cornell = self.study_service.get_phase6_cornell(doc_id)
            if cornell and (cornell.get("entries") or []):
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="COMPLETED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=f"As Cornell Notes de **{doc_title}** já estão geradas ({len(cornell.get('entries') or [])} secções).",
                    result_ref={"reused_cached": True, "entries_count": len(cornell.get("entries") or [])},
                    navigation=StudyNavigationTarget(document_id=doc_id, tab="notes", label="Abrir Cornell Notes"),
                )

        return None

    @staticmethod
    def _filter_cards_by_scope(
        cards: List[Dict[str, Any]],
        chap_res: ChapterResolutionResult,
        topic: Optional[str],
    ) -> List[Dict[str, Any]]:
        if not chap_res.chapter_id and not chap_res.source_section_ids and not topic:
            return cards
        t_norm = normalize_match_text(topic or "")
        sids = set(chap_res.source_section_ids)
        out: List[Dict[str, Any]] = []
        for c in cards:
            if chap_res.chapter_id and str(c.get("chapter_id")) == chap_res.chapter_id:
                out.append(c)
                continue
            if sids and str(c.get("section_id")) in sids:
                out.append(c)
                continue
            hay = normalize_match_text(f"{c.get('topic', '')} {c.get('front', '')} {c.get('back', '')}")
            if t_norm and any(tok in hay for tok in t_norm.split() if len(tok) > 3):
                out.append(c)
        return out

    def _handle_start_active_recall(self, request: StudyCapabilityRequest, doc: Any) -> StudyCapabilityResult:
        doc_id = doc.document_id
        doc_title = getattr(doc, "title", doc_id)
        try:
            existing = self.study_service.get_active_recall_prompts(doc_id)
            prompts = self._extract_prompts(existing)
            if not prompts or request.force_recompute:
                self._ensure_phase6_prerequisites(doc_id, lambda *_: None, threading.Event())
                res = self.study_service.generate_active_recall(
                    doc_id,
                    force_regenerate=request.force_recompute,
                    target_prompts=int(request.question_count or 6),
                )
                prompts = self._extract_prompts(res)
        except Exception as exc:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=f"Não foi possível preparar questões de Active Recall: {exc}",
                error_code="ACTIVE_RECALL_FAILED",
                error_message=str(exc),
            )

        if not prompts:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=f"Não foram geradas questões de Active Recall para **{doc_title}**.",
                error_code="NO_PROMPTS",
            )

        # Escolher prompt relevante ao tópico se indicado
        chosen = prompts[0]
        if request.topic:
            tn = normalize_match_text(request.topic)
            for p in prompts:
                if tn in normalize_match_text(f"{p.get('topic', '')} {p.get('prompt_text', '')}"):
                    chosen = p
                    break

        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc_id,
            document_title=doc_title,
            summary_markdown=(
                f"### Active Recall — **{doc_title}**\n\n"
                f"**Pergunta:** {chosen.get('prompt_text')}\n\n"
                "Responde aqui no chat ou abre a vista interativa de Active Recall para registar o teu progresso."
            ),
            result_ref={
                "prompt_id": chosen.get("prompt_id"),
                "prompts_count": len(prompts),
                "topic": chosen.get("topic"),
            },
            navigation=StudyNavigationTarget(
                document_id=doc_id,
                tab="active_recall",
                topic=request.topic or chosen.get("topic"),
                label="Abrir Active Recall",
            ),
        )

    def _handle_submit_active_recall(
        self,
        request: StudyCapabilityRequest,
        doc: Any,
        ctx: Any,
    ) -> StudyCapabilityResult:
        doc_id = doc.document_id
        doc_title = getattr(doc, "title", doc_id)
        prompt_id = request.prompt_id or (
            ctx.last_active_recall_prompt_id if ctx.active_document_id == doc_id else None
        )

        if not prompt_id:
            data = self.study_service.get_active_recall_prompts(doc_id)
            prompts = self._extract_prompts(data)
            if prompts:
                prompt_id = prompts[0].get("prompt_id")

        if not prompt_id:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown="Não há nenhuma pergunta de Active Recall ativa nesta conversa.",
                error_code="NO_ACTIVE_PROMPT",
            )

        if request.reveal_answer:
            revealed = self.study_service.study_modes.get_active_recall_prompts(doc_id, reveal_answers=True)
            prompts = self._extract_prompts(revealed)
            target = next((p for p in prompts if p.get("prompt_id") == prompt_id), None)
            if not target:
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="FAILED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown="Pergunta de Active Recall não encontrada.",
                    error_code="PROMPT_NOT_FOUND",
                )
            ref_answer = (
                target.get("grounded_reference_answer")
                or target.get("reference_answer")
                or target.get("key_points_expected")
                or target.get("expected_points")
                or "Resposta de referência não disponível."
            )
            if isinstance(ref_answer, list):
                ref_answer = "\n".join(f"- {item}" for item in ref_answer)
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="COMPLETED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=f"**Resposta de referência ({doc_title}):**\n\n{ref_answer}",
                result_ref={"prompt_id": prompt_id, "revealed": True},
                navigation=StudyNavigationTarget(document_id=doc_id, tab="active_recall", label="Ver no Active Recall"),
            )

        res = self.study_service.submit_active_recall_attempt(
            doc_id,
            prompt_id,
            student_response=request.answer_text or request.raw_prompt,
            self_confidence=3,
        )
        attempt = (res or {}).get("attempt") or {}
        score_pct = attempt.get("score_pct")
        feedback = attempt.get("feedback") or "Tentativa avaliada e registada no Active Recall Engine."
        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc_id,
            document_title=doc_title,
            summary_markdown=f"**Avaliação Active Recall ({score_pct}%):** {feedback}",
            result_ref={"prompt_id": prompt_id, "score_pct": score_pct, "attempt_id": attempt.get("attempt_id")},
            navigation=StudyNavigationTarget(document_id=doc_id, tab="active_recall", label="Abrir Active Recall"),
        )

    def _handle_start_daily_review(self, request: StudyCapabilityRequest, doc: Any) -> StudyCapabilityResult:
        doc_id = doc.document_id
        doc_title = getattr(doc, "title", doc_id)
        try:
            q = self.study_service.get_daily_review_queue(doc_id)
        except Exception as exc:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=f"Não foi possível calcular a fila de revisão diária: {exc}",
                error_code="DAILY_QUEUE_FAILED",
                error_message=str(exc),
            )

        ordered_items: List[Dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for bucket_key in ("lapsed_items", "due_items", "low_confidence_items", "new_items"):
            for item in q.get(bucket_key) or []:
                if not isinstance(item, dict) or not item.get("item_id"):
                    continue
                itype = str(item.get("item_type") or "flashcard").lower()
                key = (itype, str(item["item_id"]))
                if key in seen:
                    continue
                seen.add(key)
                ordered_items.append(
                    {
                        "item_id": str(item["item_id"]),
                        "item_type": itype,
                        "queue_category": bucket_key.replace("_items", ""),
                        "title": str(item.get("title") or item.get("topic") or ""),
                        "topic": str(item.get("topic") or ""),
                    }
                )

        if not ordered_items:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="COMPLETED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=(
                    f"Não tens cartões ou itens pendentes para rever hoje em **{doc_title}**. "
                    "Podes gerar novos flashcards/Active Recall ou explorar o Hub Adaptativo."
                ),
                result_ref={"due_count": 0, "total_queue_count": 0},
                navigation=StudyNavigationTarget(document_id=doc_id, tab="adaptive", label="Abrir Hub Adaptativo"),
            )

        req_sid = normalize_chat_session_id(request.chat_session_id)
        session = self.study_service.start_study_session(
            document_id=doc_id,
            mode="DAILY_REVIEW",
            title=f"Revisão Diária — {doc_title}",
            items=ordered_items,
            item_ids=[it["item_id"] for it in ordered_items],
            config={"chat_session_id": req_sid} if req_sid else {},
        )
        first_tab = "active_recall" if ordered_items[0]["item_type"] == "active_recall" else "flashcards"
        session_id = str(session.get("session_id") or "")
        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc_id,
            document_title=doc_title,
            study_session_id=session_id,
            summary_markdown=(
                f"Sessão de Revisão Diária iniciada para **{doc_title}** (`{session_id}`): "
                f"**{len(ordered_items)} item(ns)** em fila "
                f"({len(q.get('lapsed_items') or [])} em atraso, {len(q.get('due_items') or [])} devidos, "
                f"{len(q.get('new_items') or [])} novos)."
            ),
            result_ref={
                "session_id": session_id,
                "total_queue_count": len(ordered_items),
                "first_item_type": ordered_items[0]["item_type"],
            },
            navigation=StudyNavigationTarget(
                document_id=doc_id,
                tab=first_tab,
                session_id=session_id,
                label="Iniciar Revisão",
            ),
            navigation_actions=[
                StudyNavigationTarget(document_id=doc_id, tab=first_tab, session_id=session_id, label="Iniciar Revisão"),
                StudyNavigationTarget(document_id=doc_id, tab="adaptive", session_id=session_id, label="Ver Fila Diária"),
            ],
            auto_navigate=True,
        )

    def _handle_learning_progress(self, request: StudyCapabilityRequest, doc: Any) -> StudyCapabilityResult:
        doc_id = doc.document_id
        doc_title = getattr(doc, "title", doc_id)
        try:
            prog = self.study_service.get_learning_progress(doc_id, recompute=True)
            queue = self.study_service.get_daily_review_queue(doc_id)
        except Exception as exc:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=f"Não foi possível obter progresso de aprendizagem: {exc}",
                error_code="PROGRESS_FAILED",
                error_message=str(exc),
            )

        acc = prog.get("overall_accuracy_pct")
        acc_txt = f"{acc:.1f}%" if isinstance(acc, (int, float)) else "Sem tentativas suficientes"
        mastery = prog.get("mastery_level") or "INSUFFICIENT_EVIDENCE"
        gaps = list(prog.get("knowledge_gaps") or [])
        missed = list(prog.get("repeatedly_missed_concepts") or [])
        weak_topics = list(queue.get("weak_topics") or [])
        due_count = int(queue.get("total_queue_count") or 0)

        lines = [
            f"### Progresso & Lacunas — **{doc_title}**",
            f"- **Domínio global:** `{mastery}` | **Precisão:** `{acc_txt}`",
            f"- **Atividade registada:** {prog.get('flashcard_reviews_total', 0)} revisões de flashcards | "
            f"{prog.get('questions_answered', 0)} perguntas respondidas | "
            f"{prog.get('active_recall_attempts_total', 0)} Active Recall",
            f"- **Revisões diárias pendentes:** **{due_count}**",
        ]
        if gaps:
            lines.append("\n**Principais tópicos com dificuldade / lacunas detetadas:**")
            for g in gaps[:5]:
                label = g.get("topic") or g.get("concept") or g.get("chapter_id") or "Tópico"
                reason = g.get("reason") or g.get("severity") or ""
                lines.append(f"- **{label}** ({reason})")
        elif missed or weak_topics:
            lines.append(f"- **Conceitos/tópicos a reforçar:** {', '.join([*missed, *weak_topics][:6])}")
        else:
            lines.append("- Nenhuma lacuna recorrente registada até ao momento.")

        return StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc_id,
            document_title=doc_title,
            summary_markdown="\n".join(lines),
            result_ref={
                "mastery_level": mastery,
                "overall_accuracy_pct": acc,
                "due_count": due_count,
                "knowledge_gaps": gaps[:6],
                "repeatedly_missed_concepts": missed[:6],
            },
            navigation=StudyNavigationTarget(document_id=doc_id, tab="adaptive", label="Abrir Progresso & Lacunas"),
        )

    @staticmethod
    def _session_owner(session: Dict[str, Any]) -> Optional[str]:
        cfg = session.get("config")
        if isinstance(cfg, dict):
            return normalize_chat_session_id(cfg.get("chat_session_id"))
        return None

    @classmethod
    def _is_session_accessible_implicitly(
        cls,
        session: Dict[str, Any],
        req_sid: Optional[str],
        ctx: Any,
        *,
        require_document_match: bool = True,
    ) -> bool:
        """Determina se uma sessão é elegível para retoma implícita nesta conversa."""
        if not req_sid:
            return False
        owner = cls._session_owner(session)
        active_doc_id = getattr(ctx, "active_document_id", None)
        if owner == req_sid:
            if require_document_match and active_doc_id:
                return session.get("document_id") == active_doc_id
            return True
        if owner is None and active_doc_id:
            return session.get("document_id") == active_doc_id
        return False

    def _try_session_without_explicit_doc(
        self,
        request: StudyCapabilityRequest,
        ctx: Any,
    ) -> Optional[StudyCapabilityResult]:
        req_sid = normalize_chat_session_id(request.chat_session_id)
        all_sessions = list(self.study_service.list_study_sessions() or [])
        if request.study_session_id:
            target = next((s for s in all_sessions if s.get("session_id") == request.study_session_id), None)
            if not target:
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="FAILED",
                    summary_markdown=f"Sessão de estudo '{request.study_session_id}' não encontrada.",
                    error_code="SESSION_NOT_FOUND",
                )
            doc = self.study_service.get_document(target.get("document_id"))
            return self._apply_session_action(request, target, doc)

        action = request.session_action or "resume"
        if action in {"resume", "pause", "complete"}:
            if not req_sid:
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="NEEDS_CLARIFICATION",
                    summary_markdown=(
                        "Falta o identificador da conversa para retomar contexto implícito de estudo. "
                        "Indica explicitamente `study_session_id` ou executa numa conversa identificada."
                    ),
                    error_code="MISSING_CHAT_SESSION",
                    navigation=StudyNavigationTarget(tab="adaptive", label="Abrir Hub Adaptativo"),
                )

            active_or_paused = [
                s for s in all_sessions
                if str(s.get("status", "")).upper() in {"PAUSED", "IN_PROGRESS"}
            ]
            if ctx.active_study_session_id:
                ctx_target = next(
                    (s for s in active_or_paused if s.get("session_id") == ctx.active_study_session_id),
                    None,
                )
                if ctx_target and (
                    not ctx.active_document_id or ctx_target.get("document_id") == ctx.active_document_id
                ) and self._session_owner(ctx_target) in {None, req_sid}:
                    doc = self.study_service.get_document(ctx_target.get("document_id"))
                    return self._apply_session_action(request, ctx_target, doc)

            candidates = [
                s for s in active_or_paused
                if self._is_session_accessible_implicitly(s, req_sid, ctx)
            ]
            if not candidates:
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="NEEDS_CLARIFICATION",
                    summary_markdown=(
                        "Não encontrei nenhuma sessão de estudo ativa ou pausada associada a esta conversa. "
                        "Indica explicitamente o `study_session_id` ou o documento que pretendes retomar."
                    ),
                    error_code="SESSION_CLARIFICATION_REQUIRED",
                    navigation=StudyNavigationTarget(tab="adaptive", label="Abrir Hub Adaptativo"),
                )
            if len(candidates) == 1:
                doc = self.study_service.get_document(candidates[0].get("document_id"))
                return self._apply_session_action(request, candidates[0], doc)

            opts = [
                {
                    "session_id": s.get("session_id"),
                    "document_id": s.get("document_id"),
                    "title": s.get("title") or s.get("mode"),
                }
                for s in candidates[:5]
            ]
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="NEEDS_CLARIFICATION",
                summary_markdown=(
                    "Tens várias sessões de estudo pausadas/ativas nesta conversa. Qual pretendes continuar?\n"
                    + "\n".join(f"- **{o['title']}** (`{o['session_id']}`)" for o in opts)
                ),
                clarification_options=opts,
                error_code="AMBIGUOUS_SESSION",
            )
        return None

    def _handle_manage_session(
        self,
        request: StudyCapabilityRequest,
        doc: Any,
        ctx: Any,
    ) -> StudyCapabilityResult:
        doc_id = doc.document_id
        doc_title = getattr(doc, "title", doc_id)
        action = request.session_action or "resume"
        req_sid = normalize_chat_session_id(request.chat_session_id)
        all_doc_sessions = list(self.study_service.list_study_sessions(document_id=doc_id) or [])
        sessions = [
            s for s in all_doc_sessions
            if self._session_owner(s) in ({req_sid, None} if req_sid else {None})
        ]

        if action == "list":
            if not sessions:
                return StudyCapabilityResult(
                    operation_id=request.operation_id,
                    capability=request.capability.value,
                    status="COMPLETED",
                    document_id=doc_id,
                    document_title=doc_title,
                    summary_markdown=f"Não existem sessões de estudo registadas para **{doc_title}** nesta conversa.",
                    navigation=StudyNavigationTarget(document_id=doc_id, tab="adaptive", label="Abrir Hub Adaptativo"),
                )
            lines = [f"Sessões de estudo para **{doc_title}**:\n"]
            for s in sessions[:6]:
                lines.append(f"- `{s.get('session_id')}` — **{s.get('mode')}** [{s.get('status')}] ({len(s.get('completed_item_ids') or [])}/{len(s.get('items') or s.get('item_ids') or [])} itens)")
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="COMPLETED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown="\n".join(lines),
                result_ref={"sessions": sessions[:6]},
                navigation=StudyNavigationTarget(document_id=doc_id, tab="adaptive", label="Abrir Sessões"),
            )

        if action == "start":
            return self._handle_start_daily_review(request, doc)

        if request.study_session_id:
            target_session = next(
                (s for s in all_doc_sessions if s.get("session_id") == request.study_session_id),
                None,
            )
        else:
            target_id = ctx.active_study_session_id if ctx.active_document_id == doc_id else None
            target_session = (
                next((s for s in sessions if s.get("session_id") == target_id), None)
                if target_id
                else next(
                    (s for s in sessions if str(s.get("status", "")).upper() in {"PAUSED", "IN_PROGRESS"}),
                    None,
                )
            )
        if not target_session:
            return StudyCapabilityResult(
                operation_id=request.operation_id,
                capability=request.capability.value,
                status="FAILED",
                document_id=doc_id,
                document_title=doc_title,
                summary_markdown=f"Nenhuma sessão de estudo ativa ou pausada encontrada para **{doc_title}** nesta conversa.",
                error_code="SESSION_NOT_FOUND",
                navigation=StudyNavigationTarget(document_id=doc_id, tab="adaptive", label="Iniciar Nova Sessão"),
            )
        return self._apply_session_action(request, target_session, doc)

    def _apply_session_action(
        self,
        request: StudyCapabilityRequest,
        session: Dict[str, Any],
        doc: Any,
    ) -> StudyCapabilityResult:
        sid = str(session.get("session_id") or "")
        doc_id = str(session.get("document_id") or (doc.document_id if doc else ""))
        doc_title = getattr(doc, "title", doc_id) if doc else doc_id
        action = request.session_action or "resume"

        if action == "pause":
            updated = self.study_service.pause_study_session(sid)
            tab = "adaptive"
            msg = f"Sessão **{updated.get('title') or sid}** (`{sid}`) pausada com progresso guardado."
            auto_nav = False
        elif action == "complete":
            updated = self.study_service.complete_study_session(sid)
            tab = "adaptive"
            msg = f"Sessão **{updated.get('title') or sid}** (`{sid}`) concluída."
            auto_nav = False
        else:
            updated = self.study_service.resume_study_session(sid)
            items = list(updated.get("items") or [])
            idx = int(updated.get("current_index") or 0)
            cur_item = items[idx] if 0 <= idx < len(items) else (items[0] if items else None)
            cur_type = str((cur_item or {}).get("item_type") or "").lower()
            if cur_type == "active_recall" or updated.get("mode") == "ACTIVE_RECALL":
                tab = "active_recall"
            elif updated.get("mode") in {"ASSESSMENT", "EXAM_SIM"}:
                tab = "quiz"
            elif cur_type == "flashcard" or updated.get("mode") in {"FLASHCARD_REVIEW", "DAILY_REVIEW"}:
                tab = "flashcards"
            else:
                tab = "adaptive"
            done_cnt = len(updated.get("completed_item_ids") or [])
            total_cnt = len(items) or len(updated.get("item_ids") or [])
            msg = f"Sessão **{updated.get('title') or sid}** retomada (`{sid}`): {done_cnt}/{total_cnt} itens concluídos."
            auto_nav = True

        res = StudyCapabilityResult(
            operation_id=request.operation_id,
            capability=request.capability.value,
            status="COMPLETED",
            document_id=doc_id,
            document_title=doc_title,
            study_session_id=sid,
            summary_markdown=msg,
            result_ref={"session": updated},
            navigation=StudyNavigationTarget(
                document_id=doc_id,
                tab=tab,
                session_id=sid,
                label="Retomar na Interface" if auto_nav else "Abrir Hub",
            ),
            auto_navigate=auto_nav,
        )
        # Sincronizar contexto com documento da sessão apenas quando há conversa identificada
        req_sid = normalize_chat_session_id(request.chat_session_id)
        if req_sid:
            self.context_manager.update_context(
                req_sid,
                document_id=doc_id,
                document_title=doc_title,
                activity=tab,
                study_session_id=sid,
                operation_id=request.operation_id,
                operation_type=request.capability.value,
            )
        return res
