"""
JARVIS OS — Study Engine Phase 6: Study Mode Orchestrator
Orquestra artefactos das Fases 2–5, valida prontidão e obsolescência,
coordena Flashcards, Cornell Notes, Assessments, Active Recall, SM-2,
Progresso/Lacunas e Sessões persistentes com rastreabilidade epistémica estrita.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from services.academic_reasoning_engine import AcademicReasoningDossier
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import EditorialStudyPlan
from services.study_modes.active_recall_engine import ActiveRecallEngine
from services.study_modes.assessment_engine import AssessmentEngine
from services.study_modes.contracts import (
    ActiveRecallAttempt,
    ActiveRecallDeck,
    ActiveRecallPrompt,
    AdaptiveFlashcard,
    AssessmentAttempt,
    AssessmentConfig,
    AssessmentQuestion,
    CornellNoteEntry,
    CornellPersonalNote,
    CornellStudyDocument,
    DailyReviewQueue,
    FlashcardReviewStatus,
    LearningProgressSnapshot,
    QuestionAttemptOutcome,
    ReviewHistoryEntry,
    ReviewLearningState,
    ReviewSchedulingState,
    SourceFingerprintSnapshot,
    StudyAssessment,
    StudyDeck,
    StudyModeReadiness,
    StudyModeReadinessStatus,
    StudySessionState,
)
from services.study_modes.cornell_notes_engine import CornellNotesEngine
from services.study_modes.flashcards_engine import FlashcardEngine
from services.study_modes.grounding import (
    LLMCaller,
    Phase6GroundingHelper,
    compute_source_fingerprints,
)
from services.study_modes.learning_progress_engine import LearningProgressEngine
from services.study_modes.persistence import StudyModePersistence
from services.study_modes.session_manager import StudySessionManager
from services.study_modes.spaced_repetition_engine import SpacedRepetitionEngine


class StudyModeOrchestrator:
    """Serviço central da Fase 6 que consome artefactos reais das Fases 2–5 sem duplicá-las."""

    META_FILE = "study_modes_meta.json"

    def __init__(
        self,
        storage_dir: Path | str = Path("data/study"),
        *,
        llm_caller: Optional[LLMCaller] = None,
    ) -> None:
        self.storage_dir = Path(storage_dir)
        self.persistence = StudyModePersistence(self.storage_dir)
        self.llm_caller = llm_caller
        self.flashcards = FlashcardEngine(self.persistence)
        self.cornell = CornellNotesEngine(self.persistence)
        self.assessments = AssessmentEngine(self.persistence)
        self.active_recall = ActiveRecallEngine(self.persistence)
        self.srs = SpacedRepetitionEngine(self.persistence)
        self.progress = LearningProgressEngine(self.persistence)
        self.sessions = StudySessionManager(self.persistence)

    # ------------------------------------------------------------------
    # Carregamento e Verificação de Prontidão (Fases 2–5)
    # ------------------------------------------------------------------

    def _resolve_upstream(
        self,
        document_id: str,
        *,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        ast: Optional[AcademicDocumentAST] = None,
    ) -> Tuple[Optional[EditorialStudyPlan], Optional[AcademicReasoningDossier], Optional[AcademicDocumentAST], Dict[str, Any]]:
        raw = self.persistence.load_upstream_artifacts(document_id)
        resolved_ast = ast
        if resolved_ast is None and isinstance(raw.get("ast_data"), dict):
            try:
                resolved_ast = AcademicDocumentAST.from_dict(raw["ast_data"])
            except Exception:
                resolved_ast = None

        resolved_dossier = dossier
        if resolved_dossier is None and isinstance(raw.get("dossier_data"), dict):
            try:
                resolved_dossier = AcademicReasoningDossier.from_dict(raw["dossier_data"])
            except Exception:
                resolved_dossier = None

        resolved_plan = plan
        if resolved_plan is None and isinstance(raw.get("plan_data"), dict):
            try:
                resolved_plan = EditorialStudyPlan.from_dict(raw["plan_data"])
            except Exception:
                resolved_plan = None

        return resolved_plan, resolved_dossier, resolved_ast, raw

    def check_readiness(
        self,
        document_id: str,
        *,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        ast: Optional[AcademicDocumentAST] = None,
    ) -> StudyModeReadiness:
        doc_dir = self.persistence.document_dir(document_id)
        r_plan, r_dossier, r_ast, raw = self._resolve_upstream(
            document_id, plan=plan, dossier=dossier, ast=ast
        )
        has_ast = r_ast is not None
        has_dossier = r_dossier is not None
        has_plan = r_plan is not None
        has_docgen = isinstance(raw.get("docgen_result_data"), dict)

        if not doc_dir.exists() and not (has_ast or has_dossier or has_plan):
            return StudyModeReadiness(
                document_id=document_id,
                status=StudyModeReadinessStatus.MISSING_DOCUMENT.value,
                is_ready=False,
                missing_artifacts=["ast.json", "reasoning_dossier.json", "editorial_study_plan.json"],
                actionable_message=f"Documento '{document_id}' sem artefactos extraídos. Execute as Fases 2–4 primeiro.",
            )

        missing: List[str] = []
        if not has_dossier:
            missing.append("reasoning_dossier.json (Fase 3)")
        if not has_plan:
            missing.append("editorial_study_plan.json (Fase 4)")
        if not has_ast:
            missing.append("ast.json (Fase 2 - recomendado)")

        if not has_dossier:
            return StudyModeReadiness(
                document_id=document_id,
                status=StudyModeReadinessStatus.MISSING_DOSSIER.value,
                is_ready=False,
                has_ast=has_ast,
                has_dossier=False,
                has_plan=has_plan,
                has_study_document=has_docgen,
                missing_artifacts=missing,
                actionable_message="Falta o Dossier de Raciocínio Académico (Fase 3). Gere a análise antes de iniciar modos de estudo.",
            )

        if not has_plan:
            return StudyModeReadiness(
                document_id=document_id,
                status=StudyModeReadinessStatus.MISSING_PLAN.value,
                is_ready=False,
                has_ast=has_ast,
                has_dossier=True,
                has_plan=False,
                has_study_document=has_docgen,
                missing_artifacts=missing,
                actionable_message="Falta o Plano Editorial Pedagógico (Fase 4). Gere o plano antes de iniciar modos de estudo.",
            )

        assert r_plan is not None and r_dossier is not None
        if not r_plan.chapters:
            return StudyModeReadiness(
                document_id=document_id,
                status=StudyModeReadinessStatus.INVALID_UPSTREAM_ARTIFACT.value,
                is_ready=False,
                has_ast=has_ast,
                has_dossier=True,
                has_plan=True,
                has_study_document=has_docgen,
                actionable_message="O Plano Editorial (Fase 4) não possui capítulos estruturados.",
            )

        current_fp = compute_source_fingerprints(r_plan, r_dossier, r_ast)
        stale_reasons = self._detect_staleness(document_id, current_fp)
        status = (
            StudyModeReadinessStatus.STALE_SOURCE_ARTIFACTS.value
            if stale_reasons
            else StudyModeReadinessStatus.READY.value
        )
        return StudyModeReadiness(
            document_id=document_id,
            status=status,
            is_ready=True,
            has_ast=has_ast,
            has_dossier=True,
            has_plan=True,
            has_study_document=has_docgen,
            is_stale=bool(stale_reasons),
            stale_reasons=stale_reasons,
            missing_artifacts=missing if not has_ast else [],
            actionable_message=(
                "Os artefactos de origem (AST/Dossier/Plano) foram atualizados; considere regenerar modos desatualizados (edições manuais serão preservadas)."
                if stale_reasons
                else "Artefactos académicos prontos para os modos de estudo da Fase 6."
            ),
            current_fingerprints=current_fp,
        )

    def _detect_staleness(self, document_id: str, current_fp: SourceFingerprintSnapshot) -> List[str]:
        reasons: List[str] = []
        meta = self.persistence.load_json_doc_artifact(document_id, self.META_FILE, None)
        if not isinstance(meta, dict):
            return reasons
        saved_fp = SourceFingerprintSnapshot.from_dict(meta.get("fingerprints") or {})
        if saved_fp.plan_fingerprint and saved_fp.plan_fingerprint != current_fp.plan_fingerprint:
            reasons.append("PLAN_CHANGED")
        if saved_fp.dossier_fingerprint and saved_fp.dossier_fingerprint != current_fp.dossier_fingerprint:
            reasons.append("DOSSIER_CHANGED")
        if saved_fp.ast_fingerprint and current_fp.ast_fingerprint != "AST_ABSENT" and saved_fp.ast_fingerprint != current_fp.ast_fingerprint:
            reasons.append("AST_CHANGED")
        return reasons

    def _update_meta_fingerprints(self, document_id: str, fp: SourceFingerprintSnapshot) -> None:
        self.persistence.save_json_doc_artifact(
            document_id,
            self.META_FILE,
            {
                "document_id": document_id,
                "fingerprints": fp.to_dict(),
                "updated_at": datetime.now().isoformat(),
            },
        )

    def _require_grounding(
        self,
        document_id: str,
        *,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        ast: Optional[AcademicDocumentAST] = None,
    ) -> Phase6GroundingHelper:
        readiness = self.check_readiness(document_id, plan=plan, dossier=dossier, ast=ast)
        if not readiness.is_ready:
            raise ValueError(f"[{readiness.status}] {readiness.actionable_message}")
        r_plan, r_dossier, r_ast, raw = self._resolve_upstream(
            document_id, plan=plan, dossier=dossier, ast=ast
        )
        assert r_plan is not None and r_dossier is not None
        return Phase6GroundingHelper(
            r_plan,
            r_dossier,
            ast=r_ast,
            developed_content=raw.get("developed_content_data"),
        )

    # ------------------------------------------------------------------
    # 1. Flashcards & Repetição Espaçada
    # ------------------------------------------------------------------

    def generate_flashcards(
        self,
        document_id: str,
        *,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        ast: Optional[AcademicDocumentAST] = None,
        force_regenerate: bool = False,
        target_cards: int = 16,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
    ) -> StudyDeck:
        grounding = self._require_grounding(document_id, plan=plan, dossier=dossier, ast=ast)
        deck = self.flashcards.generate_deck(
            grounding,
            force_regenerate=force_regenerate,
            target_cards=target_cards,
            llm_caller=self.llm_caller,
            on_progress=on_progress,
        )
        # Registar cartões ativos no SRS sem sobrescrever histórico existente
        srs_items = [
            ReviewSchedulingState(
                item_id=c.card_id,
                item_type="flashcard",
                document_id=document_id,
                chapter_id=c.chapter_id,
                section_id=c.section_id,
                topic=c.topic,
                concept_ids=list(c.concept_ids),
                learning_objective_id=c.learning_objective_id,
                content_difficulty=c.content_difficulty,
                question_difficulty=c.question_difficulty,
            )
            for c in deck.cards
            if not c.is_deleted
        ]
        self.srs.register_items(srs_items)
        if deck.fingerprints:
            self._update_meta_fingerprints(document_id, deck.fingerprints)
        return deck

    def get_flashcards(self, document_id: str, *, include_deleted: bool = False) -> Dict[str, Any]:
        deck = self.flashcards.load_deck(document_id)
        if not deck:
            return {"document_id": document_id, "deck": None, "cards": []}
        states = self.srs.get_all_states(document_id=document_id)
        cards_out = []
        for c in deck.cards:
            if not include_deleted and c.is_deleted:
                continue
            cd = c.to_dict()
            st = states.get(c.card_id)
            if st is not None:
                cd["srs"] = st.to_dict()
            cards_out.append(cd)
        return {"document_id": document_id, "deck": deck.to_dict(), "cards": cards_out}

    def edit_flashcard(self, document_id: str, card_id: str, **updates: Any) -> AdaptiveFlashcard:
        return self.flashcards.edit_flashcard(document_id, card_id, **updates)

    def delete_flashcard(self, document_id: str, card_id: str) -> bool:
        return self.flashcards.delete_flashcard(document_id, card_id)

    def create_flashcard(self, document_id: str, **fields: Any) -> AdaptiveFlashcard:
        card = self.flashcards.create_custom_flashcard(document_id, **fields)
        self.srs.register_items([
            ReviewSchedulingState(
                item_id=card.card_id,
                item_type="flashcard",
                document_id=document_id,
                chapter_id=card.chapter_id,
                section_id=card.section_id,
                topic=card.topic,
                content_difficulty=card.content_difficulty,
                question_difficulty=card.question_difficulty,
            )
        ])
        return card

    def regenerate_flashcard(
        self,
        document_id: str,
        card_id: str,
        *,
        allow_overwrite_edited: bool = False,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        ast: Optional[AcademicDocumentAST] = None,
    ) -> AdaptiveFlashcard:
        grounding = self._require_grounding(document_id, plan=plan, dossier=dossier, ast=ast)
        return self.flashcards.regenerate_single_card(
            grounding,
            card_id,
            allow_overwrite_edited=allow_overwrite_edited,
            llm_caller=self.llm_caller,
        )

    def review_flashcard(
        self,
        document_id: str,
        card_id: str,
        rating: str,
        *,
        confidence: int = 3,
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        deck = self.flashcards.load_deck(document_id)
        if not deck:
            raise ValueError(f"Baralho não encontrado para '{document_id}'.")
        card = next((c for c in deck.cards if c.card_id == card_id and not c.is_deleted), None)
        if not card:
            raise ValueError(f"Flashcard '{card_id}' não encontrado.")

        srs_state, history_ev = self.srs.record_review(
            item_id=card.card_id,
            item_type="flashcard",
            document_id=document_id,
            rating=rating,
            confidence=confidence,
            content_difficulty=card.content_difficulty,
            question_difficulty=card.question_difficulty,
            chapter_id=card.chapter_id,
            section_id=card.section_id,
            topic=card.topic,
            concept_ids=card.concept_ids,
            learning_objective_id=card.learning_objective_id,
            now_ts=now_ts,
        )

        if srs_state.learning_state == ReviewLearningState.MATURE.value:
            card.review_status = FlashcardReviewStatus.MASTERED.value
        elif card.user_edited:
            card.review_status = FlashcardReviewStatus.EDITED.value
        else:
            card.review_status = FlashcardReviewStatus.LEARNING.value
        self.flashcards.save_deck(deck)

        prog = self.get_learning_progress(document_id, recompute=True)
        return {
            "flashcard": card.to_dict(),
            "srs_state": srs_state.to_dict(),
            "history_event": history_ev.to_dict(),
            "progress": prog.to_dict(),
        }

    # ------------------------------------------------------------------
    # 2. Cornell Notes
    # ------------------------------------------------------------------

    def generate_cornell_notes(
        self,
        document_id: str,
        *,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        ast: Optional[AcademicDocumentAST] = None,
        force_regenerate: bool = False,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
    ) -> CornellStudyDocument:
        grounding = self._require_grounding(document_id, plan=plan, dossier=dossier, ast=ast)
        doc = self.cornell.generate_cornell(
            grounding,
            force_regenerate=force_regenerate,
            llm_caller=self.llm_caller,
            on_progress=on_progress,
        )
        if doc.fingerprints:
            self._update_meta_fingerprints(document_id, doc.fingerprints)
        return doc

    def get_cornell_notes(self, document_id: str) -> Optional[CornellStudyDocument]:
        return self.cornell.load_cornell(document_id)

    def edit_cornell_entry(self, document_id: str, section_id: str, **updates: Any) -> CornellNoteEntry:
        return self.cornell.edit_entry(document_id, section_id, **updates)

    def add_cornell_personal_note(
        self,
        document_id: str,
        section_id: str,
        content: str,
        *,
        is_important: bool = False,
    ) -> CornellPersonalNote:
        return self.cornell.add_personal_note(document_id, section_id, content, is_important=is_important)

    def export_cornell_markdown(self, document_id: str, *, vault_root: Optional[str] = None) -> str:
        doc = self.cornell.load_cornell(document_id)
        if not doc:
            raise ValueError(f"Cornell Notes não encontradas para '{document_id}'.")
        return self.cornell.export_markdown(doc, vault_root=vault_root)

    # ------------------------------------------------------------------
    # 3. Avaliações & Quizzes
    # ------------------------------------------------------------------

    def generate_assessment(
        self,
        document_id: str,
        *,
        config: Optional[AssessmentConfig] = None,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        ast: Optional[AcademicDocumentAST] = None,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
    ) -> StudyAssessment:
        grounding = self._require_grounding(document_id, plan=plan, dossier=dossier, ast=ast)
        assessment = self.assessments.generate_assessment(
            grounding,
            config=config,
            llm_caller=self.llm_caller,
            on_progress=on_progress,
        )
        if assessment.fingerprints:
            self._update_meta_fingerprints(document_id, assessment.fingerprints)
        return assessment

    def get_assessments(self, document_id: str) -> List[StudyAssessment]:
        return self.assessments.load_assessments(document_id)

    def check_single_question(
        self,
        document_id: str,
        assessment_id: str,
        question_id: str,
        student_answer: Any,
        *,
        use_llm_for_open: bool = False,
    ) -> QuestionAttemptOutcome:
        assessment = self.assessments.get_assessment(document_id, assessment_id)
        if not assessment:
            raise ValueError(f"Avaliação '{assessment_id}' não encontrada.")
        question = next((q for q in assessment.questions if q.question_id == question_id), None)
        if not question:
            raise ValueError(f"Questão '{question_id}' não encontrada.")
        return self.assessments.evaluate_single_question(
            question,
            student_answer,
            use_llm_for_open=use_llm_for_open,
            llm_caller=self.llm_caller,
        )

    def submit_assessment(
        self,
        document_id: str,
        assessment_id: str,
        user_answers: Dict[str, Any],
        *,
        use_llm_for_open: bool = False,
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        assessment = self.assessments.get_assessment(document_id, assessment_id)
        if not assessment:
            raise ValueError(f"Avaliação '{assessment_id}' não encontrada para '{document_id}'.")

        attempt = self.assessments.submit_assessment(
            assessment,
            user_answers,
            use_llm_for_open=use_llm_for_open,
            llm_caller=self.llm_caller,
        )
        self.progress.record_assessment_attempt(attempt)

        # Alimentar repetição espaçada por questão respondida
        for out in attempt.outcomes:
            if out.verdict == "UNANSWERED":
                continue
            self.srs.record_review(
                item_id=out.question_id,
                item_type="assessment_question",
                document_id=document_id,
                score_ratio=out.score_ratio,
                confidence=4 if out.is_correct else 2,
                content_difficulty=out.content_difficulty,
                question_difficulty=out.question_difficulty,
                chapter_id=out.chapter_id,
                section_id=out.section_id,
                topic=out.topic,
                concept_ids=out.related_concept_ids,
                learning_objective_id=out.learning_objective_id,
                now_ts=now_ts,
            )

        prog = self.get_learning_progress(document_id, recompute=True)
        return {
            "attempt": attempt.to_dict(),
            "progress": prog.to_dict(),
        }

    # ------------------------------------------------------------------
    # 4. Active Recall
    # ------------------------------------------------------------------

    def generate_active_recall(
        self,
        document_id: str,
        *,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        ast: Optional[AcademicDocumentAST] = None,
        force_regenerate: bool = False,
        target_prompts: int = 8,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
    ) -> ActiveRecallDeck:
        grounding = self._require_grounding(document_id, plan=plan, dossier=dossier, ast=ast)
        deck = self.active_recall.generate_prompts(
            grounding,
            force_regenerate=force_regenerate,
            target_prompts=target_prompts,
            llm_caller=self.llm_caller,
            on_progress=on_progress,
        )
        self.srs.register_items([
            ReviewSchedulingState(
                item_id=p.prompt_id,
                item_type="active_recall",
                document_id=document_id,
                chapter_id=p.chapter_id,
                section_id=p.section_id,
                topic=p.topic,
                concept_ids=list(p.concept_ids),
                learning_objective_id=p.learning_objective_id,
                content_difficulty=p.content_difficulty,
                question_difficulty=p.question_difficulty,
            )
            for p in deck.prompts
        ])
        if deck.fingerprints:
            self._update_meta_fingerprints(document_id, deck.fingerprints)
        return deck

    def get_active_recall_prompts(self, document_id: str, *, reveal_answers: bool = False) -> Dict[str, Any]:
        deck = self.active_recall.load_deck(document_id)
        if not deck:
            return {"document_id": document_id, "prompts": []}
        return {
            "document_id": document_id,
            "generation_mode": deck.generation_mode,
            "prompts": [
                self.active_recall.serialize_for_student(p, reveal_answer=reveal_answers)
                for p in deck.prompts
            ],
        }

    def submit_active_recall(
        self,
        document_id: str,
        prompt_id: str,
        *,
        student_response: str,
        self_confidence: int = 3,
        outline_used: bool = False,
        use_llm: bool = False,
        now_ts: Optional[float] = None,
    ) -> Dict[str, Any]:
        deck = self.active_recall.load_deck(document_id)
        if not deck:
            raise ValueError(f"Atividades de Active Recall não encontradas para '{document_id}'.")
        prompt = next((p for p in deck.prompts if p.prompt_id == prompt_id), None)
        if not prompt:
            raise ValueError(f"Prompt de Active Recall '{prompt_id}' não encontrado.")

        attempt = self.active_recall.submit_attempt(
            prompt,
            student_response=student_response,
            self_confidence=self_confidence,
            outline_used=outline_used,
            use_llm=use_llm,
            llm_caller=self.llm_caller,
        )

        rating = "RECALL_PASS" if attempt.self_rating == "RECALLED" else ("HARD" if attempt.self_rating == "PARTIAL" else "RECALL_MISS")
        srs_state, _ = self.srs.record_review(
            item_id=prompt.prompt_id,
            item_type="active_recall",
            document_id=document_id,
            rating=rating,
            score_ratio=attempt.score_ratio,
            confidence=attempt.self_confidence,
            content_difficulty=prompt.content_difficulty,
            question_difficulty=prompt.question_difficulty,
            chapter_id=prompt.chapter_id,
            section_id=prompt.section_id,
            topic=prompt.topic,
            concept_ids=prompt.concept_ids,
            learning_objective_id=prompt.learning_objective_id,
            now_ts=now_ts,
        )
        attempt.scheduled_next_review_ts = srs_state.next_review_ts
        self.progress.record_recall_attempt(attempt)

        prog = self.get_learning_progress(document_id, recompute=True)
        gap_concepts = {g.concept_id for g in prog.knowledge_gaps if g.concept_id}
        if set(prompt.concept_ids) & gap_concepts or attempt.self_rating == "MISSED":
            attempt.identified_gap_triggered = bool(set(prompt.concept_ids) & gap_concepts)

        return {
            "attempt": attempt.to_dict(),
            "srs_state": srs_state.to_dict(),
            "progress": prog.to_dict(),
        }

    # ------------------------------------------------------------------
    # 5. Revisão Diária, Progresso e Sessões
    # ------------------------------------------------------------------

    def get_daily_review_queue(
        self,
        document_id: str,
        *,
        daily_new_limit: int = 10,
        daily_review_limit: int = 30,
        now_ts: Optional[float] = None,
    ) -> DailyReviewQueue:
        available: List[Dict[str, Any]] = []
        deck = self.flashcards.load_deck(document_id)
        if deck:
            for c in deck.cards:
                if c.is_deleted:
                    continue
                available.append({
                    "item_id": c.card_id,
                    "item_type": "flashcard",
                    "title": c.front,
                    "topic": c.topic,
                    "chapter_id": c.chapter_id,
                    "section_id": c.section_id,
                    "content_difficulty": c.content_difficulty,
                    "question_difficulty": c.question_difficulty,
                    "epistemic_status": c.epistemic_status,
                })
        ar_deck = self.active_recall.load_deck(document_id)
        if ar_deck:
            for p in ar_deck.prompts:
                available.append({
                    "item_id": p.prompt_id,
                    "item_type": "active_recall",
                    "title": p.prompt_text,
                    "topic": p.topic,
                    "chapter_id": p.chapter_id,
                    "section_id": p.section_id,
                    "content_difficulty": p.content_difficulty,
                    "question_difficulty": p.question_difficulty,
                    "epistemic_status": p.epistemic_status,
                })

        prog = self.get_learning_progress(document_id, recompute=False)
        weak_topics = [
            t for t, stats in (prog.by_topic.items() if prog else [])
            if stats.get("accuracy_pct", 100.0) < 70.0
        ]
        for g in (prog.knowledge_gaps if prog else []):
            if g.concept_name:
                weak_topics.append(g.concept_name)

        return self.srs.build_daily_queue(
            document_id,
            available_items=available,
            weak_topics=list(dict.fromkeys(weak_topics)),
            daily_new_limit=daily_new_limit,
            daily_review_limit=daily_review_limit,
            now_ts=now_ts,
        )

    def get_learning_progress(
        self,
        document_id: str,
        *,
        recompute: bool = True,
    ) -> LearningProgressSnapshot:
        if not recompute:
            cached = self.progress.load_progress(document_id)
            if cached is not None:
                return cached
        r_plan, r_dossier, _, _ = self._resolve_upstream(document_id)
        srs_states = self.srs.get_all_states(document_id=document_id)
        srs_hist = self.srs.get_history(document_id=document_id)
        ar_deck = self.active_recall.load_deck(document_id)
        return self.progress.recompute_progress(
            document_id,
            plan=r_plan,
            dossier=r_dossier,
            srs_states=srs_states,
            srs_history=srs_hist,
            recall_deck=ar_deck,
        )

    # Atalhos para Gestão de Sessões e Histórico
    def start_study_session(self, **kwargs: Any) -> StudySessionState:
        return self.sessions.start_session(**kwargs)

    def record_session_step(self, session_id: str, **kwargs: Any) -> StudySessionState:
        return self.sessions.record_step(session_id, **kwargs)

    def pause_study_session(self, session_id: str) -> StudySessionState:
        return self.sessions.pause_session(session_id)

    def resume_study_session(self, session_id: str) -> StudySessionState:
        return self.sessions.resume_session(session_id)

    def complete_study_session(self, session_id: str, *, summary_stats: Optional[Dict[str, Any]] = None) -> StudySessionState:
        return self.sessions.complete_session(session_id, summary_stats=summary_stats)

    def list_study_sessions(self, *, document_id: Optional[str] = None, status: Optional[str] = None) -> List[StudySessionState]:
        return self.sessions.list_sessions(document_id=document_id, status=status)

    def get_study_session(self, session_id: str) -> Optional[StudySessionState]:
        return self.sessions.get_session(session_id)

