"""
JARVIS OS — Study Engine Phase 6: Intelligent Flashcards Engine
Gera flashcards adaptativos por natureza do documento a partir de EditorialStudyPlan +
AcademicReasoningDossier + AST, preserva edições manuais e impede duplicados.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from services.study_modes.contracts import (
    AdaptiveFlashcard,
    ContentDifficulty,
    FlashcardReviewStatus,
    FlashcardType,
    QuestionDifficulty,
    StudyDeck,
)
from services.study_modes.grounding import (
    LLMCaller,
    Phase6GroundingHelper,
    compute_source_fingerprints,
    invoke_phase6_json_llm,
    map_depth_to_content_difficulty,
)
from services.study_modes.persistence import StudyModePersistence
from services.study_modes.qa_engine import StudyModeQA, jaccard_similarity


_NATURE_CARD_TYPES: Dict[str, List[str]] = {
    "EMPIRICAL_RESEARCH_ARTICLE": [
        FlashcardType.DEFINITION.value,
        FlashcardType.CONCEPTUAL_UNDERSTANDING.value,
        FlashcardType.RELATIONSHIP.value,
        FlashcardType.METHODOLOGY.value,
        FlashcardType.RESULTS_CONCLUSIONS.value,
        FlashcardType.ANALYTICAL.value,
    ],
    "THEORETICAL_CONCEPTUAL_PAPER": [
        FlashcardType.DEFINITION.value,
        FlashcardType.CONCEPTUAL_UNDERSTANDING.value,
        FlashcardType.RELATIONSHIP.value,
        FlashcardType.ANALYTICAL.value,
        FlashcardType.APPLICATION.value,
    ],
    "TECHNICAL_MANUAL_SPEC": [
        FlashcardType.DEFINITION.value,
        FlashcardType.CONCEPTUAL_UNDERSTANDING.value,
        FlashcardType.APPLICATION.value,
        FlashcardType.ANALYTICAL.value,
    ],
    "STUDY_MATERIAL_LECTURE": [
        FlashcardType.DEFINITION.value,
        FlashcardType.CONCEPTUAL_UNDERSTANDING.value,
        FlashcardType.RELATIONSHIP.value,
        FlashcardType.APPLICATION.value,
    ],
}


class FlashcardEngine:
    """Motor de geração, validação, edição e gestão de baralhos inteligentes."""

    DECK_FILE = "flashcards_deck.json"

    def __init__(self, persistence: StudyModePersistence) -> None:
        self.persistence = persistence

    def load_deck(self, document_id: str) -> Optional[StudyDeck]:
        raw = self.persistence.load_json_doc_artifact(document_id, self.DECK_FILE, None)
        if isinstance(raw, dict) and raw.get("document_id"):
            return StudyDeck.from_dict(raw)
        return None

    def save_deck(self, deck: StudyDeck) -> StudyDeck:
        deck.updated_at = datetime.now().isoformat()
        self.persistence.save_json_doc_artifact(deck.document_id, self.DECK_FILE, deck.to_dict())
        return deck

    def _allowed_types_for_document(self, grounding: Phase6GroundingHelper) -> List[str]:
        nature = str(getattr(grounding.plan.overview, "document_nature", "") or "")
        base = list(_NATURE_CARD_TYPES.get(nature, [
            FlashcardType.DEFINITION.value,
            FlashcardType.CONCEPTUAL_UNDERSTANDING.value,
            FlashcardType.RELATIONSHIP.value,
            FlashcardType.ANALYTICAL.value,
        ]))
        meth = getattr(grounding.dossier, "methodology_analysis", None)
        if not (meth and getattr(meth, "is_applicable", False) and (meth.methods_used or meth.methodological_design)):
            base = [t for t in base if t != FlashcardType.METHODOLOGY.value]
        if not (getattr(grounding.dossier, "results_and_evidence", None) or []):
            base = [t for t in base if t != FlashcardType.RESULTS_CONCLUSIONS.value]
        if not (getattr(grounding.plan, "conceptual_relationships", None) or []):
            base = [t for t in base if t != FlashcardType.RELATIONSHIP.value]
        return base or [FlashcardType.DEFINITION.value, FlashcardType.CONCEPTUAL_UNDERSTANDING.value]

    def generate_deck(
        self,
        grounding: Phase6GroundingHelper,
        *,
        force_regenerate: bool = False,
        target_cards: int = 16,
        llm_caller: Optional[LLMCaller] = None,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
    ) -> StudyDeck:
        doc_id = grounding.plan.metadata.document_id or grounding.dossier.document_id
        current_fp = compute_source_fingerprints(grounding.plan, grounding.dossier, grounding.ast)
        existing = self.load_deck(doc_id)

        if (
            not force_regenerate
            and existing is not None
            and existing.fingerprints is not None
            and existing.fingerprints.plan_fingerprint == current_fp.plan_fingerprint
            and existing.fingerprints.dossier_fingerprint == current_fp.dossier_fingerprint
            and existing.fingerprints.ast_fingerprint == current_fp.ast_fingerprint
            and existing.cards
        ):
            return existing

        # Preservar cartões editados pelo utilizador e tombstones de apagamento
        preserved_edited: List[AdaptiveFlashcard] = []
        deleted_fronts: List[str] = []
        if existing is not None:
            for c in existing.cards:
                if c.is_deleted:
                    deleted_fronts.append(c.front)
                    preserved_edited.append(c)
                elif c.user_edited or c.generation_mode == "USER_CREATED":
                    preserved_edited.append(c)

        allowed_types = self._allowed_types_for_document(grounding)
        generated_cards: List[AdaptiveFlashcard] = []
        failed_ops: List[Dict[str, Any]] = []
        llm_used_any = False
        chapters = list(grounding.plan.chapters or [])
        per_chap_quota = max(3, min(8, (max(6, target_cards) + max(1, len(chapters)) - 1) // max(1, len(chapters))))

        for idx, chapter in enumerate(chapters):
            if on_progress:
                on_progress(
                    "FLASHCARDS",
                    0.15 + 0.65 * ((idx + 1) / max(1, len(chapters))),
                    f"A gerar flashcards fundamentados para o Capítulo {idx + 1}/{len(chapters)}: {chapter.title}",
                )

            payload = grounding.build_chapter_prompt_payload(chapter)
            system_prompt = (
                "És um especialista em pedagogia universitária. Gera flashcards académicos em Português Europeu "
                "estritamente baseados nos artefactos fornecidos.\n"
                f"Tipos de cartão permitidos para este documento: {allowed_types}.\n"
                "Regras obrigatórias:\n"
                "1. Nunca inventes factos, números, paragraph_id, section_id ou páginas.\n"
                "2. Não cries perguntas triviais nem respostas que repitam a pergunta.\n"
                "3. Para cartões APPLICATION com cenários hipotéticos, define is_hypothetical_scenario=true e epistemic_status='MODEL_INFERENCE'.\n"
                "4. Usa epistemic_status='SOURCE_FACT' apenas quando a resposta reproduz fielmente factos com evidence_refs exatos; "
                "usa 'MODEL_INFERENCE' para explicações, sínteses e aplicações.\n"
                "5. Devolve APENAS JSON com chave 'cards': [{\"front\", \"back\", \"card_type\", \"question_difficulty\", "
                "\"section_id\", \"topic\", \"concept_ids\", \"evidence_refs\", \"epistemic_status\", \"is_hypothetical_scenario\"}]."
            )
            user_prompt = (
                f"Gera até {per_chap_quota} flashcards de elevada qualidade pedagógica para este capítulo:\n"
                f"{payload}"
            )

            def _validate(obj: Dict[str, Any]) -> Tuple[bool, str]:
                cards_raw = obj.get("cards")
                if not isinstance(cards_raw, list) or not cards_raw:
                    return False, "Campo 'cards' deve ser uma lista JSON não vazia."
                for i, c in enumerate(cards_raw):
                    if not isinstance(c, dict) or not str(c.get("front", "")).strip() or not str(c.get("back", "")).strip():
                        return False, f"Cartão na posição {i} sem front/back."
                return True, "OK"

            parsed, llm_meta = invoke_phase6_json_llm(
                llm_caller=llm_caller,
                operation=f"phase6_flashcards_{chapter.chapter_id}",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                document_id=doc_id,
                validator=_validate,
            )

            chap_cards: List[AdaptiveFlashcard] = []
            if parsed and isinstance(parsed.get("cards"), list):
                llm_used_any = True
                chap_cards = self._parse_llm_cards(
                    parsed["cards"],
                    grounding=grounding,
                    chapter=chapter,
                    allowed_types=allowed_types,
                    gen_meta=llm_meta,
                )
            else:
                failed_ops.append({
                    "operation": f"phase6_flashcards_{chapter.chapter_id}",
                    "error": llm_meta.get("error", "LLM indisponível ou inválido; aplicado gerador determinístico."),
                    "fallback": "DETERMINISTIC_GROUNDED",
                    "timestamp": datetime.now().isoformat(),
                })
                chap_cards = self._build_deterministic_cards_for_chapter(
                    grounding=grounding,
                    chapter=chapter,
                    allowed_types=allowed_types,
                    limit=per_chap_quota,
                )
            generated_cards.extend(chap_cards)

        # Garantir deduplicação e filtragem de cartões previamente removidos ou substituídos por edições do utilizador
        qa = StudyModeQA(grounding=grounding)
        validated_new, _ = qa.validate_flashcards(generated_cards)

        active_user_fronts = [c.front for c in preserved_edited if not c.is_deleted]
        merged: List[AdaptiveFlashcard] = list(preserved_edited)
        for card in validated_new:
            if any(jaccard_similarity(card.front, df) >= 0.85 for df in deleted_fronts):
                continue
            if any(jaccard_similarity(card.front, uf) >= 0.82 for uf in active_user_fronts):
                continue
            merged.append(card)

        deck = StudyDeck(
            deck_id=existing.deck_id if existing else f"deck_{hashlib.sha1(doc_id.encode('utf-8')).hexdigest()[:10]}",
            document_id=doc_id,
            title=getattr(grounding.dossier.document_analysis, "title", "") or doc_id,
            document_nature=str(getattr(grounding.plan.overview, "document_nature", "") or ""),
            cards=merged[: max(target_cards + len(preserved_edited), len(preserved_edited) + 4)],
            fingerprints=current_fp,
            generation_mode="LLM_GROUNDED" if llm_used_any and not failed_ops else ("PARTIAL_FALLBACK" if llm_used_any else "DETERMINISTIC_GROUNDED"),
            status="COMPLETED" if merged else "PARTIAL",
            failed_operations=failed_ops,
        )
        return self.save_deck(deck)

    def _parse_llm_cards(
        self,
        raw_cards: Sequence[Dict[str, Any]],
        *,
        grounding: Phase6GroundingHelper,
        chapter: Any,
        allowed_types: Sequence[str],
        gen_meta: Dict[str, Any],
    ) -> List[AdaptiveFlashcard]:
        doc_id = grounding.plan.metadata.document_id or grounding.dossier.document_id
        secs_by_id = {s.section_id: s for s in (chapter.sections or [])}
        default_sec = chapter.sections[0] if chapter.sections else None
        out: List[AdaptiveFlashcard] = []

        for idx, raw in enumerate(raw_cards):
            front = str(raw.get("front") or "").strip()
            back = str(raw.get("back") or "").strip()
            ctype = str(raw.get("card_type") or FlashcardType.CONCEPTUAL_UNDERSTANDING.value).upper()
            if ctype not in allowed_types:
                ctype = allowed_types[0]

            sec_id = str(raw.get("section_id") or "").strip()
            sec = secs_by_id.get(sec_id, default_sec)
            sec_title = sec.title if sec else ""
            orig_sids = list(getattr(sec, "original_section_ids", []) or []) if sec else []
            obj_id, obj_txt = grounding.pick_objective_for_section(chapter, sec) if sec else ("", chapter.pedagogical_objective)

            cids = [
                str(c).strip()
                for c in (raw.get("concept_ids") or [])
                if str(c).strip() in grounding.concepts_by_id
            ]
            if not cids and sec:
                cids = [c for c in (sec.associated_concept_ids or []) if c in grounding.concepts_by_id][:3]

            is_hyp = bool(raw.get("is_hypothetical_scenario", False)) or (ctype == FlashcardType.APPLICATION.value)
            req_ep = str(raw.get("epistemic_status") or ("MODEL_INFERENCE" if ctype != FlashcardType.DEFINITION.value else "SOURCE_FACT"))

            valid_refs, pages, ep_status, rej = grounding.validate_and_ground_refs(
                raw.get("evidence_refs"),
                allowed_section_ids=orig_sids,
                candidate_text=f"{front} {back}",
                requested_status=req_ep,
                is_hypothetical=is_hyp,
            )
            if is_hyp and "cenário hipotético" not in back.lower():
                back = f"[Cenário hipotético de aplicação] {back}"

            qdiff = str(raw.get("question_difficulty") or QuestionDifficulty.MEDIUM.value).upper()
            if qdiff not in ("EASY", "MEDIUM", "HARD"):
                qdiff = QuestionDifficulty.MEDIUM.value
            depth = (
                sec.pedagogical_treatments[0].depth_level
                if sec and getattr(sec, "pedagogical_treatments", None)
                else "IN_DEPTH"
            )
            cdiff = map_depth_to_content_difficulty(depth, sec.content_role if sec else "")

            cid_hash = hashlib.sha1(f"{doc_id}:{chapter.chapter_id}:{front.lower()}".encode("utf-8")).hexdigest()[:10]
            out.append(
                AdaptiveFlashcard(
                    card_id=f"fc_{cid_hash}",
                    document_id=doc_id,
                    front=front,
                    back=back,
                    card_type=ctype,
                    content_difficulty=cdiff,
                    question_difficulty=qdiff,
                    chapter_id=chapter.chapter_id,
                    chapter_title=chapter.title,
                    section_id=sec.section_id if sec else "",
                    section_title=sec_title,
                    topic=str(raw.get("topic") or sec_title or chapter.title),
                    learning_objective_id=obj_id,
                    learning_objective_text=obj_txt,
                    concept_ids=cids,
                    evidence_refs=valid_refs,
                    source_pages=pages,
                    epistemic_status=ep_status,
                    is_hypothetical_scenario=is_hyp,
                    generation_mode="LLM_GROUNDED",
                    generation_metadata={"model": "qwen3.5:9b", "attempts": gen_meta.get("attempts", 1), "rejected_refs": rej},
                )
            )
        return out

    def _build_deterministic_cards_for_chapter(
        self,
        *,
        grounding: Phase6GroundingHelper,
        chapter: Any,
        allowed_types: Sequence[str],
        limit: int,
    ) -> List[AdaptiveFlashcard]:
        doc_id = grounding.plan.metadata.document_id or grounding.dossier.document_id
        cards: List[AdaptiveFlashcard] = []
        default_sec = chapter.sections[0] if chapter.sections else None

        # 1. Cartões de definição & compreensão conceptual baseados nos conceitos do capítulo
        chap_cids = list(dict.fromkeys(list(getattr(chapter, "key_concept_ids", []) or []) + [
            cid for s in (chapter.sections or []) for cid in (s.associated_concept_ids or [])
        ]))
        for cid in chap_cids:
            if len(cards) >= limit:
                break
            c = grounding.concepts_by_id.get(cid)
            if not c or not (c.definition or c.explanation):
                continue
            target_sec = next(
                (s for s in (chapter.sections or []) if cid in (s.associated_concept_ids or [])),
                default_sec,
            )
            orig_sids = list(getattr(target_sec, "original_section_ids", []) or []) if target_sec else []
            obj_id, obj_txt = grounding.pick_objective_for_section(chapter, target_sec) if target_sec else ("", chapter.pedagogical_objective)
            ans_text = c.definition.strip() or c.explanation.strip()
            refs, pages, ep_st, _ = grounding.validate_and_ground_refs(
                [r.to_dict() if hasattr(r, "to_dict") else {"section_id": r.section_id, "paragraph_id": r.paragraph_id, "page_number": r.page_number, "status": r.status} for r in (c.evidence_refs or [])],
                allowed_section_ids=orig_sids,
                candidate_text=ans_text,
                requested_status="SOURCE_FACT" if c.definition else "MODEL_INFERENCE",
            )
            front = f"Como se define e contextualiza o conceito «{c.name}» neste estudo?"
            back = ans_text + (f"\nContexto: {c.explanation.strip()}" if c.definition and c.explanation and c.explanation.strip() != c.definition.strip() else "")
            cards.append(
                AdaptiveFlashcard(
                    card_id=f"fc_{hashlib.sha1(f'{doc_id}:{cid}:{front}'.encode('utf-8')).hexdigest()[:10]}",
                    document_id=doc_id,
                    front=front,
                    back=back.strip(),
                    card_type=FlashcardType.DEFINITION.value if FlashcardType.DEFINITION.value in allowed_types else allowed_types[0],
                    content_difficulty=ContentDifficulty.FOUNDATIONAL.value,
                    question_difficulty=QuestionDifficulty.EASY.value,
                    chapter_id=chapter.chapter_id,
                    chapter_title=chapter.title,
                    section_id=target_sec.section_id if target_sec else "",
                    section_title=target_sec.title if target_sec else "",
                    topic=c.name,
                    learning_objective_id=obj_id,
                    learning_objective_text=obj_txt,
                    concept_ids=[cid],
                    evidence_refs=refs,
                    source_pages=pages,
                    epistemic_status=ep_st,
                    generation_mode="DETERMINISTIC_GROUNDED",
                    generation_metadata={"source": "dossier.conceptual_analysis"},
                )
            )

        # 2. Cartões de relação entre conceitos
        if FlashcardType.RELATIONSHIP.value in allowed_types and len(cards) < limit:
            chap_set = set(chap_cids)
            for rel in getattr(grounding.plan, "conceptual_relationships", []) or []:
                if len(cards) >= limit:
                    break
                if rel.source_concept_id not in chap_set and rel.target_concept_id not in chap_set:
                    continue
                if not rel.justification:
                    continue
                refs, pages, ep_st, _ = grounding.validate_and_ground_refs(
                    [r.__dict__ for r in (rel.evidence_refs or [])],
                    allowed_section_ids=getattr(default_sec, "original_section_ids", None) if default_sec else None,
                    candidate_text=rel.justification,
                    requested_status="MODEL_INFERENCE",
                )
                front = f"Qual é a relação ({rel.relation_type}) entre «{rel.source_concept_name}» e «{rel.target_concept_name}»?"
                cards.append(
                    AdaptiveFlashcard(
                        card_id=f"fc_{hashlib.sha1(f'{doc_id}:rel:{rel.relationship_id}'.encode('utf-8')).hexdigest()[:10]}",
                        document_id=doc_id,
                        front=front,
                        back=rel.justification.strip(),
                        card_type=FlashcardType.RELATIONSHIP.value,
                        content_difficulty=ContentDifficulty.INTERMEDIATE.value,
                        question_difficulty=QuestionDifficulty.MEDIUM.value,
                        chapter_id=chapter.chapter_id,
                        chapter_title=chapter.title,
                        section_id=default_sec.section_id if default_sec else "",
                        section_title=default_sec.title if default_sec else "",
                        topic=f"{rel.source_concept_name} ↔ {rel.target_concept_name}",
                        concept_ids=[rel.source_concept_id, rel.target_concept_id],
                        evidence_refs=refs,
                        source_pages=pages,
                        epistemic_status=ep_st,
                        generation_mode="DETERMINISTIC_GROUNDED",
                    )
                )

        # 3. Cartão de metodologia (quando aplicável e no primeiro capítulo metodológico)
        meth = getattr(grounding.dossier, "methodology_analysis", None)
        if (
            FlashcardType.METHODOLOGY.value in allowed_types
            and meth
            and getattr(meth, "is_applicable", False)
            and (meth.methodological_design or meth.methods_used)
            and len(cards) < limit
        ):
            refs, pages, ep_st, _ = grounding.validate_and_ground_refs(
                [r.__dict__ for r in (meth.evidence_refs or [])],
                allowed_section_ids=getattr(default_sec, "original_section_ids", None) if default_sec else None,
                candidate_text=f"{meth.methodological_design} {' '.join(meth.methods_used)}",
                requested_status="SOURCE_FACT",
            )
            back_parts = []
            if meth.methodological_design:
                back_parts.append(f"Desenho: {meth.methodological_design}")
            if meth.methods_used:
                back_parts.append(f"Métodos: {', '.join(meth.methods_used[:5])}")
            if meth.sample_or_participants:
                back_parts.append(f"Amostra: {meth.sample_or_participants}")
            front = f"Qual o desenho metodológico e os principais procedimentos utilizados em «{grounding.dossier.document_title}»?"
            cards.append(
                AdaptiveFlashcard(
                    card_id=f"fc_{hashlib.sha1(f'{doc_id}:meth:{chapter.chapter_id}'.encode('utf-8')).hexdigest()[:10]}",
                    document_id=doc_id,
                    front=front,
                    back="\n".join(back_parts),
                    card_type=FlashcardType.METHODOLOGY.value,
                    content_difficulty=ContentDifficulty.ADVANCED.value,
                    question_difficulty=QuestionDifficulty.HARD.value,
                    chapter_id=chapter.chapter_id,
                    chapter_title=chapter.title,
                    section_id=default_sec.section_id if default_sec else "",
                    section_title=default_sec.title if default_sec else "",
                    topic="Metodologia",
                    evidence_refs=refs,
                    source_pages=pages,
                    epistemic_status=ep_st,
                    generation_mode="DETERMINISTIC_GROUNDED",
                )
            )

        # 4. Cartões de resultados / conclusões
        if FlashcardType.RESULTS_CONCLUSIONS.value in allowed_types and len(cards) < limit:
            for r_idx, res in enumerate((grounding.dossier.results_and_evidence or [])[:2]):
                if len(cards) >= limit or not str(res.statement or "").strip():
                    break
                refs, pages, ep_st, _ = grounding.validate_and_ground_refs(
                    [er.__dict__ for er in (res.evidence_refs or [])],
                    allowed_section_ids=getattr(default_sec, "original_section_ids", None) if default_sec else None,
                    candidate_text=res.statement,
                    requested_status="SOURCE_FACT",
                )
                front = f"Qual a principal evidência/resultado reportado em relação a: «{res.relation_to_objectives or chapter.title}»?"
                back = res.statement + (f" (Dados: {res.evidence_data})" if res.evidence_data else "")
                cards.append(
                    AdaptiveFlashcard(
                        card_id=f"fc_{hashlib.sha1(f'{doc_id}:res:{chapter.chapter_id}:{r_idx}'.encode('utf-8')).hexdigest()[:10]}",
                        document_id=doc_id,
                        front=front,
                        back=back,
                        card_type=FlashcardType.RESULTS_CONCLUSIONS.value,
                        content_difficulty=ContentDifficulty.INTERMEDIATE.value,
                        question_difficulty=QuestionDifficulty.MEDIUM.value,
                        chapter_id=chapter.chapter_id,
                        chapter_title=chapter.title,
                        section_id=default_sec.section_id if default_sec else "",
                        section_title=default_sec.title if default_sec else "",
                        topic="Resultados e Conclusões",
                        evidence_refs=refs,
                        source_pages=pages,
                        epistemic_status=ep_st,
                        generation_mode="DETERMINISTIC_GROUNDED",
                    )
                )

        return cards

    # ------------------------------------------------------------------
    # Edição, Eliminação, Regeneração Individual e Filtragem
    # ------------------------------------------------------------------

    def edit_flashcard(
        self,
        document_id: str,
        card_id: str,
        *,
        front: Optional[str] = None,
        back: Optional[str] = None,
        topic: Optional[str] = None,
        question_difficulty: Optional[str] = None,
    ) -> AdaptiveFlashcard:
        deck = self.load_deck(document_id)
        if not deck:
            raise ValueError(f"Baralho não encontrado para '{document_id}'.")
        for c in deck.cards:
            if c.card_id == card_id and not c.is_deleted:
                if front is not None and front.strip():
                    c.front = front.strip()
                if back is not None and back.strip():
                    c.back = back.strip()
                if topic is not None and topic.strip():
                    c.topic = topic.strip()
                if question_difficulty in ("EASY", "MEDIUM", "HARD"):
                    c.question_difficulty = question_difficulty
                c.user_edited = True
                c.edited_at = datetime.now().isoformat()
                c.review_status = FlashcardReviewStatus.EDITED.value
                self.save_deck(deck)
                return c
        raise ValueError(f"Flashcard '{card_id}' não encontrado.")

    def delete_flashcard(self, document_id: str, card_id: str) -> bool:
        deck = self.load_deck(document_id)
        if not deck:
            return False
        for c in deck.cards:
            if c.card_id == card_id:
                c.is_deleted = True
                c.edited_at = datetime.now().isoformat()
                self.save_deck(deck)
                return True
        return False

    def create_custom_flashcard(
        self,
        document_id: str,
        *,
        front: str,
        back: str,
        chapter_id: str = "",
        section_id: str = "",
        topic: str = "",
        question_difficulty: str = QuestionDifficulty.MEDIUM.value,
        card_type: str = FlashcardType.CONCEPTUAL_UNDERSTANDING.value,
    ) -> AdaptiveFlashcard:
        deck = self.load_deck(document_id) or StudyDeck(
            deck_id=f"deck_{hashlib.sha1(document_id.encode('utf-8')).hexdigest()[:10]}",
            document_id=document_id,
            title=document_id,
        )
        card = AdaptiveFlashcard(
            card_id=f"fc_{uuid.uuid4().hex[:10]}",
            document_id=document_id,
            front=front.strip(),
            back=back.strip(),
            card_type=card_type,
            question_difficulty=question_difficulty if question_difficulty in ("EASY", "MEDIUM", "HARD") else "MEDIUM",
            chapter_id=chapter_id,
            section_id=section_id,
            topic=topic or "Nota Pessoal",
            epistemic_status="MODEL_INFERENCE",
            generation_mode="USER_CREATED",
            user_edited=True,
            edited_at=datetime.now().isoformat(),
            review_status=FlashcardReviewStatus.EDITED.value,
        )
        deck.cards.append(card)
        self.save_deck(deck)
        return card

    def regenerate_single_card(
        self,
        grounding: Phase6GroundingHelper,
        card_id: str,
        *,
        allow_overwrite_edited: bool = False,
        llm_caller: Optional[LLMCaller] = None,
    ) -> AdaptiveFlashcard:
        doc_id = grounding.plan.metadata.document_id or grounding.dossier.document_id
        deck = self.load_deck(doc_id)
        if not deck:
            raise ValueError(f"Baralho não encontrado para '{doc_id}'.")

        target_idx = next((i for i, c in enumerate(deck.cards) if c.card_id == card_id and not c.is_deleted), -1)
        if target_idx < 0:
            raise ValueError(f"Flashcard '{card_id}' não encontrado.")

        old_card = deck.cards[target_idx]
        if old_card.user_edited and not allow_overwrite_edited:
            raise ValueError("Este cartão foi editado manualmente; a regeneração individual requer confirmação explícita.")

        chapter = next(
            (ch for ch in grounding.plan.chapters if ch.chapter_id == old_card.chapter_id),
            grounding.plan.chapters[0],
        )
        payload = grounding.build_chapter_prompt_payload(chapter, max_chars=7000)

        parsed, meta = invoke_phase6_json_llm(
            llm_caller=llm_caller,
            operation=f"phase6_regen_card_{card_id}",
            system_prompt=(
                "Reformula este flashcard académico melhorando a clareza pedagógica, preservando o tópico "
                "e mantendo fidelidade estrita à fonte. Devolve apenas JSON {\"front\", \"back\", \"evidence_refs\", \"epistemic_status\"}."
            ),
            user_prompt=(
                f"Cartão atual: {old_card.front} -> {old_card.back}\n"
                f"Contexto documental: {payload}"
            ),
            document_id=doc_id,
            validator=lambda o: (bool(str(o.get("front", "")).strip() and str(o.get("back", "")).strip()), "front/back obrigatórios."),
            max_retries=1,
        )
        if parsed:
            new_front = str(parsed.get("front") or old_card.front).strip()
            new_back = str(parsed.get("back") or old_card.back).strip()
            valid_refs, pages, ep_st, _ = grounding.validate_and_ground_refs(
                parsed.get("evidence_refs") or [r.__dict__ for r in old_card.evidence_refs],
                candidate_text=f"{new_front} {new_back}",
                requested_status=str(parsed.get("epistemic_status") or old_card.epistemic_status),
                is_hypothetical=old_card.is_hypothetical_scenario,
            )
            old_card.front = new_front
            old_card.back = new_back
            old_card.evidence_refs = valid_refs or old_card.evidence_refs
            old_card.source_pages = pages or old_card.source_pages
            old_card.epistemic_status = ep_st
            old_card.generation_mode = "LLM_GROUNDED"
            old_card.generation_metadata = {"regenerated_at": datetime.now().isoformat(), "attempts": meta.get("attempts", 1)}
            old_card.user_edited = False
            self.save_deck(deck)
            return old_card

        raise RuntimeError(meta.get("error", "Falha ao regenerar o cartão com o modelo local."))

    @staticmethod
    def filter_cards(
        deck: StudyDeck,
        *,
        chapter_id: Optional[str] = None,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        card_type: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[AdaptiveFlashcard]:
        out: List[AdaptiveFlashcard] = []
        t_low = topic.strip().lower() if topic else ""
        for c in deck.cards:
            if not include_deleted and c.is_deleted:
                continue
            if chapter_id and c.chapter_id != chapter_id:
                continue
            if difficulty and difficulty.upper() != "ALL" and c.question_difficulty.upper() != difficulty.upper():
                continue
            if card_type and card_type.upper() != "ALL" and c.card_type.upper() != card_type.upper():
                continue
            if t_low and t_low not in (c.topic or "").lower() and t_low not in (c.section_title or "").lower():
                continue
            out.append(c)
        return out

