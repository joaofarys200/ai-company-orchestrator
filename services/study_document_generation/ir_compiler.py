"""
JARVIS OS — Study Engine Phase 5: Document Structure Compiler (Componente 5.3)
Compila o conteúdo académico desenvolvido, os elementos visuais fundamentados,
as tabelas/equações originais e a bibliografia numa Representação Intermédia Semântica
(StudyDocumentIR) independente de formato e rigorosamente validável.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Sequence

from services.academic_reasoning_engine import AcademicReasoningDossier
from services.document_intelligence import AcademicDocumentAST
from services.editorial_intelligence_engine import EditorialStudyPlan
from services.study_document_generation.contracts import (
    CalloutBoxKind,
    DevelopedChapterContent,
    DevelopedContentBlock,
    DevelopedSectionContent,
    DevelopedStudyDocumentContent,
    ElaborationType,
    GeneratedVisualAsset,
    IRBibliographyEntry,
    IRBlock,
    IRBlockKind,
    IRChapter,
    IRDocumentMetadata,
    IRHeaderFooterSpec,
    IRPaginationHint,
    IRSection,
    IRTOCEntry,
    StudyDocumentIR,
    normalize_epistemic_status,
)
from services.study_document_generation.design_system import DesignStyleProfile
from services.study_document_generation.provenance_renderer import ReferenceAndProvenanceRenderer


class DocumentStructureCompiler:
    """
    Componente 5.3 — Document Structure Compiler.
    Agrega todas as fontes estruturadas numa árvore semântica `StudyDocumentIR`.
    """

    def __init__(
        self,
        arg1: Any = None,
        arg2: Any = None,
        arg3: Any = None,
        arg4: Any = None,
        profile: Optional[DesignStyleProfile] = None,
        provenance: Optional[ReferenceAndProvenanceRenderer] = None,
    ) -> None:
        from services.study_document_generation.design_system import ACADEMIC_EDITORIAL_CLASSIC
        self.default_plan: Optional[EditorialStudyPlan] = None
        self.default_dossier: Optional[AcademicReasoningDossier] = None
        self.default_ast: Optional[AcademicDocumentAST] = None

        if isinstance(arg1, DesignStyleProfile):
            self.profile = arg1
            self.provenance = arg2
        elif isinstance(arg1, EditorialStudyPlan):
            self.default_plan = arg1
            self.default_dossier = arg2
            self.default_ast = arg3
            self.provenance = arg4 or provenance
            self.profile = profile or ACADEMIC_EDITORIAL_CLASSIC
        else:
            self.profile = profile or (arg1 if isinstance(arg1, DesignStyleProfile) else ACADEMIC_EDITORIAL_CLASSIC)
            self.provenance = provenance or (arg2 if isinstance(arg2, ReferenceAndProvenanceRenderer) else None)

    def compile(
        self,
        developed: DevelopedStudyDocumentContent,
        plan: Any = None,
        dossier: Any = None,
        visual_assets: Sequence[GeneratedVisualAsset] = (),
        ast: Optional[AcademicDocumentAST] = None,
        style_profile: Optional[DesignStyleProfile] = None,
    ) -> StudyDocumentIR:
        """
        Compila a representação intermédia semântica completa.
        Suporta chamadas flexíveis da orquestração e testes unitários.
        """
        if not isinstance(plan, EditorialStudyPlan):
            if isinstance(plan, (list, tuple)):
                visual_assets = plan
            plan = self.default_plan
            dossier = self.default_dossier
            ast = ast or self.default_ast

        if style_profile is not None:
            self.profile = style_profile

        if plan is None:
            raise ValueError("DocumentStructureCompiler requer um EditorialStudyPlan válido para compilar a IR.")

        ir_id = f"ir_{uuid.uuid4().hex[:12]}"
        meta = self._compile_metadata(developed, plan, dossier, ir_id, ast)

        # Mapa de visuais indexados por (target_chapter_id, target_section_id)
        visuals_by_sec: Dict[str, List[GeneratedVisualAsset]] = {}
        for va in visual_assets:
            sec_key = va.target_section_id or va.target_chapter_id
            visuals_by_sec.setdefault(sec_key, []).append(va)

        # 1. Visão Geral Executiva (Abertura do Documento de Estudo)
        overview_blocks = self._compile_executive_overview_blocks(developed, plan, dossier)

        # 2. Objetivos de Aprendizagem
        learning_objs: List[str] = []
        for lo in plan.overview.learning_objectives:
            if isinstance(lo, dict):
                oid = str(lo.get("objective_id", "")).strip()
                desc = str(lo.get("description", "")).strip()
                st = normalize_epistemic_status(lo.get("epistemic_status"), default="UNVERIFIED")
            else:
                oid = str(getattr(lo, "objective_id", "")).strip()
                desc = str(getattr(lo, "description", "")).strip()
                st = normalize_epistemic_status(getattr(lo, "epistemic_status", None), default="UNVERIFIED")
            if desc:
                learning_objs.append(f"{oid}: {desc} [{st}]" if oid else f"{desc} [{st}]")
        if not learning_objs:
            learning_objs = [
                f"Compreender aprofundadamente a problemática central de «{developed.document_title}».",
                "Analisar com rigor as metodologias, evidências empíricas e interpretações reportadas.",
                "Consolidar as relações conceptuais e implicações teóricas do documento.",
            ]

        # 3. Capítulos e Secções Semânticos
        ir_chapters: List[IRChapter] = []
        toc_entries: List[IRTOCEntry] = []

        for ch in developed.chapters:
            plan_ch = next((c for c in plan.chapters if c.chapter_id == ch.chapter_id), None)
            ir_ch, ch_toc = self._compile_chapter(
                ch=ch,
                plan_ch=plan_ch,
                visuals_by_sec=visuals_by_sec,
                ast=ast,
            )
            ir_chapters.append(ir_ch)
            toc_entries.extend(ch_toc)

        # 4. Síntese Global Transversal
        global_synth_blocks = self._compile_global_synthesis(developed, plan, dossier)

        # 5. Referências Bibliográficas e Notas de Proveniência (Componente 5.7)
        bib_entries, prov_notes = self.provenance.compile_bibliography()

        # 6. Cabeçalhos e Rodapés
        doc_short_title = developed.document_title[:45] if developed.document_title else "Caderno de Estudo"
        header_footer = IRHeaderFooterSpec(
            running_header_left="JARVIS OS • Study Engine",
            running_header_right=doc_short_title,
            footer_left=f"{self.profile.display_name} • Proveniência Auditada",
            footer_center="",
            show_page_numbers=True,
            show_epistemic_notice=True,
        )

        return StudyDocumentIR(
            metadata=meta,
            executive_overview_blocks=overview_blocks,
            learning_objectives=learning_objs,
            toc_entries=toc_entries,
            chapters=ir_chapters,
            global_synthesis_blocks=global_synth_blocks,
            bibliography=bib_entries,
            provenance_summary_notes=prov_notes,
            header_footer=header_footer,
        )

    def _compile_metadata(
        self,
        developed: DevelopedStudyDocumentContent,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
        ir_id: str,
        ast: Optional[AcademicDocumentAST],
    ) -> IRDocumentMetadata:
        orig_fname = ""
        authors: List[str] = []
        year: Optional[str] = None
        venue: Optional[str] = None

        if ast is not None and getattr(ast, "metadata", None) is not None:
            orig_fname = getattr(ast.metadata, "filename", "") or ""
            raw_authors = getattr(ast.metadata, "authors", []) or []
            authors = []
            for a in raw_authors:
                if isinstance(a, dict):
                    name = a.get("name") or a.get("raw") or str(a)
                    authors.append(name)
                else:
                    authors.append(str(a))
            pub_date = getattr(ast.metadata, "publication_date", None)
            if isinstance(pub_date, dict):
                year = str(pub_date.get("year", "")) or None
            elif pub_date:
                year = str(pub_date)
            else:
                year = getattr(ast.metadata, "year", None)
            venue = getattr(ast.metadata, "journal_or_venue", None) or getattr(ast.metadata, "venue", None)

        doc_title = (
            developed.document_title
            or getattr(dossier, "document_title", None)
            or (getattr(ast.metadata, "title", None) if ast and getattr(ast, "metadata", None) else None)
            or "Caderno Académico de Estudo"
        )

        return IRDocumentMetadata(
            document_id=developed.document_id,
            ir_id=ir_id,
            title=doc_title,
            subtitle=developed.document_subtitle or plan.overview.central_theme or "Estudo Aprofundado & Rigor Epistémico",
            original_filename=orig_fname,
            authors=authors,
            year=year,
            publication_venue=venue,
            subject=getattr(dossier, "domain", "Investigação Académica"),
            language="pt-PT",
            design_profile_id=self.profile.profile_id,
            plan_id=developed.plan_id,
            plan_version=developed.plan_version,
            dossier_fingerprint=developed.dossier_fingerprint,
            plan_fingerprint=developed.plan_fingerprint,
            created_at=developed.created_at,
            model_name=developed.model_name,
        )

    def _compile_executive_overview_blocks(
        self,
        developed: DevelopedStudyDocumentContent,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
    ) -> List[IRBlock]:
        blocks: List[IRBlock] = []

        # Bloco de Tema Central e Enquadramento
        theme_txt = plan.overview.central_theme
        strat_txt = plan.overview.editorial_strategy or plan.overview.global_organization_summary
        aud_txt = f"Público-alvo e estratégia pedagógica: {plan.overview.target_audience}."

        blocks.append(
            IRBlock(
                block_id="overview_theme_block",
                kind=IRBlockKind.CALLOUT_BOX.value,
                title="Âmbito & Visão Geral do Documento de Estudo",
                callout_kind=CalloutBoxKind.CONCEPT_BOX.value,
                paragraphs=[theme_txt, strat_txt, aud_txt],
                epistemic_status=normalize_epistemic_status(plan.overview.central_theme_status, default="MODEL_INFERENCE"),
                elaboration_type=ElaborationType.EDITORIAL_SYNTHESIS.value,
                provenance_summary="Visão Editorial & Metadados do Estudo (Fase 4)",
                pagination=IRPaginationHint(keep_together=True),
            )
        )

        if developed.executive_study_overview:
            blocks.append(
                IRBlock(
                    block_id="overview_exec_text",
                    kind=IRBlockKind.PARAGRAPH.value,
                    paragraphs=[developed.executive_study_overview],
                    epistemic_status="MODEL_INFERENCE",
                    pagination=IRPaginationHint(prevent_widow_orphan=True),
                )
            )

        return blocks

    def _compile_chapter(
        self,
        ch: DevelopedChapterContent,
        plan_ch: Optional[EditorialChapter],
        visuals_by_sec: Dict[str, List[GeneratedVisualAsset]],
        ast: Optional[AcademicDocumentAST],
    ) -> Tuple[IRChapter, List[IRTOCEntry]]:
        toc_entries: List[IRTOCEntry] = []
        ch_num = f"Capítulo {ch.order}"

        # Entrada no TOC para o Capítulo
        ch_entry_id = f"toc_ch_{ch.order}"
        ch_heading_block_id = f"heading_ch_{ch.chapter_id}"
        toc_entries.append(
            IRTOCEntry(
                entry_id=ch_entry_id,
                level=1,
                number_label=ch_num,
                title=ch.title,
                target_block_id=ch_heading_block_id,
            )
        )

        intro_blocks: List[IRBlock] = []

        # Título do Capítulo (Heading nível 1) com keep-with-next obrigatório
        intro_blocks.append(
            IRBlock(
                block_id=ch_heading_block_id,
                kind=IRBlockKind.HEADING.value,
                chapter_id=ch.chapter_id,
                level=1,
                number_label=ch_num,
                title=f"{ch_num} — {ch.title}",
                pagination=IRPaginationHint(
                    keep_with_next=True,
                    page_break_before=(ch.order > 1),  # Capítulos subsequentes quebram página
                    min_follow_height_pt=self.profile.geometry.min_heading_follow_pt,
                ),
            )
        )

        # Introdução e Objetivo Pedagógico do Capítulo (elaboração editorial = MODEL_INFERENCE)
        if ch.chapter_introduction:
            intro_blocks.append(
                IRBlock(
                    block_id=f"intro_p_{ch.chapter_id}",
                    kind=IRBlockKind.PARAGRAPH.value,
                    chapter_id=ch.chapter_id,
                    paragraphs=[ch.chapter_introduction],
                    epistemic_status="MODEL_INFERENCE",
                    elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
                    evidence_refs=ch.evidence_refs,
                    provenance_summary=self.provenance.format_provenance_summary(
                        "MODEL_INFERENCE",
                        ch.evidence_refs,
                        elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
                    ),
                    pagination=IRPaginationHint(prevent_widow_orphan=True),
                )
            )

        # Visuais ao nível de Capítulo (se existirem)
        for va in visuals_by_sec.get(ch.chapter_id, []):
            intro_blocks.append(self._compile_visual_block(va, ch.chapter_id, ""))

        # Compilar Secções do Capítulo
        ir_sections: List[IRSection] = []
        for s_idx, sec in enumerate(ch.sections, start=1):
            sec_num = f"{ch.order}.{s_idx}"
            ir_sec, sec_toc = self._compile_section(
                sec=sec,
                sec_num=sec_num,
                ch_id=ch.chapter_id,
                visuals_by_sec=visuals_by_sec,
                ast=ast,
            )
            ir_sections.append(ir_sec)
            toc_entries.extend(sec_toc)

        # Síntese do Capítulo
        synthesis_blocks: List[IRBlock] = []
        if ch.chapter_synthesis or ch.key_takeaways:
            synthesis_blocks.append(
                IRBlock(
                    block_id=f"synth_box_{ch.chapter_id}",
                    kind=IRBlockKind.CALLOUT_BOX.value,
                    chapter_id=ch.chapter_id,
                    title=f"Síntese e Pontos-Chave: {ch_num}",
                    callout_kind=CalloutBoxKind.SYNTHESIS_BOX.value,
                    paragraphs=[ch.chapter_synthesis] if ch.chapter_synthesis else [],
                    items=ch.key_takeaways,
                    epistemic_status="MODEL_INFERENCE",
                    pagination=IRPaginationHint(keep_together=True),
                )
            )

        ir_ch = IRChapter(
            chapter_id=ch.chapter_id,
            number_label=ch_num,
            title=ch.title,
            order=ch.order,
            pedagogical_objective=ch.pedagogical_objective,
            role_in_progression=ch.role_in_progression,
            intro_blocks=intro_blocks,
            sections=ir_sections,
            synthesis_blocks=synthesis_blocks,
            evidence_refs=ch.evidence_refs,
        )
        return ir_ch, toc_entries

    def _compile_section(
        self,
        sec: DevelopedSectionContent,
        sec_num: str,
        ch_id: str,
        visuals_by_sec: Dict[str, List[GeneratedVisualAsset]],
        ast: Optional[AcademicDocumentAST],
    ) -> Tuple[IRSection, List[IRTOCEntry]]:
        toc_entries: List[IRTOCEntry] = []
        sec_heading_id = f"heading_sec_{sec.section_id}"

        # Entrada no TOC para a Secção
        toc_entries.append(
            IRTOCEntry(
                entry_id=f"toc_sec_{sec.section_id}",
                level=2,
                number_label=sec_num,
                title=sec.title,
                target_block_id=sec_heading_id,
            )
        )

        blocks: List[IRBlock] = []

        # Título da Secção (Heading nível 2) com keep-with-next
        blocks.append(
            IRBlock(
                block_id=sec_heading_id,
                kind=IRBlockKind.HEADING.value,
                chapter_id=ch_id,
                section_id=sec.section_id,
                level=2,
                number_label=sec_num,
                title=f"{sec_num} — {sec.title}",
                pagination=IRPaginationHint(
                    keep_with_next=True,
                    min_follow_height_pt=self.profile.geometry.min_heading_follow_pt,
                ),
            )
        )

        # Abertura / Enquadramento da Secção (desenvolvimento pedagógico não herda SOURCE_FACT)
        if sec.opening_contextualization:
            open_st = normalize_epistemic_status(sec.epistemic_status, default="MODEL_INFERENCE")
            open_elab = sec.elaboration_type or ElaborationType.PEDAGOGICAL_EXPLANATION.value
            blocks.append(
                IRBlock(
                    block_id=f"open_{sec.section_id}",
                    kind=IRBlockKind.PARAGRAPH.value,
                    chapter_id=ch_id,
                    section_id=sec.section_id,
                    paragraphs=[sec.opening_contextualization],
                    epistemic_status=open_st,
                    elaboration_type=open_elab,
                    evidence_ids=list(sec.evidence_ids),
                    evidence_refs=sec.evidence_refs,
                    provenance_summary=self.provenance.format_provenance_summary(
                        open_st, sec.evidence_refs, elaboration_type=open_elab
                    ),
                    pagination=IRPaginationHint(prevent_widow_orphan=True),
                )
            )

        # Definições Desenvolvidas de Conceitos (em Caixas de Conceito)
        for cdef in sec.concept_definitions:
            c_paras = [cdef.developed_definition]
            if cdef.theoretical_context:
                c_paras.append(f"Contexto Teórico: {cdef.theoretical_context}")
            if cdef.relationships_explained:
                c_paras.append(f"Articulação Conceptual: {cdef.relationships_explained}")

            c_ep = normalize_epistemic_status(cdef.epistemic_status, default="UNVERIFIED")
            prov_lbl = self.provenance.format_provenance_summary(
                c_ep, cdef.evidence_refs, elaboration_type=cdef.elaboration_type
            )
            blocks.append(
                IRBlock(
                    block_id=f"cbox_{cdef.concept_id}",
                    kind=IRBlockKind.CALLOUT_BOX.value,
                    chapter_id=ch_id,
                    section_id=sec.section_id,
                    title=f"Conceito: {cdef.term}",
                    callout_kind=CalloutBoxKind.CONCEPT_BOX.value,
                    paragraphs=c_paras,
                    epistemic_status=c_ep,
                    elaboration_type=cdef.elaboration_type,
                    provenance_summary=prov_lbl,
                    evidence_ids=list(cdef.evidence_ids),
                    evidence_refs=cdef.evidence_refs,
                    pagination=IRPaginationHint(keep_together=True),
                )
            )

        # Blocos de Conteúdo Desenvolvido (Explicações, Mecanismos, Exemplos)
        for b in sec.content_blocks:
            blocks.extend(self._compile_content_block(b, ch_id, sec.section_id))

        # Quadros de Comparação entre Conceitos / Métodos
        if sec.comparisons:
            comp_headers = ["Dimensão de Análise", "Elemento A", "Elemento B", "Síntese", "Estado"]
            comp_rows: List[List[str]] = []
            cmp_statuses: List[str] = []
            cmp_refs = []
            for cmp_item in sec.comparisons:
                c_st = normalize_epistemic_status(cmp_item.epistemic_status, default="UNVERIFIED")
                cmp_statuses.append(c_st)
                cmp_refs.extend(cmp_item.evidence_refs or [])
                comp_rows.append([
                    cmp_item.dimension,
                    f"{cmp_item.item_a_label}: {cmp_item.item_a_description}",
                    f"{cmp_item.item_b_label}: {cmp_item.item_b_description}",
                    cmp_item.synthesis_note or "Síntese comparativa",
                    c_st,
                ])
            if all(s == "SOURCE_FACT" for s in cmp_statuses) and cmp_refs:
                tbl_st = "SOURCE_FACT"
                tbl_elab = ElaborationType.SOURCE_EXTRACTED.value
            elif "UNVERIFIED" in cmp_statuses or "NOT_FOUND" in cmp_statuses:
                tbl_st = "UNVERIFIED"
                tbl_elab = ElaborationType.UNVERIFIED_CLAIM.value
            else:
                tbl_st = "MODEL_INFERENCE"
                tbl_elab = ElaborationType.ANALYTICAL_INFERENCE.value

            blocks.append(
                IRBlock(
                    block_id=f"tbl_cmp_{sec.section_id}",
                    kind=IRBlockKind.TABLE.value,
                    chapter_id=ch_id,
                    section_id=sec.section_id,
                    title=f"Quadro Comparativo: {sec.title}",
                    caption="Comparação sistemática com preservação do estado epistémico por dimensão.",
                    table_headers=comp_headers,
                    table_rows=comp_rows,
                    epistemic_status=tbl_st,
                    elaboration_type=tbl_elab,
                    evidence_refs=cmp_refs[:6],
                    provenance_summary=self.provenance.format_provenance_summary(
                        tbl_st, cmp_refs, elaboration_type=tbl_elab
                    ),
                    pagination=IRPaginationHint(keep_together=False),
                )
            )

        # Elementos Visuais associados à Secção (Componente 5.4)
        for va in visuals_by_sec.get(sec.section_id, []):
            blocks.append(self._compile_visual_block(va, ch_id, sec.section_id))

        # Limitações e Fronteiras de Validade
        if sec.limitations_and_caveats:
            lim_st = "SOURCE_FACT" if sec.evidence_refs and any(r.status == "SOURCE_FACT" for r in sec.evidence_refs) else "MODEL_INFERENCE"
            blocks.append(
                IRBlock(
                    block_id=f"lim_box_{sec.section_id}",
                    kind=IRBlockKind.CALLOUT_BOX.value,
                    chapter_id=ch_id,
                    section_id=sec.section_id,
                    title="Limitações & Fronteiras de Validade da Secção",
                    callout_kind=CalloutBoxKind.LIMITATION_BOX.value,
                    items=sec.limitations_and_caveats,
                    epistemic_status=lim_st,
                    elaboration_type=ElaborationType.SOURCE_EXTRACTED.value if lim_st == "SOURCE_FACT" else ElaborationType.ANALYTICAL_INFERENCE.value,
                    evidence_refs=sec.evidence_refs[:4],
                    provenance_summary=self.provenance.format_provenance_summary(
                        lim_st, sec.evidence_refs[:4]
                    ),
                    pagination=IRPaginationHint(keep_together=True),
                )
            )

        # Síntese da Secção
        if sec.section_synthesis:
            blocks.append(
                IRBlock(
                    block_id=f"sec_synth_{sec.section_id}",
                    kind=IRBlockKind.PARAGRAPH.value,
                    chapter_id=ch_id,
                    section_id=sec.section_id,
                    paragraphs=[f"Síntese: {sec.section_synthesis}"],
                    epistemic_status="MODEL_INFERENCE",
                    elaboration_type=ElaborationType.EDITORIAL_SYNTHESIS.value,
                    provenance_summary=self.provenance.format_provenance_summary(
                        "MODEL_INFERENCE", sec.evidence_refs[:2], elaboration_type=ElaborationType.EDITORIAL_SYNTHESIS.value
                    ),
                    pagination=IRPaginationHint(prevent_widow_orphan=True),
                )
            )

        ir_sec = IRSection(
            section_id=sec.section_id,
            chapter_id=ch_id,
            number_label=sec_num,
            title=sec.title,
            level=sec.level,
            order=sec.order,
            pedagogical_objective=sec.pedagogical_objective,
            content_role=sec.content_role,
            blocks=blocks,
            evidence_refs=sec.evidence_refs,
        )
        return ir_sec, toc_entries

    def _compile_content_block(
        self,
        b: DevelopedContentBlock,
        ch_id: str,
        sec_id: str,
    ) -> List[IRBlock]:
        blocks: List[IRBlock] = []
        ep_status = normalize_epistemic_status(b.epistemic_status, default="UNVERIFIED")
        elab_type = b.elaboration_type or ""
        rej_cnt = len(getattr(b, "rejected_reference_ids", []) or [])
        prov_lbl = self.provenance.format_provenance_summary(
            ep_status,
            b.evidence_refs,
            is_hypothetical_example=b.is_hypothetical_example,
            elaboration_type=elab_type,
            source_table_refs=b.source_table_refs,
            source_figure_refs=b.source_figure_refs,
            rejected_refs_count=rej_cnt,
        )

        # Se for Exemplo Hipotético -> Caixa semântica HYPOTHETICAL_EXAMPLE_BOX
        if b.is_hypothetical_example:
            blocks.append(
                IRBlock(
                    block_id=b.block_id,
                    kind=IRBlockKind.CALLOUT_BOX.value,
                    chapter_id=ch_id,
                    section_id=sec_id,
                    title=b.title,
                    callout_kind=CalloutBoxKind.HYPOTHETICAL_EXAMPLE_BOX.value,
                    paragraphs=b.body_paragraphs,
                    items=b.bullet_points or b.steps,
                    epistemic_status="MODEL_INFERENCE",
                    elaboration_type=ElaborationType.HYPOTHETICAL_EXAMPLE.value,
                    is_hypothetical_example=True,
                    provenance_summary=prov_lbl,
                    evidence_ids=list(b.evidence_ids),
                    evidence_refs=b.evidence_refs,
                    pagination=IRPaginationHint(keep_together=True),
                )
            )
            return blocks

        # Se for Caixa Pedagógica Explícita (CALLOUT_BOX)
        if b.block_type == "CALLOUT_BOX":
            callout_k = CalloutBoxKind.CONCEPT_BOX.value
            if "WARNING" in b.title.upper() or "ATENÇÃO" in b.title.upper():
                callout_k = CalloutBoxKind.ATTENTION_BOX.value
            elif "SYNTHESIS" in b.title.upper() or "SÍNTESE" in b.title.upper():
                callout_k = CalloutBoxKind.SYNTHESIS_BOX.value
            elif "METHOD" in b.title.upper() or "MÉTODO" in b.title.upper():
                callout_k = CalloutBoxKind.METHODOLOGY_NOTE_BOX.value
            blocks.append(
                IRBlock(
                    block_id=b.block_id,
                    kind=IRBlockKind.CALLOUT_BOX.value,
                    chapter_id=ch_id,
                    section_id=sec_id,
                    title=b.title,
                    callout_kind=callout_k,
                    paragraphs=b.body_paragraphs,
                    items=b.bullet_points or b.steps,
                    epistemic_status=ep_status,
                    elaboration_type=elab_type,
                    provenance_summary=prov_lbl,
                    evidence_ids=list(b.evidence_ids),
                    evidence_refs=b.evidence_refs,
                    pagination=IRPaginationHint(keep_together=True),
                )
            )
            return blocks

        # Se for Mecanismo Passo a Passo -> Caixa MECHANISM_BOX
        if b.block_type == "STEP_BY_STEP_MECHANISM" or (b.steps and len(b.steps) > 1):
            blocks.append(
                IRBlock(
                    block_id=b.block_id,
                    kind=IRBlockKind.CALLOUT_BOX.value,
                    chapter_id=ch_id,
                    section_id=sec_id,
                    title=f"Mecanismo Passo a Passo: {b.title}",
                    callout_kind=CalloutBoxKind.MECHANISM_BOX.value,
                    paragraphs=b.body_paragraphs,
                    items=[f"Passo {idx}: {st}" for idx, st in enumerate(b.steps, start=1)],
                    epistemic_status=ep_status,
                    elaboration_type=elab_type,
                    provenance_summary=prov_lbl,
                    evidence_ids=list(b.evidence_ids),
                    evidence_refs=b.evidence_refs,
                    pagination=IRPaginationHint(keep_together=True),
                )
            )
            return blocks

        # Bloco de Explicação Normal com Subtítulo
        if b.title and b.title != sec_id:
            blocks.append(
                IRBlock(
                    block_id=f"h3_{b.block_id}",
                    kind=IRBlockKind.HEADING.value,
                    chapter_id=ch_id,
                    section_id=sec_id,
                    level=3,
                    title=b.title,
                    epistemic_status=ep_status,
                    pagination=IRPaginationHint(
                        keep_with_next=True,
                        min_follow_height_pt=self.profile.geometry.min_heading_follow_pt,
                    ),
                )
            )

        if b.body_paragraphs:
            blocks.append(
                IRBlock(
                    block_id=b.block_id,
                    kind=IRBlockKind.PARAGRAPH.value,
                    chapter_id=ch_id,
                    section_id=sec_id,
                    paragraphs=b.body_paragraphs,
                    epistemic_status=ep_status,
                    elaboration_type=elab_type,
                    provenance_summary="" if b.bullet_points else prov_lbl,
                    evidence_ids=list(b.evidence_ids),
                    evidence_refs=b.evidence_refs,
                    pagination=IRPaginationHint(prevent_widow_orphan=True),
                )
            )

        if b.bullet_points:
            blocks.append(
                IRBlock(
                    block_id=f"bullets_{b.block_id}",
                    kind=IRBlockKind.BULLET_LIST.value,
                    chapter_id=ch_id,
                    section_id=sec_id,
                    items=b.bullet_points,
                    epistemic_status=ep_status,
                    elaboration_type=elab_type,
                    provenance_summary=prov_lbl,
                    evidence_ids=list(b.evidence_ids),
                    evidence_refs=b.evidence_refs,
                    pagination=IRPaginationHint(prevent_widow_orphan=True),
                )
            )

        return blocks

    def _compile_visual_block(
        self,
        va: GeneratedVisualAsset,
        ch_id: str,
        sec_id: str,
    ) -> IRBlock:
        va_ep = normalize_epistemic_status(va.epistemic_status, default="UNVERIFIED")
        if va.render_status == "RENDERED_AS_TABLE" and va.table_headers and va.table_rows:
            return IRBlock(
                block_id=f"vis_tbl_{va.visual_id}",
                kind=IRBlockKind.TABLE.value,
                chapter_id=ch_id,
                section_id=sec_id,
                title=va.title,
                caption=va.caption,
                table_headers=va.table_headers,
                table_rows=va.table_rows,
                visual_id=va.visual_id,
                epistemic_status=va_ep,
                provenance_summary=va.provenance_label,
                evidence_refs=va.evidence_refs,
                pagination=IRPaginationHint(keep_together=False),
            )

        if va.image_path:
            return IRBlock(
                block_id=f"vis_img_{va.visual_id}",
                kind=IRBlockKind.VISUAL_ELEMENT.value,
                chapter_id=ch_id,
                section_id=sec_id,
                title=va.title,
                caption=va.caption,
                visual_id=va.visual_id,
                image_path=va.image_path,
                image_width_px=va.width_px,
                image_height_px=va.height_px,
                epistemic_status=va_ep,
                provenance_summary=va.provenance_label,
                evidence_refs=va.evidence_refs,
                pagination=IRPaginationHint(keep_together=True),
            )

        # Fallback de omissão justificada
        return IRBlock(
            block_id=f"vis_omit_{va.visual_id}",
            kind=IRBlockKind.CALLOUT_BOX.value,
            chapter_id=ch_id,
            section_id=sec_id,
            title=f"Elemento Visual Omitido: {va.title}",
            callout_kind=CalloutBoxKind.ATTENTION_BOX.value,
            paragraphs=[
                f"Justificação de rigor: {va.omission_or_fallback_reason or 'Dados insuficientes para renderização.'}"
            ],
            epistemic_status="MODEL_INFERENCE",
            elaboration_type=ElaborationType.EDITORIAL_SYNTHESIS.value,
            provenance_summary=va.provenance_label,
            pagination=IRPaginationHint(keep_together=True),
        )

    def _compile_global_synthesis(
        self,
        developed: DevelopedStudyDocumentContent,
        plan: EditorialStudyPlan,
        dossier: AcademicReasoningDossier,
    ) -> List[IRBlock]:
        blocks: List[IRBlock] = []

        css = getattr(dossier, "cross_section_synthesis", None)
        synth_txt = (
            developed.global_integrative_synthesis
            or (getattr(css, "global_synthesis", "") if css else "")
            or (getattr(css, "integrative_synthesis", "") if css else "")
            or "Síntese global integradora do estudo."
        )
        raw_takeaways = (
            getattr(css, "key_takeaways", None)
            or getattr(css, "argumentative_progression", None)
            or []
        )
        takeaway_items: List[str] = []
        for t in raw_takeaways[:6]:
            if isinstance(t, dict):
                s = t.get("statement") or t.get("text") or str(t)
                takeaway_items.append(s)
            elif hasattr(t, "statement"):
                takeaway_items.append(t.statement)
            else:
                takeaway_items.append(str(t))

        blocks.append(
            IRBlock(
                block_id="global_synth_heading",
                kind=IRBlockKind.HEADING.value,
                level=1,
                title="Síntese Global & Integração Transversal",
                pagination=IRPaginationHint(
                    keep_with_next=True,
                    page_break_before=True,
                    min_follow_height_pt=self.profile.geometry.min_heading_follow_pt,
                ),
            )
        )

        blocks.append(
            IRBlock(
                block_id="global_synth_callout",
                kind=IRBlockKind.CALLOUT_BOX.value,
                title="Conclusões Consolidadas & Quadro Epistémico Integrador",
                callout_kind=CalloutBoxKind.SYNTHESIS_BOX.value,
                paragraphs=[synth_txt] if synth_txt else [],
                items=takeaway_items,
                epistemic_status="MODEL_INFERENCE",
                provenance_summary="Síntese Transversal (Dossier Fase 3 & Planeamento Editorial Fase 4)",
                pagination=IRPaginationHint(keep_together=True),
            )
        )

        return blocks
