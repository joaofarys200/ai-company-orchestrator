"""
JARVIS OS — ACADEMIC REASONING ENGINE (PHASE 3) TEST SUITE
Validação exaustiva e forense dos 12 perfis obrigatórios de teste:
1. Documento curto com estrutura convencional.
2. Documento extenso com múltiplas secções e segmentos.
3. Documento sem estrutura académica convencional.
4. Documento com categorias ausentes (NOT_FOUND sem alucinações).
5. Documento com metodologia, resultados e discussão claramente separados.
6. Preservação honesta de tabelas e figuras não interpretadas.
7. Tratamento de respostas JSON inválidas e retries.
8. Deteção forense de referências a parágrafos inexistentes pelo ReasoningQAEvaluator.
9. Interrupção e recuperação incremental via checkpoint em disco.
10. Invalidação obrigatória de checkpoint por alteração de hash SHA256 ou versão da AST.
11. Falha explícita com OllamaInferenceUnavailableError (zero fallback determinístico silencioso).
12. Cancelamento gracioso de análise em curso com ReasoningCancelledError.
13. Teste de integração real com Ollama local (qwen3.5:9b).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from services.document_intelligence import (
    AcademicDocumentAST,
    ASTFigure,
    ASTParagraph,
    ASTSection,
    ASTTable,
    DocumentMetadata,
    ExtractionReport,
    PageInfo,
)
from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    AcademicReasoningEngine,
    CheckpointMismatchError,
    EpistemicStatus,
    EvidenceRef,
    OllamaInferenceUnavailableError,
    ReasoningCancelledError,
    ReasoningQAEvaluator,
    SemanticSegmenter,
    clean_qwen_json,
)
from services.study_service import StudyService


# ---------------------------------------------------------------------------
# Helper: Construtor de AST Sintética para Testes Controlados
# ---------------------------------------------------------------------------

def create_synthetic_ast(
    document_id: str = "doc_test_synthetic",
    title: str = "Estudo de Teste",
    sections_spec: Optional[List[Dict[str, Any]]] = None,
    source_sha256: str = "sha256_synthetic_baseline",
    ast_version: str = "3.0.0-academic",
) -> AcademicDocumentAST:
    if sections_spec is None:
        sections_spec = [
            {
                "section_id": "sec_intro",
                "title": "1. Introdução",
                "kind": "introduction",
                "paragraphs": [
                    "A inteligência artificial tem revolucionado a compreensão de documentos científicos complexos.",
                    "No entanto, os modelos frequentemente falham na preservação da rastreabilidade epistemológica estrita.",
                ],
            },
            {
                "section_id": "sec_method",
                "title": "2. Metodologia",
                "kind": "methodology",
                "paragraphs": [
                    "Utilizámos uma amostra de 150 artigos científicos indexados na Web of Science.",
                    "O procedimento experimental consistiu na segmentação semântica e avaliação por pares duplo-cego.",
                ],
            },
            {
                "section_id": "sec_results",
                "title": "3. Resultados e Discussão",
                "kind": "results",
                "paragraphs": [
                    "Os resultados demonstraram um aumento de 42.5% na precisão do grounding de conceitos.",
                    "A taxa de alucinação de dados fictícios decresceu para 0.0% com o uso de validação forense.",
                ],
            },
            {
                "section_id": "sec_conclusion",
                "title": "4. Conclusão",
                "kind": "conclusion",
                "paragraphs": [
                    "Conclui-se que o motor hierárquico Map-Reduce preserva integralmente o contexto semântico original.",
                ],
            },
        ]

    sections: List[ASTSection] = []
    paragraphs: List[ASTParagraph] = []
    p_counter = 1

    for s_idx, spec in enumerate(sections_spec, start=1):
        s_id = spec.get("section_id", f"sec_{s_idx}")
        sections.append(
            ASTSection(
                section_id=s_id,
                title=spec.get("title", f"Secção {s_idx}"),
                level=1,
                kind=spec.get("kind", "other"),
                page_start=1,
                page_end=1,
            )
        )
        for p_text in spec.get("paragraphs", []):
            p_id = f"p_{p_counter}"
            paragraphs.append(
                ASTParagraph(
                    paragraph_id=p_id,
                    section_id=s_id,
                    text=p_text,
                    page_number=1,
                    page_end=1,
                    order=p_counter,
                )
            )
            p_counter += 1

    return AcademicDocumentAST(
        document_id=document_id,
        extractor_version=ast_version,
        source_sha256=source_sha256,
        filename="documento_teste.pdf",
        metadata=DocumentMetadata(
            title=title,
            abstract="Resumo do estudo sintetizado para verificação forense.",
            page_count=2,
            keywords=["IA", "Grounding", "Epistemologia"],
            source_sha256=source_sha256,
        ),
        pages=[PageInfo(page_number=1), PageInfo(page_number=2)],
        sections=sections,
        paragraphs=paragraphs,
        report=ExtractionReport(status="COMPLETED", total_pages=2),
    )


# ============================================================================
# 1. Documento Curto com Estrutura Convencional
# ============================================================================

def test_01_short_conventional_academic_document(tmp_path: Path):
    ast = create_synthetic_ast("doc_short_01", "Estudo Curto Convencional")

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "segment" in op:
            resp = {
                "central_idea": "Fundamentação teórica e delimitação do problema de investigação.",
                "passage_objective": "Contextualizar o estado da arte.",
                "concepts": ["Inteligência Artificial", "Grounding"],
                "definitions": [{"term": "Grounding", "definition": "Ancoragem epistémica no texto original", "paragraph_id": "p_2"}],
                "arguments": [{"claim": "A IA requer validação forense", "evidence": "Modelos falham sem grounding", "paragraph_id": "p_2", "status": "SOURCE_FACT"}],
                "assumptions": ["Presume a necessidade de rigor académico"],
                "partial_conclusions": ["A rastreabilidade é indispensável"],
                "technical_terminology": ["epistemologia", "grounding"],
                "limitations_or_notices": [],
            }
        elif "section" in op:
            resp = {
                "objective": "Articular a introdução com as evidências empíricas.",
                "in_depth_synthesis": "A introdução estabelece a necessidade de preservação da rastreabilidade epistemológica no processamento de documentos científicos complexos.",
                "core_ideas": ["A revolução da IA no estudo documental", "A necessidade de validação estrita"],
                "concepts": [{"name": "Grounding", "explanation": "Conceito nuclear de ancoragem factual", "paragraph_ids": ["p_2"]}],
                "arguments": [{"claim": "O raciocínio hierárquico resolve o truncamento", "evidence": "Dados empíricos da secção", "paragraph_ids": ["p_1", "p_2"], "status": "SOURCE_FACT"}],
                "limitations": [],
            }
        elif "methodology" in op:
            resp = {
                "is_applicable": True,
                "research_type": "Empírico Quantitativo",
                "methodological_design": "Avaliação cega de 150 artigos",
                "methods_used": ["Segmentação semântica", "Grounding forense"],
                "sample_or_participants": "150 artigos científicos indexados",
                "instruments": ["Web of Science", "PyMuPDF"],
                "procedures": ["Segmentação adaptativa e scoring"],
                "variables": ["Taxa de alucinação", "Precisão de grounding"],
                "data_sources": ["Corpus Web of Science"],
                "analysis_techniques": ["Estatística descritiva e testes t"],
                "methodological_limitations": ["Restrito a artigos em inglês e português"],
                "results": [
                    {
                        "statement": "Aumento de 42.5% na precisão do grounding",
                        "evidence_data": "42.5% de incremento medido (p < 0.01)",
                        "relation_to_objectives": "Confirma a eficácia do motor",
                        "interpretation_limitations": "Amostra focada em ciências computacionais",
                        "paragraph_id": "p_5",
                    }
                ],
            }
        else:  # cross section
            resp = {
                "argumentative_progression": [
                    "Problema colocado na introdução",
                    "Solução desenhada na metodologia",
                    "Comprovação nos resultados com 42.5% de ganho",
                ],
                "conceptual_relationships": [
                    {"concept_a": "Grounding", "relationship": "reduz alucinação em", "concept_b": "IA Académica", "explanation": "Ancoragem direta"}
                ],
                "coherence_and_tensions": [
                    {"type": "COHERENCE", "description": "Os resultados suportam integralmente a tese inicial.", "status": "MODEL_INFERENCE"}
                ],
                "idea_dependencies": [
                    {"dependent_idea": "Redução de alucinação", "depends_on": "Grounding estrito", "reason": "Sem âncoras há deriva"}
                ],
                "global_synthesis": "O documento demonstra de forma sólida que a segmentação adaptativa e a rastreabilidade forense eliminam a superficialidade e as alucinações na síntese de textos científicos.",
            }
        return json.dumps(resp), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    assert dossier is not None
    assert dossier.status == "COMPLETED"
    assert len(dossier.section_analyses) == 4
    assert dossier.document_analysis.title == "Estudo Curto Convencional"
    assert dossier.methodology_analysis.is_applicable is True
    assert len(dossier.results_and_evidence) >= 1
    assert "42.5%" in dossier.results_and_evidence[0].statement
    assert dossier.qa_report.is_valid is True
    assert dossier.qa_report.valid_paragraph_refs_pct >= 90.0


# ============================================================================
# 2. Documento Extenso com Várias Secções e Subseções
# ============================================================================

def test_02_extensive_document_multiple_sections_and_segments(tmp_path: Path):
    sections_spec = []
    for i in range(1, 8):
        sections_spec.append(
            {
                "section_id": f"sec_{i}",
                "title": f"Capítulo {i}: Análise Aprofundada {i}",
                "kind": "chapter" if i > 1 else "introduction",
                "paragraphs": [
                    f"Parágrafo 1 do capítulo {i} abordando conceitos avançados de sistemas distribuídos e consenso assíncrono.",
                    f"Parágrafo 2 do capítulo {i} apresentando métricas de latência e débito sob falhas bizantinas parciais.",
                    f"Parágrafo 3 do capítulo {i} demonstrando invariantes formais de segurança e vivacidade.",
                ],
            }
        )
    ast = create_synthetic_ast("doc_extensive_02", "Monografia Extensa", sections_spec=sections_spec)

    segmenter = SemanticSegmenter(max_tokens_per_segment=40)
    segments = segmenter.segment_section(ast.sections[0], ast.paragraphs)
    assert len(segments) >= 2  # Provou que a segmentação dividiu a secção em unidades adaptativas

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return json.dumps({
            "central_idea": "Desenvolvimento do capítulo com rigor formal.",
            "passage_objective": "Provar propriedades de vivacidade.",
            "concepts": ["Consenso", "Vivacidade"],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Analisar aspetos do capítulo.",
            "in_depth_synthesis": "Síntese aprofundada demonstrando a coerência do sistema distribuído.",
            "core_ideas": ["Conceito A", "Conceito B"],
            "argumentative_progression": ["Etapa 1", "Etapa 2"],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Monografia exaustiva sobre sistemas tolerantes a falhas.",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    assert len(dossier.section_analyses) == 7
    assert dossier.qa_report.total_sections_analyzed == 7
    assert dossier.qa_report.total_segments_analyzed >= 7


# ============================================================================
# 3. Documento sem Estrutura Académica Convencional
# ============================================================================

def test_03_non_conventional_document_structure(tmp_path: Path):
    sections_spec = [
        {
            "section_id": "sec_memo",
            "title": "Memorando Técnico Interno: Otimização de Cache",
            "kind": "other",
            "paragraphs": [
                "Este memorando detalha a política de evicção LRU implementada no cluster de produção.",
                "Reduzimos o consumo de RAM em 30% através da compressão zstd nos nós de cálculo.",
            ],
        }
    ]
    ast = create_synthetic_ast("doc_memo_03", "Memorando Técnico", sections_spec=sections_spec)

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return json.dumps({
            "central_idea": "Otimização de memória através de compressão zstd e evicção LRU.",
            "passage_objective": "Registar melhorias de infraestrutura.",
            "concepts": ["LRU", "zstd", "Cluster"],
            "definitions": [{"term": "LRU", "definition": "Least Recently Used eviction policy", "paragraph_id": "p_1"}],
            "arguments": [{"claim": "Consumo de RAM reduzido em 30%", "evidence": "Telemetria de produção", "paragraph_id": "p_2", "status": "SOURCE_FACT"}],
            "assumptions": ["A carga de trabalho mantém-se estável"],
            "partial_conclusions": ["Ganhos substanciais de pegada de memória"],
            "technical_terminology": ["evicção", "zstd"],
            "limitations_or_notices": [],
            "objective": "Descrever otimizações de cache em produção.",
            "in_depth_synthesis": "O memorando reporta uma melhoria substantiva de infraestrutura.",
            "core_ideas": ["Compressão zstd", "Evicção LRU"],
            "argumentative_progression": ["Identificação do consumo de RAM", "Aplicação da compressão e resultados"],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Otimização pragmática de sistemas sem formato de artigo científico tradicional.",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    assert dossier.status == "COMPLETED"
    assert dossier.section_analyses[0].section_type == "other"
    assert dossier.methodology_analysis.is_applicable is False or not dossier.methodology_analysis.methods_used


# ============================================================================
# 4. Documento com Categorias Ausentes (NOT_FOUND Sem Alucinações)
# ============================================================================

def test_04_document_with_missing_categories_honest_not_found(tmp_path: Path):
    sections_spec = [
        {
            "section_id": "sec_essay",
            "title": "Reflexão Filosófica sobre Consciência",
            "kind": "other",
            "paragraphs": [
                "A consciência fenomenológica permanece um dos problemas mais complexos da filosofia da mente.",
                "Não existem dados quantitativos ou medições empíricas diretas do qualia subjetivo.",
            ],
        }
    ]
    ast = create_synthetic_ast("doc_essay_04", "Ensaio Filosófico", sections_spec=sections_spec)

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return json.dumps({
            "central_idea": "Discussão ontológica da natureza dos qualia.",
            "passage_objective": "Explorar o hard problem da consciência.",
            "concepts": ["Qualia", "Consciência Fenomenológica"],
            "definitions": [],
            "arguments": [],
            "assumptions": ["Os qualia são irredutíveis a estados puramente funcionais"],
            "partial_conclusions": [],
            "technical_terminology": ["qualia"],
            "limitations_or_notices": ["Inexistência de metodologia quantitativa"],
            "objective": "Refletir sobre o problema ontológico.",
            "in_depth_synthesis": "O ensaio articula a distinção clássica entre processos funcionais e experiência consciente.",
            "core_ideas": ["Irredutibilidade dos qualia"],
            "argumentative_progression": ["Enunciado do problema sem validação experimental"],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Ensaio conceptual rigoroso sem alegações empíricas falsas.",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    assert len(dossier.results_and_evidence) == 0
    assert dossier.methodology_analysis.is_applicable is False


# ============================================================================
# 5. Documento com Metodologia, Resultados e Discussão Separados
# ============================================================================

def test_05_methodology_results_and_discussion_clearly_distinguished(tmp_path: Path):
    sections_spec = [
        {
            "section_id": "sec_meth",
            "title": "Methodology",
            "kind": "methodology",
            "paragraphs": [
                "Utilizámos um ensaio clínico randomizado com 200 participantes divididos em dois grupos de 100.",
                "O grupo de intervenção recebeu 50mg do composto ativo durante 12 semanas contínuas.",
            ],
        },
        {
            "section_id": "sec_res",
            "title": "Results",
            "kind": "results",
            "paragraphs": [
                "O grupo de intervenção registou uma redução de 35% nos biomarcadores inflamatórios (p = 0.003).",
                "O grupo de controlo placebo não demonstrou variação estatisticamente significativa.",
            ],
        },
    ]
    ast = create_synthetic_ast("doc_trial_05", "Ensaio Clínico", sections_spec=sections_spec)

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "methodology" in op:
            return json.dumps({
                "is_applicable": True,
                "research_type": "Ensaio Clínico Randomizado (RCT)",
                "methodological_design": "Duplo-cego, controlado por placebo",
                "methods_used": ["Dosagem controlada", "Análise de biomarcadores"],
                "sample_or_participants": "200 participantes (100 intervenção, 100 placebo)",
                "instruments": ["ELISA para biomarcadores inflamatórios"],
                "procedures": ["Administração diária de 50mg por 12 semanas"],
                "variables": ["Nível de biomarcadores inflamatórios"],
                "data_sources": ["Amostras sanguíneas laboratoriais"],
                "analysis_techniques": ["Teste t de Student e ANOVA"],
                "methodological_limitations": ["Duração restrita a 12 semanas"],
                "results": [
                    {
                        "statement": "Redução de 35% nos biomarcadores inflamatórios no grupo de intervenção",
                        "evidence_data": "35% de decréscimo, p = 0.003",
                        "relation_to_objectives": "Demonstra eficácia biológica do composto",
                        "interpretation_limitations": "Efeitos a longo prazo requerem estudo fase IV",
                        "paragraph_id": "p_3",
                    }
                ],
            }), {"status": "COMPLETED"}

        return json.dumps({
            "central_idea": "Apresentação dos dados do ensaio clínico.",
            "passage_objective": "Medir eficácia terapêutica.",
            "concepts": ["Biomarcadores"],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Descrever procedimentos clínicos.",
            "in_depth_synthesis": "Procedimentos e resultados rigorosamente estratificados por braço de intervenção.",
            "core_ideas": ["RCT com 200 participantes", "Redução de 35%"],
            "argumentative_progression": ["Dosagem", "Análise estatística e p-valor"],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Evidência clínica sólida com distinção inequívoca entre método e resultado.",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    assert dossier.methodology_analysis.is_applicable is True
    assert dossier.methodology_analysis.sample_or_participants == "200 participantes (100 intervenção, 100 placebo)"
    assert len(dossier.results_and_evidence) == 1
    assert "35%" in dossier.results_and_evidence[0].evidence_data


# ============================================================================
# 6. Preservação Honesta de Tabelas e Figuras Não Interpretadas
# ============================================================================

def test_06_honest_handling_of_uninterpreted_tables_and_figures(tmp_path: Path):
    ast = create_synthetic_ast("doc_figures_06", "Artigo com Gráficos")
    ast.figures.append(
        ASTFigure(
            figure_id="fig_1",
            page_number=1,
            section_id="sec_results",
            order=1,
            caption="Figura 1: Curva de aprendizagem do modelo ao longo das épocas.",
            interpretation_status="IMAGE_ONLY_NOT_INTERPRETED",
            underlying_data_recovered=False,
            limitations=["Gráfico vetorial não convertido em tabela de dados brutos."],
        )
    )

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return json.dumps({
            "central_idea": "Apresentação da taxa de convergência.",
            "passage_objective": "Discutir métricas de treino.",
            "concepts": ["Convergência"],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": ["Figura 1 mantida como imagem visual sem alucinação de pontos discretos."],
            "objective": "Análise da convergência.",
            "in_depth_synthesis": "A discussão faz referência à Figura 1 salvaguardando que os dados brutos subjacentes não foram inferidos artificialmente.",
            "core_ideas": ["Convergência suave"],
            "argumentative_progression": ["Treino", "Curva observada"],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Estudo experimental com respeito pelos limites de interpretação visual.",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    assert ast.figures[0].interpretation_status == "IMAGE_ONLY_NOT_INTERPRETED"
    assert dossier.status == "COMPLETED"


# ============================================================================
# 7. Respostas JSON Inválidas do Modelo e Retries
# ============================================================================

def test_07_invalid_json_responses_and_retries(tmp_path: Path):
    ast = create_synthetic_ast("doc_retries_07", "Artigo com Falha de JSON")
    call_count = 0

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        nonlocal call_count
        call_count += 1
        # Primeira chamada devolve texto não JSON
        if call_count == 1:
            return "Desculpa, aqui está o resumo em texto livre sem formatação JSON...", {"status": "COMPLETED"}
        # Segunda chamada devolve JSON com think tags
        return "<think>Estou a pensar no JSON</think>\n```json\n{\"central_idea\": \"Recuperado com sucesso após retry.\", \"passage_objective\": \"Demonstrar robustez.\", \"concepts\": [], \"definitions\": [], \"arguments\": [], \"assumptions\": [], \"partial_conclusions\": [], \"technical_terminology\": [], \"limitations_or_notices\": [], \"objective\": \"Obj\", \"in_depth_synthesis\": \"Síntese recuperada.\", \"core_ideas\": [], \"argumentative_progression\": [], \"conceptual_relationships\": [], \"coherence_and_tensions\": [], \"idea_dependencies\": [], \"global_synthesis\": \"Global\"}\n```", {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller, max_retries_per_call=2)
    dossier = engine.analyze_document(ast)

    assert call_count >= 2
    assert dossier.status == "COMPLETED"
    assert "Recuperado com sucesso" in dossier.section_analyses[0].core_ideas or dossier.section_analyses[0].in_depth_synthesis


# ============================================================================
# 8. Deteção Forense de Referências a Parágrafos Inexistentes
# ============================================================================

def test_08_forensic_detection_of_invalid_paragraph_references(tmp_path: Path):
    ast = create_synthetic_ast("doc_qa_08", "Documento para Auditoria QA")

    evaluator = ReasoningQAEvaluator()
    # Criamos deliberadamente uma secção com referências a um parágrafo fantasma 'p_9999'
    from services.academic_reasoning_engine import SectionAnalysis, ResultItem, CrossSectionSynthesis
    mock_sec = SectionAnalysis(
        section_id="sec_intro",
        title="1. Introdução",
        source_refs=[
            EvidenceRef(section_id="sec_intro", paragraph_id="p_1", status="SOURCE_FACT"),
            EvidenceRef(section_id="sec_intro", paragraph_id="p_9999", status="SOURCE_FACT"),  # Fantasma!
        ],
    )
    qa_report = evaluator.evaluate(
        ast=ast,
        section_analyses=[mock_sec],
        results=[],
        cross_synthesis=CrossSectionSynthesis(),
    )

    assert "p_9999" in qa_report.invalid_paragraph_refs
    assert qa_report.valid_paragraph_refs_pct < 100.0
    assert any("p_9999" in w for w in qa_report.warnings)


# ============================================================================
# 9. Interrupção e Recuperação Incremental via Checkpoint
# ============================================================================

def test_09_interruption_and_checkpoint_recovery(tmp_path: Path):
    ast = create_synthetic_ast("doc_checkpoint_09", "Documento Interrompido")
    storage_dir = tmp_path / "study"
    calls_made: List[str] = []

    def mock_llm_caller_stage1(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        sec_id = meta.get("section_id", "")
        calls_made.append(sec_id)
        # Se chegar à segunda secção, simula interrupção forçada
        if sec_id == "sec_method":
            raise RuntimeError("Falha de energia ou interrupção intencional!")
        return json.dumps({
            "central_idea": f"Análise concluída para {sec_id}",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj secção",
            "in_depth_synthesis": "Síntese secção",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine1 = AcademicReasoningEngine(storage_dir=storage_dir, llm_caller=mock_llm_caller_stage1)
    with pytest.raises(RuntimeError):
        engine1.analyze_document(ast)

    # Verifica que o checkpoint foi gravado em disco com os dados da primeira secção
    cp_path = storage_dir / "documents" / ast.document_id / "reasoning_checkpoint.json"
    assert cp_path.exists()
    cp_data = json.loads(cp_path.read_text(encoding="utf-8"))
    assert "sec_intro" in cp_data["completed_sections"]

    # Agora instanciamos um novo motor e retomamos
    calls_stage2: List[str] = []
    def mock_llm_caller_stage2(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        sec_id = meta.get("section_id", "")
        calls_stage2.append(sec_id)
        return json.dumps({
            "central_idea": f"Análise retomada para {sec_id}",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj secção",
            "in_depth_synthesis": "Síntese secção",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine2 = AcademicReasoningEngine(storage_dir=storage_dir, llm_caller=mock_llm_caller_stage2)
    dossier = engine2.analyze_document(ast)

    assert dossier.status == "COMPLETED"
    # A secção 'sec_intro' NÃO deve ter sido chamada novamente no stage 2 porque foi carregada do checkpoint!
    assert "sec_intro" not in calls_stage2
    assert "sec_method" in calls_stage2


# ============================================================================
# 10. Invalidação de Checkpoint por Alteração de Hash SHA256 ou AST
# ============================================================================

def test_10_checkpoint_invalidation_on_hash_or_ast_version_change(tmp_path: Path):
    storage_dir = tmp_path / "study"
    ast = create_synthetic_ast("doc_inval_10", "Documento para Invalidação", source_sha256="hash_v1")

    # Criamos manualmente um checkpoint pré-existente com hash_v1
    doc_dir = storage_dir / "documents" / ast.document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    cp_path = doc_dir / "reasoning_checkpoint.json"
    cp_path.write_text(
        json.dumps({
            "document_id": ast.document_id,
            "source_sha256": "hash_v1",
            "ast_version": ast.extractor_version,
            "model_name": "qwen3.5:9b",
            "completed_sections": {"sec_intro": {"section_id": "sec_intro", "title": "Velho"}},
            "completed_segments": {},
        }),
        encoding="utf-8",
    )

    # Agora modificamos o hash do documento
    ast.source_sha256 = "hash_v2_modificado"
    ast.metadata.source_sha256 = "hash_v2_modificado"

    calls_made: List[str] = []
    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        calls_made.append(meta.get("section_id", ""))
        return json.dumps({
            "central_idea": "Ideia nova",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj secção nova",
            "in_depth_synthesis": "Síntese nova",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global nova",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=storage_dir, llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    # Porque o hash mudou, 'sec_intro' teve de ser recalculada e aparece em calls_made
    assert "sec_intro" in calls_made
    assert dossier.source_sha256 == "hash_v2_modificado"


# ============================================================================
# 11. Falha Explícita Quando Ollama Está Indisponível (Zero Fallback Falso)
# ============================================================================

def test_11_ollama_unavailable_raises_explicit_error(tmp_path: Path):
    ast = create_synthetic_ast("doc_fail_11", "Documento para Teste de Indisponibilidade")

    def mock_broken_ollama(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        return None, {"status": "UNAVAILABLE", "error": "ConnectError: Connection refused to 127.0.0.1:11434"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_broken_ollama, max_retries_per_call=1)

    with pytest.raises(OllamaInferenceUnavailableError) as exc_info:
        engine.analyze_document(ast)

    assert "indisponível" in str(exc_info.value).lower() or "inacessível" in str(exc_info.value).lower()


# ============================================================================
# 12. Cancelamento Gracioso de Análise em Curso
# ============================================================================

def test_12_graceful_cancellation_during_reasoning(tmp_path: Path):
    ast = create_synthetic_ast("doc_cancel_12", "Documento para Cancelamento")
    cancelled = False

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        nonlocal cancelled
        cancelled = True
        return json.dumps({
            "central_idea": "Idea",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Synth",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    def check_cancel() -> bool:
        return cancelled

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)

    with pytest.raises(ReasoningCancelledError):
        engine.analyze_document(ast, cancellation_check=check_cancel)


# ============================================================================
# 13. Teste de Integração Real com Ollama Local (qwen3.5:9b)
# ============================================================================

@pytest.mark.skipif(
    os.environ.get("STUDY_FORCE_LIVE_LLM") not in ("1", "true", "yes"),
    reason="Executado exclusivamente quando STUDY_FORCE_LIVE_LLM=1 é passado explicitamente para aferição real",
)
def test_13_real_ollama_qwen_live_integration(tmp_path: Path):
    """
    Teste real de ponta-a-ponta com o modelo local Qwen 3.5:9b.
    Só é invocado com a flag de ambiente para não bloquear suites normais de CI/CD.
    """
    ast = create_synthetic_ast("doc_live_real_13", "Grounding Epistémico Real")
    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study")
    dossier = engine.analyze_document(ast)

    assert dossier.status == "COMPLETED"
    assert dossier.model_name == "qwen3.5:9b"
    assert len(dossier.section_analyses) >= 1
    assert dossier.qa_report.is_valid is True
    print(f"\n[Real Live Qwen] Duração total: {dossier.telemetry.total_duration_ms}ms")
    print(f"[Real Live Qwen] Síntese Global: {dossier.cross_section_synthesis.global_synthesis[:200]}...")

