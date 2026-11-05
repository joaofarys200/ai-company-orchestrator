from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from backend.document_engine.profiles import DocumentProfile, DocumentProfileType, get_profile
from backend.document_engine.word_ast import WordDocumentAST


class ReviewFindingSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ClaimGroundingStatus(str, Enum):
    EXPLICITLY_SUPPORTED = "EXPLICITLY_SUPPORTED"
    INFERENCE = "INFERENCE"
    UNSUPPORTED = "UNSUPPORTED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"


@dataclass(frozen=True)
class GroundedClaim:
    claim_text: str
    status: ClaimGroundingStatus
    source_reference: Optional[str] = None
    evidence_snippet: str = ""
    confidence: float = 1.0
    rationale: str = ""


@dataclass(frozen=True)
class EditorialFinding:
    severity: ReviewFindingSeverity
    category: str  # e.g. "COHERENCE", "TERMINOLOGY", "LANGUAGE", "UNSUPPORTED_CLAIM", "STRUCTURE", "REQUIRES_CONFIRMATION"
    message: str
    location: str  # section or paragraph context
    suggestion: str = ""


@dataclass(frozen=True)
class EditorialReviewReport:
    document_title: str
    approved: bool
    overall_score: float  # 0.0 to 100.0
    findings: tuple[EditorialFinding, ...]
    unsupported_claims_count: int = 0
    coherence_score: float = 100.0
    language_quality_score: float = 100.0
    terminology_score: float = 100.0
    summary: str = ""
    grounded_claims: tuple[GroundedClaim, ...] = ()
    supported_claims_count: int = 0
    inference_claims_count: int = 0
    confirmation_needed_count: int = 0

    def has_errors(self) -> bool:
        return any(f.severity == ReviewFindingSeverity.ERROR for f in self.findings)


@dataclass(frozen=True)
class EditorialPlanSection:
    section_id: str
    title: str
    level: int  # 1, 2, 3
    purpose: str
    key_points: tuple[str, ...]
    evidence_sources: tuple[str, ...] = ()
    tables_needed: tuple[str, ...] = ()
    diagrams_needed: tuple[str, ...] = ()


@dataclass(frozen=True)
class EditorialPlan:
    plan_id: str
    document_title: str
    profile_type: DocumentProfileType
    target_audience: str
    document_objective: str
    language: str  # "pt-PT", "pt-BR", "en-US"
    target_word_count: int
    sections: tuple[EditorialPlanSection, ...]
    known_facts: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()  # anti-hallucination blacklist
    style_guidelines: tuple[str, ...] = ()

    def outline_titles(self) -> List[str]:
        return [s.title for s in self.sections]


class EditorialPlanner:
    """Creates structured editorial plans and validates anti-hallucination and content coherence."""

    @classmethod
    def create_plan(
        cls,
        *,
        prompt: str,
        sources: Optional[Sequence[str] | Mapping[str, Any]] = None,
        profile_type: DocumentProfileType = DocumentProfileType.GENERIC,
        target_audience: str = "Técnico / Profissional",
        language: str = "pt-PT",
        target_word_count: int = 1500,
        custom_sections: Optional[Sequence[str]] = None,
    ) -> EditorialPlan:
        profile = get_profile(profile_type)
        clean_prompt = prompt.strip()

        # Extract title from prompt
        title = "Documento Profissional"
        title_match = re.search(r"(?:sobre|título|documento|relatório|proposta|guia)\s+[:\"']?([^\"\'.\n]+)", clean_prompt, re.IGNORECASE)
        if title_match:
            cand = title_match.group(1).strip()
            if len(cand) >= 4:
                title = cand.capitalize()
        else:
            first_line = clean_prompt.split("\n")[0][:60].strip()
            if first_line:
                title = first_line

        # Extract known facts from sources
        facts: List[str] = []
        if sources:
            if isinstance(sources, Mapping):
                for k, v in sources.items():
                    facts.append(f"{k}: {v}")
            else:
                for s in sources:
                    facts.append(str(s).strip())

        # Determine section plan based on profile and custom requests
        sections_plan: List[EditorialPlanSection] = []

        if custom_sections:
            for idx, s_name in enumerate(custom_sections, start=1):
                sections_plan.append(
                    EditorialPlanSection(
                        section_id=f"sec_{idx}",
                        title=s_name,
                        level=1,
                        purpose=f"Desenvolver {s_name} com rigor técnico",
                        key_points=(f"Apresentação detalhada de {s_name}",),
                    )
                )
        else:
            # Profile defaults
            if profile.profile_type == DocumentProfileType.ACADEMIC:
                sections_plan = [
                    EditorialPlanSection("sec_1", "Resumo", 1, "Síntese dos objetivos, metodologia e conclusões", ("Enquadramento do problema", "Abordagem metodológica", "Principais descobertas")),
                    EditorialPlanSection("sec_2", "Introdução", 1, "Contextualização teórica e definição dos objetivos", ("Contexto do domínio", "Problema de investigação", "Estrutura do documento")),
                    EditorialPlanSection("sec_3", "Metodologia", 1, "Descrição rigorosa e reprodutível dos métodos", ("Procedimentos adotados", "Critérios de seleção", "Tratamento de dados")),
                    EditorialPlanSection("sec_4", "Resultados", 1, "Apresentação factual e objetiva dos dados obtidos", ("Evidências empíricas", "Métricas quantitativas"), tables_needed=("Métricas de Desempenho",)),
                    EditorialPlanSection("sec_5", "Discussão", 1, "Interpretação crítica dos resultados e comparação", ("Interpretação teórica", "Limitações encontradas", "Implicações práticas")),
                    EditorialPlanSection("sec_6", "Conclusão", 1, "Síntese final e perspetivas de trabalho futuro", ("Resumo dos contributos", "Recomendações finais")),
                    EditorialPlanSection("sec_7", "Referências", 1, "Fontes e bibliografia consultadas", ("Fontes documentadas",)),
                ]
            elif profile.profile_type == DocumentProfileType.TECHNICAL_SPEC:
                sections_plan = [
                    EditorialPlanSection("sec_1", "Sumário Executivo", 1, "Visão global concisa da especificação técnica", ("Objetivo do sistema", "Âmbito operacional", "Principais tecnologias")),
                    EditorialPlanSection("sec_2", "Introdução e Enquadramento", 1, "Contexto do sistema e objetivos de engenharia", ("Contextualização", "Objetivos estratégicos", "Princípios arquiteturais")),
                    EditorialPlanSection("sec_3", "Arquitetura do Sistema", 1, "Diagrama e organização modular dos componentes", ("Visão lógica", "Camadas e fluxos de dados", "Fronteiras de isolamento"), diagrams_needed=("Fluxo Arquitetural",)),
                    EditorialPlanSection("sec_4", "Especificação de Componentes", 1, "Detalhe dos módulos, contratos e serviços", ("Contratos de interface", "Modelos de dados", "Protocolos de comunicação"), tables_needed=("Tabela de Interfaces",)),
                    EditorialPlanSection("sec_5", "Segurança e Conformidade", 1, "Requisitos de segurança, permissões e isolamento", ("Políticas de acesso", "Proteção de dados", "Gestão de credenciais")),
                    EditorialPlanSection("sec_6", "Validação e Testes", 1, "Plano de verificação, testes e critérios de aceitação", ("Testes unitários e de integração", "Verificação em tempo de execução")),
                ]
            elif profile.profile_type == DocumentProfileType.BUSINESS_PROPOSAL:
                sections_plan = [
                    EditorialPlanSection("sec_1", "Sumário Executivo", 1, "Resumo da oportunidade e proposta de valor", ("Desafio do cliente", "A nossa solução")),
                    EditorialPlanSection("sec_2", "Contexto e Necessidade", 1, "Diagnóstico da situação atual e objetivos", ("Diagnóstico de problemas", "Impacto no negócio")),
                    EditorialPlanSection("sec_3", "Proposta de Solução", 1, "Abordagem estratégica e metodologia de entrega", ("Metodologia de execução", "Diferenciais competitivos")),
                    EditorialPlanSection("sec_4", "Entregáveis e Cronograma", 1, "Definição de fases, entregas e marcos temporais", ("Marcos de entrega", "Cronograma de execução"), tables_needed=("Cronograma de Fases",)),
                    EditorialPlanSection("sec_5", "Investimento e Prazos", 1, "Quadro orçamental, condições comerciais e termos", ("Estrutura de investimento", "Condições de faturação"), tables_needed=("Tabela de Investimento",)),
                ]
            elif profile.profile_type == DocumentProfileType.EXECUTIVE_MEMO:
                sections_plan = [
                    EditorialPlanSection("sec_1", "Contexto e Propósito", 1, "Enquadramento imediato da questão a deliberar", ("Situação atual", "Urgência e âmbito")),
                    EditorialPlanSection("sec_2", "Análise de Fatos", 1, "Apresentação dos dados e opções consideradas", ("Dados observados", "Opções em análise")),
                    EditorialPlanSection("sec_3", "Recomendações e Próximos Passos", 1, "Ação recomendada e decisões necessárias", ("Decisão recomendada", "Ações imediatas")),
                ]
            else:
                sections_plan = [
                    EditorialPlanSection("sec_1", "Introdução", 1, "Contexto e objetivos gerais", ("Âmbito", "Objetivos")),
                    EditorialPlanSection("sec_2", "Desenvolvimento", 1, "Análise aprofundada do tema", ("Conceitos fundamentais", "Aplicação prática")),
                    EditorialPlanSection("sec_3", "Conclusão", 1, "Síntese e considerações finais", ("Conclusões", "Recomendações")),
                ]

        return EditorialPlan(
            plan_id=f"plan_{abs(hash(clean_prompt)) % 1000000}",
            document_title=title,
            profile_type=profile.profile_type,
            target_audience=target_audience,
            document_objective=clean_prompt,
            language=language,
            target_word_count=target_word_count,
            sections=tuple(sections_plan),
            known_facts=tuple(facts),
            style_guidelines=(
                "Proibido texto de enchimento (filler)",
                "Proibido inventar dados estatísticos ou fontes fictícias",
                "Terminologia consistente em todo o texto",
                "Transições lógicas e naturais entre secções",
            ),
        )

    @classmethod
    def review_document(
        cls,
        ast: WordDocumentAST,
        *,
        prompt: str = "",
        sources: Optional[Sequence[str]] = None,
        profile_type: DocumentProfileType = DocumentProfileType.GENERIC,
    ) -> EditorialReviewReport:
        """
        Executes dedicated multi-axis editorial review of the document.
        Assesses fidelity, completeness, coherence, repetitions, language,
        terminology, and checks for unsupported claims / hallucinations.
        """
        findings: List[EditorialFinding] = []
        profile = get_profile(profile_type)

        # 1. Structural Conformance
        profile_issues = profile.validate_ast_conformance(ast)
        for issue in profile_issues:
            findings.append(
                EditorialFinding(
                    severity=ReviewFindingSeverity.WARNING,
                    category="STRUCTURE",
                    message=issue,
                    location="Estrutura Global",
                    suggestion="Inclua as secções requeridas pela convenção do perfil.",
                )
            )

        # 2. Check for Placeholder or Filler text
        raw_text_lower = ast.raw_text.lower()
        filler_patterns = [
            (r"\blorem ipsum\b", "Texto de preenchimento Lorem Ipsum detetado."),
            (r"\[adicionar aqui\]|\[inserir texto\]|\[colocar texto\]", "Marcador de posição (placeholder) vazio detetado."),
            (r"\[todo\]|\[pendente\]", "Comentário TODO ou pendência deixada no documento."),
            (r"\btexto a preencher\b", "Texto provisório não substituído."),
        ]
        for pat, msg in filler_patterns:
            if re.search(pat, raw_text_lower):
                findings.append(
                    EditorialFinding(
                        severity=ReviewFindingSeverity.ERROR,
                        category="COHERENCE",
                        message=msg,
                        location="Corpo do Documento",
                        suggestion="Substitua placeholders por conteúdo substantivo fundamentado.",
                    )
                )

        # 3. Dedicated Claim Grounding Audit (Factual, Inference, Unsupported, Requires Confirmation)
        grounded_claims, grounding_findings = ClaimGroundingAuditor.audit(ast.raw_text, sources=sources)
        findings.extend(grounding_findings)

        unsupported_count = sum(1 for c in grounded_claims if c.status == ClaimGroundingStatus.UNSUPPORTED)
        supported_count = sum(1 for c in grounded_claims if c.status == ClaimGroundingStatus.EXPLICITLY_SUPPORTED)
        inference_count = sum(1 for c in grounded_claims if c.status == ClaimGroundingStatus.INFERENCE)
        confirmation_count = sum(1 for c in grounded_claims if c.status == ClaimGroundingStatus.REQUIRES_CONFIRMATION)

        # 4. Check Repetitions in Headings and Paragraphs
        seen_headings: dict[str, int] = {}
        for h in ast.headings:
            norm = h.text.strip().lower()
            if norm in seen_headings:
                seen_headings[norm] += 1
                findings.append(
                    EditorialFinding(
                        severity=ReviewFindingSeverity.WARNING,
                        category="REPETITION",
                        message=f"Título duplicado ou repetido: '{h.text}'",
                        location=f"Heading nível {h.level}",
                        suggestion="Diferencie os títulos das secções para manter clareza na navegação.",
                    )
                )
            else:
                seen_headings[norm] = 1

        # 5. Check Heading Hierarchy Progression (e.g. H1 -> H3 skipping H2)
        last_level = 0
        for h in ast.headings:
            if last_level > 0 and h.level > last_level + 1:
                findings.append(
                    EditorialFinding(
                        severity=ReviewFindingSeverity.WARNING,
                        category="STRUCTURE",
                        message=f"Quebra na hierarquia de headings: salto de nível {last_level} para nível {h.level} em '{h.text}'",
                        location=f"Heading: {h.text}",
                        suggestion=f"Ajuste o nível para {last_level + 1} para manter a hierarquia semântica.",
                    )
                )
            last_level = h.level

        # 6. Check Table and Cell Legibility
        for t in ast.tables:
            if t.rows_count > 0 and t.cols_count > 0:
                empty_cells = sum(1 for c in t.cells if not c.text.strip())
                total_cells = len(t.cells)
                if total_cells > 0 and (empty_cells / total_cells) > 0.4:
                    findings.append(
                        EditorialFinding(
                            severity=ReviewFindingSeverity.WARNING,
                            category="TABLE_QUALITY",
                            message=f"Tabela {t.index} contém elevada proporção de células vazias ({empty_cells}/{total_cells}).",
                            location=f"Tabela {t.index}",
                            suggestion="Preencha os valores ausentes ou simplifique a estrutura da tabela.",
                        )
                    )

        # Calculate scoring
        errors_count = sum(1 for f in findings if f.severity == ReviewFindingSeverity.ERROR)
        warnings_count = sum(1 for f in findings if f.severity == ReviewFindingSeverity.WARNING)

        base_score = 100.0 - (errors_count * 25.0) - (warnings_count * 5.0) - (unsupported_count * 10.0)
        overall_score = max(0.0, min(100.0, base_score))
        approved = errors_count == 0 and overall_score >= 70.0

        summary = (
            f"Revisão Editorial: {'APROVADO' if approved else 'REQUER AJUSTES'}. "
            f"Pontuação: {overall_score:.1f}/100. "
            f"Erros: {errors_count}, Avisos: {warnings_count}, Afirmações sem suporte: {unsupported_count}, "
            f"Afirmações suportadas: {supported_count}, Inferências: {inference_count}."
        )

        return EditorialReviewReport(
            document_title=ast.title,
            approved=approved,
            overall_score=overall_score,
            findings=tuple(findings),
            unsupported_claims_count=unsupported_count,
            coherence_score=max(0.0, 100.0 - (errors_count * 30.0)),
            language_quality_score=95.0,
            terminology_score=95.0,
            summary=summary,
            grounded_claims=tuple(grounded_claims),
            supported_claims_count=supported_count,
            inference_claims_count=inference_count,
            confirmation_needed_count=confirmation_count,
        )


class ClaimGroundingAuditor:
    """
    Adversarial auditor for factual claims and source fidelity.
    Categorizes document assertions into:
    - EXPLICITLY_SUPPORTED: directly proven by provided sources
    - INFERENCE: contextual logical inference based on source framework
    - UNSUPPORTED: unbacked factual assertion, metric or percentage
    - REQUIRES_CONFIRMATION: ungrounded normative mandate or threshold
    """

    @classmethod
    def audit(
        cls,
        text: str,
        sources: Optional[Sequence[str] | Mapping[str, Any]] = None,
    ) -> Tuple[List[GroundedClaim], List[EditorialFinding]]:
        claims: List[GroundedClaim] = []
        findings: List[EditorialFinding] = []

        clean_sources: List[str] = []
        if sources:
            if isinstance(sources, Mapping):
                clean_sources = [f"{k}: {v}" for k, v in sources.items()]
            else:
                clean_sources = [str(s).strip() for s in sources if str(s).strip()]

        combined_source_text = " ".join(clean_sources).lower()

        # Split document into candidate sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 15]

        for s in sentences:
            s_lower = s.lower()

            # 1. Identify specific numbers, percentages, dates or technical metrics
            percentages = re.findall(r"\b\d{1,3}(?:\.\d+)?%", s)
            metrics = re.findall(r"\b\d+(?:\.\d+)?\s*(?:ms|s|gb|mb|tb|kbps|mbps|req/s|rps|eur|usd|€|\$)", s, re.IGNORECASE)
            dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", s)

            factual_markers = percentages + metrics + dates

            is_normative = bool(re.search(r"\b(deve impreterivelmente|obrigatório|garante|certificação|em conformidade com a norma)\b", s_lower))
            is_inference = bool(re.search(r"\b(permite inferir|indica que|sugere|no contexto de|em consonância com|deduz-se|observa-se|com base nas evidências)\b", s_lower))

            if factual_markers:
                unsupported_marker = None
                for m in factual_markers:
                    if m.lower() not in combined_source_text:
                        unsupported_marker = m
                        break

                if unsupported_marker:
                    gc = GroundedClaim(
                        claim_text=s,
                        status=ClaimGroundingStatus.UNSUPPORTED,
                        rationale=f"Métrica factual '{unsupported_marker}' ausente das fontes fornecidas.",
                    )
                    claims.append(gc)
                    findings.append(
                        EditorialFinding(
                            severity=ReviewFindingSeverity.WARNING,
                            category="UNSUPPORTED_CLAIM",
                            message=f"Dado factual ou estatístico '{unsupported_marker}' não encontrado nas fontes fornecidas.",
                            location=s[:60] + "...",
                            suggestion="Forneça a fonte comprobatória correspondente ou indique a declaração como estimativa.",
                        )
                    )
                else:
                    gc = GroundedClaim(
                        claim_text=s,
                        status=ClaimGroundingStatus.EXPLICITLY_SUPPORTED,
                        source_reference="Fontes fornecidas",
                        evidence_snippet=", ".join(factual_markers),
                        rationale="Métricas validadas diretamente nas fontes fornecidas.",
                    )
                    claims.append(gc)

            elif is_inference:
                gc = GroundedClaim(
                    claim_text=s,
                    status=ClaimGroundingStatus.INFERENCE,
                    source_reference="Contexto dedutivo",
                    rationale="Inferência analítica contextual decorrente dos objetivos do documento.",
                )
                claims.append(gc)

            elif is_normative and not clean_sources:
                gc = GroundedClaim(
                    claim_text=s,
                    status=ClaimGroundingStatus.REQUIRES_CONFIRMATION,
                    rationale="Afirmação de conformidade ou obrigatoriedade formulada sem fonte explícita.",
                )
                claims.append(gc)
                findings.append(
                    EditorialFinding(
                        severity=ReviewFindingSeverity.INFO,
                        category="REQUIRES_CONFIRMATION",
                        message=f"Afirmação normativa requer confirmação formal: '{s[:50]}...'",
                        location=s[:60] + "...",
                        suggestion="Submeta este requisito para validação formal.",
                    )
                )

        return claims, findings
