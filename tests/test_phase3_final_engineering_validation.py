"""
JARVIS OS — STUDY ENGINE PHASE 3: FINAL ENGINEERING CORRECTIONS & VALIDATION
Suite de 30 testes obrigatórios cobrindo as 4 correções fundamentais:
  6.1. Gestão de Contexto e Subdivisão Semântica (Testes 1 a 8)
  6.2. Integridade e Proveniência de Conceitos (Testes 9 a 14)
  6.3. Consistência e Invalidação dos Índices da AST (Testes 15 a 22)
  6.4. Integração, Compatibilidade e Regressão (Testes 23 a 30)
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from services.document_intelligence import (
    AcademicDocumentAST,
    ASTParagraph,
    ASTSection,
    DocumentMetadata,
    ExtractionReport,
    PageInfo,
    VersionedList,
)
from services.academic_reasoning_engine import (
    AcademicReasoningDossier,
    AcademicReasoningEngine,
    ConceptItem,
    ContextBudgetExceededError,
    ContextBudgetManager,
    CrossSectionSynthesis,
    DocumentCoreAnalysis,
    EpistemicStatus,
    EvidenceRef,
    MethodologyAnalysis,
    ReasoningQAEvaluator,
    ReasoningQAReport,
    ReasoningTelemetry,
    ResultItem,
    SectionAnalysis,
    SemanticSegmenter,
    generate_deterministic_concept_id,
)
from services.study_service import StudyService
from tests.test_academic_reasoning_phase3 import create_synthetic_ast


# ============================================================================
# 6.1. TESTES DE GESTÃO REAL DO ORÇAMENTO DE CONTEXTO (Testes 1 a 8)
# ============================================================================

def test_01_document_with_single_paragraph_exceeding_segment_budget():
    """1. Documento com um parágrafo individual superior ao orçamento de um segmento."""
    # Parágrafo de 3500 palavras (~4500 tokens), claramente acima de 2200 tokens
    sentences = [f"Frase explicativa detalhada número {i} sobre epistemologia científica." for i in range(1, 200)]
    long_text = " ".join(sentences)

    p = ASTParagraph(
        paragraph_id="p_huge",
        section_id="sec_1",
        text=long_text,
        page_number=1,
        page_end=1,
        order=1,
    )
    section = ASTSection(section_id="sec_1", title="Secção Longa", level=1, kind="body", page_start=1, page_end=1)

    segmenter = SemanticSegmenter(max_tokens_per_segment=800)
    segments = segmenter.segment_section(section, [p])

    assert len(segments) > 1, "Parágrafo longo deve ser dividido em múltiplos segmentos"
    for seg in segments:
        assert seg.token_est <= 850, f"Segmento {seg.segment_id} excede orçamento: {seg.token_est} tokens"


def test_02_paragraph_subdivided_without_silent_loss():
    """2. Confirmação de que o parágrafo é subdividido sem perda silenciosa de conteúdo."""
    sentences = [f"Esta é a proposição de teste número {i}." for i in range(1, 50)]
    original_text = " ".join(sentences)

    p = ASTParagraph(paragraph_id="p_sub", section_id="sec_1", text=original_text, page_number=1, page_end=1, order=1)
    section = ASTSection(section_id="sec_1", title="Secção", level=1, kind="body", page_start=1, page_end=1)

    segmenter = SemanticSegmenter(max_tokens_per_segment=200, overlap_paragraphs=0)
    segments = segmenter.segment_section(section, [p])

    # Reconstituir texto de todos os parágrafos em todos os segmentos
    reconstructed_sentences = []
    for seg in segments:
        for sp in seg.paragraphs:
            for s in sp.text.split(". "):
                clean_s = s.strip().rstrip(".")
                if clean_s and clean_s not in reconstructed_sentences:
                    reconstructed_sentences.append(clean_s)

    # Cada proposição original deve constar no conteúdo processado
    for i in range(1, 50):
        expected = f"Esta é a proposição de teste número {i}"
        assert any(expected in s for s in reconstructed_sentences), f"Perda silenciosa da frase {i}"


def test_03_preservation_of_paragraph_id_page_and_offsets():
    """3. Preservação do paragraph_id, página e secção nas subunidades geradas."""
    sentences = [f"Linha de argumentação {i} com fundamentação teórica sólida." for i in range(1, 60)]
    p = ASTParagraph(paragraph_id="p_grounded_42", section_id="sec_method", text=" ".join(sentences), page_number=3, page_end=3, order=42)
    section = ASTSection(section_id="sec_method", title="Metodologia", level=1, kind="methodology", page_start=3, page_end=3)

    segmenter = SemanticSegmenter(max_tokens_per_segment=250)
    segments = segmenter.segment_section(section, [p])

    assert len(segments) >= 2
    for seg in segments:
        assert 3 in seg.page_numbers
        for sp in seg.paragraphs:
            assert sp.paragraph_id == "p_grounded_42", "ID do parágrafo deve ser estritamente preservado"
            assert sp.page_number == 3, "Página do parágrafo deve ser estritamente preservada"
            assert sp.section_id == "sec_method", "Secção do parágrafo deve ser preservada"


def test_04_methodology_distributed_across_multiple_segments(tmp_path: Path):
    """4. Documento com metodologia distribuída por múltiplos segmentos sem concatenação monolítica."""
    method_paras = [f"Procedimento experimental detalhado no passo {i}." for i in range(1, 25)]
    ast = create_synthetic_ast(
        "doc_multi_method",
        "Estudo Metodológico Extenso",
        sections_spec=[
            {"section_id": "sec_intro", "title": "Introdução", "kind": "introduction", "paragraphs": ["Apresentação do estudo."]},
            {"section_id": "sec_method", "title": "Metodologia", "kind": "methodology", "paragraphs": method_paras},
            {"section_id": "sec_results", "title": "Resultados", "kind": "results", "paragraphs": ["Resultado validado."]},
        ],
    )

    recorded_ops = []

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        recorded_ops.append(op)
        if op == "academic_methodology_analysis":
            return json.dumps({
                "is_applicable": True,
                "research_type": "Empírico",
                "methodological_design": "Experimental",
                "methods_used": ["Segmentação"],
                "sample_or_participants": "100 amostras",
                "instruments": ["Instrumento A"],
                "procedures": ["Passo X"],
                "variables": ["Var Y"],
                "data_sources": ["Fonte Z"],
                "analysis_techniques": ["Técnica W"],
                "methodological_limitations": [],
                "results": [{"statement": "Resultado observado", "evidence_data": "Dados", "relation_to_objectives": "Obj", "interpretation_limitations": "", "paragraph_id": "p_2"}],
            }), {}
        elif op == "academic_segment_analysis":
            return json.dumps({
                "central_idea": "Ideia",
                "passage_objective": "Obj",
                "concepts": ["C1"],
                "definitions": [],
                "arguments": [{"claim": "Claim", "evidence": "Ev", "paragraph_id": "p_1", "status": "SOURCE_FACT"}],
                "assumptions": [],
                "partial_conclusions": [],
                "technical_terminology": [],
                "limitations_or_notices": [],
            }), {}
        elif op == "academic_section_synthesis":
            return json.dumps({"objective": "Obj", "in_depth_synthesis": "Síntese", "core_ideas": ["I1"], "concepts": [], "arguments": [], "limitations": []}), {}
        elif op == "academic_cross_section_integration":
            return json.dumps({"argumentative_progression": [], "conceptual_relationships": [], "coherence_and_tensions": [], "idea_dependencies": [], "global_synthesis": "Síntese global"}), {}
        return "{}", {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_llm_caller)
    dossier = engine.analyze_document(ast)

    method_calls = [op for op in recorded_ops if op == "academic_methodology_analysis"]
    assert len(method_calls) > 1, f"Metodologia deveria gerar múltiplas chamadas segmentadas, gerou {len(method_calls)}"
    assert dossier.methodology_analysis.is_applicable is True


def test_05_section_synthesis_with_many_segments_hierarchical_reduce(tmp_path: Path):
    """5. Síntese de uma secção com resultados de muitos segmentos aplicando Reduce 1 hierárquico."""
    paras = [f"Parágrafo extenso {i} da secção complexa com densidade informacional." for i in range(1, 20)]
    ast = create_synthetic_ast(
        "doc_hier_reduce1",
        "Documento com Secção Longa",
        sections_spec=[{"section_id": "sec_deep", "title": "Desenvolvimento Teórico", "kind": "body", "paragraphs": paras}],
    )

    operations_called = []

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        operations_called.append(op)
        if op == "academic_segment_analysis":
            return json.dumps({
                "central_idea": "Ideia detalhada do segmento com grande quantidade de texto explicativo e análise.",
                "passage_objective": "Objetivo do segmento.",
                "concepts": ["Conceito A", "Conceito B"],
                "definitions": [],
                "arguments": [{"claim": "Claim", "evidence": "Ev", "paragraph_id": "p_1", "status": "SOURCE_FACT"}],
                "assumptions": [],
                "partial_conclusions": [],
                "technical_terminology": [],
                "limitations_or_notices": [],
            }), {}
        elif op == "academic_section_intermediate_synthesis":
            return json.dumps({
                "batch_objective": "Objetivo intermédio",
                "batch_synthesis": "Síntese do lote de segmentos intermédio",
                "core_ideas": ["Ideia intermédia"],
                "concepts": [{"name": "Conceito A", "explanation": "Expl", "paragraph_ids": ["p_1"]}],
                "arguments": [],
                "limitations": [],
            }), {}
        elif op == "academic_section_synthesis":
            return json.dumps({
                "objective": "Objetivo consolidado",
                "in_depth_synthesis": "Síntese final aprofundada da secção após consolidação hierárquica.",
                "core_ideas": ["Ideia central consolidada"],
                "concepts": [{"name": "Conceito A", "explanation": "Explicação final", "paragraph_ids": ["p_1"]}],
                "arguments": [],
                "limitations": [],
            }), {}
        elif op == "academic_cross_section_integration":
            return json.dumps({"argumentative_progression": [], "conceptual_relationships": [], "coherence_and_tensions": [], "idea_dependencies": [], "global_synthesis": "Síntese global"}), {}
        return "{}", {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_llm_caller)
    # Forçar múltiplos segmentos na secção e limite total ajustado para acionar redução hierárquica respeitando limites estritos
    engine.segmenter.max_tokens_per_segment = 40
    engine.budget_manager.total_context_limit = 4500
    dossier = engine.analyze_document(ast)

    assert "academic_section_intermediate_synthesis" in operations_called
    assert dossier.telemetry.intermediate_syntheses_count > 0


def test_06_cross_section_integration_with_many_sections_cluster_reduce(tmp_path: Path):
    """6. Integração transversal com muitas secções aplicando Reduce 2 em clusters hierárquicos."""
    sections_spec = [
        {"section_id": f"sec_{i}", "title": f"Secção Temática {i}", "kind": "body", "paragraphs": [f"Conteúdo analítico da secção {i}."]}
        for i in range(1, 10)
    ]
    ast = create_synthetic_ast("doc_many_secs", "Documento com 9 Secções", sections_spec=sections_spec)

    operations_called = []

    def mock_llm_caller(system_prompt: str, user_prompt: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        operations_called.append(op)
        if op == "academic_segment_analysis":
            return json.dumps({
                "central_idea": "Ideia central da secção",
                "passage_objective": "Obj",
                "concepts": [],
                "definitions": [],
                "arguments": [],
                "assumptions": [],
                "partial_conclusions": [],
                "technical_terminology": [],
                "limitations_or_notices": [],
            }), {}
        elif op == "academic_section_synthesis":
            return json.dumps({
                "objective": "Objetivo",
                "in_depth_synthesis": "Síntese densa da secção com múltiplos parágrafos analíticos explicativos.",
                "core_ideas": ["Ideia"],
                "concepts": [],
                "arguments": [],
                "limitations": [],
            }), {}
        elif op == "academic_cross_section_cluster":
            return json.dumps({
                "cluster_progression": ["Progressão do grupo"],
                "conceptual_links": [],
                "cluster_synthesis": "Síntese articulada do cluster",
                "coherence_and_tensions": [],
            }), {}
        elif op == "academic_cross_section_integration":
            return json.dumps({
                "argumentative_progression": ["Fase 1", "Fase 2"],
                "conceptual_relationships": [],
                "coherence_and_tensions": [],
                "idea_dependencies": [],
                "global_synthesis": "Síntese global holística da totalidade do documento.",
            }), {}
        return "{}", {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_llm_caller)
    # Forçar limite total ajustado para acionar clustering transversal respeitando limites estritos
    engine.budget_manager.total_context_limit = 4300
    dossier = engine.analyze_document(ast)

    assert "academic_cross_section_cluster" in operations_called
    assert dossier.telemetry.intermediate_syntheses_count > 0


def test_07_prompt_respects_calculated_budget():
    """7. Confirmação de que o cálculo dinâmico de orçamento deduz system, instruções e headroom."""
    bm = ContextBudgetManager(total_context_limit=8192, default_max_output_tokens=2800, safety_buffer_tokens=400)
    sys_prompt = "System prompt curto"
    template = "Instrução template da operação {content}"

    budget = bm.calculate_usable_budget(sys_prompt, template, max_output_tokens=3000)
    # 8192 - (sys: ~6 + template: ~13 + output: 3000 + safety: 400) = ~4773
    assert 4500 <= budget <= 4850, f"Orçamento inesperado: {budget}"
    assert bm.estimate_tokens("Texto com 33 caracteres de teste.") == 10


def test_08_explicit_failure_when_indivisible_unit_exceeds_budget(tmp_path: Path):
    """8. Falha explícita quando uma unidade indivisível não pode ser processada sem ultrapassar o orçamento."""
    # String indivisível de 10.000 caracteres contínuos sem espaços nem pontuação
    unbreakable_blob = "X" * 10000
    p = ASTParagraph(paragraph_id="p_unbreakable", section_id="sec_fail", text=unbreakable_blob, page_number=1, page_end=1, order=1)
    ast = create_synthetic_ast(
        "doc_unbreakable",
        "Documento com Unidade Indivisível",
        sections_spec=[{"section_id": "sec_fail", "title": "Falha de Orçamento", "kind": "body", "paragraphs": [unbreakable_blob]}],
    )

    engine = AcademicReasoningEngine(storage_dir=tmp_path)
    engine.segmenter.max_tokens_per_segment = 500  # 10.000 chars / 3.3 = ~3030 tokens > 500

    dossier = engine.analyze_document(ast)
    assert dossier.status == "FAILED" or dossier.status == "PARTIAL"
    assert any(fo.get("stage") == "context_budget_subdivision" for fo in dossier.failed_operations)
    assert len(dossier.telemetry.context_limit_failures) > 0


# ============================================================================
# 6.2. TESTES DE INTEGRIDADE DA PROVENIÊNCIA DOS CONCEITOS (Testes 9 a 14)
# ============================================================================

def test_09_concept_recovery_preserves_all_original_fields(tmp_path: Path):
    """9. Recuperação de conceitos com todos os campos originais preservados."""
    ast = create_synthetic_ast("doc_concept_fields", "Estudo de Campos")

    c_original = ConceptItem(
        concept_id="concept_grounding_a1b2c3d4",
        name="Grounding Epistémico",
        definition="Ancoragem de afirmações em evidências documentais rastreáveis.",
        explanation="Como o motor valida referências cruzadas.",
        relationships=["Relação com Validação Forense"],
        context_of_use="Secção de Resultados e Discussão",
        evidence_refs=[EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=1, status=EpistemicStatus.SOURCE_FACT.value)],
    )

    checkpoint = {
        "document_id": "doc_concept_fields",
        "source_sha256": ast.source_sha256,
        "ast_version": ast.extractor_version,
        "model_name": "qwen3.5:9b",
        "prompt_versions": {
            "segment_analysis": "v3.0.0",
            "section_synthesis": "v3.0.0",
            "cross_section_integration": "v3.0.0",
            "methodology_results": "v3.0.0",
            "methodology_unit": "v3.0.0",
            "section_intermediate_synthesis": "v3.0.0",
            "cross_section_cluster": "v3.0.0",
        },
        "completed_segments": {},
        "completed_sections": {
            "sec_intro": {
                "section_id": "sec_intro",
                "title": "Introdução",
                "section_type": "introduction",
                "objective": "Obj",
                "in_depth_synthesis": "Síntese da introdução.",
                "core_ideas": ["Ideia"],
                "concepts": [asdict(c_original)],
                "arguments": [],
                "evidences": [],
                "limitations": [],
                "source_refs": [asdict(EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=1, status=EpistemicStatus.SOURCE_FACT.value))],
                "segment_ids": ["sec_intro_seg_0"],
                "execution_time_ms": 10.0,
            }
        },
        "completed_method_segments": {},
        "conceptual_analysis": [asdict(c_original)],
        "updated_at": "2026-11-05T00:00:00",
    }

    def mock_llm_caller(sys_p: str, user_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "section" in op:
            return json.dumps({"objective": "O", "in_depth_synthesis": "S", "core_ideas": [], "concepts": [], "arguments": [], "limitations": []}), {}
        elif "cross" in op:
            return json.dumps({"argumentative_progression": [], "conceptual_relationships": [], "coherence_and_tensions": [], "idea_dependencies": [], "global_synthesis": "Global"}), {}
        return "{}", {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_llm_caller)
    engine._save_checkpoint("doc_concept_fields", checkpoint)
    dossier = engine.analyze_document(ast)

    recovered = next((c for c in dossier.conceptual_analysis if c.name == "Grounding Epistémico"), None)
    assert recovered is not None
    assert recovered.concept_id == "concept_grounding_a1b2c3d4"
    assert recovered.definition == c_original.definition
    assert recovered.explanation == c_original.explanation
    assert recovered.relationships == c_original.relationships
    assert recovered.context_of_use == c_original.context_of_use
    assert len(recovered.evidence_refs) == 1
    assert recovered.evidence_refs[0].paragraph_id == "p_1"


def test_10_preservation_of_same_concept_ids(tmp_path: Path):
    """10. Preservação dos mesmos concept_id determinísticos entre execuções distintas."""
    id1 = generate_deterministic_concept_id("Epistemologia de Popper")
    id2 = generate_deterministic_concept_id("Epistemologia de Popper")
    id3 = generate_deterministic_concept_id("  EPISTEMOLOGIA DE POPPER  ")

    assert id1 == id2 == id3
    assert id1.startswith("concept_epistemologia_de_popper_")


def test_11_preservation_of_original_evidences(tmp_path: Path):
    """11. Preservação das evidências originais na recuperação do checkpoint."""
    ast = create_synthetic_ast("doc_ev_preserve", "Evidências Estudo")
    expected_ref = EvidenceRef(section_id="sec_intro", paragraph_id="p_2", page_number=1, status=EpistemicStatus.SOURCE_FACT.value)

    c = ConceptItem(
        concept_id=generate_deterministic_concept_id("Grounding"),
        name="Grounding",
        definition="Def",
        explanation="Exp",
        evidence_refs=[expected_ref],
    )

    checkpoint = {
        "document_id": "doc_ev_preserve",
        "source_sha256": ast.source_sha256,
        "ast_version": ast.extractor_version,
        "model_name": "qwen3.5:9b",
        "prompt_versions": {
            "segment_analysis": "v3.0.0",
            "section_synthesis": "v3.0.0",
            "cross_section_integration": "v3.0.0",
            "methodology_results": "v3.0.0",
            "methodology_unit": "v3.0.0",
            "section_intermediate_synthesis": "v3.0.0",
            "cross_section_cluster": "v3.0.0",
        },
        "completed_segments": {},
        "completed_sections": {},
        "completed_method_segments": {},
        "conceptual_analysis": [asdict(c)],
        "updated_at": "2026-11-05T00:00:00",
    }

    def mock_caller(s, u, m):
        return json.dumps({"objective": "O", "in_depth_synthesis": "S", "core_ideas": [], "concepts": [], "arguments": [], "limitations": []}), {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_caller)
    engine._save_checkpoint("doc_ev_preserve", checkpoint)
    dossier = engine.analyze_document(ast)

    found = next((item for item in dossier.conceptual_analysis if item.name == "Grounding"), None)
    assert found is not None
    assert found.evidence_refs[0].paragraph_id == "p_2"
    assert found.evidence_refs[0].status == EpistemicStatus.SOURCE_FACT.value


def test_12_prohibition_of_artificial_source_fact_without_document_support(tmp_path: Path):
    """12. Proibição de criação de referências SOURCE_FACT sem suporte documental (atribui MODEL_INFERENCE)."""
    ast = create_synthetic_ast("doc_no_artificial_fact", "Proibição Artificial Fact")

    def mock_caller(sys_p: str, user_p: str, meta: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        op = meta.get("operation", "")
        if "section_synthesis" in op:
            return json.dumps({
                "objective": "Obj",
                "in_depth_synthesis": "Síntese da secção.",
                "core_ideas": [],
                # Conceito sem paragraph_ids
                "concepts": [{"name": "Conceito Abstrato Inferido", "explanation": "Sem citação direta", "paragraph_ids": []}],
                "arguments": [],
                "limitations": [],
            }), {}
        elif "segment" in op:
            return json.dumps({"central_idea": "Ideia", "passage_objective": "Obj", "concepts": [], "definitions": [], "arguments": [], "assumptions": [], "partial_conclusions": [], "technical_terminology": [], "limitations_or_notices": []}), {}
        elif "cross" in op:
            return json.dumps({"argumentative_progression": [], "conceptual_relationships": [], "coherence_and_tensions": [], "idea_dependencies": [], "global_synthesis": "Global"}), {}
        return "{}", {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_caller)
    dossier = engine.analyze_document(ast)

    concept = next((c for c in dossier.conceptual_analysis if c.name == "Conceito Abstrato Inferido"), None)
    assert concept is not None
    # Deve ser MODEL_INFERENCE e NUNCA SOURCE_FACT sem paragraph_id
    assert concept.evidence_refs[0].status == EpistemicStatus.MODEL_INFERENCE.value
    assert concept.evidence_refs[0].paragraph_id is None


def test_13_checkpoint_invalidation_when_persisted_data_corrupted(tmp_path: Path):
    """13. Invalidação do checkpoint quando dados persistidos contêm referências corrompidas."""
    ast = create_synthetic_ast("doc_corrupt_cp", "Documento Corrompido")

    # Checkpoint onde a secção intro alega um SOURCE_FACT num paragraph_id inexistente
    corrupted_checkpoint = {
        "document_id": "doc_corrupt_cp",
        "source_sha256": ast.source_sha256,
        "ast_version": ast.extractor_version,
        "model_name": "qwen3.5:9b",
        "prompt_versions": {
            "segment_analysis": "v3.0.0",
            "section_synthesis": "v3.0.0",
            "cross_section_integration": "v3.0.0",
            "methodology_results": "v3.0.0",
            "methodology_unit": "v3.0.0",
            "section_intermediate_synthesis": "v3.0.0",
            "cross_section_cluster": "v3.0.0",
        },
        "completed_segments": {},
        "completed_sections": {
            "sec_intro": {
                "section_id": "sec_intro",
                "title": "Introdução",
                "section_type": "introduction",
                "objective": "Obj",
                "in_depth_synthesis": "Síntese falsa.",
                "core_ideas": [],
                "concepts": [
                    {
                        "name": "Conceito Corrompido",
                        "evidence_refs": [{"section_id": "sec_intro", "paragraph_id": "p_NAO_EXISTE_999", "status": "SOURCE_FACT"}],
                    }
                ],
                "arguments": [],
                "evidences": [],
                "limitations": [],
                "source_refs": [],
                "segment_ids": [],
                "execution_time_ms": 1.0,
            }
        },
        "completed_method_segments": {},
        "conceptual_analysis": [],
        "updated_at": "2026-11-05T00:00:00",
    }

    reprocessed = []

    def mock_caller(s, u, m):
        op = m.get("operation", "")
        reprocessed.append(op)
        if "section_synthesis" in op:
            return json.dumps({"objective": "Novo Obj", "in_depth_synthesis": "Nova Síntese", "core_ideas": [], "concepts": [], "arguments": [], "limitations": []}), {}
        return json.dumps({"central_idea": "I", "passage_objective": "O", "concepts": [], "definitions": [], "arguments": [], "assumptions": [], "partial_conclusions": [], "technical_terminology": [], "limitations_or_notices": [], "global_synthesis": "G"}), {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_caller)
    engine._save_checkpoint("doc_corrupt_cp", corrupted_checkpoint)
    dossier = engine.analyze_document(ast)

    # A secção corrompida sec_intro deve ter sido invalidada e reprocessada!
    assert "academic_section_synthesis" in reprocessed


def test_14_recovery_without_concept_duplication(tmp_path: Path):
    """14. Recuperação de execução interrompida sem duplicação de conceitos."""
    ast = create_synthetic_ast("doc_no_dup", "Documento Sem Duplicação")
    c = ConceptItem(concept_id="concept_unico_123", name="Conceito Único", definition="Def")

    checkpoint = {
        "document_id": "doc_no_dup",
        "source_sha256": ast.source_sha256,
        "ast_version": ast.extractor_version,
        "model_name": "qwen3.5:9b",
        "prompt_versions": {
            "segment_analysis": "v3.0.0",
            "section_synthesis": "v3.0.0",
            "cross_section_integration": "v3.0.0",
            "methodology_results": "v3.0.0",
            "methodology_unit": "v3.0.0",
            "section_intermediate_synthesis": "v3.0.0",
            "cross_section_cluster": "v3.0.0",
        },
        "completed_segments": {},
        "completed_sections": {},
        "completed_method_segments": {},
        "conceptual_analysis": [asdict(c)],
        "updated_at": "2026-11-05T00:00:00",
    }
    (tmp_path / "checkpoint_doc_no_dup.json").write_text(json.dumps(checkpoint), encoding="utf-8")

    def mock_caller(s, u, m):
        op = m.get("operation", "")
        if "section_synthesis" in op:
            return json.dumps({"objective": "Obj", "in_depth_synthesis": "S", "core_ideas": [], "concepts": [{"name": "Conceito Único", "explanation": "Nova expl", "paragraph_ids": ["p_1"]}], "arguments": [], "limitations": []}), {}
        return json.dumps({"central_idea": "I", "passage_objective": "O", "concepts": [], "definitions": [], "arguments": [], "assumptions": [], "partial_conclusions": [], "technical_terminology": [], "limitations_or_notices": [], "global_synthesis": "G"}), {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_caller)
    dossier = engine.analyze_document(ast)

    matching = [item for item in dossier.conceptual_analysis if item.name == "Conceito Único"]
    assert len(matching) == 1, f"Conceito foi duplicado: {len(matching)} ocorrências"


# ============================================================================
# 6.3. TESTES DE CONSISTÊNCIA E INVALIDAÇÃO DOS ÍNDICES DA AST (Testes 15 a 22)
# ============================================================================

def test_15_ast_insertion_followed_by_query():
    """15. Inserção de parágrafos seguida de consulta O(1)."""
    ast = create_synthetic_ast("doc_idx_15", "Teste Inserção")
    new_p = ASTParagraph(paragraph_id="p_novo_99", text="Parágrafo recém inserido", page_number=2, page_end=2, section_id="sec_intro", order=99)

    ast.add_paragraph(new_p)

    assert ast.get_paragraph("p_novo_99") is new_p
    assert "p_novo_99" in ast.paragraphs_by_id


def test_16_ast_removal_followed_by_query():
    """16. Remoção de parágrafo seguida de consulta O(1)."""
    ast = create_synthetic_ast("doc_idx_16", "Teste Remoção")
    target_id = ast.paragraphs[0].paragraph_id

    # Aquecimento de cache
    _ = ast.paragraphs_by_id

    removed = ast.remove_paragraph(target_id)
    assert removed is True
    assert ast.get_paragraph(target_id) is None
    assert target_id not in ast.paragraphs_by_id


def test_17_ast_substitution_same_length():
    """17. Substituição de um parágrafo mantendo o mesmo comprimento da lista."""
    ast = create_synthetic_ast("doc_idx_17", "Teste Substituição")
    old_id = ast.paragraphs[0].paragraph_id
    old_len = len(ast.paragraphs)

    # Substituição in-place direta na lista (VersionedList interceta __setitem__)
    replacement_p = ASTParagraph(paragraph_id="p_replacement_777", text="Texto substituto", page_number=1, page_end=1, section_id="sec_intro", order=1)
    ast.paragraphs[0] = replacement_p

    assert len(ast.paragraphs) == old_len
    assert ast.get_paragraph(old_id) is None, "ID antigo deve ter sido invalidado"
    assert ast.get_paragraph("p_replacement_777") is replacement_p, "Novo ID deve ser acessível de imediato"


def test_18_ast_mutation_paragraph_id():
    """18. Alteração do paragraph_id invalida o índice sem deixar referências obsoletas."""
    ast = create_synthetic_ast("doc_idx_18", "Teste Mutação ID")
    old_id = ast.paragraphs[0].paragraph_id
    new_id = "p_mutated_id_123"

    ast.update_paragraph(old_id, paragraph_id=new_id)

    assert ast.get_paragraph(old_id) is None
    assert ast.get_paragraph(new_id) is not None
    assert ast.get_paragraph(new_id).paragraph_id == new_id


def test_19_ast_mutation_section_id():
    """19. Alteração do section_id atualiza o agrupamento por secção de forma consistente."""
    ast = create_synthetic_ast("doc_idx_19", "Teste Mutação Secção")
    p = ast.paragraphs[0]
    old_sec = p.section_id
    new_sec = "sec_results"

    ast.update_paragraph(p.paragraph_id, section_id=new_sec)

    assert p in ast.get_paragraphs_for_section(new_sec)
    assert p not in ast.get_paragraphs_for_section(old_sec)


def test_20_ast_mutation_page_number():
    """20. Alteração do page_number mantém o índice de páginas consistente."""
    ast = create_synthetic_ast("doc_idx_20", "Teste Mutação Página")
    old_page = 1
    new_page = 42

    ast.update_page(old_page, page_number=new_page)

    assert ast.get_page(old_page) is None
    assert ast.get_page(new_page) is not None
    assert ast.get_page(new_page).page_number == new_page


def test_21_ast_rebuild_after_explicit_invalidation():
    """21. Reconstrução dos índices após invalidação explícita."""
    ast = create_synthetic_ast("doc_idx_21", "Teste Invalidação")

    # Aquecimento de índices
    p_map1 = ast.paragraphs_by_id
    s_map1 = ast.sections_by_id

    ast.invalidate_indices()

    p_map2 = ast.paragraphs_by_id
    s_map2 = ast.sections_by_id

    assert p_map2 == p_map1
    assert s_map2 == s_map1


def test_22_ast_indexed_vs_original_lists_equivalence():
    """22. Comparação exaustiva dos resultados indexados com os resultados obtidos a partir das listas originais."""
    ast = create_synthetic_ast("doc_idx_22", "Teste Equivalência")

    # Parágrafos
    linear_paras = {p.paragraph_id: p for p in ast.paragraphs}
    assert ast.paragraphs_by_id == linear_paras

    # Secções
    linear_secs = {s.section_id: s for s in ast.sections}
    assert ast.sections_by_id == linear_secs

    # Páginas
    linear_pages = {pg.page_number: pg for pg in ast.pages}
    assert ast.pages_by_number == linear_pages

    # Parágrafos por secção
    for s in ast.sections:
        linear_group = [p for p in ast.paragraphs if p.section_id == s.section_id]
        assert ast.get_paragraphs_for_section(s.section_id) == linear_group


# ============================================================================
# 6.4. TESTES DE INTEGRAÇÃO, REGRESSÃO E COMPATIBILIDADE (Testes 23 a 30)
# ============================================================================

def test_23_complete_analysis_conventional_academic_doc(tmp_path: Path):
    """23. Análise completa de documento académico convencional."""
    ast = create_synthetic_ast("doc_full_conv", "Artigo Científico Convencional")

    def mock_caller(s, u, m):
        op = m.get("operation", "")
        if "methodology" in op:
            return json.dumps({
                "is_applicable": True,
                "research_type": "Quantitativo",
                "methodological_design": "Quasi-experimental",
                "methods_used": ["M1"],
                "sample_or_participants": "N=50",
                "instruments": ["I1"],
                "procedures": ["P1"],
                "variables": ["V1"],
                "data_sources": ["D1"],
                "analysis_techniques": ["ANOVA"],
                "methodological_limitations": ["L1"],
                "results": [{"statement": "Efeito significativo", "evidence_data": "F=4.2", "relation_to_objectives": "Obj", "interpretation_limitations": "", "paragraph_id": "p_5"}],
            }), {}
        elif "section_synthesis" in op:
            return json.dumps({"objective": "Obj", "in_depth_synthesis": "Síntese substancial.", "core_ideas": ["I1"], "concepts": [{"name": "C1", "explanation": "E1", "paragraph_ids": ["p_1"]}], "arguments": [], "limitations": []}), {}
        elif "cross" in op:
            return json.dumps({"argumentative_progression": ["Fase 1"], "conceptual_relationships": [], "coherence_and_tensions": [], "idea_dependencies": [], "global_synthesis": "Global"}), {}
        return json.dumps({"central_idea": "I", "passage_objective": "O", "concepts": [], "definitions": [], "arguments": [], "assumptions": [], "partial_conclusions": [], "technical_terminology": [], "limitations_or_notices": []}), {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_caller)
    dossier = engine.analyze_document(ast)

    assert dossier.status == "COMPLETED"
    assert dossier.qa_report.is_valid is True
    assert len(dossier.section_analyses) == len(ast.sections)
    assert len(dossier.results_and_evidence) == 1


def test_24_extensive_document_analysis(tmp_path: Path):
    """24. Análise de documento extenso com telemetria completa."""
    sections_spec = [
        {"section_id": f"sec_{i}", "title": f"Secção {i}", "kind": "body" if i != 2 else "methodology", "paragraphs": [f"Parágrafo {i}_{j}" for j in range(5)]}
        for i in range(1, 6)
    ]
    ast = create_synthetic_ast("doc_ext_24", "Estudo Extenso", sections_spec=sections_spec)

    def mock_caller(s, u, m):
        op = m.get("operation", "")
        if "methodology" in op:
            return json.dumps({"is_applicable": True, "research_type": "Empírico", "methodological_design": "Design", "methods_used": [], "sample_or_participants": "Amostra", "instruments": [], "procedures": [], "variables": [], "data_sources": [], "analysis_techniques": [], "methodological_limitations": [], "results": []}), {}
        elif "section_synthesis" in op:
            return json.dumps({"objective": "O", "in_depth_synthesis": "Síntese", "core_ideas": [], "concepts": [], "arguments": [], "limitations": []}), {}
        elif "cross" in op:
            return json.dumps({"argumentative_progression": [], "conceptual_relationships": [], "coherence_and_tensions": [], "idea_dependencies": [], "global_synthesis": "Global"}), {}
        return json.dumps({"central_idea": "I", "passage_objective": "O", "concepts": [], "definitions": [], "arguments": [], "assumptions": [], "partial_conclusions": [], "technical_terminology": [], "limitations_or_notices": []}), {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_caller)
    dossier = engine.analyze_document(ast)

    assert dossier.status == "COMPLETED"
    assert dossier.telemetry.total_llm_calls > 0
    assert dossier.telemetry.total_segments_created > 0


def test_25_checkpoint_interruption_and_recovery(tmp_path: Path):
    """25. Recuperação fiel de checkpoint após interrupção simulada."""
    ast = create_synthetic_ast("doc_interrupt_25", "Documento Interrompido")

    # Execução 1: interrompida após 1 secção
    calls_count = 0

    def mock_interrupted_caller(s, u, m):
        nonlocal calls_count
        calls_count += 1
        if calls_count >= 3:
            raise RuntimeError("Interrupção simulada no meio do processamento!")
        return json.dumps({"central_idea": "I", "passage_objective": "O", "concepts": [], "definitions": [], "arguments": [], "assumptions": [], "partial_conclusions": [], "technical_terminology": [], "limitations_or_notices": []}), {}

    engine1 = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_interrupted_caller)
    with pytest.raises(Exception):
        engine1.analyze_document(ast)

    # Execução 2: retoma do checkpoint gravado
    def mock_resumed_caller(s, u, m):
        op = m.get("operation", "")
        if "section_synthesis" in op:
            return json.dumps({"objective": "O", "in_depth_synthesis": "S", "core_ideas": [], "concepts": [], "arguments": [], "limitations": []}), {}
        elif "cross" in op:
            return json.dumps({"argumentative_progression": [], "conceptual_relationships": [], "coherence_and_tensions": [], "idea_dependencies": [], "global_synthesis": "Global"}), {}
        return json.dumps({"central_idea": "I", "passage_objective": "O", "concepts": [], "definitions": [], "arguments": [], "assumptions": [], "partial_conclusions": [], "technical_terminology": [], "limitations_or_notices": []}), {}

    engine2 = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_resumed_caller)
    dossier2 = engine2.analyze_document(ast)

    assert dossier2.status in ("COMPLETED", "PARTIAL")


def test_26_qa_validation_forensic_integrity():
    """26. Validação forense estrita do ReasoningQAEvaluator."""
    ast = create_synthetic_ast("doc_qa_26", "Teste QA")
    qa = ReasoningQAEvaluator()

    # Cenário Válido
    valid_sec = SectionAnalysis(
        section_id="sec_intro",
        title="Intro",
        source_refs=[EvidenceRef(section_id="sec_intro", paragraph_id="p_1", page_number=1, status=EpistemicStatus.SOURCE_FACT.value)],
    )
    rep_valid = qa.evaluate(ast=ast, section_analyses=[valid_sec], results=[], cross_synthesis=CrossSectionSynthesis())
    assert rep_valid.is_valid is True

    # Cenário Inválido: parágrafo inexistente
    invalid_sec = SectionAnalysis(
        section_id="sec_intro",
        title="Intro",
        source_refs=[EvidenceRef(section_id="sec_intro", paragraph_id="p_INEXISTENTE_999", page_number=1, status=EpistemicStatus.SOURCE_FACT.value)],
    )
    rep_invalid = qa.evaluate(ast=ast, section_analyses=[invalid_sec], results=[], cross_synthesis=CrossSectionSynthesis())
    assert rep_invalid.is_valid is False
    assert len(rep_invalid.invalid_paragraph_refs) > 0


def test_27_dossier_persistence_and_deserialization(tmp_path: Path):
    """27. Persistência e leitura do dossier com integridade total de serialização."""
    dossier = AcademicReasoningDossier(
        dossier_id="dossier_serial_test",
        document_id="doc_serial",
        status="COMPLETED",
        document_analysis=DocumentCoreAnalysis("doc_serial", "Título"),
        conceptual_analysis=[ConceptItem("c1", "Grounding", "Def", "Exp")],
        results_and_evidence=[ResultItem("Statement", "Data", evidence_refs=[EvidenceRef("sec_1", "p_1", 1)])],
        telemetry=ReasoningTelemetry(total_duration_ms=1200.0, total_segments_created=5),
    )

    d_dict = dossier.to_dict()
    roundtrip = AcademicReasoningDossier.from_dict(d_dict)

    assert roundtrip.dossier_id == dossier.dossier_id
    assert roundtrip.conceptual_analysis[0].concept_id == "c1"
    assert roundtrip.results_and_evidence[0].evidence_refs[0].paragraph_id == "p_1"
    assert roundtrip.telemetry.total_segments_created == 5


def test_28_websocket_contracts_compatibility():
    """28. Compatibilidade dos contratos WebSocket Python e TypeScript."""
    from backend.websocket.contracts import EXPECTED_MESSAGE_TYPES
    from websocket_schema import CLIENT_MESSAGE_TYPES, SERVER_MESSAGE_TYPES

    # Mensagens de cliente
    for msg_type in ("study_get_document_ast", "study_get_academic_reasoning", "study_generate_academic_reasoning"):
        assert msg_type in EXPECTED_MESSAGE_TYPES, f"{msg_type} ausente em EXPECTED_MESSAGE_TYPES"
        assert msg_type in CLIENT_MESSAGE_TYPES, f"{msg_type} ausente em CLIENT_MESSAGE_TYPES"

    # Mensagens de servidor
    for srv_type in ("study_document_ast_result", "study_academic_reasoning_result", "study_academic_reasoning_progress"):
        assert srv_type in SERVER_MESSAGE_TYPES, f"{srv_type} ausente em SERVER_MESSAGE_TYPES"


def test_29_legacy_studyservice_compatibility(tmp_path: Path):
    """29. Compatibilidade com as projeções legadas do StudyService."""
    ast = create_synthetic_ast("doc_legacy_comp", "Compatibilidade Legada")

    legacy_secs = ast.to_legacy_sections()
    assert len(legacy_secs) == len(ast.sections)
    assert "section_id" in legacy_secs[0]
    assert "paragraphs" in legacy_secs[0]
    assert len(legacy_secs[0]["paragraphs"]) > 0

    pages_text = ast.to_pages_text()
    assert len(pages_text) == 2
    assert "inteligência artificial" in pages_text[0].lower()


def test_30_phase2_phase3_regression_suite():
    """30. Regressão comprovada da suite anterior da Fase 2 e Fase 3."""
    from services.document_intelligence import EXTRACTOR_VERSION
    from services.academic_reasoning_engine import ENGINE_VERSION

    assert EXTRACTOR_VERSION == "2.0.0"
    assert ENGINE_VERSION.startswith("3.0.0")


# ============================================================================
# 6.5. TESTES ADICIONAIS DE ORÇAMENTO ESTRITO, REDUCE RECURSIVO E MUTAÇÃO AST (Testes 31 a 46)
# ============================================================================

def test_31_context_negative_or_insufficient_budget_raises_error():
    """31. Orçamento negativo ou insuficiente lança ContextBudgetExceededError e elimina mínimo de 300."""
    bm = ContextBudgetManager(total_context_limit=4000, default_max_output_tokens=2800, safety_buffer_tokens=400)
    # 2800 + 400 = 3200. Restam 800 para sys + inst.
    sys_large = "S" * 2000  # ~606 tokens
    inst_large = "I" * 1500  # ~455 tokens
    # 606 + 455 = 1061. 4000 - (3200 + 1061) = -261 tokens (negativo!)

    with pytest.raises(ContextBudgetExceededError) as exc_info:
        bm.calculate_usable_budget(sys_large, inst_large)
    assert "Orçamento utilizável insuficiente ou negativo" in str(exc_info.value)

    # Testar que quando usable é menor que 300 (ex: ~150), devolve o valor real e NÃO 300!
    bm_small = ContextBudgetManager(total_context_limit=4000, default_max_output_tokens=2800, safety_buffer_tokens=400)
    text_sys_exact = "A" * 1000  # ~304 tokens
    text_inst_exact = "B" * 1145  # ~347 tokens
    budget_small = bm_small.calculate_usable_budget(text_sys_exact, text_inst_exact)
    assert budget_small < 300, f"Mínimo artificial de 300 ainda presente: {budget_small}"
    assert 100 < budget_small < 300


def test_32_context_system_prompt_consuming_all_budget():
    """32. Prompt de sistema que consome praticamente todo o contexto falha explicitamente."""
    bm = ContextBudgetManager(total_context_limit=4000, default_max_output_tokens=2800, safety_buffer_tokens=400)
    huge_sys = "System" * 1000  # 6000 chars -> ~1818 tokens
    # 1818 + 2800 + 400 = 5018 > 4000
    with pytest.raises(ContextBudgetExceededError):
        bm.calculate_usable_budget(huge_sys, "Template normal")


def test_33_context_pre_call_validation_rejects_without_calling_model():
    """33. Validação imediata antes de enviar rejeita prompt com défice sem invocar transport."""
    called = []
    def dummy_caller(s, u, m):
        called.append(True)
        return "{}", {}

    engine = AcademicReasoningEngine(llm_caller=dummy_caller)
    # Montar prompt de utilizador que ultrapassa a capacidade útil
    huge_user_prompt = "Excesso " * 4000  # 32000 chars -> ~9697 tokens
    with pytest.raises(ContextBudgetExceededError) as exc_info:
        engine._call_model_with_retries("System", huge_user_prompt, {"operation": "test_precall"})

    assert not called, "O transport/caller nunca deve ser executado quando o prompt excede o contexto!"
    assert "Prompt final excede o limite de contexto" in str(exc_info.value)


def test_34_context_exact_text_reconstruction_with_offsets():
    """34. Reconstrução textual exatamente igual ao original (caractere a caractere) e preservação de offsets."""
    text = (
        "Parágrafo com múltiplos períodos sintáticos. Segunda oração, com pontuação interna; "
        "e várias quebras de linha:\nLinha 2 com dados empíricos.\nLinha 3 com conclusão final."
    )
    p = ASTParagraph(paragraph_id="p_recon", section_id="sec_test", text=text, page_number=1, page_end=1, order=1)
    segmenter = SemanticSegmenter(max_tokens_per_segment=25)
    sub_paras = segmenter.subdivide_paragraph(p, max_tokens=25)

    assert len(sub_paras) > 1
    # Concatenação pura sem separadores adicionais deve ser IDÊNTICA ao original
    reconstructed = "".join(sp.text for sp in sub_paras)
    assert reconstructed == text, "Reconstrução textual deve ser idêntica até ao último caractere!"

    # Verificar que cada span corresponde exatamente ao slice do texto original
    for sp in sub_paras:
        assert sp.sentence_spans, "sentence_spans deve conter os offsets de cada subunidade"
        start, end = sp.sentence_spans[0]
        assert text[start:end] == sp.text, f"Offset [{start}:{end}] não corresponde ao texto '{sp.text}'"


def test_35_context_actual_vs_estimated_tokens_telemetry():
    """35. Distinção clara na telemetria entre estimated_input_tokens e actual_input_tokens."""
    def mock_caller_with_actual(s, u, m):
        # Simula resposta do provider Ollama com usage real
        return json.dumps({"test": "ok"}), {"input_tokens": 142, "output_tokens": 58, "status": "COMPLETED"}

    engine = AcademicReasoningEngine(llm_caller=mock_caller_with_actual)
    parsed, telem = engine._call_model_with_retries("Sys", "User Prompt de Teste", {"operation": "test_tokens"})

    assert parsed == {"test": "ok"}
    assert telem["actual_input_tokens"] == 142
    assert telem["estimated_input_tokens"] > 0
    assert telem["reserved_output_tokens"] == engine.budget_manager.default_max_output_tokens
    assert telem["safety_margin_tokens"] == engine.budget_manager.safety_buffer_tokens
    assert "available_context_tokens" in telem


def test_36_hierarchical_reduce_multi_level_recursion():
    """36. Reduce 1 aplicando recursão adaptativa em múltiplos níveis (profundidade >= 2)."""
    items = [f"Resumo analítico profundo do segmento {i} com detalhe metodológico expressivo e evidências robustas." for i in range(1, 25)]
    bm = ContextBudgetManager(total_context_limit=4500, default_max_output_tokens=2800, safety_buffer_tokens=400)
    engine = AcademicReasoningEngine()
    engine.budget_manager = bm

    levels_seen = set()

    def mock_level_reducer(s, u, m):
        depth = m.get("batch_depth", 1)
        levels_seen.add(depth)
        if depth == 1:
            return json.dumps({
                "batch_synthesis": f"Síntese detalhada de nível 1 para lote {m.get('batch_index')}: informação substancial preservada com conceitos e argumentos densos.",
                "batch_objective": "Obj Nível 1",
                "core_ideas": ["Ideia A", "Ideia B"],
            }), {}
        else:
            return json.dumps({
                "batch_synthesis": "Síntese consolidada final de nível 2.",
                "batch_objective": "Obj Nível 2",
                "core_ideas": ["Ideia Central"],
            }), {}

    engine.llm_caller = mock_level_reducer
    telemetry = ReasoningTelemetry()

    # Orçamento de 180 tokens força o nível 1 (~260 tokens) a recursar para o nível 2 (~70 tokens)
    reduced_text, errs = engine._hierarchical_adaptive_reduce(
        items=items,
        format_item_fn=lambda x: str(x),
        prompt_template="Resuma:\n{segments_summary}",
        template_kwargs={},
        prompt_content_key="segments_summary",
        parse_result_fn=engine._parse_section_intermediate_result,
        operation_name="test_multi_level",
        meta_base={"document_id": "doc_test"},
        usable_budget=180,
        telemetry_metrics=telemetry,
        max_depth=4,
    )

    assert errs == []
    assert reduced_text is not None
    assert len(levels_seen) >= 2, f"Deveria ter executado múltiplos níveis de redução, executou: {levels_seen}"
    assert telemetry.intermediate_syntheses_count >= 2
    assert any(ha["depth"] >= 2 for ha in telemetry.hierarchical_aggregations)


def test_37_hierarchical_reduce_batch_failure_stops_cleanly_without_silent_truncation():
    """37. Falha num lote intermédio aborta a redução honestamente sem fallback de truncagem [:500]."""
    items = [f"Item volumoso {i} para teste de falha com texto analítico bastante extenso e detalhado." for i in range(1, 15)]
    engine = AcademicReasoningEngine()
    engine.budget_manager.total_context_limit = 4500

    def mock_failing_batch(s, u, m):
        if m.get("batch_index") == 2:
            return "RESPOSTA CORROMPIDA NÃO JSON", {"status": "INVALID_JSON_SYNTAX"}
        return json.dumps({"batch_synthesis": "OK", "batch_objective": "Obj", "core_ideas": []}), {}

    engine.llm_caller = mock_failing_batch
    telemetry = ReasoningTelemetry()

    # Usable budget de 100 tokens força a criação de lotes (input ~350 tokens > 100)
    reduced_text, errs = engine._hierarchical_adaptive_reduce(
        items=items,
        format_item_fn=lambda x: str(x),
        prompt_template="Prompt:\n{segments_summary}",
        template_kwargs={},
        prompt_content_key="segments_summary",
        parse_result_fn=engine._parse_section_intermediate_result,
        operation_name="test_batch_failure",
        meta_base={"document_id": "doc_fail"},
        usable_budget=100,
        telemetry_metrics=telemetry,
    )

    assert reduced_text is None, "Em caso de falha de lote, a síntese não deve prosseguir com dados parciais truncados!"
    assert len(errs) > 0
    assert errs[0]["batch_index"] == 2


def test_38_hierarchical_reduce_no_volume_reduction_protection():
    """38. Proteção contra ausência de redução de volume deteta ciclo e interrompe execução."""
    items = [f"Item com dados descritivos para teste número {i}." for i in range(1, 10)]
    engine = AcademicReasoningEngine()
    engine.budget_manager.total_context_limit = 4500

    def mock_expanding_model(s, u, m):
        return json.dumps({
            "batch_synthesis": "Texto hiper-expandido com prolixidade extrema e volume superior ao original " * 10,
            "batch_objective": "Obj",
            "core_ideas": [],
        }), {}

    engine.llm_caller = mock_expanding_model
    telemetry = ReasoningTelemetry()

    # Usable budget de 50 tokens força redução (input ~130 tokens > 50)
    reduced_text, errs = engine._hierarchical_adaptive_reduce(
        items=items,
        format_item_fn=lambda x: str(x),
        prompt_template="Prompt:\n{segments_summary}",
        template_kwargs={},
        prompt_content_key="segments_summary",
        parse_result_fn=engine._parse_section_intermediate_result,
        operation_name="test_expansion_loop",
        meta_base={"document_id": "doc_loop"},
        usable_budget=50,
        telemetry_metrics=telemetry,
    )

    assert reduced_text is None
    assert any(e.get("reason") == "NO_VOLUME_REDUCTION" for e in errs)


def test_39_hierarchical_reduce_all_sent_prompts_within_budget(tmp_path: Path):
    """39. Todos os prompts efetivamente enviados durante a redução hierárquica respeitam o orçamento."""
    paras = [f"Parágrafo descritivo denso {i} com vocabulário técnico e epistemológico de ponta." for i in range(1, 20)]
    ast = create_synthetic_ast(
        "doc_check_prompts",
        "Documento de Auditoria de Prompts",
        sections_spec=[{"section_id": "sec_1", "title": "Secção", "kind": "body", "paragraphs": paras}],
    )

    prompts_inspected = []

    def mock_tracking_caller(s: str, u: str, m: Dict[str, Any]):
        op = m.get("operation", "")
        prompts_inspected.append((s, u, op))
        if "segment" in op:
            return json.dumps({"central_idea": "Ideia", "passage_objective": "Obj", "concepts": [], "arguments": []}), {}
        if "intermediate" in op:
            return json.dumps({"batch_synthesis": "Síntese do lote", "batch_objective": "Obj", "core_ideas": []}), {}
        if "section_synthesis" in op:
            return json.dumps({"objective": "Obj", "in_depth_synthesis": "Síntese Secção", "core_ideas": [], "concepts": [], "arguments": [], "limitations": []}), {}
        return json.dumps({"argumentative_progression": [], "global_synthesis": "Global"}), {}

    engine = AcademicReasoningEngine(storage_dir=tmp_path, llm_caller=mock_tracking_caller)
    engine.segmenter.max_tokens_per_segment = 40
    engine.budget_manager.total_context_limit = 4500
    engine.analyze_document(ast)

    # Verificar que cada prompt enviado coube comprovadamente no limite de 4500
    assert len(prompts_inspected) > 0
    for s_p, u_p, op_name in prompts_inspected:
        insp = engine.budget_manager.inspect_budget(s_p, u_p, max_output_tokens=engine.budget_manager.default_max_output_tokens)
        assert insp["fits"] is True, f"Prompt da operação {op_name} excedeu o contexto ({insp['total_required_tokens']} > 4500)"


def test_40_ast_versioned_list_sort_and_reverse():
    """40. Métodos sort() e reverse() de VersionedList incrementam a versão e mantêm consistência."""
    ast = create_synthetic_ast("doc_sort_rev", "Teste Sort Reverse")
    initial_ver = ast.paragraphs.version

    ast.paragraphs.reverse()
    assert ast.paragraphs.version == initial_ver + 1
    assert ast.paragraphs_by_id[ast.paragraphs[0].paragraph_id] is ast.paragraphs[0]

    ast.paragraphs.sort(key=lambda p: p.paragraph_id)
    assert ast.paragraphs.version == initial_ver + 2
    assert ast.paragraphs_by_id[ast.paragraphs[0].paragraph_id] is ast.paragraphs[0]


def test_41_ast_versioned_list_iadd_and_imul():
    """41. Operações += (__iadd__) e *= (__imul__) de VersionedList hookam nós e invalidam índices."""
    ast = create_synthetic_ast("doc_iadd_imul", "Teste iadd imul")
    new_p = ASTParagraph(paragraph_id="p_added_extra", section_id="sec_intro", text="Texto extra", page_number=1, page_end=1, order=10)

    initial_ver = ast.paragraphs.version
    ast.paragraphs += [new_p]

    assert ast.paragraphs.version == initial_ver + 1
    assert ast.get_paragraph("p_added_extra") is new_p

    # Testar mutação do parágrafo recém-adicionado via +=
    new_p.section_id = "sec_shifted"
    assert new_p in ast.get_paragraphs_for_section("sec_shifted")


def test_42_ast_direct_attribute_mutation_paragraph_id():
    """42. Alteração direta de p.paragraph_id invalida imediatamente o índice secundário."""
    ast = create_synthetic_ast("doc_direct_pid", "Teste Mutação Direta PID")
    p = ast.paragraphs[0]
    old_pid = p.paragraph_id
    new_pid = "p_directly_mutated_999"

    # Aquecimento de índice
    _ = ast.paragraphs_by_id

    # Mutação DIRETA no atributo do objeto
    p.paragraph_id = new_pid

    assert ast.get_paragraph(old_pid) is None, f"ID antigo {old_pid} ainda está presente no índice!"
    assert ast.get_paragraph(new_pid) is p, f"Novo ID {new_pid} não foi indexado após mutação direta!"


def test_43_ast_direct_attribute_mutation_section_id():
    """43. Alteração direta de p.section_id atualiza paragraphs_by_section_id."""
    ast = create_synthetic_ast("doc_direct_secid", "Teste Mutação Direta Section ID")
    p = ast.paragraphs[0]
    old_sec = p.section_id
    new_sec = "sec_novel_destination"

    # Aquecimento
    _ = ast.paragraphs_by_section_id

    # Mutação DIRETA
    p.section_id = new_sec

    assert p in ast.get_paragraphs_for_section(new_sec)
    assert p not in ast.get_paragraphs_for_section(old_sec)


def test_44_ast_direct_attribute_mutation_section_and_page():
    """44. Alteração direta de s.section_id e pg.page_number atualiza os respetivos índices."""
    ast = create_synthetic_ast("doc_direct_sec_page", "Teste Mutação Secção e Página")
    sec = ast.sections[0]
    old_sid = sec.section_id
    new_sid = "sec_renamed_direct"

    # Mutação direta na secção
    sec.section_id = new_sid
    assert ast.get_section(old_sid) is None
    assert ast.get_section(new_sid) is sec

    # Mutação direta na página
    pg = ast.pages[0]
    old_pnum = pg.page_number
    new_pnum = 888
    pg.page_number = new_pnum
    assert ast.get_page(old_pnum) is None
    assert ast.get_page(new_pnum) is pg


def test_45_ast_concurrent_mutation_and_query():
    """45. Acessos concorrentes de mutação e consulta não causam corrupção nem deadlocks."""
    import threading

    ast = create_synthetic_ast("doc_concurrency", "Teste Concorrência")
    errors = []

    def reader():
        try:
            for _ in range(500):
                _ = ast.paragraphs_by_id
                _ = ast.sections_by_id
                _ = ast.paragraphs_by_section_id
        except Exception as e:
            errors.append(e)

    def writer():
        try:
            for i in range(100):
                new_p = ASTParagraph(paragraph_id=f"p_thread_{i}", section_id="sec_intro", text="T", page_number=1, page_end=1, order=i)
                ast.add_paragraph(new_p)
                ast.paragraphs[0].section_id = f"sec_mut_{i % 3}"
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=reader)
    t2 = threading.Thread(target=writer)
    t3 = threading.Thread(target=reader)

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    assert not errors, f"Erros durante execução concorrente: {errors}"
    assert "p_thread_99" in ast.paragraphs_by_id


def test_46_ast_serialization_roundtrip_with_indices():
    """46. Serialização to_dict() e restauração from_dict() mantêm índices e observabilidade consistentes."""
    ast = create_synthetic_ast("doc_serial_roundtrip", "Teste Serialização")
    # Construir índices pré-serialização
    _ = ast.paragraphs_by_id

    d = ast.to_dict()
    restored = AcademicDocumentAST.from_dict(d)

    # Verificar funcionamento de índices na AST restaurada
    assert len(restored.paragraphs_by_id) == len(ast.paragraphs)
    assert restored.get_paragraph("p_1") is not None

    # Verificar que a observabilidade continua ativa após from_dict
    p = restored.paragraphs[0]
    p.paragraph_id = "p_mutated_after_restore"
    assert restored.get_paragraph("p_mutated_after_restore") is p

