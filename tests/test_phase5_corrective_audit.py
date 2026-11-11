"""
JARVIS OS — Study Engine Phase 5: Targeted Corrective Audit Regression Tests
Cobre os cenários obrigatórios identificados na auditoria (30 testes de regressão):
- Problema 1 (8 testes): Integridade Epistémica e Proveniência
- Problema 2 (12 testes): Paginação, Medição Real, Fragmentação, DOCX e Verificação Física QA
- Problema 3 (10 testes): Consistência de Fingerprints, Recuperação Parcial e Persistência Atómica de Checkpoints
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List
from unittest.mock import patch

import pymupdf
from PIL import Image
import pytest

from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ConceptItem,
    DocumentCoreAnalysis,
    EpistemicStatus,
    EvidenceRef,
    SectionAnalysis,
)
from services.document_generation_engine import DocumentGenerationEngine
from services.document_intelligence import (
    ASTParagraph,
    ASTSection,
    AcademicDocumentAST,
    DocumentMetadata,
    PageInfo,
)
from services.editorial_intelligence_engine import (
    EditorialChapter,
    EditorialOverview,
    EditorialPlanMetadata,
    EditorialQAReport,
    EditorialSection,
    EditorialStudyPlan,
    PedagogicalExplanationSpec,
)
from services.study_document_generation.content_generator import (
    AcademicContentEnricher,
    PROMPT_VERSIONS_PHASE5,
)
from services.study_document_generation.contracts import (
    CalloutBoxKind,
    DevelopedChapterContent,
    DevelopedContentBlock,
    DevelopedSectionContent,
    DevelopedStudyDocumentContent,
    ElaborationType,
    IRBibliographyEntry,
    IRBlock,
    IRBlockKind,
    IRChapter,
    IRDocumentMetadata,
    IRPaginationHint,
    IRSection,
    IRTOCEntry,
    StudyDocumentIR,
    compute_ast_fingerprint,
    compute_plan_fingerprint,
    compute_plan_overview_fingerprint,
    compute_section_plan_fingerprint,
)
from services.study_document_generation.design_system import ACADEMIC_EDITORIAL_CLASSIC
from services.study_document_generation.ir_compiler import DocumentStructureCompiler
from services.study_document_generation.layout_composer import (
    DOCXDocumentComposer,
    DocumentRenderResult,
    PDFDocumentComposer,
)
from services.study_document_generation.orchestrator import DocumentGenerationOrchestrator
from services.study_document_generation.provenance_renderer import ReferenceAndProvenanceRenderer
from services.study_document_generation.qa_engine import DocumentQualityAssuranceEngine


# ============================================================================
# Fixtures Base Reutilizáveis
# ============================================================================

def _build_base_ast() -> AcademicDocumentAST:
    return AcademicDocumentAST(
        document_id="doc_audit_p5",
        source_sha256="sha_base_audit_001",
        filename="artigo_auditoria.pdf",
        metadata=DocumentMetadata(
            title="Auditoria Epistémica e Composição Editorial",
            authors=[{"name": "Investigador Principal"}],
            publication_date={"year": 2026},
        ),
        pages=[
            PageInfo(page_number=1, width=595.28, height=841.89),
            PageInfo(page_number=2, width=595.28, height=841.89),
        ],
        sections=[
            ASTSection(section_id="sec_orig_01", title="1. Fundamentos", level=1, page_start=1, page_end=1),
            ASTSection(section_id="sec_orig_02", title="2. Resultados", level=1, page_start=2, page_end=2),
        ],
        paragraphs=[
            ASTParagraph(
                paragraph_id="p_01",
                section_id="sec_orig_01",
                text="A execução local de modelos garante privacidade absoluta dos dados académicos sem dependência cloud.",
                page_number=1,
                page_end=1,
                order=1,
            ),
            ASTParagraph(
                paragraph_id="p_02",
                section_id="sec_orig_02",
                text="Nos ensaios controlados, a latência média desceu para 48 milissegundos com precisão de 96.2 porcento.",
                page_number=2,
                page_end=2,
                order=2,
            ),
        ],
    )


def _build_base_dossier() -> AcademicReasoningDossier:
    return AcademicReasoningDossier(
        dossier_id="dos_audit_001",
        document_id="doc_audit_p5",
        source_sha256="sha_base_audit_001",
        document_analysis=DocumentCoreAnalysis(
            document_id="doc_audit_p5",
            title="Auditoria Epistémica e Composição Editorial",
            central_thesis="Inferência local preserva soberania com alta precisão.",
        ),
        section_analyses=[
            SectionAnalysis(
                section_id="sec_orig_01",
                title="1. Fundamentos",
                in_depth_synthesis="Análise introdutória sobre privacidade e execução local.",
                core_ideas=["Execução local elimina exposição de dados a terceiros."],
                source_refs=[
                    EvidenceRef(
                        section_id="sec_orig_01",
                        paragraph_id="p_01",
                        page_number=1,
                        excerpt="execução local garante privacidade",
                        status=EpistemicStatus.SOURCE_FACT.value,
                    )
                ],
            ),
            SectionAnalysis(
                section_id="sec_orig_02",
                title="2. Resultados",
                in_depth_synthesis="Avaliação quantitativa de latência e precisão.",
                core_ideas=["Latência média registada de 48 milissegundos."],
                source_refs=[
                    EvidenceRef(
                        section_id="sec_orig_02",
                        paragraph_id="p_02",
                        page_number=2,
                        excerpt="latência média desceu para 48 milissegundos",
                        status=EpistemicStatus.SOURCE_FACT.value,
                    )
                ],
            ),
        ],
        conceptual_analysis=[
            ConceptItem(
                concept_id="c_local",
                name="Inferência Local",
                definition="Execução integral de modelos de linguagem em hardware dedicado do utilizador.",
                explanation="Previne fugas de informação para servidores externos.",
                evidence_refs=[
                    EvidenceRef(
                        section_id="sec_orig_01",
                        paragraph_id="p_01",
                        page_number=1,
                        excerpt="execução local",
                        status=EpistemicStatus.SOURCE_FACT.value,
                    )
                ],
            )
        ],
    )


def _build_base_plan() -> EditorialStudyPlan:
    return EditorialStudyPlan(
        metadata=EditorialPlanMetadata(
            plan_id="plan_audit_001",
            document_id="doc_audit_p5",
            source_sha256="sha_base_audit_001",
            ast_version="1.0",
            dossier_id="dos_audit_001",
            plan_version=1,
            created_at="2026-11-11T00:00:00",
            status="COMPLETED",
        ),
        overview=EditorialOverview(
            central_theme="Privacidade e Desempenho em Inferência Local",
            central_theme_status="MODEL_INFERENCE",
            learning_objectives=[
                {"objective_id": "OBJ_1", "description": "Compreender a arquitetura local.", "epistemic_status": "SOURCE_FACT"},
                {"objective_id": "OBJ_2", "description": "Avaliar latência e precisão empírica.", "epistemic_status": "SOURCE_FACT"},
            ],
            target_audience="Investigadores",
            document_nature="EMPIRICAL_RESEARCH_ARTICLE",
            editorial_strategy="Progressão didática com rigor factual.",
        ),
        chapters=[
            EditorialChapter(
                chapter_id="chap_01",
                title="Fundamentos Teóricos",
                pedagogical_objective="Dominar princípios de soberania computacional.",
                role_in_progression="Base",
                editorial_justification="Essencial para contextualização.",
                original_section_ids=["sec_orig_01"],
                evidence_refs=[EvidenceRef(section_id="sec_orig_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")],
                sections=[
                    EditorialSection(
                        section_id="ed_sec_01",
                        chapter_id="chap_01",
                        title="Princípios de Soberania",
                        order=1,
                        pedagogical_objective="Explicar o conceito de execução local.",
                        explanation_strategy="Definição conceptual + exemplos.",
                        original_section_ids=["sec_orig_01"],
                        associated_concept_ids=["c_local"],
                        evidence_refs=[EvidenceRef(section_id="sec_orig_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")],
                    )
                ],
            ),
            EditorialChapter(
                chapter_id="chap_02",
                title="Validação Quantitativa",
                pedagogical_objective="Analisar os resultados experimentais.",
                role_in_progression="Empírica",
                editorial_justification="Prova experimental.",
                original_section_ids=["sec_orig_02"],
                evidence_refs=[EvidenceRef(section_id="sec_orig_02", paragraph_id="p_02", page_number=2, status="SOURCE_FACT")],
                sections=[
                    EditorialSection(
                        section_id="ed_sec_02",
                        chapter_id="chap_02",
                        title="Desempenho Medido",
                        order=1,
                        pedagogical_objective="Interpretar as métricas de 48 ms.",
                        explanation_strategy="Análise comparativa rigorosa.",
                        original_section_ids=["sec_orig_02"],
                        evidence_refs=[EvidenceRef(section_id="sec_orig_02", paragraph_id="p_02", page_number=2, status="SOURCE_FACT")],
                    )
                ],
            ),
        ],
        qa_report=EditorialQAReport(validation_status="VALID", is_valid=True),
    )


# ============================================================================
# PROBLEMA 1 — INTEGRIDADE EPISTÉMICA E PROVENIÊNCIA (Testes 1.1 a 1.8)
# ============================================================================

def test_p1_01_block_without_epistemic_status_is_not_source_fact():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    prov = ReferenceAndProvenanceRenderer(dos, ast)
    sec = plan.chapters[0].sections[0]

    raw_llm = {
        "section_id": "ed_sec_01",
        "opening_contextualization": "Contextualização pedagógica.",
        "content_blocks": [
            {
                "block_type": "EXPLANATORY_PARAGRAPH",
                "title": "Bloco Sem Classificação",
                "body_paragraphs": ["Texto produzido pelo modelo sem campo epistemic_status."],
            }
        ],
    }
    dev = AcademicContentEnricher.build_enriched_section(sec, raw_llm, dos, ast, prov)
    blk = dev.content_blocks[0]
    assert blk.epistemic_status != "SOURCE_FACT"
    assert blk.epistemic_status == "UNVERIFIED"


def test_p1_02_concept_definition_without_classification_is_not_source_fact():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    prov = ReferenceAndProvenanceRenderer(dos, ast)
    sec = plan.chapters[0].sections[0]

    raw_llm = {
        "section_id": "ed_sec_01",
        "content_blocks": [
            {"block_type": "THEORETICAL_CONTEXT", "title": "Base", "body_paragraphs": ["Enquadramento."], "epistemic_status": "MODEL_INFERENCE"}
        ],
        "concept_definitions": [
            {
                "term": "Conceito Novo Sem Classificação",
                "developed_definition": "Definição elaborada pelo LLM sem campo epistemic_status.",
            }
        ],
    }
    dev = AcademicContentEnricher.build_enriched_section(sec, raw_llm, dos, ast, prov)
    target = next(c for c in dev.concept_definitions if c.term == "Conceito Novo Sem Classificação")
    assert target.epistemic_status != "SOURCE_FACT"
    assert target.epistemic_status == "UNVERIFIED"


def test_p1_03_comparison_without_classification_is_not_source_fact():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    prov = ReferenceAndProvenanceRenderer(dos, ast)
    sec = plan.chapters[0].sections[0]

    raw_llm = {
        "section_id": "ed_sec_01",
        "content_blocks": [
            {"block_type": "EXPLANATORY_PARAGRAPH", "title": "Texto", "body_paragraphs": ["Corpo."], "epistemic_status": "MODEL_INFERENCE"}
        ],
        "comparisons": [
            {
                "dimension": "Custo Computacional",
                "item_a_label": "Local",
                "item_a_description": "Sem custo por token externo.",
                "item_b_label": "Cloud",
                "item_b_description": "Cobrança recorrente.",
            }
        ],
    }
    dev = AcademicContentEnricher.build_enriched_section(sec, raw_llm, dos, ast, prov)
    assert len(dev.comparisons) == 1
    assert dev.comparisons[0].epistemic_status != "SOURCE_FACT"
    assert dev.comparisons[0].epistemic_status == "UNVERIFIED"


def test_p1_04_hypothetical_example_stays_model_inference():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    prov = ReferenceAndProvenanceRenderer(dos, ast)
    sec = plan.chapters[0].sections[0]

    raw_llm = {
        "section_id": "ed_sec_01",
        "content_blocks": [
            {
                "block_type": "HYPOTHETICAL_EXAMPLE",
                "title": "Caso Ilustrativo",
                "body_paragraphs": ["Exemplo hipotético: imagine um laboratório hospitalar offline com p_01."],
                "is_hypothetical_example": True,
                "epistemic_status": "SOURCE_FACT",  # Tentativa indevida de promoção
                "paragraph_ids": ["p_01"],
            }
        ],
    }
    dev = AcademicContentEnricher.build_enriched_section(sec, raw_llm, dos, ast, prov)
    blk = dev.content_blocks[0]
    assert blk.is_hypothetical_example is True
    assert blk.epistemic_status == "MODEL_INFERENCE"
    assert blk.elaboration_type == ElaborationType.HYPOTHETICAL_EXAMPLE.value


def test_p1_05_developed_explanation_does_not_inherit_source_fact_from_section():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    prov = ReferenceAndProvenanceRenderer(dos, ast)
    sec = plan.chapters[0].sections[0]
    assert all(r.status == "SOURCE_FACT" for r in sec.evidence_refs)

    # 1. Caminho LLM (explicação / mecanismo marcado erroneamente como SOURCE_FACT pelo modelo)
    raw_llm = {
        "section_id": "ed_sec_01",
        "opening_contextualization": "Esta secção expande pedagogicamente os conceitos.",
        "content_blocks": [
            {
                "block_type": "STEP_BY_STEP_MECHANISM",
                "title": "Mecanismo Explicado pelo Qwen",
                "body_paragraphs": ["Explicação passo a passo elaborada pelo modelo com base na secção."],
                "steps": ["Passo 1: isolamento de rede", "Passo 2: inferência local"],
                "epistemic_status": "SOURCE_FACT",
                "paragraph_ids": ["p_01"],
            }
        ],
        "section_synthesis": "Síntese editorial da secção.",
    }
    dev_llm = AcademicContentEnricher.build_enriched_section(sec, raw_llm, dos, ast, prov)
    assert dev_llm.epistemic_status == "MODEL_INFERENCE"
    assert dev_llm.content_blocks[0].epistemic_status == "MODEL_INFERENCE"
    assert dev_llm.content_blocks[0].elaboration_type == ElaborationType.PEDAGOGICAL_EXPLANATION.value

    # 2. Caminho determinístico (fallback) + compilação IR
    dev_det = AcademicContentEnricher.build_enriched_section(sec, None, dos, ast, prov)
    assert dev_det.epistemic_status == "MODEL_INFERENCE"

    compiler = DocumentStructureCompiler(plan, dos, ast, prov)
    content = DevelopedStudyDocumentContent(
        document_id=plan.metadata.document_id,
        plan_id=plan.metadata.plan_id,
        chapters=[
            DevelopedChapterContent(
                chapter_id="chap_01",
                title="Cap 1",
                order=1,
                pedagogical_objective="Obj",
                chapter_introduction="Introdução redigida para enquadramento.",
                sections=[dev_llm],
                evidence_refs=sec.evidence_refs,
            )
        ],
    )
    ir = compiler.compile(content)
    intro_blk = next(b for b in ir.chapters[0].intro_blocks if b.block_id.startswith("intro_p_"))
    open_blk = next(b for b in ir.chapters[0].sections[0].blocks if b.block_id.startswith("open_"))
    assert intro_blk.epistemic_status == "MODEL_INFERENCE"
    assert open_blk.epistemic_status == "MODEL_INFERENCE"


def test_p1_06_nonexistent_paragraph_ref_is_rejected():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    prov = ReferenceAndProvenanceRenderer(dos, ast)
    sec = plan.chapters[0].sections[0]

    raw_llm = {
        "section_id": "ed_sec_01",
        "content_blocks": [
            {
                "block_type": "EXPLANATORY_PARAGRAPH",
                "title": "Bloco Com Ref Inventada",
                "body_paragraphs": ["A execução local melhora significativamente o desempenho computacional."],
                "epistemic_status": "SOURCE_FACT",
                "paragraph_ids": ["p_inexistente_999"],
            }
        ],
    }
    dev = AcademicContentEnricher.build_enriched_section(sec, raw_llm, dos, ast, prov)
    blk = dev.content_blocks[0]
    assert not any(r.paragraph_id == "p_inexistente_999" for r in blk.evidence_refs)
    assert "p_inexistente_999" in blk.rejected_reference_ids
    assert blk.epistemic_status != "SOURCE_FACT"
    assert blk.epistemic_status == "UNVERIFIED"


def test_p1_07_existing_ref_does_not_promote_unvalidated_content_to_source_fact():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    prov = ReferenceAndProvenanceRenderer(dos, ast)
    sec = plan.chapters[0].sections[0]

    raw_llm = {
        "section_id": "ed_sec_01",
        "content_blocks": [
            # Caso A: Tem p_01 real, mas sem epistemic_status -> mantém UNVERIFIED
            {
                "block_type": "EXPLANATORY_PARAGRAPH",
                "title": "Bloco Sem Status Mas Com p_01",
                "body_paragraphs": ["A execução local de modelos garante privacidade dos dados."],
                "paragraph_ids": ["p_01"],
            },
            # Caso B: Tem p_01 real E o LLM rotulou SOURCE_FACT, mas o conteúdo não tem suporte em p_01
            {
                "block_type": "EXPLANATORY_PARAGRAPH",
                "title": "Bloco Desconexo Com p_01",
                "body_paragraphs": ["Receitas gastronómicas mediterrânicas com azeite e alecrim melhoram a digestão."],
                "epistemic_status": "SOURCE_FACT",
                "paragraph_ids": ["p_01"],
            },
        ],
    }
    dev = AcademicContentEnricher.build_enriched_section(sec, raw_llm, dos, ast, prov)
    blk_a, blk_b = dev.content_blocks[0], dev.content_blocks[1]
    assert blk_a.epistemic_status == "UNVERIFIED"
    assert any(r.paragraph_id == "p_01" for r in blk_a.evidence_refs)
    assert blk_b.epistemic_status == "UNVERIFIED"
    assert blk_b.epistemic_status != "SOURCE_FACT"


def test_p1_08_pdf_distinguishes_facts_inferences_and_unverified():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    prov = ReferenceAndProvenanceRenderer(dos, ast)
    sec = plan.chapters[0].sections[0]

    raw_llm = {
        "section_id": "ed_sec_01",
        "content_blocks": [
            {
                "block_type": "EXPLANATORY_PARAGRAPH",
                "title": "Evidência Factual Direta",
                "body_paragraphs": ["A execução local de modelos garante privacidade absoluta dos dados académicos."],
                "epistemic_status": "SOURCE_FACT",
                "paragraph_ids": ["p_01"],
            },
            {
                "block_type": "CAUSE_EFFECT_ANALYSIS",
                "title": "Inferência Analítica Derivada",
                "body_paragraphs": ["Consequentemente, arquiteturas offline tendem a reduzir riscos de conformidade."],
                "epistemic_status": "MODEL_INFERENCE",
                "paragraph_ids": ["p_01"],
            },
            {
                "block_type": "EXPLANATORY_PARAGRAPH",
                "title": "Afirmação Não Confirmada",
                "body_paragraphs": ["Supõe-se redução de 12 porcento em custos de energia elétrica."],
                "epistemic_status": "UNVERIFIED",
            },
            {
                "block_type": "HYPOTHETICAL_EXAMPLE",
                "title": "Cenário Simulado",
                "body_paragraphs": ["Exemplo hipotético: imagine um servidor clínico isolado."],
                "is_hypothetical_example": True,
                "epistemic_status": "MODEL_INFERENCE",
            },
        ],
    }
    dev_sec = AcademicContentEnricher.build_enriched_section(sec, raw_llm, dos, ast, prov)
    content = DevelopedStudyDocumentContent(
        document_id=plan.metadata.document_id,
        plan_id=plan.metadata.plan_id,
        document_title="Teste Distinção Epistémica PDF",
        chapters=[
            DevelopedChapterContent(
                chapter_id="chap_01",
                title="Capítulo Único",
                order=1,
                pedagogical_objective="Distinguir factos e inferências.",
                sections=[dev_sec],
            )
        ],
    )
    compiler = DocumentStructureCompiler(plan, dos, ast, prov)
    ir = compiler.compile(content)

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "epistemic_distinction.pdf"
        res = PDFDocumentComposer(ACADEMIC_EDITORIAL_CLASSIC).compose_pdf(ir, pdf_path)
        assert not res.render_overflow_errors

        doc = pymupdf.open(str(pdf_path))
        full_text = "\n".join(p.get_text() for p in doc)
        doc.close()

        assert "[SOURCE_FACT]" in full_text
        assert "[MODEL_INFERENCE]" in full_text
        assert "[UNVERIFIED]" in full_text
        assert "Exemplo Ilustrativo Hipotético" in full_text


# ============================================================================
# PROBLEMA 2 — PAGINAÇÃO E PREVENÇÃO DE PERDA DE CONTEÚDO (Testes 2.1 a 2.10)
# ============================================================================

def _make_minimal_ir(
    *,
    blocks: List[IRBlock],
    learning_objectives: List[str] = None,
    toc_entries: List[IRTOCEntry] = None,
    bibliography: List[IRBibliographyEntry] = None,
    chapters: List[IRChapter] = None,
) -> StudyDocumentIR:
    objs = learning_objectives or ["OBJ_1: Compreender os fundamentos."]
    if chapters is None:
        sec_blocks = [
            IRBlock(
                block_id="h_sec_1",
                kind=IRBlockKind.HEADING.value,
                chapter_id="ch_1",
                section_id="s_1",
                level=2,
                title="1.1 — Secção de Teste Extensivo",
                pagination=IRPaginationHint(keep_with_next=True, min_follow_height_pt=50.0),
            )
        ] + blocks
        chapters = [
            IRChapter(
                chapter_id="ch_1",
                number_label="Capítulo 1",
                title="Capítulo Único de Teste",
                order=1,
                intro_blocks=[
                    IRBlock(
                        block_id="h_ch_1",
                        kind=IRBlockKind.HEADING.value,
                        chapter_id="ch_1",
                        level=1,
                        title="Capítulo 1 — Capítulo Único de Teste",
                        pagination=IRPaginationHint(keep_with_next=True, min_follow_height_pt=50.0),
                    )
                ],
                sections=[
                    IRSection(
                        section_id="s_1",
                        chapter_id="ch_1",
                        number_label="1.1",
                        title="Secção de Teste Extensivo",
                        level=2,
                        order=1,
                        blocks=sec_blocks,
                    )
                ],
            )
        ]
    tocs = toc_entries or [
        IRTOCEntry(entry_id="toc_1", level=1, number_label="Capítulo 1", title="Capítulo Único de Teste", target_block_id="h_ch_1"),
        IRTOCEntry(entry_id="toc_2", level=2, number_label="1.1", title="Secção de Teste Extensivo", target_block_id="h_sec_1"),
    ]
    bib = bibliography or [
        IRBibliographyEntry(ref_id="SRC_1", citation_label="[Fonte 1]", formatted_reference="Documento de Validação Integral em Engenharia de Software (2026).")
    ]
    return StudyDocumentIR(
        metadata=IRDocumentMetadata(
            document_id="doc_pag_test",
            ir_id="ir_pag_01",
            title="Teste Estrutural de Paginação e Zero Truncagem",
            subtitle="Verificação Tipográfica Multi-Página",
            authors=["Equipa QA"],
            design_profile_id="ACADEMIC_EDITORIAL_CLASSIC",
        ),
        learning_objectives=objs,
        toc_entries=tocs,
        chapters=chapters,
        bibliography=bib,
    )


def _make_dummy_plan_from_ir(ir: StudyDocumentIR) -> EditorialStudyPlan:
    plan_chaps = []
    for ch in ir.chapters:
        secs = [
            EditorialSection(section_id=s.section_id, chapter_id=ch.chapter_id, title=s.title, order=s.order)
            for s in ch.sections
        ]
        plan_chaps.append(
            EditorialChapter(
                chapter_id=ch.chapter_id,
                title=ch.title,
                pedagogical_objective="Objetivo",
                role_in_progression="Corpo",
                editorial_justification="Teste",
                sections=secs,
            )
        )
    return EditorialStudyPlan(
        metadata=EditorialPlanMetadata(plan_id="p_pag", document_id=ir.metadata.document_id),
        overview=EditorialOverview(central_theme="Teste"),
        chapters=plan_chaps,
    )


def test_p2_01_multipage_paragraph_zero_content_loss():
    long_sentences = [
        f"SENTENCA_PAG_{i:03d}: O processamento local garante consistência algorítmica e rastreabilidade integral."
        for i in range(1, 140)
    ]
    mega_para = " ".join(long_sentences) + " MARCADOR_FINAL_ABSOLUTO_PARAGRAFO_UNICO."
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="mega_p",
                kind=IRBlockKind.PARAGRAPH.value,
                chapter_id="ch_1",
                section_id="s_1",
                paragraphs=[mega_para],
                epistemic_status="MODEL_INFERENCE",
            )
        ]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "multipage_para.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert not res.render_overflow_errors
        assert res.pages_count >= 5

        doc = pymupdf.open(str(pdf_path))
        all_txt = "\n".join(p.get_text() for p in doc)
        doc.close()

        assert "SENTENCA_PAG_001" in all_txt
        assert "SENTENCA_PAG_070" in all_txt
        assert "SENTENCA_PAG_139" in all_txt
        assert "MARCADOR_FINAL_ABSOLUTO_PARAGRAFO_UNICO" in all_txt

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        assert qa.is_valid is True


def test_p2_02_dozens_of_list_items_fully_rendered():
    items = [f"ITEM_LISTA_{i:02d}: Propriedade analítica verificada no contexto estrutural número {i}." for i in range(1, 65)]
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="long_list",
                kind=IRBlockKind.NUMBERED_LIST.value,
                chapter_id="ch_1",
                section_id="s_1",
                level=1,
                items=items,
                epistemic_status="MODEL_INFERENCE",
            )
        ]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "long_list.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert not res.render_overflow_errors

        doc = pymupdf.open(str(pdf_path))
        all_txt = "\n".join(p.get_text() for p in doc)
        doc.close()

        for idx in (1, 20, 45, 64):
            assert f"ITEM_LISTA_{idx:02d}" in all_txt

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        assert qa.is_valid is True


def test_p2_03_tall_callout_box_exceeding_one_page_is_fragmented_without_loss():
    box_paras = [
        f"CAIXA_PARAGRAFO_{i:02d}: Aprofundamento detalhado da caixa pedagógica com extensão superior a uma folha A4 completa."
        for i in range(1, 35)
    ] + ["CAIXA_FECHO_FINAL_OBRIGATORIO."]
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="mega_callout",
                kind=IRBlockKind.CALLOUT_BOX.value,
                chapter_id="ch_1",
                section_id="s_1",
                title="Caixa Pedagógica Gigante",
                callout_kind=CalloutBoxKind.CONCEPT_BOX.value,
                paragraphs=box_paras,
                epistemic_status="MODEL_INFERENCE",
            )
        ]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "tall_callout.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert not res.render_overflow_errors
        assert res.pages_count >= 4

        doc = pymupdf.open(str(pdf_path))
        all_txt = "\n".join(p.get_text() for p in doc)
        doc.close()

        assert "CAIXA_PARAGRAFO_01" in all_txt
        assert "CAIXA_PARAGRAFO_34" in all_txt
        assert "CAIXA_FECHO_FINAL_OBRIGATORIO" in all_txt
        assert "(Continuação)" in all_txt

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        assert qa.is_valid is True


def test_p2_04_multipage_table_repeats_headers_and_preserves_long_cells():
    rows = [
        [
            f"VAR_{r:02d}",
            f"Descrição completa sem corte aos trinta e oito caracteres para a linha de teste número {r:02d}.",
            f"{90.0 + r * 0.1:.1f}%",
        ]
        for r in range(1, 46)
    ]
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="mega_tbl",
                kind=IRBlockKind.TABLE.value,
                chapter_id="ch_1",
                section_id="s_1",
                title="Tabela Empírica Extensa",
                table_headers=["Identificador Longo de Variável", "Descrição Sem Truncagem Silenciosa", "Métrica Medida"],
                table_rows=rows,
                epistemic_status="SOURCE_FACT",
            )
        ]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "multipage_table.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert not res.render_overflow_errors

        doc = pymupdf.open(str(pdf_path))
        pages_txt = [p.get_text() for p in doc]
        all_txt = "\n".join(pages_txt)
        doc.close()

        # Verificar repetição do cabeçalho em páginas subsequentes de tabela
        norm_all = " ".join(all_txt.split())
        pages_with_header = sum(1 for pt in pages_txt if "Métrica Medida" in pt or "Identificador Longo" in pt)
        assert pages_with_header >= 2
        assert "linha de teste número 01" in norm_all
        assert "linha de teste número 45" in norm_all

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        assert qa.is_valid is True


def test_p2_05_image_and_caption_stay_atomic_when_remaining_space_insufficient():
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = Path(tmpdir) / "fig_test.png"
        Image.new("RGB", (800, 500), color=(40, 80, 140)).save(str(img_path))

        # Ocupar ~75% da página 2 com parágrafo antes da imagem para forçar a imagem + legenda irem para a página 3
        filler_paras = [f"BLOCO_PREENCHIMENTO_{i}: Texto introdutório ocupando espaço superior da página." for i in range(1, 24)]
        ir = _make_minimal_ir(
            blocks=[
                IRBlock(
                    block_id="filler_p",
                    kind=IRBlockKind.PARAGRAPH.value,
                    chapter_id="ch_1",
                    section_id="s_1",
                    paragraphs=filler_paras,
                    epistemic_status="MODEL_INFERENCE",
                ),
                IRBlock(
                    block_id="vis_atomic",
                    kind=IRBlockKind.VISUAL_ELEMENT.value,
                    chapter_id="ch_1",
                    section_id="s_1",
                    title="Diagrama Atómico",
                    caption="LEGENDA_ATOMICA_UNIFICADA com explicação acoplada à imagem.",
                    image_path=str(img_path),
                    image_width_px=800,
                    image_height_px=500,
                    epistemic_status="SOURCE_FACT",
                ),
            ]
        )
        pdf_path = Path(tmpdir) / "atomic_visual.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert not res.render_overflow_errors

        doc = pymupdf.open(str(pdf_path))
        img_pages = [i for i, p in enumerate(doc) if p.get_image_info()]
        cap_pages = [i for i, p in enumerate(doc) if "LEGENDA_ATOMICA_UNIFICADA" in p.get_text()]
        doc.close()

        assert len(img_pages) == 1
        assert img_pages == cap_pages  # Imagem e legenda na EXATA mesma página

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        assert qa.is_valid is True


def test_p2_06_many_chapters_and_sections_paginate_toc_and_bookmarks():
    chapters: List[IRChapter] = []
    tocs: List[IRTOCEntry] = []
    for c_idx in range(1, 13):
        ch_id = f"ch_{c_idx:02d}"
        h_ch_id = f"h_{ch_id}"
        tocs.append(
            IRTOCEntry(
                entry_id=f"toc_{ch_id}",
                level=1,
                number_label=f"Capítulo {c_idx}",
                title=f"Título Extenso do Capítulo {c_idx:02d}",
                target_block_id=h_ch_id,
            )
        )
        secs: List[IRSection] = []
        for s_idx in range(1, 5):
            s_id = f"sec_{c_idx:02d}_{s_idx:02d}"
            h_s_id = f"h_{s_id}"
            tocs.append(
                IRTOCEntry(
                    entry_id=f"toc_{s_id}",
                    level=2,
                    number_label=f"{c_idx}.{s_idx}",
                    title=f"Subtópico Académico {c_idx:02d}.{s_idx:02d}",
                    target_block_id=h_s_id,
                )
            )
            secs.append(
                IRSection(
                    section_id=s_id,
                    chapter_id=ch_id,
                    number_label=f"{c_idx}.{s_idx}",
                    title=f"Subtópico Académico {c_idx:02d}.{s_idx:02d}",
                    level=2,
                    order=s_idx,
                    blocks=[
                        IRBlock(
                            block_id=h_s_id,
                            kind=IRBlockKind.HEADING.value,
                            chapter_id=ch_id,
                            section_id=s_id,
                            level=2,
                            title=f"{c_idx}.{s_idx} — Subtópico Académico {c_idx:02d}.{s_idx:02d}",
                            pagination=IRPaginationHint(keep_with_next=True, min_follow_height_pt=45.0),
                        ),
                        IRBlock(
                            block_id=f"p_{s_id}",
                            kind=IRBlockKind.PARAGRAPH.value,
                            chapter_id=ch_id,
                            section_id=s_id,
                            paragraphs=[f"Conteúdo desenvolvido da secção {s_id}."],
                            epistemic_status="MODEL_INFERENCE",
                        ),
                    ],
                )
            )
        chapters.append(
            IRChapter(
                chapter_id=ch_id,
                number_label=f"Capítulo {c_idx}",
                title=f"Título Extenso do Capítulo {c_idx:02d}",
                order=c_idx,
                intro_blocks=[
                    IRBlock(
                        block_id=h_ch_id,
                        kind=IRBlockKind.HEADING.value,
                        chapter_id=ch_id,
                        level=1,
                        title=f"Capítulo {c_idx} — Título Extenso do Capítulo {c_idx:02d}",
                        pagination=IRPaginationHint(keep_with_next=True, page_break_before=(c_idx > 1), min_follow_height_pt=45.0),
                    )
                ],
                sections=secs,
            )
        )

    ir = _make_minimal_ir(blocks=[], toc_entries=tocs, chapters=chapters)
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "many_chapters.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert res.frontmatter_pages >= 2
        assert not res.render_overflow_errors

        doc = pymupdf.open(str(pdf_path))
        fm_text = "\n".join(doc[i].get_text() for i in range(res.frontmatter_pages))
        # Todas as 48 secções + 12 capítulos devem constar no índice visual (sem break na pág 1)
        assert "Subtópico Académico 01.01" in fm_text
        assert "Subtópico Académico 12.04" in fm_text

        # Verificar que existem links internos distribuídos pelas páginas de frontmatter
        links_count = sum(len(doc[i].get_links()) for i in range(res.frontmatter_pages))
        assert links_count == 60
        doc.close()

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        assert qa.is_valid is True


def test_p2_07_more_than_three_learning_objectives_all_preserved():
    objs = [
        f"OBJ_{i:02d}: Dominar competência pedagógica especializada de nível {i:02d} com fundamentação empírica."
        for i in range(1, 10)
    ]
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="b_ok",
                kind=IRBlockKind.PARAGRAPH.value,
                chapter_id="ch_1",
                section_id="s_1",
                paragraphs=["Parágrafo base válido."],
                epistemic_status="MODEL_INFERENCE",
            )
        ],
        learning_objectives=objs,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "many_objectives.pdf"
        docx_path = Path(tmpdir) / "many_objectives.docx"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        DOCXDocumentComposer().compose_docx(ir, docx_path)

        doc = pymupdf.open(str(pdf_path))
        all_txt = "\n".join(p.get_text() for p in doc)
        doc.close()

        for i in range(1, 10):
            assert f"OBJ_{i:02d}" in all_txt

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, docx_path=docx_path, render_result=res
        )
        assert qa.is_valid is True


def test_p2_08_full_ir_text_and_many_bib_entries_recoverable_from_pdf():
    bib = [
        IRBibliographyEntry(
            ref_id=f"REF_{i:02d}",
            citation_label=f"[{i:02d}]",
            formatted_reference=f"Autor_{i:02d} (2025). Referência bibliográfica auditável número {i:02d} sobre sistemas locais.",
        )
        for i in range(1, 38)
    ]
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="p_recov",
                kind=IRBlockKind.PARAGRAPH.value,
                chapter_id="ch_1",
                section_id="s_1",
                paragraphs=["MARCADOR_CORPO_INICIAL texto substantivo intermédio MARCADOR_CORPO_TERMINAL."],
                epistemic_status="SOURCE_FACT",
            )
        ],
        bibliography=bib,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "bib_multi.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert res.backmatter_pages >= 2

        doc = pymupdf.open(str(pdf_path))
        all_txt = "\n".join(p.get_text() for p in doc)
        doc.close()

        assert "Autor_01" in all_txt
        assert "Autor_37" in all_txt
        assert "MARCADOR_CORPO_TERMINAL" in all_txt

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        assert qa.is_valid is True


def test_p2_09_all_rendered_content_within_page_useful_bounds():
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="p_bounds",
                kind=IRBlockKind.PARAGRAPH.value,
                chapter_id="ch_1",
                section_id="s_1",
                paragraphs=["URLContínuoMuitoLongoParaTestarQuebraSemTransbordoHorizontal_" + "X" * 110],
                epistemic_status="MODEL_INFERENCE",
            )
        ]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "bounds_check.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert not res.render_overflow_errors

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        assert qa.no_text_clipping_verified is True
        assert qa.is_valid is True


def test_p2_10_qa_detects_clipping_vertical_overflow_and_missing_content():
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="expected_blk",
                kind=IRBlockKind.PARAGRAPH.value,
                chapter_id="ch_1",
                section_id="s_1",
                paragraphs=["CONTEUDO_ESPERADO_COMPLETO que deveria estar presente integralmente no PDF."],
                epistemic_status="MODEL_INFERENCE",
            )
        ]
    )
    plan = _make_dummy_plan_from_ir(ir)
    dos = _build_base_dossier()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Caso A: Construir PDF com texto fora da margem direita e abaixo da margem inferior + falta de conteúdo esperado
        bad_pdf = Path(tmpdir) / "clipped.pdf"
        doc = pymupdf.open()
        p1 = doc.new_page(width=595.28, height=841.89)
        p1.insert_text(pymupdf.Point(62, 100), "Capa incompleta")
        p2 = doc.new_page(width=595.28, height=841.89)
        # Transbordo direito (x1 > margin_right = 541) e vertical (y1 > max_content_y = 781)
        p2.insert_text(pymupdf.Point(555, 200), "TextoForaDaMargemDireita")
        p2.insert_text(pymupdf.Point(70, 825), "TextoAbaixoDoLimiteInferior")
        doc.save(str(bad_pdf))
        doc.close()

        fake_render_res = DocumentRenderResult(
            file_path=str(bad_pdf),
            pages_count=2,
            render_overflow_errors=[{"block_id": "expected_blk", "overflow_rc": -12.5}],
        )
        qa_report = DocumentQualityAssuranceEngine().audit(
            ir, plan, dos, pdf_path=bad_pdf, render_result=fake_render_res
        )
        codes = {f.code for f in qa_report.findings}
        assert qa_report.is_valid is False
        assert qa_report.no_text_clipping_verified is False
        assert "TEXT_CLIPPING" in codes
        assert "VERTICAL_OVERFLOW" in codes
        assert "CONTENT_LOST_IN_PDF" in codes
        assert "RENDER_OVERFLOW_LOSS" in codes


def test_p2_11_docx_table_export_does_not_fail_on_frozen_profile():
    from docx import Document as DocxDocument

    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="docx_tbl",
                kind=IRBlockKind.TABLE.value,
                chapter_id="ch_1",
                section_id="s_1",
                title="Tabela Comparativa DOCX",
                table_headers=["Métrica", "Valor"],
                table_rows=[["F1-Score", "0.91"], ["AUC", "0.95"]],
                epistemic_status="SOURCE_FACT",
                provenance_summary="Facto confirmado na fonte [p. 1, p_1].",
            )
        ]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / "table_export.docx"
        res = DOCXDocumentComposer().compose_docx(ir, docx_path)
        assert docx_path.exists()
        assert res.file_size_bytes > 0
        d = DocxDocument(str(docx_path))
        assert len(d.tables) >= 1
        assert any(
            cell.text.strip() == "F1-Score"
            for tbl in d.tables
            for row in tbl.rows
            for cell in row.cells
        )


def test_p2_12_qa_handles_wrapped_long_url_before_trailing_punctuation():
    long_url_ref = (
        "[47] Nielsen, Global Consumers' Trust in ‘Earned’ Advertising Grows in Importance "
        "Retrieved from http://www.nielsen.com/us/en/press-room/2012/"
        "nielsen-global-consumerstrust-in-earned-advertising-grows-longpath-segment.html2012."
    )
    ir = _make_minimal_ir(
        blocks=[
            IRBlock(
                block_id="bib_ctx_blk",
                kind=IRBlockKind.PARAGRAPH.value,
                chapter_id="ch_1",
                section_id="s_1",
                paragraphs=["Parágrafo de secção para validar bibliografia com URL longo."],
                epistemic_status="MODEL_INFERENCE",
            )
        ],
        bibliography=[
            IRBibliographyEntry(
                ref_id="ref_47",
                citation_label="[[47]]",
                formatted_reference=long_url_ref,
            )
        ],
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "wrapped_url_bib.pdf"
        res = PDFDocumentComposer().compose_pdf(ir, pdf_path)
        assert not res.render_overflow_errors

        qa = DocumentQualityAssuranceEngine().audit(
            ir, _make_dummy_plan_from_ir(ir), _build_base_dossier(), pdf_path=pdf_path, render_result=res
        )
        codes = {f.code for f in qa.findings}
        assert "CONTENT_LOST_IN_PDF" not in codes
        assert qa.is_valid is True


# ============================================================================
# PROBLEMA 3 — CONSISTÊNCIA E ATOMICIDADE DE CHECKPOINTS (Testes 3.1 a 3.10)
# ============================================================================

def _make_llm_caller_with_counter(tag_text: str = "GERADO_NOVO"):
    calls: List[str] = []

    def _caller(*, operation: str, system_prompt: str, user_prompt: str, max_output_tokens: int) -> Dict[str, Any]:
        calls.append(operation)
        # Extrair section_id do prompt
        sec_id = "ed_sec_01"
        if "ed_sec_02" in operation:
            sec_id = "ed_sec_02"
        elif "ed_sec_01" in operation:
            sec_id = "ed_sec_01"

        return {
            "ok": True,
            "prompt_tokens": 100,
            "completion_tokens": 120,
            "parsed": {
                "sections": [
                    {
                        "section_id": sec_id,
                        "opening_contextualization": f"Abertura ({tag_text}) para {sec_id}.",
                        "content_blocks": [
                            {
                                "block_type": "EXPLANATORY_PARAGRAPH",
                                "title": f"Desenvolvimento {tag_text}",
                                "body_paragraphs": [f"Conteúdo académico {tag_text} específico de {sec_id}."],
                                "epistemic_status": "MODEL_INFERENCE",
                            }
                        ],
                        "section_synthesis": f"Síntese {tag_text} de {sec_id}.",
                    }
                ]
            },
        }

    return _caller, calls


def _seed_partial_checkpoint(
    storage_dir: Path,
    plan: EditorialStudyPlan,
    dos: AcademicReasoningDossier,
    ast: AcademicDocumentAST,
    *,
    tag: str = "CACHED_VALIDO",
    chapter_limit: int = 1,
    prompt_versions: Dict[str, str] = None,
    model_name: str = "qwen3.5:9b",
) -> Path:
    doc_id = plan.metadata.document_id
    doc_dir = storage_dir / "documents" / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    cp_path = doc_dir / "document_generation_checkpoint.json"

    from services.editorial_intelligence_engine import compute_dossier_fingerprint
    section_records: Dict[str, Any] = {}
    completed_chaps = []

    for ch in plan.chapters[:chapter_limit]:
        secs = []
        for sec in ch.sections:
            dev_sec = DevelopedSectionContent(
                section_id=sec.section_id,
                chapter_id=ch.chapter_id,
                title=sec.title,
                order=sec.order,
                pedagogical_objective=sec.pedagogical_objective,
                opening_contextualization=f"Abertura {tag} para {sec.section_id}.",
                content_blocks=[
                    DevelopedContentBlock(
                        block_id=f"{sec.section_id}_blk_01",
                        block_type="EXPLANATORY_PARAGRAPH",
                        title=f"Bloco {tag}",
                        body_paragraphs=[f"Conteúdo {tag} preservado para {sec.section_id}."],
                        epistemic_status="MODEL_INFERENCE",
                        elaboration_type=ElaborationType.PEDAGOGICAL_EXPLANATION.value,
                    )
                ],
                section_synthesis=f"Síntese {tag}.",
                epistemic_status="MODEL_INFERENCE",
            )
            secs.append(dev_sec)
            section_records[sec.section_id] = {
                "chapter_id": ch.chapter_id,
                "section_fingerprint": compute_section_plan_fingerprint(ch, sec, dossier=dos, ast=ast),
                "section_data": dev_sec.to_dict(),
            }
        completed_chaps.append(
            DevelopedChapterContent(
                chapter_id=ch.chapter_id,
                title=ch.title,
                order=ch.order,
                pedagogical_objective=ch.pedagogical_objective,
                sections=secs,
            ).to_dict()
        )

    payload = {
        "schema_version": "5.1.0",
        "document_id": doc_id,
        "plan_id": plan.metadata.plan_id,
        "plan_version": plan.metadata.plan_version,
        "plan_fingerprint": compute_plan_fingerprint(plan),
        "overview_fingerprint": compute_plan_overview_fingerprint(plan),
        "dossier_id": dos.dossier_id,
        "dossier_fingerprint": compute_dossier_fingerprint(dos),
        "ast_fingerprint": compute_ast_fingerprint(ast),
        "prompt_versions": dict(prompt_versions or PROMPT_VERSIONS_PHASE5),
        "model_name": model_name,
        "section_records": section_records,
        "chapters": completed_chaps,
    }
    cp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return cp_path


def test_p3_01_checkpoint_recovery_with_identical_fingerprints():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        _seed_partial_checkpoint(storage_dir, plan, dos, ast, tag="RECUPERADO_CH1", chapter_limit=1)

        caller, calls = _make_llm_caller_with_counter("FRESH_CH2")
        engine = DocumentGenerationEngine(storage_dir, llm_caller=caller)
        res = engine.generate_study_document(plan, dos, ast, export_docx=False, force_recompute=False)

        assert res.status == "COMPLETED"
        # Apenas ed_sec_02 deve chamar o LLM; ed_sec_01 foi recuperada do checkpoint
        assert len(calls) == 1
        assert "ed_sec_02" in calls[0]

        dev_json = json.loads(Path(res.developed_content_path).read_text(encoding="utf-8"))
        assert "RECUPERADO_CH1" in json.dumps(dev_json["chapters"][0])
        assert "FRESH_CH2" in json.dumps(dev_json["chapters"][1])


def test_p3_02_plan_version_change_invalidates_checkpoint():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan_v1 = _build_base_plan()
    plan_v2 = _build_base_plan()
    plan_v2.metadata.plan_version = 2

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        _seed_partial_checkpoint(storage_dir, plan_v1, dos, ast, tag="VELHO_V1", chapter_limit=2)

        caller, calls = _make_llm_caller_with_counter("NOVO_V2")
        engine = DocumentGenerationEngine(storage_dir, llm_caller=caller)
        res = engine.generate_study_document(plan_v2, dos, ast, export_docx=False, force_recompute=False)

        assert len(calls) == 2
        txt = Path(res.developed_content_path).read_text(encoding="utf-8")
        assert "VELHO_V1" not in txt
        assert "NOVO_V2" in txt


def test_p3_03_plan_content_change_with_same_ids_invalidates_checkpoint():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan_old = _build_base_plan()
    plan_new = _build_base_plan()
    # Mesmos plan_id, plan_version, chapter_id, section_id — mas conteúdo alterado
    plan_new.overview.central_theme = "Tema Editorial Completamente Reformulado"
    plan_new.chapters[0].sections[0].pedagogical_objective = "Novo objetivo pedagógico reformulado."

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        _seed_partial_checkpoint(storage_dir, plan_old, dos, ast, tag="CONTEUDO_ANTIGO_IDS", chapter_limit=2)

        caller, calls = _make_llm_caller_with_counter("CONTEUDO_REFORMULADO")
        engine = DocumentGenerationEngine(storage_dir, llm_caller=caller)
        res = engine.generate_study_document(plan_new, dos, ast, export_docx=False, force_recompute=False)

        assert len(calls) == 2
        txt = Path(res.developed_content_path).read_text(encoding="utf-8")
        assert "CONTEUDO_ANTIGO_IDS" not in txt
        assert "CONTEUDO_REFORMULADO" in txt


def test_p3_04_dossier_change_invalidates_checkpoint():
    ast = _build_base_ast()
    dos_old = _build_base_dossier()
    plan = _build_base_plan()
    dos_new = _build_base_dossier()
    dos_new.section_analyses[0].in_depth_synthesis = "Síntese do dossier atualizada na re-auditoria."

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        _seed_partial_checkpoint(storage_dir, plan, dos_old, ast, tag="DOSSIER_ANTIGO", chapter_limit=2)

        caller, calls = _make_llm_caller_with_counter("DOSSIER_NOVO")
        engine = DocumentGenerationEngine(storage_dir, llm_caller=caller)
        res = engine.generate_study_document(plan, dos_new, ast, export_docx=False, force_recompute=False)

        assert len(calls) == 2
        txt = Path(res.developed_content_path).read_text(encoding="utf-8")
        assert "DOSSIER_ANTIGO" not in txt
        assert "DOSSIER_NOVO" in txt


def test_p3_05_ast_change_invalidates_checkpoint():
    ast_old = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()
    ast_new = _build_base_ast()
    ast_new.source_sha256 = "sha_novo_reprocessado_999"
    ast_new.paragraphs[0].text = "Texto extraído atualizado após nova análise do PDF original."

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        _seed_partial_checkpoint(storage_dir, plan, dos, ast_old, tag="AST_ANTIGA", chapter_limit=2)

        caller, calls = _make_llm_caller_with_counter("AST_ATUALIZADA")
        engine = DocumentGenerationEngine(storage_dir, llm_caller=caller)
        res = engine.generate_study_document(plan, dos, ast_new, export_docx=False, force_recompute=False)

        assert len(calls) == 2
        txt = Path(res.developed_content_path).read_text(encoding="utf-8")
        assert "AST_ANTIGA" not in txt
        assert "AST_ATUALIZADA" in txt


def test_p3_06_prompt_version_change_invalidates_checkpoint():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        _seed_partial_checkpoint(
            storage_dir,
            plan,
            dos,
            ast,
            tag="PROMPT_ANTIGO",
            chapter_limit=2,
            prompt_versions={"section_content_development": "v5.0.0-antiga"},
        )

        caller, calls = _make_llm_caller_with_counter("PROMPT_ATUAL")
        engine = DocumentGenerationEngine(
            storage_dir,
            llm_caller=caller,
            prompt_versions={"section_content_development": "v5.2.0-nova"},
        )
        res = engine.generate_study_document(plan, dos, ast, export_docx=False, force_recompute=False)

        assert len(calls) == 2
        txt = Path(res.developed_content_path).read_text(encoding="utf-8")
        assert "PROMPT_ANTIGO" not in txt
        assert "PROMPT_ATUAL" in txt


def test_p3_07_corrupted_or_incomplete_checkpoint_rejected_safely():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        cp_path = storage_dir / "documents" / plan.metadata.document_id / "document_generation_checkpoint.json"
        cp_path.parent.mkdir(parents=True, exist_ok=True)
        # JSON truncado/corrompido
        cp_path.write_text('{"document_id": "doc_audit_p5", "chapters": [{"broken": ', encoding="utf-8")

        caller, calls = _make_llm_caller_with_counter("LIMPO_POS_CORRUPCAO")
        engine = DocumentGenerationEngine(storage_dir, llm_caller=caller)
        res = engine.generate_study_document(plan, dos, ast, export_docx=False, force_recompute=False)

        assert res.status == "COMPLETED"
        assert len(calls) == 2
        assert "LIMPO_POS_CORRUPCAO" in Path(res.developed_content_path).read_text(encoding="utf-8")


def test_p3_08_atomic_write_failure_preserves_previous_valid_checkpoint():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan = _build_base_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        cp_path = _seed_partial_checkpoint(storage_dir, plan, dos, ast, tag="CHECKPOINT_VALIOSO_ANTERIOR", chapter_limit=1)
        original_content = cp_path.read_text(encoding="utf-8")

        orch = DocumentGenerationOrchestrator(storage_dir)
        # Simular falha abrupta durante `os.replace` ao gravar novo checkpoint
        with patch("services.study_document_generation.orchestrator.os.replace", side_effect=OSError("Simulação de disco cheio")):
            with pytest.raises(OSError):
                orch._save_checkpoint_atomic(
                    cp_path,
                    doc_id=plan.metadata.document_id,
                    plan=plan,
                    dossier=dos,
                    plan_fp=compute_plan_fingerprint(plan),
                    overview_fp=compute_plan_overview_fingerprint(plan),
                    dossier_fp="x",
                    ast_fp="y",
                    prompt_versions=PROMPT_VERSIONS_PHASE5,
                    model_name="qwen3.5:9b",
                    section_records={},
                    completed_chapters=[],
                )

        # Checkpoint anterior tem de permanecer exatamente igual e válido
        assert cp_path.exists()
        assert cp_path.read_text(encoding="utf-8") == original_content
        assert "CHECKPOINT_VALIOSO_ANTERIOR" in cp_path.read_text(encoding="utf-8")
        # Nenhum ficheiro temporário solto pode permanecer
        leftovers = [p for p in cp_path.parent.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []


def test_p3_09_partial_recovery_preserves_valid_chapter_and_canonical_order():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan_base = _build_base_plan()

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        _seed_partial_checkpoint(storage_dir, plan_base, dos, ast, tag="RECOVERED_UNIT", chapter_limit=2)

        # Alterar APENAS o objetivo/estratégia da secção do Capítulo 2 (mantendo plan_version, overview, dossier, ast e Chap 1 iguais)
        plan_mod = _build_base_plan()
        plan_mod.chapters[1].sections[0].pedagogical_objective = "Objetivo específico alterado apenas no Capítulo 2."

        caller, calls = _make_llm_caller_with_counter("REPROCESSED_CH2")
        engine = DocumentGenerationEngine(storage_dir, llm_caller=caller)
        res = engine.generate_study_document(plan_mod, dos, ast, export_docx=False, force_recompute=False)

        # Apenas ed_sec_02 foi reprocessada; ed_sec_01 foi recuperada parcialmente
        assert len(calls) == 1
        assert "ed_sec_02" in calls[0]

        dev_json = json.loads(Path(res.developed_content_path).read_text(encoding="utf-8"))
        # Ordem original preservada estritamente: chap_01 depois chap_02
        assert [c["chapter_id"] for c in dev_json["chapters"]] == ["chap_01", "chap_02"]
        assert "RECOVERED_UNIT" in json.dumps(dev_json["chapters"][0])
        assert "REPROCESSED_CH2" in json.dumps(dev_json["chapters"][1])


def test_p3_10_stale_content_never_leaks_into_document_from_new_plan():
    ast = _build_base_ast()
    dos = _build_base_dossier()
    plan_old = _build_base_plan()
    plan_new = _build_base_plan()
    plan_new.metadata.plan_id = "plan_novo_999"

    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        _seed_partial_checkpoint(storage_dir, plan_old, dos, ast, tag="CONTEUDO_ANTIGO_OBSOLETO_XYZ", chapter_limit=2)

        caller, calls = _make_llm_caller_with_counter("CONTEUDO_NOVO_VALIDO_ABC")
        engine = DocumentGenerationEngine(storage_dir, llm_caller=caller)
        res = engine.generate_study_document(plan_new, dos, ast, export_docx=True, force_recompute=False)

        assert res.status == "COMPLETED"
        assert len(calls) == 2

        doc = pymupdf.open(str(res.pdf_path))
        pdf_txt = "\n".join(p.get_text() for p in doc)
        doc.close()

        assert "CONTEUDO_ANTIGO_OBSOLETO_XYZ" not in pdf_txt
        assert "CONTEUDO_NOVO_VALIDO_ABC" in pdf_txt
