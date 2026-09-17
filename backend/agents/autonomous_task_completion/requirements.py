"""
JARVIS OS — Phase 57: Requirements & Acceptance Criteria Extraction
Extracts formal requirements, strictly separating USER_REQUIREMENT,
SYSTEM_INFERENCE, and ASSUMPTION. Derives observable, verifiable AcceptanceCriteria.
"""

from __future__ import annotations

import uuid
from typing import Any

from .models import (
    AcceptanceCriterion,
    CriterionStatus,
    RequirementCategory,
    RequirementItem,
    TaskUnderstandingResult,
    VerificationMethod,
)


class RequirementsExtractor:
    """Extracts verifiable requirements and observable acceptance criteria."""

    @classmethod
    def extract_requirements(cls, task_result: TaskUnderstandingResult) -> list[RequirementItem]:
        reqs: list[RequirementItem] = []
        raw = task_result.raw_intent.lower()
        domain = task_result.provenance.get("domain", "general_engineering")

        # 1. USER_REQUIREMENT: Derived directly from explicit user statements
        reqs.append(
            RequirementItem(
                req_id=f"req_user_{uuid.uuid4().hex[:6]}",
                description=f"Satisfazer o objetivo explícito: {task_result.objective}",
                category=RequirementCategory.USER_REQUIREMENT,
                critical=True,
                source="user_explicit_prompt",
            )
        )
        for constraint in task_result.constraints:
            reqs.append(
                RequirementItem(
                    req_id=f"req_user_{uuid.uuid4().hex[:6]}",
                    description=f"Cumprir restrição explícita: {constraint}",
                    category=RequirementCategory.USER_REQUIREMENT,
                    critical=True,
                    source="user_explicit_constraint",
                )
            )

        # 2. SYSTEM_INFERENCE: Inferred by JARVIS architecture rules (NOT user requirements)
        reqs.append(
            RequirementItem(
                req_id=f"req_sys_{uuid.uuid4().hex[:6]}",
                description="Código gerado deve compilar com zero erros de sintaxe e tipos",
                category=RequirementCategory.SYSTEM_INFERENCE,
                critical=True,
                source="jarvis_compilation_gate",
            )
        )
        if domain in ("frontend", "fullstack", "browser_task"):
            reqs.append(
                RequirementItem(
                    req_id=f"req_sys_{uuid.uuid4().hex[:6]}",
                    description="Componentes UI devem montar no DOM sem exceções não tratadas",
                    category=RequirementCategory.SYSTEM_INFERENCE,
                    critical=True,
                    source="jarvis_frontend_runtime_rule",
                )
            )
        if domain in ("backend", "fullstack", "contract_change"):
            reqs.append(
                RequirementItem(
                    req_id=f"req_sys_{uuid.uuid4().hex[:6]}",
                    description="Endpoints REST/WebSocket devem manter contratos e esquemas válidos",
                    category=RequirementCategory.SYSTEM_INFERENCE,
                    critical=True,
                    source="jarvis_contract_governance_rule",
                )
            )

        # 3. ASSUMPTION: Low-risk defaults assumed for underspecified parts
        for amb in task_result.ambiguities:
            if amb.resolution_strategy == "DEFAULT_POLICY" and amb.chosen_resolution:
                reqs.append(
                    RequirementItem(
                        req_id=f"req_ass_{uuid.uuid4().hex[:6]}",
                        description=f"Pressuposto padrão: {amb.chosen_resolution}",
                        category=RequirementCategory.ASSUMPTION,
                        critical=False,
                        source=f"ambiguity_default_policy:{amb.ambiguity_id}",
                    )
                )

        return reqs

    @classmethod
    def derive_acceptance_criteria(
        cls, task_result: TaskUnderstandingResult, requirements: list[RequirementItem]
    ) -> list[AcceptanceCriterion]:
        criteria: list[AcceptanceCriterion] = []
        domain = task_result.provenance.get("domain", "general_engineering")
        raw = task_result.raw_intent.lower()

        # Universal Criterion: Build Valid
        criteria.append(
            AcceptanceCriterion(
                criterion_id="crit_build_valid",
                description="Projeto e artefactos compilam sem erros de sintaxe ou tipos",
                verification_method=VerificationMethod.BUILD,
                required=True,
            )
        )

        # Universal Criterion: Relevant Tests Pass
        criteria.append(
            AcceptanceCriterion(
                criterion_id="crit_tests_pass",
                description="Suíte de testes relevantes passa com 100% de sucesso",
                verification_method=VerificationMethod.TEST,
                required=True,
            )
        )

        # Universal Criterion: Security Invariants Preserved
        criteria.append(
            AcceptanceCriterion(
                criterion_id="crit_security_valid",
                description="Nenhuma violação de isolamento, sandbox ou política do Security Sentinel",
                verification_method=VerificationMethod.SECURITY,
                required=True,
            )
        )

        # Domain Specific Criteria
        if domain in ("backend", "fullstack", "contract_change") or "api" in raw:
            criteria.append(
                AcceptanceCriterion(
                    criterion_id="crit_endpoint_exists",
                    description="Endpoint de API alvo responde adequadamente na porta de serviço",
                    verification_method=VerificationMethod.CONTRACT,
                    required=True,
                )
            )
            criteria.append(
                AcceptanceCriterion(
                    criterion_id="crit_contract_valid",
                    description="Esquemas de dados e tipos de payloads estão em conformidade com o contrato",
                    verification_method=VerificationMethod.CONTRACT,
                    required=True,
                )
            )

        if domain in ("frontend", "fullstack", "browser_task") or "ui" in raw or "interface" in raw:
            criteria.append(
                AcceptanceCriterion(
                    criterion_id="crit_frontend_loads",
                    description="Página frontend carrega sem erros críticos de consola",
                    verification_method=VerificationMethod.BROWSER,
                    required=True,
                )
            )
            criteria.append(
                AcceptanceCriterion(
                    criterion_id="crit_ui_elements_visible",
                    description="Elementos de interface essenciais são renderizados no DOM",
                    verification_method=VerificationMethod.BROWSER,
                    required=True,
                )
            )

        if domain == "bugfix" or "corrigir" in raw or "fix" in raw:
            criteria.append(
                AcceptanceCriterion(
                    criterion_id="crit_bug_repaired",
                    description="Falha diagnosticada deixa de ocorrer e regressões são nulas",
                    verification_method=VerificationMethod.BEHAVIOR,
                    required=True,
                )
            )

        # Output Artifact Criteria
        for out in task_result.required_outputs:
            criteria.append(
                AcceptanceCriterion(
                    criterion_id=f"crit_artifact_{out}",
                    description=f"Artefacto obrigatório '{out}' gerado e validado",
                    verification_method=VerificationMethod.ARTIFACT,
                    required=True,
                    details={"target_output": out},
                )
            )

        return criteria
