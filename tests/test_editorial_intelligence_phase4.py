"""
JARVIS OS — EDITORIAL INTELLIGENCE ENGINE (PHASE 4) TEST SUITE
Validação rigorosa dos cenários de aceitação A–G:
  A. Planeamento editorial adaptativo (artigo empírico, ensaio teórico, manual técnico) e integridade de cobertura.
  B. Fidelidade epistémica e proveniência (SOURCE_FACT, MODEL_INFERENCE, NOT_FOUND, UNVERIFIED, rastreabilidade a AST/Dossier).
  C. Qualidade pedagógica, seleção adequada de elementos e ordem de pré-requisitos conceptuais (hierárquicos e não hierárquicos).
  D. Planeamento visual fundamentado, bloqueio de dados inventados e deteção de insuficiência de dados.
  E. Robustez: orçamento estrito de contexto em documentos extensos, falhas explícitas, checkpoints/retoma, persistência e versionamento.
  F. Regressão e compatibilidade com Fases 2 e 3, StudyService e WebSocket.
  G. Teste de integração real End-to-End com Ollama local (qwen3.5:9b) sobre PDF académico real.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from services.document_intelligence import (
    AcademicDocumentAST,
    ASTFigure,
    ASTFormula,
    ASTParagraph,
    ASTSection,
    ASTTable,
    DocumentIntelligenceExtractor,
    DocumentMetadata,
    ExtractionReport,
    PageInfo,
)
from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    AcademicReasoningEngine,
    ConceptItem,
    ContextBudgetExceededError,
    CriticalAnalysis,
    CrossSectionSynthesis,
    DocumentCoreAnalysis,
    EpistemicStatus,
    EvidenceRef,
    MethodologyAnalysis,
    OllamaInferenceUnavailableError,
    ReasoningQAReport,
    ReasoningTelemetry,
    ResultItem,
    SectionAnalysis,
    generate_deterministic_concept_id,
)
from services.editorial_intelligence_engine import (
    ConceptRelationType,
    EditorialChapter,
    EditorialConceptRelationship,
    EditorialConsistencyEngine,
    EditorialDocumentPlanner,
    EditorialIntelligenceEngine,
    EditorialOverview,
    EditorialPlanMetadata,
    EditorialPlanningCancelledError,
    EditorialPlanningError,
    EditorialQAFinding,
    EditorialQAReport,
    EditorialQASeverity,
    EditorialSection,
    EditorialStudyPlan,
    HierarchicalContentArchitect,
    PedagogicalElementType,
    PedagogicalExplanationPlanner,
    PedagogicalExplanationSpec,
    StudyDocumentNature,
    VisualContentPlanner,
    VisualElementType,
    VisualFeasibilityStatus,
    VisualPlanItem,
    _GroundingContext,
    compute_dossier_fingerprint,
)
from services.study_service import StudyService


# ============================================================================
# Helpers de Construção de AST e Dossier Sintéticos Fundamentados
# ============================================================================

def build_empirical_ast_and_dossier(
    document_id: str = "doc_emp_01",
    source_sha256: str = "sha256_empirical_v1",
) -> Tuple[AcademicDocumentAST, AcademicReasoningDossier]:
    """Cria par (AST, Dossier) realista de um artigo científico empírico."""
    sections = [
        ASTSection(section_id="sec_intro", title="1. Introduction", level=1, kind="introduction", page_start=1, page_end=2),
        ASTSection(section_id="sec_bg", title="2. Theoretical Background", level=1, kind="background", page_start=2, page_end=4),
        ASTSection(section_id="sec_method", title="3. Experimental Methodology", level=1, kind="methodology", page_start=4, page_end=6),
        ASTSection(section_id="sec_results", title="4. Empirical Results", level=1, kind="results", page_start=6, page_end=8),
        ASTSection(section_id="sec_conc", title="5. Discussion and Conclusion", level=1, kind="conclusion", page_start=8, page_end=9),
    ]
    paragraphs = [
        ASTParagraph("p_1", "sec_intro", "Local study engines suffer from context window truncation and epistemic drift when summarizing dense papers.", 1, 1, 1),
        ASTParagraph("p_2", "sec_intro", "We investigate how hierarchical map-reduce preserves source provenance across multi-page scientific documents.", 2, 2, 2),
        ASTParagraph("p_3", "sec_bg", "Epistemic Grounding is defined as the explicit binding between every analytical claim and verifiable source spans.", 2, 2, 3),
        ASTParagraph("p_4", "sec_bg", "Adaptive Semantic Segmentation partitions sections along sentence boundaries within strict token budgets, relying on Epistemic Grounding.", 3, 3, 4),
        ASTParagraph("p_5", "sec_method", "We evaluated 240 peer-reviewed articles using a double-blind forensic audit protocol.", 4, 4, 5),
        ASTParagraph("p_6", "sec_method", "Each output was scored on reference precision, epistemic classification accuracy, and coverage completeness.", 5, 5, 6),
        ASTParagraph("p_7", "sec_results", "Reference precision increased from 61.2% to 98.7% (p < 0.001) across the 240-paper benchmark.", 6, 6, 7),
        ASTParagraph("p_8", "sec_results", "Fabricated citations dropped to 0.0% when strict AST verification was enforced.", 7, 7, 8),
        ASTParagraph("p_9", "sec_conc", "Hierarchical local reasoning achieves high fidelity, though latency remains bounded by local GPU throughput.", 8, 8, 9),
    ]
    tables = [
        ASTTable(
            table_id="tbl_1",
            page_number=6,
            section_id="sec_results",
            order=1,
            caption="Table 1: Benchmark Precision Comparison",
            rows=[["Method", "Precision"], ["Baseline", "61.2%"], ["Hierarchical AST", "98.7%"]],
            n_rows=3,
            n_cols=2,
            structure_status="RECONSTRUCTED",
            extraction_method="PYMUPDF_LINES",
        )
    ]
    figures = [
        ASTFigure(
            figure_id="fig_1",
            page_number=3,
            section_id="sec_bg",
            order=1,
            element_kind="VECTOR_GRAPHIC",
            caption="Figure 1: Pipeline overview",
            interpretation_status="IMAGE_ONLY_NOT_INTERPRETED",
            underlying_data_recovered=False,
        )
    ]

    ast = AcademicDocumentAST(
        document_id=document_id,
        extractor_version="2.0.0",
        source_sha256=source_sha256,
        filename="empirical_study.pdf",
        metadata=DocumentMetadata(
            title="Hierarchical Epistemic Grounding in Local Study Engines",
            abstract="Study of hierarchical map-reduce for local academic document comprehension.",
            keywords=["Epistemic Grounding", "Adaptive Segmentation", "Local LLM"],
            page_count=9,
            source_sha256=source_sha256,
        ),
        pages=[PageInfo(page_number=i) for i in range(1, 10)],
        sections=sections,
        paragraphs=paragraphs,
        tables=tables,
        figures=figures,
        report=ExtractionReport(status="COMPLETED", total_pages=9, tables_identified=1, tables_structure_reconstructed=1, figures_identified=1),
    )

    c_grounding_id = generate_deterministic_concept_id("Epistemic Grounding")
    c_seg_id = generate_deterministic_concept_id("Adaptive Semantic Segmentation")
    c_audit_id = generate_deterministic_concept_id("Forensic Audit Protocol")

    dossier = AcademicReasoningDossier(
        dossier_id="dossier_emp_001",
        document_id=document_id,
        source_sha256=source_sha256,
        ast_version="2.0.0",
        model_name="qwen3.5:9b",
        status="COMPLETED",
        document_analysis=DocumentCoreAnalysis(
            document_id=document_id,
            title="Hierarchical Epistemic Grounding in Local Study Engines",
            metadata={"keywords": ["Epistemic Grounding", "Adaptive Segmentation"], "page_count": 9},
            global_objective="Avaliar como a arquitetura hierárquica preserva a proveniência epistémica.",
            research_problem="Truncamento de contexto e deriva epistémica em modelos locais.",
            central_thesis="A verificação forense ancorada na AST elimina citações fabricadas e eleva a precisão para 98.7%.",
            main_contributions=[
                "Definição operacional de Epistemic Grounding",
                "Segmentação semântica adaptativa sem truncamento",
                "Validação empírica em 240 artigos revistos por pares",
            ],
            evidence_refs=[EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=1, status="SOURCE_FACT")],
        ),
        section_analyses=[
            SectionAnalysis(
                section_id="sec_intro",
                title="1. Introduction",
                section_type="introduction",
                objective="Apresentar o problema do truncamento e da deriva epistémica.",
                in_depth_synthesis="A introdução identifica as falhas de truncamento e propõe um pipeline hierárquico rastreável.",
                core_ideas=["Truncamento de contexto degrada sínteses", "Raciocínio hierárquico preserva proveniência"],
                concepts=[{"name": "Epistemic Grounding", "explanation": " Ligação verificável à fonte", "paragraph_ids": ["p_2"]}],
                arguments=[{"claim": "Modelos sofrem deriva sem ancoragem", "evidence": "Análise inicial", "paragraph_ids": ["p_1"], "status": "SOURCE_FACT"}],
                limitations=[],
                source_refs=[
                    EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=1, excerpt="Local study engines suffer...", status="SOURCE_FACT"),
                    EvidenceRef(section_id="sec_intro", paragraph_id="p_2", page_number=2, excerpt="We investigate how hierarchical...", status="SOURCE_FACT"),
                ],
                segment_ids=["sec_intro_seg_0"],
            ),
            SectionAnalysis(
                section_id="sec_bg",
                title="2. Theoretical Background",
                section_type="background",
                objective="Formalizar Epistemic Grounding e Adaptive Semantic Segmentation.",
                in_depth_synthesis="Estabelece as bases conceptuais de ancoragem epistémica e partição adaptativa por orçamento de tokens.",
                core_ideas=["Epistemic Grounding exige vínculos explícitos", "Segmentação respeita fronteiras de frase"],
                concepts=[
                    {"name": "Epistemic Grounding", "explanation": "Ancoragem explícita", "paragraph_ids": ["p_3"]},
                    {"name": "Adaptive Semantic Segmentation", "explanation": "Partição semântica controlada", "paragraph_ids": ["p_4"]},
                ],
                arguments=[],
                limitations=[],
                source_refs=[
                    EvidenceRef(section_id="sec_bg", paragraph_id="p_3", page_number=2, excerpt="Epistemic Grounding is defined...", status="SOURCE_FACT"),
                    EvidenceRef(section_id="sec_bg", paragraph_id="p_4", page_number=3, excerpt="Adaptive Semantic Segmentation...", status="SOURCE_FACT"),
                ],
                segment_ids=["sec_bg_seg_0"],
            ),
            SectionAnalysis(
                section_id="sec_method",
                title="3. Experimental Methodology",
                section_type="methodology",
                objective="Descrever o benchmark de 240 artigos e o protocolo de auditoria forense.",
                in_depth_synthesis="Avalia 240 artigos científicos sob protocolo duplamente cego medindo precisão, acurácia epistémica e cobertura.",
                core_ideas=["Amostra de 240 artigos", "Auditoria duplamente cega"],
                concepts=[{"name": "Forensic Audit Protocol", "explanation": "Avaliação cega de precisão de referências", "paragraph_ids": ["p_5", "p_6"]}],
                arguments=[],
                limitations=[],
                source_refs=[
                    EvidenceRef(section_id="sec_method", paragraph_id="p_5", page_number=4, status="SOURCE_FACT"),
                    EvidenceRef(section_id="sec_method", paragraph_id="p_6", page_number=5, status="SOURCE_FACT"),
                ],
                segment_ids=["sec_method_seg_0"],
            ),
            SectionAnalysis(
                section_id="sec_results",
                title="4. Empirical Results",
                section_type="results",
                objective="Reportar os ganhos quantitativos de precisão e redução de alucinação.",
                in_depth_synthesis="A precisão subiu de 61.2% para 98.7% (p < 0.001) e citações inventadas caíram para 0.0%.",
                core_ideas=["98.7% de precisão de referência", "0.0% de citações fabricadas"],
                concepts=[],
                arguments=[],
                limitations=[],
                source_refs=[
                    EvidenceRef(section_id="sec_results", paragraph_id="p_7", page_number=6, status="SOURCE_FACT"),
                    EvidenceRef(section_id="sec_results", paragraph_id="p_8", page_number=7, status="SOURCE_FACT"),
                ],
                segment_ids=["sec_results_seg_0"],
            ),
            SectionAnalysis(
                section_id="sec_conc",
                title="5. Discussion and Conclusion",
                section_type="conclusion",
                objective="Sintetizar contributos e discutir a limitação de latência em GPU local.",
                in_depth_synthesis="Confirma a eficácia da abordagem hierárquica, assinalando a latência de inferência local como restrição operacional.",
                core_ideas=["Alta fidelidade comprovada", "Latência limitada por GPU local"],
                concepts=[],
                arguments=[],
                limitations=["Latência limitada pelo throughput da GPU local."],
                source_refs=[
                    EvidenceRef(section_id="sec_conc", paragraph_id="p_9", page_number=8, status="SOURCE_FACT"),
                ],
                segment_ids=["sec_conc_seg_0"],
            ),
        ],
        conceptual_analysis=[
            ConceptItem(
                concept_id=c_grounding_id,
                name="Epistemic Grounding",
                definition="Vinculação explícita entre cada afirmação analítica e excertos verificáveis da fonte.",
                explanation="Base epistemológica que impede a confusão entre facto textual e inferência do modelo.",
                relationships=["Adaptive Semantic Segmentation", "Forensic Audit Protocol"],
                context_of_use=" Motores locais de estudo académico",
                evidence_refs=[EvidenceRef(section_id="sec_bg", paragraph_id="p_3", page_number=2, status="SOURCE_FACT")],
            ),
            ConceptItem(
                concept_id=c_seg_id,
                name="Adaptive Semantic Segmentation",
                definition="Partição de secções ao longo de fronteiras frásicas dentro de orçamentos estritos de tokens.",
                explanation="Permite processar documentos longos mantendo os identificadores de parágrafo para o Epistemic Grounding.",
                relationships=["Epistemic Grounding"],
                context_of_use="Pré-processamento hierárquico Map-Reduce",
                evidence_refs=[EvidenceRef(section_id="sec_bg", paragraph_id="p_4", page_number=3, status="SOURCE_FACT")],
            ),
            ConceptItem(
                concept_id=c_audit_id,
                name="Forensic Audit Protocol",
                definition="Protocolo de verificação de integridade de referências, páginas e estados epistémicos.",
                explanation="Operacionaliza o Epistemic Grounding na avaliação empírica.",
                relationships=["Epistemic Grounding"],
                context_of_use="Validação de qualidade do dossier",
                evidence_refs=[EvidenceRef(section_id="sec_method", paragraph_id="p_5", page_number=4, status="SOURCE_FACT")],
            ),
        ],
        methodology_analysis=MethodologyAnalysis(
            is_applicable=True,
            research_type="Empírico Quantitativo",
            methodological_design="Benchmark comparativo duplamente cego",
            methods_used=["Map-Reduce hierárquico", "Auditoria forense"],
            sample_or_participants="240 artigos científicos revistos por pares",
            instruments=["Validador AST"],
            procedures=["Segmentação", "Síntese", "Verificação de referências"],
            variables=["Precisão de referência", "Taxa de citações fabricadas"],
            data_sources=["Corpus de 240 PDFs"],
            analysis_techniques=["Teste de significância estatística (p < 0.001)"],
            methodological_limitations=["Latência dependente de GPU local"],
            evidence_refs=[EvidenceRef(section_id="sec_method", paragraph_id="p_5", page_number=4, status="SOURCE_FACT")],
        ),
        results_and_evidence=[
            ResultItem(
                statement="A precisão de referências aumentou de 61.2% para 98.7% (p < 0.001).",
                evidence_data="Baseline: 61.2%, Hierarchical AST: 98.7%, p < 0.001, N=240",
                relation_to_objectives="Demonstra preservação superior de proveniência.",
                interpretation_limitations="Avaliado em artigos científicos estruturados.",
                evidence_refs=[EvidenceRef(section_id="sec_results", paragraph_id="p_7", page_number=6, status="SOURCE_FACT")],
            ),
            ResultItem(
                statement="As citações fabricadas caíram para 0.0%.",
                evidence_data="0.0% fabricated citations",
                relation_to_objectives="Comprova eliminação de alucinações bibliográficas.",
                interpretation_limitations="",
                evidence_refs=[EvidenceRef(section_id="sec_results", paragraph_id="p_8", page_number=7, status="SOURCE_FACT")],
            ),
        ],
        cross_section_synthesis=CrossSectionSynthesis(
            argumentative_progression=[
                "Identificação do problema de truncamento na Introdução",
                "Formalização de Epistemic Grounding e Segmentação no Background",
                "Validação experimental em 240 artigos na Metodologia e Resultados",
                "Discussão do compromisso fidelidade vs latência na Conclusão",
            ],
            conceptual_relationships=[
                {
                    "concept_a": "Epistemic Grounding",
                    "relationship": "é pré-requisito conceptual de",
                    "concept_b": "Adaptive Semantic Segmentation",
                    "explanation": "A segmentação preserva IDs especificamente para viabilizar o grounding.",
                },
                {
                    "concept_a": "Adaptive Semantic Segmentation",
                    "relationship": "complementa",
                    "concept_b": "Forensic Audit Protocol",
                    "explanation": "Um preserva âncoras na entrada e o outro audita âncoras na saída.",
                },
            ],
            coherence_and_tensions=[
                {
                    "type": "TENSION",
                    "description": "Rigor máximo de verificação aumenta o número de chamadas locais e a latência.",
                    "sections_involved": ["sec_results", "sec_conc"],
                    "status": "MODEL_INFERENCE",
                }
            ],
            idea_dependencies=[
                {
                    "dependent_idea": "Auditoria forense de referências",
                    "depends_on": "Epistemic Grounding",
                    "reason": "Só é possível auditar referências se o contrato epistémico estiver definido.",
                }
            ],
            global_synthesis="O estudo comprova que motores de estudo locais atingem 98.7% de precisão probatória quando combinam segmentação adaptativa e validação forense contra a AST.",
        ),
        critical_analysis=CriticalAnalysis(
            epistemic_assumptions=["Assume extração determinística prévia da camada textual do PDF."],
            author_limitations=["Latência limitada pelo throughput da GPU local."],
            literature_gaps=["Escassez de benchmarks forenses para modelos 9B locais."],
            open_questions=["Como otimizar latência sem sacrificar validação por segmento?"],
        ),
        qa_report=ReasoningQAReport(total_sections_analyzed=5, total_segments_analyzed=5, is_valid=True),
        telemetry=ReasoningTelemetry(total_duration_ms=1200.0, total_llm_calls=8),
    )
    return ast, dossier


def make_mock_editorial_llm_caller(
    ast: AcademicDocumentAST,
    dossier: AcademicReasoningDossier,
) -> Any:
    """Constrói um llm_caller determinístico simulando respostas estruturadas válidas do Qwen 3.5:9b."""
    c_grounding_id = dossier.conceptual_analysis[0].concept_id
    c_seg_id = dossier.conceptual_analysis[1].concept_id
    c_audit_id = dossier.conceptual_analysis[2].concept_id

    def caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if op == "editorial_macro_planning":
            resp = {
                "document_nature": StudyDocumentNature.EMPIRICAL_RESEARCH_ARTICLE.value,
                "central_theme": "Preservação de proveniência epistémica em motores de estudo locais via raciocínio hierárquico ancorado na AST.",
                "central_theme_status": "SOURCE_FACT",
                "target_audience": "Estudantes avançados e engenheiros de sistemas de IA documental",
                "target_audience_basis": "MODEL_INFERENCE",
                "recommended_structure_rationale": "Como o artigo apresenta fundamentação conceptual seguida de benchmark empírico (N=240), a organização deve introduzir primeiro os conceitos fundacionais antes do protocolo experimental e da análise quantitativa.",
                "editorial_strategy": "Progressão dos fundamentos epistemológicos para a arquitetura técnica, seguida de validação empírica e análise crítica das limitações.",
                "global_organization_summary": "Três capítulos progressivos: (1) Problema e Fundamentos de Grounding, (2) Metodologia Forense, (3) Evidências Empíricas e Limitações.",
                "learning_objectives": [
                    {
                        "objective_id": "lo_1",
                        "description": "Compreender o conceito de Epistemic Grounding e o problema do truncamento em modelos locais.",
                        "epistemic_status": "SOURCE_FACT",
                        "source_section_ids": ["sec_intro", "sec_bg"],
                        "paragraph_ids": ["p_1", "p_3"],
                    },
                    {
                        "objective_id": "lo_2",
                        "description": "Analisar como a segmentação semântica adaptativa e o protocolo forense garantem 98.7% de precisão.",
                        "epistemic_status": "SOURCE_FACT",
                        "source_section_ids": ["sec_bg", "sec_method", "sec_results"],
                        "paragraph_ids": ["p_4", "p_5", "p_7"],
                    },
                ],
                "core_contents": [
                    "Definição e papel do Epistemic Grounding",
                    "Mecanismo de Adaptive Semantic Segmentation",
                    "Protocolo experimental em 240 artigos e resultados de precisão (98.7%)",
                ],
                "complementary_contents": [
                    "Compromisso operacional entre rigor de validação e latência em GPU local",
                ],
                "transversal_synthesis_opportunities": [
                    "Relação transversal entre segmentação na entrada (Fase 2/3) e auditoria forense na saída",
                ],
                "conceptual_relationships": [
                    {
                        "source_concept_id": c_grounding_id,
                        "target_concept_id": c_seg_id,
                        "relation_type": ConceptRelationType.PREREQUISITE_FOR.value,
                        "is_hierarchical": True,
                        "pedagogical_dependency": "SOURCE_BEFORE_TARGET",
                        "justification": "É necessário compreender o requisito de ancoragem epistémica antes de estudar como a segmentação preserva os IDs.",
                        "epistemic_status": "SOURCE_FACT",
                        "paragraph_ids": ["p_3", "p_4"],
                    },
                    {
                        "source_concept_id": c_seg_id,
                        "target_concept_id": c_audit_id,
                        "relation_type": ConceptRelationType.COMPLEMENTARY.value,
                        "is_hierarchical": False,
                        "pedagogical_dependency": "CO_PRESENTATION",
                        "justification": "Ambos os mecanismos atuam complementarmente para impedir perda e invenção de referências.",
                        "epistemic_status": "MODEL_INFERENCE",
                        "paragraph_ids": ["p_4", "p_5"],
                    },
                ],
                "chapters": [
                    {
                        "chapter_id": "ed_chap_01",
                        "title": "Fundamentos Epistemológicos e Segmentação Semântica",
                        "pedagogical_objective": "Dominar o problema da deriva epistémica e os conceitos base de ancoragem e segmentação.",
                        "description": "Integra a motivação da introdução com as definições formais do enquadramento teórico.",
                        "order": 1,
                        "role_in_progression": "FOUNDATION",
                        "editorial_justification": "Agrupa sec_intro e sec_bg para evitar repetição entre a apresentação do problema e a definição de Epistemic Grounding.",
                        "key_concept_ids": [c_grounding_id, c_seg_id],
                        "original_section_ids": ["sec_intro", "sec_bg"],
                        "learning_dependencies": [],
                        "sections": [
                            {
                                "section_id": "ed_sec_01_01",
                                "title": "Problema do Truncamento e Epistemic Grounding",
                                "level": 2,
                                "order": 1,
                                "content_role": "CORE",
                                "pedagogical_objective": "Definir Epistemic Grounding e contextualizar por que resumos locais sofrem deriva.",
                                "original_section_ids": ["sec_intro", "sec_bg"],
                                "associated_concept_ids": [c_grounding_id],
                                "introduced_concept_ids": [c_grounding_id],
                                "prerequisite_concept_ids": [],
                                "merged_or_deduplicated_notes": ["Consolida a menção introdutória de grounding (p_2) com a definição formal (p_3)."],
                            },
                            {
                                "section_id": "ed_sec_01_02",
                                "title": "Segmentação Semântica Adaptativa sob Orçamento de Contexto",
                                "level": 2,
                                "order": 2,
                                "content_role": "CORE",
                                "pedagogical_objective": "Explicar o funcionamento da partição semântica apoiada no Epistemic Grounding.",
                                "original_section_ids": ["sec_bg"],
                                "associated_concept_ids": [c_grounding_id, c_seg_id],
                                "introduced_concept_ids": [c_seg_id],
                                "prerequisite_concept_ids": [c_grounding_id],
                                "merged_or_deduplicated_notes": [],
                            },
                        ],
                    },
                    {
                        "chapter_id": "ed_chap_02",
                        "title": "Desenho Experimental e Auditoria Forense",
                        "pedagogical_objective": "Compreender como o protocolo de auditoria avalia rigorosamente 240 artigos.",
                        "description": "Apresenta o desenho metodológico duplamente cego e as métricas avaliadas.",
                        "order": 2,
                        "role_in_progression": "METHODOLOGY_OPERATIONALIZATION",
                        "editorial_justification": "Introduz a operacionalização metodológica após os conceitos base estarem consolidados.",
                        "key_concept_ids": [c_audit_id],
                        "original_section_ids": ["sec_method"],
                        "learning_dependencies": ["ed_chap_01"],
                        "sections": [
                            {
                                "section_id": "ed_sec_02_01",
                                "title": "Protocolo de Auditoria Forense e Benchmark",
                                "level": 2,
                                "order": 1,
                                "content_role": "CORE",
                                "pedagogical_objective": "Explicar o procedimento duplamente cego e variáveis medidas.",
                                "original_section_ids": ["sec_method"],
                                "associated_concept_ids": [c_audit_id, c_grounding_id],
                                "introduced_concept_ids": [c_audit_id],
                                "prerequisite_concept_ids": [c_grounding_id],
                                "merged_or_deduplicated_notes": [],
                            }
                        ],
                    },
                    {
                        "chapter_id": "ed_chap_03",
                        "title": "Evidências Empíricas, Discussão Crítica e Limitações",
                        "pedagogical_objective": "Interpretar os ganhos quantitativos observados e avaliar as limitações de latência local.",
                        "description": "Articula os resultados de precisão (98.7%) com as restrições práticas de execução em GPU local.",
                        "order": 3,
                        "role_in_progression": "EMPIRICAL_EVIDENCE",
                        "editorial_justification": "Une resultados e discussão crítica para conectar métricas diretamente às suas limitações interpretativas.",
                        "key_concept_ids": [c_grounding_id, c_audit_id],
                        "original_section_ids": ["sec_results", "sec_conc"],
                        "learning_dependencies": ["ed_chap_01", "ed_chap_02"],
                        "sections": [
                            {
                                "section_id": "ed_sec_03_01",
                                "title": "Resultados de Precisão Probatória e Eliminação de Alucinações",
                                "level": 2,
                                "order": 1,
                                "content_role": "CORE",
                                "pedagogical_objective": "Analisar a subida de 61.2% para 98.7% e a redução para 0.0% de citações inventadas.",
                                "original_section_ids": ["sec_results"],
                                "associated_concept_ids": [c_audit_id],
                                "introduced_concept_ids": [],
                                "prerequisite_concept_ids": [c_grounding_id, c_audit_id],
                                "merged_or_deduplicated_notes": [],
                            },
                            {
                                "section_id": "ed_sec_03_02",
                                "title": "Síntese Transversal e Limitações de Throughput Local",
                                "level": 2,
                                "order": 2,
                                "content_role": "SYNTHESIS",
                                "pedagogical_objective": "Avaliar criticamente o trade-off entre verificação exaustiva e latência em hardware local.",
                                "original_section_ids": ["sec_conc"],
                                "associated_concept_ids": [c_grounding_id, c_seg_id, c_audit_id],
                                "introduced_concept_ids": [],
                                "prerequisite_concept_ids": [c_grounding_id, c_seg_id, c_audit_id],
                                "merged_or_deduplicated_notes": [],
                            },
                        ],
                    },
                ],
            }
            return json.dumps(resp, ensure_ascii=False), {"status": "COMPLETED", "input_tokens": 900, "output_tokens": 750}

        if op == "editorial_chapter_pedagogy":
            chap_id = meta.get("chapter_id", "")
            if chap_id == "ed_chap_01":
                resp = {
                    "sections": [
                        {
                            "section_id": "ed_sec_01_01",
                            "explanation_strategy": "Partir do problema concreto do truncamento em LLMs locais para motivar a definição rigorosa de Epistemic Grounding.",
                            "planned_pedagogical_elements": [
                                PedagogicalElementType.CONTEXTUALIZATION.value,
                                PedagogicalElementType.DEFINITION.value,
                                PedagogicalElementType.DETAILED_EXPLANATION.value,
                            ],
                            "contents_to_cover": [
                                {
                                    "summary": "Problemas de truncamento de janela de contexto e deriva epistémica em motores locais.",
                                    "epistemic_status": "SOURCE_FACT",
                                    "source_section_id": "sec_intro",
                                    "paragraph_ids": ["p_1"],
                                },
                                {
                                    "summary": "Definição formal de Epistemic Grounding como vínculo explícito a excertos verificáveis.",
                                    "epistemic_status": "SOURCE_FACT",
                                    "source_section_id": "sec_bg",
                                    "paragraph_ids": ["p_3"],
                                },
                            ],
                            "pedagogical_treatments": [
                                {
                                    "target_topic_or_concept": "Epistemic Grounding",
                                    "concept_id": c_grounding_id,
                                    "depth_level": "IN_DEPTH",
                                    "depth_justification": "Conceito fundacional do qual dependem todos os capítulos seguintes.",
                                    "required_elements": [
                                        PedagogicalElementType.DEFINITION.value,
                                        PedagogicalElementType.CONTEXTUALIZATION.value,
                                        PedagogicalElementType.CONCEPTUAL_RELATIONS.value,
                                    ],
                                    "pedagogical_focus": {
                                        "what_it_is": "Vinculação explícita entre afirmações analíticas e spans verificáveis do documento.",
                                        "purpose": "Impedir deriva epistémica e apresentação de inferências como factos.",
                                        "how_it_works": "Associa cada claim a section_id, paragraph_id e página.",
                                        "why_relevant": "Garante fidelidade académica auditável.",
                                        "context_of_use": "Sistemas locais de compreensão de artigos científicos.",
                                        "known_limitations": "NOT_FOUND",
                                    },
                                    "epistemic_status": "SOURCE_FACT",
                                    "paragraph_ids": ["p_2", "p_3"],
                                }
                            ],
                            "related_section_ids": [
                                {"target_section_id": "ed_sec_01_02", "relation_type": "PREREQUISITE_FOR", "rationale": "Fornece o contrato de IDs usado pela segmentação."}
                            ],
                            "editorial_recommendations": ["Destacar a diferença entre SOURCE_FACT e MODEL_INFERENCE logo na abertura."],
                            "limitations_and_uncertainties": [],
                        },
                        {
                            "section_id": "ed_sec_01_02",
                            "explanation_strategy": "Explicar o mecanismo passo-a-passo de partição em fronteiras de frase respeitando o orçamento de tokens.",
                            "planned_pedagogical_elements": [
                                PedagogicalElementType.MECHANISM_OPERATION.value,
                                PedagogicalElementType.CONCEPTUAL_RELATIONS.value,
                            ],
                            "contents_to_cover": [
                                {
                                    "summary": "Partição adaptativa de secções respeitando fronteiras frásicas e preservando IDs para grounding.",
                                    "epistemic_status": "SOURCE_FACT",
                                    "source_section_id": "sec_bg",
                                    "paragraph_ids": ["p_4"],
                                }
                            ],
                            "pedagogical_treatments": [
                                {
                                    "target_topic_or_concept": "Adaptive Semantic Segmentation",
                                    "concept_id": c_seg_id,
                                    "depth_level": "IN_DEPTH",
                                    "depth_justification": "Mecanismo técnico nuclear que viabiliza o processamento sem truncamento.",
                                    "required_elements": [
                                        PedagogicalElementType.DEFINITION.value,
                                        PedagogicalElementType.MECHANISM_OPERATION.value,
                                    ],
                                    "pedagogical_focus": {
                                        "what_it_is": "Divisão semântica de secções dentro de limites estritos de tokens.",
                                        "purpose": "Evitar truncamento de contexto em documentos extensos.",
                                        "how_it_works": "Agrupa parágrafos e subdivide ao longo de fronteiras de frase mantendo paragraph_id.",
                                        "why_relevant": "Preserva a rastreabilidade exigida pelo Epistemic Grounding.",
                                        "context_of_use": "Fase Map do raciocínio hierárquico.",
                                        "known_limitations": "NOT_FOUND",
                                    },
                                    "epistemic_status": "SOURCE_FACT",
                                    "paragraph_ids": ["p_4"],
                                }
                            ],
                            "related_section_ids": [],
                            "editorial_recommendations": ["Relacionar diretamente com o orçamento de tokens do modelo local."],
                            "limitations_and_uncertainties": [],
                        },
                    ]
                }
            elif chap_id == "ed_chap_02":
                resp = {
                    "sections": [
                        {
                            "section_id": "ed_sec_02_01",
                            "explanation_strategy": "Detalhar a amostra (240 artigos), o desenho duplamente cego e as três métricas de avaliação.",
                            "planned_pedagogical_elements": [
                                PedagogicalElementType.COMPONENTS_CHARACTERISTICS.value,
                                PedagogicalElementType.MECHANISM_OPERATION.value,
                            ],
                            "contents_to_cover": [
                                {
                                    "summary": "Avaliação de 240 artigos revistos por pares sob auditoria forense duplamente cega.",
                                    "epistemic_status": "SOURCE_FACT",
                                    "source_section_id": "sec_method",
                                    "paragraph_ids": ["p_5", "p_6"],
                                }
                            ],
                            "pedagogical_treatments": [
                                {
                                    "target_topic_or_concept": "Forensic Audit Protocol",
                                    "concept_id": c_audit_id,
                                    "depth_level": "FOUNDATIONAL",
                                    "depth_justification": "Procedimento metodológico objetivo descrito diretamente na secção 3.",
                                    "required_elements": [
                                        PedagogicalElementType.DEFINITION.value,
                                        PedagogicalElementType.APPLICATIONS.value,
                                    ],
                                    "pedagogical_focus": {
                                        "what_it_is": "Protocolo duplamente cego de auditoria de precisão de referências e estados epistémicos.",
                                        "purpose": "Medir rigorosamente alucinações e cobertura documental.",
                                        "how_it_works": "Pontua precisão de referência, acurácia epistémica e completude.",
                                        "why_relevant": "Valida empiricamente a arquitetura proposta.",
                                        "context_of_use": "Benchmark de 240 artigos.",
                                        "known_limitations": "Latência dependente de GPU local.",
                                    },
                                    "epistemic_status": "SOURCE_FACT",
                                    "paragraph_ids": ["p_5", "p_6"],
                                }
                            ],
                            "related_section_ids": [],
                            "editorial_recommendations": [],
                            "limitations_and_uncertainties": [],
                        }
                    ]
                }
            else:
                resp = {
                    "sections": [
                        {
                            "section_id": "ed_sec_03_01",
                            "explanation_strategy": "Apresentar os dados quantitativos comparativos (61.2% vs 98.7%, p < 0.001 e 0.0% fabricações) ancorados na Tabela 1.",
                            "planned_pedagogical_elements": [
                                PedagogicalElementType.DETAILED_EXPLANATION.value,
                                PedagogicalElementType.GROUNDED_EXAMPLES.value,
                            ],
                            "contents_to_cover": [
                                {
                                    "summary": "Subida da precisão probatória de 61.2% para 98.7% (p < 0.001) e 0.0% de citações inventadas.",
                                    "epistemic_status": "SOURCE_FACT",
                                    "source_section_id": "sec_results",
                                    "paragraph_ids": ["p_7", "p_8"],
                                }
                            ],
                            "pedagogical_treatments": [],
                            "related_section_ids": [],
                            "editorial_recommendations": ["Contrastar os valores da baseline com a verificação AST."],
                            "limitations_and_uncertainties": [],
                        },
                        {
                            "section_id": "ed_sec_03_02",
                            "explanation_strategy": "Integrar os contributos globais e explicitar o trade-off de latência em GPU local.",
                            "planned_pedagogical_elements": [
                                PedagogicalElementType.ADVANTAGES_LIMITATIONS.value,
                                PedagogicalElementType.CONCEPTUAL_SYNTHESIS.value,
                            ],
                            "contents_to_cover": [
                                {
                                    "summary": "Alta fidelidade alcançada localmente, com latência limitada pelo throughput da GPU.",
                                    "epistemic_status": "SOURCE_FACT",
                                    "source_section_id": "sec_conc",
                                    "paragraph_ids": ["p_9"],
                                },
                                {
                                    "summary": "Síntese interpretativa da complementaridade entre segmentação e auditoria.",
                                    "epistemic_status": "MODEL_INFERENCE",
                                    "source_section_id": "sec_conc",
                                    "paragraph_ids": ["p_4", "p_9"],
                                },
                            ],
                            "pedagogical_treatments": [],
                            "related_section_ids": [],
                            "editorial_recommendations": [],
                            "limitations_and_uncertainties": ["A latência em hardware específico não é quantificada em milissegundos no artigo original."],
                        },
                    ]
                }
            return json.dumps(resp, ensure_ascii=False), {"status": "COMPLETED", "input_tokens": 700, "output_tokens": 550}

        if op == "editorial_visual_planning":
            resp = {
                "visual_plans": [
                    {
                        "visual_id": "vis_01",
                        "target_chapter_id": "ed_chap_01",
                        "target_section_id": "ed_sec_01_02",
                        "visual_type": VisualElementType.PROCESS_REPRESENTATION.value,
                        "title": "Fluxo de Segmentação Semântica Adaptativa e Grounding",
                        "pedagogical_objective": "Visualizar como uma secção longa é dividida sem perder os identificadores de parágrafo.",
                        "content_to_explain": "Relação operacional entre Adaptive Semantic Segmentation e Epistemic Grounding.",
                        "required_concepts_or_data": ["Epistemic Grounding", "Adaptive Semantic Segmentation"],
                        "information_to_represent": [
                            "Secção da AST com parágrafos numerados",
                            "Partição em fronteiras de frase dentro do orçamento de tokens",
                            "Preservação de paragraph_id e page_number até à síntese",
                        ],
                        "feasibility_status": VisualFeasibilityStatus.CONCEPTUAL_ONLY_NO_QUANT_DATA.value,
                        "source_table_ids": [],
                        "source_figure_ids": ["fig_1"],
                        "paragraph_ids": ["p_3", "p_4"],
                        "inclusion_justification": "Esclarece o mecanismo estrutural central descrito na secção 2 e referido na Figura 1 (cuja imagem original não foi interpretada automaticamente).",
                        "constraints_and_limitations": ["A Figura 1 original está marcada como IMAGE_ONLY_NOT_INTERPRETED; representar apenas o fluxo conceptual descrito textualmente em p_3 e p_4."],
                        "epistemic_status": "SOURCE_FACT",
                    },
                    {
                        "visual_id": "vis_02",
                        "target_chapter_id": "ed_chap_03",
                        "target_section_id": "ed_sec_03_01",
                        "visual_type": VisualElementType.COMPARATIVE_TABLE.value,
                        "title": "Comparação de Precisão de Referência: Baseline vs Hierarchical AST",
                        "pedagogical_objective": "Evidenciar o contraste empírico medido no benchmark de 240 artigos.",
                        "content_to_explain": "Resultados quantitativos de precisão probatória e redução de alucinações.",
                        "required_concepts_or_data": ["Baseline: 61.2%", "Hierarchical AST: 98.7%", "p < 0.001", "0.0% citações fabricadas"],
                        "information_to_represent": [
                            "Método Baseline: 61.2% de precisão",
                            "Método Hierarchical AST: 98.7% de precisão (p < 0.001)",
                            "Citações fabricadas com verificação AST: 0.0%",
                        ],
                        "feasibility_status": VisualFeasibilityStatus.SUFFICIENT_SOURCE_DATA.value,
                        "source_table_ids": ["tbl_1"],
                        "source_figure_ids": [],
                        "paragraph_ids": ["p_7", "p_8"],
                        "inclusion_justification": "Consolida os valores exatos da Tabela 1 reconstruída e dos parágrafos p_7 e p_8.",
                        "constraints_and_limitations": ["Não extrapolar métricas para além da amostra de 240 artigos."],
                        "epistemic_status": "SOURCE_FACT",
                    },
                ]
            }
            return json.dumps(resp, ensure_ascii=False), {"status": "COMPLETED", "input_tokens": 650, "output_tokens": 450}

        return json.dumps({}), {"status": "COMPLETED"}

    return caller


# ============================================================================
# Cenário A: Planeamento Editorial & Adaptação Estrutural
# ============================================================================

def test_01_valid_dossier_produces_complete_editorial_study_plan(tmp_path: Path):
    ast, dossier = build_empirical_ast_and_dossier()
    caller = make_mock_editorial_llm_caller(ast, dossier)

    engine = EditorialIntelligenceEngine(storage_dir=tmp_path / "study", llm_caller=caller)
    plan = engine.plan_study_document(dossier, ast=ast)

    assert isinstance(plan, EditorialStudyPlan)
    assert plan.metadata.status == "COMPLETED"
    assert plan.metadata.document_id == dossier.document_id
    assert plan.metadata.dossier_id == dossier.dossier_id
    assert plan.metadata.model_name == "qwen3.5:9b"
    assert plan.overview.document_nature == StudyDocumentNature.EMPIRICAL_RESEARCH_ARTICLE.value
    assert len(plan.chapters) == 3
    assert sum(len(ch.sections) for ch in plan.chapters) == 5
    assert plan.qa_report.is_valid is True
    assert plan.qa_report.blocking_errors_count == 0
    assert plan.qa_report.dossier_section_coverage_pct == 100.0


def test_02_adaptive_structure_theoretical_vs_empirical(tmp_path: Path):
    """Garante que um documento teórico sem metodologia empírica não impõe capítulos de resultados experimentais."""
    ast, dossier = build_empirical_ast_and_dossier("doc_theo_02", "sha256_theo")
    # Transformar num ensaio puramente teórico
    dossier.methodology_analysis = MethodologyAnalysis(is_applicable=False)
    dossier.results_and_evidence = []
    dossier.section_analyses = [
        sa for sa in dossier.section_analyses if sa.section_id in ("sec_intro", "sec_bg", "sec_conc")
    ]
    ast.sections = [s for s in ast.sections if s.section_id in ("sec_intro", "sec_bg", "sec_conc")]

    signals = EditorialDocumentPlanner.infer_document_signals(dossier, ast)
    assert signals["has_empirical_methodology"] is False
    assert signals["has_empirical_results"] is False
    assert signals["suggested_nature"] == StudyDocumentNature.THEORETICAL_CONCEPTUAL_PAPER.value


# ============================================================================
# Cenário B & C: Fidelidade Epistémica, Proveniência e Ordem Conceptual
# ============================================================================

def test_03_epistemic_preservation_and_provenance_integrity(tmp_path: Path):
    ast, dossier = build_empirical_ast_and_dossier()
    caller = make_mock_editorial_llm_caller(ast, dossier)

    engine = EditorialIntelligenceEngine(storage_dir=tmp_path / "study", llm_caller=caller)
    plan = engine.plan_study_document(dossier, ast=ast)

    # Verificar que inferências pedagógicas mantêm MODEL_INFERENCE e factos mantêm SOURCE_FACT com página exata da AST
    sec_3_2 = plan.chapters[2].sections[1]
    statuses = [item["epistemic_status"] for item in sec_3_2.contents_to_cover]
    assert "SOURCE_FACT" in statuses
    assert "MODEL_INFERENCE" in statuses

    # Verificar páginas resolvidas a partir da AST
    p7_refs = [
        ref for ch in plan.chapters for sec in ch.sections for ref in sec.evidence_refs if ref.paragraph_id == "p_7"
    ]
    assert len(p7_refs) >= 1
    assert all(r.page_number == 6 and r.section_id == "sec_results" for r in p7_refs)


def test_04_consistency_engine_detects_concept_before_introduction_and_dangling_refs():
    ast, dossier = build_empirical_ast_and_dossier()
    c_grounding = dossier.conceptual_analysis[0].concept_id
    c_seg = dossier.conceptual_analysis[1].concept_id

    # Criar plano com:
    # 1) Conceito c_grounding usado como pré-requisito no Cap 1 antes de ser introduzido no Cap 2 (WARNING)
    # 2) Referência a parágrafo inexistente 'p_999' (BLOCKING_ERROR)
    bad_plan = EditorialStudyPlan(
        metadata=EditorialPlanMetadata(
            plan_id="plan_bad",
            document_id=dossier.document_id,
            source_sha256=dossier.source_sha256,
            ast_version=dossier.ast_version,
            dossier_id=dossier.dossier_id,
            dossier_schema_version=dossier.schema_version,
            dossier_engine_version=dossier.engine_version,
            dossier_fingerprint=compute_dossier_fingerprint(dossier),
        ),
        overview=EditorialOverview(
            central_theme="Tema central sobre Epistemic Grounding",
            document_nature=StudyDocumentNature.EMPIRICAL_RESEARCH_ARTICLE.value,
        ),
        chapters=[
            EditorialChapter(
                chapter_id="ed_chap_01",
                title="Aplicação Avançada Prematura",
                pedagogical_objective="Usar segmentação antes da base",
                description="Cap 1",
                order=1,
                original_section_ids=["sec_bg"],
                key_concept_ids=[c_seg],
                sections=[
                    EditorialSection(
                        section_id="ed_sec_01_01",
                        chapter_id="ed_chap_01",
                        title="Segmentação",
                        pedagogical_objective="Explicar segmentação",
                        associated_concept_ids=[c_seg, c_grounding],
                        introduced_concept_ids=[c_seg],
                        prerequisite_concept_ids=[c_grounding],
                        original_section_ids=["sec_bg"],
                        evidence_refs=[
                            EvidenceRef(section_id="sec_bg", paragraph_id="p_999", page_number=2, status="SOURCE_FACT")
                        ],
                    )
                ],
            ),
            EditorialChapter(
                chapter_id="ed_chap_02",
                title="Introdução Tardia da Base",
                pedagogical_objective="Introduzir Epistemic Grounding",
                description="Cap 2",
                order=2,
                original_section_ids=["sec_intro"],
                key_concept_ids=[c_grounding],
                sections=[
                    EditorialSection(
                        section_id="ed_sec_02_01",
                        chapter_id="ed_chap_02",
                        title="Definição Tardia",
                        pedagogical_objective="Definir grounding",
                        associated_concept_ids=[c_grounding],
                        introduced_concept_ids=[c_grounding],
                        prerequisite_concept_ids=[],
                        original_section_ids=["sec_intro"],
                        evidence_refs=[
                            EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=1, status="SOURCE_FACT")
                        ],
                    )
                ],
            ),
        ],
        conceptual_relationships=[
            EditorialConceptRelationship(
                relationship_id="rel_1",
                source_concept_id=c_grounding,
                source_concept_name="Epistemic Grounding",
                target_concept_id=c_seg,
                target_concept_name="Adaptive Semantic Segmentation",
                relation_type=ConceptRelationType.PREREQUISITE_FOR.value,
                is_hierarchical=True,
                pedagogical_dependency="SOURCE_BEFORE_TARGET",
                justification="Base antes do mecanismo.",
            )
        ],
    )

    qa = EditorialConsistencyEngine().evaluate(bad_plan, dossier=dossier, ast=ast)
    codes = {f.code for f in qa.findings}
    assert "DANGLING_REFERENCE" in codes
    assert "CONCEPT_USED_BEFORE_INTRODUCTION" in codes
    assert "COVERAGE_GAP" in codes
    assert qa.is_valid is False
    assert qa.blocking_errors_count >= 1
    assert "p_999" in qa.invalid_paragraph_refs


# ============================================================================
# Cenário D: Planeamento Visual e Proibição de Dados Inventados
# ============================================================================

def test_05_visual_planner_flags_quantitative_chart_when_no_data_exists():
    ast, dossier = build_empirical_ast_and_dossier("doc_no_quant", "sha_no_quant")
    # Remover todos os dados quantitativos e tabelas reconstruídas
    dossier.results_and_evidence = []
    ast.tables = []
    for p in ast.paragraphs:
        p.text = "Conceptual discussion without any numerical measurements or statistical metrics."

    raw_visuals = [
        {
            "visual_id": "vis_bad_chart",
            "target_chapter_id": "ed_chap_01",
            "target_section_id": "ed_sec_01_01",
            "visual_type": VisualElementType.DATA_CHART.value,
            "title": "Gráfico Quantitativo sem Suporte",
            "pedagogical_objective": "Mostrar evolução numérica",
            "content_to_explain": "Evolução de desempenho",
            "required_concepts_or_data": ["Epistemic Grounding"],
            "information_to_represent": ["Curva de precisão"],
            "feasibility_status": VisualFeasibilityStatus.SUFFICIENT_SOURCE_DATA.value,
            "paragraph_ids": ["p_1"],
            "inclusion_justification": "Facilitar leitura",
            "constraints_and_limitations": [],
        }
    ]

    planner = VisualContentPlanner()
    validated = planner.validate_and_ground_visuals(
        raw_visuals,
        dossier=dossier,
        ast=ast,
        valid_chapter_ids={"ed_chap_01"},
        valid_section_ids={"ed_sec_01_01"},
        paragraphs_index={p.paragraph_id: (p.section_id, p.page_number, p.text) for p in ast.paragraphs},
    )

    assert len(validated) == 1
    v = validated[0]
    assert v.feasibility_status in (
        VisualFeasibilityStatus.CONCEPTUAL_ONLY_NO_QUANT_DATA.value,
        VisualFeasibilityStatus.INSUFFICIENT_DATA_LIMITATION.value,
    )
    assert len(v.constraints_and_limitations) >= 1


# ============================================================================
# Cenário E: Checkpoints, Persistência, Indisponibilidade e Cancelamento
# ============================================================================

def test_06_checkpoint_recovery_and_persistence_without_corrupting_phase2_3(tmp_path: Path):
    storage_dir = tmp_path / "study"
    ast, dossier = build_empirical_ast_and_dossier("doc_cp_06", "sha_cp_06")
    doc_dir = storage_dir / "documents" / dossier.document_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Persistir artefactos das Fases 2 e 3 para confirmar que permanecem intactos
    ast_bytes_before = json.dumps(ast.to_dict(), indent=2, ensure_ascii=False)
    dossier_bytes_before = json.dumps(dossier.to_dict(), indent=2, ensure_ascii=False)
    (doc_dir / "ast.json").write_text(ast_bytes_before, encoding="utf-8")
    (doc_dir / "reasoning_dossier.json").write_text(dossier_bytes_before, encoding="utf-8")

    base_caller = make_mock_editorial_llm_caller(ast, dossier)
    stage1_calls: List[str] = []

    def interrupted_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        chap = meta.get("chapter_id", "")
        stage1_calls.append(f"{op}:{chap}")
        if op == "editorial_chapter_pedagogy" and chap == "ed_chap_02":
            raise RuntimeError("Interrupção simulada a meio do planeamento editorial!")
        return base_caller(sys_p, usr_p, meta)

    engine1 = EditorialIntelligenceEngine(storage_dir=storage_dir, llm_caller=interrupted_caller)
    with pytest.raises(RuntimeError):
        engine1.plan_study_document(dossier, ast=ast)

    cp_file = doc_dir / "editorial_checkpoint.json"
    assert cp_file.exists()

    # Retomar com segundo motor
    resumed_calls: List[str] = []

    def resumed_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        chap = meta.get("chapter_id", "")
        resumed_calls.append(f"{op}:{chap}")
        return base_caller(sys_p, usr_p, meta)

    engine2 = EditorialIntelligenceEngine(storage_dir=storage_dir, llm_caller=resumed_caller)
    plan = engine2.plan_study_document(dossier, ast=ast)

    assert plan.metadata.status == "COMPLETED"
    # Macro-planeamento e Capítulo 1 já estavam no checkpoint -> não repetidos!
    assert "editorial_macro_planning:" not in resumed_calls
    assert "editorial_chapter_pedagogy:ed_chap_01" not in resumed_calls
    assert "editorial_chapter_pedagogy:ed_chap_02" in resumed_calls

    # Confirmar persistência independente e integridade das Fases 2 e 3
    plan_file = doc_dir / "editorial_study_plan.json"
    assert plan_file.exists()
    reloaded = EditorialStudyPlan.from_dict(json.loads(plan_file.read_text(encoding="utf-8")))
    assert reloaded.metadata.plan_id == plan.metadata.plan_id
    assert len(reloaded.chapters) == 3
    assert (doc_dir / "ast.json").read_text(encoding="utf-8") == ast_bytes_before
    assert (doc_dir / "reasoning_dossier.json").read_text(encoding="utf-8") == dossier_bytes_before


def test_07_ollama_unavailable_raises_explicit_error(tmp_path: Path):
    ast, dossier = build_empirical_ast_and_dossier("doc_unavail_07")

    def broken_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return None, {"status": "UNAVAILABLE", "error": "Connection refused"}

    engine = EditorialIntelligenceEngine(storage_dir=tmp_path / "study", llm_caller=broken_caller, max_retries_per_call=1)
    with pytest.raises(OllamaInferenceUnavailableError):
        engine.plan_study_document(dossier, ast=ast)


# ============================================================================
# Cenários Adicionais A–F: Cobertura Exaustiva de Engenharia Editorial
# ============================================================================

def test_08_adaptive_structure_technical_manual_and_lecture_detection():
    """Valida a deteção adaptativa de manuais técnicos, relatórios e materiais didáticos."""
    _, dossier_tech = build_empirical_ast_and_dossier("doc_tech_08", "sha_tech")
    dossier_tech.methodology_analysis = MethodologyAnalysis(is_applicable=False)
    dossier_tech.results_and_evidence = []
    dossier_tech.section_analyses[0].title = "1. Arquitetura do Sistema e Protocolo CLI"
    sig_tech = EditorialDocumentPlanner.infer_document_signals(dossier_tech)
    assert sig_tech["suggested_nature"] == StudyDocumentNature.TECHNICAL_MANUAL_SPEC.value

    _, dossier_lec = build_empirical_ast_and_dossier("doc_lec_08", "sha_lec")
    dossier_lec.methodology_analysis = MethodologyAnalysis(is_applicable=False)
    dossier_lec.results_and_evidence = []
    dossier_lec.section_analyses[0].title = "Módulo 1: Diapositivos da Aula e Exercícios"
    sig_lec = EditorialDocumentPlanner.infer_document_signals(dossier_lec)
    assert sig_lec["suggested_nature"] == StudyDocumentNature.STUDY_MATERIAL_LECTURE.value


def test_09_non_hierarchical_and_hierarchical_conceptual_relationships_preserved(tmp_path: Path):
    """Confirma que relações não hierárquicas (COMPLEMENTARY, CONTRASTING) coexistem com pré-requisitos."""
    ast, dossier = build_empirical_ast_and_dossier("doc_rels_09")
    c_grounding_id = dossier.conceptual_analysis[0].concept_id
    c_seg_id = dossier.conceptual_analysis[1].concept_id
    c_audit_id = dossier.conceptual_analysis[2].concept_id

    base_caller = make_mock_editorial_llm_caller(ast, dossier)

    def caller_with_contrast(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        raw_str, tel = base_caller(sys_p, usr_p, meta)
        if meta.get("operation") == "editorial_macro_planning":
            obj = json.loads(raw_str)
            obj["conceptual_relationships"].append(
                {
                    "source_concept_id": c_grounding_id,
                    "target_concept_id": c_audit_id,
                    "relation_type": ConceptRelationType.CONTRASTING.value,
                    "is_hierarchical": True,  # Mesmo que o modelo envie True por engano, CONTRASTING não é hierárquico!
                    "pedagogical_dependency": "CONTRASTIVE_SYNTHESIS",
                    "justification": "Contraste entre especificação declarativa e auditoria pós-execução.",
                    "epistemic_status": "MODEL_INFERENCE",
                    "paragraph_ids": ["p_3", "p_5"],
                }
            )
            return json.dumps(obj, ensure_ascii=False), tel
        return raw_str, tel

    engine = EditorialIntelligenceEngine(storage_dir=tmp_path / "study", llm_caller=caller_with_contrast)
    plan = engine.plan_study_document(dossier, ast=ast)

    rel_types = {r.relation_type: r for r in plan.conceptual_relationships}
    assert ConceptRelationType.PREREQUISITE_FOR.value in rel_types
    assert rel_types[ConceptRelationType.PREREQUISITE_FOR.value].is_hierarchical is True
    assert ConceptRelationType.COMPLEMENTARY.value in rel_types
    assert rel_types[ConceptRelationType.COMPLEMENTARY.value].is_hierarchical is False
    assert ConceptRelationType.CONTRASTING.value in rel_types
    assert rel_types[ConceptRelationType.CONTRASTING.value].is_hierarchical is False


def test_10_pedagogical_explanation_planner_selective_elements_and_downgrades_unanchored_fact(tmp_path: Path):
    """Confirma que SOURCE_FACT sem paragraph_id é reclassificado honestamente para MODEL_INFERENCE."""
    ast, dossier = build_empirical_ast_and_dossier("doc_ped_10")
    base_caller = make_mock_editorial_llm_caller(ast, dossier)

    def caller_unanchored_fact(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        raw_str, tel = base_caller(sys_p, usr_p, meta)
        if meta.get("operation") == "editorial_chapter_pedagogy" and meta.get("chapter_id") == "ed_chap_01":
            obj = json.loads(raw_str)
            # Tentar passar SOURCE_FACT sem paragraph_ids
            obj["sections"][0]["contents_to_cover"].append(
                {
                    "summary": "Contextualização pedagógica inferida sem parágrafo explícito.",
                    "epistemic_status": "SOURCE_FACT",
                    "source_section_id": "sec_intro",
                    "paragraph_ids": [],
                }
            )
            return json.dumps(obj, ensure_ascii=False), tel
        return raw_str, tel

    engine = EditorialIntelligenceEngine(storage_dir=tmp_path / "study", llm_caller=caller_unanchored_fact)
    plan = engine.plan_study_document(dossier, ast=ast)

    sec_01 = plan.chapters[0].sections[0]
    # Elementos selecionados de forma parcimoniosa (< 10 elementos disponíveis)
    assert 1 <= len(sec_01.planned_pedagogical_elements) <= 5
    inferred_item = next(c for c in sec_01.contents_to_cover if "Contextualização pedagógica" in c["summary"])
    assert inferred_item["epistemic_status"] == EpistemicStatus.MODEL_INFERENCE.value
    assert plan.qa_report.is_valid is True


def test_11_consistency_engine_three_tier_severity_warnings_do_not_block_plan():
    """Garante que avisos menores e recomendações não bloqueiam o plano (is_valid=True), ao contrário de erros impeditivos."""
    ast, dossier = build_empirical_ast_and_dossier("doc_sev_11")
    c_grounding = dossier.conceptual_analysis[0].concept_id

    # Criar 7 micro-secções sobre uma única secção original -> RECOMMENDATION (EXCESSIVE_FRAGMENTATION)
    # E omitir sec_conc -> WARNING (COVERAGE_GAP)
    micro_sections = [
        EditorialSection(
            section_id=f"ed_sec_01_{i:02d}",
            chapter_id="ed_chap_01",
            title=f"Subtópico {i}",
            order=i,
            pedagogical_objective=f"Explicar faceta {i}",
            associated_concept_ids=[c_grounding],
            introduced_concept_ids=[c_grounding] if i == 1 else [],
            original_section_ids=["sec_intro"],
            evidence_refs=[EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=1, status="SOURCE_FACT")],
        )
        for i in range(1, 8)
    ]

    plan_warn = EditorialStudyPlan(
        metadata=EditorialPlanMetadata(plan_id="p_warn", document_id=dossier.document_id),
        overview=EditorialOverview(central_theme="Tema", document_nature=StudyDocumentNature.EMPIRICAL_RESEARCH_ARTICLE.value),
        chapters=[
            EditorialChapter(
                chapter_id="ed_chap_01",
                title="Capítulo Fragmentado",
                pedagogical_objective="Objetivo válido",
                order=1,
                original_section_ids=["sec_intro"],
                key_concept_ids=[c_grounding],
                sections=micro_sections,
            )
        ],
    )

    qa = EditorialConsistencyEngine().evaluate(plan_warn, dossier=dossier, ast=ast)
    assert qa.blocking_errors_count == 0
    assert qa.warnings_count >= 1
    assert qa.recommendations_count >= 1
    assert qa.is_valid is True
    assert qa.validation_status == "VALID_WITH_WARNINGS"


def test_12_extensive_dossier_hierarchical_reduction_and_strict_context_budget(tmp_path: Path):
    """Testa um dossier extenso sob orçamento apertado (3600 tokens), provando redução hierárquica sem truncamento."""
    sections = []
    paragraphs = []
    sec_analyses = []
    for i in range(1, 13):
        sid = f"sec_{i:02d}"
        pid = f"p_{i:02d}"
        sections.append(ASTSection(section_id=sid, title=f"Section {i}: Domain Module", level=1, kind="body", page_start=i, page_end=i))
        paragraphs.append(ASTParagraph(pid, sid, f"Empirical measurement {i} achieved 91.{i}% accuracy across distributed nodes.", i, i, i))
        sec_analyses.append(
            SectionAnalysis(
                section_id=sid,
                title=f"Section {i}: Domain Module",
                section_type="body",
                objective=f"Analyze architectural module {i} in detail across multiple operational regimes.",
                in_depth_synthesis=(
                    f"Extensive synthesis for module {i}: "
                    + ("detailed academic reasoning about distributed state convergence and epistemic verification. " * 12)
                ),
                core_ideas=[f"Core idea {i}.1", f"Core idea {i}.2"],
                source_refs=[EvidenceRef(section_id=sid, paragraph_id=pid, page_number=i, status="SOURCE_FACT")],
                segment_ids=[f"{sid}_seg_0"],
            )
        )

    ast = AcademicDocumentAST(
        document_id="doc_ext_12",
        extractor_version="2.0.0",
        source_sha256="sha_ext_12",
        filename="extensive.pdf",
        metadata=DocumentMetadata(title="Extensive Multi-Section Study", page_count=12, source_sha256="sha_ext_12"),
        pages=[PageInfo(page_number=i) for i in range(1, 13)],
        sections=sections,
        paragraphs=paragraphs,
        report=ExtractionReport(status="COMPLETED", total_pages=12),
    )
    dossier = AcademicReasoningDossier(
        dossier_id="dos_ext_12",
        document_id="doc_ext_12",
        source_sha256="sha_ext_12",
        ast_version="2.0.0",
        status="COMPLETED",
        document_analysis=DocumentCoreAnalysis(
            document_id="doc_ext_12",
            title="Extensive Multi-Section Study",
            global_objective="Evaluate 12 modules",
            research_problem="Scale",
            central_thesis="Modular convergence",
        ),
        section_analyses=sec_analyses,
        cross_section_synthesis=CrossSectionSynthesis(global_synthesis="Global 12-module synthesis."),
    )

    prompts_seen: List[Tuple[str, str, str]] = []

    def tracking_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        prompts_seen.append((sys_p, usr_p, op))
        if op == "editorial_dossier_cluster_digest":
            # Extrair os IDs presentes no cluster
            found_sids = [f"sec_{i:02d}" for i in range(1, 13) if f"[sec_{i:02d}]" in usr_p or f"sec_{i:02d}" in usr_p]
            return json.dumps(
                {
                    "cluster_editorial_digest": f"Síntese compacta para {', '.join(found_sids)}.",
                    "preserved_section_ids": found_sids,
                    "key_concepts_and_refs": [f"Ref {s}" for s in found_sids],
                },
                ensure_ascii=False,
            ), {"status": "COMPLETED"}
        if op == "editorial_macro_planning":
            return json.dumps(
                {
                    "document_nature": StudyDocumentNature.TECHNICAL_MANUAL_SPEC.value,
                    "central_theme": "Arquitetura modular de 12 subsistemas",
                    "central_theme_status": "MODEL_INFERENCE",
                    "target_audience": "Engenheiros de sistemas",
                    "target_audience_basis": "MODEL_INFERENCE",
                    "recommended_structure_rationale": "Agrupamento em 2 capítulos de 6 módulos.",
                    "editorial_strategy": "Progressão modular",
                    "global_organization_summary": "2 capítulos",
                    "learning_objectives": [{"objective_id": "lo_1", "description": "Dominar os 12 módulos", "epistemic_status": "MODEL_INFERENCE", "source_section_ids": ["sec_01"]}],
                    "chapters": [
                        {
                            "chapter_id": "ed_chap_01",
                            "title": "Módulos Base 1-6",
                            "pedagogical_objective": "Compreender módulos 1 a 6",
                            "order": 1,
                            "original_section_ids": [f"sec_{i:02d}" for i in range(1, 7)],
                            "sections": [
                                {
                                    "section_id": "ed_sec_01_01",
                                    "title": "Núcleo 1-6",
                                    "order": 1,
                                    "pedagogical_objective": "Estudar sec_01 a sec_06",
                                    "original_section_ids": [f"sec_{i:02d}" for i in range(1, 7)],
                                }
                            ],
                        },
                        {
                            "chapter_id": "ed_chap_02",
                            "title": "Módulos Avançados 7-12",
                            "pedagogical_objective": "Compreender módulos 7 a 12",
                            "order": 2,
                            "original_section_ids": [f"sec_{i:02d}" for i in range(7, 13)],
                            "learning_dependencies": ["ed_chap_01"],
                            "sections": [
                                {
                                    "section_id": "ed_sec_02_01",
                                    "title": "Núcleo 7-12",
                                    "order": 1,
                                    "pedagogical_objective": "Estudar sec_07 a sec_12",
                                    "original_section_ids": [f"sec_{i:02d}" for i in range(7, 13)],
                                }
                            ],
                        },
                    ],
                },
                ensure_ascii=False,
            ), {"status": "COMPLETED"}
        if op == "editorial_chapter_pedagogy":
            cid = meta.get("chapter_id")
            sid = "ed_sec_01_01" if cid == "ed_chap_01" else "ed_sec_02_01"
            pid = "p_01" if cid == "ed_chap_01" else "p_07"
            orig = "sec_01" if cid == "ed_chap_01" else "sec_07"
            return json.dumps(
                {
                    "sections": [
                        {
                            "section_id": sid,
                            "explanation_strategy": "Explicação modular progressiva",
                            "planned_pedagogical_elements": ["DEFINITION", "MECHANISM_OPERATION"],
                            "contents_to_cover": [{"summary": "Síntese verificada", "epistemic_status": "SOURCE_FACT", "source_section_id": orig, "paragraph_ids": [pid]}],
                            "pedagogical_treatments": [],
                        }
                    ]
                },
                ensure_ascii=False,
            ), {"status": "COMPLETED"}
        return json.dumps({"visual_plans": []}), {"status": "COMPLETED"}

    engine = EditorialIntelligenceEngine(
        storage_dir=tmp_path / "study",
        llm_caller=tracking_caller,
        total_context_limit=3800,
        default_max_output_tokens=900,
        safety_buffer_tokens=300,
    )
    plan = engine.plan_study_document(dossier, ast=ast)

    assert plan.metadata.status == "COMPLETED"
    assert len(plan.telemetry.hierarchical_aggregations) >= 1
    assert plan.qa_report.dossier_section_coverage_pct == 100.0
    for s_p, u_p, op_name in prompts_seen:
        insp = engine.budget_manager.inspect_budget(s_p, u_p, max_output_tokens=900)
        assert insp["fits"] is True, f"Operação {op_name} excedeu orçamento ({insp['total_required_tokens']} > 3800)"


def test_13_impossible_context_budget_raises_explicit_error(tmp_path: Path):
    """Confirma que um orçamento fisicamente impossível lança ContextBudgetExceededError explícito."""
    ast, dossier = build_empirical_ast_and_dossier("doc_tiny_budget")
    caller = make_mock_editorial_llm_caller(ast, dossier)

    engine = EditorialIntelligenceEngine(
        storage_dir=tmp_path / "study",
        llm_caller=caller,
        total_context_limit=500,
        default_max_output_tokens=300,
        safety_buffer_tokens=200,
    )
    with pytest.raises(ContextBudgetExceededError):
        engine.plan_study_document(dossier, ast=ast)


def test_14_checkpoint_invalidation_and_plan_version_history_on_reprocessing(tmp_path: Path):
    """Verifica invalidação de checkpoint por mudança no dossier e histórico versionado no reprocessamento."""
    storage_dir = tmp_path / "study"
    ast, dossier = build_empirical_ast_and_dossier("doc_ver_14", "sha_v1")
    caller = make_mock_editorial_llm_caller(ast, dossier)
    engine = EditorialIntelligenceEngine(storage_dir=storage_dir, llm_caller=caller)

    plan_v1 = engine.plan_study_document(dossier, ast=ast)
    assert plan_v1.metadata.plan_version == 1

    # Alterar o dossier -> is_plan_up_to_date passa a False (DOSSIER_CHANGED)
    dossier.document_analysis.central_thesis = "Nova tese revista após reprocessamento da Fase 3."
    up_to_date, reason = engine.is_plan_up_to_date(plan_v1, dossier)
    assert up_to_date is False
    assert reason == "DOSSIER_CHANGED"

    # Novo planeamento arquiva v1 em editorial_plan_history e incrementa para v2
    plan_v2 = engine.plan_study_document(dossier, ast=ast)
    assert plan_v2.metadata.plan_version == 2
    assert plan_v2.metadata.previous_plan_id == plan_v1.metadata.plan_id
    hist_files = list((storage_dir / "documents" / "doc_ver_14" / "editorial_plan_history").glob("v001_*.json"))
    assert len(hist_files) == 1


def test_15_cooperative_cancellation_and_explicit_partial_or_failed_states(tmp_path: Path):
    """Verifica cancelamento cooperativo, rejeição de dossier FAILED e estados PARTIAL/FAILED sem falsos completos."""
    from services.editorial_intelligence_engine import InvalidReasoningDossierError

    ast, dossier = build_empirical_ast_and_dossier("doc_states_15")
    caller = make_mock_editorial_llm_caller(ast, dossier)

    # 1. Dossier FAILED é recusado à entrada
    failed_dossier = AcademicReasoningDossier(dossier_id="bad", document_id="doc_states_15", status="FAILED")
    engine = EditorialIntelligenceEngine(storage_dir=tmp_path / "s1", llm_caller=caller)
    with pytest.raises(InvalidReasoningDossierError):
        engine.plan_study_document(failed_dossier)

    # 2. Cancelamento cooperativo lança EditorialPlanningCancelledError
    with pytest.raises(EditorialPlanningCancelledError):
        engine.plan_study_document(dossier, ast=ast, cancellation_check=lambda: True)

    # 3. Falha JSON na etapa macro produz status="FAILED" explícito (zero capítulos inventados)
    engine_fail = EditorialIntelligenceEngine(
        storage_dir=tmp_path / "s2",
        llm_caller=lambda s, u, m: ("isto não é json", {"status": "INVALID"}),
        max_retries_per_call=1,
    )
    failed_plan = engine_fail.plan_study_document(dossier, ast=ast)
    assert failed_plan.metadata.status == "FAILED"
    assert failed_plan.chapters == []
    assert len(failed_plan.failed_operations) >= 1

    # 4. Falha parcial num capítulo marca status="PARTIAL" e regista a falha
    def partial_caller(s: str, u: str, m: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        if m.get("operation") == "editorial_chapter_pedagogy" and m.get("chapter_id") == "ed_chap_02":
            return "json_corrompido_irreversivel", {"status": "INVALID"}
        return caller(s, u, m)

    engine_partial = EditorialIntelligenceEngine(storage_dir=tmp_path / "s3", llm_caller=partial_caller, max_retries_per_call=1)
    partial_plan = engine_partial.plan_study_document(dossier, ast=ast)
    assert partial_plan.metadata.status == "PARTIAL"
    assert any(op.get("chapter_id") == "ed_chap_02" for op in partial_plan.failed_operations)


def test_16_study_service_and_websocket_handler_integration(tmp_path: Path):
    """Testa integração ponta-a-ponta simulada com StudyService e StudyWebSocketHandler."""
    import asyncio
    from backend.websocket.context import WebSocketSessionState
    from backend.websocket.handlers.study import StudyWebSocketHandler

    storage_dir = tmp_path / "study"
    vault_dir = tmp_path / "vault"
    service = StudyService(storage_dir=str(storage_dir), vault_root=str(vault_dir), workspace_root=str(tmp_path))

    ast, dossier = build_empirical_ast_and_dossier("doc_ws_16", "sha_ws_16")
    doc_dir = storage_dir / "documents" / "doc_ws_16"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "ast.json").write_text(json.dumps(ast.to_dict(), ensure_ascii=False), encoding="utf-8")
    (doc_dir / "reasoning_dossier.json").write_text(json.dumps(dossier.to_dict(), ensure_ascii=False), encoding="utf-8")

    st_before = service.get_editorial_plan_status("doc_ws_16")
    assert st_before["state"] == "NOT_GENERATED"
    assert st_before["has_dossier"] is True
    assert st_before["has_ast"] is True

    caller = make_mock_editorial_llm_caller(ast, dossier)
    generated = service.generate_editorial_study_plan("doc_ws_16", llm_caller=caller)
    assert generated is not None
    assert generated["metadata"]["status"] == "COMPLETED"

    st_after = service.get_editorial_plan_status("doc_ws_16")
    assert st_after["state"] == "COMPLETED"
    assert st_after["has_plan"] is True
    assert st_after["is_stale"] is False

    # Testar StudyWebSocketHandler.get_editorial_plan
    sent_messages: List[Dict[str, Any]] = []

    class DummyConnections:
        async def send(self, ws: Any, payload: Dict[str, Any]) -> None:
            sent_messages.append(payload)

    handler = StudyWebSocketHandler(DummyConnections(), service)
    asyncio.run(
        handler.get_editorial_plan(
            websocket=object(),
            message={"type": "study_get_editorial_plan", "document_id": "doc_ws_16", "request_id": "req_42"},
            _session=WebSocketSessionState(),
        )
    )
    assert len(sent_messages) == 1
    assert sent_messages[0]["type"] == "study_editorial_plan_result"
    assert sent_messages[0]["request_id"] == "req_42"
    assert sent_messages[0]["plan"]["metadata"]["document_id"] == "doc_ws_16"
    assert sent_messages[0]["plan_status"]["state"] == "COMPLETED"


# ============================================================================
# Cenário G: Teste de Integração Real com Ollama Local (qwen3.5:9b) sobre PDF Real
# ============================================================================

@pytest.mark.skipif(
    os.environ.get("STUDY_FORCE_LIVE_LLM") not in ("1", "true", "yes"),
    reason="Executado quando STUDY_FORCE_LIVE_LLM=1 está ativo para aferição real com Ollama local (qwen3.5:9b).",
)
def test_17_real_pdf_ollama_qwen_end_to_end_pipeline(tmp_path: Path):
    """
    Valida o percurso completo:
      Original PDF -> AcademicDocumentAST -> AcademicReasoningDossier -> EditorialStudyPlan
    usando um documento académico real e inferência local exclusiva no modelo qwen3.5:9b.
    """
    repo_root = Path(__file__).resolve().parent.parent
    custom_pdf = os.environ.get("STUDY_E2E_PDF_PATH")
    real_pdf = (
        Path(custom_pdf)
        if custom_pdf
        else repo_root / "data" / "study" / "a3b336f4295d0d51_Predicting_performance_online_consumer_reviews(1).pdf"
    )
    assert real_pdf.exists(), f"PDF académico real não encontrado em {real_pdf}"

    storage_dir = tmp_path / "real_study_e2e"
    assets_dir = storage_dir / "documents" / "doc_real_reviews" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fase 2 — Extração real da AcademicDocumentAST a partir do PDF original
    t0 = time.perf_counter()
    pdf_to_extract = real_pdf
    excerpt_pages = int(os.environ.get("STUDY_E2E_MAX_PAGES", "0"))
    if excerpt_pages > 0:
        import pymupdf
        sub_pdf = tmp_path / "real_academic_excerpt.pdf"
        src_doc = pymupdf.open(str(real_pdf))
        out_doc = pymupdf.open()
        out_doc.insert_pdf(src_doc, from_page=0, to_page=min(excerpt_pages - 1, src_doc.page_count - 1))
        out_doc.save(str(sub_pdf))
        out_doc.close()
        src_doc.close()
        pdf_to_extract = sub_pdf

    extractor = DocumentIntelligenceExtractor(assets_dir=assets_dir)
    ast = extractor.extract(str(pdf_to_extract), "doc_real_reviews", filename=real_pdf.name)
    phase2_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    assert len(ast.sections) >= 2
    assert len(ast.paragraphs) >= 10

    doc_dir = storage_dir / "documents" / "doc_real_reviews"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "ast.json").write_text(json.dumps(ast.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Fase 3 — AcademicReasoningEngine real com Ollama qwen3.5:9b
    reasoning_engine = AcademicReasoningEngine(storage_dir=storage_dir)
    dossier = reasoning_engine.analyze_document(ast)
    assert dossier.status in ("COMPLETED", "PARTIAL")
    assert len(dossier.section_analyses) >= 1

    # 3. Fase 4 — EditorialIntelligenceEngine real com Ollama qwen3.5:9b
    editorial_engine = EditorialIntelligenceEngine(storage_dir=storage_dir)
    plan = editorial_engine.plan_study_document(dossier, ast=ast)

    print(f"\n[E2E REAL PDF->AST->DOSSIER->EDITORIAL PLAN]")
    print(f"  Phase 2 AST ms: {phase2_ms} | Pages: {ast.metadata.page_count} | Sections: {len(ast.sections)} | Paras: {len(ast.paragraphs)}")
    print(f"  Phase 3 Dossier status: {dossier.status} | LLM calls: {dossier.telemetry.total_llm_calls} | Duration ms: {dossier.telemetry.total_duration_ms}")
    print(f"  Phase 4 Editorial status: {plan.metadata.status} | Nature: {plan.overview.document_nature}")
    print(f"  Phase 4 LLM calls: {plan.telemetry.total_llm_calls} | Retries: {plan.telemetry.retries_count} | Failures: {plan.telemetry.failures_count} | Duration ms: {plan.telemetry.total_duration_ms}")
    print(f"  Phase 4 Tokens (in/out actual): {plan.telemetry.actual_input_tokens}/{plan.telemetry.actual_output_tokens} | Est: {plan.telemetry.input_tokens_est}/{plan.telemetry.output_tokens_est}")
    print(f"  Phase 4 Chapters: {len(plan.chapters)} | Visuals: {len(plan.visual_plans)} | QA: {plan.qa_report.validation_status} (valid_refs={plan.qa_report.valid_evidence_refs_pct}%)")

    dump_path = os.environ.get("STUDY_E2E_DUMP_PLAN_PATH")
    if dump_path:
        Path(dump_path).write_text(
            json.dumps(
                {
                    "phase2_ms": phase2_ms,
                    "ast_summary": {
                        "title": ast.metadata.title,
                        "pages": ast.metadata.page_count,
                        "sections": len(ast.sections),
                        "paragraphs": len(ast.paragraphs),
                        "tables": len(ast.tables),
                        "figures": len(ast.figures),
                    },
                    "dossier_summary": {
                        "dossier_id": dossier.dossier_id,
                        "status": dossier.status,
                        "sections_analyzed": len(dossier.section_analyses),
                        "concepts_count": len(dossier.conceptual_analysis),
                        "llm_calls": dossier.telemetry.total_llm_calls,
                        "duration_ms": dossier.telemetry.total_duration_ms,
                    },
                    "plan": plan.to_dict(),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    assert plan.metadata.status == "COMPLETED"
    assert plan.qa_report.is_valid is True
    assert plan.qa_report.blocking_errors_count == 0
    assert len(plan.chapters) >= 1
    assert sum(len(ch.sections) for ch in plan.chapters) >= 1
    assert (doc_dir / "editorial_study_plan.json").exists()


def test_18_dense_10_section_33_concept_dossier_hierarchical_convergence(tmp_path: Path):
    """
    Reproduz o perfil denso de um artigo empírico real com front_matter + 9 secções substantivas (~8400 tokens)
    e 33 conceitos (~2300 tokens), validando convergência rápida em 1 nível e exclusão de front_matter.
    """
    sections = [ASTSection("sec_0", "Início do documento", 1, "front_matter", 1, 1)]
    paragraphs = [ASTParagraph("p_0", "sec_0", "Authors and journal metadata header.", 1, 1, 0)]
    sec_analyses = [
        SectionAnalysis(
            section_id="sec_0",
            title="Início do documento",
            section_type="front_matter",
            objective="Apresentar metadados editoriais da publicação.",
            in_depth_synthesis="Cabeçalho editorial e afiliações institucionais.",
            core_ideas=["Metadados de revista"],
            source_refs=[EvidenceRef(section_id="sec_0", paragraph_id="p_0", page_number=1, status="SOURCE_FACT")],
        )
    ]
    for i in range(1, 10):
        sid = f"sec_{i}"
        pid = f"p_{i}"
        sections.append(ASTSection(sid, f"Secção Científica {i}", 1, "body", i, i))
        paragraphs.append(ASTParagraph(pid, sid, f"Dados empíricos na secção {i}: R2 = 0.{40+i}, p < 0.01.", i, i, i))
        sec_analyses.append(
            SectionAnalysis(
                section_id=sid,
                title=f"Secção Científica {i}",
                section_type="methodology" if i == 5 else ("results" if i == 6 else "body"),
                objective=f"Analisar dimensão empírica e conceptual {i} em profundidade.",
                in_depth_synthesis=("Análise densa de mineração de sentimento, regressão empírica e utilidade percebida em avaliações online. " * 38),
                core_ideas=[f"Ideia nuclear {i}.a", f"Ideia nuclear {i}.b", f"Ideia nuclear {i}.c"],
                source_refs=[EvidenceRef(section_id=sid, paragraph_id=pid, page_number=i, status="SOURCE_FACT")],
            )
        )

    concepts = [
        ConceptItem(
            concept_id=f"concept_c{k:02d}",
            name=f"Conceito Analítico {k}",
            definition=("Definição académica detalhada sobre variáveis de sentimento, volume e valência em plataformas digitais. " * 2),
            evidence_refs=[EvidenceRef(section_id="sec_1", paragraph_id="p_1", page_number=1, status="SOURCE_FACT")],
        )
        for k in range(1, 34)
    ]

    ast = AcademicDocumentAST(
        document_id="doc_dense_18",
        extractor_version="2.0.0",
        source_sha256="sha_dense_18",
        filename="dense_empirical.pdf",
        metadata=DocumentMetadata(title="Dense Empirical Study", page_count=10, source_sha256="sha_dense_18"),
        pages=[PageInfo(page_number=i) for i in range(1, 11)],
        sections=sections,
        paragraphs=paragraphs,
        report=ExtractionReport(status="COMPLETED", total_pages=10),
    )
    dossier = AcademicReasoningDossier(
        dossier_id="dos_dense_18",
        document_id="doc_dense_18",
        source_sha256="sha_dense_18",
        ast_version="2.0.0",
        status="COMPLETED",
        document_analysis=DocumentCoreAnalysis(
            document_id="doc_dense_18",
            title="Dense Empirical Study",
            global_objective="Avaliar impacto preditivo de sentimentos em avaliações online.",
            research_problem="Sobrecarga informacional em avaliações de consumidores.",
            central_thesis="Sentimento contextualizado prediz desempenho das avaliações.",
        ),
        section_analyses=sec_analyses,
        conceptual_analysis=concepts,
        methodology_analysis=MethodologyAnalysis(is_applicable=True, research_type="Empírico", methodological_design="Econométrico"),
        results_and_evidence=[
            ResultItem(
                statement="Sentimento influencia utilidade (p < 0.01).",
                evidence_data="R2 = 0.46",
                evidence_refs=[EvidenceRef(section_id="sec_6", paragraph_id="p_6", page_number=6, status="SOURCE_FACT")],
            )
        ],
        cross_section_synthesis=CrossSectionSynthesis(global_synthesis="Síntese transversal completa das 9 secções substantivas."),
    )

    digest_calls = 0

    def mock_dense_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        nonlocal digest_calls
        op = meta.get("operation", "")
        if op == "editorial_dossier_cluster_digest":
            digest_calls += 1
            found = [f"sec_{i}" for i in range(0, 10) if f"[sec_{i}]" in usr_p]
            return json.dumps(
                {
                    "cluster_editorial_digest": f"Síntese compacta preservando {', '.join(found)} com foco metodológico e empírico.",
                    "preserved_section_ids": found,
                    "key_concepts_and_refs": [f"concept_c01 ({s})" for s in found[:4]],
                },
                ensure_ascii=False,
            ), {"status": "COMPLETED"}
        if op == "editorial_macro_planning":
            # Mapear apenas sec_1..sec_9 (omitindo sec_0 front_matter) -> deve ter 100% de cobertura substantiva!
            return json.dumps(
                {
                    "document_nature": StudyDocumentNature.EMPIRICAL_RESEARCH_ARTICLE.value,
                    "central_theme": "Predição de desempenho de avaliações online por análise de sentimento",
                    "central_theme_status": "SOURCE_FACT",
                    "target_audience": "Investigadores em sistemas de informação e ciência de dados",
                    "target_audience_basis": "MODEL_INFERENCE",
                    "recommended_structure_rationale": "Progressão do enquadramento teórico para metodologia e resultados.",
                    "editorial_strategy": "Progressão empírica estruturada",
                    "global_organization_summary": "2 capítulos cobrindo sec_1 a sec_9",
                    "learning_objectives": [
                        {"objective_id": "lo_1", "description": "Compreender o modelo de mineração de sentimento", "epistemic_status": "SOURCE_FACT", "source_section_ids": ["sec_1"], "paragraph_ids": ["p_1"]}
                    ],
                    "chapters": [
                        {
                            "chapter_id": "ed_chap_01",
                            "title": "Fundamentos e Modelo de Investigação",
                            "pedagogical_objective": "Estabelecer base conceptual e hipóteses",
                            "order": 1,
                            "original_section_ids": ["sec_1", "sec_2", "sec_3", "sec_4"],
                            "key_concept_ids": ["concept_c01"],
                            "sections": [
                                {
                                    "section_id": "ed_sec_01_01",
                                    "title": "Enquadramento e Hipóteses",
                                    "order": 1,
                                    "pedagogical_objective": "Explicar sec_1 a sec_4",
                                    "original_section_ids": ["sec_1", "sec_2", "sec_3", "sec_4"],
                                    "associated_concept_ids": ["concept_c01"],
                                    "introduced_concept_ids": ["concept_c01"],
                                }
                            ],
                        },
                        {
                            "chapter_id": "ed_chap_02",
                            "title": "Metodologia, Resultados e Implicações",
                            "pedagogical_objective": "Analisar desenho empírico e conclusões",
                            "order": 2,
                            "original_section_ids": ["sec_5", "sec_6", "sec_7", "sec_8", "sec_9"],
                            "learning_dependencies": ["ed_chap_01"],
                            "sections": [
                                {
                                    "section_id": "ed_sec_02_01",
                                    "title": "Validação Empírica e Discussão",
                                    "order": 1,
                                    "pedagogical_objective": "Explicar sec_5 a sec_9",
                                    "original_section_ids": ["sec_5", "sec_6", "sec_7", "sec_8", "sec_9"],
                                    "associated_concept_ids": ["concept_c01"],
                                }
                            ],
                        },
                    ],
                },
                ensure_ascii=False,
            ), {"status": "COMPLETED"}
        if op == "editorial_chapter_pedagogy":
            cid = meta.get("chapter_id")
            sid = "ed_sec_01_01" if cid == "ed_chap_01" else "ed_sec_02_01"
            pid = "p_1" if cid == "ed_chap_01" else "p_6"
            orig = "sec_1" if cid == "ed_chap_01" else "sec_6"
            return json.dumps(
                {
                    "sections": [
                        {
                            "section_id": sid,
                            "explanation_strategy": "Desenvolvimento analítico fundamentado",
                            "planned_pedagogical_elements": ["DEFINITION", "DETAILED_EXPLANATION"],
                            "contents_to_cover": [{"summary": f"Análise fundamentada de {orig}", "epistemic_status": "SOURCE_FACT", "source_section_id": orig, "paragraph_ids": [pid]}],
                            "pedagogical_treatments": [],
                        }
                    ]
                },
                ensure_ascii=False,
            ), {"status": "COMPLETED"}
        return json.dumps({"visual_plans": []}), {"status": "COMPLETED"}

    engine = EditorialIntelligenceEngine(storage_dir=tmp_path / "study", llm_caller=mock_dense_caller)
    plan = engine.plan_study_document(dossier, ast=ast)

    assert plan.metadata.status == "COMPLETED"
    assert len(plan.telemetry.hierarchical_aggregations) >= 1
    assert all(agg["depth"] == 1 for agg in plan.telemetry.hierarchical_aggregations)
    assert plan.qa_report.dossier_section_coverage_pct == 100.0
    assert plan.qa_report.blocking_errors_count == 0


# ============================================================================
# Patch Estrito de Identidade Pedagógica Um-Para-Um (Testes Obrigatórios A–F)
# ============================================================================

def _make_single_chapter_macro_payload(section_ids: List[str], dossier: AcademicReasoningDossier) -> Dict[str, Any]:
    """Constrói uma resposta macro válida de 1 capítulo com as secções esperadas (sec_01, sec_02, ...)."""
    all_orig = [sa.section_id for sa in dossier.section_analyses]
    c0 = dossier.conceptual_analysis[0].concept_id
    sections_spec: List[Dict[str, Any]] = []
    for idx, sid in enumerate(section_ids, start=1):
        # Distribuir todas as secções originais para manter 100% de cobertura substantiva
        if idx < len(section_ids):
            orig_slice = [all_orig[(idx - 1) % len(all_orig)]]
        else:
            covered = {all_orig[(k - 1) % len(all_orig)] for k in range(1, len(section_ids))}
            rem = [o for o in all_orig if o not in covered]
            orig_slice = rem if rem else [all_orig[-1]]
        sections_spec.append(
            {
                "section_id": sid,
                "title": f"Secção Editorial {sid}",
                "order": idx,
                "content_role": "CORE",
                "pedagogical_objective": f"Objetivo pedagógico específico de {sid}",
                "original_section_ids": orig_slice,
                "associated_concept_ids": [c0],
                "introduced_concept_ids": [c0] if idx == 1 else [],
            }
        )
    return {
        "document_nature": StudyDocumentNature.EMPIRICAL_RESEARCH_ARTICLE.value,
        "central_theme": "Validação estrita um-para-um de identidade pedagógica",
        "central_theme_status": "SOURCE_FACT",
        "target_audience": "Investigadores de engenharia de software",
        "target_audience_basis": "MODEL_INFERENCE",
        "recommended_structure_rationale": "Capítulo único coeso com secções distintas.",
        "editorial_strategy": "Progressão analítica verificada",
        "global_organization_summary": "1 capítulo estruturado",
        "learning_objectives": [
            {
                "objective_id": "lo_1",
                "description": "Garantir correspondência estrita por section_id",
                "epistemic_status": "SOURCE_FACT",
                "source_section_ids": ["sec_intro"],
                "paragraph_ids": ["p_1"],
            }
        ],
        "conceptual_relationships": [],
        "chapters": [
            {
                "chapter_id": "ed_chap_01",
                "title": "Capítulo Único de Teste de Identidade",
                "pedagogical_objective": "Testar associação estrita por section_id",
                "order": 1,
                "original_section_ids": all_orig,
                "key_concept_ids": [c0],
                "sections": sections_spec,
            }
        ],
    }


def _make_pedagogy_section_item(section_id: Optional[str], label: str, paragraph_id: str = "p_1") -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "explanation_strategy": f"Estratégia exclusiva para {label}",
        "planned_pedagogical_elements": [PedagogicalElementType.DEFINITION.value],
        "contents_to_cover": [
            {
                "summary": f"Conteúdo pedagógico exclusivo de {label}",
                "epistemic_status": "SOURCE_FACT",
                "source_section_id": "sec_intro",
                "paragraph_ids": [paragraph_id],
            }
        ],
        "pedagogical_treatments": [],
    }
    if section_id is not None:
        item["section_id"] = section_id
    return item


def test_19_patch_a_duplicate_section_ids_rejected_and_retried(tmp_path: Path):
    """
    Teste A — Identificadores duplicados:
      Esperado: sec_01, sec_02, sec_03.
      Recebido: sec_01, sec_01, sec_03.
      Verifica rejeição, retry, ausência de associação posicional e estado PARTIAL após esgotar retries.
    """
    ast, dossier = build_empirical_ast_and_dossier("doc_patch_a")
    grounding = _GroundingContext(dossier, ast)
    expected = ["sec_01", "sec_02", "sec_03"]
    dup_payload = [
        _make_pedagogy_section_item("sec_01", "SEC_01_COPIA_A", "p_1"),
        _make_pedagogy_section_item("sec_01", "SEC_01_COPIA_B", "p_2"),
        _make_pedagogy_section_item("sec_03", "SEC_03_VALIDA", "p_3"),
    ]

    # 1. Validação direta da função de identidade e ausência de fallback posicional em enrich_chapter_sections
    ok, err_msg, diag = PedagogicalExplanationPlanner.validate_pedagogical_sections_identity(dup_payload, expected)
    assert ok is False
    assert diag["duplicate_section_ids"] == ["sec_01"]
    assert diag["missing_section_ids"] == ["sec_02"]
    assert "sec_01" in err_msg and "sec_02" in err_msg

    direct_chap = EditorialChapter(
        chapter_id="ed_chap_01",
        title="Cap Direto",
        pedagogical_objective="Obj",
        sections=[
            EditorialSection(section_id="sec_01", chapter_id="ed_chap_01", title="S1", pedagogical_objective="O1", original_section_ids=["sec_intro"]),
            EditorialSection(section_id="sec_02", chapter_id="ed_chap_01", title="S2", pedagogical_objective="O2", original_section_ids=["sec_bg"]),
            EditorialSection(section_id="sec_03", chapter_id="ed_chap_01", title="S3", pedagogical_objective="O3", original_section_ids=["sec_method"]),
        ],
    )
    direct_failures: List[Dict[str, Any]] = []
    PedagogicalExplanationPlanner.enrich_chapter_sections(
        direct_chap, dup_payload, grounding, set(expected), failed_operations=direct_failures
    )
    assert len(direct_failures) == 1
    assert direct_failures[0]["duplicate_section_ids"] == ["sec_01"]
    assert direct_failures[0]["missing_section_ids"] == ["sec_02"]
    # Nenhuma associação posicional a sec_02 nem escolha arbitrária entre as cópias ambíguas de sec_01
    assert direct_chap.sections[0].explanation_strategy == ""
    assert direct_chap.sections[1].explanation_strategy == ""
    assert direct_chap.sections[1].contents_to_cover == []
    assert direct_chap.sections[2].explanation_strategy == "Estratégia exclusiva para SEC_03_VALIDA"

    # 2. Pipeline completo com esgotamento de retries -> rejeição, retries e estado PARTIAL explícito
    pedagogy_attempts: List[int] = []

    def always_dup_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation")
        if op == "editorial_macro_planning":
            return json.dumps(_make_single_chapter_macro_payload(expected, dossier), ensure_ascii=False), {"status": "COMPLETED"}
        if op == "editorial_chapter_pedagogy":
            pedagogy_attempts.append(int(meta.get("attempt", 1)))
            return json.dumps({"sections": dup_payload}, ensure_ascii=False), {"status": "COMPLETED"}
        return json.dumps({"visual_plans": []}), {"status": "COMPLETED"}

    engine = EditorialIntelligenceEngine(
        storage_dir=tmp_path / "study_a",
        llm_caller=always_dup_caller,
        max_retries_per_call=2,
        max_sections_per_pedagogy_batch=3,
    )
    plan = engine.plan_study_document(dossier, ast=ast)

    assert pedagogy_attempts == [1, 2, 3]  # 1 tentativa inicial + 2 retries
    assert plan.telemetry.retries_count == 2
    assert plan.telemetry.failures_count == 1
    assert plan.metadata.status == "PARTIAL"
    assert len(plan.failed_operations) == 1
    f_op = plan.failed_operations[0]
    assert f_op["reason"] == "SECTION_IDENTITY_VALIDATION_FAILED"
    assert f_op["duplicate_section_ids"] == ["sec_01"]
    assert f_op["missing_section_ids"] == ["sec_02"]
    # A resposta inválida nunca foi consumida como se fosse válida
    for s in plan.chapters[0].sections:
        assert s.explanation_strategy == ""
        assert s.contents_to_cover == []


def test_20_patch_b_unknown_section_id_rejected_and_logged(tmp_path: Path):
    """
    Teste B — Identificador desconhecido:
      Esperado: sec_01, sec_02.
      Recebido: sec_01, sec_99.
      Verifica rejeição, registo da secção inesperada e ausência de associação indevida.
    """
    ast, dossier = build_empirical_ast_and_dossier("doc_patch_b")
    grounding = _GroundingContext(dossier, ast)
    expected = ["sec_01", "sec_02"]
    unknown_payload = [
        _make_pedagogy_section_item("sec_01", "SEC_01_CORRETA", "p_1"),
        _make_pedagogy_section_item("sec_99", "SEC_99_INTRUSA", "p_2"),
    ]

    ok, err_msg, diag = PedagogicalExplanationPlanner.validate_pedagogical_sections_identity(unknown_payload, expected)
    assert ok is False
    assert diag["unexpected_section_ids"] == ["sec_99"]
    assert diag["missing_section_ids"] == ["sec_02"]
    assert "sec_99" in err_msg

    # Chamada direta a enrich_chapter_sections nunca associa sec_99 a sec_02
    direct_chap = EditorialChapter(
        chapter_id="ed_chap_01",
        title="Cap B",
        pedagogical_objective="Obj",
        sections=[
            EditorialSection(section_id="sec_01", chapter_id="ed_chap_01", title="S1", pedagogical_objective="O1", original_section_ids=["sec_intro"]),
            EditorialSection(section_id="sec_02", chapter_id="ed_chap_01", title="S2", pedagogical_objective="O2", original_section_ids=["sec_bg"]),
        ],
    )
    direct_failures: List[Dict[str, Any]] = []
    PedagogicalExplanationPlanner.enrich_chapter_sections(
        direct_chap, unknown_payload, grounding, set(expected), failed_operations=direct_failures
    )
    assert len(direct_failures) == 1
    assert direct_failures[0]["unexpected_section_ids"] == ["sec_99"]
    assert direct_chap.sections[1].explanation_strategy == ""
    assert all("SEC_99_INTRUSA" not in str(c) for c in direct_chap.sections[1].contents_to_cover)

    # Pipeline completo (com configuração default de lote = 2 secções)
    def unknown_id_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation")
        if op == "editorial_macro_planning":
            return json.dumps(_make_single_chapter_macro_payload(expected, dossier), ensure_ascii=False), {"status": "COMPLETED"}
        if op == "editorial_chapter_pedagogy":
            return json.dumps({"sections": unknown_payload}, ensure_ascii=False), {"status": "COMPLETED"}
        return json.dumps({"visual_plans": []}), {"status": "COMPLETED"}

    engine = EditorialIntelligenceEngine(
        storage_dir=tmp_path / "study_b",
        llm_caller=unknown_id_caller,
        max_retries_per_call=1,
    )
    plan = engine.plan_study_document(dossier, ast=ast)

    assert plan.metadata.status == "PARTIAL"
    assert plan.telemetry.retries_count == 1
    assert len(plan.failed_operations) == 1
    assert plan.failed_operations[0]["unexpected_section_ids"] == ["sec_99"]
    assert "sec_99" in plan.failed_operations[0]["error"]
    for s in plan.chapters[0].sections:
        assert s.explanation_strategy == ""
        assert s.contents_to_cover == []


def test_21_patch_c_missing_section_with_equal_length_rejected(tmp_path: Path):
    """
    Teste C — Secção em falta com número igual de elementos:
      Esperado: sec_01, sec_02, sec_03.
      Recebido: sec_01, sec_03, sec_03.
      Verifica rejeição, deteção simultânea da omissão de sec_02 e da duplicação de sec_03.
    """
    ast, dossier = build_empirical_ast_and_dossier("doc_patch_c")
    expected = ["sec_01", "sec_02", "sec_03"]
    equal_len_bad_payload = [
        _make_pedagogy_section_item("sec_01", "SEC_01", "p_1"),
        _make_pedagogy_section_item("sec_03", "SEC_03_A", "p_3"),
        _make_pedagogy_section_item("sec_03", "SEC_03_B", "p_4"),
    ]
    assert len(equal_len_bad_payload) == len(expected) == 3

    ok, err_msg, diag = PedagogicalExplanationPlanner.validate_pedagogical_sections_identity(
        equal_len_bad_payload, expected
    )
    assert ok is False
    assert diag["missing_section_ids"] == ["sec_02"]
    assert diag["duplicate_section_ids"] == ["sec_03"]
    assert "sec_02" in err_msg
    assert "sec_03" in err_msg

    prompts_received: List[str] = []

    def equal_len_bad_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation")
        if op == "editorial_macro_planning":
            return json.dumps(_make_single_chapter_macro_payload(expected, dossier), ensure_ascii=False), {"status": "COMPLETED"}
        if op == "editorial_chapter_pedagogy":
            prompts_received.append(usr_p)
            return json.dumps({"sections": equal_len_bad_payload}, ensure_ascii=False), {"status": "COMPLETED"}
        return json.dumps({"visual_plans": []}), {"status": "COMPLETED"}

    engine = EditorialIntelligenceEngine(
        storage_dir=tmp_path / "study_c",
        llm_caller=equal_len_bad_caller,
        max_retries_per_call=1,
        max_sections_per_pedagogy_batch=3,
    )
    plan = engine.plan_study_document(dossier, ast=ast)

    assert len(prompts_received) == 2
    # A pista de retry inclui explicitamente tanto a omissão de sec_02 como a duplicação de sec_03
    assert "sec_02" in prompts_received[1] and "sec_03" in prompts_received[1]
    assert plan.metadata.status == "PARTIAL"
    assert len(plan.failed_operations) == 1
    f_op = plan.failed_operations[0]
    assert f_op["missing_section_ids"] == ["sec_02"]
    assert f_op["duplicate_section_ids"] == ["sec_03"]
    for s in plan.chapters[0].sections:
        assert s.explanation_strategy == ""


def test_22_patch_d_out_of_order_valid_section_ids_accepted_one_to_one(tmp_path: Path):
    """
    Teste D — Ordem diferente, mas identificadores corretos:
      Esperado: sec_01, sec_02, sec_03.
      Recebido: sec_03, sec_01, sec_02.
      Verifica aceitação imediata, associação exata por section_id e preservação da identidade/ordem das secções.
    """
    ast, dossier = build_empirical_ast_and_dossier("doc_patch_d")
    expected = ["sec_01", "sec_02", "sec_03"]
    reordered_payload = [
        _make_pedagogy_section_item("sec_03", "CONTEUDO_DA_TRES", "p_5"),
        _make_pedagogy_section_item("sec_01", "CONTEUDO_DA_UM", "p_1"),
        _make_pedagogy_section_item("sec_02", "CONTEUDO_DA_DOIS", "p_3"),
    ]

    ok, err_msg, diag = PedagogicalExplanationPlanner.validate_pedagogical_sections_identity(
        reordered_payload, expected
    )
    assert ok is True
    assert err_msg == ""
    assert diag["missing_section_ids"] == []
    assert diag["duplicate_section_ids"] == []
    assert diag["unexpected_section_ids"] == []

    def reordered_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation")
        if op == "editorial_macro_planning":
            return json.dumps(_make_single_chapter_macro_payload(expected, dossier), ensure_ascii=False), {"status": "COMPLETED"}
        if op == "editorial_chapter_pedagogy":
            return json.dumps({"sections": reordered_payload}, ensure_ascii=False), {"status": "COMPLETED"}
        return json.dumps({"visual_plans": []}), {"status": "COMPLETED"}

    engine = EditorialIntelligenceEngine(
        storage_dir=tmp_path / "study_d",
        llm_caller=reordered_caller,
        max_retries_per_call=2,
        max_sections_per_pedagogy_batch=3,
    )
    plan = engine.plan_study_document(dossier, ast=ast)

    assert plan.metadata.status == "COMPLETED"
    assert plan.telemetry.retries_count == 0
    assert plan.telemetry.failures_count == 0
    assert plan.failed_operations == []
    assert plan.qa_report.is_valid is True

    secs = plan.chapters[0].sections
    # Identidade e ordem original das secções do capítulo permanecem inalteradas
    assert [s.section_id for s in secs] == ["sec_01", "sec_02", "sec_03"]
    assert [s.order for s in secs] == [1, 2, 3]
    # Conteúdos associados estritamente por section_id (nunca pela posição 0, 1, 2 da resposta)
    assert secs[0].explanation_strategy == "Estratégia exclusiva para CONTEUDO_DA_UM"
    assert secs[0].contents_to_cover[0]["summary"] == "Conteúdo pedagógico exclusivo de CONTEUDO_DA_UM"
    assert secs[1].explanation_strategy == "Estratégia exclusiva para CONTEUDO_DA_DOIS"
    assert secs[1].contents_to_cover[0]["summary"] == "Conteúdo pedagógico exclusivo de CONTEUDO_DA_DOIS"
    assert secs[2].explanation_strategy == "Estratégia exclusiva para CONTEUDO_DA_TRES"
    assert secs[2].contents_to_cover[0]["summary"] == "Conteúdo pedagógico exclusivo de CONTEUDO_DA_TRES"


def test_23_patch_e_missing_section_id_rejected_without_positional_fallback(tmp_path: Path):
    """
    Teste E — Ausência de section_id:
      Recebido um elemento sem section_id (e variante com section_id vazio).
      Verifica rejeição e proibição absoluta de usar a posição na lista para compensar o ID em falta.
    """
    ast, dossier = build_empirical_ast_and_dossier("doc_patch_e")
    grounding = _GroundingContext(dossier, ast)
    expected = ["sec_01", "sec_02"]
    no_id_payload = [
        _make_pedagogy_section_item(None, "ITEM_ANONIMO_POSICAO_ZERO", "p_1"),
        _make_pedagogy_section_item("sec_02", "SEC_02_IDENTIFICADA", "p_3"),
    ]
    empty_id_payload = [
        _make_pedagogy_section_item("   ", "ITEM_VAZIO_POSICAO_ZERO", "p_1"),
        _make_pedagogy_section_item("sec_02", "SEC_02_IDENTIFICADA", "p_3"),
    ]

    for bad_payload in (no_id_payload, empty_id_payload):
        ok, err_msg, diag = PedagogicalExplanationPlanner.validate_pedagogical_sections_identity(bad_payload, expected)
        assert ok is False
        assert diag["missing_id_indices"] == [0]
        assert diag["missing_section_ids"] == ["sec_01"]
        assert "section_id" in err_msg

    # Verificar diretamente em enrich_chapter_sections que sec_01 (índice 0) NÃO recebe o item sem ID na posição 0
    direct_chap = EditorialChapter(
        chapter_id="ed_chap_01",
        title="Cap E",
        pedagogical_objective="Obj",
        sections=[
            EditorialSection(section_id="sec_01", chapter_id="ed_chap_01", title="S1", pedagogical_objective="O1", original_section_ids=["sec_intro"]),
            EditorialSection(section_id="sec_02", chapter_id="ed_chap_01", title="S2", pedagogical_objective="O2", original_section_ids=["sec_bg"]),
        ],
    )
    direct_failures: List[Dict[str, Any]] = []
    PedagogicalExplanationPlanner.enrich_chapter_sections(
        direct_chap, no_id_payload, grounding, set(expected), failed_operations=direct_failures
    )
    assert len(direct_failures) == 1
    assert direct_failures[0]["missing_id_indices"] == [0]
    assert direct_chap.sections[0].explanation_strategy == ""
    assert direct_chap.sections[0].contents_to_cover == []
    assert direct_chap.sections[1].explanation_strategy == "Estratégia exclusiva para SEC_02_IDENTIFICADA"

    # Pipeline completo -> rejeição, retry, zero compensação posicional e estado PARTIAL
    def missing_id_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation")
        if op == "editorial_macro_planning":
            return json.dumps(_make_single_chapter_macro_payload(expected, dossier), ensure_ascii=False), {"status": "COMPLETED"}
        if op == "editorial_chapter_pedagogy":
            return json.dumps({"sections": no_id_payload}, ensure_ascii=False), {"status": "COMPLETED"}
        return json.dumps({"visual_plans": []}), {"status": "COMPLETED"}

    engine = EditorialIntelligenceEngine(
        storage_dir=tmp_path / "study_e",
        llm_caller=missing_id_caller,
        max_retries_per_call=1,
    )
    plan = engine.plan_study_document(dossier, ast=ast)

    assert plan.metadata.status == "PARTIAL"
    assert plan.telemetry.retries_count == 1
    assert len(plan.failed_operations) == 1
    assert plan.failed_operations[0]["missing_id_indices"] == [0]
    assert plan.chapters[0].sections[0].explanation_strategy == ""
    assert plan.chapters[0].sections[0].contents_to_cover == []


def test_24_patch_f_pipeline_regression_checkpoint_qa_and_traceability(tmp_path: Path):
    """
    Teste F — Regressão da pipeline:
      Confirma geração editorial completa, recuperação e higienização de checkpoints,
      QA editorial e rastreabilidade integral de referências após o patch corretivo.
    """
    storage_dir = tmp_path / "study_f"
    ast, dossier = build_empirical_ast_and_dossier("doc_patch_f", "sha_patch_f")
    base_caller = make_mock_editorial_llm_caller(ast, dossier)

    # 1. Simular primeira tentativa onde ed_chap_02 falha na 1ª tentativa por duplicação de ID
    #    mas recupera no retry, enquanto ed_chap_03 é interrompido para testar checkpoint recovery!
    chap2_attempts = 0

    def transient_and_interrupted_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        nonlocal chap2_attempts
        op = meta.get("operation")
        chap = meta.get("chapter_id")
        if op == "editorial_chapter_pedagogy" and chap == "ed_chap_01" and int(meta.get("attempt", 1)) == 1:
            chap2_attempts += 1
            # Devolver secções em ordem invertida no ed_chap_01 (ed_sec_01_02, ed_sec_01_01) -> aceite à 1ª!
            raw_ok, tel = base_caller(sys_p, usr_p, meta)
            obj = json.loads(raw_ok)
            obj["sections"] = list(reversed(obj["sections"]))
            return json.dumps(obj, ensure_ascii=False), tel
        if op == "editorial_chapter_pedagogy" and chap == "ed_chap_03":
            raise RuntimeError("Interrupção controlada antes do capítulo 3")
        return base_caller(sys_p, usr_p, meta)

    engine_1 = EditorialIntelligenceEngine(storage_dir=storage_dir, llm_caller=transient_and_interrupted_caller)
    with pytest.raises(RuntimeError):
        engine_1.plan_study_document(dossier, ast=ast)

    cp_path = storage_dir / "documents" / dossier.document_id / "editorial_checkpoint.json"
    assert cp_path.exists()

    # 2. Corromper deliberadamente ed_chap_02 no checkpoint (removendo section_id) para provar
    #    que o motor não consome um checkpoint sem identidade inequívoca e o reprocessa!
    cp_data = json.loads(cp_path.read_text(encoding="utf-8"))
    cp_data["completed_chapters"]["ed_chap_02"] = [{"explanation_strategy": "Checkpoint corrompido sem section_id"}]
    cp_path.write_text(json.dumps(cp_data, ensure_ascii=False), encoding="utf-8")

    resumed_ops: List[str] = []

    def clean_resumed_caller(sys_p: str, usr_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        resumed_ops.append(f"{meta.get('operation')}:{meta.get('chapter_id', '')}")
        return base_caller(sys_p, usr_p, meta)

    engine_2 = EditorialIntelligenceEngine(storage_dir=storage_dir, llm_caller=clean_resumed_caller)
    plan = engine_2.plan_study_document(dossier, ast=ast)

    assert plan.metadata.status == "COMPLETED"
    assert plan.failed_operations == []
    # ed_chap_01 válido no checkpoint (mesmo em ordem invertida) NÃO foi repetido;
    # ed_chap_02 corrompido sem section_id FOI descartado e reprocessado; ed_chap_03 foi concluído!
    assert "editorial_chapter_pedagogy:ed_chap_01" not in resumed_ops
    assert "editorial_chapter_pedagogy:ed_chap_02" in resumed_ops
    assert "editorial_chapter_pedagogy:ed_chap_03" in resumed_ops

    # QA editorial e rastreabilidade 100% íntegros
    assert plan.qa_report.is_valid is True
    assert plan.qa_report.validation_status == "VALID"
    assert plan.qa_report.blocking_errors_count == 0
    assert plan.qa_report.dossier_section_coverage_pct == 100.0
    assert plan.qa_report.valid_evidence_refs_pct == 100.0
    assert not cp_path.exists()



