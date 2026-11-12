"""
JARVIS OS — Study Engine Phase 7: Context & Disambiguation Manager
Mantém referências ligeiras de contexto académico por sessão de conversa,
respeitando isolamento estrito entre documentos e persistência atómica.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Dict, List, Optional, Tuple
import unicodedata

from services.study_integration.contracts import (
    StudyConversationContext,
    _utc_now_iso,
    normalize_chat_session_id,
)


_ORDINAL_CHAPTER_WORDS: Dict[str, int] = {
    "primeiro": 1,
    "primeira": 1,
    "first": 1,
    "1": 1,
    "segundo": 2,
    "segunda": 2,
    "second": 2,
    "2": 2,
    "terceiro": 3,
    "terceira": 3,
    "third": 3,
    "3": 3,
    "quarto": 4,
    "quarta": 4,
    "fourth": 4,
    "4": 4,
    "quinto": 5,
    "quinta": 5,
    "fifth": 5,
    "5": 5,
    "sexto": 6,
    "sexta": 6,
    "sixth": 6,
    "6": 6,
    "setimo": 7,
    "sétimo": 7,
    "7": 7,
    "oitavo": 8,
    "eighth": 8,
    "8": 8,
    "nono": 9,
    "nona": 9,
    "9": 9,
    "decimo": 10,
    "décimo": 10,
    "10": 10,
}


def normalize_match_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(text or ""))
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip().lower()


@dataclass
class DocumentResolutionResult:
    status: str  # RESOLVED | AMBIGUOUS | NOT_FOUND | UNBOUND
    document: Any = None
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""


@dataclass
class ChapterResolutionResult:
    status: str  # RESOLVED | NONE_REQUESTED | NOT_FOUND | AMBIGUOUS
    chapter_id: Optional[str] = None
    chapter_title: Optional[str] = None
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    source_section_ids: List[str] = field(default_factory=list)
    message: str = ""


class StudyContextManager:
    """Gestão thread-safe e persistente de contexto conversacional do Study Engine."""

    def __init__(self, storage_dir: Path | str = Path("data/study")) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.context_path = self.storage_dir / "jarvis_study_context.json"
        self._lock = threading.Lock()
        self._contexts: Dict[str, StudyConversationContext] = self._load_contexts()

    def _load_contexts(self) -> Dict[str, StudyConversationContext]:
        if not self.context_path.exists():
            return {}
        from services.study_fs import read_json_safe
        raw, corrupt = read_json_safe(
            self.context_path, default={}, expected_type=dict, backup_on_corrupt=True
        )
        if corrupt or not isinstance(raw, dict):
            return {}
        try:
            loaded: Dict[str, StudyConversationContext] = {}
            for sid, item in raw.items():
                norm_sid = normalize_chat_session_id(sid)
                if norm_sid and isinstance(item, dict):
                    loaded[norm_sid] = StudyConversationContext.from_dict(
                        {**item, "chat_session_id": norm_sid}
                    )
            return loaded
        except Exception:
            return {}

    def _save_contexts(self) -> None:
        from services.study_fs import atomic_write_json
        payload = {sid: ctx.to_dict() for sid, ctx in self._contexts.items()}
        atomic_write_json(self.context_path, payload, indent=2)

    def get_context(self, chat_session_id: Optional[str] = None) -> StudyConversationContext:
        sid = normalize_chat_session_id(chat_session_id)
        if sid is None:
            return StudyConversationContext(chat_session_id="")
        with self._lock:
            ctx = self._contexts.get(sid)
            if ctx is None:
                ctx = StudyConversationContext(chat_session_id=sid)
                self._contexts[sid] = ctx
            return StudyConversationContext.from_dict(ctx.to_dict())

    def sync_ui_context(
        self,
        chat_session_id: Optional[str],
        study_service: Any,
        ui_context: Optional[Dict[str, Any]],
    ) -> StudyConversationContext:
        sid = normalize_chat_session_id(chat_session_id)
        if sid is None:
            return StudyConversationContext(chat_session_id="")
        if not isinstance(ui_context, dict) or not ui_context:
            return self.get_context(sid)

        doc_id = str(ui_context.get("document_id") or "").strip() or None
        tab = str(ui_context.get("tab") or "").strip() or None
        chapter_id = str(ui_context.get("chapter_id") or "").strip() or None
        section_id = str(ui_context.get("section_id") or "").strip() or None
        session_id = str(ui_context.get("session_id") or "").strip() or None

        doc_title: Optional[str] = None
        if doc_id:
            doc = study_service.get_document(doc_id)
            if not doc:
                doc_id = None
            else:
                doc_title = getattr(doc, "title", None)

        if session_id and hasattr(study_service, "list_study_sessions"):
            known_sessions = {
                s.get("session_id"): s for s in study_service.list_study_sessions()
            }
            if session_id not in known_sessions:
                session_id = None
            elif doc_id and known_sessions[session_id].get("document_id") != doc_id:
                session_id = None

        return self.update_context(
            chat_session_id,
            document_id=doc_id,
            document_title=doc_title,
            chapter_id=chapter_id,
            section_id=section_id,
            activity=tab,
            study_session_id=session_id,
            preserve_missing=True,
        )

    def update_context(
        self,
        chat_session_id: Optional[str],
        *,
        document_id: Optional[str] = None,
        document_title: Optional[str] = None,
        collection_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
        section_id: Optional[str] = None,
        activity: Optional[str] = None,
        study_session_id: Optional[str] = None,
        last_assessment_id: Optional[str] = None,
        last_active_recall_prompt_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        question_count: Optional[int] = None,
        concepts: Optional[List[str]] = None,
        preserve_missing: bool = True,
    ) -> StudyConversationContext:
        sid = normalize_chat_session_id(chat_session_id)
        if sid is None:
            return StudyConversationContext(chat_session_id="")
        with self._lock:
            ctx = self._contexts.get(sid) or StudyConversationContext(chat_session_id=sid)

            # Isolamento estrito entre documentos: ao mudar de documento, limpar sub-referências antigas
            if document_id and document_id != ctx.active_document_id:
                ctx.active_document_id = document_id
                ctx.active_document_title = document_title or ctx.active_document_title
                ctx.active_chapter_id = None
                ctx.active_section_id = None
                ctx.active_study_session_id = None
                ctx.last_assessment_id = None
                ctx.last_active_recall_prompt_id = None
                ctx.last_topic = None
                ctx.recent_concepts = []
            elif document_id:
                ctx.active_document_id = document_id
                if document_title:
                    ctx.active_document_title = document_title

            if collection_id is not None or not preserve_missing:
                ctx.active_collection_id = collection_id
            if chapter_id is not None or not preserve_missing:
                ctx.active_chapter_id = chapter_id
            if section_id is not None or not preserve_missing:
                ctx.active_section_id = section_id
            if activity is not None or not preserve_missing:
                ctx.active_activity = activity
            if study_session_id is not None or not preserve_missing:
                ctx.active_study_session_id = study_session_id
            if last_assessment_id is not None or not preserve_missing:
                ctx.last_assessment_id = last_assessment_id
            if last_active_recall_prompt_id is not None or not preserve_missing:
                ctx.last_active_recall_prompt_id = last_active_recall_prompt_id
            if operation_id is not None:
                ctx.last_operation_id = operation_id
            if operation_type is not None:
                ctx.last_operation_type = operation_type
            if topic is not None:
                ctx.last_topic = topic
            if difficulty is not None:
                ctx.last_difficulty = difficulty
            if question_count is not None:
                ctx.last_question_count = question_count
            if concepts:
                merged = list(dict.fromkeys([c for c in [*concepts, *ctx.recent_concepts] if c]))
                ctx.recent_concepts = merged[:12]
            ctx.updated_at = _utc_now_iso()
            self._contexts[sid] = ctx
            self._save_contexts()
            return StudyConversationContext.from_dict(ctx.to_dict())

    def resolve_document(
        self,
        study_service: Any,
        *,
        chat_session_id: str,
        explicit_document_id: Optional[str] = None,
        document_query: Optional[str] = None,
        prompt: str = "",
        ui_context: Optional[Dict[str, Any]] = None,
    ) -> DocumentResolutionResult:
        docs = list(study_service.list_documents() or [])

        # 1. ID explícito fornecido
        if explicit_document_id:
            exact = study_service.get_document(explicit_document_id)
            if exact:
                return DocumentResolutionResult(status="RESOLVED", document=exact)
            return DocumentResolutionResult(
                status="NOT_FOUND",
                message=f"Documento '{explicit_document_id}' não encontrado na biblioteca de estudo.",
            )

        if not docs:
            return DocumentResolutionResult(
                status="NOT_FOUND",
                message="Não existem documentos carregados na Biblioteca de Estudo.",
            )

        norm_prompt = normalize_match_text(prompt)
        norm_query = normalize_match_text(document_query or "")
        docs_by_id = {d.document_id: d for d in docs}

        # 2. Match direto por document_id mencionado no texto ou query
        for doc in docs:
            did_low = doc.document_id.lower()
            if (norm_query and norm_query == did_low) or (did_low and did_low in norm_prompt):
                return DocumentResolutionResult(status="RESOLVED", document=doc)

        # 3. Match explícito por título / ficheiro / tema quando fornecido
        search_terms = [norm_query] if norm_query else []
        quoted_match = re.findall(r'["«]([^"»]{3,80})["»]', prompt or "")
        for qm in quoted_match:
            nq = normalize_match_text(qm)
            if nq and nq not in search_terms:
                search_terms.append(nq)

        about_match = re.search(
            r"(?:documento|artigo|paper|ficheiro|livro|pdf|aula)\s+(?:sobre|de|do|da|chamado|intitulado)?\s*[:«\"]?([a-z0-9\u00c0-\u017f _\.\-]{3,70})",
            norm_prompt,
        )
        if about_match:
            cand = about_match.group(1).strip()
            generic_words = {
                "este", "esta", "esse", "essa", "isto", "isso", "ele", "ela", "estudo",
                "atual", "corrente", "anterior", "novo", "acima", "disponiveis", "todos",
            }
            if cand and cand.split()[0] not in generic_words and cand not in search_terms:
                search_terms.append(cand)

        if search_terms:
            scored: List[Tuple[int, Any]] = []
            for doc in docs:
                title_norm = normalize_match_text(getattr(doc, "title", ""))
                subj_norm = normalize_match_text(getattr(doc, "subject", ""))
                fname_norm = normalize_match_text((getattr(doc, "metadata", {}) or {}).get("filename", ""))
                haystack = " | ".join(filter(None, [title_norm, fname_norm, subj_norm]))
                best_score = 0
                for term in search_terms:
                    if not term:
                        continue
                    if term == title_norm or term == fname_norm:
                        best_score = max(best_score, 100)
                    elif term in haystack:
                        best_score = max(best_score, 70)
                    else:
                        tokens = [t for t in re.findall(r"[a-z0-9]{3,}", term) if t not in {"sobre", "documento", "artigo", "paper", "estudo"}]
                        if tokens:
                            hits = sum(1 for t in tokens if t in haystack)
                            if hits > 0:
                                best_score = max(best_score, int((hits / len(tokens)) * 55))
                if best_score >= 30:
                    scored.append((best_score, doc))

            if scored:
                scored.sort(key=lambda item: item[0], reverse=True)
                top_score = scored[0][0]
                tied = [d for s, d in scored if s >= top_score - 10 and top_score < 95] if len(scored) > 1 else [scored[0][1]]
                if len(tied) == 1 or top_score >= 95:
                    return DocumentResolutionResult(status="RESOLVED", document=scored[0][1])
                cands = [
                    {
                        "document_id": d.document_id,
                        "title": getattr(d, "title", d.document_id),
                        "subject": getattr(d, "subject", "Geral"),
                    }
                    for d in tied[:5]
                ]
                return DocumentResolutionResult(
                    status="AMBIGUOUS",
                    candidates=cands,
                    message=(
                        "Encontrei mais do que um documento compatível com essa referência. "
                        "Qual destes pretende usar?\n"
                        + "\n".join(f"- **{c['title']}** (`{c['document_id']}`)" for c in cands)
                    ),
                )
            elif norm_query or search_terms:
                wanted = document_query or search_terms[0]
                return DocumentResolutionResult(
                    status="NOT_FOUND",
                    message=f"Não encontrei nenhum documento correspondente a '{wanted}' na Biblioteca de Estudo.",
                )

        # 4. Contexto ativo da UI (ex: utilizador está a ler um artigo no StudyContainer)
        if isinstance(ui_context, dict):
            ui_doc_id = str(ui_context.get("document_id") or "").strip()
            if ui_doc_id and ui_doc_id in docs_by_id:
                return DocumentResolutionResult(status="RESOLVED", document=docs_by_id[ui_doc_id])

        # 5. Contexto conversacional persistido para esta sessão JARVIS
        ctx = self.get_context(chat_session_id)
        if ctx.active_document_id and ctx.active_document_id in docs_by_id:
            return DocumentResolutionResult(status="RESOLVED", document=docs_by_id[ctx.active_document_id])

        # 6. Se só existir exatamente 1 documento na biblioteca, podemos resolver univocamente quando pedido sem ambiguidade
        if len(docs) == 1:
            return DocumentResolutionResult(status="RESOLVED", document=docs[0])

        cands = [
            {
                "document_id": d.document_id,
                "title": getattr(d, "title", d.document_id),
                "subject": getattr(d, "subject", "Geral"),
            }
            for d in docs[:6]
        ]
        return DocumentResolutionResult(
            status="AMBIGUOUS",
            candidates=cands,
            message=(
                "Existem vários documentos na Biblioteca de Estudo e nenhum está selecionado nesta conversa. "
                "Indica o nome ou ID do documento:\n"
                + "\n".join(f"- **{c['title']}** (`{c['document_id']}`)" for c in cands)
            ),
        )

    def resolve_chapter_or_section(
        self,
        study_service: Any,
        document_id: str,
        *,
        chapter_id: Optional[str] = None,
        chapter_ref: Optional[str] = None,
        section_id: Optional[str] = None,
        section_ref: Optional[str] = None,
        prompt: str = "",
        active_chapter_id: Optional[str] = None,
        active_section_id: Optional[str] = None,
    ) -> ChapterResolutionResult:
        """Resolve capítulo ou secção estritamente dentro do documento especificado."""
        plan = study_service.get_editorial_study_plan(document_id) if hasattr(study_service, "get_editorial_study_plan") else None
        ast_dict = study_service.get_document_ast(document_id) if hasattr(study_service, "get_document_ast") else None
        doc = study_service.get_document(document_id)

        chapters = list((plan or {}).get("chapters") or [])
        ast_sections = list((ast_dict or {}).get("sections") or []) or list(getattr(doc, "sections", []) or [])

        # 1. IDs explícitos
        if chapter_id:
            matched_ch = next((c for c in chapters if str(c.get("chapter_id")) == chapter_id), None)
            if not matched_ch:
                return ChapterResolutionResult(
                    status="NOT_FOUND",
                    message=f"Capítulo '{chapter_id}' não existe no documento '{document_id}'.",
                )
            src_sids = self._extract_chapter_source_sections(matched_ch)
            return ChapterResolutionResult(
                status="RESOLVED",
                chapter_id=matched_ch.get("chapter_id"),
                chapter_title=matched_ch.get("title"),
                source_section_ids=src_sids,
            )

        if section_id:
            matched_sec = next((s for s in ast_sections if str(s.get("section_id")) == section_id), None)
            if matched_sec:
                return ChapterResolutionResult(
                    status="RESOLVED",
                    section_id=str(matched_sec.get("section_id")),
                    section_title=str(matched_sec.get("title") or ""),
                    source_section_ids=[str(matched_sec.get("section_id"))],
                )
            return ChapterResolutionResult(
                status="NOT_FOUND",
                message=f"Secção '{section_id}' não existe no documento '{document_id}'.",
            )

        # 2. Detetar referência ordinal ou nominal de capítulo/secção
        norm_prompt = normalize_match_text(f"{chapter_ref or ''} {section_ref or ''} {prompt}")
        explicit_num: Optional[int] = None
        num_match = re.search(r"(?:capitulo|chapter|cap\.?)\s*(\d+)", norm_prompt)
        if num_match:
            explicit_num = int(num_match.group(1))
        else:
            for word, num in _ORDINAL_CHAPTER_WORDS.items():
                if re.search(rf"\b{re.escape(word)}\s+(?:capitulo|chapter|cap\.?)\b", norm_prompt) or re.search(
                    rf"\b(?:capitulo|chapter|cap\.?)\s+{re.escape(word)}\b", norm_prompt
                ):
                    explicit_num = num
                    break

        if explicit_num is not None:
            if chapters:
                if 1 <= explicit_num <= len(chapters):
                    matched_ch = chapters[explicit_num - 1]
                    return ChapterResolutionResult(
                        status="RESOLVED",
                        chapter_id=matched_ch.get("chapter_id"),
                        chapter_title=matched_ch.get("title"),
                        source_section_ids=self._extract_chapter_source_sections(matched_ch),
                    )
                return ChapterResolutionResult(
                    status="NOT_FOUND",
                    message=(
                        f"O documento '{getattr(doc, 'title', document_id)}' tem apenas {len(chapters)} capítulo(s); "
                        f"não existe o capítulo {explicit_num}."
                    ),
                )
            if ast_sections:
                if 1 <= explicit_num <= len(ast_sections):
                    sec = ast_sections[explicit_num - 1]
                    sid = str(sec.get("section_id") or "")
                    return ChapterResolutionResult(
                        status="RESOLVED",
                        section_id=sid,
                        section_title=str(sec.get("title") or ""),
                        source_section_ids=[sid] if sid else [],
                    )
                return ChapterResolutionResult(
                    status="NOT_FOUND",
                    message=(
                        f"O documento tem {len(ast_sections)} secção(ões); não existe a secção/capítulo {explicit_num}."
                    ),
                )

        # 3. Referência semântica por nome de capítulo ou secção ("metodologia", "resultados", etc.)
        ref_candidate = normalize_match_text(chapter_ref or section_ref or "")
        if not ref_candidate:
            ref_match = re.search(
                r"(?:sobre\s+a|sobre\s+o|sobre\s+os|sobre\s+as|da\s+seccao|do\s+capitulo|na\s+seccao|apenas\s+sobre\s+a?)\s+([a-z0-9 \-_]{3,50})",
                norm_prompt,
            )
            if ref_match:
                ref_candidate = ref_match.group(1).strip()
        if not ref_candidate:
            for kw in ("metodologia", "resultados", "conclusoes", "conclusao", "fundamentos", "introducao", "arquitetura"):
                if re.search(rf"\b{kw}\b", norm_prompt):
                    ref_candidate = kw
                    break

        if ref_candidate:
            for ch in chapters:
                ch_title = normalize_match_text(str(ch.get("title") or ""))
                if ref_candidate in ch_title or any(tok in ch_title for tok in ref_candidate.split() if len(tok) > 3):
                    return ChapterResolutionResult(
                        status="RESOLVED",
                        chapter_id=ch.get("chapter_id"),
                        chapter_title=ch.get("title"),
                        source_section_ids=self._extract_chapter_source_sections(ch),
                    )
            for sec in ast_sections:
                sec_title = normalize_match_text(str(sec.get("title") or ""))
                if ref_candidate in sec_title or any(tok in sec_title for tok in ref_candidate.split() if len(tok) > 3):
                    sid = str(sec.get("section_id") or "")
                    return ChapterResolutionResult(
                        status="RESOLVED",
                        section_id=sid,
                        section_title=str(sec.get("title") or ""),
                        source_section_ids=[sid] if sid else [],
                    )

        # 4. Continuidade anafórica ("este capítulo", "esta secção", "essa parte")
        if any(p in norm_prompt for p in ("este capitulo", "deste capitulo", "essa parte", "esta seccao", "nesta seccao")):
            if active_chapter_id:
                matched_ch = next((c for c in chapters if str(c.get("chapter_id")) == active_chapter_id), None)
                if matched_ch:
                    return ChapterResolutionResult(
                        status="RESOLVED",
                        chapter_id=matched_ch.get("chapter_id"),
                        chapter_title=matched_ch.get("title"),
                        source_section_ids=self._extract_chapter_source_sections(matched_ch),
                    )
            if active_section_id:
                matched_sec = next((s for s in ast_sections if str(s.get("section_id")) == active_section_id), None)
                if matched_sec:
                    sid = str(matched_sec.get("section_id") or "")
                    return ChapterResolutionResult(
                        status="RESOLVED",
                        section_id=sid,
                        section_title=str(matched_sec.get("title") or ""),
                        source_section_ids=[sid] if sid else [],
                    )

        return ChapterResolutionResult(status="NONE_REQUESTED")

    @staticmethod
    def _extract_chapter_source_sections(chapter: Dict[str, Any]) -> List[str]:
        sids: List[str] = [str(orig) for orig in (chapter.get("original_section_ids") or []) if orig]
        for sec in chapter.get("sections") or []:
            if isinstance(sec, dict):
                if sec.get("section_id"):
                    sids.append(str(sec["section_id"]))
                for orig in sec.get("original_section_ids") or []:
                    sids.append(str(orig))
        return list(dict.fromkeys(sids))
