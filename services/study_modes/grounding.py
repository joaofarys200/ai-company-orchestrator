"""
JARVIS OS — Study Engine Phase 6: Epistemic Grounding & Source Verification
Reutiliza ReferenceAndProvenanceRenderer (Fase 5) e os artefactos canónicos das Fases 2–4
para validar referências, bloquear invenções e preservar classificações epistémicas.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ConceptItem,
    ContextBudgetManager,
    EpistemicStatus,
    EvidenceRef,
    clean_qwen_json,
)
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import (
    EditorialChapter,
    EditorialSection,
    EditorialStudyPlan,
    compute_dossier_fingerprint,
)
from services.study_ai_engine import invoke_study_llm_observable
from services.study_document_generation.contracts import (
    compute_ast_fingerprint,
    compute_plan_fingerprint,
    normalize_epistemic_status,
)
from services.study_document_generation.provenance_renderer import ReferenceAndProvenanceRenderer
from services.study_modes.contracts import (
    ContentDifficulty,
    PROMPT_VERSIONS_PHASE6,
    SourceFingerprintSnapshot,
    SourceLocation,
)


LLMCaller = Callable[..., Tuple[Optional[Any], Dict[str, Any]] | Dict[str, Any]]


class StudyModeCancelledError(RuntimeError):
    """Raised when a Phase 6 generation operation is cancelled cooperatively."""


def compute_source_fingerprints(
    plan: EditorialStudyPlan,
    dossier: AcademicReasoningDossier,
    ast: Optional[AcademicDocumentAST],
    *,
    model_name: str = "qwen3.5:9b",
) -> SourceFingerprintSnapshot:
    return SourceFingerprintSnapshot(
        document_id=plan.metadata.document_id or dossier.document_id,
        ast_fingerprint=compute_ast_fingerprint(ast) if ast is not None else "AST_ABSENT",
        dossier_fingerprint=compute_dossier_fingerprint(dossier),
        plan_fingerprint=compute_plan_fingerprint(plan),
        plan_version=int(getattr(plan.metadata, "plan_version", 1) or 1),
        model_name=model_name,
        prompt_versions=dict(PROMPT_VERSIONS_PHASE6),
    )


def fingerprints_match(
    saved: Optional[SourceFingerprintSnapshot],
    current: SourceFingerprintSnapshot,
) -> bool:
    """Verifica validade de cache exigindo correspondência integral de AST, Dossier e Plano."""
    if saved is None:
        return False
    return (
        saved.plan_fingerprint == current.plan_fingerprint
        and saved.dossier_fingerprint == current.dossier_fingerprint
        and saved.ast_fingerprint == current.ast_fingerprint
    )


def map_depth_to_content_difficulty(depth_level: str, role: str = "") -> str:
    d = str(depth_level or "").upper()
    r = str(role or "").upper()
    if d == "FOUNDATIONAL" or r == "PREREQUISITE":
        return ContentDifficulty.FOUNDATIONAL.value
    if d == "IN_DEPTH" or r in ("SYNTHESIS",):
        return ContentDifficulty.ADVANCED.value
    return ContentDifficulty.INTERMEDIATE.value


class Phase6GroundingHelper:
    """
    Encapsula a validação de evidências, rastreabilidade de parágrafos/páginas/conceitos
    e preparação de contexto delimitado para o LLM local (qwen3.5:9b).
    """

    def __init__(
        self,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST] = None,
        developed_content: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.plan = plan
        self.dossier = dossier
        self.ast = ast
        self.developed_content = developed_content or {}
        self.provenance = ReferenceAndProvenanceRenderer(dossier, ast=ast)
        self.budget_manager = ContextBudgetManager()

        self.concepts_by_id: Dict[str, ConceptItem] = {
            c.concept_id: c for c in (dossier.conceptual_analysis or []) if getattr(c, "concept_id", "")
        }
        self.sections_by_id: Dict[str, Any] = {
            sa.section_id: sa for sa in (dossier.section_analyses or []) if getattr(sa, "section_id", "")
        }
        self.objectives_by_id: Dict[str, Dict[str, Any]] = {}
        for obj in (getattr(plan.overview, "learning_objectives", None) or []):
            if isinstance(obj, dict) and obj.get("objective_id"):
                self.objectives_by_id[str(obj["objective_id"])] = obj
        self.dev_sections_by_id: Dict[str, Dict[str, Any]] = {}
        for ch in self.developed_content.get("chapters", []) or []:
            if isinstance(ch, dict):
                for sec in ch.get("sections", []) or []:
                    if isinstance(sec, dict) and sec.get("section_id"):
                        self.dev_sections_by_id[str(sec["section_id"])] = sec

    def validate_and_ground_refs(
        self,
        raw_refs: Any,
        *,
        allowed_section_ids: Optional[Sequence[str]] = None,
        candidate_text: str = "",
        requested_status: str = "MODEL_INFERENCE",
        is_hypothetical: bool = False,
    ) -> Tuple[List[EvidenceRef], List[int], str, List[str]]:
        """
        Valida referências enviadas pelo LLM ou construídas a partir da fonte.
        Nunca inventa referências para factos e nunca promove NOT_FOUND/UNVERIFIED.
        Devolve: (valid_refs, valid_pages, resolved_epistemic_status, rejection_notes)
        """
        rejections: List[str] = []
        parsed_refs: List[EvidenceRef] = []

        if isinstance(raw_refs, list):
            for item in raw_refs:
                if isinstance(item, EvidenceRef):
                    parsed_refs.append(item)
                elif isinstance(item, dict):
                    pid = str(item.get("paragraph_id") or "").strip() or None
                    sid = str(item.get("section_id") or "").strip()
                    pg_raw = item.get("page_number")
                    pg = int(pg_raw) if isinstance(pg_raw, (int, float)) and int(pg_raw) > 0 else None
                    # Só inferir secção a partir do próprio parágrafo validado no documento
                    if not sid and pid and pid in self.provenance.para_to_section:
                        sid = self.provenance.para_to_section[pid]
                    parsed_refs.append(
                        EvidenceRef(
                            section_id=sid,
                            paragraph_id=pid,
                            page_number=pg,
                            excerpt=str(item.get("excerpt") or "")[:200],
                            status=normalize_epistemic_status(item.get("status"), default="MODEL_INFERENCE"),
                        )
                    )

        valid_refs, rej_pids, rej_pgs, rej_sids = self.provenance.validate_evidence_refs(
            parsed_refs,
            allow_section_fallback=False,
            default_status="MODEL_INFERENCE",
        )
        if rej_pids:
            rejections.append(f"REJECTED_UNKNOWN_PARAGRAPHS:{rej_pids}")
        if rej_pgs:
            rejections.append(f"REJECTED_INVALID_PAGES:{rej_pgs}")
        if rej_sids:
            rejections.append(f"REJECTED_UNKNOWN_SECTIONS:{rej_sids}")

        # Garantir fallback apenas se estivermos a ligar à própria secção editorial real
        # (sem promover para SOURCE_FACT!).
        if not valid_refs and allowed_section_ids:
            for sid in allowed_section_ids:
                s_clean = str(sid).strip()
                if s_clean in self.provenance.valid_sections:
                    pages = self.provenance.sec_to_pages.get(s_clean, [])
                    valid_refs.append(
                        EvidenceRef(
                            section_id=s_clean,
                            paragraph_id=None,
                            page_number=pages[0] if pages else None,
                            excerpt="",
                            status=EpistemicStatus.MODEL_INFERENCE.value,
                        )
                    )
                    break

        norm_req = normalize_epistemic_status(requested_status, default=EpistemicStatus.MODEL_INFERENCE.value)
        if is_hypothetical:
            resolved_status = EpistemicStatus.MODEL_INFERENCE.value
        elif norm_req in (EpistemicStatus.NOT_FOUND.value, EpistemicStatus.UNVERIFIED.value):
            resolved_status = norm_req
        elif norm_req == EpistemicStatus.SOURCE_FACT.value:
            has_concrete_anchor = any(r.paragraph_id or r.page_number for r in valid_refs)
            overlap_ok = (
                self.provenance.has_minimal_source_overlap(candidate_text, valid_refs)
                if candidate_text and valid_refs
                else False
            )
            if valid_refs and has_concrete_anchor and overlap_ok and not rejections:
                resolved_status = EpistemicStatus.SOURCE_FACT.value
            elif valid_refs:
                resolved_status = EpistemicStatus.MODEL_INFERENCE.value
            else:
                resolved_status = EpistemicStatus.UNVERIFIED.value
        else:
            resolved_status = EpistemicStatus.MODEL_INFERENCE.value if valid_refs else EpistemicStatus.UNVERIFIED.value

        pages = sorted({int(r.page_number) for r in valid_refs if r.page_number and int(r.page_number) > 0})
        return valid_refs, pages, resolved_status, rejections

    def resolve_section_evidence_pool(self, sec: EditorialSection) -> Tuple[List[EvidenceRef], List[str], List[int]]:
        """Extrai todas as evidências fidedignas disponíveis para uma secção editorial."""
        pool: List[EvidenceRef] = []
        pool.extend(getattr(sec, "evidence_refs", []) or [])
        for orig_sid in getattr(sec, "original_section_ids", []) or []:
            sa = self.sections_by_id.get(orig_sid)
            if sa is not None:
                pool.extend(getattr(sa, "source_refs", []) or [])
        for cid in getattr(sec, "associated_concept_ids", []) or []:
            c = self.concepts_by_id.get(cid)
            if c is not None:
                pool.extend(getattr(c, "evidence_refs", []) or [])

        valid_refs, _, _, _ = self.provenance.validate_evidence_refs(
            pool,
            fallback_section_ids=getattr(sec, "original_section_ids", None),
            allow_section_fallback=True,
            default_status="SOURCE_FACT",
        )
        # Nunca propagar NOT_FOUND/UNVERIFIED como prova factual no pool
        grounded = [
            r for r in valid_refs
            if r.status not in (EpistemicStatus.NOT_FOUND.value, EpistemicStatus.UNVERIFIED.value)
        ]
        pids = list(dict.fromkeys([r.paragraph_id for r in grounded if r.paragraph_id]))
        pages = sorted({int(r.page_number) for r in grounded if r.page_number and int(r.page_number) > 0})
        return grounded, pids, pages

    def pick_objective_for_section(self, chapter: EditorialChapter, sec: EditorialSection) -> Tuple[str, str]:
        """Seleciona o objetivo de aprendizagem editorial mais alinhado à secção."""
        orig_set = set(getattr(sec, "original_section_ids", []) or [])
        for obj_id, obj in self.objectives_by_id.items():
            src_sids = set(str(x) for x in (obj.get("source_section_ids") or []))
            if orig_set and (orig_set & src_sids):
                return obj_id, str(obj.get("description") or "")
        if self.objectives_by_id:
            first_id, first_obj = next(iter(self.objectives_by_id.items()))
            return first_id, str(first_obj.get("description") or sec.pedagogical_objective or chapter.pedagogical_objective)
        return "", str(sec.pedagogical_objective or chapter.pedagogical_objective or "")

    def build_chapter_prompt_payload(self, chapter: EditorialChapter, *, max_chars: int = 14000) -> Dict[str, Any]:
        """Constrói payload compacto e fiel das evidências do capítulo respeitando limites de contexto."""
        secs_payload: List[Dict[str, Any]] = []
        concept_ids_seen: List[str] = list(getattr(chapter, "key_concept_ids", []) or [])

        for sec in chapter.sections or []:
            grounded_refs, pids, pages = self.resolve_section_evidence_pool(sec)
            orig_analyses: List[Dict[str, Any]] = []
            for osid in getattr(sec, "original_section_ids", []) or []:
                sa = self.sections_by_id.get(osid)
                if sa is not None:
                    # Excluir argumentos marcados NOT_FOUND ou UNVERIFIED da formulação factual
                    safe_args = [
                        arg for arg in (getattr(sa, "arguments", []) or [])
                        if isinstance(arg, dict) and str(arg.get("status", "")).upper() not in ("NOT_FOUND", "UNVERIFIED")
                    ]
                    orig_analyses.append({
                        "original_section_id": sa.section_id,
                        "title": sa.title,
                        "section_type": sa.section_type,
                        "synthesis": str(sa.in_depth_synthesis or "")[:1200],
                        "core_ideas": [str(x)[:280] for x in (sa.core_ideas or [])[:6]],
                        "arguments": safe_args[:6],
                        "limitations": [str(x)[:220] for x in (sa.limitations or [])[:4]],
                    })

            source_snippets: List[Dict[str, Any]] = []
            for pid in pids[:10]:
                txt = self.provenance.para_texts.get(pid) or self.provenance.verified_source_excerpts.get(pid, "")
                if txt:
                    source_snippets.append({
                        "paragraph_id": pid,
                        "section_id": self.provenance.para_to_section.get(pid, ""),
                        "page_number": self.provenance.para_to_page.get(pid),
                        "text": txt[:420],
                    })

            concept_ids_seen.extend(getattr(sec, "associated_concept_ids", []) or [])
            obj_id, obj_desc = self.pick_objective_for_section(chapter, sec)
            secs_payload.append({
                "editorial_section_id": sec.section_id,
                "title": sec.title,
                "pedagogical_objective": sec.pedagogical_objective,
                "learning_objective_id": obj_id,
                "learning_objective_text": obj_desc,
                "content_role": sec.content_role,
                "original_section_ids": list(getattr(sec, "original_section_ids", []) or []),
                "available_paragraph_ids": pids[:12],
                "available_pages": pages[:12],
                "section_analyses": orig_analyses,
                "source_excerpts": source_snippets,
                "evidence_refs": [
                    {
                        "section_id": r.section_id,
                        "paragraph_id": r.paragraph_id,
                        "page_number": r.page_number,
                        "status": r.status,
                    }
                    for r in grounded_refs[:6]
                ],
            })

        concepts_payload: List[Dict[str, Any]] = []
        for cid in dict.fromkeys(concept_ids_seen):
            c = self.concepts_by_id.get(cid)
            if c is None:
                continue
            c_refs = [
                {
                    "section_id": r.section_id,
                    "paragraph_id": r.paragraph_id,
                    "page_number": r.page_number,
                    "status": r.status,
                }
                for r in self.provenance.sanitize_evidence_refs(c.evidence_refs, allow_section_fallback=False)
            ]
            concepts_payload.append({
                "concept_id": c.concept_id,
                "name": c.name,
                "definition": str(c.definition or "")[:350],
                "explanation": str(c.explanation or "")[:350],
                "evidence_refs": c_refs[:4],
            })

        rels_payload: List[Dict[str, Any]] = []
        c_set = set(dict.fromkeys(concept_ids_seen))
        for rel in getattr(self.plan, "conceptual_relationships", []) or []:
            if rel.source_concept_id in c_set or rel.target_concept_id in c_set:
                rels_payload.append({
                    "source_concept_id": rel.source_concept_id,
                    "source_name": rel.source_concept_name,
                    "target_concept_id": rel.target_concept_id,
                    "target_name": rel.target_concept_name,
                    "relation_type": rel.relation_type,
                    "justification": str(rel.justification or "")[:240],
                    "epistemic_status": normalize_epistemic_status(rel.epistemic_status, default="MODEL_INFERENCE"),
                })

        meth = getattr(self.dossier, "methodology_analysis", None)
        methodology_payload: Optional[Dict[str, Any]] = None
        if meth and getattr(meth, "is_applicable", False):
            methodology_payload = {
                "research_type": meth.research_type,
                "methodological_design": str(meth.methodological_design or "")[:360],
                "methods_used": list(meth.methods_used or [])[:6],
                "sample_or_participants": str(meth.sample_or_participants or "")[:220],
                "analysis_techniques": list(meth.analysis_techniques or [])[:6],
                "methodological_limitations": list(meth.methodological_limitations or [])[:4],
            }

        results_payload = [
            {
                "statement": str(r.statement or "")[:280],
                "evidence_data": str(r.evidence_data or "")[:200],
                "relation_to_objectives": str(r.relation_to_objectives or "")[:200],
                "evidence_refs": [
                    {"section_id": er.section_id, "paragraph_id": er.paragraph_id, "page_number": er.page_number}
                    for er in self.provenance.sanitize_evidence_refs(r.evidence_refs, allow_section_fallback=False)[:3]
                ],
            }
            for r in (getattr(self.dossier, "results_and_evidence", []) or [])[:8]
            if str(r.statement or "").strip()
        ]

        payload = {
            "document_id": self.plan.metadata.document_id,
            "document_title": getattr(self.dossier.document_analysis, "title", "") or self.plan.metadata.document_id,
            "document_nature": getattr(self.plan.overview, "document_nature", ""),
            "chapter_id": chapter.chapter_id,
            "chapter_title": chapter.title,
            "chapter_objective": chapter.pedagogical_objective,
            "sections": secs_payload,
            "concepts": concepts_payload[:14],
            "relationships": rels_payload[:10],
            "methodology": methodology_payload,
            "results": results_payload,
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        if len(serialized) > max_chars:
            # Redução controlada mantendo secções e conceitos principais
            for sp in payload["sections"]:
                sp["source_excerpts"] = sp["source_excerpts"][:2]
                for oa in sp["section_analyses"]:
                    oa["synthesis"] = oa["synthesis"][:500]
            payload["concepts"] = payload["concepts"][:8]
            payload["results"] = payload["results"][:4]
        return payload

    def build_source_location(
        self,
        *,
        chapter_id: str,
        section_id: str,
        orig_section_ids: Sequence[str],
        refs: Sequence[EvidenceRef],
        concept_ids: Sequence[str],
        learning_objective_id: str = "",
        learning_objective_text: str = "",
    ) -> SourceLocation:
        return SourceLocation(
            document_id=self.plan.metadata.document_id or self.dossier.document_id,
            chapter_id=chapter_id,
            section_id=section_id,
            original_section_id=orig_section_ids[0] if orig_section_ids else "",
            paragraph_ids=list(dict.fromkeys([r.paragraph_id for r in refs if r.paragraph_id])),
            page_numbers=sorted({int(r.page_number) for r in refs if r.page_number and int(r.page_number) > 0}),
            concept_ids=list(dict.fromkeys([c for c in concept_ids if c])),
            learning_objective_id=learning_objective_id,
            learning_objective_text=learning_objective_text,
        )


_TERMINAL_LLM_STATUSES = {
    "UNAVAILABLE",
    "TIMEOUT",
    "CANCELLED",
    "SKIPPED_LIVE_LLM_DISABLED",
}


def _coerce_parsed_json_dict(raw_val: Any) -> Optional[Dict[str, Any]]:
    """Extrai um dicionário JSON válido quer de dict direto quer de texto com `<think>`/markdown fences."""
    if isinstance(raw_val, dict):
        return raw_val
    if not isinstance(raw_val, str):
        return None
    cleaned = clean_qwen_json(raw_val)
    if isinstance(cleaned, dict):
        return cleaned
    if isinstance(cleaned, str):
        candidate = json.loads(cleaned)
        if isinstance(candidate, dict):
            return candidate
    return None


def invoke_phase6_json_llm(
    *,
    llm_caller: Optional[LLMCaller],
    operation: str,
    system_prompt: str,
    user_prompt: str,
    document_id: str,
    validator: Callable[[Dict[str, Any]], Tuple[bool, str]],
    max_output_tokens: int = 2400,
    max_retries: int = 2,
    cancellation_check: Optional[Callable[[], bool]] = None,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Executa chamada ao modelo local qwen3.5:9b (ou llm_caller injetado em testes)
    com validação JSON estrita e retries limitados. Nunca recorre a serviços cloud.
    """
    from services.study_ai_engine import is_study_generation_cancelled

    caller = llm_caller
    cur_prompt = user_prompt
    last_err = ""
    total_calls = 0
    prompt_tokens = 0
    completion_tokens = 0
    terminal_status = ""

    def _is_cancelled() -> bool:
        if cancellation_check and cancellation_check():
            return True
        return bool(document_id and is_study_generation_cancelled(document_id)) or is_study_generation_cancelled("global")

    for attempt in range(max_retries + 1):
        if _is_cancelled():
            terminal_status = "CANCELLED"
            last_err = "Geração cancelada pelo utilizador."
            break

        total_calls += 1
        if caller is not None:
            res = caller(
                operation=f"{operation}_try{attempt + 1}",
                system_prompt=system_prompt,
                user_prompt=cur_prompt,
                max_output_tokens=max_output_tokens,
            )
            if isinstance(res, tuple) and len(res) >= 2:
                raw_or_parsed, obs = res[0], res[1] if isinstance(res[1], dict) else {}
                parsed = obs.get("parsed") if isinstance(obs.get("parsed"), dict) else raw_or_parsed
            elif isinstance(res, dict):
                obs = res
                parsed = res.get("parsed")
                if parsed is None and isinstance(res.get("raw_text"), str):
                    parsed = res.get("raw_text")
            else:
                obs = {}
                parsed = res if isinstance(res, str) else None
            prompt_tokens += int(obs.get("prompt_tokens") or obs.get("input_tokens") or 0)
            completion_tokens += int(obs.get("completion_tokens") or obs.get("output_tokens") or 0)
            obs_status = str(obs.get("status") or "").upper()
            if obs_status in _TERMINAL_LLM_STATUSES or obs.get("cancelled") is True:
                terminal_status = obs_status or "CANCELLED"
                last_err = str(obs.get("error") or ", ".join(obs.get("validation_errors") or []) or terminal_status)
                break
            if isinstance(obs, dict) and obs.get("ok") is False:
                last_err = str(obs.get("error") or "Erro reportado pelo invocador LLM.")
                cur_prompt = f"{user_prompt}\n\n[CORREÇÃO TENTATIVA {attempt + 2}]: {last_err}"
                continue
        else:
            raw_text, obs = invoke_study_llm_observable(
                operation=operation,
                system_prompt=system_prompt,
                user_prompt=cur_prompt,
                expect_json=True,
                max_output_tokens=max_output_tokens,
                document_id=document_id,
                cancellation_check=_is_cancelled,
            )
            prompt_tokens += int(obs.get("input_tokens") or obs.get("prompt_tokens") or 0)
            completion_tokens += int(obs.get("output_tokens") or obs.get("completion_tokens") or 0)
            obs_status = str(obs.get("status") or "").upper()
            if obs_status in _TERMINAL_LLM_STATUSES or obs.get("cancelled") is True:
                terminal_status = obs_status or "CANCELLED"
                last_err = str(obs.get("error") or ", ".join(obs.get("validation_errors") or []) or terminal_status)
                break
            parsed = raw_text

        if isinstance(parsed, str):
            try:
                coerced = _coerce_parsed_json_dict(parsed)
                if coerced is None:
                    last_err = "JSON inválido ou objeto não encontrado."
                parsed = coerced
            except Exception as exc:
                last_err = f"JSON inválido: {exc}"
                parsed = None

        if not isinstance(parsed, dict):
            cur_prompt = (
                f"{user_prompt}\n\n[CORREÇÃO OBRIGATÓRIA TENTATIVA {attempt + 2}]: "
                f"Devolve exclusivamente um objeto JSON válido ({last_err or 'objeto não encontrado'})."
            )
            if caller is None and attempt < max_retries:
                time.sleep(min(0.25 * (attempt + 1), 0.75))
            continue

        ok, reason = validator(parsed)
        if ok:
            return parsed, {
                "ok": True,
                "attempts": total_calls,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        last_err = reason
        cur_prompt = (
            f"{user_prompt}\n\n[CORREÇÃO OBRIGATÓRIA TENTATIVA {attempt + 2}]: "
            f"O JSON anterior falhou validação: {reason}."
        )
        if caller is None and attempt < max_retries:
            time.sleep(min(0.25 * (attempt + 1), 0.75))

    return None, {
        "ok": False,
        "status": terminal_status or "FAILED_VALIDATION",
        "cancelled": terminal_status == "CANCELLED",
        "attempts": total_calls,
        "error": last_err or "Falha de geração estruturada com qwen3.5:9b.",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
