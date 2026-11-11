"""
JARVIS OS — Study Engine Phase 6: Spaced Repetition Engine (SM-2 Adaptativo)

Algoritmo escolhido: SuperMemo SM-2 Modificado e Versionado (`sm2-v6.0`).
Justificação arquitetural:
  - Determinístico, transparente, auditável e adequado a históricos discretos de estudo local
    sem exigir grandes volumes de treino por utilizador (ao contrário de modelos FSRS treinados por ML).
  - Separa explicitamente três variáveis distintas:
      1. `content_difficulty`: complexidade intrínseca do tópico na fonte (`FOUNDATIONAL | INTERMEDIATE | ADVANCED`)
      2. `question_difficulty`: exigência da questão/cartão (`EASY | MEDIUM | HARD`)
      3. `student_performance`: desempenho real observado do estudante (`quality_score` 0..5 + `confidence` 1..5)
  - Limitações documentadas do SM-2:
      * A atualização linear do fator de facilidade (`EF`) penaliza lapsos repetidos e converge
        para um teto máximo de 365 dias (`MAX_INTERVAL_DAYS`);
      * Não modela dependência cruzada temporal entre dois conceitos na mesma sessão
        (mitigado na fila diária através da ordenação por tópicos fracos e baixa confiança).
  - Uma mudança futura de `algorithm_version` nunca corrompe o histórico: cada registo
    preserva o `algorithm_version` e os parâmetros ativos no momento da avaliação.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from services.study_modes.contracts import (
    ContentDifficulty,
    DailyReviewQueue,
    QuestionDifficulty,
    ReviewHistoryEntry,
    ReviewLearningState,
    ReviewSchedulingState,
    SRS_ALGORITHM_VERSION,
)
from services.study_modes.persistence import StudyModePersistence


class SpacedRepetitionEngine:
    """Agenda revisões adaptativas com base no algoritmo determinístico SM-2 Modificado."""

    STATES_FILE = "srs_state.json"
    HISTORY_FILE = "srs_history.json"

    MIN_EASE_FACTOR = 1.3
    DEFAULT_EASE_FACTOR = 2.5
    MAX_EASE_FACTOR = 3.2
    MIN_INTERVAL_DAYS = 1.0
    MAX_INTERVAL_DAYS = 365.0
    MATURE_INTERVAL_THRESHOLD_DAYS = 21.0

    def __init__(self, persistence: StudyModePersistence) -> None:
        self.persistence = persistence

    # ------------------------------------------------------------------
    # Conversão determinística desempenho -> qualidade SM-2 (0..5)
    # ------------------------------------------------------------------

    @staticmethod
    def map_outcome_to_quality(
        *,
        rating: Optional[str] = None,
        score_ratio: Optional[float] = None,
        confidence: int = 3,
    ) -> int:
        if rating:
            r = str(rating).strip().upper()
            mapping = {
                "AGAIN": 1,
                "FAIL": 1,
                "MISSED": 1,
                "RECALL_MISS": 1,
                "HARD": 3,
                "PARTIAL": 3,
                "GOOD": 4,
                "RECALL_PASS": 4,
                "EASY": 5,
            }
            if r in mapping:
                q = mapping[r]
                # Confiança muito baixa (1) em resposta "Good" atenua ligeiramente o ganho
                if q == 4 and confidence <= 1:
                    return 3
                return q
        ratio = float(score_ratio if score_ratio is not None else 0.0)
        if ratio >= 0.90:
            return 5 if confidence >= 4 else 4
        if ratio >= 0.70:
            return 4 if confidence >= 3 else 3
        if ratio >= 0.45:
            return 3
        if ratio > 0.15:
            return 2
        return 1

    # ------------------------------------------------------------------
    # Núcleo SM-2 Modificado (puro e testável)
    # ------------------------------------------------------------------

    def compute_next_schedule(
        self,
        state: ReviewSchedulingState,
        *,
        quality_score: int,
        rating_label: str,
        confidence: int = 3,
        now_ts: float,
    ) -> TupleResult:
        q = max(0, min(5, int(quality_score)))
        conf = max(1, min(5, int(confidence)))

        prev_interval = float(state.interval_days)
        prev_ef = float(state.ease_factor or self.DEFAULT_EASE_FACTOR)
        prev_learning_state = state.learning_state

        # Ajuste ligeiro de dificuldade intrínseca para modulação controlada do passo, sem misturar variáveis
        difficulty_mod = 1.0
        if state.question_difficulty == QuestionDifficulty.HARD.value:
            difficulty_mod = 0.92
        elif state.question_difficulty == QuestionDifficulty.EASY.value:
            difficulty_mod = 1.05
        if state.content_difficulty == ContentDifficulty.ADVANCED.value:
            difficulty_mod *= 0.95

        if q < 3:
            # Falha ou lapso de recordação -> reinicia intervalo para consolidação imediata
            new_consecutive_success = 0
            new_consecutive_failures = state.consecutive_failures + 1
            failed_delta = 1
            success_delta = 0
            new_interval = self.MIN_INTERVAL_DAYS
            # Penalização SM-2 padrão no fator de facilidade com limite mínimo 1.3
            delta_ef = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
            new_ef = max(self.MIN_EASE_FACTOR, round(prev_ef + delta_ef, 4))
            if state.reviews_count > 0:
                new_learning_state = ReviewLearningState.LAPSED.value
            else:
                new_learning_state = ReviewLearningState.LEARNING.value
        else:
            new_consecutive_success = state.consecutive_successes + 1
            new_consecutive_failures = 0
            failed_delta = 0
            success_delta = 1
            delta_ef = 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
            new_ef = min(self.MAX_EASE_FACTOR, max(self.MIN_EASE_FACTOR, round(prev_ef + delta_ef, 4)))

            if new_consecutive_success == 1:
                new_interval = 1.0
            elif new_consecutive_success == 2:
                new_interval = 6.0 if q >= 4 else 3.0
            else:
                base = max(1.0, prev_interval) * new_ef * difficulty_mod
                if q == 3:
                    base *= 0.8
                elif q == 5:
                    base *= 1.15
                new_interval = base

            new_interval = round(min(self.MAX_INTERVAL_DAYS, max(self.MIN_INTERVAL_DAYS, new_interval)), 2)
            new_learning_state = (
                ReviewLearningState.MATURE.value
                if new_interval >= self.MATURE_INTERVAL_THRESHOLD_DAYS
                else ReviewLearningState.LEARNING.value
            )

        next_ts = now_ts + (new_interval * 86400.0)

        updated = ReviewSchedulingState(
            item_id=state.item_id,
            item_type=state.item_type,
            document_id=state.document_id,
            chapter_id=state.chapter_id,
            section_id=state.section_id,
            topic=state.topic,
            concept_ids=list(state.concept_ids),
            learning_objective_id=state.learning_objective_id,
            content_difficulty=state.content_difficulty,
            question_difficulty=state.question_difficulty,
            last_reviewed_ts=now_ts,
            next_review_ts=next_ts,
            reviews_count=state.reviews_count + 1,
            successful_recalls=state.successful_recalls + success_delta,
            failed_recalls=state.failed_recalls + failed_delta,
            consecutive_successes=new_consecutive_success,
            consecutive_failures=new_consecutive_failures,
            last_confidence=conf,
            last_performance_quality=q,
            learning_state=new_learning_state,
            interval_days=new_interval,
            ease_factor=new_ef,
            scheduling_params={
                "difficulty_modifier": round(difficulty_mod, 3),
                "min_ease_factor": self.MIN_EASE_FACTOR,
                "max_interval_days": self.MAX_INTERVAL_DAYS,
            },
            algorithm_version=SRS_ALGORITHM_VERSION,
        )

        event = ReviewHistoryEntry(
            event_id=f"srsev_{uuid.uuid4().hex[:10]}",
            item_id=state.item_id,
            item_type=state.item_type,
            document_id=state.document_id,
            timestamp=now_ts,
            rating=rating_label,
            quality_score=q,
            confidence=conf,
            content_difficulty=state.content_difficulty,
            question_difficulty=state.question_difficulty,
            previous_interval_days=prev_interval,
            new_interval_days=new_interval,
            previous_ease_factor=prev_ef,
            new_ease_factor=new_ef,
            previous_state=prev_learning_state,
            new_state=new_learning_state,
            algorithm_version=SRS_ALGORITHM_VERSION,
        )
        return updated, event

    # ------------------------------------------------------------------
    # Operações com Persistência
    # ------------------------------------------------------------------

    def get_all_states(self, document_id: Optional[str] = None) -> Dict[str, ReviewSchedulingState]:
        raw = self.persistence.load_state_file(self.STATES_FILE, {})
        out: Dict[str, ReviewSchedulingState] = {}
        if isinstance(raw, dict):
            for k, v in raw.items():
                if not isinstance(v, dict):
                    continue
                st = ReviewSchedulingState.from_dict(v)
                if not document_id or st.document_id == document_id:
                    out[k] = st
        return out

    def get_history(self, document_id: Optional[str] = None, item_id: Optional[str] = None) -> List[ReviewHistoryEntry]:
        raw = self.persistence.load_state_file(self.HISTORY_FILE, [])
        out: List[ReviewHistoryEntry] = []
        if isinstance(raw, list):
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                ev = ReviewHistoryEntry.from_dict(entry)
                if document_id and ev.document_id != document_id:
                    continue
                if item_id and ev.item_id != item_id:
                    continue
                out.append(ev)
        return out

    def register_items(self, items: Sequence[ReviewSchedulingState]) -> None:
        if not items:
            return

        def _mutate(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            for st in items:
                if st.item_id not in store:
                    store[st.item_id] = st.to_dict()
            return store

        self.persistence.update_state_file_atomic(self.STATES_FILE, {}, _mutate)

    def record_review(
        self,
        *,
        item_id: str,
        item_type: str,
        document_id: str,
        rating: Optional[str] = None,
        score_ratio: Optional[float] = None,
        confidence: int = 3,
        content_difficulty: str = ContentDifficulty.INTERMEDIATE.value,
        question_difficulty: str = QuestionDifficulty.MEDIUM.value,
        chapter_id: str = "",
        section_id: str = "",
        topic: str = "",
        concept_ids: Optional[Sequence[str]] = None,
        learning_objective_id: str = "",
        now_ts: Optional[float] = None,
    ) -> TupleResult:
        import time as _time

        ts = float(now_ts if now_ts is not None else _time.time())
        q = self.map_outcome_to_quality(rating=rating, score_ratio=score_ratio, confidence=confidence)
        label = rating or (f"SCORE_{round((score_ratio or 0.0) * 100)}")

        result_holder: List[Any] = []

        def _mutate_state(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            existing_raw = store.get(item_id)
            if isinstance(existing_raw, dict):
                base_state = ReviewSchedulingState.from_dict(existing_raw)
            else:
                base_state = ReviewSchedulingState(
                    item_id=item_id,
                    item_type=item_type,
                    document_id=document_id,
                    chapter_id=chapter_id,
                    section_id=section_id,
                    topic=topic,
                    concept_ids=list(concept_ids or []),
                    learning_objective_id=learning_objective_id,
                    content_difficulty=content_difficulty,
                    question_difficulty=question_difficulty,
                )
            updated, event = self.compute_next_schedule(
                base_state,
                quality_score=q,
                rating_label=label,
                confidence=confidence,
                now_ts=ts,
            )
            store[item_id] = updated.to_dict()
            result_holder[:] = [updated, event]
            return store

        self.persistence.update_state_file_atomic(self.STATES_FILE, {}, _mutate_state)
        updated, event = result_holder[0], result_holder[1]

        def _append_hist(cur: Any) -> List[Any]:
            hist = list(cur) if isinstance(cur, list) else []
            hist.append(event.to_dict())
            return hist

        self.persistence.update_state_file_atomic(self.HISTORY_FILE, [], _append_hist)
        return updated, event

    def set_suspended(self, item_id: str, suspended: bool) -> Optional[ReviewSchedulingState]:
        holder: List[Optional[ReviewSchedulingState]] = [None]

        def _mutate(cur: Any) -> Dict[str, Any]:
            store = dict(cur) if isinstance(cur, dict) else {}
            raw = store.get(item_id)
            if not isinstance(raw, dict):
                return store
            st = ReviewSchedulingState.from_dict(raw)
            if suspended:
                st.learning_state = ReviewLearningState.SUSPENDED.value
            else:
                st.learning_state = (
                    ReviewLearningState.NEW.value
                    if st.reviews_count == 0
                    else (
                        ReviewLearningState.MATURE.value
                        if st.interval_days >= self.MATURE_INTERVAL_THRESHOLD_DAYS
                        else ReviewLearningState.LEARNING.value
                    )
                )
            store[item_id] = st.to_dict()
            holder[0] = st
            return store

        self.persistence.update_state_file_atomic(self.STATES_FILE, {}, _mutate)
        return holder[0]

    # ------------------------------------------------------------------
    # Fila Diária de Revisão (Sem sobrecarregar com cartões novos)
    # ------------------------------------------------------------------

    def build_daily_queue(
        self,
        document_id: str,
        *,
        available_items: Sequence[Dict[str, Any]],
        weak_topics: Optional[Sequence[str]] = None,
        daily_new_limit: int = 10,
        daily_review_limit: int = 30,
        now_ts: Optional[float] = None,
    ) -> DailyReviewQueue:
        import time as _time

        ts = float(now_ts if now_ts is not None else _time.time())
        states = self.get_all_states(document_id=document_id)
        weak_set = {w.lower() for w in (weak_topics or [])}

        lapsed: List[Dict[str, Any]] = []
        due: List[Dict[str, Any]] = []
        low_conf: List[Dict[str, Any]] = []
        new_items: List[Dict[str, Any]] = []

        for item in available_items:
            iid = str(item.get("item_id") or "")
            if not iid:
                continue
            st = states.get(iid)
            if st and st.learning_state == ReviewLearningState.SUSPENDED.value:
                continue
            enriched = dict(item)
            if st is None or st.reviews_count == 0:
                enriched["srs_state"] = ReviewLearningState.NEW.value
                enriched["interval_days"] = 0.0
                enriched["ease_factor"] = self.DEFAULT_EASE_FACTOR
                new_items.append(enriched)
                continue

            enriched["srs_state"] = (
                ReviewLearningState.DUE.value
                if st.learning_state != ReviewLearningState.LAPSED.value and st.next_review_ts <= ts
                else st.learning_state
            )
            enriched["interval_days"] = st.interval_days
            enriched["ease_factor"] = st.ease_factor
            enriched["last_confidence"] = st.last_confidence
            enriched["next_review_ts"] = st.next_review_ts

            topic_low = str(item.get("topic") or "").lower() in weak_set
            if st.learning_state == ReviewLearningState.LAPSED.value or st.consecutive_failures > 0:
                lapsed.append(enriched)
            elif st.next_review_ts <= ts:
                due.append(enriched)
            elif st.last_confidence <= 2 or topic_low:
                low_conf.append(enriched)

        # Priorizar lapsos > devidos (mais atrasados/tópicos fracos primeiro) > baixa confiança > novos limitados
        due.sort(key=lambda x: x.get("next_review_ts", 0.0))
        lapsed.sort(key=lambda x: x.get("next_review_ts", 0.0))
        low_conf.sort(key=lambda x: (x.get("last_confidence", 3), x.get("next_review_ts", 0.0)))

        cap_review = max(1, int(daily_review_limit))
        lapsed_capped = lapsed[:cap_review]
        rem_rev = max(0, cap_review - len(lapsed_capped))
        due_capped = due[:rem_rev]
        rem_rev = max(0, rem_rev - len(due_capped))
        low_conf_capped = low_conf[:rem_rev]

        new_capped = new_items[: max(0, int(daily_new_limit))]

        return DailyReviewQueue(
            document_id=document_id,
            generated_at=datetime.now().isoformat(),
            daily_new_limit=int(daily_new_limit),
            daily_review_limit=int(daily_review_limit),
            due_items=due_capped,
            lapsed_items=lapsed_capped,
            low_confidence_items=low_conf_capped,
            new_items=new_capped,
            weak_topics=list(weak_topics or []),
            total_queue_count=len(lapsed_capped) + len(due_capped) + len(low_conf_capped) + len(new_capped),
        )


# Alias de tipo para anotações limpas
TupleResult = tuple[ReviewSchedulingState, ReviewHistoryEntry]

