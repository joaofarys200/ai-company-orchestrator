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
import os
import time
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
    # Study Video Intelligence
    "study_get_video_context": "get_video_context",
    "study_explain_video_moment": "explain_video_moment",
    "study_explain_video_visual": "explain_video_visual",
    "study_search_video_transcript": "search_video_transcript",
    "study_ask_video": "ask_video",
    "study_save_video_note": "save_video_note",
    "study_update_video_progress": "update_video_progress",
    "study_ingest_video_url": "ingest_video_url",
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
        if not os.path.exists(file_path):
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

    async def generate_summary(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        mode = message.get("mode", "Study")

        try:
            summary = await asyncio.to_thread(
                self.study_service.generate_summary,
                doc_id,
                mode=mode,
            )
            await self.connections.send(websocket, {
                "type": "study_summary_ready",
                "document_id": doc_id,
                "summary": summary,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": str(e),
            })

    async def generate_cornell(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        doc_id = message.get("document_id", "")
        try:
            cornell = await asyncio.to_thread(
                self.study_service.generate_cornell_from_document,
                doc_id,
            )
            await self.connections.send(websocket, {
                "type": "study_notes_ready",
                "document_id": doc_id,
                "cornell": cornell,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": str(e),
            })

    async def save_to_knowledge(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        title = message.get("title", "Nota de Estudo")
        content = message.get("content", "")
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
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
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
                **result,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
                "message": str(e),
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
        action = message.get("action", "Good")  # Again, Hard, Good, Easy

        try:
            fc = await asyncio.to_thread(
                self.study_service.review_flashcard,
                card_id,
                action,
            )
            await self.connections.send(websocket, {
                "type": "study_flashcard_reviewed",
                "flashcard": asdict(fc),
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
        try:
            result = await asyncio.to_thread(
                self.study_service.synthesize_documents,
                doc_ids,
            )
            await self.connections.send(websocket, {
                "type": "study_synthesis_ready",
                **result,
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "study_error",
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
        cid = f"col_{uuid.uuid4().hex[:8]}"

        from services.study_service import StudyCollection
        col = StudyCollection(
            collection_id=cid,
            name=name,
            subject=subject,
            document_ids=doc_ids,
            created_at=datetime.now().isoformat(),
        )
        self.study_service.collections[cid] = col
        self.study_service._save_collections()

        await self.connections.broadcast({
            "type": "study_collection_created",
            "collection": asdict(col),
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
