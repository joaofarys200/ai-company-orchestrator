"""
JARVIS OS — Study Engine Phase 6: Dedicated Active Recall Engine
Promove recuperação ativa genuína (sem expor a resposta antes da tentativa),
capta a resposta escrita do estudante, revela a referência fundamentada da fonte,
regista confiança e alimenta a deteção de lacunas + SM-2.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.study_modes.assessment_engine import AssessmentEngine
from services.study_modes.contracts import (
    ActiveRecallAttempt,
    ActiveRecallDeck,
    ActiveRecallPrompt,
    ActiveRecallPromptType,
    AssessmentQuestion,
    ContentDifficulty,
    OpenAnswerVerdict,
    QuestionDifficulty,
    ScoringCriterion,
)
from services.study_modes.grounding import (
    LLMCaller,
    Phase6GroundingHelper,
    compute_source_fingerprints,
    fingerprints_match,
    invoke_phase6_json_llm,
)
from services.study_modes.persistence import StudyModePersistence
from services.study_modes.qa_engine import StudyModeQA, normalized_token_set


class ActiveRecallEngine:
    """Experiência dedicada de Active Recall baseada em objetivos e estrutura editorial."""

    RECALL_FILE = "active_recall.json"

    def __init__(self, persistence: StudyModePersistence) -> None:
        self.persistence = persistence
        self.assessor = AssessmentEngine(persistence)

    def load_deck(self, document_id: str) -> Optional[ActiveRecallDeck]:
        raw = self.persistence.load_json_doc_artifact(document_id, self.RECALL_FILE, None)
        if isinstance(raw, dict) and raw.get("document_id"):
            return ActiveRecallDeck.from_dict(raw)
        return None

    def save_deck(self, deck: ActiveRecallDeck) -> ActiveRecallDeck:
        self.persistence.save_json_doc_artifact(deck.document_id, self.RECALL_FILE, deck.to_dict())
        return deck

    def generate_prompts(
        self,
        grounding: Phase6GroundingHelper,
        *,
        force_regenerate: bool = False,
        target_prompts: int = 8,
        llm_caller: Optional[LLMCaller] = None,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
    ) -> ActiveRecallDeck:
        doc_id = grounding.plan.metadata.document_id or grounding.dossier.document_id
        current_fp = compute_source_fingerprints(grounding.plan, grounding.dossier, grounding.ast)
        existing = self.load_deck(doc_id)

        if (
            not force_regenerate
            and existing is not None
            and fingerprints_match(existing.fingerprints, current_fp)
            and existing.prompts
        ):
            return existing

        prompts: List[ActiveRecallPrompt] = []
        failed_ops: List[Dict[str, Any]] = []
        llm_used = False
        chapters = list(grounding.plan.chapters or [])
        per_chap = max(2, (target_prompts + max(1, len(chapters)) - 1) // max(1, len(chapters)))

        for idx, chapter in enumerate(chapters):
            if on_progress:
                on_progress(
                    "ACTIVE_RECALL",
                    0.15 + 0.65 * ((idx + 1) / max(1, len(chapters))),
                    f"A desenhar prompts de Active Recall para «{chapter.title}»",
                )
            payload = grounding.build_chapter_prompt_payload(chapter)
            system_prompt = (
                "És um especialista em ciência cognitiva e aprendizagem ativa. Cria atividades de Active Recall "
                "em Português Europeu (reconstrução de argumentos, explicação de conceitos sem consulta, passos metodológicos, "
                "relações entre conceitos, significado de resultados, estrutura do capítulo).\n"
                "Devolve APENAS JSON com chave 'prompts': [{\"prompt_text\", \"prompt_type\", "
                "\"question_difficulty\", \"section_id\", \"topic\", \"concept_ids\", "
                "\"optional_outline\": [...], \"key_points_expected\": [...], "
                "\"grounded_reference_answer\", \"evidence_refs\", \"epistemic_status\"}]."
            )
            user_prompt = f"Gera {per_chap} prompts de Active Recall fundamentados:\n{payload}"

            def _validate(obj: Dict[str, Any]) -> Tuple[bool, str]:
                arr = obj.get("prompts")
                if not isinstance(arr, list) or not arr:
                    return False, "Lista 'prompts' ausente ou vazia."
                for i, p in enumerate(arr):
                    if not isinstance(p, dict) or not str(p.get("prompt_text", "")).strip() or not str(p.get("grounded_reference_answer", "")).strip():
                        return False, f"Prompt {i} incompleto."
                return True, "OK"

            parsed, meta = invoke_phase6_json_llm(
                llm_caller=llm_caller,
                operation=f"phase6_recall_{chapter.chapter_id}",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                document_id=doc_id,
                validator=_validate,
            )
            if parsed and isinstance(parsed.get("prompts"), list):
                llm_used = True
                prompts.extend(self._parse_llm_prompts(parsed["prompts"], grounding=grounding, chapter=chapter))
            else:
                failed_ops.append({
                    "operation": f"phase6_recall_{chapter.chapter_id}",
                    "error": meta.get("error", "LLM indisponível; gerados prompts determinísticos."),
                    "timestamp": datetime.now().isoformat(),
                })
                prompts.extend(self._build_deterministic_prompts(grounding=grounding, chapter=chapter, limit=per_chap))

        valid_prompts = StudyModeQA(grounding=grounding).validate_recall_prompts(prompts)[: max(target_prompts, 4)]
        deck = ActiveRecallDeck(
            document_id=doc_id,
            prompts=valid_prompts,
            fingerprints=current_fp,
            generation_mode="LLM_GROUNDED" if llm_used and not failed_ops else ("PARTIAL_FALLBACK" if llm_used else "DETERMINISTIC_GROUNDED"),
            status="COMPLETED" if valid_prompts else "PARTIAL",
            failed_operations=failed_ops,
        )
        return self.save_deck(deck)

    def _parse_llm_prompts(
        self,
        raw_prompts: List[Dict[str, Any]],
        *,
        grounding: Phase6GroundingHelper,
        chapter: Any,
    ) -> List[ActiveRecallPrompt]:
        doc_id = grounding.plan.metadata.document_id or grounding.dossier.document_id
        secs_by_id = {s.section_id: s for s in (chapter.sections or [])}
        default_sec = chapter.sections[0] if chapter.sections else None
        out: List[ActiveRecallPrompt] = []

        valid_types = {t.value for t in ActiveRecallPromptType}
        for rp in raw_prompts:
            ptxt = str(rp.get("prompt_text") or "").strip()
            ref_ans = str(rp.get("grounded_reference_answer") or "").strip()
            ptype = str(rp.get("prompt_type") or ActiveRecallPromptType.CONCEPT_EXPLANATION.value).upper()
            if ptype not in valid_types:
                ptype = ActiveRecallPromptType.CONCEPT_EXPLANATION.value

            sec = secs_by_id.get(str(rp.get("section_id") or "").strip(), default_sec)
            orig_sids = list(getattr(sec, "original_section_ids", []) or []) if sec else []
            obj_id, obj_txt = grounding.pick_objective_for_section(chapter, sec) if sec else ("", chapter.pedagogical_objective)

            cids = [str(c).strip() for c in (rp.get("concept_ids") or []) if str(c).strip() in grounding.concepts_by_id]
            if not cids and sec:
                cids = [c for c in (sec.associated_concept_ids or []) if c in grounding.concepts_by_id][:3]

            valid_refs, pages, ep_st, _ = grounding.validate_and_ground_refs(
                rp.get("evidence_refs"),
                allowed_section_ids=orig_sids,
                candidate_text=ref_ans,
                requested_status=str(rp.get("epistemic_status") or "MODEL_INFERENCE"),
            )
            pid = f"ar_{hashlib.sha1(f'{doc_id}:{chapter.chapter_id}:{ptxt}'.encode('utf-8')).hexdigest()[:10]}"
            out.append(
                ActiveRecallPrompt(
                    prompt_id=pid,
                    document_id=doc_id,
                    prompt_text=ptxt,
                    prompt_type=ptype,
                    content_difficulty=ContentDifficulty.INTERMEDIATE.value,
                    question_difficulty=str(rp.get("question_difficulty") or QuestionDifficulty.MEDIUM.value).upper(),
                    chapter_id=chapter.chapter_id,
                    chapter_title=chapter.title,
                    section_id=sec.section_id if sec else "",
                    section_title=sec.title if sec else "",
                    topic=str(rp.get("topic") or (sec.title if sec else chapter.title)),
                    learning_objective_id=obj_id,
                    learning_objective_text=obj_txt,
                    concept_ids=cids,
                    optional_outline=[str(x).strip() for x in (rp.get("optional_outline") or []) if str(x).strip()],
                    key_points_expected=[str(x).strip() for x in (rp.get("key_points_expected") or []) if str(x).strip()],
                    grounded_reference_answer=ref_ans,
                    evidence_refs=valid_refs,
                    source_pages=pages,
                    epistemic_status=ep_st,
                    generation_mode="LLM_GROUNDED",
                )
            )
        return out

    def _build_deterministic_prompts(
        self,
        *,
        grounding: Phase6GroundingHelper,
        chapter: Any,
        limit: int,
    ) -> List[ActiveRecallPrompt]:
        doc_id = grounding.plan.metadata.document_id or grounding.dossier.document_id
        default_sec = chapter.sections[0] if chapter.sections else None
        out: List[ActiveRecallPrompt] = []

        for sec in (chapter.sections or []):
            if len(out) >= limit:
                break
            refs, _, pages = grounding.resolve_section_evidence_pool(sec)
            orig_sids = list(getattr(sec, "original_section_ids", []) or [])
            analyses = [grounding.sections_by_id[s] for s in orig_sids if s in grounding.sections_by_id]
            synthesis_texts = [sa.in_depth_synthesis.strip() for sa in analyses if getattr(sa, "in_depth_synthesis", "").strip()]
            core_ideas = [str(i).strip() for sa in analyses for i in (getattr(sa, "core_ideas", []) or []) if str(i).strip()]
            cnames = [grounding.concepts_by_id[cid].name for cid in (sec.associated_concept_ids or []) if cid in grounding.concepts_by_id]
            obj_id, obj_txt = grounding.pick_objective_for_section(chapter, sec)

            ref_answer = " ".join(synthesis_texts) or " ".join(core_ideas) or sec.pedagogical_objective
            if len(ref_answer.strip()) < 15:
                continue

            outline = [f"Definir contexto de «{sec.title}»"] + ([f"Explicar conceitos: {', '.join(cnames[:3])}"] if cnames else []) + ["Sintetizar implicações ou limitações"]
            key_pts = core_ideas[:4] or cnames[:4] or [sec.pedagogical_objective]
            prompt_txt = (
                f"Sem consultar o documento, reconstrói os argumentos principais e o objetivo de «{sec.title}»"
                + (f", articulando {', '.join(cnames[:3])}." if cnames else ".")
            )
            pid = f"ar_{hashlib.sha1(f'{doc_id}:{sec.section_id}'.encode('utf-8')).hexdigest()[:10]}"
            out.append(
                ActiveRecallPrompt(
                    prompt_id=pid,
                    document_id=doc_id,
                    prompt_text=prompt_txt,
                    prompt_type=ActiveRecallPromptType.ARGUMENT_RECONSTRUCTION.value,
                    content_difficulty=ContentDifficulty.INTERMEDIATE.value,
                    question_difficulty=QuestionDifficulty.MEDIUM.value,
                    chapter_id=chapter.chapter_id,
                    chapter_title=chapter.title,
                    section_id=sec.section_id,
                    section_title=sec.title,
                    topic=sec.title,
                    learning_objective_id=obj_id,
                    learning_objective_text=obj_txt,
                    concept_ids=[c for c in (sec.associated_concept_ids or []) if c in grounding.concepts_by_id],
                    optional_outline=outline,
                    key_points_expected=key_pts,
                    grounded_reference_answer=ref_answer.strip(),
                    evidence_refs=refs[:5],
                    source_pages=pages,
                    epistemic_status="MODEL_INFERENCE",
                    generation_mode="DETERMINISTIC_GROUNDED",
                )
            )

        # Prompt de estrutura metodológica quando aplicável
        meth = getattr(grounding.dossier, "methodology_analysis", None)
        if meth and getattr(meth, "is_applicable", False) and (meth.methodological_design or meth.procedures) and len(out) < limit:
            ref_txt = f"{meth.methodological_design}. Procedimentos: {', '.join(meth.procedures[:5] or meth.methods_used[:5])}."
            refs, pages, ep_st, _ = grounding.validate_and_ground_refs(
                [r.__dict__ for r in (meth.evidence_refs or [])],
                allowed_section_ids=getattr(default_sec, "original_section_ids", None) if default_sec else None,
                candidate_text=ref_txt,
                requested_status="SOURCE_FACT",
            )
            pid = f"ar_{hashlib.sha1(f'{doc_id}:meth:{chapter.chapter_id}'.encode('utf-8')).hexdigest()[:10]}"
            out.append(
                ActiveRecallPrompt(
                    prompt_id=pid,
                    document_id=doc_id,
                    prompt_text="Descreve de memória os passos do desenho metodológico, amostra e técnicas de análise utilizados neste estudo.",
                    prompt_type=ActiveRecallPromptType.METHODOLOGY_STEPS.value,
                    content_difficulty=ContentDifficulty.ADVANCED.value,
                    question_difficulty=QuestionDifficulty.HARD.value,
                    chapter_id=chapter.chapter_id,
                    chapter_title=chapter.title,
                    section_id=default_sec.section_id if default_sec else "",
                    section_title="Metodologia",
                    topic="Metodologia",
                    optional_outline=["Tipo de investigação e desenho", "Amostra / fontes de dados", "Técnicas analíticas e limitações"],
                    key_points_expected=list(meth.methods_used or meth.analysis_techniques or ["desenho metodológico"])[:5],
                    grounded_reference_answer=ref_txt,
                    evidence_refs=refs[:4],
                    source_pages=pages,
                    epistemic_status=ep_st,
                    generation_mode="DETERMINISTIC_GROUNDED",
                )
            )
        return out

    @staticmethod
    def serialize_for_student(prompt: ActiveRecallPrompt, *, reveal_answer: bool = False) -> Dict[str, Any]:
        """Devolve payload sem expor a resposta esperada antes de o estudante tentar responder."""
        d = prompt.to_dict()
        if not reveal_answer:
            d["grounded_reference_answer"] = ""
            d["key_points_expected"] = []
            d["answer_hidden"] = True
        else:
            d["answer_hidden"] = False
        return d

    def submit_attempt(
        self,
        prompt: ActiveRecallPrompt,
        *,
        student_response: str,
        self_confidence: int = 3,
        outline_used: bool = False,
        use_llm: bool = False,
        llm_caller: Optional[LLMCaller] = None,
    ) -> ActiveRecallAttempt:
        resp_clean = (student_response or "").strip()
        if not resp_clean:
            raise ValueError("Submete a tua resposta de recuperação antes de revelar a referência.")

        conf = max(1, min(5, int(self_confidence)))
        synthetic_q = AssessmentQuestion(
            question_id=prompt.prompt_id,
            document_id=prompt.document_id,
            question_text=prompt.prompt_text,
            correct_answer=prompt.grounded_reference_answer,
            epistemic_status=prompt.epistemic_status,
            scoring_criteria=[
                ScoringCriterion(
                    criterion_id="ar_crit_1",
                    description="Cobertura dos pontos-chave esperados da unidade.",
                    required_concepts=list(prompt.key_points_expected[:5]),
                    factual_anchors=list(normalized_token_set(prompt.grounded_reference_answer))[:6],
                )
            ],
        )
        ev = self.assessor.evaluate_open_answer(
            question=synthetic_q,
            student_answer=resp_clean,
            use_llm=use_llm,
            llm_caller=llm_caller,
        )

        if ev.score_ratio >= 0.72 and ev.verdict == OpenAnswerVerdict.CORRECT.value:
            self_rating = "RECALLED"
        elif ev.score_ratio >= 0.35:
            self_rating = "PARTIAL"
        else:
            self_rating = "MISSED"

        return ActiveRecallAttempt(
            attempt_id=f"aratt_{uuid.uuid4().hex[:10]}",
            prompt_id=prompt.prompt_id,
            document_id=prompt.document_id,
            student_response=resp_clean,
            self_confidence=conf,
            self_rating=self_rating,
            outline_used=bool(outline_used),
            evaluation=ev,
            score_ratio=ev.score_ratio,
            revealed_reference=prompt.grounded_reference_answer,
            evidence_refs=list(prompt.evidence_refs),
        )

