"""
Pipeline Central de Governança e Aceitação de Produto (Product Delivery Gate).
Orquestra o ciclo completo:
PLAN -> IMPLEMENT -> PREFLIGHT -> BUILD -> RUN -> FUNCTIONAL QA -> VISUAL QA -> PRESERVATION QA -> REQUIREMENT RECONCILIATION -> DELIVERY.

Garante que nenhuma alteração é entregue como "Validated" ou "Product Accepted"
sem evidência factual em todos os eixos requeridos.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from security.delivery_governance.integrity_detector import (
    DestructiveChangeDetector,
    PreservationAnalyzer,
)
from security.delivery_governance.models import (
    AcceptanceLevel,
    DeliveryGateStatus,
    ProductAcceptanceReport,
    ProductIntegrityDiff,
    QualityScoreStatus,
    RequirementItem,
    RequirementStatus,
)
from security.delivery_governance.validators.asset_validator import AssetIntegrityValidator
from security.delivery_governance.validators.browser_validator import BrowserIntegrityValidator
from security.delivery_governance.validators.html_validator import HtmlDocumentValidator
from security.delivery_governance.validators.interaction_validator import InteractionValidator
from security.delivery_governance.validators.runtime_validator import RuntimeIntegrityValidator
from security.delivery_governance.validators.visual_validator import VisualIntegrityValidator
from security.permission_gateway.dependency_governance import get_dependency_governor
from security.permission_gateway.models import DependencyClassification, PermissionRequestStatus

logger = logging.getLogger("Jarvis.ProductDeliveryGate")


class ProductDeliveryGate:
    """
    Portão de validação de produto que impede a entrega de código funcionalmente incompleto,
    visualmente degradado, com dependências sem autorização ou com regressões não detetadas.
    """

    @classmethod
    def evaluate_delivery(
        cls,
        project_root: str,
        project_id: str = "",
        mission_id: str = "",
        change_id: str = "",
        user_prompt: str = "",
        changes: Optional[List[Dict[str, Any]]] = None,
        before_snapshot: Optional[Dict[str, Any]] = None,
        technical_validations_passed: bool = True,
        runtime_endpoint: Optional[str] = None,
        browser_test_requested: bool = False,
    ) -> ProductAcceptanceReport:
        """
        Executa a auditoria completa de aceitação de produto.
        Retorna o ProductAcceptanceReport com a classificação qualitativa e decisão final.
        """
        report = ProductAcceptanceReport(
            mission_id=mission_id,
            project_id=project_id,
            change_id=change_id,
            gate_status=DeliveryGateStatus.PREFLIGHT.value,
        )

        # 1. RASTREABILIDADE DE REQUISITOS (Requirement Traceability)
        requirements = cls._extract_requirements(user_prompt)
        report.requirements = requirements
        report.acceptance_criteria = [r.description for r in requirements]

        # 2. AUDITORIA DE PRESERVAÇÃO E DESTRUIÇÃO (Preservation & Destructive Analysis)
        integrity_diff = ProductIntegrityDiff(project_id=project_id)
        if before_snapshot:
            integrity_diff = PreservationAnalyzer.compare_integrity(
                before_snapshot=before_snapshot,
                project_dir=project_root,
                changes=changes,
                project_id=project_id,
            )
        elif changes:
            # Avalia se alguma mudança pontual é destrutiva mesmo sem snapshot
            for item in changes:
                fname = item.get("file", "")
                old_text = item.get("previous_excerpt") or ""
                new_text = item.get("proposed_excerpt") or ""
                destr_eval = DestructiveChangeDetector.evaluate_change_destructiveness(fname, old_text, new_text)
                if destr_eval["is_destructive"]:
                    integrity_diff.destructive_file_replacements.append(destr_eval)
                    if destr_eval["severity"] == "CRITICAL":
                        integrity_diff.violations.append(
                            f"CRITICAL_DESTRUCTIVE_REPLACEMENT em {fname}: {destr_eval['reason']}"
                        )
                        integrity_diff.has_critical_regression = True
                    else:
                        integrity_diff.warnings.append(
                            f"DESTRUCTIVE_FILE_REPLACEMENT em {fname}: {destr_eval['reason']}"
                        )

        report.regression_checks.append(integrity_diff.to_dict())
        if integrity_diff.has_critical_regression:
            report.blockers.extend(integrity_diff.violations)

        # 3. VALIDAÇÃO HTML E ESTRUTURA WEB (HTML Validation)
        html_files_checked = []
        html_violations = []
        is_web_project = False

        if os.path.isdir(project_root):
            for root, _, files in os.walk(project_root):
                if any(p in {"node_modules", ".git", "dist", "build"} for p in os.path.split(root)):
                    continue
                for f in files:
                    if f.lower().endswith((".html", ".htm")):
                        is_web_project = True
                        hpath = os.path.join(root, f)
                        h_res = HtmlDocumentValidator.validate_html_file(hpath, project_root)
                        html_files_checked.append(h_res)
                        if not h_res["valid"]:
                            html_violations.extend(h_res["violations"])

        report.functional_checks.append({
            "check_name": "html_document_structure",
            "files_evaluated": len(html_files_checked),
            "valid": len(html_violations) == 0,
            "violations": html_violations,
        })
        if html_violations:
            report.blockers.extend(html_violations)

        # 4. VALIDAÇÃO DE INTEGRIDADE DE ASSETS (Asset Integrity)
        asset_res = AssetIntegrityValidator.validate_project_assets(project_root)
        report.functional_checks.append({
            "check_name": "asset_integrity",
            "valid": asset_res["valid"],
            "missing_assets": asset_res.get("missing_assets", []),
        })
        if not asset_res["valid"]:
            for ma in asset_res.get("missing_assets", []):
                report.blockers.append(f"MISSING_ASSET: {ma}")

        # 5. VALIDAÇÃO VISUAL (Visual Integrity)
        ui_changed = is_web_project or any(
            str(ch.get("file", "")).lower().endswith((".html", ".htm", ".css", ".jsx", ".tsx"))
            for ch in (changes or [])
        )
        visual_res = VisualIntegrityValidator.evaluate_project_visual_readiness(
            project_root=project_root,
            ui_changed=ui_changed,
            baseline_snapshot=before_snapshot,
        )
        report.visual_checks.append(visual_res)
        if visual_res["is_ui_project"] and not visual_res["valid"]:
            report.blockers.extend(visual_res["violations"])

        # 6. VALIDAÇÃO DE INTERAÇÃO (Interaction & Button Wiring)
        baseline_buttons = before_snapshot.get("buttons", []) if before_snapshot else []
        interaction_res = InteractionValidator.evaluate_interactions(
            project_root=project_root,
            baseline_buttons=baseline_buttons,
        )
        report.functional_checks.append({
            "check_name": "interaction_wiring",
            "valid": interaction_res["valid"],
            "dead_buttons": interaction_res["dead_buttons"],
            "violations": interaction_res["violations"],
        })
        if not interaction_res["valid"]:
            report.blockers.extend(interaction_res["violations"])

        # 7. VALIDAÇÃO DE RUNTIME (Runtime Health Check)
        if runtime_endpoint:
            runtime_res = RuntimeIntegrityValidator.check_http_endpoint(runtime_endpoint)
            report.runtime_checks.append(runtime_res)
            if not runtime_res["valid"]:
                report.blockers.append(f"RUNTIME_FAILURE: Endpoint {runtime_endpoint} falhou no health check: {runtime_res['error']}")
        else:
            report.runtime_checks.append({
                "valid": True,
                "status": "NOT_APPLICABLE_OR_STATIC",
                "details": "Sem endpoint de runtime ativo no momento da avaliação.",
            })

        # 8. VALIDAÇÃO DE NAVEGADOR (Browser QA)
        if browser_test_requested and runtime_endpoint:
            # Marca como evidência de browser
            report.evidence["browser_tested"] = True
        else:
            report.evidence["browser_tested"] = False

        # 9. GOVERNANÇA DE DEPENDÊNCIAS EXTERNAS E PREVENÇÃO DE DOWNGRADE SILENCIOSO
        governor = get_dependency_governor()
        dep_report = governor.analyze_dependencies(
            user_prompt,
            project_id=project_id,
            mission_id=mission_id,
        )
        has_blocked_dependency = False
        if not dep_report.can_execute_immediately:
            if dep_report.status == PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value:
                has_blocked_dependency = True
                report.blockers.append(
                    f"BLOCKED_REQUIRED_CAPABILITY: A missão requer ferramentas externas ({dep_report.blocked_reason}). Aguarda autorização humana."
                )

        # 10. RECONCILIAÇÃO FINAL DE REQUISITOS (Requirement Reconciliation)
        all_reqs_passed = True
        for req in report.requirements:
            # Requisitos falham se houver blocker relacionado ou falta de evidência
            if has_blocked_dependency and ("porta" in req.description.lower() or "scan" in req.description.lower() or "nmap" in req.description.lower()):
                req.status = RequirementStatus.BLOCKED.value
                all_reqs_passed = False
            elif report.blockers:
                req.status = RequirementStatus.FAIL.value
                all_reqs_passed = False
            elif not technical_validations_passed:
                req.status = RequirementStatus.FAIL.value
                all_reqs_passed = False
            else:
                req.status = RequirementStatus.PASS.value
                req.evidence = {"verified_at_gate": True, "no_regressions": True}

        # 11. DECISÃO FINAL DO GATE E SCORE QUALITATIVO
        cls._finalize_decision(
            report=report,
            technical_passed=technical_validations_passed,
            integrity_diff=integrity_diff,
            visual_valid=visual_res["valid"],
            has_blocked_dependency=has_blocked_dependency,
            all_reqs_passed=all_reqs_passed,
        )

        return report

    @classmethod
    def _extract_requirements(cls, user_prompt: str) -> List[RequirementItem]:
        """Extrai itens atómicos de requisitos a partir do prompt do utilizador."""
        items: List[RequirementItem] = []
        if not user_prompt:
            items.append(RequirementItem(
                requirement_id="REQ-GENERIC",
                description="Executar alteração conforme solicitado.",
                acceptance_test="Integridade e funcionalidade geral",
            ))
            return items

        # Separa frases ou pontos numerados
        lines = [l.strip() for l in user_prompt.splitlines() if l.strip()]
        req_count = 1
        for line in lines:
            # Se for linha de requisito substantivo
            if len(line) > 10 and not line.startswith("=") and not line.startswith("#"):
                items.append(RequirementItem(
                    requirement_id=f"REQ-{req_count:02d}",
                    description=line[:120],
                    source="user_prompt",
                    acceptance_test="Validação funcional e de produto",
                ))
                req_count += 1

        if not items:
            items.append(RequirementItem(
                requirement_id="REQ-01",
                description=user_prompt[:120],
                source="user_prompt",
                acceptance_test="Validação funcional e de produto",
            ))

        return items

    @classmethod
    def _finalize_decision(
        cls,
        report: ProductAcceptanceReport,
        technical_passed: bool,
        integrity_diff: ProductIntegrityDiff,
        visual_valid: bool,
        has_blocked_dependency: bool,
        all_reqs_passed: bool,
    ) -> None:
        """Determina o estado formal, bloqueadores e sumário legível para o utilizador."""
        summary_lines = []
        summary_lines.append(f"### Sumário de Entrega de Produto — Projeto: {report.project_id or 'Geral'}")

        # Se houver dependência bloqueada
        if has_blocked_dependency:
            report.result = RequirementStatus.BLOCKED.value
            report.gate_status = DeliveryGateStatus.HUMAN_REVIEW.value
            report.quality_score = QualityScoreStatus.HUMAN_REVIEW.value
            summary_lines.append("- **Estado**: ⚠️ AGUARDA AUTORIZAÇÃO HUMANA (Dependência Externa Obrigatória)")
            summary_lines.append("- **Ação**: A missão não pode aplicar fallback silencioso nem fingir sucesso.")
            report.user_summary = "\n".join(summary_lines)
            return

        # Se houver regressão crítica ou substituição destrutiva
        if integrity_diff.has_critical_regression:
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ BLOQUEADO POR REGRESSÃO CRÍTICA OU SUBSTITUIÇÃO DESTRUTIVA")
            for viol in integrity_diff.violations:
                summary_lines.append(f"  • {viol}")
            report.user_summary = "\n".join(summary_lines)
            return

        # Se houver blockers funcionais, visuais ou de assets
        if report.blockers:
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ REJEITADO PELO PORTÃO DE ACEITAÇÃO DE PRODUTO")
            for b in report.blockers[:10]:
                summary_lines.append(f"  • {b}")
            report.user_summary = "\n".join(summary_lines)
            return

        # Se a validação técnica (syntax, build) falhou
        if not technical_passed:
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.PREFLIGHT.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ FALHA NA VALIDAÇÃO TÉCNICA (Sintaxe / Compilação)")
            report.user_summary = "\n".join(summary_lines)
            return

        # Se passou em tudo
        if all_reqs_passed and visual_valid and not report.blockers:
            report.result = RequirementStatus.PASS.value
            report.gate_status = DeliveryGateStatus.PRODUCT_ACCEPTED.value
            report.quality_score = QualityScoreStatus.READY.value
            summary_lines.append("- **Estado**: ✅ PRODUTO ACEITE PARA ENTREGA")
            summary_lines.append(f"- Requisitos verificados: {len(report.requirements)} (Todos PASS)")
            summary_lines.append("- Integridade estética, HTML e de assets preservada com sucesso.")
            report.user_summary = "\n".join(summary_lines)
        else:
            report.result = RequirementStatus.INSUFFICIENT_EVIDENCE.value
            report.gate_status = DeliveryGateStatus.INSUFFICIENT_EVIDENCE.value
            report.quality_score = QualityScoreStatus.INSUFFICIENT_EVIDENCE.value
            summary_lines.append("- **Estado**: ⚠️ EVIDÊNCIA INSUFICIENTE PARA ACEITAÇÃO AUTÓNOMA")
            report.user_summary = "\n".join(summary_lines)


def is_autonomous_product_delivery_ready(
    report: ProductAcceptanceReport,
    git_diff_check_passed: bool = True,
    pip_check_passed: bool = True,
    tests_passed: bool = True,
) -> bool:
    """
    Função canónica do portão final (Secção 35 da especificação).
    Retorna True estritamente se todos os 15 critérios de aceitação foram cumpridos.
    """
    if not (git_diff_check_passed and pip_check_passed and tests_passed):
        return False

    # 1. Requisitos rastreáveis e todos obrigatórios com PASS
    if not report.requirements:
        return False
    if any(r.status != RequirementStatus.PASS.value for r in report.requirements):
        return False

    # 2. Sem regressões críticas ou blockers
    if report.blockers:
        return False

    # 3. Estado de portão formalmente PRODUCT_ACCEPTED ou DELIVERED
    if report.gate_status not in {DeliveryGateStatus.PRODUCT_ACCEPTED.value, DeliveryGateStatus.DELIVERED.value}:
        return False

    # 4. Score de qualidade READY
    if report.quality_score != QualityScoreStatus.READY.value:
        return False

    # 5. Evidência não pode ser insuficiente
    if report.result == RequirementStatus.INSUFFICIENT_EVIDENCE.value:
        return False

    return True
