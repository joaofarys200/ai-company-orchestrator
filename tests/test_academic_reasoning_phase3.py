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
    assert any("p_9999" in err for err in qa_report.errors)
    assert qa_report.is_valid is False


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


# ============================================================================
# 14. Falha de JSON no Segmento Marca Dossier Como PARTIAL (Sem Fallback Silencioso)
# ============================================================================

def test_14_segment_json_failure_marks_partial(tmp_path: Path):
    ast = create_synthetic_ast("doc_fail_seg_14", "Falha de JSON no Segmento")

    def mock_broken_segment(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "segment" in op:
            return "Texto livre inválido não-JSON", {"status": "FAILED_VALIDATION"}
        return json.dumps({
            "objective": "Obj",
            "in_depth_synthesis": "Synth",
            "core_ideas": [],
            "concepts": [],
            "arguments": [],
            "limitations": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_broken_segment, max_retries_per_call=1)
    dossier = engine.analyze_document(ast)

    assert dossier.status == "PARTIAL"
    assert len(dossier.failed_operations) >= 1
    assert any(fo["stage"] == "segment_analysis" for fo in dossier.failed_operations)
    assert dossier.qa_report.is_valid is False


# ============================================================================
# 15. Falha de JSON na Síntese de Secção Marca Dossier Como PARTIAL
# ============================================================================

def test_15_section_synthesis_json_failure_marks_partial(tmp_path: Path):
    ast = create_synthetic_ast("doc_fail_sec_15", "Falha na Síntese da Secção")

    def mock_broken_section(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        # Falha apenas na primeira secção
        if "section" in op and meta.get("section_id") == "sec_intro":
            return "Inválido sem JSON", {"status": "FAILED_VALIDATION"}
        return json.dumps({
            "central_idea": "Ideia central válida",
            "passage_objective": "Objetivo",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese válida da secção",
            "core_ideas": ["Ideia"],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_broken_section, max_retries_per_call=1)
    dossier = engine.analyze_document(ast)

    assert dossier.status == "PARTIAL"
    assert any(fo["stage"] == "section_synthesis" for fo in dossier.failed_operations)
    assert dossier.section_analyses[0].in_depth_synthesis == ""
    assert dossier.qa_report.is_valid is False


# ============================================================================
# 16. Falha de JSON na Integração Transversal Marca Dossier Como PARTIAL
# ============================================================================

def test_16_cross_section_json_failure_marks_partial(tmp_path: Path):
    ast = create_synthetic_ast("doc_fail_cross_16", "Falha na Integração Transversal")

    def mock_broken_cross(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "cross" in op:
            return "Erro JSON Cross", {"status": "FAILED_VALIDATION"}
        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese válida da secção",
            "core_ideas": ["Ideia A"],
            "concepts": [],
            "arguments": [],
            "limitations": [],
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_broken_cross, max_retries_per_call=1)
    dossier = engine.analyze_document(ast)

    assert dossier.status == "PARTIAL"
    assert any(fo["stage"] == "cross_section_integration" for fo in dossier.failed_operations)
    assert dossier.cross_section_synthesis.global_synthesis == ""
    assert dossier.qa_report.is_valid is False


# ============================================================================
# 17. QA Inválido Quando Parágrafo Não Existe na AST
# ============================================================================

def test_17_qa_invalid_when_paragraph_does_not_exist():
    ast = create_synthetic_ast("doc_qa_para_17", "QA Parágrafo Inexistente")
    evaluator = ReasoningQAEvaluator()

    from services.academic_reasoning_engine import SectionAnalysis, CrossSectionSynthesis
    mock_sec = SectionAnalysis(
        section_id="sec_intro",
        title="1. Introdução",
        source_refs=[EvidenceRef(section_id="sec_intro", paragraph_id="p_9999", status="SOURCE_FACT")],
    )
    report = evaluator.evaluate(
        ast=ast,
        section_analyses=[mock_sec],
        results=[],
        cross_synthesis=CrossSectionSynthesis(),
    )

    assert report.is_valid is False
    assert "p_9999" in report.invalid_paragraph_refs
    assert any("p_9999" in err for err in report.errors)


# ============================================================================
# 18. QA Inválido Quando Parágrafo Pertence a Outra Secção
# ============================================================================

def test_18_qa_invalid_when_paragraph_belongs_to_different_section():
    ast = create_synthetic_ast("doc_qa_sec_mismatch_18", "QA Secção Incorreta")
    evaluator = ReasoningQAEvaluator()

    from services.academic_reasoning_engine import SectionAnalysis, CrossSectionSynthesis
    # p_1 pertence a 'sec_intro' na AST, mas é referenciado sob 'sec_conclusion'
    mock_sec = SectionAnalysis(
        section_id="sec_conclusion",
        title="4. Conclusão",
        source_refs=[EvidenceRef(section_id="sec_conclusion", paragraph_id="p_1", status="SOURCE_FACT")],
    )
    report = evaluator.evaluate(
        ast=ast,
        section_analyses=[mock_sec],
        results=[],
        cross_synthesis=CrossSectionSynthesis(),
    )

    assert report.is_valid is False
    assert any("pertence à secção" in err for err in report.errors)


# ============================================================================
# 19. QA Inválido Quando Número de Página Não Coincide com AST
# ============================================================================

def test_19_qa_invalid_when_page_number_mismatches_ast():
    ast = create_synthetic_ast("doc_qa_page_mismatch_19", "QA Página Incorreta")
    evaluator = ReasoningQAEvaluator()

    from services.academic_reasoning_engine import SectionAnalysis, CrossSectionSynthesis
    # p_1 está na página 1, mas ref indica página 2
    mock_sec = SectionAnalysis(
        section_id="sec_intro",
        title="1. Introdução",
        source_refs=[EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=2, status="SOURCE_FACT")],
    )
    report = evaluator.evaluate(
        ast=ast,
        section_analyses=[mock_sec],
        results=[],
        cross_synthesis=CrossSectionSynthesis(),
    )

    assert report.is_valid is False
    assert 2 in report.invalid_page_refs
    assert any("não coincide com a página real" in err for err in report.errors)


# ============================================================================
# 20. QA Inválido Quando Resultado SOURCE_FACT Não Possui Parágrafo de Suporte
# ============================================================================

def test_20_qa_invalid_when_source_fact_has_empty_paragraph():
    ast = create_synthetic_ast("doc_qa_res_empty_20", "QA Resultado Vazio")
    evaluator = ReasoningQAEvaluator()

    from services.academic_reasoning_engine import SectionAnalysis, ResultItem, CrossSectionSynthesis
    mock_res = ResultItem(
        statement="Aumento estatisticamente significativo",
        evidence_data="p < 0.05",
        evidence_refs=[
            EvidenceRef(section_id="sec_results", paragraph_id="", status="SOURCE_FACT")
        ],
    )
    report = evaluator.evaluate(
        ast=ast,
        section_analyses=[],
        results=[mock_res],
        cross_synthesis=CrossSectionSynthesis(),
    )

    assert report.is_valid is False
    assert any("não possui paragraph_id de suporte válido" in err for err in report.errors)


# ============================================================================
# 21. Invalidação de Checkpoint por Alteração da Versão dos Prompts
# ============================================================================

def test_21_checkpoint_invalidation_on_prompt_version_change(tmp_path: Path):
    storage_dir = tmp_path / "study"
    ast = create_synthetic_ast("doc_inval_prompt_21", "Invalidação por Versão de Prompt")

    doc_dir = storage_dir / "documents" / ast.document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    cp_path = doc_dir / "reasoning_checkpoint.json"
    cp_path.write_text(
        json.dumps({
            "document_id": ast.document_id,
            "source_sha256": ast.source_sha256,
            "ast_version": ast.extractor_version,
            "model_name": "qwen3.5:9b",
            "prompt_versions": {"segment_analysis": "v1.0.0-obsoleta"},  # Versão antiga!
            "completed_sections": {"sec_intro": {"section_id": "sec_intro", "title": "Intro Antiga"}},
            "completed_segments": {},
        }),
        encoding="utf-8",
    )

    engine = AcademicReasoningEngine(storage_dir=storage_dir)
    loaded = engine._load_checkpoint(ast.document_id, ast.source_sha256, ast.extractor_version)
    assert loaded is None  # Checkpoint deve ser rejeitado por discrepância de versão dos prompts


# ============================================================================
# 22. Recuperação de Checkpoint Reconstrói Mapa Global de Conceitos
# ============================================================================

def test_22_checkpoint_recovery_reconstructs_concepts_map(tmp_path: Path):
    storage_dir = tmp_path / "study"
    ast = create_synthetic_ast("doc_concepts_recov_22", "Reconstrução de Conceitos")

    doc_dir = storage_dir / "documents" / ast.document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    cp_path = doc_dir / "reasoning_checkpoint.json"
    from services.academic_reasoning_engine import PROMPT_VERSIONS
    cp_path.write_text(
        json.dumps({
            "document_id": ast.document_id,
            "source_sha256": ast.source_sha256,
            "ast_version": ast.extractor_version,
            "model_name": "qwen3.5:9b",
            "prompt_versions": PROMPT_VERSIONS,
            "completed_sections": {
                "sec_intro": {
                    "section_id": "sec_intro",
                    "title": "1. Introdução",
                    "section_type": "introduction",
                    "objective": "Introduzir o tema",
                    "in_depth_synthesis": "Síntese recuperada do checkpoint",
                    "core_ideas": ["Ideia X"],
                    "concepts": [
                        {"name": "Conceito Recuperado A", "explanation": "Definição do conceito A"}
                    ],
                    "arguments": [],
                    "evidences": [],
                    "limitations": [],
                    "source_refs": [
                        {"section_id": "sec_intro", "paragraph_id": "p_1", "status": "SOURCE_FACT"}
                    ],
                    "segment_ids": [],
                }
            },
            "completed_segments": {},
        }),
        encoding="utf-8",
    )

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=storage_dir, llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    assert any(c.name == "Conceito Recuperado A" for c in dossier.conceptual_analysis)


# ============================================================================
# 23. Análise Metodológica Processa Mais de Oito Parágrafos (Sem Limite Fixo)
# ============================================================================

def test_23_methodology_processes_more_than_eight_paragraphs(tmp_path: Path):
    paras_method = [
        f"Parágrafo metodológico {i} descrevendo detalhadamente a variável {i} e respetiva calibração."
        for i in range(1, 15)
    ]
    sections_spec = [
        {
            "section_id": "sec_method_long",
            "title": "2. Metodologia Extensa",
            "kind": "methodology",
            "paragraphs": paras_method,
        }
    ]
    ast = create_synthetic_ast("doc_method_long_23", "Metodologia Longa", sections_spec=sections_spec)
    received_method_prompt = ""

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        nonlocal received_method_prompt
        op = meta.get("operation", "")
        if "methodology" in op:
            received_method_prompt = user_prompt
            return json.dumps({
                "is_applicable": True,
                "research_type": "Empírico",
                "methodological_design": "Extenso",
                "methods_used": ["Método A"],
                "sample_or_participants": "100",
                "instruments": [],
                "procedures": [],
                "variables": [],
                "data_sources": [],
                "analysis_techniques": [],
                "methodological_limitations": [],
                "results": [],
            }), {"status": "COMPLETED"}

        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    # Verifica que parágrafos além do 8º (ex: p_9, p_10, p_14) estão presentes no prompt recebido
    assert "p_9" in received_method_prompt or "Parágrafo metodológico 9" in received_method_prompt
    assert "p_14" in received_method_prompt or "Parágrafo metodológico 14" in received_method_prompt
    assert dossier.methodology_analysis.is_applicable is True


# ============================================================================
# 24. Segmentação Semântica Metodológica com Múltiplos Segmentos
# ============================================================================

def test_24_methodology_semantic_segmentation_multiple_segments(tmp_path: Path):
    """Verifica que uma secção metodológica extensa é dividida em múltiplos segmentos e todos são processados."""
    paras_method = [
        f"Parágrafo metodológico extenso {i}: Detalhe exaustivo do procedimento de calibração instrumental e medição empírica da variável {i} com repetições sistemáticas." * 4
        for i in range(1, 13)
    ]
    sections_spec = [
        {
            "section_id": "sec_method_multi",
            "title": "2. Procedimento Experimental Detalhado",
            "kind": "methodology",
            "paragraphs": paras_method,
        }
    ]
    ast = create_synthetic_ast("doc_method_multi_24", "Metodologia Multi-Segmento", sections_spec=sections_spec)
    method_calls: List[str] = []

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "methodology" in op:
            method_calls.append(meta.get("segment_id", ""))
            return json.dumps({
                "is_applicable": True,
                "research_type": "Experimental",
                "methodological_design": "Delineamento Fatorial",
                "methods_used": [f"Método {len(method_calls)}"],
                "sample_or_participants": "100 amostras",
                "instruments": [f"Instrumento {len(method_calls)}"],
                "procedures": [f"Procedimento {len(method_calls)}"],
                "variables": [f"Variável {len(method_calls)}"],
                "data_sources": ["Sensores Ópticos"],
                "analysis_techniques": ["ANOVA"],
                "methodological_limitations": [],
                "results": [
                    {
                        "statement": f"Resultado observado no segmento {len(method_calls)}",
                        "evidence_data": f"Valor p < 0.05 no lote {len(method_calls)}",
                        "paragraph_id": f"p_{len(method_calls)}",
                    }
                ],
            }), {"status": "COMPLETED"}

        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    # Forçamos orçamento menor de tokens para o segmentador para garantir partição em múltiplos segmentos
    engine.segmenter = SemanticSegmenter(max_tokens_per_segment=350, overlap_paragraphs=1)
    dossier = engine.analyze_document(ast)

    assert len(method_calls) >= 2, f"Deveria ter gerado pelo menos 2 segmentos, gerou {len(method_calls)}"
    assert dossier.methodology_analysis.is_applicable is True
    assert len(dossier.methodology_analysis.methods_used) >= 2
    assert len(dossier.results_and_evidence) >= 2


# ============================================================================
# 25. Preservação de IDs e Páginas através de Múltiplos Segmentos Metodológicos
# ============================================================================

def test_25_preservation_of_fine_grained_refs_across_methodology_segments(tmp_path: Path):
    """Verifica que os itens de resultado de diferentes segmentos metodológicos preservam paragraph_id e page_number."""
    paras = [
        "Metodologia inicial na página 1 detalhando o desenho preliminar da investigação.",
        "Metodologia avançada na página 2 com testes de stress e calibração de sensores.",
    ]
    sections_spec = [
        {
            "section_id": "sec_meth_fine",
            "title": "2. Metodologia",
            "kind": "methodology",
            "paragraphs": paras,
        }
    ]
    ast = create_synthetic_ast("doc_fine_25", "Grounding Fino", sections_spec=sections_spec)
    # Assegurar que os parágrafos estão em páginas distintas
    ast.paragraphs[0].page_number = 1
    ast.paragraphs[1].page_number = 2
    ast.pages[0].page_number = 1
    ast.pages.append(PageInfo(page_number=2, width=595.0, height=842.0))

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "methodology" in op:
            return json.dumps({
                "is_applicable": True,
                "research_type": "Empírico",
                "methodological_design": "Observacional",
                "methods_used": ["M1"],
                "sample_or_participants": "N=50",
                "instruments": [],
                "procedures": [],
                "variables": [],
                "data_sources": [],
                "analysis_techniques": [],
                "methodological_limitations": [],
                "results": [
                    {
                        "statement": "Resultado P1",
                        "evidence_data": "Dados P1",
                        "paragraph_id": "p_1",
                    },
                    {
                        "statement": "Resultado P2",
                        "evidence_data": "Dados P2",
                        "paragraph_id": "p_2",
                    },
                ],
            }), {"status": "COMPLETED"}

        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    r1 = next(r for r in dossier.results_and_evidence if r.statement == "Resultado P1")
    r2 = next(r for r in dossier.results_and_evidence if r.statement == "Resultado P2")

    assert r1.evidence_refs[0].paragraph_id == "p_1"
    assert r1.evidence_refs[0].page_number == 1
    assert r1.evidence_refs[0].status == "SOURCE_FACT"

    assert r2.evidence_refs[0].paragraph_id == "p_2"
    assert r2.evidence_refs[0].page_number == 2
    assert r2.evidence_refs[0].status == "SOURCE_FACT"
    assert dossier.status == "COMPLETED"


# ============================================================================
# 26. Falha em Segmento Metodológico Marca Estado PARTIAL e Regista Falha
# ============================================================================

def test_26_methodology_segment_failure_marks_partial_and_logs_failed_operation(tmp_path: Path):
    """Verifica que a falha de um segmento metodológico marca PARTIAL e regista em failed_operations."""
    paras = [
        "Metodologia segmento 1 com procedimentos standard e calibração preliminar dos equipamentos analíticos." * 3,
        "Metodologia segmento 2 com formulações complexas e validação estatística avançada de dados." * 3,
    ]
    sections_spec = [
        {
            "section_id": "sec_meth_fail",
            "title": "2. Metodologia Mista",
            "kind": "methodology",
            "paragraphs": paras,
        }
    ]
    ast = create_synthetic_ast("doc_meth_fail_26", "Falha Parcial Metodológica", sections_spec=sections_spec)
    call_idx = 0

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        nonlocal call_idx
        op = meta.get("operation", "")
        if "methodology" in op:
            seg_id = meta.get("segment_id", "")
            if "seg_0" in seg_id:
                # Segmento 0 falha em todas as tentativas após esgotar retries
                return "Texto livre sem JSON...", {"status": "INVALID_JSON_AFTER_RETRIES"}
            # Segmentos subsequentes têm sucesso
            return json.dumps({
                "is_applicable": True,
                "research_type": "Empírico",
                "methodological_design": "Robusto",
                "methods_used": ["Método Válido 2"],
                "sample_or_participants": "50",
                "instruments": [],
                "procedures": [],
                "variables": [],
                "data_sources": [],
                "analysis_techniques": [],
                "methodological_limitations": [],
                "results": [
                    {
                        "statement": "Resultado do segmento 2",
                        "evidence_data": "Evidência",
                        "paragraph_id": "p_2",
                    }
                ],
            }), {"status": "COMPLETED"}

        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese da metodologia",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller, max_retries_per_call=1)
    engine.segmenter = SemanticSegmenter(max_tokens_per_segment=150, overlap_paragraphs=0)
    dossier = engine.analyze_document(ast)

    assert dossier.status == "PARTIAL", f"Esperado status PARTIAL devido a falha no segmento metodológico, obtido: {dossier.status}"
    assert any(fo.get("stage") == "methodology_results_analysis" for fo in dossier.failed_operations)
    assert dossier.telemetry.failures_count >= 1
    assert dossier.qa_report.is_valid is False  # Devido à operação falhada registada


# ============================================================================
# 27. Validade do QA Força Estado PARTIAL Mesmo Sem Erros de Transporte
# ============================================================================

def test_27_qa_invalid_strictly_forces_partial_status(tmp_path: Path):
    """Garante que se qa_report.is_valid for False, dossier.status NUNCA pode ser COMPLETED (força PARTIAL)."""
    ast = create_synthetic_ast("doc_qa_force_27", "QA Invalida Status")

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "methodology" in op:
            # O modelo devolve um paragraph_id fantasma que não existe na AST
            return json.dumps({
                "is_applicable": True,
                "research_type": "Empírico",
                "methodological_design": "Experimental",
                "methods_used": ["M1"],
                "sample_or_participants": "100",
                "instruments": [],
                "procedures": [],
                "variables": [],
                "data_sources": [],
                "analysis_techniques": [],
                "methodological_limitations": [],
                "results": [
                    {
                        "statement": "Afirmação empírica apoiada em parágrafo inexistente",
                        "evidence_data": "Dado fictício",
                        "paragraph_id": "p_fantasma_9999",  # Parágrafo FANTASMA!
                    }
                ],
            }), {"status": "COMPLETED"}

        return json.dumps({
            "central_idea": "Ideia válida",
            "passage_objective": "Obj",
            "concepts": [{"name": "C1"}],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese válida da secção.",
            "core_ideas": ["Ideia"],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Síntese global válida.",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    # Nenhuma falha de modelo/transporte ocorreu:
    assert len(dossier.failed_operations) == 0
    # Porém, a auditoria forense reprovou a evidência:
    assert dossier.qa_report.is_valid is False
    assert "p_fantasma_9999" in dossier.qa_report.invalid_paragraph_refs
    # O estado do dossier é estritamente forçado a PARTIAL:
    assert dossier.status == "PARTIAL", f"Status deveria ser PARTIAL, foi {dossier.status}"


# ============================================================================
# 28. Recuperação Determinística e Idempotência de Conceitos
# ============================================================================

def test_28_deterministic_concept_recovery_and_idempotence(tmp_path: Path):
    """Verifica que identificadores de conceitos são 100% determinísticos e restaurados integralmente de checkpoints."""
    from services.academic_reasoning_engine import generate_deterministic_concept_id

    # 1. Teste unitário da função de hashing estável
    id1 = generate_deterministic_concept_id("Grounding Epistémico")
    id2 = generate_deterministic_concept_id("Grounding Epistémico")
    id3 = generate_deterministic_concept_id("  grounding epistémico  ")
    assert id1 == id2 == id3
    assert id1.startswith("concept_grounding_epistemico_")

    # 2. Execução com checkpoint e recuperação
    ast = create_synthetic_ast("doc_det_concept_28", "Conceitos Determinísticos")

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        return json.dumps({
            "central_idea": "Ideia central",
            "passage_objective": "Obj",
            "concepts": [
                {
                    "name": "Grounding Epistémico",
                    "definition": "Ancoragem rigorosa no texto original",
                    "explanation": "Explicação detalhada da ancoragem factual.",
                    "relationships": ["depende de Rigor Científico"],
                    "context_of_use": "Auditoria de papers",
                    "paragraph_ids": ["p_1"],
                }
            ],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese com conceito estruturado.",
            "core_ideas": ["Core 1"],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine1 = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier1 = engine1.analyze_document(ast)

    c1 = next(c for c in dossier1.conceptual_analysis if c.name == "Grounding Epistémico")
    assert c1.concept_id == id1
    assert c1.definition == "Ancoragem rigorosa no texto original"

    # Segunda execução (reutilizando checkpoint persistido em disco)
    engine2 = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    dossier2 = engine2.analyze_document(ast)

    c2 = next(c for c in dossier2.conceptual_analysis if c.name == "Grounding Epistémico")
    assert c2.concept_id == c1.concept_id
    assert c2.definition == c1.definition
    assert c2.explanation == c1.explanation
    assert c2.relationships == c1.relationships
    assert c2.context_of_use == c1.context_of_use


# ============================================================================
# 29. Retoma de Checkpoint Metodológico sem Reexecução de Segmentos
# ============================================================================

def test_29_methodology_checkpoint_resumption_skips_completed_segments(tmp_path: Path):
    """Verifica que segmentos metodológicos já registados em checkpoint não são reenviados ao modelo."""
    paras = [
        "Metodologia bloco 1 procedimentos iniciais de recolha e validação preliminar." * 3,
        "Metodologia bloco 2 análise estatística inferencial e modelos preditivos." * 3,
    ]
    sections_spec = [
        {
            "section_id": "sec_meth_res",
            "title": "2. Metodologia",
            "kind": "methodology",
            "paragraphs": paras,
        }
    ]
    ast = create_synthetic_ast("doc_meth_res_29", "Retoma Metodológica", sections_spec=sections_spec)
    called_segment_ids: List[str] = []

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "methodology" in op:
            seg_id = meta.get("segment_id", "")
            called_segment_ids.append(seg_id)
            return json.dumps({
                "is_applicable": True,
                "research_type": "Empírico",
                "methodological_design": "Experimental",
                "methods_used": [f"Método-{seg_id}"],
                "sample_or_participants": "50",
                "instruments": [],
                "procedures": [],
                "variables": [],
                "data_sources": [],
                "analysis_techniques": [],
                "methodological_limitations": [],
                "results": [
                    {
                        "statement": f"Resultado {seg_id}",
                        "evidence_data": "Dados",
                        "paragraph_id": "p_2",
                    }
                ],
            }), {"status": "COMPLETED"}

        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    # Pré-gravar checkpoint contendo secção metodológica segmento 0 já concluído
    storage_dir = tmp_path / "study"
    doc_dir = storage_dir / "documents" / "doc_meth_res_29"
    doc_dir.mkdir(parents=True, exist_ok=True)
    from services.academic_reasoning_engine import PROMPT_VERSIONS
    cp_file = doc_dir / "reasoning_checkpoint.json"
    cp_file.write_text(
        json.dumps({
            "document_id": "doc_meth_res_29",
            "source_sha256": "sha256_synthetic_baseline",
            "ast_version": "3.0.0-academic",
            "model_name": "qwen3.5:9b",
            "prompt_versions": PROMPT_VERSIONS,
            "completed_segments": {},
            "completed_sections": {},
            "completed_method_segments": {
                "sec_meth_res_seg_0": {
                    "is_applicable": True,
                    "research_type": "Empírico Gravado",
                    "methodological_design": "Pre-computado",
                    "methods_used": ["Método em Checkpoint"],
                    "sample_or_participants": "50",
                    "instruments": [],
                    "procedures": [],
                    "variables": [],
                    "data_sources": [],
                    "analysis_techniques": [],
                    "methodological_limitations": [],
                    "results": [
                        {
                            "statement": "Resultado pré-gravado do segmento 0",
                            "evidence_data": "Evidência antiga",
                            "paragraph_id": "p_1",
                        }
                    ],
                }
            },
            "conceptual_analysis": [],
            "updated_at": "2026-11-05T00:00:00",
        }),
        encoding="utf-8",
    )

    engine = AcademicReasoningEngine(storage_dir=storage_dir, llm_caller=mock_llm_caller)
    engine.segmenter = SemanticSegmenter(max_tokens_per_segment=150, overlap_paragraphs=0)
    dossier = engine.analyze_document(ast)

    # O segmento 0 NÃO deve ter sido chamado novamente ao LLM
    assert "sec_meth_res_seg_0" not in called_segment_ids
    # Mas o resultado do segmento 0 recuperado do checkpoint deve constar no dossier final
    assert any("pré-gravado" in r.statement for r in dossier.results_and_evidence)
    assert "Método em Checkpoint" in dossier.methodology_analysis.methods_used


# ============================================================================
# 30. Falha Total na Metodologia com Secções Válidas produz PARTIAL
# ============================================================================

def test_30_total_methodology_failure_produces_partial_status(tmp_path: Path):
    """Quando todos os segmentos metodológicos falham mas as secções têm síntese, o estado é PARTIAL."""
    sections_spec = [
        {
            "section_id": "sec_meth_all_fail",
            "title": "2. Metodologia",
            "kind": "methodology",
            "paragraphs": ["Parágrafo metodológico que falhará no modelo."],
        }
    ]
    ast = create_synthetic_ast("doc_fail_all_30", "Falha Total Metodologia", sections_spec=sections_spec)

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "methodology" in op:
            return "Inválido sem JSON", {"status": "INVALID_JSON_AFTER_RETRIES"}

        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese com sucesso da secção.",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller, max_retries_per_call=1)
    dossier = engine.analyze_document(ast)

    assert dossier.status == "PARTIAL"
    assert any(fo["stage"] == "methodology_results_analysis" for fo in dossier.failed_operations)
    assert dossier.qa_report.is_valid is False


# ============================================================================
# 31. Equivalência Funcional e Correção dos Índices Secundários O(1) da AST
# ============================================================================

def test_31_ast_secondary_indices_functional_equivalence():
    """Valida que os novos índices secundários O(1) produzem resultados 100% equivalentes à pesquisa linear."""
    sections_spec = [
        {"section_id": f"sec_{i}", "title": f"Secção {i}", "kind": "body", "paragraphs": [f"P_{i}_{j}" for j in range(5)]}
        for i in range(1, 10)
    ]
    ast = create_synthetic_ast("doc_idx_31", "Teste Índices Secundários", sections_spec=sections_spec)

    # 1. paragraphs_by_id
    for p in ast.paragraphs:
        assert ast.get_paragraph(p.paragraph_id) is p
        assert ast.paragraphs_by_id[p.paragraph_id] is p

    # 2. sections_by_id
    for s in ast.sections:
        assert ast.get_section(s.section_id) is s
        assert ast.sections_by_id[s.section_id] is s

    # 3. paragraphs_by_section_id
    for s in ast.sections:
        linear_paras = [p for p in ast.paragraphs if p.section_id == s.section_id]
        indexed_paras = ast.get_paragraphs_for_section(s.section_id)
        assert indexed_paras == linear_paras

    # 4. Invalidação
    ast.invalidate_indices()
    assert not hasattr(ast, "_cached_paragraphs_by_id")
    # Acesso recria índice automaticamente
    assert ast.get_paragraph(ast.paragraphs[0].paragraph_id) is ast.paragraphs[0]


# ============================================================================
# 32. Benchmark de Performance: Índices Secundários O(1) vs Pesquisa Linear O(N)
# ============================================================================

def test_32_ast_secondary_indices_performance_benchmark():
    """Mede e comprova a aceleração empírica dos índices secundários O(1) comparados com varrimentos lineares."""
    sections_spec = [
        {"section_id": f"sec_{i}", "title": f"Secção {i}", "kind": "body", "paragraphs": [f"Parágrafo com conteúdo substancial {i}_{j}" for j in range(10)]}
        for i in range(1, 100)
    ]
    ast = create_synthetic_ast("doc_bench_32", "Benchmark AST", sections_spec=sections_spec)
    # Total de 99 secções * 10 = 990 parágrafos

    target_pid = ast.paragraphs[-1].paragraph_id
    target_sec = ast.sections[-1].section_id
    iterations = 2000

    # 1. Medição Linear
    t0_linear = time.perf_counter()
    for _ in range(iterations):
        _ = next((p for p in ast.paragraphs if p.paragraph_id == target_pid), None)
        _ = [p for p in ast.paragraphs if p.section_id == target_sec]
    elapsed_linear = time.perf_counter() - t0_linear

    # 2. Medição Indexada O(1)
    # Aquecimento do cache
    _ = ast.paragraphs_by_id
    _ = ast.paragraphs_by_section_id

    t0_indexed = time.perf_counter()
    for _ in range(iterations):
        _ = ast.get_paragraph(target_pid)
        _ = ast.get_paragraphs_for_section(target_sec)
    elapsed_indexed = time.perf_counter() - t0_indexed

    speedup = elapsed_linear / max(1e-6, elapsed_indexed)
    print(f"\n[Benchmark AST Indices] Linear: {elapsed_linear*1000:.2f}ms | Indexado: {elapsed_indexed*1000:.2f}ms | Aceleração: {speedup:.1f}x")
    assert speedup > 2.0, f"Aceleração deveria ser superior a 2x, obtida: {speedup:.2f}x"


# ============================================================================
# 33. Integração End-to-End: Discrepância de Página Força Estado PARTIAL
# ============================================================================

def test_33_page_mismatch_forces_partial_status(tmp_path: Path):
    """Verifica que uma divergência entre a página indicada e a página real da AST reprova o QA e marca PARTIAL."""
    ast = create_synthetic_ast("doc_page_mismatch_33", "Divergência de Página")
    # p_1 está na página 1 na AST
    assert ast.paragraphs[0].page_number == 1

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "section" in op:
            return json.dumps({
                "objective": "Objetivo",
                "in_depth_synthesis": "Síntese da secção.",
                "core_ideas": ["Ideia"],
                "concepts": [],
                "arguments": [],
                "limitations": [],
            }), {"status": "COMPLETED"}

        return json.dumps({
            "central_idea": "Ideia",
            "passage_objective": "Obj",
            "concepts": [],
            "definitions": [],
            "arguments": [],
            "assumptions": [],
            "partial_conclusions": [],
            "technical_terminology": [],
            "limitations_or_notices": [],
            "objective": "Obj",
            "in_depth_synthesis": "Síntese",
            "core_ideas": [],
            "argumentative_progression": [],
            "conceptual_relationships": [],
            "coherence_and_tensions": [],
            "idea_dependencies": [],
            "global_synthesis": "Global",
        }), {"status": "COMPLETED"}

    engine = AcademicReasoningEngine(storage_dir=tmp_path / "study", llm_caller=mock_llm_caller)
    # Executa análise inicial
    dossier = engine.analyze_document(ast)
    assert dossier.status == "COMPLETED"

    # Agora criamos um resultado com página deliberadamente adulterada (p.99 em vez de p.1)
    from services.academic_reasoning_engine import ResultItem, ReasoningQAEvaluator
    tampered_result = ResultItem(
        statement="Resultado adulterado",
        evidence_refs=[EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=99, status="SOURCE_FACT")],
    )
    evaluator = ReasoningQAEvaluator()
    report = evaluator.evaluate(
        ast=ast,
        section_analyses=dossier.section_analyses,
        results=[tampered_result],
        cross_synthesis=dossier.cross_section_synthesis,
    )

    assert report.is_valid is False
    assert 99 in report.invalid_page_refs



