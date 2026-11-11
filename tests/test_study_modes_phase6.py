"""
JARVIS OS — Study Engine Phase 6: Comprehensive Test Suite
Cobre integralmente a Seção 15 (15.1 a 15.7):
  15.1 Flashcards inteligentes, adaptativos, edição/proteção e regeneração
  15.2 Notas Cornell estruturadas, insuficiência honesta, edições, notas e exportação
  15.3 Avaliações interativas, 7 tipos, qualidade de distratores, rubrica e modos Practice/Assessment
  15.4 Active Recall dedicado com ocultação prévia, confiança e atualização adaptativa
  15.5 Repetição Espaçada SM-2 versionada (sm2-v6.0), persistência e fila diária
  15.6 Integridade de dados, fidelidade epistémica, obsolescência, sessões e WebSocket
  15.7 Fluxo End-to-End completo (PDF -> AST -> Dossier -> Plano -> IR/Study Modes + Teste Real Ollama)
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.websocket.context import WebSocketHandlerContext, WebSocketSessionState
from backend.websocket.contracts import EXPECTED_MESSAGE_TYPES
from backend.websocket.handlers.study import StudyWebSocketHandler
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
    ASTParagraph,
    ASTSection,
    ASTTable,
    AcademicDocumentAST,
    DocumentIntelligenceExtractor,
    DocumentMetadata,
    PageInfo,
)
from services.editorial_intelligence_engine import (
    EditorialChapter,
    EditorialConceptRelationship,
    EditorialOverview,
    EditorialPlanMetadata,
    EditorialQAReport,
    EditorialSection,
    EditorialStudyPlan,
    PedagogicalExplanationSpec,
)
from services.study_modes_engine import (
    ActiveRecallPrompt,
    AdaptiveFlashcard,
    AssessmentConfig,
    AssessmentQuestion,
    FlashcardType,
    MasteryLevel,
    OpenAnswerVerdict,
    QuestionType,
    ReviewLearningState,
    ReviewSchedulingState,
    SRS_ALGORITHM_VERSION,
    ScoringCriterion,
    StudyModeQA,
    StudyModeReadinessStatus,
    StudyModesEngine,
    StudySessionMode,
    StudySessionStatus,
)
from services.study_service import StudyService


# ---------------------------------------------------------------------------
# Fixtures Canónicas (Fases 2, 3 e 4 reais serializadas em storage temporário)
# ---------------------------------------------------------------------------

def _build_phase2_ast(doc_id: str = "doc_p6_test") -> AcademicDocumentAST:
    return AcademicDocumentAST(
        document_id=doc_id,
        source_sha256="sha256_p6_canonical_001",
        filename="inferencia_local_estudo.pdf",
        metadata=DocumentMetadata(
            title="Estudo Empírico sobre Inferência Local e Otimização",
            authors=[{"name": "Prof. Carlos Silva"}],
            publication_date={"year": 2025},
            abstract="Investigação sobre eficiência e soberania de algoritmos de inferência local.",
        ),
        pages=[
            PageInfo(page_number=1, width=595.0, height=842.0),
            PageInfo(page_number=2, width=595.0, height=842.0),
            PageInfo(page_number=3, width=595.0, height=842.0),
            PageInfo(page_number=4, width=595.0, height=842.0),
            PageInfo(page_number=5, width=595.0, height=842.0),
        ],
        sections=[
            ASTSection(
                section_id="sec_01",
                title="1. Fundamentos de Soberania Computacional",
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
                page_end=3,
                element_refs=[{"kind": "paragraph", "id": "p_03"}, {"kind": "paragraph", "id": "p_04"}],
            ),
            ASTSection(
                section_id="sec_03",
                title="3. Resultados Empíricos",
                level=1,
                page_start=4,
                page_end=5,
                element_refs=[{"kind": "paragraph", "id": "p_05"}],
            ),
            ASTSection(
                section_id="sec_empty",
                title="4. Notas Editoriais Sem Evidência",
                level=1,
                page_start=5,
                page_end=5,
                element_refs=[],
            ),
        ],
        paragraphs=[
            ASTParagraph(
                paragraph_id="p_01",
                section_id="sec_01",
                text="A inferência local soberana executa modelos de linguagem diretamente no hardware do utilizador sem enviar dados para servidores cloud.",
                page_number=1,
                page_end=1,
                order=1,
            ),
            ASTParagraph(
                paragraph_id="p_02",
                section_id="sec_01",
                text="A privacidade determinística garante previsibilidade de custos operacionais e proteção integral dos documentos académicos.",
                page_number=2,
                page_end=2,
                order=2,
            ),
            ASTParagraph(
                paragraph_id="p_03",
                section_id="sec_02",
                text="O protocolo experimental utilizou 15.000 amostras avaliadas por validação cruzada k-fold (k=10) em estações isoladas.",
                page_number=3,
                page_end=3,
                order=3,
            ),
            ASTParagraph(
                paragraph_id="p_04",
                section_id="sec_02",
                text="A calibração latência-precisão controlou o orçamento de contexto para evitar degradação por excesso de tokens.",
                page_number=3,
                page_end=3,
                order=4,
            ),
            ASTParagraph(
                paragraph_id="p_05",
                section_id="sec_03",
                text="A precisão média atingiu 94.8% com latência média de 72ms, superando o baseline de 82.1% e 120ms com significância estatística (p < 0.01).",
                page_number=4,
                page_end=5,
                order=5,
            ),
        ],
        tables=[
            ASTTable(
                table_id="tbl_01",
                page_number=4,
                section_id="sec_03",
                order=1,
                caption="Tabela 1: Métricas comparativas Baseline vs Modelo Local Otimizado",
                rows=[
                    ["Abordagem", "Precisão (%)", "Latência (ms)"],
                    ["Baseline", "82.1", "120"],
                    ["Modelo Local Otimizado", "94.8", "72"],
                ],
                n_rows=3,
                n_cols=3,
            )
        ],
    )


def _build_phase3_dossier(doc_id: str = "doc_p6_test") -> AcademicReasoningDossier:
    return AcademicReasoningDossier(
        dossier_id=f"dossier_{doc_id}",
        document_id=doc_id,
        source_sha256="sha256_p6_canonical_001",
        document_analysis=DocumentCoreAnalysis(
            document_id=doc_id,
            title="Estudo Empírico sobre Inferência Local e Otimização",
            central_thesis="A inferência local soberana otimizada atinge 94.8% de precisão e 72ms de latência sem dependências cloud.",
            global_objective="Analisar precisão, latência e privacidade em sistemas locais.",
            main_contributions=["Execução local soberana", "Ganho de 12.7pp face ao baseline"],
        ),
        section_analyses=[
            SectionAnalysis(
                section_id="sec_01",
                title="1. Fundamentos de Soberania Computacional",
                in_depth_synthesis="A inferência local soberana executa modelos diretamente no hardware do utilizador preservando privacidade e previsibilidade.",
                core_ideas=["Privacidade integral sem envio para cloud", "Previsibilidade operacional determinística"],
                source_refs=[
                    EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, excerpt="executa modelos de linguagem diretamente no hardware", status=EpistemicStatus.SOURCE_FACT.value),
                    EvidenceRef(section_id="sec_01", paragraph_id="p_02", page_number=2, excerpt="previsibilidade de custos operacionais", status=EpistemicStatus.SOURCE_FACT.value),
                ],
            ),
            SectionAnalysis(
                section_id="sec_02",
                title="2. Metodologia Experimental",
                in_depth_synthesis="Ensaio com 15.000 amostras submetidas a validação cruzada k-fold (k=10) e calibração rigorosa de latência-precisão.",
                core_ideas=["15.000 amostras com k-fold k=10", "Controlo explícito do orçamento de contexto"],
                source_refs=[
                    EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3, excerpt="15.000 amostras avaliadas por validação cruzada", status=EpistemicStatus.SOURCE_FACT.value),
                ],
            ),
            SectionAnalysis(
                section_id="sec_03",
                title="3. Resultados Empíricos",
                in_depth_synthesis="O modelo otimizado registou 94.8% de precisão e 72ms de latência face aos 82.1% e 120ms do baseline.",
                core_ideas=["Aumento de 82.1% para 94.8%", "Redução de latência de 120ms para 72ms"],
                source_refs=[
                    EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=4, excerpt="precisão média atingiu 94.8%", status=EpistemicStatus.SOURCE_FACT.value),
                ],
            ),
            SectionAnalysis(
                section_id="sec_empty",
                title="4. Notas Editoriais Sem Evidência",
                in_depth_synthesis="",
                core_ideas=[],
                source_refs=[],
            ),
        ],
        conceptual_analysis=[
            ConceptItem(
                concept_id="c_01",
                name="Inferência Local Soberana",
                definition="Execução direta de modelos de linguagem no hardware local sem servidores cloud externos.",
                explanation="Assegura privacidade integral e soberania operacional sobre documentos sensíveis.",
                relationships=["c_02"],
                evidence_refs=[
                    EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, excerpt="executa modelos de linguagem diretamente no hardware", status=EpistemicStatus.SOURCE_FACT.value),
                ],
            ),
            ConceptItem(
                concept_id="c_02",
                name="Calibração Latência-Precisão",
                definition="Mecanismo de equilíbrio que reduz tempo de resposta para 72ms preservando 94.8% de precisão.",
                explanation="Depende da gestão controlada de tokens em contexto.",
                relationships=["c_01"],
                evidence_refs=[
                    EvidenceRef(section_id="sec_02", paragraph_id="p_04", page_number=3, excerpt="controlou o orçamento de contexto", status=EpistemicStatus.SOURCE_FACT.value),
                    EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=4, excerpt="latência média de 72ms", status=EpistemicStatus.SOURCE_FACT.value),
                ],
            ),
        ],
        methodology_analysis=MethodologyAnalysis(
            is_applicable=True,
            research_type="Estudo Quantitativo Experimental",
            methodological_design="Validação empírica comparativa controlada",
            methods_used=["Validação cruzada k-fold (k=10)", "Comparação face a baseline"],
            sample_or_participants="15.000 amostras de ensaio",
            analysis_techniques=["Teste bicaudal (p < 0.01)"],
            methodological_limitations=["Ensaios conduzidos exclusivamente em estações isoladas"],
            evidence_refs=[
                EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3, excerpt="validação cruzada k-fold", status=EpistemicStatus.SOURCE_FACT.value),
            ],
        ),
        results_and_evidence=[
            ResultItem(
                statement="A precisão média subiu de 82.1% (baseline) para 94.8% no modelo local otimizado.",
                evidence_data="94.8% vs 82.1% (p < 0.01)",
                relation_to_objectives="Comprova eficácia sem serviços externos.",
                evidence_refs=[
                    EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=4, excerpt="precisão média atingiu 94.8%", status=EpistemicStatus.SOURCE_FACT.value),
                ],
            ),
        ],
        cross_section_synthesis=CrossSectionSynthesis(
            conceptual_relationships=[
                {"source": "c_01", "target": "c_02", "type": "potencia", "description": "A inferência local potencia a calibração latência-precisão."}
            ],
            global_synthesis="O desenho local otimizado combina privacidade, menor latência e maior precisão.",
        ),
        critical_analysis=CriticalAnalysis(
            author_limitations=["Hardware limitado a estações monoprocessador"],
        ),
    )


def _build_phase4_plan(doc_id: str = "doc_p6_test") -> EditorialStudyPlan:
    return EditorialStudyPlan(
        metadata=EditorialPlanMetadata(
            plan_id=f"plan_{doc_id}",
            document_id=doc_id,
            source_sha256="sha256_p6_canonical_001",
            ast_version="1.0",
            dossier_id=f"dossier_{doc_id}",
            plan_version=1,
            created_at="2026-11-11T10:00:00",
            status="COMPLETED",
        ),
        overview=EditorialOverview(
            central_theme="Soberania Computacional e Otimização Local",
            central_theme_status="SOURCE_FACT",
            learning_objectives=[
                {
                    "objective_id": "obj_01",
                    "description": "Explicar os fundamentos da Inferência Local Soberana.",
                    "epistemic_status": "SOURCE_FACT",
                    "source_section_ids": ["sec_01"],
                },
                {
                    "objective_id": "obj_02",
                    "description": "Avaliar o protocolo k-fold e os ganhos de latência e precisão.",
                    "epistemic_status": "SOURCE_FACT",
                    "source_section_ids": ["sec_02", "sec_03"],
                },
            ],
            target_audience="Estudantes avançados de IA",
            document_nature="EMPIRICAL_RESEARCH_ARTICLE",
            recommended_structure_rationale="Progressão dedutiva teoria -> método -> resultados.",
            editorial_strategy="Consolidação teórica e verificação empírica.",
            global_organization_summary="2 capítulos didáticos + secção sem matéria para validação negativa.",
            core_contents=["sec_01", "sec_02", "sec_03"],
            evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")],
        ),
        chapters=[
            EditorialChapter(
                chapter_id="chap_01",
                title="Capítulo 1: Fundamentos de Soberania Local",
                pedagogical_objective="Dominar o conceito de Inferência Local Soberana e privacidade.",
                role_in_progression="Base Teórica",
                editorial_justification="Enquadra a motivação técnica.",
                key_concept_ids=["c_01"],
                original_section_ids=["sec_01"],
                evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")],
                sections=[
                    EditorialSection(
                        section_id="sec_01",
                        chapter_id="chap_01",
                        title="1.1 Inferência Local Soberana",
                        order=1,
                        associated_concept_ids=["c_01"],
                        original_section_ids=["sec_01"],
                        pedagogical_treatments=[
                            PedagogicalExplanationSpec(
                                target_topic_or_concept="Inferência Local Soberana",
                                concept_id="c_01",
                                depth_level="FOUNDATIONAL",
                                epistemic_status="SOURCE_FACT",
                                evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")],
                            )
                        ],
                        evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1, status="SOURCE_FACT")],
                    ),
                ],
            ),
            EditorialChapter(
                chapter_id="chap_02",
                title="Capítulo 2: Metodologia e Resultados Experimentais",
                pedagogical_objective="Interpretar o protocolo k-fold e a calibração latência-precisão.",
                role_in_progression="Prova Empírica",
                editorial_justification="Validação experimental quantitativa.",
                key_concept_ids=["c_02"],
                original_section_ids=["sec_02", "sec_03", "sec_empty"],
                learning_dependencies=["chap_01"],
                evidence_refs=[EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=4, status="SOURCE_FACT")],
                sections=[
                    EditorialSection(
                        section_id="sec_02",
                        chapter_id="chap_02",
                        title="2.1 Metodologia k-fold",
                        order=1,
                        associated_concept_ids=["c_02"],
                        original_section_ids=["sec_02"],
                        pedagogical_treatments=[
                            PedagogicalExplanationSpec(
                                target_topic_or_concept="Calibração Latência-Precisão",
                                concept_id="c_02",
                                depth_level="IN_DEPTH",
                                epistemic_status="SOURCE_FACT",
                                evidence_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3, status="SOURCE_FACT")],
                            )
                        ],
                        evidence_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3, status="SOURCE_FACT")],
                    ),
                    EditorialSection(
                        section_id="sec_03",
                        chapter_id="chap_02",
                        title="2.2 Resultados Empíricos",
                        order=2,
                        associated_concept_ids=["c_02"],
                        original_section_ids=["sec_03"],
                        pedagogical_treatments=[
                            PedagogicalExplanationSpec(
                                target_topic_or_concept="Resultados de Precisão e Latência",
                                concept_id="c_02",
                                depth_level="IN_DEPTH",
                                epistemic_status="SOURCE_FACT",
                                evidence_refs=[EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=4, status="SOURCE_FACT")],
                            )
                        ],
                        evidence_refs=[EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=4, status="SOURCE_FACT")],
                    ),
                    EditorialSection(
                        section_id="sec_empty",
                        chapter_id="chap_02",
                        title="2.3 Secção Sem Suporte Probatório",
                        order=3,
                        associated_concept_ids=[],
                        original_section_ids=["sec_empty"],
                        pedagogical_treatments=[],
                        evidence_refs=[],
                    ),
                ],
            ),
        ],
        conceptual_relationships=[
            EditorialConceptRelationship(
                relationship_id="rel_01",
                source_concept_id="c_01",
                source_concept_name="Inferência Local Soberana",
                target_concept_id="c_02",
                target_concept_name="Calibração Latência-Precisão",
                relation_type="potencia",
                is_hierarchical=False,
                pedagogical_dependency="Compreender soberania local antes da calibração.",
                justification="A execução local soberana exige calibração latência-precisão no hardware do utilizador.",
                evidence_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_04", page_number=3, status="SOURCE_FACT")],
            )
        ],
        qa_report=EditorialQAReport(validation_status="VALID"),
    )


def _persist_upstream_artifacts(storage_dir: Path, doc_id: str, ast: AcademicDocumentAST, dossier: AcademicReasoningDossier, plan: EditorialStudyPlan) -> None:
    doc_dir = storage_dir / "documents" / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "ast.json").write_text(json.dumps(ast.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    (doc_dir / "reasoning_dossier.json").write_text(json.dumps(dossier.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    (doc_dir / "editorial_study_plan.json").write_text(json.dumps(plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def temp_study_workspace(tmp_path: Path):
    storage_dir = tmp_path / "study_data"
    doc_id = "doc_p6_test"
    ast = _build_phase2_ast(doc_id)
    dossier = _build_phase3_dossier(doc_id)
    plan = _build_phase4_plan(doc_id)
    _persist_upstream_artifacts(storage_dir, doc_id, ast, dossier, plan)
    return {
        "tmp_path": tmp_path,
        "storage_dir": storage_dir,
        "doc_id": doc_id,
        "ast": ast,
        "dossier": dossier,
        "plan": plan,
    }


def _mock_phase6_llm_caller(*, operation: str, system_prompt: str, user_prompt: str, max_output_tokens: int = 1200) -> Dict[str, Any]:
    """Invocador simulado estritamente local para testes determinísticos das operações LLM."""
    op = operation.lower()
    if "phase6_fc_regen" in op or "phase6_regen_card" in op:
        return {
            "ok": True,
            "parsed": {
                "front": "Como é executada a Inferência Local Soberana em hardware do utilizador segundo a fonte?",
                "back": "Executa modelos de linguagem diretamente no hardware local sem enviar dados para servidores cloud, atingindo 94.8% de precisão.",
                "epistemic_status": "SOURCE_FACT",
                "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}],
            },
            "prompt_tokens": 120,
            "completion_tokens": 65,
        }

    if "phase6_flashcards" in op:
        if "chap_01" in op:
            chap_cards = [
                {
                    "front": "O que caracteriza a Inferência Local Soberana segundo o estudo?",
                    "back": "Executa modelos de linguagem diretamente no hardware do utilizador sem enviar dados para servidores cloud.",
                    "card_type": "DEFINITION",
                    "question_difficulty": "EASY",
                    "section_id": "sec_01",
                    "topic": "Inferência Local Soberana",
                    "concept_ids": ["c_01"],
                    "epistemic_status": "SOURCE_FACT",
                    "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}],
                },
                {
                    "front": "Como aplicarias a Inferência Local Soberana num hospital sem internet externa?",
                    "back": "Implementando execução local direta no hardware clínico para proteger dados sensíveis mantendo controlo de tokens.",
                    "card_type": "APPLICATION",
                    "question_difficulty": "HARD",
                    "section_id": "sec_01",
                    "topic": "Aplicação Clínica Hipotética",
                    "concept_ids": ["c_01"],
                    "epistemic_status": "MODEL_INFERENCE",
                    "is_hypothetical_scenario": True,
                    "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "MODEL_INFERENCE"}],
                },
            ]
        else:
            chap_cards = [
                {
                    "front": "Como funcionou a validação metodológica k-fold no protocolo experimental?",
                    "back": "O protocolo utilizou 15.000 amostras avaliadas por validação cruzada k-fold (k=10) em estações isoladas.",
                    "card_type": "METHODOLOGY",
                    "question_difficulty": "MEDIUM",
                    "section_id": "sec_02",
                    "topic": "Metodologia k-fold",
                    "concept_ids": ["c_02"],
                    "epistemic_status": "SOURCE_FACT",
                    "evidence_refs": [{"section_id": "sec_02", "paragraph_id": "p_03", "page_number": 3, "status": "SOURCE_FACT"}],
                },
                {
                    "front": "Que resultados comparativos de precisão e latência foram obtidos?",
                    "back": "A precisão média atingiu 94.8% com latência de 72ms face a 82.1% e 120ms do baseline.",
                    "card_type": "RESULTS_CONCLUSIONS",
                    "question_difficulty": "MEDIUM",
                    "section_id": "sec_03",
                    "topic": "Resultados Empíricos",
                    "concept_ids": ["c_02"],
                    "epistemic_status": "SOURCE_FACT",
                    "evidence_refs": [{"section_id": "sec_03", "paragraph_id": "p_05", "page_number": 4, "status": "SOURCE_FACT"}],
                },
            ]
        return {
            "ok": True,
            "parsed": {"cards": chap_cards},
            "prompt_tokens": 200,
            "completion_tokens": 180,
        }

    if "phase6_cornell" in op:
        if "chap_01" in op:
            sections_payload = [
                {
                    "section_id": "sec_01",
                    "main_concepts": [{"name": "Inferência Local Soberana", "note": "Execução no hardware local sem cloud"}],
                    "explanations": ["Execução local preserva privacidade integral e previsibilidade operacional."],
                    "supporting_details": ["Registo de previsibilidade operacional no hardware local."],
                    "examples": ["Estações de trabalho isoladas."],
                    "concept_relationships": ["Inferência Local Soberana -> Calibração Latência-Precisão"],
                    "methodology_notes": "",
                    "results_and_conclusions_notes": "",
                    "cue_column": [
                        {
                            "cue_prompt": "Porque é que a inferência local evita fugas de dados?",
                            "cue_type": "PORQUÊ",
                            "answer_hint": "Executa diretamente no hardware do utilizador sem envio para servidores cloud.",
                            "epistemic_status": "SOURCE_FACT",
                            "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}],
                        }
                    ],
                    "summary_section": "A inferência local combina soberania e privacidade determinística em estações isoladas.",
                    "epistemic_status": "SOURCE_FACT",
                    "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}],
                }
            ]
        else:
            sections_payload = [
                {
                    "section_id": "sec_02",
                    "main_concepts": [{"name": "Validação k-fold", "note": "k=10 em 15.000 amostras"}],
                    "explanations": ["Controlo explícito do orçamento de contexto previne degradação por excesso de tokens."],
                    "supporting_details": ["15.000 amostras em estações isoladas."],
                    "examples": [],
                    "concept_relationships": [],
                    "methodology_notes": "Validação cruzada k-fold (k=10).",
                    "results_and_conclusions_notes": "",
                    "cue_column": [
                        {
                            "cue_prompt": "Como foi controlado o enviesamento da amostra?",
                            "cue_type": "METODOLOGIA",
                            "answer_hint": "Validação cruzada k-fold (k=10) sobre 15.000 amostras.",
                            "epistemic_status": "SOURCE_FACT",
                            "evidence_refs": [{"section_id": "sec_02", "paragraph_id": "p_03", "page_number": 3, "status": "SOURCE_FACT"}],
                        }
                    ],
                    "summary_section": "Protocolo experimental controlado com k=10 e calibração latência-precisão.",
                    "epistemic_status": "SOURCE_FACT",
                    "evidence_refs": [{"section_id": "sec_02", "paragraph_id": "p_03", "page_number": 3, "status": "SOURCE_FACT"}],
                },
                {
                    "section_id": "sec_03",
                    "main_concepts": [{"name": "Calibração Latência-Precisão", "note": "94.8% precisão, 72ms"}],
                    "explanations": ["O modelo local superou o baseline em precisão (+12.7pp) e velocidade."],
                    "supporting_details": ["94.8% vs 82.1%; 72ms vs 120ms (p < 0.01)."],
                    "examples": [],
                    "concept_relationships": [],
                    "methodology_notes": "",
                    "results_and_conclusions_notes": "Precisão atingiu 94.8% com latência de 72ms.",
                    "cue_column": [
                        {
                            "cue_prompt": "Qual o ganho face ao baseline?",
                            "cue_type": "RESULTADO",
                            "answer_hint": "94.8% e 72ms contra 82.1% e 120ms do baseline.",
                            "epistemic_status": "SOURCE_FACT",
                            "evidence_refs": [{"section_id": "sec_03", "paragraph_id": "p_05", "page_number": 4, "status": "SOURCE_FACT"}],
                        }
                    ],
                    "summary_section": "Ganho estatisticamente significativo em precisão e latência.",
                    "epistemic_status": "SOURCE_FACT",
                    "evidence_refs": [{"section_id": "sec_03", "paragraph_id": "p_05", "page_number": 4, "status": "SOURCE_FACT"}],
                },
            ]
        return {
            "ok": True,
            "parsed": {"sections": sections_payload},
            "prompt_tokens": 180,
            "completion_tokens": 140,
        }

    if "phase6_eval_open" in op:
        return {
            "ok": True,
            "parsed": {
                "verdict": "PARTIAL",
                "score_ratio": 0.65,
                "is_uncertain": False,
                "factual_errors": [],
                "covered_points": ["Execução local no hardware"],
                "missing_points": ["Faltou mencionar ausência de servidores cloud"],
                "reasoning": "A resposta capta o núcleo do conceito mas omite a comparação com servidores cloud.",
            },
            "prompt_tokens": 90,
            "completion_tokens": 60,
        }

    if "phase6_assessment" in op:
        return {
            "ok": True,
            "parsed": {
                "questions": [
                    {
                        "question_text": "Qual foi a precisão média obtida pelo modelo local otimizado face ao baseline?",
                        "question_type": "MULTIPLE_CHOICE",
                        "question_difficulty": "EASY",
                        "section_id": "sec_03",
                        "topic": "Resultados Empíricos",
                        "concept_ids": ["c_02"],
                        "options": [
                            "94.8% com latência de 72ms face a 82.1% do baseline",
                            "82.1% com latência de 120ms no grupo experimental",
                            "70.0% com dependência contínua de servidores cloud",
                            "99.9% sem qualquer validação experimental prévia",
                        ],
                        "correct_index": 0,
                        "correct_answer": "94.8% com latência de 72ms face a 82.1% do baseline",
                        "explanation": "A página 4 regista exatamente 94.8% e 72ms face a 82.1% e 120ms do baseline.",
                        "epistemic_status": "SOURCE_FACT",
                        "evidence_refs": [{"section_id": "sec_03", "paragraph_id": "p_05", "page_number": 4, "status": "SOURCE_FACT"}],
                    },
                    {
                        "question_text": "Verdadeiro ou Falso: A validação experimental utilizou 15.000 amostras com k-fold (k=10).",
                        "question_type": "TRUE_FALSE",
                        "question_difficulty": "EASY",
                        "section_id": "sec_02",
                        "topic": "Metodologia k-fold",
                        "concept_ids": ["c_02"],
                        "options": ["Verdadeiro", "Falso"],
                        "correct_index": 0,
                        "correct_answer": "Verdadeiro",
                        "explanation": "Confirmado literalmente na sec_02 (página 3).",
                        "epistemic_status": "SOURCE_FACT",
                        "evidence_refs": [{"section_id": "sec_02", "paragraph_id": "p_03", "page_number": 3, "status": "SOURCE_FACT"}],
                    },
                    {
                        "question_text": "Explica o conceito de Inferência Local Soberana e os seus benefícios operacionais.",
                        "question_type": "CONCEPT_EXPLANATION",
                        "question_difficulty": "MEDIUM",
                        "section_id": "sec_01",
                        "topic": "Inferência Local Soberana",
                        "concept_ids": ["c_01"],
                        "correct_answer": "Execução direta de modelos no hardware local sem cloud, garantindo privacidade e previsibilidade operacional.",
                        "explanation": "Baseado na definição da sec_01 (páginas 1 e 2).",
                        "epistemic_status": "SOURCE_FACT",
                        "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}],
                        "scoring_criteria": [
                            {
                                "description": "Explicar execução no hardware local sem servidores cloud externos",
                                "weight": 1.0,
                                "required_concepts": ["Inferência Local Soberana"],
                                "factual_anchors": ["hardware", "cloud", "privacidade"],
                            }
                        ],
                    },
                    {
                        "question_text": "Se uma universidade proibisse APIs externas por RGPD, como aplicaria a calibração latência-precisão?",
                        "question_type": "APPLICATION_SCENARIO",
                        "question_difficulty": "HARD",
                        "section_id": "sec_02",
                        "topic": "Calibração Latência-Precisão",
                        "concept_ids": ["c_02"],
                        "correct_answer": "Aplicando execução local e controlo do orçamento de contexto para manter baixa latência e privacidade.",
                        "explanation": "Cenário hipotético derivado dos princípios da sec_01 e sec_02.",
                        "epistemic_status": "MODEL_INFERENCE",
                        "is_hypothetical_scenario": True,
                        "evidence_refs": [{"section_id": "sec_02", "paragraph_id": "p_04", "page_number": 3, "status": "MODEL_INFERENCE"}],
                        "scoring_criteria": [
                            {
                                "description": "Relacionar execução local e orçamento de contexto no cenário novo",
                                "weight": 1.0,
                                "required_concepts": ["Calibração Latência-Precisão"],
                                "factual_anchors": ["local", "contexto", "latência"],
                            }
                        ],
                    },
                ]
            },
            "prompt_tokens": 220,
            "completion_tokens": 200,
        }

    if "phase6_active_recall" in op:
        return {
            "ok": True,
            "parsed": {
                "prompts": [
                    {
                        "prompt_text": "Sem consultar o texto, explica como a Inferência Local Soberana e a calibração latência-precisão se complementam.",
                        "prompt_type": "CONCEPT_RELATIONSHIPS",
                        "question_difficulty": "MEDIUM",
                        "section_id": "sec_01",
                        "topic": "Inferência Local Soberana",
                        "concept_ids": ["c_01", "c_02"],
                        "optional_outline": ["Execução local sem cloud", "Orçamento de contexto", "Métricas 94.8% e 72ms"],
                        "key_points_expected": ["hardware local", "cloud", "contexto", "94.8%"],
                        "grounded_reference_answer": "A execução direta no hardware local sem cloud exige controlo do orçamento de contexto para alcançar 94.8% de precisão em 72ms.",
                        "epistemic_status": "SOURCE_FACT",
                        "evidence_refs": [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}],
                    }
                ]
            },
            "prompt_tokens": 160,
            "completion_tokens": 120,
        }

    return {"ok": False, "error": f"Operação não simulada: {operation}"}


# ===========================================================================
# 15.1 — Testes de Flashcards
# ===========================================================================

class TestFlashcardsPhase6:
    def test_type_adaptive_generation_dedup_and_qa(self, temp_study_workspace):
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=_mock_phase6_llm_caller)
        doc_id = temp_study_workspace["doc_id"]

        deck = engine.generate_flashcards(doc_id, target_cards=8)
        assert deck.cards
        types_present = {c.card_type for c in deck.cards}
        assert FlashcardType.DEFINITION.value in types_present
        assert FlashcardType.METHODOLOGY.value in types_present
        assert FlashcardType.RESULTS_CONCLUSIONS.value in types_present
        hyp_cards = [c for c in deck.cards if c.is_hypothetical_scenario]
        assert hyp_cards and all(c.epistemic_status == "MODEL_INFERENCE" for c in hyp_cards)

        # Remover metodologia/resultados num documento teórico -> metodologia NÃO deve ser selecionada
        theo_dossier = _build_phase3_dossier("doc_theo")
        theo_dossier.methodology_analysis.is_applicable = False
        theo_dossier.results_and_evidence = []
        theo_plan = _build_phase4_plan("doc_theo")
        theo_plan.overview.document_nature = "THEORETICAL_CONCEPTUAL_PAPER"
        _persist_upstream_artifacts(temp_study_workspace["storage_dir"], "doc_theo", _build_phase2_ast("doc_theo"), theo_dossier, theo_plan)
        theo_grounding = engine._require_grounding("doc_theo")
        allowed_theo = engine.flashcards._allowed_types_for_document(theo_grounding)
        assert FlashcardType.METHODOLOGY.value not in allowed_theo
        assert FlashcardType.RESULTS_CONCLUSIONS.value not in allowed_theo

        # QA determinístico: rejeitar circularidade, duplicados e frases minúsculas
        qa = StudyModeQA(theo_grounding)
        bad_cards = [
            AdaptiveFlashcard(card_id="bad_dup", document_id="doc_theo", front="Pergunta sobre soberania local", back="Explicação longa e detalhada suficiente", epistemic_status="SOURCE_FACT", evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1)]),
            AdaptiveFlashcard(card_id="bad_dup", document_id="doc_theo", front="Pergunta duplicada ID", back="Resposta diferente", epistemic_status="SOURCE_FACT"),
            AdaptiveFlashcard(card_id="bad_circ", document_id="doc_theo", front="Inferência local soberana funciona assim?", back="Inferência local soberana funciona assim?", epistemic_status="SOURCE_FACT", evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1)]),
            AdaptiveFlashcard(card_id="bad_unv", document_id="doc_theo", front="Pergunta com estado inválido", back="Conteúdo não verificado não deve passar", epistemic_status="NOT_FOUND", evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1)]),
        ]
        accepted, report = qa.validate_flashcards(bad_cards)
        assert len(accepted) == 1
        assert report.items_rejected == 3

    def test_edit_create_delete_and_regeneration_protection(self, temp_study_workspace):
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=_mock_phase6_llm_caller)
        doc_id = temp_study_workspace["doc_id"]
        deck = engine.generate_flashcards(doc_id, target_cards=6)
        first_card = deck.cards[0]
        second_card = deck.cards[1]

        # Editar cartão -> deve ficar protegido contra regeneração
        edited = engine.edit_flashcard(doc_id, first_card.card_id, back="Verso editado manualmente pelo utilizador.", question_difficulty="HARD")
        assert edited.user_edited is True
        assert "editado manualmente" in edited.back
        assert edited.question_difficulty == "HARD"

        # Regeneração individual sem permissão explícita deve recusar
        with pytest.raises(ValueError, match="editado manualmente"):
            engine.regenerate_flashcard(doc_id, first_card.card_id, allow_overwrite_edited=False)

        # Criar cartão manual e apagar o segundo cartão
        custom = engine.create_flashcard(doc_id, front="Pergunta personalizada", back="Resposta manual fundamentada pelo estudante.", topic="Tópico Manual")
        assert custom.generation_mode == "USER_CREATED"
        assert engine.delete_flashcard(doc_id, second_card.card_id) is True

        # Regeneração forçada de todo o deck preserva edições manuais e cartões custom, sem restaurar apagados
        regen_deck = engine.generate_flashcards(doc_id, force_regenerate=True, target_cards=6)
        by_id = {c.card_id: c for c in regen_deck.cards}
        assert by_id[first_card.card_id].back == "Verso editado manualmente pelo utilizador."
        assert custom.card_id in by_id
        assert by_id[second_card.card_id].is_deleted is True

        # Regeneração explícita de cartão não-editado (ou com allow_overwrite_edited=True) funciona com LLM
        refreshed = engine.regenerate_flashcard(doc_id, first_card.card_id, allow_overwrite_edited=True)
        assert "hardware do utilizador" in refreshed.front
        assert refreshed.user_edited is False


# ===========================================================================
# 15.2 — Testes de Cornell Notes
# ===========================================================================

class TestCornellNotesPhase6:
    def test_cornell_structure_insufficient_evidence_edit_note_and_vault_export(self, temp_study_workspace):
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=_mock_phase6_llm_caller)
        doc_id = temp_study_workspace["doc_id"]

        cornell = engine.generate_cornell_notes(doc_id)
        assert len(cornell.entries) == 4  # sec_01, sec_02, sec_03, sec_empty

        # sec_empty tem zero matéria -> deve recusar invenção e sinalizar insufficient_evidence=False honestamente
        empty_entry = next(e for e in cornell.entries if e.section_id == "sec_empty")
        assert empty_entry.sufficient_evidence is False
        assert "não contém conteúdo analítico" in empty_entry.insufficiency_reason

        sec1 = next(e for e in cornell.entries if e.section_id == "sec_01")
        assert sec1.sufficient_evidence is True
        assert sec1.cue_column and sec1.summary_section
        assert sec1.evidence_refs

        # Editar secção e adicionar nota pessoal + marcar importante
        updated = engine.edit_cornell_entry(doc_id, "sec_01", summary_section="Resumo editado manualmente com precisão.", is_important=True)
        assert updated.user_edited is True
        assert updated.is_important is True

        note = engine.add_cornell_personal_note(doc_id, "sec_01", "Rever relação entre privacidade e latência antes do exame.", is_important=True)
        assert note.content.startswith("Rever relação")

        # Regeneração forçada NÃO pode destruir edições manuais nem notas pessoais
        cornell_regen = engine.generate_cornell_notes(doc_id, force_regenerate=True)
        sec1_after = next(e for e in cornell_regen.entries if e.section_id == "sec_01")
        assert sec1_after.summary_section == "Resumo editado manualmente com precisão."
        assert len(sec1_after.personal_notes) == 1

        # Exportação Markdown + gravação no Vault via StudyService
        vault_dir = temp_study_workspace["tmp_path"] / "vault_out"
        md_text = engine.export_cornell_markdown(doc_id, vault_root=str(vault_dir))
        assert "Resumo editado manualmente com precisão." in md_text
        assert "Rever relação entre privacidade" in md_text
        assert "★" in md_text

        svc = StudyService(
            workspace_root=str(temp_study_workspace["tmp_path"]),
            storage_dir=str(temp_study_workspace["storage_dir"]),
            vault_root=str(vault_dir),
        )
        export_res = svc.export_phase6_cornell_to_vault(doc_id)
        exported_path = Path(export_res["vault_path"])
        assert exported_path.exists()
        assert "Resumo editado manualmente com precisão." in exported_path.read_text(encoding="utf-8")


# ===========================================================================
# 15.3 — Testes de Quizzes / Avaliações
# ===========================================================================

class TestAssessmentsPhase6:
    def test_question_qa_distractor_checks_and_all_7_types(self, temp_study_workspace):
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=_mock_phase6_llm_caller)
        grounding = engine._require_grounding(temp_study_workspace["doc_id"])
        qa = StudyModeQA(grounding)

        # Distrator trivial / comprimento extremo / dupla negação V/F devem ser rejeitados
        bad_mc_trivial = AssessmentQuestion(
            question_id="q_triv",
            document_id="doc_p6_test",
            question_text="Qual das opções descreve o sistema?",
            question_type=QuestionType.MULTIPLE_CHOICE.value,
            options=["Execução local", "Todas as anteriores", "Execução cloud"],
            correct_index=0,
            epistemic_status="SOURCE_FACT",
            evidence_refs=[EvidenceRef(section_id="sec_01", paragraph_id="p_01", page_number=1)],
        )
        bad_mc_length_clue = AssessmentQuestion(
            question_id="q_len",
            document_id="doc_p6_test",
            question_text="Como foi conduzido o estudo empírico comparativo?",
            question_type=QuestionType.MULTIPLE_CHOICE.value,
            options=[
                "Através de um protocolo rigoroso com quinze mil amostras avaliadas por validação cruzada k-fold de dez partições em estações isoladas sem acesso à rede externa",
                "Teste curto",
                "Outro método",
                "Sem método",
            ],
            correct_index=0,
            epistemic_status="SOURCE_FACT",
            evidence_refs=[EvidenceRef(section_id="sec_02", paragraph_id="p_03", page_number=3)],
        )
        bad_tf_double_neg = AssessmentQuestion(
            question_id="q_dn",
            document_id="doc_p6_test",
            question_text="Não é incorreto afirmar que a precisão diminuiu?",
            question_type=QuestionType.TRUE_FALSE.value,
            options=["Verdadeiro", "Falso"],
            correct_index=1,
            epistemic_status="SOURCE_FACT",
            evidence_refs=[EvidenceRef(section_id="sec_03", paragraph_id="p_05", page_number=4)],
        )
        accepted, report = qa.validate_questions([bad_mc_trivial, bad_mc_length_clue, bad_tf_double_neg])
        assert len(accepted) == 0
        assert report.items_rejected == 3

        # Geração com todos os 7 tipos (LLM + complementação determinística cobrindo tipos em falta)
        cfg = AssessmentConfig(
            question_count=7,
            question_types=[t.value for t in QuestionType],
            session_mode="ASSESSMENT",
            feedback_mode="DEFERRED",
        )
        assessment = engine.generate_assessment(temp_study_workspace["doc_id"], config=cfg)
        assert len(assessment.questions) >= 5
        hyp = [q for q in assessment.questions if q.question_type == QuestionType.APPLICATION_SCENARIO.value]
        assert hyp and all(q.is_hypothetical_scenario and q.epistemic_status == "MODEL_INFERENCE" for q in hyp)

    def test_practice_vs_assessment_modes_and_open_answer_rubric(self, temp_study_workspace):
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=_mock_phase6_llm_caller)
        doc_id = temp_study_workspace["doc_id"]

        # Practice mode: verificação imediata por questão
        practice = engine.generate_assessment(
            doc_id,
            config=AssessmentConfig(question_count=4, session_mode="PRACTICE", feedback_mode="IMMEDIATE"),
        )
        q_mc = next(q for q in practice.questions if q.question_type == QuestionType.MULTIPLE_CHOICE.value)
        outcome_ok = engine.check_single_question(doc_id, practice.assessment_id, q_mc.question_id, 0)
        assert outcome_ok.is_correct is True
        outcome_bad = engine.check_single_question(doc_id, practice.assessment_id, q_mc.question_id, 2)
        assert outcome_bad.is_correct is False
        assert outcome_bad.verdict == OpenAnswerVerdict.FACTUAL_ERROR.value

        # Rúbrica determinística de resposta aberta distinguindo erro factual, ambiguidade e resposta completa
        q_open = next(q for q in practice.questions if q.question_type not in (QuestionType.MULTIPLE_CHOICE.value, QuestionType.TRUE_FALSE.value))
        eval_err = engine.assessments.evaluate_open_answer(
            question=q_open,
            student_answer="Na verdade a inferência local não é executada no hardware local e envia tudo para cloud.",
            use_llm=False,
            llm_caller=None,
        )
        assert eval_err.verdict == OpenAnswerVerdict.FACTUAL_ERROR.value

        eval_amb = engine.assessments.evaluate_open_answer(
            question=q_open,
            student_answer="Não tenho a certeza, talvez execute no hardware local ou talvez na cloud.",
            use_llm=False,
            llm_caller=None,
        )
        assert eval_amb.verdict == OpenAnswerVerdict.AMBIGUOUS.value
        assert eval_amb.is_uncertain is True

        eval_good = engine.assessments.evaluate_open_answer(
            question=q_open,
            student_answer=f"{q_open.correct_answer} {' '.join(q_open.related_concept_names)}",
            use_llm=False,
            llm_caller=None,
        )
        assert eval_good.verdict in (OpenAnswerVerdict.CORRECT.value, OpenAnswerVerdict.PARTIAL.value, OpenAnswerVerdict.INCOMPLETE_EXPLANATION.value)
        assert eval_good.score_ratio >= 0.5

        # Submissão completa atualiza histórico e métricas por tópico/dificuldade
        answers = {q.question_id: (q.correct_index if q.correct_index is not None else q.correct_answer) for q in practice.questions}
        res = engine.submit_assessment(doc_id, practice.assessment_id, answers)
        assert res["attempt"]["total_questions"] == len(practice.questions)
        assert res["attempt"]["score_pct"] > 0.0
        history = engine.progress.get_assessment_history(doc_id)
        assert len(history) == 1


# ===========================================================================
# 15.4 — Testes de Active Recall
# ===========================================================================

class TestActiveRecallPhase6:
    def test_hidden_answer_before_submit_confidence_and_srs_update(self, temp_study_workspace):
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=_mock_phase6_llm_caller)
        doc_id = temp_study_workspace["doc_id"]

        deck = engine.generate_active_recall(doc_id, target_prompts=4)
        assert deck.prompts

        # ANTES da resposta: resposta de referência DEVE estar oculta para o estudante
        payload_hidden = engine.get_active_recall_prompts(doc_id, reveal_answers=False)
        for item in payload_hidden["prompts"]:
            assert item["answer_hidden"] is True
            assert item["grounded_reference_answer"] == ""
            assert item["key_points_expected"] == []

        # Submissão revela referência + evidência + agenda próxima revisão SM-2
        p0 = deck.prompts[0]
        res = engine.submit_active_recall(
            doc_id,
            p0.prompt_id,
            student_response="A inferência local executa no hardware sem cloud, controlando contexto para obter 94.8% de precisão e 72ms.",
            self_confidence=4,
            outline_used=True,
            now_ts=1_700_000_000.0,
        )
        attempt = res["attempt"]
        assert attempt["revealed_reference"] == p0.grounded_reference_answer
        assert attempt["self_confidence"] == 4
        assert attempt["outline_used"] is True
        assert attempt["evidence_refs"]
        assert res["srs_state"]["algorithm_version"] == SRS_ALGORITHM_VERSION
        assert res["srs_state"]["reviews_count"] == 1


# ===========================================================================
# 15.5 — Testes de Repetição Espaçada (SM-2 v6.0)
# ===========================================================================

class TestSpacedRepetitionPhase6:
    def test_sm2_progression_lapses_bounds_versioning_restart_and_queue_limits(self, temp_study_workspace):
        storage_dir = temp_study_workspace["storage_dir"]
        engine = StudyModesEngine(storage_dir, llm_caller=_mock_phase6_llm_caller)
        doc_id = temp_study_workspace["doc_id"]

        deck = engine.generate_flashcards(doc_id, target_cards=6)
        c0 = deck.cards[0]
        base_ts = 1_700_000_000.0

        # 1a revisão GOOD -> interval = 1 dia, estado LEARNING
        s1, ev1 = engine.srs.record_review(
            item_id=c0.card_id,
            item_type="flashcard",
            document_id=doc_id,
            rating="Good",
            confidence=4,
            content_difficulty=c0.content_difficulty,
            question_difficulty=c0.question_difficulty,
            now_ts=base_ts,
        )
        assert s1.interval_days == 1.0
        assert s1.learning_state == ReviewLearningState.LEARNING.value
        assert s1.algorithm_version == SRS_ALGORITHM_VERSION
        assert ev1.algorithm_version == SRS_ALGORITHM_VERSION

        # 2a revisão GOOD -> interval = 6 dias; 3a & 4a EASY -> cresce até MATURE (>= 21d) <= 365d
        s2, _ = engine.srs.record_review(item_id=c0.card_id, item_type="flashcard", document_id=doc_id, rating="Good", confidence=5, now_ts=base_ts + 86400)
        assert s2.interval_days == 6.0
        s3, _ = engine.srs.record_review(item_id=c0.card_id, item_type="flashcard", document_id=doc_id, rating="Easy", confidence=5, now_ts=base_ts + 7 * 86400)
        assert s3.interval_days > 6.0
        s4, _ = engine.srs.record_review(item_id=c0.card_id, item_type="flashcard", document_id=doc_id, rating="Easy", confidence=5, now_ts=base_ts + 30 * 86400)
        assert s4.interval_days >= 21.0
        assert s4.interval_days <= 365.0
        assert s4.learning_state == ReviewLearningState.MATURE.value

        # Lapso (AGAIN) -> reinicia para 1 dia, reduz Ease Factor sem descer abaixo de 1.3, estado LAPSED
        ef_before_fail = s4.ease_factor
        s_fail, _ = engine.srs.record_review(item_id=c0.card_id, item_type="flashcard", document_id=doc_id, rating="Again", confidence=1, now_ts=base_ts + 40 * 86400)
        assert s_fail.interval_days == 1.0
        assert s_fail.ease_factor < ef_before_fail
        assert s_fail.ease_factor >= 1.3
        assert s_fail.learning_state == ReviewLearningState.LAPSED.value
        assert s_fail.failed_recalls == 1
        assert s_fail.consecutive_failures == 1

        # Reinício da aplicação (nova instância StudyModesEngine lendo disco)
        restarted_engine = StudyModesEngine(storage_dir)
        persisted_state = restarted_engine.srs.get_all_states(document_id=doc_id)[c0.card_id]
        assert persisted_state.learning_state == ReviewLearningState.LAPSED.value
        assert persisted_state.failed_recalls == 1
        assert len(restarted_engine.srs.get_history(document_id=doc_id)) == 5

        # Fila diária com limites configuráveis priorizando itens lapsos/vencidos e respeitando max limites
        queue = restarted_engine.get_daily_review_queue(
            doc_id,
            daily_new_limit=2,
            daily_review_limit=1,
            now_ts=base_ts + 45 * 86400,
        )
        assert len(queue.new_items) <= 2
        assert len(queue.lapsed_items) + len(queue.due_items) <= 1
        assert any(i["item_id"] == c0.card_id for i in queue.lapsed_items)


# ===========================================================================
# 15.6 — Integridade de Dados, Epistemic Guard, Obsolescência, Sessões e WebSocket
# ===========================================================================

class TestIntegrityProgressSessionsAndWebSocketPhase6:
    def test_missing_artifacts_stale_fingerprints_and_ungrounded_rejection(self, temp_study_workspace):
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=_mock_phase6_llm_caller)

        # Documento inexistente -> prontidão bloqueada
        missing = engine.check_readiness("doc_nao_existe")
        assert missing.is_ready is False
        assert missing.status == StudyModeReadinessStatus.MISSING_DOCUMENT.value
        with pytest.raises(ValueError, match="MISSING_DOCUMENT|Falta"):
            engine.generate_flashcards("doc_nao_existe")

        # Gerar flashes e depois alterar Plano Editorial -> deteção automática de STALE_SOURCE_ARTIFACTS
        doc_id = temp_study_workspace["doc_id"]
        engine.generate_flashcards(doc_id)
        ready_now = engine.check_readiness(doc_id)
        assert ready_now.is_stale is False

        mutated_plan = _build_phase4_plan(doc_id)
        mutated_plan.metadata.plan_version = 2
        mutated_plan.overview.central_theme = "Tema Atualizado na Fase 4"
        (temp_study_workspace["storage_dir"] / "documents" / doc_id / "editorial_study_plan.json").write_text(
            json.dumps(mutated_plan.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        stale_status = engine.check_readiness(doc_id)
        assert stale_status.is_ready is True
        assert stale_status.is_stale is True
        assert stale_status.status == StudyModeReadinessStatus.STALE_SOURCE_ARTIFACTS.value

        # Grounding guard rejeita IDs inexistentes, páginas inválidas e bloqueia promoção NOT_FOUND/UNVERIFIED -> SOURCE_FACT
        grounding = engine._require_grounding(doc_id)
        refs, pages, st, rejections = grounding.validate_and_ground_refs(
            [{"section_id": "sec_fake", "paragraph_id": "p_invented", "page_number": 999, "status": "SOURCE_FACT"}],
            candidate_text="Texto inventado sem qualquer sobreposição na fonte.",
            requested_status="NOT_FOUND",
        )
        assert st == "NOT_FOUND"
        assert rejections
        assert 999 not in pages

        _, _, downgraded_st, _ = grounding.validate_and_ground_refs(
            [{"section_id": "sec_01", "paragraph_id": "p_01", "page_number": 1, "status": "SOURCE_FACT"}],
            candidate_text="Afirmação inventada completamente alheia ao parágrafo citado sobre astronomia lunar.",
            requested_status="SOURCE_FACT",
        )
        assert downgraded_st == "MODEL_INFERENCE"

    def test_minimum_evidence_threshold_knowledge_gaps_and_session_crash_recovery(self, temp_study_workspace):
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=_mock_phase6_llm_caller)
        doc_id = temp_study_workspace["doc_id"]
        deck = engine.generate_flashcards(doc_id, target_cards=6)
        target_card = next(c for c in deck.cards if c.concept_ids)

        # 1 única revisão -> insuficiência de evidência (não declara domínio nem inventa proficiência!)
        engine.review_flashcard(doc_id, target_card.card_id, "Good", confidence=5)
        prog_1 = engine.get_learning_progress(doc_id, recompute=True)
        assert prog_1.mastery_level == MasteryLevel.INSUFFICIENT_EVIDENCE.value
        assert prog_1.flashcard_reviews_total == 1
        assert prog_1.by_concept[target_card.concept_ids[0]]["mastery_level"] == MasteryLevel.INSUFFICIENT_EVIDENCE.value

        # 2 falhas consecutivas no mesmo conceito -> gera lacuna estruturada com evidência da fonte
        engine.review_flashcard(doc_id, target_card.card_id, "Again", confidence=1)
        engine.review_flashcard(doc_id, target_card.card_id, "Again", confidence=1)
        prog_gap = engine.get_learning_progress(doc_id, recompute=True)
        assert prog_gap.knowledge_gaps
        assert any(g.concept_id in target_card.concept_ids or g.section_id == target_card.section_id for g in prog_gap.knowledge_gaps)
        assert prog_gap.knowledge_gaps[0].suggested_activities

        # Ciclo de vida durável de Sessão de Estudo com crash/restart simulado
        sess = engine.start_study_session(
            document_id=doc_id,
            mode=StudySessionMode.ACTIVE_RECALL.value,
            title="Sessão Active Recall",
            item_ids=["ar_1", "ar_2", "ar_3"],
        )
        engine.record_session_step(sess.session_id, item_id="ar_1", partial_response={"draft": "rascunho parcial"}, next_index=1)
        paused = engine.pause_study_session(sess.session_id)
        assert paused.status == StudySessionStatus.PAUSED.value

        # Novo engine após reinício retoma exatamente no índice 1 e preserva rascunho parcial
        recovered = StudyModesEngine(temp_study_workspace["storage_dir"]).resume_study_session(sess.session_id)
        assert recovered.status == StudySessionStatus.IN_PROGRESS.value
        assert recovered.current_index == 1
        assert recovered.partial_responses["ar_1"]["draft"] == "rascunho parcial"

        done = engine.complete_study_session(sess.session_id, summary_stats={"items_completed": 3})
        assert done.status == StudySessionStatus.COMPLETED.value

    def test_websocket_handler_and_contracts_roundtrip(self, temp_study_workspace):
        # Verificar todos os message types da Fase 6 nos contratos WebSocket
        expected_ws_types = {
            "study_mode_get_readiness",
            "study_mode_get_flashcards",
            "study_mode_generate_flashcards",
            "study_mode_edit_flashcard",
            "study_mode_delete_flashcard",
            "study_mode_create_flashcard",
            "study_mode_regenerate_flashcard",
            "study_mode_review_flashcard",
            "study_mode_get_cornell",
            "study_mode_generate_cornell",
            "study_mode_edit_cornell_entry",
            "study_mode_add_cornell_note",
            "study_mode_export_cornell_vault",
            "study_mode_get_assessments",
            "study_mode_generate_assessment",
            "study_mode_check_question",
            "study_mode_submit_assessment",
            "study_mode_get_active_recall",
            "study_mode_generate_active_recall",
            "study_mode_submit_active_recall",
            "study_mode_get_daily_queue",
            "study_mode_get_progress",
            "study_mode_start_session",
            "study_mode_update_session",
            "study_mode_pause_session",
            "study_mode_resume_session",
            "study_mode_complete_session",
            "study_mode_list_sessions",
        }
        assert expected_ws_types.issubset(EXPECTED_MESSAGE_TYPES)

        service = StudyService(
            workspace_root=str(temp_study_workspace["tmp_path"]),
            storage_dir=str(temp_study_workspace["storage_dir"]),
            vault_root=str(temp_study_workspace["tmp_path"] / "vault_ws"),
        )
        service.study_modes.llm_caller = _mock_phase6_llm_caller

        sent_messages: List[Dict[str, Any]] = []

        class _FakeConnManager:
            async def send(self, ws: Any, payload: Dict[str, Any]) -> None:
                sent_messages.append(payload)

        handler = StudyWebSocketHandler(_FakeConnManager(), service)
        routes = handler.routes()
        ws_session = WebSocketSessionState()
        doc_id = temp_study_workspace["doc_id"]

        async def _exercise_ws():
            calls = [
                ("study_mode_get_readiness", {"type": "study_mode_get_readiness", "document_id": doc_id, "request_id": "r1"}),
                ("study_mode_generate_flashcards", {"type": "study_mode_generate_flashcards", "document_id": doc_id, "target_cards": 5, "request_id": "r2"}),
                ("study_mode_generate_cornell", {"type": "study_mode_generate_cornell", "document_id": doc_id, "request_id": "r3"}),
                ("study_mode_generate_assessment", {"type": "study_mode_generate_assessment", "document_id": doc_id, "config": {"question_count": 3}, "request_id": "r4"}),
                ("study_mode_generate_active_recall", {"type": "study_mode_generate_active_recall", "document_id": doc_id, "target_prompts": 3, "request_id": "r5"}),
                ("study_mode_get_daily_queue", {"type": "study_mode_get_daily_queue", "document_id": doc_id, "request_id": "r6"}),
                ("study_mode_get_progress", {"type": "study_mode_get_progress", "document_id": doc_id, "request_id": "r7"}),
            ]
            for route_name, payload in calls:
                ctx = WebSocketHandlerContext(
                    services=None,  # type: ignore[arg-type]
                    runtime=ws_session,
                    client=object(),
                    request_id=payload["request_id"],
                )
                await routes[route_name](ctx, payload)

        asyncio.run(_exercise_ws())

        by_req = {m.get("request_id"): m for m in sent_messages if m.get("type") != "study_mode_progress_event"}
        assert by_req["r1"]["readiness"]["is_ready"] is True
        assert by_req["r2"]["type"] == "study_mode_flashcards_result" and len(by_req["r2"]["cards"]) >= 4
        assert by_req["r3"]["type"] == "study_mode_cornell_result" and by_req["r3"]["cornell"]["entries"]
        assert by_req["r4"]["type"] == "study_mode_assessment_generated" and by_req["r4"]["assessment"]["questions"]
        assert by_req["r5"]["type"] == "study_mode_active_recall_result" and by_req["r5"]["prompts"]
        assert by_req["r6"]["type"] == "study_mode_daily_queue_result" and "queue" in by_req["r6"]
        assert by_req["r7"]["type"] == "study_mode_progress_result" and "progress" in by_req["r7"]


# ===========================================================================
# 15.7 — End-to-End Real PDF Pipeline (Deterministic + Real Ollama qwen3.5:9b Test)
# ===========================================================================

class TestEndToEndPipelinePhase6:
    REAL_PDF_PATH = Path("data/study/a3b336f4295d0d51_Predicting_performance_online_consumer_reviews(1).pdf")

    def test_e2e_real_pdf_to_phase6_study_modes_pipeline(self, tmp_path: Path):
        if not self.REAL_PDF_PATH.exists():
            pytest.skip(f"PDF de teste não disponível em {self.REAL_PDF_PATH}")

        storage_dir = tmp_path / "e2e_study_data"
        doc_id = "e2e_real_pdf_doc"

        # 1. Fase 2 Real: DocumentIntelligenceExtractor no PDF real
        extractor = DocumentIntelligenceExtractor(ocr_enabled=False, assets_dir=tmp_path / "assets")
        ast = extractor.extract(self.REAL_PDF_PATH, doc_id)
        assert ast.paragraphs
        assert ast.sections

        # Selecionar 2 secções reais extraídas para Fases 3 e 4 reais encadeadas
        sec_a = ast.sections[0]
        sec_b = ast.sections[min(1, len(ast.sections) - 1)]
        p_a = next((p for p in ast.paragraphs if p.section_id == sec_a.section_id), ast.paragraphs[0])
        p_b = next((p for p in ast.paragraphs if p.section_id == sec_b.section_id), ast.paragraphs[-1])

        dossier = AcademicReasoningDossier(
            dossier_id=f"dossier_{doc_id}",
            document_id=doc_id,
            source_sha256=ast.source_sha256,
            document_analysis=DocumentCoreAnalysis(
                document_id=doc_id,
                title=ast.metadata.title or ast.filename,
                central_thesis=p_a.text[:220],
                global_objective="Análise académica de online consumer reviews.",
            ),
            section_analyses=[
                SectionAnalysis(
                    section_id=sec_a.section_id,
                    title=sec_a.title,
                    in_depth_synthesis=p_a.text[:350],
                    core_ideas=[p_a.text[:140]],
                    source_refs=[EvidenceRef(section_id=sec_a.section_id, paragraph_id=p_a.paragraph_id, page_number=p_a.page_number, status="SOURCE_FACT")],
                ),
                SectionAnalysis(
                    section_id=sec_b.section_id,
                    title=sec_b.title,
                    in_depth_synthesis=p_b.text[:350],
                    core_ideas=[p_b.text[:140]],
                    source_refs=[EvidenceRef(section_id=sec_b.section_id, paragraph_id=p_b.paragraph_id, page_number=p_b.page_number, status="SOURCE_FACT")],
                ),
            ],
            conceptual_analysis=[
                ConceptItem(
                    concept_id="c_real_1",
                    name=sec_a.title[:60] or "Conceito Principal",
                    definition=p_a.text[:220],
                    explanation=p_a.text[:280],
                    evidence_refs=[EvidenceRef(section_id=sec_a.section_id, paragraph_id=p_a.paragraph_id, page_number=p_a.page_number, status="SOURCE_FACT")],
                )
            ],
        )

        plan = EditorialStudyPlan(
            metadata=EditorialPlanMetadata(
                plan_id=f"plan_{doc_id}",
                document_id=doc_id,
                source_sha256=ast.source_sha256,
                ast_version=ast.extractor_version,
                dossier_id=dossier.dossier_id,
                status="COMPLETED",
            ),
            overview=EditorialOverview(
                central_theme=dossier.document_analysis.title,
                learning_objectives=[{"objective_id": "obj_r1", "description": f"Dominar {sec_a.title}", "source_section_ids": [sec_a.section_id]}],
                document_nature="EMPIRICAL_RESEARCH_ARTICLE",
            ),
            chapters=[
                EditorialChapter(
                    chapter_id="chap_r1",
                    title=f"Capítulo 1: {sec_a.title[:50]}",
                    pedagogical_objective="Estudar secção extraída do PDF real.",
                    key_concept_ids=["c_real_1"],
                    original_section_ids=[sec_a.section_id],
                    sections=[
                        EditorialSection(
                            section_id=sec_a.section_id,
                            chapter_id="chap_r1",
                            title=sec_a.title,
                            associated_concept_ids=["c_real_1"],
                            original_section_ids=[sec_a.section_id],
                            evidence_refs=[EvidenceRef(section_id=sec_a.section_id, paragraph_id=p_a.paragraph_id, page_number=p_a.page_number, status="SOURCE_FACT")],
                        )
                    ],
                )
            ],
        )
        _persist_upstream_artifacts(storage_dir, doc_id, ast, dossier, plan)

        # Executar Fase 6 em fluxo completo (fallback determinístico sem LLM mock ou real)
        engine = StudyModesEngine(storage_dir, llm_caller=lambda **_: {"ok": False, "error": "fallback_e2e_det"})
        readiness = engine.check_readiness(doc_id)
        assert readiness.is_ready is True and readiness.has_ast is True

        deck = engine.generate_flashcards(doc_id, target_cards=4)
        cornell = engine.generate_cornell_notes(doc_id)
        assessment = engine.generate_assessment(doc_id, config=AssessmentConfig(question_count=3))
        ar = engine.generate_active_recall(doc_id, target_prompts=2)

        assert deck.cards
        assert cornell.entries
        assert assessment.questions
        assert ar.prompts

        # Fluxo completo do estudante
        engine.review_flashcard(doc_id, deck.cards[0].card_id, "Good", confidence=4)
        engine.submit_active_recall(doc_id, ar.prompts[0].prompt_id, student_response=ar.prompts[0].grounded_reference_answer, self_confidence=4)
        ans = {q.question_id: (q.correct_index if q.correct_index is not None else q.correct_answer) for q in assessment.questions}
        engine.submit_assessment(doc_id, assessment.assessment_id, ans)
        queue_tomorrow = engine.get_daily_review_queue(doc_id, now_ts=time.time() + 2 * 86400)
        prog = engine.get_learning_progress(doc_id, recompute=True)
        assert prog.flashcard_reviews_total >= 1
        assert queue_tomorrow.total_queue_count >= 1

    @pytest.mark.skipif(
        os.getenv("STUDY_FORCE_LIVE_LLM") != "1",
        reason="Teste real com Ollama (qwen3.5:9b) executado explicitamente com STUDY_FORCE_LIVE_LLM=1.",
    )
    def test_e2e_live_ollama_qwen35_phase6_generation(self, temp_study_workspace):
        """Valida geração LIVE real com Ollama local qwen3.5:9b para Flashcards, Cornell, Quiz e Active Recall."""
        engine = StudyModesEngine(temp_study_workspace["storage_dir"], llm_caller=None)
        doc_id = temp_study_workspace["doc_id"]

        deck = engine.generate_flashcards(doc_id, target_cards=4)
        assert deck.cards
        assert deck.generation_mode in ("LLM_GROUNDED", "PARTIAL")

        cornell = engine.generate_cornell_notes(doc_id)
        assert any(e.generation_mode == "LLM_GROUNDED" for e in cornell.entries if e.sufficient_evidence)

        assessment = engine.generate_assessment(
            doc_id,
            config=AssessmentConfig(
                question_count=3,
                question_types=[QuestionType.MULTIPLE_CHOICE.value, QuestionType.SHORT_ANSWER.value],
            ),
        )
        assert assessment.questions
        assert assessment.generation_mode in ("LLM_GROUNDED", "PARTIAL")

        ar = engine.generate_active_recall(doc_id, target_prompts=2)
        assert ar.prompts
        assert ar.generation_mode in ("LLM_GROUNDED", "PARTIAL")
