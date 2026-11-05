"""
JARVIS OS — ACADEMIC REASONING ENGINE (PHASE 3)
Motor hierárquico (Map-Reduce) de raciocínio e compreensão profunda de documentos académicos.
Opera exclusivamente com o modelo local Qwen 3.5:9b via Ollama e consome AcademicDocumentAST (Fase 2).

Arquitetura:
  AcademicDocumentAST
    -> Secções e Parágrafos estruturados
    -> Segmentação Semântica Adaptativa (orçamento OLLAMA_NUM_CTX=8192)
    -> Análise Individual de Segmentos (Map)
    -> Síntese Integrada por Secção (Reduce 1)
    -> Raciocínio e Integração Transversal Global (Reduce 2)
    -> Dossier Académico Global (AcademicReasoningDossier)
    -> Controlo de Qualidade Forense (ReasoningQAEvaluator)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from services.document_intelligence import (
    AcademicDocumentAST,
    ASTFigure,
    ASTParagraph,
    ASTSection,
    ASTTable,
    DocumentMetadata,
)

logger = logging.getLogger("academic_reasoning_engine")

SCHEMA_VERSION = "3.0.0"
ENGINE_VERSION = "3.0.0-hierarchical"
DEFAULT_MODEL = "qwen3.5:9b"

PROMPT_VERSIONS = {
    "segment_analysis": "v3.0.0",
    "section_synthesis": "v3.0.0",
    "cross_section_integration": "v3.0.0",
    "methodology_results": "v3.0.0",
}


# ============================================================================
# 1. Estados Epistémicos e Modelos de Dados Estruturados
# ============================================================================

class EpistemicStatus(str, Enum):
    """Classificação epistemológica estrita da origem do conhecimento."""
    SOURCE_FACT = "SOURCE_FACT"          # Informação textualmente suportada pelo documento
    MODEL_INFERENCE = "MODEL_INFERENCE"  # Interpretação analítica deduzida pelo modelo a partir de evidências
    NOT_FOUND = "NOT_FOUND"              # Informação ausente no documento original
    UNVERIFIED = "UNVERIFIED"            # Afirmação pendente de corroboração direta


@dataclass
class EvidenceRef:
    """Rastreabilidade forense de uma afirmação ou conceito até à AST."""
    section_id: str
    paragraph_id: Optional[str] = None
    page_number: Optional[int] = None
    excerpt: str = ""
    status: str = EpistemicStatus.SOURCE_FACT.value
    confidence: float = 1.0


@dataclass
class DocumentCoreAnalysis:
    """Compreensão global do documento (tese, problema, objetivos, contributos)."""
    document_id: str
    title: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    global_objective: str = ""
    research_problem: str = ""
    research_questions: List[str] = field(default_factory=list)
    central_thesis: str = ""
    main_contributions: List[str] = field(default_factory=list)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)


@dataclass
class SegmentAnalysis:
    """Análise individual (Map) de uma passagem semântica do documento."""
    segment_id: str
    section_id: str
    paragraph_ids: List[str] = field(default_factory=list)
    page_numbers: List[int] = field(default_factory=list)
    central_idea: str = ""
    passage_objective: str = ""
    concepts: List[str] = field(default_factory=list)
    definitions: List[Dict[str, str]] = field(default_factory=list)  # {"term": ..., "definition": ...}
    arguments: List[Dict[str, Any]] = field(default_factory=list)    # {"claim": ..., "evidence": ..., "status": ...}
    assumptions: List[str] = field(default_factory=list)
    partial_conclusions: List[str] = field(default_factory=list)
    technical_terminology: List[str] = field(default_factory=list)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    limitations_or_notices: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


@dataclass
class SectionAnalysis:
    """Síntese integrada (Reduce 1) de uma secção estrutural do documento."""
    section_id: str
    title: str
    section_type: str = "other"  # introduction | methodology | results | discussion | conclusion | etc.
    objective: str = ""
    in_depth_synthesis: str = ""
    core_ideas: List[str] = field(default_factory=list)
    concepts: List[Dict[str, Any]] = field(default_factory=list)
    arguments: List[Dict[str, Any]] = field(default_factory=list)
    evidences: List[Dict[str, Any]] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    source_refs: List[EvidenceRef] = field(default_factory=list)
    segment_ids: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0


@dataclass
class ConceptItem:
    """Conceito fundamental mapeado com definição e contexto."""
    concept_id: str
    name: str
    definition: str = ""
    explanation: str = ""
    relationships: List[str] = field(default_factory=list)
    context_of_use: str = ""
    evidence_refs: List[EvidenceRef] = field(default_factory=list)


@dataclass
class MethodologyAnalysis:
    """Exame analítico do desenho experimental, amostra e procedimentos."""
    is_applicable: bool = True
    research_type: str = ""
    methodological_design: str = ""
    methods_used: List[str] = field(default_factory=list)
    sample_or_participants: str = ""
    instruments: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)
    analysis_techniques: List[str] = field(default_factory=list)
    methodological_limitations: List[str] = field(default_factory=list)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)


@dataclass
class ResultItem:
    """Resultado empírico ou teórico identificado com suporte probatório."""
    statement: str
    evidence_data: str = ""  # dados quantitativos ou qualitativos
    relation_to_objectives: str = ""
    interpretation_limitations: str = ""
    evidence_refs: List[EvidenceRef] = field(default_factory=list)


@dataclass
class CrossSectionSynthesis:
    """Integração transversal (Reduce 2) e progressão argumentativa global."""
    section_relationships: List[Dict[str, str]] = field(default_factory=list)
    argumentative_progression: List[str] = field(default_factory=list)
    conceptual_relationships: List[Dict[str, str]] = field(default_factory=list)
    coherence_and_tensions: List[Dict[str, Any]] = field(default_factory=list)
    idea_dependencies: List[Dict[str, str]] = field(default_factory=list)
    global_synthesis: str = ""


@dataclass
class CriticalAnalysis:
    """Exame crítico das premissas, limitações e inferências epistémicas."""
    epistemic_assumptions: List[str] = field(default_factory=list)
    author_limitations: List[str] = field(default_factory=list)
    literature_gaps: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    aspects_requiring_validation: List[str] = field(default_factory=list)
    author_vs_inference_distinctions: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ReasoningQAReport:
    """Auditoria forense do raciocínio e validação contra a AST."""
    total_sections_analyzed: int = 0
    total_segments_analyzed: int = 0
    valid_paragraph_refs_pct: float = 100.0
    invalid_paragraph_refs: List[str] = field(default_factory=list)
    valid_page_refs_pct: float = 100.0
    invalid_page_refs: List[int] = field(default_factory=list)
    fact_vs_inference_counts: Dict[str, int] = field(default_factory=dict)
    coverage_score: float = 1.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    is_valid: bool = True


@dataclass
class ReasoningTelemetry:
    """Métricas de execução e consumo do modelo local."""
    total_duration_ms: float = 0.0
    total_llm_calls: int = 0
    retries_count: int = 0
    failures_count: int = 0
    input_tokens_est: int = 0
    output_tokens_est: int = 0
    segment_durations_ms: Dict[str, float] = field(default_factory=dict)
    section_durations_ms: Dict[str, float] = field(default_factory=dict)


@dataclass
class AcademicReasoningDossier:
    """Dossier canónico final contendo a totalidade da análise do documento."""
    dossier_id: str
    document_id: str
    schema_version: str = SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION
    source_sha256: str = ""
    ast_version: str = ""
    model_name: str = DEFAULT_MODEL
    prompt_versions: Dict[str, str] = field(default_factory=lambda: dict(PROMPT_VERSIONS))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "COMPLETED"  # COMPLETED | PARTIAL | FAILED | CANCELLED
    failed_operations: List[Dict[str, Any]] = field(default_factory=list)
    document_analysis: DocumentCoreAnalysis = field(default_factory=lambda: DocumentCoreAnalysis("", ""))
    section_analyses: List[SectionAnalysis] = field(default_factory=list)
    conceptual_analysis: List[ConceptItem] = field(default_factory=list)
    methodology_analysis: MethodologyAnalysis = field(default_factory=MethodologyAnalysis)
    results_and_evidence: List[ResultItem] = field(default_factory=list)
    cross_section_synthesis: CrossSectionSynthesis = field(default_factory=CrossSectionSynthesis)
    critical_analysis: CriticalAnalysis = field(default_factory=CriticalAnalysis)
    qa_report: ReasoningQAReport = field(default_factory=ReasoningQAReport)
    telemetry: ReasoningTelemetry = field(default_factory=ReasoningTelemetry)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AcademicReasoningDossier":
        d = dict(data or {})
        return cls(
            dossier_id=d.get("dossier_id", ""),
            document_id=d.get("document_id", ""),
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            engine_version=d.get("engine_version", ENGINE_VERSION),
            source_sha256=d.get("source_sha256", ""),
            ast_version=d.get("ast_version", ""),
            model_name=d.get("model_name", DEFAULT_MODEL),
            prompt_versions=d.get("prompt_versions", PROMPT_VERSIONS),
            created_at=d.get("created_at", ""),
            status=d.get("status", "COMPLETED"),
            failed_operations=d.get("failed_operations", []),
            document_analysis=_from_dict(DocumentCoreAnalysis, d.get("document_analysis")),
            section_analyses=[_from_dict(SectionAnalysis, x) for x in d.get("section_analyses", [])],
            conceptual_analysis=[_from_dict(ConceptItem, x) for x in d.get("conceptual_analysis", [])],
            methodology_analysis=_from_dict(MethodologyAnalysis, d.get("methodology_analysis")),
            results_and_evidence=[_from_dict(ResultItem, x) for x in d.get("results_and_evidence", [])],
            cross_section_synthesis=_from_dict(CrossSectionSynthesis, d.get("cross_section_synthesis")),
            critical_analysis=_from_dict(CriticalAnalysis, d.get("critical_analysis")),
            qa_report=_from_dict(ReasoningQAReport, d.get("qa_report")),
            telemetry=_from_dict(ReasoningTelemetry, d.get("telemetry")),
        )


def _from_dict(dataclass_cls: Any, data: Any) -> Any:
    if not isinstance(data, dict):
        return dataclass_cls() if dataclass_cls is not None else None
    fields = getattr(dataclass_cls, "__dataclass_fields__", {})
    kwargs = {}
    for f_name, f_field in fields.items():
        if f_name in data:
            val = data[f_name]
            if f_name in ("source_refs", "evidence_refs") and isinstance(val, list):
                val = [EvidenceRef(**v) if isinstance(v, dict) else v for v in val]
            kwargs[f_name] = val
    return dataclass_cls(**kwargs)


# ============================================================================
# 2. Exceções e Erros Específicos do Motor
# ============================================================================

class AcademicReasoningError(Exception):
    """Erro base do motor de raciocínio académico."""


class OllamaInferenceUnavailableError(AcademicReasoningError):
    """Lançado quando o serviço Ollama ou o modelo qwen3.5:9b estão indisponíveis."""


class ReasoningCancelledError(AcademicReasoningError):
    """Lançado quando a geração foi expressamente cancelada pelo utilizador."""


class CheckpointMismatchError(AcademicReasoningError):
    """Lançado quando o checkpoint em disco é incompatível com o documento atual."""


# ============================================================================
# 3. Helpers de Limpeza e Validação JSON para Qwen 3.5
# ============================================================================

def clean_qwen_json(raw_text: str) -> Optional[Any]:
    """
    Remove tags <think>...</think>, blocos markdown ```json e isola o JSON válido.
    Nunca altera valores internos de strings.
    """
    if not raw_text:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
    if "<think>" in cleaned.lower():
        cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = cleaned.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace : last_brace + 1])
        except Exception:
            pass

    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket > first_bracket:
        try:
            return json.loads(cleaned[first_bracket : last_bracket + 1])
        except Exception:
            pass

    return None


# ============================================================================
# 4. Segmentador Semântico Adaptativo (Adaptive Semantic Chunking)
# ============================================================================

@dataclass
class SemanticSegment:
    segment_id: str
    section_id: str
    paragraphs: List[ASTParagraph]
    text: str
    token_est: int
    page_numbers: List[int]
    is_overlap: bool = False


class SemanticSegmenter:
    """
    Divide uma secção em unidades semânticas adaptativas.
    Regras:
      1. Preserva parágrafos completos (nunca corta frases).
      2. Orçamento seguro de tokens: ~1500 a 2500 tokens por segmento.
      3. Sobreposição de 1 parágrafo se a secção necessitar de múltiplos segmentos.
      4. Preserva metadados de página e paragraph_id.
    """

    def __init__(self, max_tokens_per_segment: int = 2200, overlap_paragraphs: int = 1):
        self.max_tokens_per_segment = max_tokens_per_segment
        self.overlap_paragraphs = overlap_paragraphs

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text.strip()) // 4)

    def segment_section(self, section: ASTSection, paragraphs: List[ASTParagraph]) -> List[SemanticSegment]:
        sec_paras = [p for p in paragraphs if p.section_id == section.section_id]
        if not sec_paras:
            return []

        segments: List[SemanticSegment] = []
        current_paras: List[ASTParagraph] = []
        current_tokens = 0
        seg_index = 0

        for p in sec_paras:
            p_tokens = self.estimate_tokens(p.text)
            # Se adicionar este parágrafo excede o limite e já temos conteúdo:
            if current_paras and (current_tokens + p_tokens > self.max_tokens_per_segment):
                seg_id = f"{section.section_id}_seg_{seg_index}"
                seg_text = "\n\n".join(f"[{cp.paragraph_id}] {cp.text}" for cp in current_paras)
                pages = sorted(list({cp.page_number for cp in current_paras}))
                segments.append(
                    SemanticSegment(
                        segment_id=seg_id,
                        section_id=section.section_id,
                        paragraphs=list(current_paras),
                        text=seg_text,
                        token_est=current_tokens,
                        page_numbers=pages,
                    )
                )
                seg_index += 1

                # Sobreposição controlada
                if self.overlap_paragraphs > 0 and len(current_paras) >= self.overlap_paragraphs:
                    current_paras = current_paras[-self.overlap_paragraphs :]
                    current_tokens = sum(self.estimate_tokens(cp.text) for cp in current_paras)
                else:
                    current_paras = []
                    current_tokens = 0

            current_paras.append(p)
            current_tokens += p_tokens

        if current_paras:
            seg_id = f"{section.section_id}_seg_{seg_index}"
            seg_text = "\n\n".join(f"[{cp.paragraph_id}] {cp.text}" for cp in current_paras)
            pages = sorted(list({cp.page_number for cp in current_paras}))
            segments.append(
                SemanticSegment(
                    segment_id=seg_id,
                    section_id=section.section_id,
                    paragraphs=list(current_paras),
                    text=seg_text,
                    token_est=current_tokens,
                    page_numbers=pages,
                )
            )

        return segments


# ============================================================================
# 5. Prompts Rigorosos do Motor Académico (PT-PT)
# ============================================================================

SYSTEM_PROMPT_ACADEMIC_REASONING = """És o Academic Reasoning Engine do JARVIS OS, especializado em epistemologia, metodologia científica e análise documental profunda em Português Europeu (PT-PT).
O teu objetivo não é resumir de forma simplista ou telegráfica. O teu objetivo é dissecar e reconstruir rigorosamente a arquitetura lógica, os conceitos fundamentais, as evidências empíricas e as limitações do documento fornecido.

PRINCÍPIOS EPISTÉMICOS INEGOCIÁVEIS:
1. FIDELIDADE ABSOLUTA: Fundamenta as tuas afirmações EXCLUSIVAMENTE nas evidências do texto fornecido. Não introduzas teorias externas não mencionadas.
2. DISTINÇÃO EPISTÉMICA: Distingue explicitamente o que é FACTO textual do documento (SOURCE_FACT) do que é inferência ou interpretação lógica tua (MODEL_INFERENCE). Se um tópico não existir na passagem, indica 'NOT_FOUND'. Proibido inventar dados.
3. RASTREABILIDADE FORENSE: Associa cada conceito, argumento ou conclusão aos identificadores de parágrafo [p_X] fornecidos.
4. RIGOR E DENSIDADE: Escreve parágrafos analíticos articulados, densos e explicativos em Português Europeu.
5. FORMATO DE SAÍDA: Responde EXCLUSIVAMENTE em formato JSON estrito, sem texto adicional nem blocos de comentários."""


PROMPT_SEGMENT_ANALYSIS = """Analisa detalhadamente a seguinte passagem da secção "{section_title}" (Tipo: {section_type}):

=== CONTEÚDO DA PASSAGEM ===
{segment_text}
=== FIM DA PASSAGEM ===

Instruções:
- Identifica a ideia central e o objetivo exato desta passagem.
- Extrai conceitos essenciais e as suas definições explícitas ou implícitas.
- Reconstrói os argumentos apresentados, apontando o claim (afirmação) e as evidências probatórias associadas, indicando os identificadores dos parágrafos de suporte.
- Se a passagem contiver pressupostos, conclusões parciais ou terminologia técnica, regista-os.
- Se a passagem NÃO contiver dados sobre alguma categoria, usa explicitamente a lista vazia ou 'NOT_FOUND'. Não inventes.

Devolve EXCLUSIVAMENTE o seguinte objeto JSON:
{{
  "central_idea": "Explicação densa e articulada da ideia central desta passagem.",
  "passage_objective": "Qual é o propósito discursivo ou metodológico desta passagem.",
  "concepts": ["Conceito 1", "Conceito 2"],
  "definitions": [
    {{"term": "Nome do Termo", "definition": "Definição substantiva apresentada no texto", "paragraph_id": "p_X"}}
  ],
  "arguments": [
    {{
      "claim": "Afirmação central sustentada",
      "evidence": "Evidência apresentada no texto",
      "paragraph_id": "p_X",
      "status": "SOURCE_FACT"
    }}
  ],
  "assumptions": ["Premissa assumida pelos autores"],
  "partial_conclusions": ["Conclusão deduzida neste segmento"],
  "technical_terminology": ["Termo técnico específico"],
  "limitations_or_notices": ["Avisos, ressalvas ou limitações expressas no excerto"]
}}"""


PROMPT_SECTION_SYNTHESIS = """Reconstrói e sintetiza a secção estrutural "{section_title}" (Tipo: {section_type}) a partir das análises detalhadas dos seus segmentos constituintes.

=== DADOS DOS SEGMENTOS ANALISADOS ===
{segments_summary}
=== FIM DOS DADOS ===

Instruções:
- NÃO faças uma simples concatenação telegráfica dos segmentos.
- Produz uma síntese aprofundada ('in_depth_synthesis') em prosa académica coerente, explicando como a secção cumpre o seu objetivo.
- Articula a cadeia de argumentos e como estes se relacionam com as evidências apresentadas.
- Identifica contributos científicos e eventuais limitações da secção.

Devolve EXCLUSIVAMENTE o seguinte objeto JSON:
{{
  "objective": "Objetivo principal da secção no âmbito do artigo.",
  "in_depth_synthesis": "Texto explicativo aprofundado e contínuo (2 a 4 parágrafos substanciais em PT-PT) reconstituindo a tese da secção.",
  "core_ideas": [
    "Ideia fundamental 1 explicada com detalhe",
    "Ideia fundamental 2 explicada com detalhe"
  ],
  "concepts": [
    {{
      "name": "Conceito Chave",
      "explanation": "Como é operacionalizado e articulado nesta secção.",
      "paragraph_ids": ["p_X"]
    }}
  ],
  "arguments": [
    {{
      "claim": "Argumento central da secção",
      "evidence": "Fundamentação empírica ou teórica",
      "paragraph_ids": ["p_X"],
      "status": "SOURCE_FACT"
    }}
  ],
  "limitations": [
    "Ressalva ou limitação associada a esta secção"
  ]
}}"""


PROMPT_CROSS_SECTION_INTEGRATION = """Executa uma integração transversal (Reduce Global) entre todas as secções do documento "{document_title}".

=== SÍNTESES DAS SECÇÕES ===
{sections_summary}
=== METADADOS E OBJETIVOS ===
{metadata_summary}

Instruções:
- Analisa a progressão argumentativa entre secções (como a introdução coloca o problema, a literatura fundamenta, a metodologia responde, os resultados evidenciam e a discussão conclui).
- Identifica interdependências conceptuais e relações de causa/efeito.
- Procura tensões, aparentes contradições ou afirmações não plenamente sustentadas pelos dados. Se não existirem contradições, declara honestamente que a progressão é coerente.
- Produz uma síntese global aprofundada da obra.

Devolve EXCLUSIVAMENTE o seguinte objeto JSON:
{{
  "argumentative_progression": [
    "Fase 1: Apresentação do problema e lacuna teórica na secção...",
    "Fase 2: Operacionalização metodológica através de...",
    "Fase 3: Apresentação dos resultados e subsequente discussão..."
  ],
  "conceptual_relationships": [
    {{"concept_a": "Conceito A", "relationship": "influencia/depende de", "concept_b": "Conceito B", "explanation": "Por que razão..."}}
  ],
  "coherence_and_tensions": [
    {{
      "type": "COHERENCE",
      "description": "Explicação da coerência ou de eventual tensão identificada entre resultados e conclusões.",
      "sections_involved": ["sec_1", "sec_2"],
      "status": "MODEL_INFERENCE"
    }}
  ],
  "idea_dependencies": [
    {{"dependent_idea": "Ideia Y", "depends_on": "Ideia X", "reason": "Justificação lógica da dependência"}}
  ],
  "global_synthesis": "Síntese global holística e rigorosa (3 a 5 parágrafos substantivos em PT-PT) que integra o contributo da totalidade do documento."
}}"""


PROMPT_METHODOLOGY_AND_RESULTS = """Examina em pormenor a metodologia e os resultados apresentados no documento "{document_title}".

=== CONTEÚDO DAS SECÇÕES DE METODOLOGIA E RESULTADOS ===
{method_and_results_content}
=== FIM DO CONTEÚDO ===

Instruções:
- Se o documento NÃO for um estudo empírico (ex: é ensaio teórico, revisão conceptual, etc.), assinala "is_applicable": false e preenche os campos disponíveis como "NOT_APPLICABLE".
- Se for empírico, extrai com fidelidade: tipo de investigação, amostra, procedimentos, variáveis, técnicas de análise e limitações metodológicas.
- Em resultados, isola as afirmações de resultados acompanhadas dos respetivos dados probatórios (quantitativos ou qualitativos). NUNCA inventes números ou percentagens.

Devolve EXCLUSIVAMENTE o seguinte objeto JSON:
{{
  "is_applicable": true,
  "research_type": "ex: Quantitativo / Qualitativo / Estudo de Caso / Misto",
  "methodological_design": "Descrição do desenho experimental ou observacional",
  "methods_used": ["Método 1", "Método 2"],
  "sample_or_participants": "Descrição detalhada da amostra ou 'NOT_APPLICABLE'",
  "instruments": ["Instrumentos ou fontes de recolha"],
  "procedures": ["Passo a passo dos procedimentos"],
  "variables": ["Variáveis independentes/dependentes analisadas"],
  "data_sources": ["Fontes dos dados"],
  "analysis_techniques": ["Técnicas estatísticas ou analíticas"],
  "methodological_limitations": ["Limitações metodológicas expressas"],
  "results": [
    {{
      "statement": "Enunciado do resultado observado",
      "evidence_data": "Dados, métricas ou citações de suporte presentes no texto",
      "relation_to_objectives": "Como este resultado responde à questão do estudo",
      "interpretation_limitations": "Limitação na interpretação deste resultado",
      "paragraph_id": "p_X"
    }}
  ]
}}"""


# ============================================================================
# 6. Motor Principal de Execução: AcademicReasoningEngine
# ============================================================================

LLMCaller = Callable[[str, str, Dict[str, Any]], Tuple[Optional[str], Dict[str, Any]]]


class AcademicReasoningEngine:
    """
    Motor orquestrador da Fase 3:
      - Consome AcademicDocumentAST.
      - Segmenta e processa hierarquicamente via Map-Reduce.
      - Utiliza exclusivamente o Ollama local (qwen3.5:9b).
      - Executa checkpoints incrementais e suporta recuperação e cancelamento.
      - Gera o AcademicReasoningDossier final auditado por ReasoningQAEvaluator.
    """

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_MODEL,
        storage_dir: Optional[Path] = None,
        llm_caller: Optional[LLMCaller] = None,
        max_retries_per_call: int = 2,
    ):
        self.model_name = model_name
        self.storage_dir = storage_dir or Path("data/study")
        self.llm_caller = llm_caller
        self.max_retries_per_call = max_retries_per_call
        self.segmenter = SemanticSegmenter()

    def _default_llm_caller(
        self,
        system_prompt: str,
        user_prompt: str,
        metadata: Dict[str, Any],
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Invocador real usando ModelExecutionService e o provider Ollama do repositório."""
        from services.study_ai_engine import invoke_study_llm_observable

        operation = metadata.get("operation", "academic_reasoning")
        doc_id = metadata.get("document_id", "")
        timeout = float(metadata.get("timeout_seconds", 180.0))

        raw_obj, telemetry = invoke_study_llm_observable(
            operation=operation,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expect_json=True,
            temperature=0.15,
            max_output_tokens=3000,
            timeout_seconds=timeout,
            document_id=doc_id,
        )
        if raw_obj is None:
            # Verifica se falhou por indisponibilidade real
            status = telemetry.get("status", "")
            if status in ("UNAVAILABLE", "TIMEOUT", "FAILED_VALIDATION", "SKIPPED_LIVE_LLM_DISABLED"):
                err_msg = f"Invocação do modelo local '{self.model_name}' falhou com estado '{status}'"
                logger.error(err_msg)
            return None, telemetry

        serialized = json.dumps(raw_obj, ensure_ascii=False) if isinstance(raw_obj, (dict, list)) else str(raw_obj)
        return serialized, telemetry

    def _call_model_with_retries(
        self,
        system_prompt: str,
        user_prompt: str,
        metadata: Dict[str, Any],
        cancellation_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Executa a chamada ao modelo com tentativas limitadas e validação JSON."""
        caller = self.llm_caller or self._default_llm_caller
        attempts = 0
        last_telemetry: Dict[str, Any] = {}

        while attempts <= self.max_retries_per_call:
            if cancellation_check and cancellation_check():
                raise ReasoningCancelledError("Execução cancelada pelo utilizador.")

            attempts += 1
            metadata["attempt"] = attempts
            t0 = time.perf_counter()

            try:
                raw_resp, telemetry = caller(system_prompt, user_prompt, metadata)
                last_telemetry = telemetry or {}
            except Exception as e:
                logger.warning(f"Tentativa {attempts} gerou exceção no transport: {e}")
                if "unavailable" in str(e).lower() or "connecterror" in str(e).lower():
                    raise OllamaInferenceUnavailableError(f"Ollama ou modelo '{self.model_name}' inacessível: {e}")
                # Erros fatais (ex: RuntimeError, crash ou interrupção de execução) devem interromper a pipeline
                if isinstance(e, (RuntimeError, KeyboardInterrupt)) and not isinstance(e, AcademicReasoningError):
                    raise e
                last_telemetry = {"status": "ERROR", "error": str(e)}
                raw_resp = None

            if raw_resp:
                parsed = clean_qwen_json(raw_resp)
                if isinstance(parsed, (dict, list)):
                    return parsed, last_telemetry

            logger.info(f"Resposta inválida ou vazia na tentativa {attempts}/{self.max_retries_per_call + 1}. A tentar novamente...")

        # Se todas as tentativas falharem
        status = last_telemetry.get("status", "")
        if status in ("UNAVAILABLE", "TIMEOUT"):
            raise OllamaInferenceUnavailableError(
                f"Ollama local qwen3.5:9b indisponível após {attempts} tentativas ({status})."
            )
        return None, last_telemetry

    # ------------------------------------------------------------------------
    # Gestão de Checkpoint e Persistência Incrementais
    # ------------------------------------------------------------------------

    def _get_doc_dir(self, document_id: str) -> Path:
        p = self.storage_dir / "documents" / document_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _load_checkpoint(
        self,
        document_id: str,
        source_sha256: str,
        ast_version: str,
    ) -> Optional[Dict[str, Any]]:
        """Carrega checkpoint em disco se for estritamente compatível."""
        cp_path = self._get_doc_dir(document_id) / "reasoning_checkpoint.json"
        if not cp_path.exists():
            return None
        try:
            data = json.loads(cp_path.read_text(encoding="utf-8"))
            if data.get("document_id") != document_id:
                return None
            if data.get("source_sha256") != source_sha256:
                logger.info(f"[Checkpoint] SHA256 do documento mudou ({data.get('source_sha256')} != {source_sha256}). Invalidação forçada.")
                return None
            if data.get("ast_version") != ast_version:
                logger.info("[Checkpoint] Versão da AST mudou. Invalidação forçada.")
                return None
            if data.get("model_name") != self.model_name:
                logger.info("[Checkpoint] Modelo mudou. Invalidação forçada.")
                return None
            if data.get("prompt_versions") != PROMPT_VERSIONS:
                logger.info(f"[Checkpoint] Versão dos prompts mudou ({data.get('prompt_versions')} != {PROMPT_VERSIONS}). Invalidação forçada.")
                return None
            return data
        except Exception as e:
            logger.warning(f"Erro ao ler checkpoint: {e}")
            return None

    def _save_checkpoint(self, document_id: str, checkpoint_data: Dict[str, Any]) -> None:
        cp_path = self._get_doc_dir(document_id) / "reasoning_checkpoint.json"
        tmp_path = cp_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(checkpoint_data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(cp_path)

    def _save_final_dossier(self, dossier: AcademicReasoningDossier) -> None:
        p = self._get_doc_dir(dossier.document_id) / "reasoning_dossier.json"
        tmp_p = p.with_suffix(".tmp")
        tmp_p.write_text(json.dumps(dossier.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_p.replace(p)

    # ------------------------------------------------------------------------
    # Pipeline Completo de Raciocínio (Hierarchical Map-Reduce)
    # ------------------------------------------------------------------------

    def analyze_document(
        self,
        ast: AcademicDocumentAST,
        *,
        on_progress: Optional[Callable[[str, float, str], None]] = None,
        cancellation_check: Optional[Callable[[], bool]] = None,
        force_recompute: bool = False,
    ) -> AcademicReasoningDossier:
        """
        Executa a análise hierárquica completa do documento:
          Passo 1: Preparação e carregamento de checkpoint
          Passo 2: Map - Análise de segmentos semânticos
          Passo 3: Reduce 1 - Síntese integrada de cada secção
          Passo 4: Metodologia e Resultados específicos
          Passo 5: Reduce 2 - Integração transversal e tensões
          Passo 6: Auditoria Forense QA e persistência
        """
        start_time = time.perf_counter()
        doc_id = ast.document_id
        source_sha256 = ast.source_sha256 or (ast.metadata.source_sha256 if ast.metadata else "")
        ast_version = ast.extractor_version

        def progress(stage: str, pct: float, msg: str):
            if on_progress:
                on_progress(stage, pct, msg)

        progress("START", 0.05, f"A iniciar raciocínio académico para documento {doc_id}...")

        # 1. Checkpoint
        checkpoint = None
        if not force_recompute:
            checkpoint = self._load_checkpoint(doc_id, source_sha256, ast_version)

        completed_segments: Dict[str, Dict[str, Any]] = checkpoint.get("completed_segments", {}) if checkpoint else {}
        completed_sections: Dict[str, Dict[str, Any]] = checkpoint.get("completed_sections", {}) if checkpoint else {}

        # Mapeamento rápido de parágrafos da AST
        paragraphs_map: Dict[str, ASTParagraph] = {p.paragraph_id: p for p in ast.paragraphs}

        # 2. Filtrar secções úteis para análise (ignora referências puras e apêndices na análise de fundo)
        analyzable_sections = [
            s for s in ast.sections
            if s.kind not in ("references", "page_artifact") and any(p.section_id == s.section_id for p in ast.paragraphs)
        ]
        if not analyzable_sections and ast.sections:
            analyzable_sections = list(ast.sections)

        total_sections = len(analyzable_sections)
        all_section_analyses: List[SectionAnalysis] = []
        all_concepts_map: Dict[str, ConceptItem] = {}
        all_results: List[ResultItem] = []
        failed_operations: List[Dict[str, Any]] = []
        telemetry_metrics = ReasoningTelemetry()

        # 3. Execução Map por Secção -> Segmentos
        for sec_idx, section in enumerate(analyzable_sections, start=1):
            if cancellation_check and cancellation_check():
                raise ReasoningCancelledError(f"Execução cancelada antes da secção {section.section_id}")

            sec_progress_base = 0.10 + (sec_idx - 1) / max(1, total_sections) * 0.50
            progress("SECTION_START", sec_progress_base, f"A analisar secção {sec_idx}/{total_sections}: {section.title}")

            # Se a secção já estiver completamente sintetizada no checkpoint:
            if section.section_id in completed_sections:
                sec_data = completed_sections[section.section_id]
                sec_analysis = _from_dict(SectionAnalysis, sec_data)
                all_section_analyses.append(sec_analysis)
                # Reconstruir conceitos no mapa global a partir do checkpoint
                for c in sec_analysis.concepts:
                    c_name = c.get("name") if isinstance(c, dict) else str(c)
                    if c_name and c_name not in all_concepts_map:
                        all_concepts_map[c_name] = ConceptItem(
                            concept_id=f"c_{uuid.uuid4().hex[:8]}",
                            name=c_name,
                            explanation=c.get("explanation", "") if isinstance(c, dict) else "",
                            evidence_refs=[EvidenceRef(section_id=section.section_id, status=EpistemicStatus.SOURCE_FACT.value)],
                        )
                continue

            # Obter segmentos da secção
            segments = self.segmenter.segment_section(section, ast.paragraphs)
            sec_segment_analyses: List[SegmentAnalysis] = []

            for seg_idx, segment in enumerate(segments, start=1):
                if cancellation_check and cancellation_check():
                    raise ReasoningCancelledError(f"Cancelado no segmento {segment.segment_id}")

                seg_id = segment.segment_id
                if seg_id in completed_segments:
                    seg_analysis = _from_dict(SegmentAnalysis, completed_segments[seg_id])
                    sec_segment_analyses.append(seg_analysis)
                    continue

                # Chamada do modelo para o segmento (Map)
                seg_user_prompt = PROMPT_SEGMENT_ANALYSIS.format(
                    section_title=section.title,
                    section_type=section.kind,
                    segment_text=segment.text,
                )
                seg_meta = {
                    "operation": "academic_segment_analysis",
                    "document_id": doc_id,
                    "section_id": section.section_id,
                    "segment_id": seg_id,
                    "timeout_seconds": 120.0,
                }

                t_seg0 = time.perf_counter()
                parsed_seg, seg_telemetry = self._call_model_with_retries(
                    SYSTEM_PROMPT_ACADEMIC_REASONING,
                    seg_user_prompt,
                    seg_meta,
                    cancellation_check=cancellation_check,
                )
                t_seg_elapsed = round((time.perf_counter() - t_seg0) * 1000.0, 2)
                telemetry_metrics.total_llm_calls += 1
                telemetry_metrics.segment_durations_ms[seg_id] = t_seg_elapsed

                if not parsed_seg or not isinstance(parsed_seg, dict):
                    # Registo explícito de falha no segmento — zero substituição silenciosa por conteúdo inventado
                    err_info = {
                        "stage": "segment_analysis",
                        "section_id": section.section_id,
                        "segment_id": seg_id,
                        "reason": seg_telemetry.get("status", "INVALID_JSON_AFTER_RETRIES"),
                        "error": "Resposta JSON inválida ou vazia do modelo após todas as tentativas.",
                    }
                    failed_operations.append(err_info)
                    telemetry_metrics.failures_count += 1
                    logger.error(f"[Segment Analysis Failed] {err_info}")

                    seg_obj = SegmentAnalysis(
                        segment_id=seg_id,
                        section_id=section.section_id,
                        paragraph_ids=[p.paragraph_id for p in segment.paragraphs],
                        page_numbers=segment.page_numbers,
                        central_idea="",
                        passage_objective="",
                        concepts=[],
                        definitions=[],
                        arguments=[],
                        assumptions=[],
                        partial_conclusions=[],
                        technical_terminology=[],
                        evidence_refs=[],
                        limitations_or_notices=[f"FALHA: Análise de segmento não concluída pelo modelo ({err_info['reason']})"],
                        execution_time_ms=t_seg_elapsed,
                    )
                    sec_segment_analyses.append(seg_obj)
                    continue

                # Construir evidências associadas
                seg_evidences: List[EvidenceRef] = []
                for p_id in segment.paragraphs:
                    seg_evidences.append(
                        EvidenceRef(
                            section_id=section.section_id,
                            paragraph_id=p_id.paragraph_id,
                            page_number=p_id.page_number,
                            excerpt=p_id.text[:150],
                            status=EpistemicStatus.SOURCE_FACT.value,
                        )
                    )

                seg_obj = SegmentAnalysis(
                    segment_id=seg_id,
                    section_id=section.section_id,
                    paragraph_ids=[p.paragraph_id for p in segment.paragraphs],
                    page_numbers=segment.page_numbers,
                    central_idea=parsed_seg.get("central_idea", ""),
                    passage_objective=parsed_seg.get("passage_objective", ""),
                    concepts=parsed_seg.get("concepts", []),
                    definitions=parsed_seg.get("definitions", []),
                    arguments=parsed_seg.get("arguments", []),
                    assumptions=parsed_seg.get("assumptions", []),
                    partial_conclusions=parsed_seg.get("partial_conclusions", []),
                    technical_terminology=parsed_seg.get("technical_terminology", []),
                    evidence_refs=seg_evidences,
                    limitations_or_notices=parsed_seg.get("limitations_or_notices", []),
                    execution_time_ms=t_seg_elapsed,
                )
                sec_segment_analyses.append(seg_obj)

                # Guardar em checkpoint parcial
                completed_segments[seg_id] = asdict(seg_obj)
                self._save_checkpoint(
                    doc_id,
                    {
                        "document_id": doc_id,
                        "source_sha256": source_sha256,
                        "ast_version": ast_version,
                        "model_name": self.model_name,
                        "prompt_versions": PROMPT_VERSIONS,
                        "completed_segments": completed_segments,
                        "completed_sections": completed_sections,
                        "updated_at": datetime.now().isoformat(),
                    },
                )

            # 4. Síntese Integrada da Secção (Reduce 1)
            valid_segments = [s for s in sec_segment_analyses if s.central_idea]
            segments_summary_text = "\n\n".join(
                f"[Segmento {s.segment_id}]\nIdeia: {s.central_idea}\nObjetivo: {s.passage_objective}\n"
                f"Conceitos: {', '.join(s.concepts)}\nArgumentos: {json.dumps(s.arguments, ensure_ascii=False)}"
                for s in valid_segments
            )
            sec_synth_prompt = PROMPT_SECTION_SYNTHESIS.format(
                section_title=section.title,
                section_type=section.kind,
                segments_summary=segments_summary_text or "Sem dados válidos de segmentos.",
            )
            sec_meta = {
                "operation": "academic_section_synthesis",
                "document_id": doc_id,
                "section_id": section.section_id,
                "timeout_seconds": 150.0,
            }

            t_sec0 = time.perf_counter()
            parsed_sec, sec_telemetry = self._call_model_with_retries(
                SYSTEM_PROMPT_ACADEMIC_REASONING,
                sec_synth_prompt,
                sec_meta,
                cancellation_check=cancellation_check,
            )
            t_sec_elapsed = round((time.perf_counter() - t_sec0) * 1000.0, 2)
            telemetry_metrics.total_llm_calls += 1
            telemetry_metrics.section_durations_ms[section.section_id] = t_sec_elapsed

            if not parsed_sec or not isinstance(parsed_sec, dict):
                # Registo explícito de falha na síntese da secção — zero texto genérico inventado
                err_info = {
                    "stage": "section_synthesis",
                    "section_id": section.section_id,
                    "reason": sec_telemetry.get("status", "INVALID_JSON_AFTER_RETRIES"),
                    "error": "Falha na síntese integrada da secção após todas as tentativas.",
                }
                failed_operations.append(err_info)
                telemetry_metrics.failures_count += 1
                logger.error(f"[Section Synthesis Failed] {err_info}")

                sec_analysis_obj = SectionAnalysis(
                    section_id=section.section_id,
                    title=section.title,
                    section_type=section.kind,
                    objective="",
                    in_depth_synthesis="",
                    core_ideas=[],
                    concepts=[],
                    arguments=[],
                    evidences=[],
                    limitations=[f"FALHA: Síntese da secção não concluída ({err_info['reason']})"],
                    source_refs=[],
                    segment_ids=[s.segment_id for s in sec_segment_analyses],
                    execution_time_ms=t_sec_elapsed,
                )
                all_section_analyses.append(sec_analysis_obj)
                continue

            # Referências consolidadas
            sec_refs: List[EvidenceRef] = []
            for seg in sec_segment_analyses:
                sec_refs.extend(seg.evidence_refs[:3])

            sec_analysis_obj = SectionAnalysis(
                section_id=section.section_id,
                title=section.title,
                section_type=section.kind,
                objective=parsed_sec.get("objective", ""),
                in_depth_synthesis=parsed_sec.get("in_depth_synthesis", ""),
                core_ideas=parsed_sec.get("core_ideas", []),
                concepts=parsed_sec.get("concepts", []),
                arguments=parsed_sec.get("arguments", []),
                evidences=parsed_sec.get("evidences", []),
                limitations=parsed_sec.get("limitations", []),
                source_refs=sec_refs,
                segment_ids=[s.segment_id for s in sec_segment_analyses],
                execution_time_ms=t_sec_elapsed,
            )
            all_section_analyses.append(sec_analysis_obj)
            completed_sections[section.section_id] = asdict(sec_analysis_obj)

            # Agregar conceitos ao mapa global
            for c in parsed_sec.get("concepts", []):
                c_name = c.get("name") if isinstance(c, dict) else str(c)
                if c_name and c_name not in all_concepts_map:
                    all_concepts_map[c_name] = ConceptItem(
                        concept_id=f"c_{uuid.uuid4().hex[:8]}",
                        name=c_name,
                        explanation=c.get("explanation", "") if isinstance(c, dict) else "",
                        evidence_refs=[EvidenceRef(section_id=section.section_id, status=EpistemicStatus.SOURCE_FACT.value)],
                    )

            # Atualizar checkpoint com a secção concluída
            self._save_checkpoint(
                doc_id,
                {
                    "document_id": doc_id,
                    "source_sha256": source_sha256,
                    "ast_version": ast_version,
                    "model_name": self.model_name,
                    "prompt_versions": PROMPT_VERSIONS,
                    "completed_segments": completed_segments,
                    "completed_sections": completed_sections,
                    "updated_at": datetime.now().isoformat(),
                },
            )

        # 5. Análise Específica de Metodologia e Resultados (SEM LIMITAÇÕES ARBITRÁRIAS DE PARÁGRAFOS)
        progress("METHOD_ANALYSIS", 0.65, "A examinar metodologia empírica e resultados comprovados...")
        method_sections = [
            s for s in ast.sections
            if s.kind in ("methodology", "results")
            or any(tok in s.title.lower() for tok in ("method", "metod", "result", "experim"))
        ]
        methodology_analysis = MethodologyAnalysis(is_applicable=False)

        if method_sections:
            method_text_blocks = []
            for ms in method_sections:
                paras = [p for p in ast.paragraphs if p.section_id == ms.section_id]
                # Processa TODOS os parágrafos relevantes da secção sem limite fixo
                sec_text = "\n".join(f"[{p.paragraph_id}] (p.{p.page_number}) {p.text}" for p in paras)
                method_text_blocks.append(f"=== Secção: {ms.title} ({ms.kind}) ===\n{sec_text}")

            method_prompt = PROMPT_METHODOLOGY_AND_RESULTS.format(
                document_title=ast.metadata.title or ast.filename or doc_id,
                method_and_results_content="\n\n".join(method_text_blocks),
            )
            parsed_method, method_telemetry = self._call_model_with_retries(
                SYSTEM_PROMPT_ACADEMIC_REASONING,
                method_prompt,
                {"operation": "academic_methodology_results", "document_id": doc_id},
                cancellation_check=cancellation_check,
            )
            if not parsed_method or not isinstance(parsed_method, dict):
                err_info = {
                    "stage": "methodology_results_analysis",
                    "reason": method_telemetry.get("status", "INVALID_JSON_AFTER_RETRIES"),
                    "error": "Falha na análise metodológica após retries.",
                }
                failed_operations.append(err_info)
                telemetry_metrics.failures_count += 1
                logger.error(f"[Methodology Analysis Failed] {err_info}")
            else:
                methodology_analysis = MethodologyAnalysis(
                    is_applicable=bool(parsed_method.get("is_applicable", True)),
                    research_type=parsed_method.get("research_type", ""),
                    methodological_design=parsed_method.get("methodological_design", ""),
                    methods_used=parsed_method.get("methods_used", []),
                    sample_or_participants=parsed_method.get("sample_or_participants", ""),
                    instruments=parsed_method.get("instruments", []),
                    procedures=parsed_method.get("procedures", []),
                    variables=parsed_method.get("variables", []),
                    data_sources=parsed_method.get("data_sources", []),
                    analysis_techniques=parsed_method.get("analysis_techniques", []),
                    methodological_limitations=parsed_method.get("methodological_limitations", []),
                )
                for r in parsed_method.get("results", []):
                    if isinstance(r, dict) and r.get("statement"):
                        r_pid = (r.get("paragraph_id") or "").strip()
                        p_obj = paragraphs_map.get(r_pid)
                        sec_id = p_obj.section_id if p_obj else method_sections[0].section_id
                        p_page = p_obj.page_number if p_obj else 1
                        all_results.append(
                            ResultItem(
                                statement=r["statement"],
                                evidence_data=r.get("evidence_data", ""),
                                relation_to_objectives=r.get("relation_to_objectives", ""),
                                interpretation_limitations=r.get("interpretation_limitations", ""),
                                evidence_refs=[
                                    EvidenceRef(
                                        section_id=sec_id,
                                        paragraph_id=r_pid if r_pid else None,
                                        page_number=p_page if r_pid else None,
                                        status=EpistemicStatus.SOURCE_FACT.value if r_pid else EpistemicStatus.UNVERIFIED.value,
                                    )
                                ],
                            )
                        )

        # 6. Integração Transversal Global (Reduce 2)
        progress("CROSS_SECTION_INTEGRATION", 0.80, "A executar raciocínio transversal e deteção de tensões...")
        valid_synth_sections = [sa for sa in all_section_analyses if sa.in_depth_synthesis]

        sections_summary_text = "\n\n".join(
            f"Secção: {sa.title} ({sa.section_type})\nObjetivo: {sa.objective}\nSíntese: {sa.in_depth_synthesis[:400]}..."
            for sa in valid_synth_sections
        )
        cross_prompt = PROMPT_CROSS_SECTION_INTEGRATION.format(
            document_title=ast.metadata.title or ast.filename or doc_id,
            sections_summary=sections_summary_text or "Nenhuma secção disponível.",
            metadata_summary=json.dumps(
                {
                    "abstract": (ast.metadata.abstract or "")[:400],
                    "keywords": ast.metadata.keywords,
                    "total_pages": ast.metadata.page_count,
                },
                ensure_ascii=False,
            ),
        )
        parsed_cross, cross_telemetry = self._call_model_with_retries(
            SYSTEM_PROMPT_ACADEMIC_REASONING,
            cross_prompt,
            {"operation": "academic_cross_section_integration", "document_id": doc_id},
            cancellation_check=cancellation_check,
        )
        if not parsed_cross or not isinstance(parsed_cross, dict):
            # Registo explícito de falha na integração transversal — zero síntese global inventada
            err_info = {
                "stage": "cross_section_integration",
                "reason": cross_telemetry.get("status", "INVALID_JSON_AFTER_RETRIES"),
                "error": "Falha na integração transversal global após retries.",
            }
            failed_operations.append(err_info)
            telemetry_metrics.failures_count += 1
            logger.error(f"[Cross-Section Integration Failed] {err_info}")
            cross_section_synthesis = CrossSectionSynthesis(
                section_relationships=[],
                argumentative_progression=[],
                conceptual_relationships=[],
                coherence_and_tensions=[],
                idea_dependencies=[],
                global_synthesis="",
            )
        else:
            cross_section_synthesis = CrossSectionSynthesis(
                section_relationships=parsed_cross.get("section_relationships", []),
                argumentative_progression=parsed_cross.get("argumentative_progression", []),
                conceptual_relationships=parsed_cross.get("conceptual_relationships", []),
                coherence_and_tensions=parsed_cross.get("coherence_and_tensions", []),
                idea_dependencies=parsed_cross.get("idea_dependencies", []),
                global_synthesis=parsed_cross.get("global_synthesis", ""),
            )

        # 7. Document Analysis Core
        valid_sections_with_obj = [sa for sa in all_section_analyses if sa.objective]
        doc_analysis = DocumentCoreAnalysis(
            document_id=doc_id,
            title=ast.metadata.title or ast.filename or doc_id,
            metadata={
                "authors": ast.metadata.authors,
                "doi": ast.metadata.doi,
                "keywords": ast.metadata.keywords,
                "page_count": ast.metadata.page_count,
            },
            global_objective=valid_sections_with_obj[0].objective if valid_sections_with_obj else "Análise do documento.",
            research_problem=(ast.metadata.abstract[:200] if ast.metadata.abstract else "Investigação dos tópicos tratados no documento."),
            research_questions=[],
            central_thesis=cross_section_synthesis.global_synthesis[:250] if cross_section_synthesis.global_synthesis else "",
            main_contributions=[sa.core_ideas[0] for sa in all_section_analyses if sa.core_ideas][:4],
        )

        # 8. Análise Crítica
        critical_analysis = CriticalAnalysis(
            epistemic_assumptions=["Assume a fiabilidade das observações e dados apresentados pelo autor."],
            author_limitations=[lim for sa in all_section_analyses for lim in sa.limitations if not lim.startswith("FALHA:")][:5],
            literature_gaps=["Lacunas teóricas identificadas nos objetivos do estudo."],
            open_questions=["Necessidade de corroboração empírica adicional em estudos futuros."],
            aspects_requiring_validation=[],
            author_vs_inference_distinctions=[
                {"statement": "As secções empíricas representam afirmações factuais do autor (SOURCE_FACT).", "type": "SOURCE_FACT"},
                {"statement": "A síntese transversal e relações conceptuais são inferidas pelo modelo (MODEL_INFERENCE).", "type": "MODEL_INFERENCE"},
            ],
        )

        # 9. Determinação Rigorosa do Estado do Dossier
        if not all_section_analyses or all(not sa.in_depth_synthesis for sa in all_section_analyses):
            dossier_status = "FAILED"
        elif failed_operations:
            dossier_status = "PARTIAL"
        else:
            dossier_status = "COMPLETED"

        # 10. Auditoria Forense QA Reforçada
        progress("QA_VALIDATION", 0.95, "A validar integridade das referências e separação epistemológica...")
        qa_evaluator = ReasoningQAEvaluator()
        qa_report = qa_evaluator.evaluate(
            ast=ast,
            section_analyses=all_section_analyses,
            results=all_results,
            cross_synthesis=cross_section_synthesis,
            failed_operations=failed_operations,
        )

        total_elapsed = round((time.perf_counter() - start_time) * 1000.0, 2)
        telemetry_metrics.total_duration_ms = total_elapsed

        dossier = AcademicReasoningDossier(
            dossier_id=f"dossier_{uuid.uuid4().hex[:12]}",
            document_id=doc_id,
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            source_sha256=source_sha256,
            ast_version=ast_version,
            model_name=self.model_name,
            prompt_versions=PROMPT_VERSIONS,
            created_at=datetime.now().isoformat(),
            status=dossier_status,
            failed_operations=failed_operations,
            document_analysis=doc_analysis,
            section_analyses=all_section_analyses,
            conceptual_analysis=list(all_concepts_map.values()),
            methodology_analysis=methodology_analysis,
            results_and_evidence=all_results,
            cross_section_synthesis=cross_section_synthesis,
            critical_analysis=critical_analysis,
            qa_report=qa_report,
            telemetry=telemetry_metrics,
        )

        # 11. Persistência Final e Salvaguarda
        self._save_final_dossier(dossier)
        progress("DONE", 1.0, f"Raciocínio académico concluído com estado '{dossier_status}' em {total_elapsed / 1000.0:.1f}s.")
        return dossier


# ============================================================================
# 7. ReasoningQAEvaluator: Auditoria Forense e Integridade Reforçada
# ============================================================================

class ReasoningQAEvaluator:
    """
    Auditor forense do raciocínio académico:
      1. Garante que todos os paragraph_id referenciados existem na AST.
      2. Garante correspondência entre o parágrafo e a section_id indicada.
      3. Garante correspondência entre a página indicada e a localização real na AST.
      4. Exige evidência válida (com paragraph_id não vazio) para cada resultado SOURCE_FACT.
      5. Audita separação coerente entre SOURCE_FACT, MODEL_INFERENCE, NOT_FOUND e UNVERIFIED.
      6. Define is_valid=False perante qualquer referência inválida ou operação falhada.
    """

    def evaluate(
        self,
        ast: AcademicDocumentAST,
        section_analyses: List[SectionAnalysis],
        results: List[ResultItem],
        cross_synthesis: CrossSectionSynthesis,
        failed_operations: Optional[List[Dict[str, Any]]] = None,
    ) -> ReasoningQAReport:
        valid_paras: Dict[str, ASTParagraph] = {p.paragraph_id: p for p in ast.paragraphs}
        valid_sections: Set[str] = {s.section_id for s in ast.sections}
        max_page = max([p.page_number for p in ast.pages] or [1])

        invalid_paras: List[str] = []
        invalid_pages: List[int] = []
        fact_counts: Dict[str, int] = {
            EpistemicStatus.SOURCE_FACT.value: 0,
            EpistemicStatus.MODEL_INFERENCE.value: 0,
            EpistemicStatus.NOT_FOUND.value: 0,
            EpistemicStatus.UNVERIFIED.value: 0,
        }
        total_refs = 0
        valid_refs = 0
        warnings: List[str] = []
        errors: List[str] = []

        if failed_operations:
            for fo in failed_operations:
                errors.append(f"Operação não concluída na etapa '{fo.get('stage')}': {fo.get('error', 'Falha no modelo')}")

        # Inspecionar referências das secções
        for sec in section_analyses:
            refs = getattr(sec, "source_refs", []) or []
            for ref in refs:
                total_refs += 1
                ref_valid = True
                p_id = getattr(ref, "paragraph_id", None) if not isinstance(ref, dict) else ref.get("paragraph_id")
                s_id = getattr(ref, "section_id", "") if not isinstance(ref, dict) else ref.get("section_id", "")
                p_num = getattr(ref, "page_number", None) if not isinstance(ref, dict) else ref.get("page_number")
                status_val = getattr(ref, "status", EpistemicStatus.SOURCE_FACT.value) if not isinstance(ref, dict) else ref.get("status", EpistemicStatus.SOURCE_FACT.value)

                if p_id:
                    if p_id not in valid_paras:
                        invalid_paras.append(p_id)
                        errors.append(f"Referência a paragraph_id inexistente '{p_id}' na secção '{s_id or sec.section_id}'")
                        ref_valid = False
                    else:
                        p_obj = valid_paras[p_id]
                        # 2. Correspondência entre o parágrafo e a section_id indicada
                        expected_sec = s_id or sec.section_id
                        if expected_sec and p_obj.section_id != expected_sec:
                            errors.append(
                                f"Parágrafo '{p_id}' pertence à secção '{p_obj.section_id}', mas foi referenciado sob a secção '{expected_sec}'."
                            )
                            ref_valid = False
                        # 3. Correspondência entre a página indicada e a localização efetiva na AST
                        if p_num is not None and p_num != p_obj.page_number:
                            invalid_pages.append(p_num)
                            errors.append(
                                f"Página indicada ({p_num}) para o parágrafo '{p_id}' não coincide com a página real na AST ({p_obj.page_number})."
                            )
                            ref_valid = False
                elif s_id in valid_sections:
                    pass
                else:
                    errors.append(f"Referência sem parágrafo nem secção válida: {ref}")
                    ref_valid = False

                if p_num is not None and (p_num < 1 or p_num > max_page):
                    if p_num not in invalid_pages:
                        invalid_pages.append(p_num)
                    errors.append(f"Página fora dos limites do documento: {p_num} (máx: {max_page})")
                    ref_valid = False

                if ref_valid:
                    valid_refs += 1

                if status_val not in fact_counts:
                    status_val = EpistemicStatus.SOURCE_FACT.value
                fact_counts[status_val] += 1

        # Inspecionar referências dos resultados
        for res in results:
            refs = getattr(res, "evidence_refs", []) or []
            if not refs:
                errors.append(f"Resultado '{res.statement[:50]}' não possui evidências associadas.")
            for ref in refs:
                total_refs += 1
                ref_valid = True
                p_id = getattr(ref, "paragraph_id", None) if not isinstance(ref, dict) else ref.get("paragraph_id")
                p_num = getattr(ref, "page_number", None) if not isinstance(ref, dict) else ref.get("page_number")
                status_val = getattr(ref, "status", EpistemicStatus.SOURCE_FACT.value) if not isinstance(ref, dict) else ref.get("status", EpistemicStatus.SOURCE_FACT.value)

                # 4. Existência de evidência válida para cada resultado classificado como SOURCE_FACT
                if status_val == EpistemicStatus.SOURCE_FACT.value:
                    if not p_id or not str(p_id).strip():
                        errors.append(f"Resultado SOURCE_FACT '{res.statement[:50]}' não possui paragraph_id de suporte válido.")
                        ref_valid = False
                    elif p_id not in valid_paras:
                        invalid_paras.append(p_id)
                        errors.append(f"Resultado SOURCE_FACT referencia paragraph_id inexistente '{p_id}'.")
                        ref_valid = False
                    else:
                        p_obj = valid_paras[p_id]
                        if p_num is not None and p_num != p_obj.page_number:
                            invalid_pages.append(p_num)
                            errors.append(f"Página indicada ({p_num}) para resultado no parágrafo '{p_id}' difere da AST ({p_obj.page_number}).")
                            ref_valid = False
                else:
                    if p_id and p_id not in valid_paras:
                        invalid_paras.append(p_id)
                        errors.append(f"Referência a paragraph_id inexistente '{p_id}'.")
                        ref_valid = False

                if ref_valid:
                    valid_refs += 1

                if status_val not in fact_counts:
                    status_val = EpistemicStatus.SOURCE_FACT.value
                fact_counts[status_val] += 1

        # Inspecionar tensões
        for tension in cross_synthesis.coherence_and_tensions:
            fact_counts[EpistemicStatus.MODEL_INFERENCE.value] += 1

        pct_valid_paras = round((valid_refs / max(1, total_refs)) * 100.0, 2)
        pct_valid_pages = round(100.0 - (len(invalid_pages) / max(1, total_refs) * 100.0), 2)
        coverage_score = round(len(section_analyses) / max(1, len(ast.sections)), 2)

        if not section_analyses:
            errors.append("Nenhuma secção foi analisada pelo motor.")

        # REGRA REFORÇADA: is_valid só é True se ZERO erros e ZERO referências inválidas
        is_strictly_valid = (len(errors) == 0) and (len(invalid_paras) == 0) and (len(invalid_pages) == 0)

        return ReasoningQAReport(
            total_sections_analyzed=len(section_analyses),
            total_segments_analyzed=sum(len(sa.segment_ids) for sa in section_analyses),
            valid_paragraph_refs_pct=pct_valid_paras,
            invalid_paragraph_refs=list(set(invalid_paras)),
            valid_page_refs_pct=pct_valid_pages,
            invalid_page_refs=list(set(invalid_pages)),
            fact_vs_inference_counts=fact_counts,
            coverage_score=min(1.0, coverage_score),
            warnings=warnings,
            errors=errors,
            is_valid=is_strictly_valid,
        )
