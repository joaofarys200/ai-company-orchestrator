"""
JARVIS OS — Study Engine Phase 6: Learning Progress & Knowledge Gap Engine
Agrega o desempenho real entre flashcards, quizzes e active recall, exige evidência mínima
antes de declarar proficiência e liga lacunas persistentes às respetivas provas da fonte.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
from typing import Any, Dict, List, Optional, Sequence

from services.academic_reasoning_engine import AcademicReasoningDossier, EvidenceRef
from services.editorial_intelligence_engine import EditorialStudyPlan
from services.study_modes.contracts import (
    ActiveRecallAttempt,
    ActiveRecallDeck,
    AssessmentAttempt,
    KnowledgeGap,
    KnowledgeGapType,
    LearningProgressSnapshot,
    MasteryLevel,
    ReviewHistoryEntry,
    ReviewLearningState,
    ReviewSchedulingState,
    _deserialize_refs,
)
from services.study_modes.persistence import StudyModePersistence


class LearningProgressEngine:
    """Calcula progresso granular e lacunas reais sem declarar domínio com dados insuficientes."""

    PROGRESS_FILE = "learning_progress.json"
    ATTEMPTS_FILE = "assessment_attempts.json"
    RECALL_ATTEMPTS_FILE = "active_recall_attempts.json"

    # Limiar mínimo de evidência: evitar considerar todo um capítulo dominado após 1 pergunta fácil
    MIN_OBS_FOR_CHAPTER_MASTERY = 3
    MIN_OBS_FOR_CONCEPT_MASTERY = 2
    MIN_FAILURES_FOR_GAP = 2

    def __init__(self, persistence: StudyModePersistence) -> None:
        self.persistence = persistence

    @staticmethod
    def _classify_mastery(attempts: int, weighted_acc: float, min_obs: int) -> str:
        if attempts < min_obs:
            return MasteryLevel.INSUFFICIENT_EVIDENCE.value
        if weighted_acc >= 0.85:
            return MasteryLevel.PROFICIENT.value
        if weighted_acc >= 0.65:
            return MasteryLevel.DEVELOPING.value
        return MasteryLevel.EMERGING.value

    def load_progress(self, document_id: str) -> Optional[LearningProgressSnapshot]:
        raw = self.persistence.load_state_file(self.PROGRESS_FILE, {})
        if isinstance(raw, dict) and isinstance(raw.get(document_id), dict):
            return LearningProgressSnapshot.from_dict(raw[document_id])
        return None

    def recompute_progress(
        self,
        document_id: str,
        *,
        plan: Optional[EditorialStudyPlan] = None,
        dossier: Optional[AcademicReasoningDossier] = None,
        srs_states: Optional[Dict[str, ReviewSchedulingState]] = None,
        srs_history: Optional[Sequence[ReviewHistoryEntry]] = None,
        recall_deck: Optional[ActiveRecallDeck] = None,
    ) -> LearningProgressSnapshot:
        attempts_raw = self.persistence.load_state_file(self.ATTEMPTS_FILE, [])
        doc_attempts = [
            AssessmentAttempt.from_dict(a)
            for a in (attempts_raw if isinstance(attempts_raw, list) else [])
            if isinstance(a, dict) and a.get("document_id") == document_id
        ]

        recall_raw = self.persistence.load_state_file(self.RECALL_ATTEMPTS_FILE, [])
        doc_recall = [
            ActiveRecallAttempt.from_dict(r)
            for r in (recall_raw if isinstance(recall_raw, list) else [])
            if isinstance(r, dict) and r.get("document_id") == document_id
        ]

        recall_prompts_by_id = {
            p.prompt_id: p for p in (getattr(recall_deck, "prompts", None) or [])
        }
        concept_names: Dict[str, str] = {}
        concept_refs: Dict[str, List[EvidenceRef]] = {}
        if dossier is not None:
            for c in dossier.conceptual_analysis or []:
                concept_names[c.concept_id] = c.name
                concept_refs[c.concept_id] = list(c.evidence_refs or [])

        section_titles: Dict[str, str] = {}
        objective_texts: Dict[str, str] = {}
        if plan is not None:
            for obj in (getattr(plan.overview, "learning_objectives", None) or []):
                if isinstance(obj, dict) and obj.get("objective_id"):
                    objective_texts[str(obj["objective_id"])] = str(obj.get("description") or "")
            for ch in plan.chapters or []:
                for sec in ch.sections or []:
                    section_titles[sec.section_id] = sec.title

        # Estruturas acumuladoras
        chapter_stats: Dict[str, Dict[str, Any]] = {}
        section_stats: Dict[str, Dict[str, Any]] = {}
        concept_stats: Dict[str, Dict[str, Any]] = {}
        objective_stats: Dict[str, Dict[str, Any]] = {}
        topic_stats: Dict[str, Dict[str, Any]] = {}

        def _bump(bucket: Dict[str, Dict[str, Any]], key: str, ratio: float, passed: bool, label: str = "") -> None:
            if not key:
                return
            entry = bucket.setdefault(
                key,
                {
                    "id": key,
                    "label": label or key,
                    "attempts": 0,
                    "correct": 0,
                    "failures": 0,
                    "score_sum": 0.0,
                    "refs": [],
                },
            )
            entry["attempts"] += 1
            entry["score_sum"] += float(ratio)
            if passed:
                entry["correct"] += 1
            else:
                entry["failures"] += 1

        questions_answered = 0
        correct_answers = 0
        partial_answers = 0
        incorrect_answers = 0
        score_ratio_sum = 0.0
        confidences: List[float] = []

        # 1. Processar respostas de avaliações
        for att in doc_attempts:
            for out in att.outcomes:
                if out.verdict == "UNANSWERED":
                    continue
                questions_answered += 1
                score_ratio_sum += out.score_ratio
                if out.is_correct:
                    correct_answers += 1
                elif out.score_ratio >= 0.4:
                    partial_answers += 1
                else:
                    incorrect_answers += 1

                _bump(chapter_stats, out.chapter_id, out.score_ratio, out.is_correct)
                _bump(section_stats, out.section_id, out.score_ratio, out.is_correct, section_titles.get(out.section_id, out.section_id))
                _bump(topic_stats, out.topic, out.score_ratio, out.is_correct)
                _bump(objective_stats, out.learning_objective_id, out.score_ratio, out.is_correct, objective_texts.get(out.learning_objective_id, out.learning_objective_id))
                for cid in out.related_concept_ids:
                    _bump(concept_stats, cid, out.score_ratio, out.is_correct, concept_names.get(cid, cid))
                    if out.evidence_refs and not concept_stats[cid]["refs"]:
                        concept_stats[cid]["refs"] = [asdict(r) for r in out.evidence_refs[:2]]

        # 2. Processar tentativas de Active Recall
        for rec in doc_recall:
            confidences.append(float(rec.self_confidence))
            prompt = recall_prompts_by_id.get(rec.prompt_id)
            passed = rec.score_ratio >= 0.7 or rec.self_rating == "RECALLED"
            if prompt is not None:
                _bump(chapter_stats, prompt.chapter_id, rec.score_ratio, passed)
                _bump(section_stats, prompt.section_id, rec.score_ratio, passed, prompt.section_title)
                _bump(topic_stats, prompt.topic, rec.score_ratio, passed)
                _bump(objective_stats, prompt.learning_objective_id, rec.score_ratio, passed, prompt.learning_objective_text)
                for cid in prompt.concept_ids:
                    _bump(concept_stats, cid, rec.score_ratio, passed, concept_names.get(cid, cid))
                    if prompt.evidence_refs and not concept_stats[cid]["refs"]:
                        concept_stats[cid]["refs"] = [asdict(r) for r in prompt.evidence_refs[:2]]

        # 3. Processar revisões SRS (flashcards / itens agendados)
        flashcard_reviews_total = 0
        for ev in (srs_history or []):
            if ev.document_id != document_id:
                continue
            confidences.append(float(ev.confidence))
            if ev.item_type == "flashcard":
                flashcard_reviews_total += 1
            st = (srs_states or {}).get(ev.item_id)
            if st is not None:
                ok_recall = ev.quality_score >= 3
                ratio = min(1.0, max(0.0, ev.quality_score / 5.0))
                _bump(chapter_stats, st.chapter_id, ratio, ok_recall)
                _bump(section_stats, st.section_id, ratio, ok_recall, section_titles.get(st.section_id, st.section_id))
                _bump(topic_stats, st.topic, ratio, ok_recall)
                _bump(objective_stats, st.learning_objective_id, ratio, ok_recall)
                for cid in st.concept_ids:
                    _bump(concept_stats, cid, ratio, ok_recall, concept_names.get(cid, cid))

        # Finalizar mastery em cada bucket
        def _finalize_bucket(bucket: Dict[str, Dict[str, Any]], min_obs: int) -> Dict[str, Dict[str, Any]]:
            res: Dict[str, Dict[str, Any]] = {}
            for k, b in bucket.items():
                att = max(1, b["attempts"])
                acc = b["score_sum"] / att
                res[k] = {
                    "id": k,
                    "label": b["label"],
                    "attempts": b["attempts"],
                    "correct": b["correct"],
                    "failures": b["failures"],
                    "accuracy_pct": round(acc * 100.0, 1),
                    "mastery_level": self._classify_mastery(b["attempts"], acc, min_obs),
                }
            return res

        by_chapter = _finalize_bucket(chapter_stats, self.MIN_OBS_FOR_CHAPTER_MASTERY)
        by_section = _finalize_bucket(section_stats, self.MIN_OBS_FOR_CONCEPT_MASTERY)
        by_concept = _finalize_bucket(concept_stats, self.MIN_OBS_FOR_CONCEPT_MASTERY)
        by_objective = _finalize_bucket(objective_stats, self.MIN_OBS_FOR_CONCEPT_MASTERY)
        by_topic = _finalize_bucket(topic_stats, self.MIN_OBS_FOR_CONCEPT_MASTERY)

        # Objetivos sem evidência suficiente
        insufficient_objs: List[str] = []
        for obj_id, obj_desc in objective_texts.items():
            st_obj = by_objective.get(obj_id)
            if not st_obj or st_obj["mastery_level"] == MasteryLevel.INSUFFICIENT_EVIDENCE.value:
                insufficient_objs.append(obj_id)

        repeatedly_missed_concepts = [
            cid for cid, cs in by_concept.items() if cs["failures"] >= self.MIN_FAILURES_FOR_GAP
        ]
        consistently_recalled_concepts = [
            cid
            for cid, cs in by_concept.items()
            if cs["attempts"] >= self.MIN_OBS_FOR_CONCEPT_MASTERY
            and cs["accuracy_pct"] >= 80.0
            and cs["failures"] == 0
        ]

        # Identificação rigorosa de Knowledge Gaps (apenas com histórico suficiente!)
        gaps: List[KnowledgeGap] = []
        avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else None

        for cid, cs in concept_stats.items():
            if cs["failures"] >= self.MIN_FAILURES_FOR_GAP:
                c_name = concept_names.get(cid, cid)
                refs = concept_refs.get(cid) or _deserialize_refs(cs.get("refs", []))
                gap_id = f"gap_{hashlib.sha1(f'{document_id}:{cid}'.encode('utf-8')).hexdigest()[:10]}"
                gaps.append(
                    KnowledgeGap(
                        gap_id=gap_id,
                        document_id=document_id,
                        gap_type=KnowledgeGapType.REPEATED_CONCEPT_MISS.value,
                        concept_id=cid,
                        concept_name=c_name,
                        section_id=refs[0].section_id if refs else "",
                        severity="HIGH" if cs["failures"] >= 3 else "MEDIUM",
                        failure_count=cs["failures"],
                        attempts_count=cs["attempts"],
                        avg_confidence=avg_conf or 0.0,
                        description=(
                            f"Dificuldade recorrente no conceito «{c_name}» "
                            f"({cs['failures']} falha(s) em {cs['attempts']} tentativa(s))."
                        ),
                        evidence_refs=refs[:3],
                        suggested_activities=[
                            {"mode": "ACTIVE_RECALL", "label": f"Praticar Active Recall sobre «{c_name}»", "target": cid},
                            {"mode": "FLASHCARD_REVIEW", "label": f"Rever cartões de «{c_name}»", "target": cid},
                            {"mode": "CORNELL_STUDY", "label": "Consultar secção nas Cornell Notes", "target": refs[0].section_id if refs else ""},
                        ],
                    )
                )

        for ch_id, ch_s in by_chapter.items():
            if ch_s["attempts"] >= self.MIN_OBS_FOR_CHAPTER_MASTERY and ch_s["failures"] >= 2 and ch_s["accuracy_pct"] < 60.0:
                gap_id = f"gap_{hashlib.sha1(f'{document_id}:ch:{ch_id}'.encode('utf-8')).hexdigest()[:10]}"
                gaps.append(
                    KnowledgeGap(
                        gap_id=gap_id,
                        document_id=document_id,
                        gap_type=KnowledgeGapType.CHAPTER_STRUGGLE.value,
                        chapter_id=ch_id,
                        severity="HIGH" if ch_s["accuracy_pct"] < 40.0 else "MEDIUM",
                        failure_count=ch_s["failures"],
                        attempts_count=ch_s["attempts"],
                        avg_confidence=avg_conf or 0.0,
                        description=(
                            f"Desempenho consistente abaixo do limiar no capítulo {ch_id} "
                            f"({ch_s['accuracy_pct']}% de acerto em {ch_s['attempts']} verificações)."
                        ),
                        suggested_activities=[
                            {"mode": "CORNELL_STUDY", "label": "Rever síntese Cornell do capítulo", "target": ch_id},
                            {"mode": "ASSESSMENT", "label": "Fazer sessão prática dirigida ao capítulo", "target": ch_id},
                        ],
                    )
                )

        total_obs = questions_answered + len(doc_recall) + flashcard_reviews_total
        overall_acc = (
            round((score_ratio_sum / questions_answered) * 100.0, 1)
            if questions_answered > 0
            else None
        )
        overall_ratio = (overall_acc / 100.0) if overall_acc is not None else 0.0
        overall_mastery = self._classify_mastery(total_obs, overall_ratio, self.MIN_OBS_FOR_CHAPTER_MASTERY)

        snapshot = LearningProgressSnapshot(
            document_id=document_id,
            questions_answered=questions_answered,
            correct_answers=correct_answers,
            partial_answers=partial_answers,
            incorrect_answers=incorrect_answers,
            flashcard_reviews_total=flashcard_reviews_total,
            active_recall_attempts_total=len(doc_recall),
            overall_accuracy_pct=overall_acc,
            avg_recall_confidence=avg_conf,
            mastery_level=overall_mastery,
            by_chapter=by_chapter,
            by_section=by_section,
            by_concept=by_concept,
            by_objective=by_objective,
            by_topic=by_topic,
            repeatedly_missed_concepts=repeatedly_missed_concepts,
            consistently_recalled_concepts=consistently_recalled_concepts,
            insufficient_evidence_objectives=insufficient_objs,
            knowledge_gaps=gaps,
        )

        def _save_prog(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            store[document_id] = snapshot.to_dict()
            return store

        self.persistence.update_state_file_atomic(self.PROGRESS_FILE, {}, _save_prog)
        return snapshot

    def record_assessment_attempt(self, attempt: AssessmentAttempt) -> None:
        def _append(cur: Any) -> List[Any]:
            arr = list(cur) if isinstance(cur, list) else []
            arr.append(attempt.to_dict())
            return arr

        self.persistence.update_state_file_atomic(self.ATTEMPTS_FILE, [], _append)

    def get_assessment_history(self, document_id: Optional[str] = None) -> List[AssessmentAttempt]:
        raw = self.persistence.load_state_file(self.ATTEMPTS_FILE, [])
        out: List[AssessmentAttempt] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                att = AssessmentAttempt.from_dict(item)
                if not document_id or att.document_id == document_id:
                    out.append(att)
        return list(reversed(out))

    def record_recall_attempt(self, attempt: ActiveRecallAttempt) -> None:
        def _append(cur: Any) -> List[Any]:
            arr = list(cur) if isinstance(cur, list) else []
            arr.append(attempt.to_dict())
            return arr

        self.persistence.update_state_file_atomic(self.RECALL_ATTEMPTS_FILE, [], _append)

    def get_recall_history(self, document_id: Optional[str] = None) -> List[ActiveRecallAttempt]:
        raw = self.persistence.load_state_file(self.RECALL_ATTEMPTS_FILE, [])
        out: List[ActiveRecallAttempt] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                att = ActiveRecallAttempt.from_dict(item)
                if not document_id or att.document_id == document_id:
                    out.append(att)
        return list(reversed(out))
