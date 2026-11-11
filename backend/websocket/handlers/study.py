"""
JARVIS OS - Study WebSocket Handler
Gerencia a experiência pedagógica unificada:
Biblioteca, Leitor de Artigos Científicos, Assistente Contextual,
Cornell Notes, Quizzes com Scoring Real, Flashcards e Obsidian Knowledge Vault.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import asdict
from datetime import datetime
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from backend.logging_config import log_event
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
try:
    from backend.websocket.gateway import ConnectionManager
except ImportError:
    ConnectionManager = Any
from backend.websocket.handlers import bind_handler_methods
from services.study_service import StudyService


STUDY_HANDLERS = {
    "study_list_documents": "list_documents",
    "study_get_document": "get_document",
    "study_upload_document": "upload_document",
    "study_delete_document": "delete_document",
    "study_update_progress": "update_progress",
    "study_contextual_assist": "contextual_assist",
    "study_ask_paper": "ask_paper",
    "study_generate_summary": "generate_summary",
    "study_generate_cornell": "generate_cornell",
    "study_save_to_knowledge": "save_to_knowledge",
    "study_save_to_vault": "save_to_knowledge",
    "study_generate_quiz": "generate_quiz",
    "study_submit_quiz": "submit_quiz",
    "study_list_flashcards": "list_flashcards",
    "study_review_flashcard": "review_flashcard",
    "study_add_reading_note": "add_reading_note",
    "study_add_highlight": "add_highlight",
    "study_synthesize_documents": "synthesize_documents",
    "study_list_collections": "list_collections",
    "study_create_collection": "create_collection",
    "study_get_document_file": "get_document_file",
    "study_get_document_ast": "get_document_ast",
    "study_get_academic_reasoning": "get_academic_reasoning",
    "study_generate_academic_reasoning": "generate_academic_reasoning",
    "study_get_editorial_plan": "get_editorial_plan",
    "study_generate_editorial_plan": "generate_editorial_plan",
    "study_get_generated_document_status": "get_generated_document_status",
    "study_generate_study_document": "generate_study_document",
    "study_get_generated_document_file": "get_generated_document_file",
    "study_search_rag": "search_rag",
    # Study Folder Sync & Courses
    "study_link_folder": "link_folder",
    "study_unlink_folder": "unlink_folder",
    "study_sync_folder": "sync_folder",
    "study_ask_course": "ask_course",
    "study_get_course_details": "get_course_details",
    "study_retry_document": "retry_document",
    # Study Video Intelligence
    "study_get_video_context": "get_video_context",
    "study_explain_video_moment": "explain_video_moment",
    "study_explain_video_visual": "explain_video_visual",
    "study_search_video_transcript": "search_video_transcript",
    "study_ask_video": "ask_video",
    "study_save_video_note": "save_video_note",
    "study_update_video_progress": "update_video_progress",
    "study_ingest_video_url": "ingest_video_url",
    "study_cancel_generation": "cancel_generation",
    # Phase 6 — Study Modes, Active Recall & Adaptive Learning
    "study_mode_get_readiness": "phase6_get_readiness",
    "study_mode_get_flashcards": "phase6_get_flashcards",
    "study_mode_generate_flashcards": "phase6_generate_flashcards",
    "study_mode_edit_flashcard": "phase6_edit_flashcard",
    "study_mode_delete_flashcard": "phase6_delete_flashcard",
    "study_mode_create_flashcard": "phase6_create_flashcard",
    "study_mode_regenerate_flashcard": "phase6_regenerate_flashcard",
    "study_mode_review_flashcard": "phase6_review_flashcard",
    "study_mode_get_cornell": "phase6_get_cornell",
    "study_mode_generate_cornell": "phase6_generate_cornell",
    "study_mode_edit_cornell_entry": "phase6_edit_cornell_entry",
    "study_mode_add_cornell_note": "phase6_add_cornell_note",
    "study_mode_export_cornell_vault": "phase6_export_cornell_vault",
    "study_mode_get_assessments": "phase6_get_assessments",
    "study_mode_generate_assessment": "phase6_generate_assessment",
    "study_mode_check_question": "phase6_check_question",
    "study_mode_submit_assessment": "phase6_submit_assessment",
    "study_mode_get_active_recall": "phase6_get_active_recall",
    "study_mode_generate_active_recall": "phase6_generate_active_recall",
    "study_mode_submit_active_recall": "phase6_submit_active_recall",
    "study_mode_get_daily_queue": "phase6_get_daily_queue",
    "study_mode_get_progress": "phase6_get_progress",
    "study_mode_start_session": "phase6_start_session",
    "study_mode_update_session": "phase6_update_session",
    "study_mode_pause_session": "phase6_pause_session",
    "study_mode_resume_session": "phase6_resume_session",
    "study_mode_complete_session": "phase6_complete_session",
    "study_mode_list_sessions": "phase6_list_sessions",
}


class StudyWebSocketHandler:
    def __init__(
        self,
        connections: ConnectionManager,
        study_service: StudyService,
        logger: Any = None,
    ) -> None:
        self.connections = connections
        self.study_service = study_service
        self.logger = logger

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, STUDY_HANDLERS)

    async def list_documents(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        docs = [d.to_dict() for d in self.study_service.list_documents()]
        # Ordenar por data mais recente
        docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
        print(f"[WS] list_documents requested -> {len(docs)} documents returned", flush=True)
        await self.connections.send(websocket, {
            "type": "study_documents_list",
            "event": "study.document_list",
            "documents": docs,
        })

    async def get_document(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        doc = self.study_service.get_document(doc_id)
        if not doc:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Documento '{doc_id}' não encontrado.",
            })
            return

        # Encontrar notas e destaques associados
        notes = [asdict(n) if hasattr(n, "asdict") else n.__dict__ for n in self.study_service.notes if n.document_id == doc_id]
        highlights = [asdict(h) if hasattr(h, "asdict") else h.__dict__ for n in self.study_service.highlights if (h := n).document_id == doc_id]

        await self.connections.send(websocket, {
            "type": "study_document_details",
            "document": doc.to_dict(),
            "notes": notes,
            "highlights": highlights,
        })

    async def get_document_file(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        doc = self.study_service.get_document(doc_id)
        if not doc or not doc.metadata.get("file_path"):
            await self.connections.send(websocket, {
                "type": "study_document_file_result",
                "document_id": doc_id,
                "error": "Document file not found",
                "request_id": message.get("request_id"),
            })
            return

        file_path = doc.metadata.get("file_path")
        if file_path and not os.path.isabs(file_path):
            file_path = os.path.join(self.study_service.workspace_root, file_path)
        if not file_path or not os.path.exists(file_path):
            await self.connections.send(websocket, {
                "type": "study_document_file_result",
                "document_id": doc_id,
                "error": "File does not exist on disk",
                "request_id": message.get("request_id"),
            })
            return

        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
            b64 = base64.b64encode(raw_bytes).decode("ascii")
            await self.connections.send(websocket, {
                "type": "study_document_file_result",
                "document_id": doc_id,
                "filename": doc.metadata.get("filename", "document.pdf"),
                "content_base64": b64,
                "size_bytes": len(raw_bytes),
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_document_file_result",
                "document_id": doc_id,
                "error": str(e),
                "request_id": message.get("request_id"),
            })

    async def get_document_ast(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        ast_dict = await asyncio.to_thread(self.study_service.get_document_ast, doc_id)
        if ast_dict:
            await self.connections.send(websocket, {
                "type": "study_document_ast_result",
                "document_id": doc_id,
                "ast": ast_dict,
                "request_id": message.get("request_id"),
            })
        else:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"AST não disponível para o documento '{doc_id}'.",
                "request_id": message.get("request_id"),
            })

    async def get_academic_reasoning(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        dossier = await asyncio.to_thread(self.study_service.get_academic_reasoning_dossier, doc_id)
        if dossier:
            await self.connections.send(websocket, {
                "type": "study_academic_reasoning_result",
                "document_id": doc_id,
                "dossier": dossier,
                "request_id": message.get("request_id"),
            })
        else:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Dossier de raciocínio académico não disponível para '{doc_id}'.",
                "request_id": message.get("request_id"),
            })

    async def generate_academic_reasoning(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        force_recompute = bool(message.get("force_recompute", False))
        req_id = message.get("request_id")

        loop = asyncio.get_running_loop()

        def on_prog(stage: str, pct: float, msg: str):
            asyncio.run_coroutine_threadsafe(
                self.connections.send(websocket, {
                    "type": "study_academic_reasoning_progress",
                    "document_id": doc_id,
                    "stage": stage,
                    "progress": pct,
                    "message": msg,
                    "request_id": req_id,
                }),
                loop,
            )

        try:
            dossier = await asyncio.to_thread(
                self.study_service.generate_academic_reasoning,
                doc_id,
                force_recompute=force_recompute,
                on_progress=on_prog,
            )
            if dossier:
                await self.connections.send(websocket, {
                    "type": "study_academic_reasoning_result",
                    "document_id": doc_id,
                    "dossier": dossier,
                    "request_id": req_id,
                })
            else:
                await self.connections.send(websocket, {
                    "type": "study_error",
                    "message": f"Não foi possível gerar raciocínio académico para '{doc_id}'.",
                    "request_id": req_id,
                })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro durante raciocínio académico: {e}",
                "request_id": req_id,
            })

    async def get_editorial_plan(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        req_id = message.get("request_id")
        plan = await asyncio.to_thread(self.study_service.get_editorial_study_plan, doc_id)
        plan_status = await asyncio.to_thread(self.study_service.get_editorial_plan_status, doc_id)
        await self.connections.send(websocket, {
            "type": "study_editorial_plan_result",
            "document_id": doc_id,
            "plan": plan,
            "plan_status": plan_status,
            "request_id": req_id,
        })

    async def generate_editorial_plan(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        force_recompute = bool(message.get("force_recompute", False))
        auto_generate_dossier = bool(message.get("auto_generate_dossier", False))
        req_id = message.get("request_id")

        loop = asyncio.get_running_loop()

        def on_prog(stage: str, pct: float, msg: str):
            try:
                asyncio.run_coroutine_threadsafe(
                    self.connections.send(websocket, {
                        "type": "study_editorial_plan_progress",
                        "document_id": doc_id,
                        "stage": stage,
                        "progress": pct,
                        "message": msg,
                        "request_id": req_id,
                    }),
                    loop,
                )
            except Exception:
                pass

        try:
            plan = await asyncio.to_thread(
                self.study_service.generate_editorial_study_plan,
                doc_id,
                force_recompute=force_recompute,
                auto_generate_dossier=auto_generate_dossier,
                on_progress=on_prog,
            )
            plan_status = await asyncio.to_thread(self.study_service.get_editorial_plan_status, doc_id)
            if plan:
                await self.connections.send(websocket, {
                    "type": "study_editorial_plan_result",
                    "document_id": doc_id,
                    "plan": plan,
                    "plan_status": plan_status,
                    "request_id": req_id,
                })
            else:
                await self.connections.send(websocket, {
                    "type": "study_error",
                    "message": (
                        f"Não foi possível gerar o plano editorial para '{doc_id}': "
                        "dossier de raciocínio académico (Fase 3) não encontrado."
                    ),
                    "request_id": req_id,
                })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro durante planeamento editorial: {e}",
                "request_id": req_id,
            })

    async def get_generated_document_status(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        req_id = message.get("request_id")
        status = await asyncio.to_thread(self.study_service.get_study_document_generation_status, doc_id)
        await self.connections.send(websocket, {
            "type": "study_generated_document_status_result",
            "document_id": doc_id,
            "status": status,
            "request_id": req_id,
        })

    async def generate_study_document(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        req_id = message.get("request_id")
        force_recompute = bool(message.get("force_recompute", False))
        auto_generate_plan = bool(message.get("auto_generate_plan", False))
        design_profile_id = str(message.get("design_profile_id", "ACADEMIC_EDITORIAL_CLASSIC"))
        export_docx = bool(message.get("export_docx", True))

        loop = asyncio.get_running_loop()

        def on_prog(stage: str, pct: float, msg: str):
            try:
                asyncio.run_coroutine_threadsafe(
                    self.connections.send(websocket, {
                        "type": "study_generated_document_progress",
                        "document_id": doc_id,
                        "stage": stage,
                        "progress": pct,
                        "message": msg,
                        "request_id": req_id,
                    }),
                    loop,
                )
            except Exception:
                pass

        try:
            result = await asyncio.to_thread(
                self.study_service.generate_study_document,
                doc_id,
                design_profile_id=design_profile_id,
                export_docx=export_docx,
                force_recompute=force_recompute,
                auto_generate_plan=auto_generate_plan,
                on_progress=on_prog,
            )
            status = await asyncio.to_thread(self.study_service.get_study_document_generation_status, doc_id)
            if result:
                await self.connections.send(websocket, {
                    "type": "study_generated_document_result",
                    "document_id": doc_id,
                    "result": result,
                    "status": status,
                    "request_id": req_id,
                })
            else:
                await self.connections.send(websocket, {
                    "type": "study_error",
                    "message": (
                        f"Não foi possível gerar o documento de estudo para '{doc_id}': "
                        "plano editorial (Fase 4) ou dossier de raciocínio (Fase 3) não encontrados."
                    ),
                    "request_id": req_id,
                })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro durante geração do documento de estudo: {e}",
                "request_id": req_id,
            })

    async def get_generated_document_file(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        req_id = message.get("request_id")
        fmt = message.get("format", "pdf")
        version = message.get("version")
        if version is not None:
            try:
                version = int(version)
            except (ValueError, TypeError):
                version = None

        file_payload = await asyncio.to_thread(
            self.study_service.get_generated_study_document_file,
            doc_id,
            format_type=fmt,
            version=version,
        )
        if file_payload:
            await self.connections.send(websocket, {
                "type": "study_generated_document_file_result",
                "document_id": doc_id,
                "request_id": req_id,
                **file_payload,
            })
        else:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Ficheiro do documento de estudo ({fmt}) não encontrado para '{doc_id}'.",
                "request_id": req_id,
            })

    async def upload_document(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        filename = message.get("filename", "novo_documento.pdf")
        content_b64 = message.get("content_base64", "")
        content_text = message.get("content_text", "")
        subject = message.get("subject", "Geral")
        source_type = message.get("source_type")
        custom_title = message.get("title")

        # Broadcast estado de início de upload / processamento
        await self.connections.broadcast({
            "type": "study_document_processing",
            "filename": filename,
            "status": "EXTRACTING",
        })

        loop = asyncio.get_running_loop()
        def on_progress(status: str, percent: float, msg: str):
            try:
                asyncio.run_coroutine_threadsafe(
                    self.connections.broadcast({
                        "type": "study_document_processing",
                        "filename": filename,
                        "status": status,
                        "percent": percent,
                        "message": msg,
                    }),
                    loop,
                )
            except Exception:
                pass

        try:
            if content_b64:
                raw_bytes = base64.b64decode(content_b64)
                doc = await asyncio.to_thread(
                    self.study_service.ingest_document,
                    raw_bytes,
                    filename,
                    subject=subject,
                    source_type=source_type,
                    custom_title=custom_title,
                    progress_callback=on_progress,
                )
            elif content_text:
                raw_bytes = content_text.encode("utf-8")
                doc = await asyncio.to_thread(
                    self.study_service.ingest_document,
                    raw_bytes,
                    filename,
                    subject=subject,
                    source_type=source_type or "TXT",
                    custom_title=custom_title,
                    progress_callback=on_progress,
                )
            else:
                # Verificar se file_path foi passado
                file_path = message.get("file_path")
                if file_path and os.path.exists(file_path):
                    doc = await asyncio.to_thread(
                        self.study_service.ingest_document,
                        file_path,
                        filename,
                        subject=subject,
                        source_type=source_type,
                        custom_title=custom_title,
                        progress_callback=on_progress,
                    )
                else:
                    raise ValueError("Conteúdo do documento não fornecido (content_base64, content_text ou file_path).")

            # Broadcast de sucesso
            await self.connections.broadcast({
                "type": "study_document_ready",
                "event": "study.document_ready",
                "document": doc.to_dict(),
            })

            # Atualizar lista de documentos em todos os clientes
            docs = [d.to_dict() for d in self.study_service.list_documents()]
            docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
            await self.connections.broadcast({
                "type": "study_documents_list",
                "event": "study.document_added",
                "documents": docs,
            })

        except Exception as e:
            log_event(self.logger, "study.upload_failed", filename=filename, error=str(e))
            print(f"[Study] Erro no upload de '{filename}': {e}", flush=True)
            await self.connections.broadcast({
                "type": "study_document_failed",
                "filename": filename,
                "error": str(e),
            })

    async def delete_document(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        delete_file = bool(message.get("delete_file", True))
        if not doc_id:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": "ID do documento não fornecido para eliminação.",
            })
            return

        try:
            success = await asyncio.to_thread(self.study_service.delete_document, doc_id, delete_file)
            if success:
                log_event(self.logger, "study.document_deleted", document_id=doc_id)
                docs = [d.to_dict() for d in self.study_service.list_documents()]
                docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
                await self.connections.broadcast({
                    "type": "study_document_deleted",
                    "document_id": doc_id,
                    "success": True,
                })
                await self.connections.broadcast({
                    "type": "study_documents_list",
                    "event": "study.document_deleted",
                    "documents": docs,
                })
            else:
                await self.connections.send(websocket, {
                    "type": "study_error",
                    "message": f"Documento '{doc_id}' não encontrado para eliminação.",
                })
        except Exception as e:
            log_event(self.logger, "study.delete_failed", document_id=doc_id, error=str(e))
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao eliminar documento '{doc_id}': {e}",
            })

    async def update_progress(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        page = int(message.get("current_page", 1))
        sec = str(message.get("current_section", ""))
        scroll = int(message.get("scroll_position", 0))

        try:
            progress = await asyncio.to_thread(
                self.study_service.update_reading_progress,
                doc_id,
                page,
                sec,
                scroll,
            )
            await self.connections.send(websocket, {
                "type": "study_progress_updated",
                "document_id": doc_id,
                "reading_progress": progress,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": str(e),
            })

    async def contextual_assist(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        action = message.get("action", "explain")  # translate, explain, summarize_section, define_concept, explain_figure, explain_table
        selected_text = message.get("selected_text", "")
        section_id = message.get("section_id")
        page_num = message.get("page_number")
        level = message.get("level", "Intermédio")

        result = await asyncio.to_thread(
            self.study_service.contextual_assist,
            doc_id,
            action,
            selected_text,
            section_id=section_id,
            page_number=page_num,
            level=level,
            media_id=message.get("media_id"),
        )

        await self.connections.send(websocket, {
            "type": "study_contextual_assist_result",
            "document_id": doc_id,
            "request_id": message.get("request_id"),
            **result,
        })

    async def ask_paper(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        question = message.get("question", "")
        section_id = message.get("section_id")

        result = await asyncio.to_thread(
            self.study_service.ask_paper,
            doc_id,
            question,
            section_id=section_id,
        )

        await self.connections.send(websocket, {
            "type": "study_ask_paper_result",
            "document_id": doc_id,
            "request_id": message.get("request_id"),
            **result,
        })

    async def cancel_generation(
        self,
        websocket: Any,
        message: dict,
        _session: Optional[WebSocketSessionState] = None,
    ) -> None:
        doc_id = message.get("document_id", "")
        from services.study_ai_engine import cancel_study_generation
        cancelled = cancel_study_generation(doc_id or "global")
        if hasattr(self.connections, "broadcast"):
            b_coro = self.connections.broadcast({
                "type": "study_document_processing",
                "document_id": doc_id,
                "status": "CANCELLED",
                "percent": 100.0,
                "message": "Geração cancelada pelo utilizador.",
            })
            if asyncio.iscoroutine(b_coro):
                await b_coro
        await self.connections.send(websocket, {
            "type": "study_generation_cancelled",
            "document_id": doc_id,
            "cancelled": cancelled,
            "request_id": message.get("request_id"),
        })

    async def generate_summary(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        mode = message.get("mode", "Study")
        force_regenerate = bool(message.get("force_regenerate", False))

        try:
            summary = await asyncio.to_thread(
                self.study_service.generate_summary,
                doc_id,
                mode=mode,
                force_regenerate=force_regenerate,
            )
            doc = self.study_service.documents.get(doc_id)
            if doc and hasattr(self.connections, "broadcast"):
                b_coro = self.connections.broadcast({
                    "type": "study_document_ready",
                    "event": "study.document_ready",
                    "document": doc.to_dict(),
                })
                if asyncio.iscoroutine(b_coro):
                    await b_coro

            await self.connections.send(websocket, {
                "type": "study_summary_ready",
                "document_id": doc_id,
                "mode": mode,
                "request_id": message.get("request_id"),
                "summary": summary,
                "summaries": (doc.metadata or {}).get("summaries", {}) if doc else summary.get("summaries", {}),
                "generation_mode": (doc.metadata or {}).get("generation_mode", "EXTRACTIVE_GROUNDED") if doc else summary.get("generation_mode", "EXTRACTIVE_GROUNDED"),
                "generation_telemetry": (doc.metadata or {}).get("generation_telemetry", {}) if doc else summary.get("generation_telemetry", {}),
                "artifact_modes": (doc.metadata or {}).get("artifact_modes", {}) if doc else summary.get("artifact_modes", {}),
                "unavailable_generative_features": (doc.metadata or {}).get("unavailable_generative_features", []) if doc else summary.get("unavailable_generative_features", []),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "request_id": message.get("request_id"),
                "message": str(e),
            })

    async def generate_cornell(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        force_regenerate = bool(message.get("force_regenerate", False))
        try:
            cornell = await asyncio.to_thread(
                self.study_service.generate_cornell_from_document,
                doc_id,
                force_regenerate=force_regenerate,
            )
            doc = self.study_service.documents.get(doc_id)
            if doc and hasattr(self.connections, "broadcast"):
                b_coro = self.connections.broadcast({
                    "type": "study_document_ready",
                    "event": "study.document_ready",
                    "document": doc.to_dict(),
                })
                if asyncio.iscoroutine(b_coro):
                    await b_coro
            await self.connections.send(websocket, {
                "type": "study_notes_ready",
                "document_id": doc_id,
                "request_id": message.get("request_id"),
                "cornell": cornell,
                "generation_mode": (doc.metadata or {}).get("generation_mode", "EXTRACTIVE_GROUNDED") if doc else cornell.get("generation_mode", "EXTRACTIVE_GROUNDED"),
                "generation_telemetry": (doc.metadata or {}).get("generation_telemetry", {}) if doc else {},
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "request_id": message.get("request_id"),
                "message": str(e),
            })

    async def save_to_knowledge(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        title = message.get("title", "Nota de Estudo")
        content = message.get("content") or message.get("markdown_content", "")
        subject = message.get("subject", "Geral")
        doc_ids = message.get("source_document_ids", [])

        try:
            path = await asyncio.to_thread(
                self.study_service.save_to_knowledge_vault,
                title,
                content,
                subject=subject,
                source_document_ids=doc_ids,
            )
            await self.connections.broadcast({
                "type": "study_knowledge_saved",
                "title": title,
                "vault_path": path.replace("\\", "/"),
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "request_id": message.get("request_id"),
                "message": str(e),
            })

    async def generate_quiz(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        count = int(message.get("question_count", 5))

        try:
            quiz = await asyncio.to_thread(
                self.study_service.generate_quiz,
                doc_id,
                question_count=count,
            )
            await self.connections.send(websocket, {
                "type": "study_quiz_ready",
                "document_id": doc_id,
                "request_id": message.get("request_id"),
                "quiz": {
                    "quiz_id": quiz.quiz_id,
                    "topic": quiz.topic,
                    "questions": quiz.questions,
                    "transfer_question": quiz.transfer_question,
                },
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": str(e),
            })

    async def submit_quiz(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        quiz_id = message.get("quiz_id", "")
        answers = message.get("answers", {})
        transfer_answer = message.get("transfer_answer", "")

        try:
            result = await asyncio.to_thread(
                self.study_service.evaluate_quiz,
                quiz_id,
                answers,
                transfer_answer,
            )
            await self.connections.send(websocket, {
                "type": "study_quiz_evaluated",
                "quiz_id": quiz_id,
                "request_id": message.get("request_id"),
                **result,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": str(e),
            })

    async def search_rag(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        query = message.get("query", "")
        doc_id = message.get("document_id", "")
        req_id = message.get("request_id")
        try:
            results = await asyncio.to_thread(
                self.study_service.search_study_rag,
                query,
                document_id=doc_id,
            )
            await self.connections.send(websocket, {
                "type": "study_search_rag_result",
                "document_id": doc_id,
                "request_id": req_id,
                "results": results,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_search_rag_result",
                "document_id": doc_id,
                "request_id": req_id,
                "results": [],
                "error": str(e),
            })

    async def list_flashcards(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id")
        if doc_id and not any(fc.document_id == doc_id for fc in self.study_service.flashcards.values()):
            # Auto-gerar se não existirem ainda
            await asyncio.to_thread(self.study_service.generate_flashcards, doc_id)

        cards = [
            asdict(fc)
            for fc in self.study_service.flashcards.values()
            if not doc_id or fc.document_id == doc_id
        ]
        await self.connections.send(websocket, {
            "type": "study_flashcards_list",
            "flashcards": cards,
        })

    async def review_flashcard(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        card_id = message.get("card_id", "")
        action = message.get("rating") or message.get("action") or "Good"  # Again, Hard, Good, Easy

        try:
            fc = await asyncio.to_thread(
                self.study_service.review_flashcard,
                card_id,
                action,
            )
            await self.connections.send(websocket, {
                "type": "study_flashcard_reviewed",
                "flashcard": asdict(fc),
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": str(e),
            })

    async def add_reading_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        page = int(message.get("page", 1))
        selection = message.get("selection", "")
        note_text = message.get("note", "")
        sec_id = message.get("section_id", "")

        note = await asyncio.to_thread(
            self.study_service.add_reading_note,
            doc_id,
            page,
            selection,
            note_text,
            section_id=sec_id,
        )
        await self.connections.send(websocket, {
            "type": "study_note_added",
            "note": asdict(note),
        })

    async def add_highlight(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        page = int(message.get("page", 1))
        text = message.get("selected_text", "")
        ctx = message.get("context", "")
        color = message.get("color", "yellow")

        hl = await asyncio.to_thread(
            self.study_service.add_highlight,
            doc_id,
            page,
            text,
            context=ctx,
            color=color,
        )
        await self.connections.send(websocket, {
            "type": "study_highlight_added",
            "highlight": asdict(hl),
        })

    async def synthesize_documents(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_ids = message.get("document_ids", [])
        req_id = message.get("request_id")
        try:
            result = await asyncio.to_thread(
                self.study_service.synthesize_documents,
                doc_ids,
            )
            await self.connections.send(websocket, {
                "type": "study_synthesis_ready",
                "request_id": req_id,
                **result,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "request_id": req_id,
                "message": str(e),
            })

    async def list_collections(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        cols = [asdict(c) for c in self.study_service.collections.values()]
        await self.connections.send(websocket, {
            "type": "study_collections_list",
            "collections": cols,
        })

    async def create_collection(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        name = message.get("name", "Nova Coleção")
        subject = message.get("subject", "Geral")
        doc_ids = message.get("document_ids", [])
        req_id = message.get("request_id")

        col = self.study_service.create_collection(
            name=name,
            subject=subject,
            document_ids=doc_ids,
        )

        res = {
            "type": "study_collection_created",
            "collection": asdict(col),
            "request_id": req_id,
        }
        await self.connections.send(websocket, res)
        await self.connections.broadcast(res)

    async def link_folder(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        collection_id = message.get("collection_id", "")
        folder_path = message.get("folder_path", "")
        sync_enabled = bool(message.get("sync_enabled", True))
        recursive = bool(message.get("recursive", True))
        req_id = message.get("request_id")

        try:
            result = await asyncio.to_thread(
                self.study_service.link_folder_to_collection,
                collection_id,
                folder_path,
                sync_enabled=sync_enabled,
                recursive=recursive,
            )
            if hasattr(result.get("report"), "to_dict"):
                result["report"] = result["report"].to_dict()
            await self.connections.send(websocket, {
                "type": "study_folder_linked",
                "request_id": req_id,
                **result,
            })
            cols = [c.to_dict() for c in self.study_service.list_collections()]
            await self.connections.broadcast({
                "type": "study_collections_list",
                "collections": cols,
            })
            docs = [d.to_dict() for d in self.study_service.list_documents()]
            docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
            await self.connections.broadcast({
                "type": "study_documents_list",
                "documents": docs,
            })
        except Exception as e:
            log_event(self.logger, "study.link_folder_failed", collection_id=collection_id, error=str(e))
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao vincular pasta: {e}",
                "request_id": req_id,
            })

    async def unlink_folder(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        collection_id = message.get("collection_id", "")
        folder_path = message.get("folder_path", "")
        remove_materials = bool(message.get("remove_materials", False))
        req_id = message.get("request_id")

        try:
            result = await asyncio.to_thread(
                self.study_service.unlink_folder_from_collection,
                collection_id,
                folder_path,
                remove_materials=remove_materials,
            )
            await self.connections.send(websocket, {
                "type": "study_folder_unlinked",
                "request_id": req_id,
                **result,
            })
            cols = [c.to_dict() for c in self.study_service.list_collections()]
            await self.connections.broadcast({
                "type": "study_collections_list",
                "collections": cols,
            })
            docs = [d.to_dict() for d in self.study_service.list_documents()]
            docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
            await self.connections.broadcast({
                "type": "study_documents_list",
                "documents": docs,
            })
        except Exception as e:
            log_event(self.logger, "study.unlink_folder_failed", collection_id=collection_id, error=str(e))
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao desvincular pasta: {e}",
                "request_id": req_id,
            })

    async def sync_folder(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        collection_id = message.get("collection_id", "")
        folder_path = message.get("folder_path")
        req_id = message.get("request_id")

        try:
            report = await asyncio.to_thread(
                self.study_service.sync_collection_folder,
                collection_id,
                folder_path,
            )
            await self.connections.send(websocket, {
                "type": "study_folder_synced",
                "request_id": req_id,
                "report": report.to_dict(),
            })
            docs = [d.to_dict() for d in self.study_service.list_documents()]
            docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
            await self.connections.broadcast({
                "type": "study_documents_list",
                "documents": docs,
            })
            cols = [c.to_dict() for c in self.study_service.list_collections()]
            await self.connections.broadcast({
                "type": "study_collections_list",
                "collections": cols,
            })
        except Exception as e:
            log_event(self.logger, "study.sync_folder_failed", collection_id=collection_id, error=str(e))
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao sincronizar pasta: {e}",
                "request_id": req_id,
            })

    async def ask_course(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        collection_id = message.get("collection_id", "")
        question = message.get("question", "")
        req_id = message.get("request_id")

        try:
            result = await asyncio.to_thread(
                self.study_service.ask_course,
                collection_id,
                question,
            )
            await self.connections.send(websocket, {
                "type": "study_ask_course_result",
                "collection_id": collection_id,
                "request_id": req_id,
                **result,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro na consulta do curso: {e}",
                "request_id": req_id,
            })

    async def get_course_details(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        collection_id = message.get("collection_id", "")
        req_id = message.get("request_id")

        try:
            details = await asyncio.to_thread(
                self.study_service.get_course_details,
                collection_id,
            )
            await self.connections.send(websocket, {
                "type": "study_course_details",
                "request_id": req_id,
                **details,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao obter detalhes do curso: {e}",
                "request_id": req_id,
            })

    async def retry_document(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        document_id = message.get("document_id", "")
        req_id = message.get("request_id")

        try:
            doc = await asyncio.to_thread(
                self.study_service.retry_document,
                document_id,
            )
            await self.connections.send(websocket, {
                "type": "study_document_ready",
                "request_id": req_id,
                "document": doc.to_dict(),
            })
            docs = [d.to_dict() for d in self.study_service.list_documents()]
            docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
            await self.connections.broadcast({
                "type": "study_documents_list",
                "documents": docs,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Falha ao retentar processamento de '{document_id}': {e}",
                "request_id": req_id,
            })

    # =========================================================================
    # Video Intelligence Handlers
    # =========================================================================

    async def get_video_context(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        timestamp = float(message.get("timestamp", 0.0))
        try:
            result = self.study_service.get_video_context(doc_id, timestamp)
            await self.connections.send(websocket, {
                "type": "study_video_context_result",
                "document_id": doc_id,
                "timestamp": timestamp,
                "context": result,
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao obter contexto do vídeo: {str(e)}",
                "request_id": message.get("request_id"),
            })

    async def explain_video_moment(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        timestamp = float(message.get("timestamp", 0.0))
        try:
            result = await asyncio.to_thread(
                self.study_service.explain_video_moment,
                doc_id,
                timestamp,
            )
            await self.connections.send(websocket, {
                "type": "study_explain_video_moment_result",
                "document_id": doc_id,
                "timestamp": timestamp,
                **result,
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao explicar momento do vídeo: {str(e)}",
                "request_id": message.get("request_id"),
            })

    async def explain_video_visual(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        timestamp = float(message.get("timestamp", 0.0))
        try:
            result = await asyncio.to_thread(
                self.study_service.explain_video_visual,
                doc_id,
                timestamp,
            )
            await self.connections.send(websocket, {
                "type": "study_explain_video_visual_result",
                "document_id": doc_id,
                "timestamp": timestamp,
                **result,
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao explicar visual do vídeo: {str(e)}",
                "request_id": message.get("request_id"),
            })

    async def search_video_transcript(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        query = message.get("query", "")
        try:
            results = self.study_service.search_video_transcript(doc_id, query)
            await self.connections.send(websocket, {
                "type": "study_search_video_transcript_result",
                "document_id": doc_id,
                "query": query,
                "occurrences": len(results),
                "results": results,
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro na pesquisa de transcrição: {str(e)}",
                "request_id": message.get("request_id"),
            })

    async def ask_video(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        question = message.get("question", "")
        timestamp = float(message.get("timestamp", 0.0)) if message.get("timestamp") is not None else None
        try:
            result = await asyncio.to_thread(
                self.study_service.ask_video,
                doc_id,
                question,
                timestamp,
            )
            await self.connections.send(websocket, {
                "type": "study_ask_video_result",
                "document_id": doc_id,
                "question": question,
                **result,
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao perguntar ao vídeo: {str(e)}",
                "request_id": message.get("request_id"),
            })

    async def save_video_note(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        timestamp = float(message.get("timestamp", 0.0))
        note_text = message.get("note_text", "")
        frame_id = message.get("frame_id")
        selected_text = message.get("selected_text")
        try:
            note = self.study_service.save_video_note(
                doc_id, timestamp, note_text, frame_id, selected_text
            )
            await self.connections.send(websocket, {
                "type": "study_video_note_saved",
                "document_id": doc_id,
                "note": note,
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao salvar nota do vídeo: {str(e)}",
                "request_id": message.get("request_id"),
            })

    async def update_video_progress(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        timestamp = float(message.get("timestamp", 0.0))
        progress_percent = float(message.get("progress_percent", 0.0))
        try:
            prog = self.study_service.update_video_progress(doc_id, timestamp, progress_percent)
            await self.connections.send(websocket, {
                "type": "study_video_progress_updated",
                "document_id": doc_id,
                "progress": prog,
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": f"Erro ao atualizar progresso do vídeo: {str(e)}",
                "request_id": message.get("request_id"),
            })

    async def ingest_video_url(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        url = message.get("url", "")
        subject = message.get("subject", "Geral")
        title = message.get("title")
        loop = asyncio.get_running_loop()
        def on_progress(status: str, percent: float, msg: str):
            try:
                asyncio.run_coroutine_threadsafe(
                    self.connections.broadcast({
                        "type": "study_document_processing",
                        "filename": url,
                        "status": status,
                        "percent": percent,
                        "message": msg,
                    }),
                    loop,
                )
            except Exception:
                pass

        try:
            doc = await asyncio.to_thread(
                self.study_service.ingest_video_url,
                url,
                subject,
                title,
                on_progress,
            )
            await self.connections.broadcast({
                "type": "study_document_ready",
                "event": "study.document_ready",
                "document": doc.to_dict(),
            })
            docs = [d.to_dict() for d in self.study_service.list_documents()]
            docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
            await self.connections.broadcast({
                "type": "study_documents_list",
                "event": "study.document_added",
                "documents": docs,
            })
            await self.connections.send(websocket, {
                "type": "study_video_url_ingested",
                "document": doc.to_dict(),
                "request_id": message.get("request_id"),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_document_failed",
                "filename": url,
                "error": str(e),
                "request_id": message.get("request_id"),
            })

    # ------------------------------------------------------------------
    # Phase 6 — Study Modes, Active Recall & Adaptive Learning Handlers
    # ------------------------------------------------------------------

    async def _dispatch_phase6(
        self,
        websocket: Any,
        message: dict,
        result_type: str,
        fn: Any,
        *,
        extra_fields: Optional[Dict[str, Any]] = None,
        with_progress: bool = False,
    ) -> None:
        req_id = message.get("request_id")
        doc_id = str(message.get("document_id") or "")
        loop = asyncio.get_running_loop()

        def on_prog(stage: str, pct: float, msg_txt: str) -> None:
            if not with_progress:
                return
            try:
                asyncio.run_coroutine_threadsafe(
                    self.connections.send(websocket, {
                        "type": "study_mode_progress_event",
                        "document_id": doc_id,
                        "stage": stage,
                        "progress": pct,
                        "message": msg_txt,
                        "request_id": req_id,
                    }),
                    loop,
                )
            except Exception:
                pass

        try:
            res = await asyncio.to_thread(fn, on_prog) if with_progress else await asyncio.to_thread(fn)
            payload: Dict[str, Any] = {
                "type": result_type,
                "document_id": doc_id,
                "request_id": req_id,
            }
            if isinstance(res, dict):
                payload.update(res)
            else:
                payload["data"] = res
            if extra_fields:
                payload.update(extra_fields)
            await self.connections.send(websocket, payload)
        except Exception as exc:
            await self.connections.send(websocket, {
                "type": "study_error",
                "document_id": doc_id,
                "message": str(exc),
                "request_id": req_id,
            })

    async def phase6_get_readiness(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_readiness_result",
            lambda: {"readiness": self.study_service.get_study_mode_readiness(doc_id)},
        )

    async def phase6_get_flashcards(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_flashcards_result",
            lambda: self.study_service.get_adaptive_flashcards(doc_id),
        )

    async def phase6_generate_flashcards(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        force = bool(msg.get("force_regenerate", False))
        target = int(msg.get("target_cards", 16))
        await self._dispatch_phase6(
            ws, msg, "study_mode_flashcards_result",
            lambda on_p: self.study_service.generate_adaptive_flashcards(
                doc_id, force_regenerate=force, target_cards=target, on_progress=on_p
            ),
            with_progress=True,
        )

    async def phase6_edit_flashcard(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        card_id = str(msg.get("card_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_flashcard_saved",
            lambda: {
                "flashcard": self.study_service.edit_adaptive_flashcard(
                    doc_id,
                    card_id,
                    front=msg.get("front"),
                    back=msg.get("back"),
                    topic=msg.get("topic"),
                    question_difficulty=msg.get("question_difficulty"),
                )
            },
        )

    async def phase6_delete_flashcard(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        card_id = str(msg.get("card_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_flashcard_deleted",
            lambda: {"card_id": card_id, "deleted": self.study_service.delete_adaptive_flashcard(doc_id, card_id)},
        )

    async def phase6_create_flashcard(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_flashcard_saved",
            lambda: {
                "flashcard": self.study_service.create_adaptive_flashcard(
                    doc_id,
                    front=str(msg.get("front") or ""),
                    back=str(msg.get("back") or ""),
                    chapter_id=str(msg.get("chapter_id") or ""),
                    section_id=str(msg.get("section_id") or ""),
                    topic=str(msg.get("topic") or ""),
                    question_difficulty=str(msg.get("question_difficulty") or "MEDIUM"),
                    card_type=str(msg.get("card_type") or "CONCEPTUAL_UNDERSTANDING"),
                )
            },
        )

    async def phase6_regenerate_flashcard(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        card_id = str(msg.get("card_id") or "")
        overwrite = bool(msg.get("allow_overwrite_edited", False))
        await self._dispatch_phase6(
            ws, msg, "study_mode_flashcard_saved",
            lambda: {
                "flashcard": self.study_service.regenerate_adaptive_flashcard(
                    doc_id, card_id, allow_overwrite_edited=overwrite
                )
            },
        )

    async def phase6_review_flashcard(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        card_id = str(msg.get("card_id") or "")
        rating = str(msg.get("rating") or "Good")
        confidence = int(msg.get("confidence", 3))
        await self._dispatch_phase6(
            ws, msg, "study_mode_flashcard_reviewed",
            lambda: self.study_service.review_adaptive_flashcard(doc_id, card_id, rating, confidence=confidence),
        )

    async def phase6_get_cornell(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_cornell_result",
            lambda: {
                "cornell": self.study_service.get_phase6_cornell(doc_id),
                "readiness": self.study_service.get_study_mode_readiness(doc_id),
            },
        )

    async def phase6_generate_cornell(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        force = bool(msg.get("force_regenerate", False))
        await self._dispatch_phase6(
            ws, msg, "study_mode_cornell_result",
            lambda on_p: {
                "cornell": self.study_service.generate_phase6_cornell(
                    doc_id, force_regenerate=force, on_progress=on_p
                ),
                "readiness": self.study_service.get_study_mode_readiness(doc_id),
            },
            with_progress=True,
        )

    async def phase6_edit_cornell_entry(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        sec_id = str(msg.get("section_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_cornell_entry_saved",
            lambda: {
                "entry": self.study_service.edit_phase6_cornell_entry(
                    doc_id,
                    sec_id,
                    summary_section=msg.get("summary_section"),
                    explanations=msg.get("explanations"),
                    supporting_details=msg.get("supporting_details"),
                    cue_column=msg.get("cue_column"),
                    is_important=msg.get("is_important"),
                )
            },
        )

    async def phase6_add_cornell_note(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        sec_id = str(msg.get("section_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_cornell_note_saved",
            lambda: {
                "section_id": sec_id,
                "personal_note": self.study_service.add_phase6_cornell_personal_note(
                    doc_id,
                    sec_id,
                    str(msg.get("content") or ""),
                    is_important=bool(msg.get("is_important", False)),
                ),
            },
        )

    async def phase6_export_cornell_vault(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_cornell_exported",
            lambda: self.study_service.export_phase6_cornell_to_vault(doc_id),
        )

    async def phase6_get_assessments(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_assessments_result",
            lambda: self.study_service.get_phase6_assessments(doc_id),
        )

    async def phase6_generate_assessment(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        cfg = msg.get("config") or {}
        await self._dispatch_phase6(
            ws, msg, "study_mode_assessment_generated",
            lambda on_p: {"assessment": self.study_service.generate_phase6_assessment(doc_id, cfg, on_progress=on_p)},
            with_progress=True,
        )

    async def phase6_check_question(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_question_checked",
            lambda: {
                "outcome": self.study_service.check_phase6_question(
                    doc_id,
                    str(msg.get("assessment_id") or ""),
                    str(msg.get("question_id") or ""),
                    msg.get("answer"),
                    use_llm_for_open=bool(msg.get("use_llm_for_open", False)),
                )
            },
        )

    async def phase6_submit_assessment(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_assessment_submitted",
            lambda: self.study_service.submit_phase6_assessment(
                doc_id,
                str(msg.get("assessment_id") or ""),
                dict(msg.get("answers") or {}),
                use_llm_for_open=bool(msg.get("use_llm_for_open", False)),
            ),
        )

    async def phase6_get_active_recall(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_active_recall_result",
            lambda: self.study_service.get_active_recall_prompts(doc_id),
        )

    async def phase6_generate_active_recall(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        force = bool(msg.get("force_regenerate", False))
        target = int(msg.get("target_prompts", 8))
        await self._dispatch_phase6(
            ws, msg, "study_mode_active_recall_result",
            lambda on_p: self.study_service.generate_active_recall(
                doc_id, force_regenerate=force, target_prompts=target, on_progress=on_p
            ),
            with_progress=True,
        )

    async def phase6_submit_active_recall(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_active_recall_submitted",
            lambda: self.study_service.submit_active_recall_attempt(
                doc_id,
                str(msg.get("prompt_id") or ""),
                student_response=str(msg.get("student_response") or ""),
                self_confidence=int(msg.get("self_confidence", 3)),
                outline_used=bool(msg.get("outline_used", False)),
                use_llm=bool(msg.get("use_llm", False)),
            ),
        )

    async def phase6_get_daily_queue(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_daily_queue_result",
            lambda: {
                "queue": self.study_service.get_daily_review_queue(
                    doc_id,
                    daily_new_limit=int(msg.get("daily_new_limit", 10)),
                    daily_review_limit=int(msg.get("daily_review_limit", 30)),
                )
            },
        )

    async def phase6_get_progress(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_progress_result",
            lambda: {
                "progress": self.study_service.get_learning_progress(
                    doc_id, recompute=bool(msg.get("recompute", True))
                )
            },
        )

    async def phase6_start_session(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = str(msg.get("document_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_session_updated",
            lambda: {
                "session": self.study_service.start_study_session(
                    document_id=doc_id,
                    mode=str(msg.get("mode") or "FLASHCARD_REVIEW"),
                    title=str(msg.get("title") or ""),
                    item_ids=msg.get("item_ids") or [],
                    config=msg.get("config") or {},
                )
            },
        )

    async def phase6_update_session(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        sid = str(msg.get("session_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_session_updated",
            lambda: {
                "session": self.study_service.record_study_session_step(
                    sid,
                    item_id=msg.get("item_id"),
                    partial_response=msg.get("partial_response"),
                    outcome=msg.get("outcome"),
                    next_index=msg.get("next_index"),
                    mark_completed=bool(msg.get("mark_completed", False)),
                )
            },
        )

    async def phase6_pause_session(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        sid = str(msg.get("session_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_session_updated",
            lambda: {"session": self.study_service.pause_study_session(sid)},
        )

    async def phase6_resume_session(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        sid = str(msg.get("session_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_session_updated",
            lambda: {"session": self.study_service.resume_study_session(sid)},
        )

    async def phase6_complete_session(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        sid = str(msg.get("session_id") or "")
        await self._dispatch_phase6(
            ws, msg, "study_mode_session_updated",
            lambda: {
                "session": self.study_service.complete_study_session(
                    sid, summary_stats=msg.get("summary_stats")
                )
            },
        )

    async def phase6_list_sessions(self, ws: Any, msg: dict, _: WebSocketSessionState) -> None:
        doc_id = msg.get("document_id")
        status = msg.get("status")
        await self._dispatch_phase6(
            ws, msg, "study_mode_sessions_list",
            lambda: {"sessions": self.study_service.list_study_sessions(document_id=doc_id, status=status)},
        )
