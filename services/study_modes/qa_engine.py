"""
JARVIS OS — Study Engine Phase 6: Deterministic Quality Assurance (StudyModeQA)
Valida unicidade, não-circularidade, qualidade de distratores em escolha múltipla,
rubricas de avaliação aberta, validade de referências e fidelidade epistémica.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from services.study_document_generation.contracts import VALID_EPISTEMIC_STATUSES
from services.study_modes.contracts import (
    ActiveRecallPrompt,
    AdaptiveFlashcard,
    AssessmentQuestion,
    CornellNoteEntry,
    QuestionType,
    StudyModeQAFinding,
    StudyModeQAReport,
)
from services.study_modes.grounding import Phase6GroundingHelper


def normalized_token_set(text: str) -> Set[str]:
    return {
        tok
        for tok in re.findall(r"[0-9a-zà-öø-ÿ]{3,}", (text or "").lower())
        if tok not in {
            "para", "como", "sobre", "entre", "com", "uma", "dos", "das", "nos",
            "nas", "que", "qual", "quais", "the", "and", "for", "with", "that", "this",
        }
    }


def jaccard_similarity(text_a: str, text_b: str) -> float:
    a = normalized_token_set(text_a)
    b = normalized_token_set(text_b)
    if not a or not b:
        return 0.0
    return len(a & b) / float(len(a | b))


class StudyModeQA:
    """Auditoria determinística dos artefactos pedagógicos da Fase 6."""

    def __init__(self, grounding: Optional[Phase6GroundingHelper] = None) -> None:
        self.grounding = grounding

    def validate_flashcards(
        self,
        cards: Sequence[AdaptiveFlashcard],
    ) -> Tuple[List[AdaptiveFlashcard], StudyModeQAReport]:
        accepted: List[AdaptiveFlashcard] = []
        findings: List[StudyModeQAFinding] = []
        seen_ids: Set[str] = set()
        duplicates = 0
        rejected = 0

        for card in cards:
            cid = str(card.card_id or "").strip()
            front = str(card.front or "").strip()
            back = str(card.back or "").strip()

            if not cid or cid in seen_ids:
                rejected += 1
                findings.append(StudyModeQAFinding("DUPLICATE_OR_EMPTY_ID", "BLOCKING", "Cartão sem ID ou com ID duplicado.", cid))
                continue
            seen_ids.add(cid)

            if len(front) < 8 or len(back) < 8:
                rejected += 1
                findings.append(StudyModeQAFinding("INSUFFICIENT_CARD_CONTENT", "BLOCKING", "Frente ou verso demasiado curtos.", cid))
                continue

            if jaccard_similarity(front, back) > 0.88 and len(back.split()) <= len(front.split()) + 2:
                rejected += 1
                findings.append(StudyModeQAFinding("CIRCULAR_ANSWER", "BLOCKING", "Resposta apenas repete a pergunta.", cid))
                continue

            if card.epistemic_status not in VALID_EPISTEMIC_STATUSES:
                rejected += 1
                findings.append(StudyModeQAFinding("INVALID_EPISTEMIC_STATUS", "BLOCKING", f"Estado epistémico inválido: {card.epistemic_status}", cid))
                continue

            # Factual SOURCE_FACT precisa de evidência rastreável (quando grounding está ativo)
            if self.grounding is not None:
                if card.epistemic_status in ("NOT_FOUND", "UNVERIFIED") and card.card_type != "APPLICATION":
                    rejected += 1
                    findings.append(StudyModeQAFinding("UNVERIFIED_CARD_CONTENT", "BLOCKING", "Cartão factual não pode assentar em NOT_FOUND/UNVERIFIED.", cid))
                    continue
                if not card.evidence_refs:
                    rejected += 1
                    findings.append(StudyModeQAFinding("MISSING_EVIDENCE_REF", "BLOCKING", "Cartão sem referência de evidência rastreável.", cid))
                    continue
                if card.epistemic_status == "SOURCE_FACT" and not any(
                    r.paragraph_id or r.page_number for r in card.evidence_refs
                ):
                    findings.append(StudyModeQAFinding("WEAK_FACT_ANCHOR", "WARNING", "Facto rebaixado para MODEL_INFERENCE por falta de âncora página/parágrafo.", cid))
                    card.epistemic_status = "MODEL_INFERENCE"

            # Detetar quase-duplicados face a cartões já aceites
            is_near_dup = any(
                jaccard_similarity(front, existing.front) >= 0.82
                for existing in accepted
                if not existing.is_deleted
            )
            if is_near_dup:
                duplicates += 1
                rejected += 1
                findings.append(StudyModeQAFinding("NEAR_DUPLICATE_CARD", "WARNING", f"Cartão redundante suprimido: {front[:60]}", cid))
                continue

            accepted.append(card)

        report = StudyModeQAReport(
            is_valid=not any(f.severity == "BLOCKING" for f in findings if f.item_id in {c.card_id for c in accepted}),
            items_checked=len(cards),
            items_accepted=len(accepted),
            items_rejected=rejected,
            duplicates_removed=duplicates,
            findings=findings,
        )
        return accepted, report

    def validate_questions(
        self,
        questions: Sequence[AssessmentQuestion],
    ) -> Tuple[List[AssessmentQuestion], StudyModeQAReport]:
        accepted: List[AssessmentQuestion] = []
        findings: List[StudyModeQAFinding] = []
        seen_ids: Set[str] = set()
        duplicates = 0
        rejected = 0

        for q in questions:
            qid = str(q.question_id or "").strip()
            stem = str(q.question_text or "").strip()
            if not qid or qid in seen_ids or len(stem) < 10:
                rejected += 1
                findings.append(StudyModeQAFinding("INVALID_QUESTION_ID_OR_STEM", "BLOCKING", "Questão com ID inválido/duplicado ou enunciado vazio.", qid))
                continue
            seen_ids.add(qid)

            if q.epistemic_status in ("NOT_FOUND", "UNVERIFIED"):
                rejected += 1
                findings.append(StudyModeQAFinding("EPISTEMIC_DISQUALIFICATION", "BLOCKING", "Não criar perguntas a partir de conteúdo NOT_FOUND ou UNVERIFIED.", qid))
                continue

            if self.grounding is not None and not q.evidence_refs:
                rejected += 1
                findings.append(StudyModeQAFinding("MISSING_QUESTION_EVIDENCE", "BLOCKING", "Questão sem prova documental associada.", qid))
                continue

            if q.question_type == QuestionType.MULTIPLE_CHOICE.value:
                ok_mc, mc_err = self._validate_mc_question(q)
                if not ok_mc:
                    rejected += 1
                    findings.append(StudyModeQAFinding("INVALID_MULTIPLE_CHOICE", "BLOCKING", mc_err, qid))
                    continue
            elif q.question_type == QuestionType.TRUE_FALSE.value:
                ok_tf, tf_err = self._validate_tf_question(q)
                if not ok_tf:
                    rejected += 1
                    findings.append(StudyModeQAFinding("INVALID_TRUE_FALSE", "BLOCKING", tf_err, qid))
                    continue
            else:
                if not q.correct_answer.strip() or not q.scoring_criteria:
                    rejected += 1
                    findings.append(StudyModeQAFinding("MISSING_OPEN_ANSWER_RUBRIC", "BLOCKING", "Questão aberta sem resposta esperada nem critérios explícitos de avaliação.", qid))
                    continue

            if any(jaccard_similarity(stem, ex.question_text) >= 0.85 for ex in accepted):
                duplicates += 1
                rejected += 1
                findings.append(StudyModeQAFinding("DUPLICATE_QUESTION", "WARNING", f"Pergunta repetida ignorada: {stem[:60]}", qid))
                continue

            accepted.append(q)

        return accepted, StudyModeQAReport(
            is_valid=len(accepted) > 0,
            items_checked=len(questions),
            items_accepted=len(accepted),
            items_rejected=rejected,
            duplicates_removed=duplicates,
            findings=findings,
        )

    def _validate_mc_question(self, q: AssessmentQuestion) -> Tuple[bool, str]:
        opts = [str(o).strip() for o in (q.options or []) if str(o).strip()]
        if len(opts) < 3 or len(opts) > 5:
            return False, f"Escolha múltipla requer 3 a 5 opções válidas (recebidas {len(opts)})."
        if len({o.lower() for o in opts}) != len(opts):
            return False, "Opções de escolha múltipla duplicadas."
        if q.correct_index is None or not (0 <= q.correct_index < len(opts)):
            return False, f"correct_index fora dos limites ({q.correct_index})."

        correct_opt = opts[q.correct_index]
        distractors = [o for idx, o in enumerate(opts) if idx != q.correct_index]
        for d in distractors:
            if "todas as anteriores" in d.lower() or "nenhuma das anteriores" in d.lower():
                return False, "Distrator genérico trivial proibido ('todas/nenhuma das anteriores')."

        # Evitar pista óbvia por discrepância extrema de comprimento
        med_dist_len = sorted(len(d) for d in distractors)[len(distractors) // 2]
        if med_dist_len > 0 and len(correct_opt) > max(120, med_dist_len * 3.2):
            return False, "Resposta correta desproporcionalmente longa face aos distratores (pista de formato)."

        q.correct_answer = correct_opt
        return True, "OK"

    def _validate_tf_question(self, q: AssessmentQuestion) -> Tuple[bool, str]:
        lower = q.question_text.lower()
        if "não é incorreto" in lower or "exceto não" in lower:
            return False, "Dupla negação torna afirmação Verdadeiro/Falso ambígua."
        opts = [str(o).strip() for o in (q.options or []) if str(o).strip()]
        if len(opts) != 2:
            q.options = ["Verdadeiro", "Falso"]
        if q.correct_index not in (0, 1):
            ans = q.correct_answer.strip().lower()
            if ans in ("verdadeiro", "true", "v", "1"):
                q.correct_index = 0
            elif ans in ("falso", "false", "f", "0"):
                q.correct_index = 1
            else:
                return False, "Questão Verdadeiro/Falso sem resposta booleana clara."
        q.correct_answer = q.options[q.correct_index]
        return True, "OK"

    def validate_cornell_entry(self, entry: CornellNoteEntry) -> Tuple[bool, str]:
        if not entry.sufficient_evidence:
            return True, "INSUFFICIENT_SOURCE_HONEST"
        has_notes = bool(entry.main_concepts or entry.explanations or entry.supporting_details)
        has_cues = bool(entry.cue_column)
        has_sum = len(entry.summary_section.strip()) >= 15
        if not (has_notes and has_cues and has_sum):
            return False, "Nota Cornell incompleta (faltam notas, cues ou síntese)."
        return True, "OK"

    def validate_recall_prompts(self, prompts: Sequence[ActiveRecallPrompt]) -> List[ActiveRecallPrompt]:
        out: List[ActiveRecallPrompt] = []
        seen: Set[str] = set()
        for p in prompts:
            if not p.prompt_id or p.prompt_id in seen:
                continue
            if len(p.prompt_text.strip()) < 10 or len(p.grounded_reference_answer.strip()) < 15:
                continue
            if p.epistemic_status in ("NOT_FOUND", "UNVERIFIED"):
                continue
            if any(jaccard_similarity(p.prompt_text, ex.prompt_text) >= 0.85 for ex in out):
                continue
            seen.add(p.prompt_id)
            out.append(p)
        return out

