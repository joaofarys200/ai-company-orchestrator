"""
JARVIS OS — Study Engine Phase 5: Document Content Generation & Academic Enrichment Engine
(Componentes 5.1 e 5.2)

Gera explicações académicas aprofundadas e enriquecimento pedagógico adaptativo por unidade editorial
(capítulo / secção), respeitando estritamente o orçamento de contexto (ContextBudgetManager),
a validação de identidade 1-para-1 (section_id) e a fidelidade epistémica à fonte original.
"""

from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ContextBudgetManager,
    SectionAnalysis,
    clean_qwen_json,
)
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import (
    EditorialChapter,
    EditorialEvidenceRef,
    EditorialSection,
    EditorialStudyPlan,
)
from services.study_ai_engine import invoke_study_llm_observable
from services.study_document_generation.contracts import (
    ContentBlockType,
    DevelopedChapterContent,
    DevelopedComparisonItem,
    DevelopedConceptDefinition,
    DevelopedContentBlock,
    DevelopedSectionContent,
    DevelopedStudyDocumentContent,
    DocumentGenerationTelemetry,
    ElaborationType,
    VALID_EPISTEMIC_STATUSES,
    compute_plan_fingerprint,
    normalize_epistemic_status,
)
from services.study_document_generation.provenance_renderer import ReferenceAndProvenanceRenderer


DEFAULT_CONTENT_GEN_MAX_OUTPUT_TOKENS = 3000

PROMPT_VERSIONS_PHASE5 = {
    "section_content_development": "v5.1.0-sec-content",
    "chapter_synthesis_enrichment": "v5.1.0-chap-synth",
}


class AcademicContentEnricher:
    """
    Componente 5.2 — Academic Content Enrichment.
    Valida, enriquece e normaliza os blocos de conteúdo académico gerados para uma secção,
    garantindo:
    - Identidade estrita 1-para-1 de `section_id` (sem fallback posicional).
    - Distinção rigorosa entre `SOURCE_FACT`, `MODEL_INFERENCE` e exemplos hipotéticos (`HYPOTHETICAL_EXAMPLE`).
    - Cobertura de todos os pontos obrigatórios (`contents_to_cover`), conceitos e limitações da secção.
    """

    def __init__(self, llm_caller: Any = None) -> None:
        self.llm_caller = llm_caller

    def _validate_section_batch_strict(
        self,
        raw_sections_payload: Any,
        expected_section_ids: Sequence[str],
    ) -> Tuple[bool, str]:
        return self.validate_developed_sections_identity(expected_section_ids, raw_sections_payload)

    @staticmethod
    def validate_developed_sections_identity(
        expected_section_ids: Sequence[str],
        raw_sections_payload: Any,
    ) -> Tuple[bool, str]:
        """
        Validação estrita 1-para-1 de identidade de secções desenvolvidas:
        1. `raw_sections_payload` tem de ser uma lista com a mesma cardinalidade de `expected_section_ids`.
        2. Todos os elementos têm de ser objetos (dict) válidos.
        3. Todos têm de possuir `section_id` não vazio.
        4. Não podem existir identificadores duplicados.
        5. Não podem existir identificadores desconhecidos ou inesperados.
        6. Todos os identificadores esperados têm de estar presentes exatamente uma vez (independente da ordem).
        """
        expected_list = [str(sid).strip() for sid in (expected_section_ids or []) if str(sid).strip()]
        expected_set = set(expected_list)

        if not isinstance(raw_sections_payload, list):
            return False, "A lista 'sections' não é um array JSON válido."

        if len(raw_sections_payload) == 0 and len(expected_list) > 0:
            return False, f"Lista 'sections' vazia (esperadas {len(expected_list)} secções: {expected_list})."

        received_ids: List[str] = []
        seen_ids: Set[str] = set()
        duplicate_ids: List[str] = []

        for idx, item in enumerate(raw_sections_payload):
            if not isinstance(item, dict):
                return False, f"Elemento na posição {idx} de 'sections' não é um objeto JSON válido."
            sid = str(item.get("section_id") or "").strip()
            if not sid:
                return False, f"Elemento na posição {idx} de 'sections' tem 'section_id' vazio ou ausente."
            if sid in seen_ids:
                if sid not in duplicate_ids:
                    duplicate_ids.append(sid)
            else:
                seen_ids.add(sid)
            received_ids.append(sid)

        if duplicate_ids:
            return False, f"Identificadores 'section_id' duplicados na resposta: {duplicate_ids}"

        received_set = set(received_ids)
        unknown_ids = sorted(received_set - expected_set)
        if unknown_ids:
            return False, f"Identificadores 'section_id' desconhecidos/inesperados na resposta: {unknown_ids}"

        missing_ids = sorted(expected_set - received_set)
        if missing_ids:
            return False, f"Secções esperadas em falta na resposta: {missing_ids}"

        if len(received_ids) != len(expected_list):
            return (
                False,
                f"Contagem de secções recebidas ({len(received_ids)}) difere das esperadas ({len(expected_list)}).",
            )

        return True, "OK"

    @classmethod
    def build_enriched_section(
        cls,
        plan_sec: EditorialSection,
        raw_sec_dict: Optional[Dict[str, Any]],
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        provenance: ReferenceAndProvenanceRenderer,
    ) -> DevelopedSectionContent:
        """
        Constrói um `DevelopedSectionContent` validado e pedagogicamente enriquecido.
        Se `raw_sec_dict` for None (ex.: falha após retries), constrói uma explicação académica
        determinística e fundamentada nos dados da Fase 3 e Fase 2, marcando `generation_status="FALLBACK_GROUNDED"`.
        """
        sec_refs = provenance.sanitize_evidence_refs(
            plan_sec.evidence_refs,
            fallback_section_ids=plan_sec.original_section_ids,
        )

        # Mapear SectionAnalyses originais associadas
        linked_analyses: List[SectionAnalysis] = [
            sa for sa in dossier.section_analyses if sa.section_id in set(plan_sec.original_section_ids)
        ]
        if not linked_analyses and dossier.section_analyses:
            # Tentar associar através de evidence_refs
            ref_sids = {r.section_id for r in sec_refs if r.section_id}
            linked_analyses = [sa for sa in dossier.section_analyses if sa.section_id in ref_sids]

        # Conceitos relevantes do Dossier
        target_cids = set(plan_sec.associated_concept_ids + plan_sec.introduced_concept_ids)
        concepts_pool = getattr(dossier, "conceptual_analysis", [])
        if hasattr(concepts_pool, "concepts"):
            concepts_pool = concepts_pool.concepts
        elif not isinstance(concepts_pool, list):
            concepts_pool = []

        relevant_concepts = [
            c for c in concepts_pool
            if getattr(c, "concept_id", "") in target_cids or getattr(c, "name", "").lower() in plan_sec.title.lower()
        ]
        if not relevant_concepts and linked_analyses:
            for sa in linked_analyses:
                for sc in getattr(sa, "key_concepts", getattr(sa, "concepts", []))[:4]:
                    relevant_concepts.append(sc)

        if raw_sec_dict is not None:
            return cls._parse_and_enrich_llm_section(
                plan_sec=plan_sec,
                raw=raw_sec_dict,
                linked_analyses=linked_analyses,
                relevant_concepts=relevant_concepts,
                dossier=dossier,
                ast=ast,
                provenance=provenance,
                sec_refs=sec_refs,
            )

        return cls._build_deterministic_grounded_section(
            plan_sec=plan_sec,
            linked_analyses=linked_analyses,
            relevant_concepts=relevant_concepts,
            dossier=dossier,
            ast=ast,
            provenance=provenance,
            sec_refs=sec_refs,
        )

    @staticmethod
    def _infer_elaboration_type(block_type: str, is_hyp: bool, ep_status: str) -> str:
        if is_hyp or block_type == ContentBlockType.HYPOTHETICAL_EXAMPLE.value:
            return ElaborationType.HYPOTHETICAL_EXAMPLE.value
        if block_type in (
            ContentBlockType.CAUSE_EFFECT_ANALYSIS.value,
            ContentBlockType.RESULTS_INTERPRETATION.value,
            ContentBlockType.CONCEPT_COMPARISON.value,
        ):
            return ElaborationType.ANALYTICAL_INFERENCE.value
        if block_type in (
            ContentBlockType.SECTION_SYNTHESIS.value,
            ContentBlockType.CHAPTER_SYNTHESIS.value,
        ):
            return ElaborationType.EDITORIAL_SYNTHESIS.value
        if ep_status == "UNVERIFIED":
            return ElaborationType.UNVERIFIED_CLAIM.value
        if ep_status == "SOURCE_FACT":
            return ElaborationType.SOURCE_EXTRACTED.value
        return ElaborationType.PEDAGOGICAL_EXPLANATION.value

    @staticmethod
    def _extract_candidate_refs_from_raw(
        raw_item: Dict[str, Any],
        plan_sec: EditorialSection,
        provenance: ReferenceAndProvenanceRenderer,
        default_status: str,
    ) -> Tuple[List[EditorialEvidenceRef], List[str], bool]:
        """
        Extrai referências explícitas de um objeto gerado pelo LLM sem fallback silencioso para `sec_refs`.
        Devolve (valid_refs, rejected_ref_labels, explicitly_cited_any).
        """
        cand_refs: List[EditorialEvidenceRef] = []
        raw_pids = [str(x).strip() for x in (raw_item.get("paragraph_ids") or []) if str(x).strip()]
        raw_pages = [
            int(x) for x in (raw_item.get("page_numbers") or [])
            if isinstance(x, (int, float)) and not isinstance(x, bool) and int(x) > 0
        ]
        raw_ev_objs = raw_item.get("evidence_refs") or []
        explicitly_cited = bool(raw_pids or raw_pages or raw_ev_objs)

        for ev in raw_ev_objs:
            if isinstance(ev, dict):
                ev_pid = str(ev.get("paragraph_id") or "").strip()
                ev_sid = str(ev.get("section_id") or "").strip()
                if not ev_sid and ev_pid and ev_pid in provenance.para_to_section:
                    ev_sid = provenance.para_to_section[ev_pid]
                cand_refs.append(
                    EditorialEvidenceRef(
                        paragraph_id=ev_pid,
                        section_id=ev_sid,
                        page_number=ev.get("page_number"),
                        status=default_status,
                        excerpt=str(ev.get("excerpt") or ""),
                    )
                )
        for pid in raw_pids[:6]:
            cand_refs.append(
                EditorialEvidenceRef(
                    paragraph_id=pid,
                    section_id=provenance.para_to_section.get(pid, ""),
                    page_number=provenance.para_to_page.get(pid),
                    status=default_status,
                )
            )
        for pg in raw_pages[:4]:
            cand_refs.append(
                EditorialEvidenceRef(
                    paragraph_id="",
                    section_id="",
                    page_number=pg,
                    status=default_status,
                )
            )

        valid_refs, rej_pids, rej_pages, rej_sids = provenance.validate_evidence_refs(
            cand_refs,
            allow_section_fallback=False,
            default_status=default_status,
        )
        rejected = list(rej_pids) + [f"p.{p}" for p in rej_pages] + list(rej_sids)
        return valid_refs, rejected, explicitly_cited

    @classmethod
    def _parse_and_enrich_llm_section(
        cls,
        plan_sec: EditorialSection,
        raw: Dict[str, Any],
        linked_analyses: List[SectionAnalysis],
        relevant_concepts: List[Any],
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        provenance: ReferenceAndProvenanceRenderer,
        sec_refs: List[EditorialEvidenceRef],
    ) -> DevelopedSectionContent:
        opening = str(raw.get("opening_contextualization") or "").strip()
        if not opening:
            opening = (
                f"Esta secção aborda «{plan_sec.title}» com o objetivo pedagógico de {plan_sec.pedagogical_objective}. "
                f"A abordagem segue a estratégia editorial definida: {plan_sec.explanation_strategy}."
            )

        blocks: List[DevelopedContentBlock] = []
        raw_blocks = raw.get("content_blocks")
        if isinstance(raw_blocks, list):
            for b_idx, rb in enumerate(raw_blocks, start=1):
                if not isinstance(rb, dict):
                    continue
                b_type_raw = str(rb.get("block_type") or ContentBlockType.EXPLANATORY_PARAGRAPH.value).upper().strip()
                valid_types = {t.value for t in ContentBlockType}
                if b_type_raw not in valid_types:
                    b_type_raw = ContentBlockType.EXPLANATORY_PARAGRAPH.value

                b_title = str(rb.get("title") or plan_sec.title).strip()
                paras = [str(p).strip() for p in (rb.get("body_paragraphs") or []) if str(p).strip()]
                if not paras and rb.get("text"):
                    paras = [str(rb["text"]).strip()]
                bullets = [str(x).strip() for x in (rb.get("bullet_points") or []) if str(x).strip()]
                steps = [str(s).strip() for s in (rb.get("steps") or []) if str(s).strip()]

                if not paras and not bullets and not steps:
                    continue

                is_hyp = bool(rb.get("is_hypothetical_example", False)) or (
                    b_type_raw == ContentBlockType.HYPOTHETICAL_EXAMPLE.value
                )
                combined_txt_low = (" ".join(paras) + " " + b_title).lower()
                if any(
                    marker in combined_txt_low
                    for marker in ("exemplo hipotético", "exemplo ilustrativo", "hipoteticamente", "cenário hipotético")
                ):
                    is_hyp = True
                    b_type_raw = ContentBlockType.HYPOTHETICAL_EXAMPLE.value

                # 1. Política explícita: nunca assumir SOURCE_FACT por omissão em conteúdo gerado pelo LLM
                raw_ep = str(rb.get("epistemic_status") or "").upper().strip()
                if raw_ep not in VALID_EPISTEMIC_STATUSES:
                    ep_status = "UNVERIFIED"
                else:
                    ep_status = raw_ep

                # 2. Validar referências explícitas sem fallback silencioso para sec_refs
                valid_refs, rejected_refs, explicitly_cited = cls._extract_candidate_refs_from_raw(
                    rb,
                    plan_sec=plan_sec,
                    provenance=provenance,
                    default_status=ep_status,
                )
                claim_corpus = " ".join([b_title] + paras + bullets + steps)

                if is_hyp:
                    # Regra 4.2 e 5.2: Exemplos hipotéticos criados pelo modelo são sempre MODEL_INFERENCE
                    ep_status = "MODEL_INFERENCE"
                    if "hipotético" not in b_title.lower() and "ilustrativo" not in b_title.lower():
                        b_title = f"Exemplo Ilustrativo Hipotético: {b_title}"
                    elab_type = ElaborationType.HYPOTHETICAL_EXAMPLE.value
                elif ep_status == "SOURCE_FACT":
                    # Bloco gerado pelo LLM reivindicando SOURCE_FACT exige referência explícita válida
                    # e rastreabilidade textual plausível na evidência citada.
                    has_concrete_ref = any(r.paragraph_id or r.page_number for r in valid_refs)
                    if not valid_refs or not has_concrete_ref:
                        ep_status = "UNVERIFIED"
                        elab_type = ElaborationType.UNVERIFIED_CLAIM.value
                    elif b_type_raw in (
                        ContentBlockType.STEP_BY_STEP_MECHANISM.value,
                        ContentBlockType.THEORETICAL_CONTEXT.value,
                        ContentBlockType.CAUSE_EFFECT_ANALYSIS.value,
                        ContentBlockType.RESULTS_INTERPRETATION.value,
                        ContentBlockType.METHODOLOGY_EXPLANATION.value,
                        ContentBlockType.LIMITATIONS_DISCUSSION.value,
                        ContentBlockType.CONCEPT_COMPARISON.value,
                    ):
                        # Explicações, mecanismos e interpretações produzidos pelo LLM são MODEL_INFERENCE
                        # fundamentados na fonte (nunca herdam automaticamente SOURCE_FACT).
                        ep_status = "MODEL_INFERENCE"
                        elab_type = cls._infer_elaboration_type(b_type_raw, False, ep_status)
                    elif not provenance.has_minimal_source_overlap(claim_corpus, valid_refs):
                        # Uma referência existente não transforma texto sem suporte verificável em SOURCE_FACT
                        ep_status = "UNVERIFIED"
                        elab_type = ElaborationType.UNVERIFIED_CLAIM.value
                    else:
                        elab_type = ElaborationType.SOURCE_EXTRACTED.value
                else:
                    elab_type = cls._infer_elaboration_type(b_type_raw, False, ep_status)

                # Se nenhuma ref explícita foi citada num bloco pedagógico, manter apenas contexto não factual (ou vazio se UNVERIFIED/rejeitado)
                final_refs = valid_refs
                if not explicitly_cited and ep_status == "MODEL_INFERENCE" and not is_hyp and sec_refs:
                    final_refs = provenance.sanitize_evidence_refs(
                        sec_refs[:2],
                        allow_section_fallback=False,
                        default_status="MODEL_INFERENCE",
                    )

                for ref in final_refs:
                    ref.status = ep_status

                ev_ids = [
                    r.paragraph_id or f"{r.section_id}:p{r.page_number or 0}"
                    for r in final_refs
                    if r.paragraph_id or r.section_id
                ]

                blocks.append(
                    DevelopedContentBlock(
                        block_id=f"{plan_sec.section_id}_blk_{b_idx:02d}",
                        block_type=b_type_raw,
                        title=b_title,
                        body_paragraphs=paras,
                        bullet_points=bullets,
                        steps=steps,
                        is_hypothetical_example=is_hyp,
                        epistemic_status=ep_status,
                        elaboration_type=elab_type,
                        evidence_ids=ev_ids,
                        evidence_refs=final_refs,
                        rejected_reference_ids=rejected_refs,
                        source_table_refs=[str(x) for x in (rb.get("source_table_refs") or []) if str(x).strip()],
                        source_figure_refs=[str(x) for x in (rb.get("source_figure_refs") or []) if str(x).strip()],
                        source_formula_refs=[str(x) for x in (rb.get("source_formula_refs") or []) if str(x).strip()],
                    )
                )

        # Garantir que nenhum conteúdo obrigatório de `contents_to_cover` foi descartado silenciosamente
        cls._ensure_mandatory_contents_covered(plan_sec, blocks, linked_analyses, provenance, sec_refs)

        # Definições desenvolvidas de conceitos
        concept_defs: List[DevelopedConceptDefinition] = []
        raw_cdefs = raw.get("concept_definitions")
        seen_terms: Set[str] = set()
        phase3_concepts_by_name = {
            getattr(c, "name", "").strip().lower(): c for c in relevant_concepts if getattr(c, "name", "").strip()
        }

        if isinstance(raw_cdefs, list):
            for c_idx, rc in enumerate(raw_cdefs, start=1):
                if not isinstance(rc, dict):
                    continue
                term = str(rc.get("term") or "").strip()
                c_def = str(rc.get("developed_definition") or "").strip()
                if not term or not c_def or term.lower() in seen_terms:
                    continue
                seen_terms.add(term.lower())

                raw_c_st = str(rc.get("epistemic_status") or "").upper().strip()
                c_st = raw_c_st if raw_c_st in VALID_EPISTEMIC_STATUSES else "UNVERIFIED"
                c_valid_refs, _, c_explicitly_cited = cls._extract_candidate_refs_from_raw(
                    rc,
                    plan_sec=plan_sec,
                    provenance=provenance,
                    default_status=c_st,
                )

                matched_cnode = phase3_concepts_by_name.get(term.lower())
                if not c_explicitly_cited and matched_cnode is not None:
                    matched_refs = provenance.sanitize_evidence_refs(
                        getattr(matched_cnode, "evidence_refs", []) or [],
                        allow_section_fallback=False,
                        default_status=c_st,
                    )
                    if matched_refs:
                        c_valid_refs = matched_refs

                if c_st == "SOURCE_FACT":
                    has_concrete = any(r.paragraph_id or r.page_number for r in c_valid_refs)
                    if not has_concrete or not provenance.has_minimal_source_overlap(f"{term} {c_def}", c_valid_refs):
                        c_st = "UNVERIFIED"

                for r in c_valid_refs:
                    r.status = c_st

                c_elab = (
                    ElaborationType.SOURCE_EXTRACTED.value
                    if c_st == "SOURCE_FACT"
                    else (ElaborationType.UNVERIFIED_CLAIM.value if c_st == "UNVERIFIED" else ElaborationType.PEDAGOGICAL_EXPLANATION.value)
                )
                c_ev_ids = [r.paragraph_id or f"{r.section_id}:p{r.page_number or 0}" for r in c_valid_refs]
                concept_defs.append(
                    DevelopedConceptDefinition(
                        concept_id=str(rc.get("concept_id") or f"cdef_{plan_sec.section_id}_{c_idx}"),
                        term=term,
                        developed_definition=c_def,
                        theoretical_context=str(rc.get("theoretical_context") or "").strip(),
                        relationships_explained=str(rc.get("relationships_explained") or "").strip(),
                        epistemic_status=c_st,
                        elaboration_type=c_elab,
                        evidence_ids=c_ev_ids,
                        evidence_refs=c_valid_refs,
                    )
                )

        # Complementar com conceitos verificados do Dossier (Fase 3) que não tenham sido incluídos pelo modelo
        for c_node in relevant_concepts[:5]:
            c_name = getattr(c_node, "name", "")
            c_desc = (
                getattr(c_node, "definition", "")
                or getattr(c_node, "definition_or_description", "")
                or getattr(c_node, "explanation", "")
            )
            if c_name and c_desc and c_name.lower() not in seen_terms:
                seen_terms.add(c_name.lower())
                raw_node_refs = getattr(c_node, "evidence_refs", []) or []
                node_valid_refs = provenance.sanitize_evidence_refs(
                    raw_node_refs,
                    allow_section_fallback=False,
                    default_status="UNVERIFIED",
                )
                explicit_node_status = getattr(getattr(c_node, "epistemic_status", None), "value", getattr(c_node, "epistemic_status", None))
                if explicit_node_status:
                    node_st = normalize_epistemic_status(explicit_node_status, default="UNVERIFIED")
                elif node_valid_refs and all(r.status == "SOURCE_FACT" for r in node_valid_refs):
                    node_st = "SOURCE_FACT"
                elif node_valid_refs and any(r.status == "MODEL_INFERENCE" for r in node_valid_refs):
                    node_st = "MODEL_INFERENCE"
                else:
                    node_st = "UNVERIFIED"

                concept_defs.append(
                    DevelopedConceptDefinition(
                        concept_id=getattr(c_node, "concept_id", f"cdef_{len(concept_defs)+1}"),
                        term=c_name,
                        developed_definition=c_desc,
                        theoretical_context=getattr(c_node, "academic_relevance", "") or getattr(c_node, "context_of_use", ""),
                        relationships_explained="",
                        epistemic_status=node_st,
                        elaboration_type=(
                            ElaborationType.SOURCE_EXTRACTED.value if node_st == "SOURCE_FACT" else ElaborationType.PEDAGOGICAL_EXPLANATION.value
                        ),
                        evidence_ids=[r.paragraph_id or f"{r.section_id}:p{r.page_number or 0}" for r in node_valid_refs],
                        evidence_refs=node_valid_refs,
                    )
                )

        # Comparações entre conceitos / métodos
        comparisons: List[DevelopedComparisonItem] = []
        raw_comps = raw.get("comparisons")
        if isinstance(raw_comps, list):
            for rc in raw_comps:
                if not isinstance(rc, dict):
                    continue
                dim = str(rc.get("dimension") or "").strip()
                a_lbl = str(rc.get("item_a_label") or "").strip()
                a_desc = str(rc.get("item_a_description") or "").strip()
                b_lbl = str(rc.get("item_b_label") or "").strip()
                b_desc = str(rc.get("item_b_description") or "").strip()
                if dim and a_desc and b_desc:
                    raw_cmp_st = str(rc.get("epistemic_status") or "").upper().strip()
                    cmp_st = raw_cmp_st if raw_cmp_st in VALID_EPISTEMIC_STATUSES else "UNVERIFIED"
                    cmp_valid_refs, _, _ = cls._extract_candidate_refs_from_raw(
                        rc,
                        plan_sec=plan_sec,
                        provenance=provenance,
                        default_status=cmp_st,
                    )
                    if cmp_st == "SOURCE_FACT":
                        has_concrete = any(r.paragraph_id or r.page_number for r in cmp_valid_refs)
                        if not has_concrete or not provenance.has_minimal_source_overlap(
                            f"{dim} {a_lbl} {a_desc} {b_lbl} {b_desc}", cmp_valid_refs
                        ):
                            cmp_st = "UNVERIFIED"
                    for r in cmp_valid_refs:
                        r.status = cmp_st
                    comparisons.append(
                        DevelopedComparisonItem(
                            dimension=dim,
                            item_a_label=a_lbl or "Elemento A",
                            item_a_description=a_desc,
                            item_b_label=b_lbl or "Elemento B",
                            item_b_description=b_desc,
                            synthesis_note=str(rc.get("synthesis_note") or "").strip(),
                            epistemic_status=cmp_st,
                            elaboration_type=(
                                ElaborationType.SOURCE_EXTRACTED.value
                                if cmp_st == "SOURCE_FACT"
                                else (ElaborationType.UNVERIFIED_CLAIM.value if cmp_st == "UNVERIFIED" else ElaborationType.ANALYTICAL_INFERENCE.value)
                            ),
                            evidence_ids=[r.paragraph_id or f"{r.section_id}:p{r.page_number or 0}" for r in cmp_valid_refs],
                            evidence_refs=cmp_valid_refs,
                        )
                    )

        # Limitações e ressalvas
        limitations: List[str] = [
            str(x).strip() for x in (raw.get("limitations_and_caveats") or []) if str(x).strip()
        ]
        for lim in plan_sec.limitations_and_uncertainties:
            if lim and lim not in limitations:
                limitations.append(lim)

        sec_synth = str(raw.get("section_synthesis") or "").strip()
        if not sec_synth:
            sec_synth = (
                f"Em síntese, «{plan_sec.title}» consolida os elementos fundamentais previstos no plano editorial "
                f"({plan_sec.pedagogical_objective}), articulando as evidências verificadas na fonte com a progressão "
                f"pedagógica do documento."
            )

        # O invólucro pedagógico da secção desenvolvida é elaboração editorial (nunca herda SOURCE_FACT automaticamente)
        return DevelopedSectionContent(
            section_id=plan_sec.section_id,
            chapter_id=plan_sec.chapter_id,
            title=plan_sec.title,
            order=plan_sec.order,
            level=plan_sec.level,
            pedagogical_objective=plan_sec.pedagogical_objective,
            content_role=plan_sec.content_role,
            explanation_strategy=plan_sec.explanation_strategy,
            opening_contextualization=opening,
            content_blocks=blocks,
            concept_definitions=concept_defs,
            comparisons=comparisons,
            limitations_and_caveats=limitations,
            section_synthesis=sec_synth,
            epistemic_status="MODEL_INFERENCE",
            elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
            evidence_ids=[r.paragraph_id or f"{r.section_id}:p{r.page_number or 0}" for r in sec_refs],
            evidence_refs=sec_refs,
            generation_status="COMPLETED",
        )

    @classmethod
    def _ensure_mandatory_contents_covered(
        cls,
        plan_sec: EditorialSection,
        blocks: List[DevelopedContentBlock],
        linked_analyses: List[SectionAnalysis],
        provenance: ReferenceAndProvenanceRenderer,
        sec_refs: List[EditorialEvidenceRef],
    ) -> None:
        """
        Garante proteção contra perda silenciosa de conteúdo (Secção 7 / Critério A):
        todos os pontos de `plan_sec.contents_to_cover` e análises nucleares têm de estar representados,
        preservando estritamente a classificação epistémica sem promoção automática a SOURCE_FACT.
        """
        if not blocks:
            paras: List[str] = []
            for sa in linked_analyses:
                synth = getattr(sa, "in_depth_synthesis", "") or getattr(sa, "argumentative_synthesis", "")
                if synth:
                    paras.append(synth)
                detail = getattr(sa, "detailed_interpretation", "")
                if detail:
                    paras.append(detail)
                for idea in getattr(sa, "core_ideas", []):
                    if idea not in paras:
                        paras.append(idea)
            for item in plan_sec.contents_to_cover:
                s_txt = str(item.get("summary") or "").strip()
                if s_txt and s_txt not in " ".join(paras):
                    paras.append(s_txt)
            if not paras:
                paras.append(
                    f"Desenvolvimento de «{plan_sec.title}»: {plan_sec.pedagogical_objective}. "
                    f"Estratégia: {plan_sec.explanation_strategy}."
                )
            blocks.append(
                DevelopedContentBlock(
                    block_id=f"{plan_sec.section_id}_blk_01",
                    block_type=ContentBlockType.EXPLANATORY_PARAGRAPH.value,
                    title=f"Análise e Desenvolvimento: {plan_sec.title}",
                    body_paragraphs=paras,
                    epistemic_status="MODEL_INFERENCE",
                    elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
                    evidence_refs=sec_refs,
                )
            )
            return

        # Verificar se os pontos de `contents_to_cover` têm cobertura semântica nos blocos
        existing_corpus = " ".join(
            " ".join(b.body_paragraphs + b.bullet_points + b.steps) for b in blocks
        ).lower()
        uncovered_facts: List[str] = []
        uncovered_inferences: List[str] = []
        uncovered_unverified: List[str] = []
        fact_refs: List[EditorialEvidenceRef] = []

        for item in plan_sec.contents_to_cover:
            summary = str(item.get("summary") or "").strip()
            if not summary:
                continue
            words = [w.lower().strip(".,;:()[]«»\"'") for w in summary.split() if len(w) > 4]
            if words:
                matched = sum(1 for w in words[:8] if w in existing_corpus)
                if matched >= max(1, min(2, len(words) // 3)):
                    continue
            st = normalize_epistemic_status(item.get("epistemic_status"), default="UNVERIFIED")
            item_pids = [str(x).strip() for x in (item.get("paragraph_ids") or []) if str(x).strip()]
            item_pgs = [int(x) for x in (item.get("page_numbers") or []) if isinstance(x, (int, float)) and int(x) > 0]
            if st == "SOURCE_FACT":
                cands = [
                    EditorialEvidenceRef(
                        paragraph_id=pid,
                        section_id=plan_sec.original_section_ids[0] if plan_sec.original_section_ids else "",
                        page_number=provenance.para_to_page.get(pid),
                        status="SOURCE_FACT",
                    )
                    for pid in item_pids
                ] + [
                    EditorialEvidenceRef(
                        paragraph_id="",
                        section_id=plan_sec.original_section_ids[0] if plan_sec.original_section_ids else "",
                        page_number=pg,
                        status="SOURCE_FACT",
                    )
                    for pg in item_pgs
                ]
                v_refs, _, _, _ = provenance.validate_evidence_refs(cands or sec_refs, allow_section_fallback=False, default_status="SOURCE_FACT")
                if v_refs:
                    uncovered_facts.append(summary)
                    fact_refs.extend(v_refs)
                else:
                    uncovered_unverified.append(summary)
            elif st == "MODEL_INFERENCE":
                uncovered_inferences.append(summary)
            else:
                uncovered_unverified.append(summary)

        if uncovered_facts:
            blocks.append(
                DevelopedContentBlock(
                    block_id=f"{plan_sec.section_id}_blk_cov_fact",
                    block_type=ContentBlockType.EXPLANATORY_PARAGRAPH.value,
                    title="Evidências e Factos Essenciais da Fonte",
                    body_paragraphs=[
                        "Em complemento à análise desenvolvida, destacam-se os seguintes elementos factuais "
                        "extraídos diretamente das secções correspondentes da fonte original:"
                    ],
                    bullet_points=uncovered_facts,
                    epistemic_status="SOURCE_FACT",
                    elaboration_type=ElaborationType.SOURCE_EXTRACTED.value,
                    evidence_refs=fact_refs or sec_refs,
                )
            )

        if uncovered_inferences:
            blocks.append(
                DevelopedContentBlock(
                    block_id=f"{plan_sec.section_id}_blk_cov_inf",
                    block_type=ContentBlockType.THEORETICAL_CONTEXT.value,
                    title="Implicações Analíticas e Inferências Fundamentadas",
                    body_paragraphs=[
                        "A partir da articulação das evidências da fonte, identificam-se as seguintes "
                        "inferências analíticas e relações conceptuais (MODEL_INFERENCE):"
                    ],
                    bullet_points=uncovered_inferences,
                    epistemic_status="MODEL_INFERENCE",
                    elaboration_type=ElaborationType.ANALYTICAL_INFERENCE.value,
                    evidence_refs=sec_refs,
                )
            )

        if uncovered_unverified:
            blocks.append(
                DevelopedContentBlock(
                    block_id=f"{plan_sec.section_id}_blk_cov_unv",
                    block_type=ContentBlockType.EXPLANATORY_PARAGRAPH.value,
                    title="Tópicos Planeados Sem Confirmação Factual Direta (UNVERIFIED)",
                    body_paragraphs=[
                        "Tópicos previstos no roteiro editorial cuja sustentação factual literal não pôde ser "
                        "confirmada diretamente na evidência validada:"
                    ],
                    bullet_points=uncovered_unverified,
                    epistemic_status="UNVERIFIED",
                    elaboration_type=ElaborationType.UNVERIFIED_CLAIM.value,
                    evidence_refs=[],
                )
            )

    @classmethod
    def _build_deterministic_grounded_section(
        cls,
        plan_sec: EditorialSection,
        linked_analyses: List[SectionAnalysis],
        relevant_concepts: List[Any],
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        provenance: ReferenceAndProvenanceRenderer,
        sec_refs: List[EditorialEvidenceRef],
    ) -> DevelopedSectionContent:
        """
        Constrói determinísticamente o conteúdo desenvolvido da secção a partir do Dossier (Fase 3),
        do Plano Editorial (Fase 4) e dos parágrafos/tabelas da AST (Fase 2), garantindo que nenhuma
        secção fica vazia e separando estritamente factos da fonte de elaborações pedagógicas.
        """
        opening = (
            f"Esta secção desenvolve «{plan_sec.title}», visando {plan_sec.pedagogical_objective}. "
            f"A exposição organiza-se segundo a estratégia pedagógica planeada: {plan_sec.explanation_strategy}."
        )

        blocks: List[DevelopedContentBlock] = []
        blk_counter = 1

        # 1. Factos explícitos vs Contextualização pedagógica das Secções Originais
        for sa in linked_analyses:
            verified_sa_refs = provenance.sanitize_evidence_refs(
                getattr(sa, "source_refs", []) or [],
                allow_section_fallback=False,
                default_status="UNVERIFIED",
            )
            fact_bullets = [getattr(f, "statement", str(f)) for f in getattr(sa, "explicit_facts", []) if f]
            if not fact_bullets and getattr(sa, "evidences", []):
                fact_bullets = [str(ev.get("claim") or ev) if isinstance(ev, dict) else str(ev) for ev in sa.evidences[:4]]

            verified_fact_refs = [r for r in verified_sa_refs if r.status == "SOURCE_FACT"]
            if fact_bullets and (verified_fact_refs or verified_sa_refs):
                blocks.append(
                    DevelopedContentBlock(
                        block_id=f"{plan_sec.section_id}_blk_{blk_counter:02d}_facts",
                        block_type=ContentBlockType.EXPLANATORY_PARAGRAPH.value,
                        title=f"Factos e Evidências Diretas: {sa.title}",
                        body_paragraphs=[
                            f"Elementos factuais extraídos e referenciados da secção original «{sa.title}»:"
                        ],
                        bullet_points=fact_bullets,
                        epistemic_status="SOURCE_FACT" if verified_fact_refs else "MODEL_INFERENCE",
                        elaboration_type=(
                            ElaborationType.SOURCE_EXTRACTED.value if verified_fact_refs else ElaborationType.PEDAGOGICAL_EXPLANATION.value
                        ),
                        evidence_refs=verified_fact_refs or verified_sa_refs,
                    )
                )
                blk_counter += 1

            paras: List[str] = []
            obj = getattr(sa, "objective", "") or getattr(sa, "central_objective", "")
            if obj:
                paras.append(f"Enquadramento na fonte original («{sa.title}»): {obj}")
            synth = getattr(sa, "in_depth_synthesis", "") or getattr(sa, "argumentative_synthesis", "")
            if synth:
                paras.append(synth)
            detail = getattr(sa, "detailed_interpretation", "")
            if detail and detail not in paras:
                paras.append(detail)
            for idea in getattr(sa, "core_ideas", []):
                if idea not in paras:
                    paras.append(idea)

            if paras:
                # Síntese e desenvolvimento analítico da secção (MODEL_INFERENCE fundamentado na fonte)
                blocks.append(
                    DevelopedContentBlock(
                        block_id=f"{plan_sec.section_id}_blk_{blk_counter:02d}",
                        block_type=ContentBlockType.EXPLANATORY_PARAGRAPH.value,
                        title=f"Análise e Enquadramento Académico: {sa.title}",
                        body_paragraphs=paras,
                        epistemic_status="MODEL_INFERENCE",
                        elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
                        evidence_refs=verified_sa_refs or sec_refs,
                    )
                )
                blk_counter += 1

            inf_bullets = [getattr(i, "statement", str(i)) for i in getattr(sa, "inferences", []) if i]
            if not inf_bullets and getattr(sa, "arguments", []):
                inf_bullets = [str(arg.get("claim") or arg) if isinstance(arg, dict) else str(arg) for arg in sa.arguments[:4]]
            if inf_bullets:
                blocks.append(
                    DevelopedContentBlock(
                        block_id=f"{plan_sec.section_id}_blk_{blk_counter:02d}",
                        block_type=ContentBlockType.CAUSE_EFFECT_ANALYSIS.value,
                        title=f"Interpretação Analítica e Inferências ({sa.title})",
                        body_paragraphs=[
                            "Com base nos dados reportados nesta unidade, derivam-se as seguintes "
                            "interpretações analíticas (MODEL_INFERENCE):"
                        ],
                        bullet_points=inf_bullets,
                        epistemic_status="MODEL_INFERENCE",
                        elaboration_type=ElaborationType.ANALYTICAL_INFERENCE.value,
                        evidence_refs=sec_refs,
                    )
                )
                blk_counter += 1

        # 2. Garantir cobertura de `contents_to_cover`
        cls._ensure_mandatory_contents_covered(plan_sec, blocks, linked_analyses, provenance, sec_refs)

        # 3. Tratamentos pedagógicos planeados na Fase 4 (desenvolvimento pedagógico = MODEL_INFERENCE)
        for pt_idx, pt in enumerate(plan_sec.pedagogical_treatments, start=1):
            focus_lines = [f"{k}: {v}" for k, v in (pt.pedagogical_focus or {}).items() if v]
            b_type = (
                ContentBlockType.CALLOUT_BOX.value
                if any("BOX" in str(el).upper() or "CALLOUT" in str(el).upper() for el in (pt.required_elements or []))
                else ContentBlockType.STEP_BY_STEP_MECHANISM.value
            )
            pt_refs = provenance.sanitize_evidence_refs(pt.evidence_refs or [], allow_section_fallback=False, default_status="MODEL_INFERENCE")
            blocks.append(
                DevelopedContentBlock(
                    block_id=f"{plan_sec.section_id}_blk_pt_{pt_idx:02d}",
                    block_type=b_type,
                    title=f"Aprofundamento Pedagógico: {pt.target_topic_or_concept}",
                    body_paragraphs=[
                        f"Nível de profundidade ({pt.depth_level}): {pt.depth_justification or pt.target_topic_or_concept}"
                    ],
                    steps=focus_lines or pt.required_elements,
                    epistemic_status="MODEL_INFERENCE",
                    elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
                    evidence_refs=pt_refs or sec_refs,
                )
            )

        # Se houver planned_pedagogical_elements que ainda não estejam em blocks
        for p_elem in getattr(plan_sec, "planned_pedagogical_elements", []):
            if any(box_k in str(p_elem).upper() for box_k in ("BOX", "CALLOUT")):
                if not any(b.block_type == ContentBlockType.CALLOUT_BOX.value for b in blocks):
                    blocks.append(
                        DevelopedContentBlock(
                            block_id=f"{plan_sec.section_id}_blk_box_{len(blocks)+1:02d}",
                            block_type=ContentBlockType.CALLOUT_BOX.value,
                            title=f"Caixa Pedagógica ({p_elem}): {plan_sec.title}",
                            body_paragraphs=[
                                f"Enquadramento temático segundo o modelo {p_elem}: consolidação de princípios chave da secção."
                            ],
                            epistemic_status="MODEL_INFERENCE",
                            elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
                            evidence_refs=sec_refs,
                        )
                    )

        # 4. Definições de conceitos verificados do Dossier
        concept_defs: List[DevelopedConceptDefinition] = []
        seen_terms: Set[str] = set()
        for c_node in relevant_concepts[:6]:
            c_name = getattr(c_node, "name", "")
            c_desc = (
                getattr(c_node, "definition", "")
                or getattr(c_node, "definition_or_description", "")
                or getattr(c_node, "explanation", "")
            )
            if c_name and c_desc and c_name.lower() not in seen_terms:
                seen_terms.add(c_name.lower())
                raw_node_refs = getattr(c_node, "evidence_refs", []) or []
                node_valid_refs = provenance.sanitize_evidence_refs(
                    raw_node_refs,
                    allow_section_fallback=False,
                    default_status="UNVERIFIED",
                )
                explicit_node_status = getattr(getattr(c_node, "epistemic_status", None), "value", getattr(c_node, "epistemic_status", None))
                if explicit_node_status:
                    node_st = normalize_epistemic_status(explicit_node_status, default="UNVERIFIED")
                elif node_valid_refs and all(r.status == "SOURCE_FACT" for r in node_valid_refs):
                    node_st = "SOURCE_FACT"
                elif node_valid_refs and any(r.status == "MODEL_INFERENCE" for r in node_valid_refs):
                    node_st = "MODEL_INFERENCE"
                else:
                    node_st = "UNVERIFIED"

                concept_defs.append(
                    DevelopedConceptDefinition(
                        concept_id=getattr(c_node, "concept_id", f"cdef_{len(concept_defs)+1}"),
                        term=c_name,
                        developed_definition=c_desc,
                        theoretical_context=getattr(c_node, "academic_relevance", "") or getattr(c_node, "context_of_use", ""),
                        epistemic_status=node_st,
                        elaboration_type=(
                            ElaborationType.SOURCE_EXTRACTED.value if node_st == "SOURCE_FACT" else ElaborationType.PEDAGOGICAL_EXPLANATION.value
                        ),
                        evidence_ids=[r.paragraph_id or f"{r.section_id}:p{r.page_number or 0}" for r in node_valid_refs],
                        evidence_refs=node_valid_refs,
                    )
                )

        limitations = list(plan_sec.limitations_and_uncertainties)
        for sa in linked_analyses:
            for lim in getattr(sa, "limitations", getattr(sa, "limitations_and_gaps", [])):
                stmt = getattr(lim, "statement", str(lim))
                if stmt and stmt not in limitations:
                    limitations.append(stmt)

        sec_synth = (
            f"Síntese da Secção «{plan_sec.title}»: Os conteúdos desenvolvidos asseguram o cumprimento "
            f"do objetivo pedagógico ({plan_sec.pedagogical_objective}), mantendo rastreabilidade integral "
            f"às secções e páginas originais."
        )

        return DevelopedSectionContent(
            section_id=plan_sec.section_id,
            chapter_id=plan_sec.chapter_id,
            title=plan_sec.title,
            order=plan_sec.order,
            level=plan_sec.level,
            pedagogical_objective=plan_sec.pedagogical_objective,
            content_role=plan_sec.content_role,
            explanation_strategy=plan_sec.explanation_strategy,
            opening_contextualization=opening,
            content_blocks=blocks,
            concept_definitions=concept_defs,
            comparisons=[],
            limitations_and_caveats=limitations,
            section_synthesis=sec_synth,
            epistemic_status="MODEL_INFERENCE",
            elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
            evidence_ids=[r.paragraph_id or f"{r.section_id}:p{r.page_number or 0}" for r in sec_refs],
            evidence_refs=sec_refs,
            generation_status="FALLBACK_GROUNDED",
        )


class DocumentContentGenerationEngine:
    """
    Componente 5.1 — Document Content Generation Engine.
    Prepara e desenvolve o conteúdo académico de cada capítulo e secção a partir do
    `EditorialStudyPlan` (Fase 4), `AcademicReasoningDossier` (Fase 3) e `AcademicDocumentAST` (Fase 2).
    """

    def __init__(
        self,
        *,
        llm_caller: Optional[Callable[..., Dict[str, Any]]] = None,
        budget_manager: Optional[ContextBudgetManager] = None,
        max_retries: int = 2,
        model_name: str = "qwen3.5:9b",
    ) -> None:
        self.llm_caller = llm_caller or invoke_study_llm_observable
        self.budget = budget_manager or ContextBudgetManager(
            total_context_limit=8192,
            safety_buffer_tokens=600,
        )
        self.max_retries = max_retries
        self.model_name = model_name

    def develop_content(
        self,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        provenance: ReferenceAndProvenanceRenderer,
        telemetry: Optional[DocumentGenerationTelemetry] = None,
        failed_operations: Optional[List[Dict[str, Any]]] = None,
    ) -> DevelopedStudyDocumentContent:
        """
        Gera e compila o DevelopedStudyDocumentContent completo para todos os capítulos e secções do plano.
        """
        telemetry = telemetry or DocumentGenerationTelemetry()
        failed_operations = failed_operations if failed_operations is not None else []

        completed_chapters: List[DevelopedChapterContent] = []
        for ch in plan.chapters:
            developed_sections: List[DevelopedSectionContent] = []
            for sec in ch.sections:
                dev_sec = self.generate_section_content(
                    chapter=ch,
                    section=sec,
                    plan=plan,
                    dossier=dossier,
                    ast=ast,
                    provenance=provenance,
                    telemetry=telemetry,
                    failed_operations=failed_operations,
                )
                developed_sections.append(dev_sec)

            dev_chap = self.finalize_chapter_content(
                chapter=ch,
                developed_sections=developed_sections,
                dossier=dossier,
                provenance=provenance,
            )
            completed_chapters.append(dev_chap)

        return DevelopedStudyDocumentContent(
            document_id=plan.metadata.document_id,
            plan_id=plan.metadata.plan_id,
            plan_version=getattr(plan.metadata, "plan_version", 1),
            dossier_fingerprint=getattr(plan.metadata, "dossier_fingerprint", ""),
            plan_fingerprint=compute_plan_fingerprint(plan),
            document_title=dossier.document_title or "Caderno Académico de Estudo",
            document_subtitle=plan.overview.central_theme or "Estudo Aprofundado & Rigor Epistémico",
            executive_study_overview=plan.overview.global_organization_summary or plan.overview.editorial_strategy,
            chapters=completed_chapters,
            global_integrative_synthesis=getattr(dossier.cross_section_synthesis, "global_synthesis", ""),
            model_name=self.model_name,
        )

    def generate_section_content(
        self,
        chapter: EditorialChapter,
        section: EditorialSection,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        provenance: ReferenceAndProvenanceRenderer,
        telemetry: DocumentGenerationTelemetry,
        failed_operations: List[Dict[str, Any]],
    ) -> DevelopedSectionContent:
        """
        Gera o conteúdo aprofundado de uma secção editorial individual através do modelo local
        (`qwen3.5:9b`), respeitando o orçamento de contexto e validando estritamente `section_id`.
        """
        telemetry.prompt_versions["section_content_development"] = PROMPT_VERSIONS_PHASE5["section_content_development"]

        system_prompt = (
            "És um autor e pedagogo académico universitário de excelência em Português Europeu (PT-PT).\n"
            "A tua tarefa é desenvolver o conteúdo de estudo aprofundado para a secção editorial solicitada, "
            "com base exclusivamente nos factos, inferências e trechos da fonte original fornecidos.\n"
            "REGRAS OBRIGATÓRIAS:\n"
            "1. Devolve APENAS um objeto JSON válido com a chave 'sections' contendo exatamente a secção pedida.\n"
            "2. Preserva o 'section_id' EXATO fornecido. Não alteres nem omitas o 'section_id'.\n"
            "3. Desenvolve explicações académicas completas, claras e rigorosas (não faças apenas resumos telegráficos).\n"
            "4. Distingue rigorosamente factos literais da fonte ('SOURCE_FACT', exigindo 'paragraph_ids' reais do contexto) "
            "de explicações pedagógicas, interpretações ou relações ('MODEL_INFERENCE') e afirmações sem suporte ('UNVERIFIED').\n"
            "5. NUNCA inventes dados empíricos, resultados estatísticos, citações, 'paragraph_ids' ou páginas que não constem no contexto.\n"
            "6. Se criares um exemplo ilustrativo para facilitar a compreensão, marca 'block_type': 'HYPOTHETICAL_EXAMPLE', "
            "'is_hypothetical_example': true e 'epistemic_status': 'MODEL_INFERENCE', identificando-o como exemplo hipotético."
        )

        context_str = self._build_section_prompt_context(
            chapter=chapter,
            section=section,
            plan=plan,
            dossier=dossier,
            ast=ast,
            system_prompt=system_prompt,
        )

        schema_hint = (
            '{\n'
            '  "sections": [\n'
            '    {\n'
            f'      "section_id": "{section.section_id}",\n'
            '      "opening_contextualization": "Contextualização teórica e enquadramento inicial da secção...",\n'
            '      "content_blocks": [\n'
            '        {\n'
            '          "block_type": "THEORETICAL_CONTEXT | EXPLANATORY_PARAGRAPH | STEP_BY_STEP_MECHANISM | CAUSE_EFFECT_ANALYSIS | RESULTS_INTERPRETATION | METHODOLOGY_EXPLANATION | LIMITATIONS_DISCUSSION | HYPOTHETICAL_EXAMPLE",\n'
            '          "title": "Título semântico do bloco",\n'
            '          "body_paragraphs": ["Parágrafo académico aprofundado 1...", "Parágrafo 2..."],\n'
            '          "bullet_points": ["Ponto analítico detalhado (opcional)"],\n'
            '          "steps": ["Passo 1 do mecanismo/processo (opcional)"],\n'
            '          "is_hypothetical_example": false,\n'
            '          "epistemic_status": "MODEL_INFERENCE | SOURCE_FACT | UNVERIFIED",\n'
            '          "paragraph_ids": ["p_0001"],\n'
            '          "page_numbers": [1]\n'
            '        }\n'
            '      ],\n'
            '      "concept_definitions": [\n'
            '        {\n'
            '          "concept_id": "id_opcional",\n'
            '          "term": "Nome do Conceito",\n'
            '          "developed_definition": "Definição académica desenvolvida...",\n'
            '          "theoretical_context": "Papel teórico e importância no documento...",\n'
            '          "relationships_explained": "Como se relaciona com outros conceitos...",\n'
            '          "epistemic_status": "MODEL_INFERENCE | SOURCE_FACT | UNVERIFIED"\n'
            '        }\n'
            '      ],\n'
            '      "comparisons": [\n'
            '        {\n'
            '          "dimension": "Critério comparado",\n'
            '          "item_a_label": "Conceito/Método A",\n'
            '          "item_a_description": "Caracterização A",\n'
            '          "item_b_label": "Conceito/Método B",\n'
            '          "item_b_description": "Caracterização B",\n'
            '          "synthesis_note": "Conclusão comparativa",\n'
            '          "epistemic_status": "MODEL_INFERENCE | SOURCE_FACT | UNVERIFIED"\n'
            '        }\n'
            '      ],\n'
            '      "limitations_and_caveats": ["Limitação ou fronteira de validade..."],\n'
            '      "section_synthesis": "Síntese integradora da secção..."\n'
            '    }\n'
            '  ]\n'
            '}'
        )

        user_prompt = (
            f"{context_str}\n\n"
            f"Esquema JSON obrigatório (devolve a secção '{section.section_id}'):\n{schema_hint}"
        )

        expected_ids = [section.section_id]

        def _validate_sec_payload(data: Dict[str, Any]) -> Tuple[bool, str]:
            s_list = data.get("sections")
            ok_id, reason = AcademicContentEnricher.validate_developed_sections_identity(expected_ids, s_list)
            if not ok_id:
                return False, reason
            sec_item = s_list[0]
            blocks = sec_item.get("content_blocks")
            if not isinstance(blocks, list) or len(blocks) == 0:
                return False, f"A secção '{section.section_id}' não contém 'content_blocks' desenvolvidos."
            has_body = any(
                isinstance(b, dict)
                and (
                    (isinstance(b.get("body_paragraphs"), list) and len(b.get("body_paragraphs")) > 0)
                    or bool(str(b.get("text") or "").strip())
                    or (isinstance(b.get("steps"), list) and len(b.get("steps")) > 0)
                )
                for b in blocks
            )
            if not has_body:
                return False, f"Os blocos da secção '{section.section_id}' estão vazios."
            return True, "OK"

        parsed = self._call_model_with_retries(
            operation=f"phase5_section_content_{section.section_id}",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=DEFAULT_CONTENT_GEN_MAX_OUTPUT_TOKENS,
            validator=_validate_sec_payload,
            strict_validation=True,
            telemetry=telemetry,
            failed_operations=failed_operations,
        )

        raw_sec_dict: Optional[Dict[str, Any]] = None
        if isinstance(parsed, dict) and isinstance(parsed.get("sections"), list):
            for item in parsed["sections"]:
                if isinstance(item, dict) and str(item.get("section_id") or "").strip() == section.section_id:
                    raw_sec_dict = item
                    break

        return AcademicContentEnricher.build_enriched_section(
            plan_sec=section,
            raw_sec_dict=raw_sec_dict,
            dossier=dossier,
            ast=ast,
            provenance=provenance,
        )

    def finalize_chapter_content(
        self,
        chapter: EditorialChapter,
        developed_sections: List[DevelopedSectionContent],
        dossier: AcademicReasoningDossier,
        provenance: ReferenceAndProvenanceRenderer,
    ) -> DevelopedChapterContent:
        """
        Compõe a introdução, síntese integradora e conclusões-chave (`key_takeaways`) do capítulo
        com base nas secções desenvolvidas e na justificação editorial do capítulo.
        """
        ch_refs = provenance.sanitize_evidence_refs(
            chapter.evidence_refs,
            fallback_section_ids=chapter.original_section_ids,
        )
        sec_titles = ", ".join(f"«{s.title}»" for s in developed_sections)
        intro = (
            f"O Capítulo {chapter.order} («{chapter.title}») tem como objetivo pedagógico {chapter.pedagogical_objective}. "
            f"{chapter.description} "
            f"No plano da progressão de aprendizagem ({chapter.role_in_progression}), este capítulo estrutura-se "
            f"em {len(developed_sections)} secções complementares: {sec_titles}."
        ).strip()

        takeaways: List[str] = []
        for s in developed_sections:
            if s.section_synthesis:
                takeaways.append(f"[{s.title}] {s.section_synthesis}")

        synth = (
            f"Síntese do Capítulo {chapter.order} («{chapter.title}»): "
            f"A articulação entre {sec_titles} permite consolidar {chapter.pedagogical_objective}. "
            f"{chapter.editorial_justification}"
        ).strip()

        return DevelopedChapterContent(
            chapter_id=chapter.chapter_id,
            title=chapter.title,
            order=chapter.order,
            pedagogical_objective=chapter.pedagogical_objective,
            role_in_progression=chapter.role_in_progression,
            chapter_introduction=intro,
            sections=developed_sections,
            chapter_synthesis=synth,
            key_takeaways=takeaways[:8],
            evidence_refs=ch_refs,
        )

    def _build_section_prompt_context(
        self,
        chapter: EditorialChapter,
        section: EditorialSection,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ast: Optional[AcademicDocumentAST],
        system_prompt: str,
    ) -> str:
        """
        Constrói o contexto fundamentado para uma secção respeitando rigorosamente o orçamento de tokens
        (`ContextBudgetManager.compute_input_budget`).
        """
        avail_tokens = self.budget.calculate_usable_budget(
            system_prompt,
            "",
            max_output_tokens=DEFAULT_CONTENT_GEN_MAX_OUTPUT_TOKENS,
        )

        header_lines = [
            f"DOCUMENTO: {dossier.document_title}",
            f"NATUREZA DOCUMENTAL: {plan.overview.document_nature}",
            f"CAPÍTULO {chapter.order} ({chapter.chapter_id}): {chapter.title}",
            f"OBJETIVO DO CAPÍTULO: {chapter.pedagogical_objective}",
            f"SECÇÃO ALVO ({section.section_id}): {section.title}",
            f"PAPEL EDITORIAL: {section.content_role}",
            f"OBJETIVO PEDAGÓGICO DA SECÇÃO: {section.pedagogical_objective}",
            f"ESTRATÉGIA DE EXPLICAÇÃO: {section.explanation_strategy}",
            f"ELEMENTOS PEDAGÓGICOS PLANEADOS: {', '.join(section.planned_pedagogical_elements)}",
        ]

        # Conteúdos obrigatórios a cobrir
        if section.contents_to_cover:
            header_lines.append("\nCONTEÚDOS OBRIGATÓRIOS A COBRIR NESTA SECÇÃO:")
            for idx, item in enumerate(section.contents_to_cover, start=1):
                st = normalize_epistemic_status(item.get("epistemic_status"), default="UNVERIFIED")
                pids = ", ".join(item.get("paragraph_ids") or [])
                pgs = ", ".join(str(p) for p in (item.get("page_numbers") or []))
                loc = f" [¶{pids} | p.{pgs}]" if (pids or pgs) else ""
                header_lines.append(f"  {idx}. [{st}]{loc} {item.get('summary', '')}")

        # Tratamentos pedagógicos planeados na Fase 4
        if section.pedagogical_treatments:
            header_lines.append("\nESPECIFICAÇÕES DE PROFUNDIDADE PEDAGÓGICA (FASE 4):")
            for pt in section.pedagogical_treatments[:5]:
                focus_str = "; ".join(f"{k}={v}" for k, v in (pt.pedagogical_focus or {}).items() if v)
                header_lines.append(
                    f"  - Tópico: {pt.target_topic_or_concept} | Nível: {pt.depth_level} | "
                    f"Elementos: {', '.join(pt.required_elements)} | Foco: {focus_str}"
                )

        # Análises de secção correspondentes na Fase 3
        linked_analyses = [
            sa for sa in dossier.section_analyses if sa.section_id in set(section.original_section_ids)
        ]
        if linked_analyses:
            header_lines.append("\nANÁLISE ACADÉMICA DAS SECÇÕES ORIGINAIS (FASE 3):")
            for sa in linked_analyses[:3]:
                synth = getattr(sa, "in_depth_synthesis", "") or getattr(sa, "objective", "")
                header_lines.append(f"  * [{sa.section_id}] {sa.title}: {synth}")
                for idea in getattr(sa, "core_ideas", [])[:4]:
                    header_lines.append(f"    - [CORE_IDEA] {idea}")
                for ref in getattr(sa, "source_refs", [])[:4]:
                    loc = f"p.{ref.page_number} ¶{ref.paragraph_id}" if ref.page_number else (ref.paragraph_id or "")
                    excerpt = ref.excerpt or ""
                    header_lines.append(f"    - [{ref.status}] [{loc}] {excerpt}")

        # Conceitos relevantes
        target_cids = set(section.associated_concept_ids + section.introduced_concept_ids)
        concepts_list = getattr(dossier, "conceptual_analysis", [])
        concepts = [c for c in concepts_list if c.concept_id in target_cids]
        if concepts:
            header_lines.append("\nCONCEITOS ASSOCIADOS A DEFINIR E RELACIONAR:")
            for c in concepts[:6]:
                defn = getattr(c, "definition", "") or getattr(c, "explanation", "")
                header_lines.append(f"  - [{c.concept_id}] {c.name}: {defn[:240]}")

        # Contexto específico de Metodologia ou Resultados quando aplicável
        role_upper = section.content_role.upper()
        if "METHOD" in role_upper or "METOD" in section.title.upper():
            ma = getattr(dossier, "methodology_analysis", None)
            if ma and (getattr(ma, "methodological_design", "") or getattr(ma, "data_sources", [])):
                m_design = getattr(ma, "methodological_design", "") or getattr(ma, "research_type", "")
                m_sources = ", ".join(getattr(ma, "data_sources", []))
                header_lines.append(f"\nDADOS DE METODOLOGIA (FASE 3): Desenho={m_design} | Amostra/Dados={m_sources}")
        if "RESULT" in role_upper or "EMPIR" in role_upper:
            results_list = getattr(dossier, "results_and_evidence", [])
            if results_list:
                header_lines.append("\nRESULTADOS EMPÍRICOS REGISTADOS (FASE 3):")
                for rf in results_list[:5]:
                    header_lines.append(f"  - {rf.statement} ({rf.evidence_data})")

        base_context = "\n".join(header_lines)
        used_tokens = self.budget.estimate_tokens(base_context)
        remaining_tokens = max(0, avail_tokens - used_tokens - 350)

        # Se a AST estiver disponível e houver orçamento, incluir excertos diretos dos parágrafos originais
        if ast is not None and remaining_tokens > 200:
            target_pids = {r.paragraph_id for r in section.evidence_refs if r.paragraph_id}
            target_sids = set(section.original_section_ids)
            candidate_paras = [
                p for p in ast.paragraphs
                if p.paragraph_id in target_pids or p.section_id in target_sids
            ]
            para_lines: List[str] = []
            acc_tokens = 0
            for p in candidate_paras[:10]:
                line = f"  [{p.paragraph_id} | p.{p.page_number}] {p.text[:380]}"
                t_est = self.budget.estimate_tokens(line)
                if acc_tokens + t_est > remaining_tokens:
                    break
                para_lines.append(line)
                acc_tokens += t_est
            if para_lines:
                base_context += "\n\nEXCERTOS TEXTUAIS DIRETOS DA FONTE ORIGINAL (AST FASE 2):\n" + "\n".join(para_lines)

        return base_context

    def _call_model_with_retries(
        self,
        *,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        validator: Callable[[Dict[str, Any]], Tuple[bool, str]],
        strict_validation: bool = True,
        telemetry: DocumentGenerationTelemetry,
        failed_operations: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        last_error = "Sem resposta do modelo local."
        cur_user_prompt = user_prompt

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                telemetry.llm_retries_count += 1

            caller_res = self.llm_caller(
                operation=f"{operation}_try{attempt + 1}",
                system_prompt=system_prompt,
                user_prompt=cur_user_prompt,
                max_output_tokens=max_output_tokens,
            )
            telemetry.llm_calls_count += 1

            parsed: Optional[Any] = None
            obs: Dict[str, Any] = {}
            if isinstance(caller_res, tuple):
                if len(caller_res) >= 2:
                    parsed, obs = caller_res[0], caller_res[1]
                elif len(caller_res) == 1:
                    parsed = caller_res[0]
                if not isinstance(obs, dict):
                    obs = {}
                if parsed is not None and "parsed" not in obs:
                    obs["parsed"] = parsed
                    obs["ok"] = True
            elif isinstance(caller_res, dict):
                obs = caller_res
                parsed = obs.get("parsed")
            else:
                obs = {"ok": False, "error": "Resposta de formato inesperado do LLM caller."}

            telemetry.prompt_tokens_total += int(obs.get("prompt_tokens") or 0)
            telemetry.completion_tokens_total += int(obs.get("completion_tokens") or 0)

            if not obs.get("ok"):
                last_error = str(obs.get("error") or "Erro na chamada ao modelo Ollama local.")
                continue

            parsed = obs.get("parsed")
            if not isinstance(parsed, dict):
                raw_text = str(obs.get("raw_text") or "")
                cleaned = clean_qwen_json(raw_text)
                try:
                    import json
                    candidate = json.loads(cleaned)
                    if isinstance(candidate, dict):
                        parsed = candidate
                except Exception as exc:
                    last_error = f"JSON inválido ({exc})"
                    parsed = None

            if not isinstance(parsed, dict):
                cur_user_prompt = (
                    user_prompt
                    + f"\n\n[CORREÇÃO OBRIGATÓRIA — TENTATIVA {attempt + 2}]: "
                    f"A resposta anterior falhou ({last_error}). Devolve APENAS um objeto JSON válido."
                )
                continue

            is_valid, reason = validator(parsed)
            if is_valid:
                return parsed

            last_error = f"Falha de validação estrutural: {reason}"
            cur_user_prompt = (
                user_prompt
                + f"\n\n[CORREÇÃO OBRIGATÓRIA — TENTATIVA {attempt + 2}]: "
                f"A tua resposta JSON anterior foi rejeitada pelo validador: {reason}. "
                "Corrige estritamente este problema e preserva todos os identificadores exatos."
            )

        failed_operations.append({
            "operation": operation,
            "error": last_error,
            "strict_rejected": bool(strict_validation),
            "timestamp": datetime.now().isoformat(),
        })
        return None

