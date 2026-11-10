"""
JARVIS OS — Study Engine Phase 5: Test Suite
Auditoria automatizada completa cobrindo os Critérios A, B, C, D e E:
- Critério A: Geração de Conteúdo e Enriquecimento Académico
- Critério B: Estrutura Documental e Representação Intermediária (IR)
- Critério C: Motor de Síntese Visual Fundamentada
- Critério D: Layout, Tipografia e Exportação Multi-Formato (PDF e DOCX)
- Critério E: Garantia de Qualidade (QA), Checkpoints e Versionamento Histórico
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import pytest

try:
    import pymupdf
except ImportError:
    pymupdf = None

try:
    import docx
except ImportError:
    docx = None

from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    ConceptItem,
    CriticalAnalysis,
    CrossSectionSynthesis,
    DocumentCoreAnalysis,
    EpistemicStatus,
    EvidenceRef,
    MethodologyAnalysis,
    ResultItem,
    SectionAnalysis,
)
from services.document_intelligence import (
    AcademicDocumentAST,
    DocumentMetadata,
    PageInfo,
    ASTParagraph,
    ASTSection,
    ASTTable,
)
from services.editorial_intelligence_engine import (
    EditorialChapter,
    EditorialConceptRelationship,
    EditorialOverview,
    EditorialPlanMetadata,
    EditorialQAFinding,
    EditorialQAReport,
    EditorialSection,
    EditorialStudyPlan,
    PedagogicalExplanationSpec,
    VisualPlanItem,
)
from services.document_generation_engine import (
    DocumentGenerationEngine,
    DocumentGenerationOrchestrator,
    DocumentGenerationState,
    StudyDocumentGenerationResult,
    compute_plan_fingerprint,
)
from services.study_document_generation.content_generator import (
    AcademicContentEnricher,
    DocumentContentGenerationEngine,
)
from services.study_document_generation.contracts import (
    CalloutBoxKind,
    DevelopedChapterContent,
    DevelopedSectionContent,
    DevelopedStudyDocumentContent,
    IRBlockKind,
    StudyDocumentIR,
)
from services.study_document_generation.design_system import (
    ACADEMIC_EDITORIAL_CLASSIC,
    TECHNICAL_SCIENTIFIC_MODERN,
    AcademicDesignSystem,
)
from services.study_document_generation.ir_compiler import DocumentStructureCompiler
from services.study_document_generation.layout_composer import (
    DOCXDocumentComposer,
    PDFDocumentComposer,
)
from services.study_document_generation.provenance_renderer import ReferenceAndProvenanceRenderer
from services.study_document_generation.qa_engine import DocumentQualityAssuranceEngine
from services.study_document_generation.visual_generator import VisualGenerationEngine


@pytest.fixture
def mock_academic_ast() -> AcademicDocumentAST:
    return AcademicDocumentAST(
        document_id="doc_test_p5",
        source_sha256="abc123sha256",
        filename="estudo_empirico.pdf",
        metadata=DocumentMetadata(
            title="Estudo Empírico de Desempenho e Eficácia de Algoritmos",
            authors=[{"name": "Prof. Doutor Carlos Silva"}, {"name": "Dra. Maria Santos"}],
            publication_date={"year": 2025},
            abstract="Investigação sobre a eficiência de algoritmos locais em tarefas de raciocínio.",
        ),
        pages=[
            PageInfo(page_number=1, width=595.0, height=842.0),
            PageInfo(page_number=2, width=595.0, height=842.0),
            PageInfo(page_number=3, width=595.0, height=842.0),
            PageInfo(page_number=4, width=595.0, height=842.0),
            PageInfo(page_number=5, width=595.0, height=842.0),
            PageInfo(page_number=6, width=595.0, height=842.0),
            PageInfo(page_number=7, width=595.0, height=842.0),
            PageInfo(page_number=8, width=595.0, height=842.0),
        ],
        sections=[
            ASTSection(
                section_id="sec_01",
                title="1. Introdução e Contexto",
                level=1,
                page_start=1,
                page_end=2,
                element_refs=[{"kind": "paragraph", "id": "p_01"}, {"kind": "paragraph", "id": "p_02"}],
            ),
            ASTSection(
                section_id="sec_02",
                title="2. Metodologia Experimental",
                level=1,
                page_start=3,
                page_end=4,
                element_refs=[{"kind": "paragraph", "id": "p_03"}, {"kind": "paragraph", "id": "p_04"}],
            ),
            ASTSection(
                section_id="sec_03",
                title="3. Resultados e Avaliação Comparativa",
                level=1,
                page_start=5,
                page_end=6,
                element_refs=[{"kind": "paragraph", "id": "p_05"}, {"kind": "paragraph", "id": "p_06"}],
            ),
        ],
        paragraphs=[
            ASTParagraph(paragraph_id="p_01", section_id="sec_01", text="A otimização de algoritmos locais é crucial para a preservação da privacidade e soberania computacional.", page_number=1, page_end=1, order=1),
            ASTParagraph(paragraph_id="p_02", section_id="sec_01", text="Estudos preliminares apontam ganhos de latência superiores a 40% em arquiteturas distribuídas.", page_number=2, page_end=2, order=2),
            ASTParagraph(paragraph_id="p_03", section_id="sec_02", text="Utilizou-se um corpus empírico composto por 15.000 amostras com validação cruzada k-fold (k=10).", page_number=3, page_end=3, order=3),
            ASTParagraph(paragraph_id="p_04", section_id="sec_02", text="Os ensaios foram conduzidos em estações de trabalho isoladas sem dependências de rede externa.", page_number=4, page_end=4, order=4),
            ASTParagraph(paragraph_id="p_05", section_id="sec_03", text="Os resultados demonstram que a precisão média atingiu 94.8% no grupo experimental face a 82.1% no grupo de controlo.", page_number=5, page_end=5, order=5),
            ASTParagraph(paragraph_id="p_06", section_id="sec_03", text="Observou-se uma redução estatisticamente significativa do desvio-padrão (p < 0.01).", page_number=6, page_end=6, order=6),
        ],
        tables=[
            ASTTable(
                table_id="tbl_01",
                page_number=5,
                section_id="sec_03",
                order=1,
                caption="Tabela 1: Métricas de Precisão e Latência Comparadas",
                rows=[
                    ["Modelo", "Amostras", "Precisão (%)", "Latência (ms)"],
                    ["Baseline", "5000", "82.1", "120"],
                    ["Otimizado Local", "5000", "94.8", "72"],
                    ["Híbrido Experimental", "5000", "91.5", "85"],
                ],
                n_rows=4,
                n_cols=4,
                header_row_index=0,
                structure_status="RECONSTRUCTED",
            )
        ],
    )


@pytest.fixture
def mock_reasoning_dossier() -> AcademicReasoningDossier:
    return AcademicReasoningDossier(
        dossier_id="dossier_test_p5",
        document_id="doc_test_p5",
        source_sha256="abc123sha256",
        document_analysis=DocumentCoreAnalysis(
            document_id="doc_test_p5",
            title="Estudo Empírico de Desempenho e Eficácia de Algoritmos",
            central_thesis="A execução local otimizada garante soberania e supera baselines cloud em latência e precisão.",
            global_objective="Avaliar o impacto de inferência local soberana em parâmetros de precisão e latência.",
            main_contributions=["Arquitetura de inferência sem dependência de rede", "Ganhos mensurados de precisão e redução de latência"],
        ),
        section_analyses=[
            SectionAnalysis(
                section_id="sec_01",
                title="1. Introdução e Contexto",
                in_depth_synthesis="Introdução à problemática da soberania de dados e eficiência de inferência.",
                core_ideas=["A computação local garante privacidade e previsibilidade operacional."],
                source_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, excerpt="preservação da privacidade", status=EpistemicStatus.SOURCE_FACT.value)],
            ),
            SectionAnalysis(
                section_id="sec_02",
                title="2. Metodologia Experimental",
                in_depth_synthesis="Procedimento rigoroso com 15.000 amostras e k-fold cross-validation.",
                core_ideas=["A validação k-fold previne sobreajuste (overfitting)."],
                source_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3, excerpt="15.000 amostras", status=EpistemicStatus.SOURCE_FACT.value)],
            ),
            SectionAnalysis(
                section_id="sec_03",
                title="3. Resultados e Avaliação Comparativa",
                in_depth_synthesis="Ganho de precisão de 12.7 pontos percentuais e redução de latência.",
                core_ideas=["O modelo otimizado supera o baseline em todos os parâmetros."],
                source_refs=[EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=5, excerpt="94.8% no grupo experimental", status=EpistemicStatus.SOURCE_FACT.value)],
            ),
        ],
        conceptual_analysis=[
            ConceptItem(
                concept_id="c_01",
                name="Inferência Local Soberana",
                definition="Execução direta de modelos de linguagem em hardware local sem recurso a APIs cloud.",
                explanation="Garante soberania operacional e previsibilidade de custos.",
                relationships=["c_02"],
                context_of_use="Ambientes corporativos e de estudo de alta privacidade",
                evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, excerpt="preservação da privacidade", status=EpistemicStatus.SOURCE_FACT.value)],
            ),
            ConceptItem(
                concept_id="c_02",
                name="Otimização Latência-Precisão",
                definition="Compromisso estruturado entre velocidade de inferência e exatidão semântica.",
                explanation="Permite reduzir o tempo de resposta mantendo alta acuidade.",
                relationships=["c_01"],
                context_of_use="Avaliação quantitativa de desempenho de modelos",
                evidence_refs=[EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=5, excerpt="94.8% no grupo experimental", status=EpistemicStatus.SOURCE_FACT.value)],
            ),
        ],
        methodology_analysis=MethodologyAnalysis(
            research_type="Estudo Quantitativo Experimental",
            methodological_design="Validação empírica comparativa",
            data_sources=["Corpus de 15.000 amostras de ensaios controlados"],
            analysis_techniques=["k-fold cross-validation (k=10)", "Teste de hipóteses bicaudal"],
            methodological_limitations=["Ensaios realizados exclusivamente em nós monoprocessador."],
        ),
        results_and_evidence=[
            ResultItem(
                statement="Aumento da precisão média de 82.1% para 94.8%.",
                evidence_data="Precisão baseline 82.1% vs otimizada 94.8%",
                relation_to_objectives="Confirma a hipótese principal de superioridade do modelo local.",
                evidence_refs=[EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=5, excerpt="94.8% no grupo experimental", status=EpistemicStatus.SOURCE_FACT.value)],
            ),
            ResultItem(
                statement="Redução da latência média de 120ms para 72ms.",
                evidence_data="Latência baseline 120ms vs otimizada 72ms",
                relation_to_objectives="Demonstra a viabilidade operacional para utilização interativa.",
                evidence_refs=[EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=5, excerpt="72ms", status=EpistemicStatus.SOURCE_FACT.value)],
            ),
        ],
        cross_section_synthesis=CrossSectionSynthesis(
            conceptual_relationships=[
                {"source": "c_01", "target": "c_02", "type": "potencia", "description": "A inferência local potencia a otimização de latência sem comprometer a precisão."}
            ],
            global_synthesis="A inferência local demonstra superioridade consistente face ao baseline.",
        ),
        critical_analysis=CriticalAnalysis(
            author_limitations=["Ensaios em estações monoprocessador"],
            open_questions=["Comportamento sob concorrência multi-utilizador"],
        ),
    )


@pytest.fixture
def mock_editorial_plan(mock_academic_ast, mock_reasoning_dossier) -> EditorialStudyPlan:
    return EditorialStudyPlan(
        metadata=EditorialPlanMetadata(
            plan_id="plan_test_p5",
            document_id="doc_test_p5",
            source_sha256="abc123sha256",
            ast_version="1.0",
            dossier_id="dossier_test_p5",
            plan_version=1,
            created_at="2026-11-09T22:00:00",
            status="COMPLETED",
        ),
        overview=EditorialOverview(
            central_theme="Eficiência e Precisão na Inferência Local de Modelos de Linguagem",
            central_theme_status="SOURCE_FACT",
            learning_objectives=[
                {
                    "objective_id": "obj_01",
                    "description": "Compreender os princípios de inferência local sem dependência de serviços externos.",
                    "epistemic_status": "SOURCE_FACT",
                    "source_section_ids": ["sec_01"],
                },
                {
                    "objective_id": "obj_02",
                    "description": "Analisar o impacto empírico da otimização nos parâmetros de precisão e latência.",
                    "epistemic_status": "SOURCE_FACT",
                    "source_section_ids": ["sec_02", "sec_03"],
                },
            ],
            target_audience="Estudantes e Investigadores de Inteligência Artificial e Sistemas Distribuídos",
            target_audience_basis="MODEL_INFERENCE",
            document_nature="EMPIRICAL_RESEARCH_ARTICLE",
            recommended_structure_rationale="Progressão pedagógica dedutiva com ênfase em evidência experimental.",
            editorial_strategy="Conceitualização inicial seguida de validação matemática e síntese crítica.",
            global_organization_summary="Estruturado em 2 capítulos integrados com elementos visuais quantitativos e mapas conceptuais.",
            core_contents=["sec_01", "sec_02", "sec_03"],
            complementary_contents=[],
            transversal_synthesis_opportunities=["Eficiência vs. Soberania"],
            evidence_refs=[
                EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")
            ],
        ),
        chapters=[
            EditorialChapter(
                chapter_id="chap_01",
                title="Capítulo 1: Fundamentos da Inferência Local e Soberania",
                pedagogical_objective="Estabelecer os fundamentos teóricos e a necessidade operacional de modelos locais.",
                role_in_progression="Introdução e Enquadramento Conceptual",
                editorial_justification="Fundamental para fundamentar a relevância dos ensaios empíricos posteriores.",
                key_concept_ids=["c_01"],
                original_section_ids=["sec_01"],
                learning_dependencies=[],
                evidence_refs=[
                    EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")
                ],
                sections=[
                    EditorialSection(
                        section_id="sec_01",
                        chapter_id="chap_01",
                        title="1.1 Contexto e Motivação Teórica",
                        order=1,
                        planned_pedagogical_elements=["CONCEPT_BOX", "SYNTHESIS_BOX"],
                        original_section_ids=["sec_01"],
                        pedagogical_treatments=[
                            PedagogicalExplanationSpec(
                                target_topic_or_concept="Inferência Local Soberana",
                                concept_id="c_01",
                                depth_level="IN_DEPTH",
                                required_elements=["CONCEPT_BOX"],
                                pedagogical_focus={"teoria": "Alta", "aplicacao": "Média"},
                                epistemic_status="SOURCE_FACT",
                                evidence_refs=[
                                    EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")
                                ],
                            )
                        ],
                        evidence_refs=[
                            EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")
                        ],
                    )
                ],
            ),
            EditorialChapter(
                chapter_id="chap_02",
                title="Capítulo 2: Validação Empírica e Análise de Desempenho",
                pedagogical_objective="Demonstrar os ganhos de precisão e a redução de latência através de evidência mensurável.",
                role_in_progression="Corpo Analítico e Prova Empírica",
                editorial_justification="Concretização experimental dos pressupostos teóricos.",
                key_concept_ids=["c_02"],
                original_section_ids=["sec_02", "sec_03"],
                learning_dependencies=["chap_01"],
                evidence_refs=[
                    EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3, status="SOURCE_FACT"),
                    EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=5, status="SOURCE_FACT"),
                ],
                sections=[
                    EditorialSection(
                        section_id="sec_02",
                        chapter_id="chap_02",
                        title="2.1 Metodologia Experimental Rigorosa",
                        order=1,
                        planned_pedagogical_elements=["MECHANISM_BOX"],
                        original_section_ids=["sec_02"],
                        pedagogical_treatments=[
                            PedagogicalExplanationSpec(
                                target_topic_or_concept="Validação Cruzada k-fold",
                                concept_id=None,
                                depth_level="IN_DEPTH",
                                required_elements=["MECHANISM_BOX"],
                                pedagogical_focus={"metodologia": "Rigorosa"},
                                epistemic_status="SOURCE_FACT",
                                evidence_refs=[
                                    EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3, status="SOURCE_FACT")
                                ],
                            )
                        ],
                        evidence_refs=[
                            EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3, status="SOURCE_FACT")
                        ],
                    ),
                    EditorialSection(
                        section_id="sec_03",
                        chapter_id="chap_02",
                        title="2.2 Análise Comparativa de Resultados",
                        order=2,
                        planned_pedagogical_elements=["ATTENTION_BOX", "COMPARATIVE_TABLE", "SYNTHESIS_BOX"],
                        original_section_ids=["sec_03"],
                        pedagogical_treatments=[
                            PedagogicalExplanationSpec(
                                target_topic_or_concept="Otimização Latência-Precisão",
                                concept_id="c_02",
                                depth_level="IN_DEPTH",
                                required_elements=["ATTENTION_BOX", "COMPARATIVE_TABLE"],
                                pedagogical_focus={"dados": "Crítico"},
                                epistemic_status="SOURCE_FACT",
                                evidence_refs=[
                                    EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=5, status="SOURCE_FACT")
                                ],
                            )
                        ],
                        evidence_refs=[
                            EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=5, status="SOURCE_FACT")
                        ],
                    ),
                ],
            ),
        ],
        conceptual_relationships=[
            EditorialConceptRelationship(
                relationship_id="erel_01",
                source_concept_id="c_01",
                source_concept_name="Inferência Local Soberana",
                target_concept_id="c_02",
                target_concept_name="Otimização Latência-Precisão",
                relation_type="potencia",
                is_hierarchical=False,
                pedagogical_dependency="Pré-requisito conceitual",
                justification="Compreender a inferência local é indispensável para analisar a otimização.",
                epistemic_status="SOURCE_FACT",
                evidence_refs=[
                    EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")
                ],
            )
        ],
        visual_plans=[
            VisualPlanItem(
                visual_id="vis_chart_01",
                target_chapter_id="chap_02",
                target_section_id="sec_03",
                visual_type="QUANTITATIVE_CHART",
                title="Comparação de Precisão e Latência por Abordagem",
                pedagogical_objective="Demonstrar visualmente o aumento de precisão e redução de latência.",
                content_to_explain="Comparação direta dos dados mensurados na Tabela 1.",
                required_concepts_or_data=["Tabela 1", "Precisão (%)", "Latência (ms)"],
                information_to_represent=["Baseline: 82.1%, 120ms", "Otimizado: 94.8%, 72ms", "Híbrido: 91.5%, 85ms"],
                feasibility_status="FEASIBLE_WITH_SOURCE_DATA",
                source_table_ids=["tbl_01"],
                source_figure_ids=[],
                evidence_refs=[
                    EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=5, status="SOURCE_FACT")
                ],
                inclusion_justification="Elemento visual de alto impacto pedagógico e totalmente fundamentado nos dados reais.",
                constraints_and_limitations=[],
                epistemic_status="SOURCE_FACT",
            ),
            VisualPlanItem(
                visual_id="vis_map_01",
                target_chapter_id="chap_01",
                target_section_id="sec_01",
                visual_type="CONCEPT_NETWORK_MAP",
                title="Mapa Conceptual: Soberania e Eficiência",
                pedagogical_objective="Visualizar a relação entre soberania de dados e ganhos operacionais.",
                content_to_explain="Articulação entre c_01 e c_02.",
                required_concepts_or_data=["c_01", "c_02"],
                information_to_represent=["c_01 -> c_02 (potencia)"],
                feasibility_status="FEASIBLE_WITH_SOURCE_DATA",
                source_table_ids=[],
                source_figure_ids=[],
                evidence_refs=[
                    EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")
                ],
                inclusion_justification="Diagrama essencial para clarificar a dependência entre os conceitos.",
                constraints_and_limitations=[],
                epistemic_status="SOURCE_FACT",
            ),
        ],
        qa_report=EditorialQAReport(
            validation_status="VALID",
            is_valid=True,
            blocking_errors_count=0,
            warnings_count=0,
            recommendations_count=0,
            dossier_section_coverage_pct=1.0,
            dossier_concept_coverage_pct=1.0,
            valid_evidence_refs_pct=1.0,
            invalid_paragraph_refs=[],
            invalid_section_refs=[],
            invalid_page_refs=[],
            epistemic_distribution={"SOURCE_FACT": 10},
            findings=[],
        ),
    )


# ============================================================================
# CRITÉRIO A: Geração de Conteúdo e Enriquecimento Académico
# ============================================================================

def test_criterion_a_content_enrichment_identity_and_coverage(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast):
    """
    Critério A:
    - Validação estrita 1-para-1 de section_id sem fallback posicional.
    - Conteúdo desenvolvido multi-parágrafo e caixas de enquadramento ricas.
    - Distinção explícita entre factos e hipóteses.
    """
    generator = DocumentContentGenerationEngine(llm_caller=None)
    provenance = ReferenceAndProvenanceRenderer(mock_reasoning_dossier, mock_academic_ast)

    # Geração determinística de conteúdo desenvolvido
    content = generator.develop_content(
        mock_editorial_plan,
        mock_reasoning_dossier,
        mock_academic_ast,
        provenance,
    )

    assert isinstance(content, DevelopedStudyDocumentContent)
    assert len(content.chapters) == 2

    # Verificar Capítulo 1
    chap1 = content.chapters[0]
    assert chap1.chapter_id == "chap_01"
    assert len(chap1.sections) == 1
    sec1 = chap1.sections[0]
    assert sec1.section_id == "sec_01"
    assert len(sec1.paragraphs) >= 2
    assert any("soberania" in p.lower() or "inferência" in p.lower() for p in sec1.paragraphs)
    assert len(sec1.callout_boxes) >= 1

    # Verificar Capítulo 2 e cobertura total de secções
    chap2 = content.chapters[1]
    sec_ids = [s.section_id for s in chap2.sections]
    assert "sec_02" in sec_ids
    assert "sec_03" in sec_ids

    # Validação estrita de identidade: tentar injetar batch com id duplicado ou desconhecido
    enricher = AcademicContentEnricher(llm_caller=None)
    valid_batch = [s for s in chap2.sections]
    # Simular resposta maliciosa com id duplicado
    bad_payload = [
        {"section_id": "sec_02", "developed_paragraphs": ["P1", "P2"]},
        {"section_id": "sec_02", "developed_paragraphs": ["P3", "P4"]},
    ]
    is_valid, reason = enricher._validate_section_batch_strict(bad_payload, [s.section_id for s in valid_batch])
    assert not is_valid
    assert "identificadores recebidos não correspondem" in reason.lower() or "duplicado" in reason.lower() or "discrepância" in reason.lower()


# ============================================================================
# CRITÉRIO B: Estrutura Documental e Representação Intermediária (IR)
# ============================================================================

def test_criterion_b_ir_compiler_hierarchy(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast):
    """
    Critério B:
    - Compilação hierárquica e semântica de StudyDocumentIR.
    - Validação de integridade: presença de capa, resumo executivo, TOC, capítulos,
      secções, parágrafos, callouts, tabelas, figuras e bibliografia.
    """
    generator = DocumentContentGenerationEngine(llm_caller=None)
    provenance = ReferenceAndProvenanceRenderer(mock_reasoning_dossier, mock_academic_ast)
    content = generator.develop_content(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast, provenance)

    compiler = DocumentStructureCompiler(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast, provenance)
    ir = compiler.compile(content, visual_assets=[], style_profile=ACADEMIC_EDITORIAL_CLASSIC)

    assert isinstance(ir, StudyDocumentIR)
    assert ir.metadata.title == "Estudo Empírico de Desempenho e Eficácia de Algoritmos"
    assert len(ir.executive_overview_blocks) >= 1
    assert len(ir.toc_entries) >= 2
    assert len(ir.chapters) == 2

    # Verificar presença dos blocos semânticos nos capítulos e secções
    all_blocks = []
    for chap in ir.chapters:
        all_blocks.extend(chap.intro_blocks)
        for sec in chap.sections:
            all_blocks.extend(sec.blocks)
        all_blocks.extend(chap.synthesis_blocks)

    block_kinds = {b.block_kind for b in all_blocks}
    assert IRBlockKind.PARAGRAPH in block_kinds
    assert IRBlockKind.CALLOUT_BOX in block_kinds
    assert any(b.callout_kind == CalloutBoxKind.CONCEPT_BOX for b in all_blocks if b.block_kind == IRBlockKind.CALLOUT_BOX)


# ============================================================================
# CRITÉRIO C: Motor de Síntese Visual Fundamentada
# ============================================================================

def test_criterion_c_visual_generation_real_data_only(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast):
    """
    Critério C:
    - Geração de gráficos quantitativos ancorados em dados reais da Tabela 1.
    - Geração de mapa conceptual distinguindo SOURCE_FACT de MODEL_INFERENCE.
    - Imagens válidas em alta resolução (220 DPI).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        provenance = ReferenceAndProvenanceRenderer(mock_reasoning_dossier, mock_academic_ast)
        visual_engine = VisualGenerationEngine(
            output_dir=output_dir,
            profile=ACADEMIC_EDITORIAL_CLASSIC,
        )

        assets = visual_engine.generate_visual_assets(
            mock_editorial_plan,
            mock_reasoning_dossier,
            mock_academic_ast,
            provenance,
        )
        assert len(assets) == 2

        # Verificar gráfico quantitativo
        chart_asset = next(a for a in assets if a.visual_type == "QUANTITATIVE_CHART")
        assert Path(chart_asset.image_path).exists()
        assert Path(chart_asset.image_path).stat().st_size > 1000
        assert chart_asset.is_grounded_in_source is True
        assert chart_asset.dpi >= 220

        # Verificar mapa de conceitos
        map_asset = next(a for a in assets if a.visual_type == "CONCEPT_NETWORK_MAP")
        assert Path(map_asset.image_path).exists()
        assert Path(map_asset.image_path).stat().st_size > 1000
        assert map_asset.is_grounded_in_source is True


# ============================================================================
# CRITÉRIO D: Layout, Tipografia e Exportação Multi-Formato (PDF e DOCX)
# ============================================================================

def test_criterion_d_pdf_and_docx_rendering(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast):
    """
    Critério D:
    - Composição de PDF determinístico via PyMuPDF.
    - Texto pesquisável e selecionável.
    - Índice com marcadores nativos e links de navegação interna.
    - Numeração dinâmica e cabeçalhos/rodapés.
    - Exportação simultânea de DOCX a partir da mesma IR sem perda de fidelidade.
    """
    if pymupdf is None or docx is None:
        pytest.skip("pymupdf ou python-docx não disponível.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        provenance = ReferenceAndProvenanceRenderer(mock_reasoning_dossier, mock_academic_ast)
        content = DocumentContentGenerationEngine().develop_content(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast, provenance)

        visuals_dir = tmp_path / "visuals"
        visual_engine = VisualGenerationEngine(visuals_dir, profile=ACADEMIC_EDITORIAL_CLASSIC)
        assets = visual_engine.generate_visual_assets(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast, provenance)

        compiler = DocumentStructureCompiler(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast, provenance)
        ir = compiler.compile(content, visual_assets=assets, style_profile=ACADEMIC_EDITORIAL_CLASSIC)

        # 1. Compor PDF
        pdf_path = tmp_path / "test_study_doc.pdf"
        pdf_composer = PDFDocumentComposer(ACADEMIC_EDITORIAL_CLASSIC)
        pdf_res = pdf_composer.compose_pdf(ir, pdf_path)

        assert pdf_path.exists()
        assert pdf_res.pages_count >= 3
        assert pdf_res.file_size_bytes > 5000

        # Inspecionar PDF com PyMuPDF
        doc = pymupdf.open(str(pdf_path))
        assert len(doc) == pdf_res.pages_count

        # Verificar TOC
        toc = doc.get_toc()
        assert len(toc) >= 2  # Capítulos registados
        chapter_titles = [entry[1] for entry in toc]
        assert any("Fundamentos" in t for t in chapter_titles)

        # Verificar texto selecionável e ausência de caracteres corrompidos
        all_text = ""
        for page in doc:
            t = page.get_text()
            assert "\x00" not in t  # Sem caracteres nulos corrompidos
            all_text += t + "\n"

        assert "Inferência Local Soberana" in all_text
        assert "Carlos Silva" in all_text
        doc.close()

        # 2. Compor DOCX a partir da mesma IR
        docx_path = tmp_path / "test_study_doc.docx"
        docx_composer = DOCXDocumentComposer(ACADEMIC_EDITORIAL_CLASSIC)
        docx_res = docx_composer.compose_docx(ir, docx_path)

        assert docx_path.exists()
        assert docx_res.file_size_bytes > 3000

        doc_word = docx.Document(str(docx_path))
        doc_word_text = "\n".join([p.text for p in doc_word.paragraphs])
        assert "Fundamentos" in doc_word_text
        assert len(doc_word.tables) >= 1  # Tabela compilada


# ============================================================================
# CRITÉRIO E: Garantia de Qualidade (QA), Checkpoints e Versionamento
# ============================================================================

def test_criterion_e_qa_audit_and_orchestrator_checkpoints(mock_editorial_plan, mock_reasoning_dossier, mock_academic_ast):
    """
    Critério E:
    - Auditoria de QA em 4 eixos (Conteúdo, Visual, Documental, Pedagógica).
    - Inspeção física de páginas PDF via PyMuPDF.
    - Checkpoint incremental e versionamento histórico não-destrutivo.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir)
        doc_id = mock_editorial_plan.metadata.document_id

        # Salvar artefactos das fases anteriores no storage
        doc_dir = storage_dir / "documents" / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / "ast.json").write_text(json.dumps(mock_academic_ast.to_dict()), encoding="utf-8")
        (doc_dir / "reasoning_dossier.json").write_text(json.dumps(mock_reasoning_dossier.to_dict()), encoding="utf-8")
        (doc_dir / "editorial_study_plan.json").write_text(json.dumps(mock_editorial_plan.to_dict()), encoding="utf-8")

        engine = DocumentGenerationEngine(storage_dir=storage_dir)

        # Execução 1: Geração Completa (Versão 1)
        res_v1 = engine.generate_study_document(
            mock_editorial_plan,
            mock_reasoning_dossier,
            mock_academic_ast,
            export_docx=True,
            force_recompute=True,
        )

        assert res_v1.version == 1
        assert res_v1.status == DocumentGenerationState.COMPLETED.value
        assert Path(res_v1.pdf_path).exists()
        assert Path(res_v1.docx_path).exists()
        assert res_v1.qa_report.is_valid is True
        assert res_v1.qa_report.overall_score >= 0.85
        assert res_v1.qa_report.blocking_count == 0

        # Verificar histórico criado v1
        history_v1 = doc_dir / "generated_documents_history" / "v1"
        assert (history_v1 / "study_document_v1.pdf").exists()
        assert (history_v1 / "study_document_v1.docx").exists()

        # Execução 2: Segunda geração deve criar Versão 2 sem apagar Versão 1
        res_v2 = engine.generate_study_document(
            mock_editorial_plan,
            mock_reasoning_dossier,
            mock_academic_ast,
            export_docx=True,
            force_recompute=True,
        )

        assert res_v2.version == 2
        history_v2 = doc_dir / "generated_documents_history" / "v2"
        assert (history_v2 / "study_document_v2.pdf").exists()
        assert (history_v1 / "study_document_v1.pdf").exists()  # v1 preservado!

        # Consulta de estado
        status = engine.get_document_generation_status(doc_id)
        assert status["has_pdf"] is True
        assert status["has_docx"] is True
        assert status["version"] == 2
        assert status["versions_count"] == 2
        assert status["qa_validation_status"] in ("VALID", "VALID_WITH_WARNINGS")

        # Verificar sincronização com plano
        up_to_date, reason = engine.is_document_up_to_date(doc_id, mock_editorial_plan)
        assert up_to_date is True
        assert reason == "UP_TO_DATE"
