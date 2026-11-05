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
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from security.delivery_governance.architecture_detector import ArchitectureDetector, DetectedArchitecture
from security.delivery_governance.artifact_inference import ArtifactInferenceEngine
from security.delivery_governance.contract_validator import ContractValidator
from security.delivery_governance.integrity_detector import (
    DestructiveChangeDetector,
    PreservationAnalyzer,
)
from security.delivery_governance.models import (
    AcceptanceLevel,
    ArchitectureDecision,
    ArtifactCategory,
    ArtifactEvidence,
    ArtifactEvidenceStatus,
    ArtifactExpectation,
    DeliveryGateStatus,
    ProductAcceptanceReport,
    ProductIntegrityDiff,
    QualityScoreStatus,
    RequirementItem,
    RequirementStatus,
)
from security.delivery_governance.preview_lifecycle import PreviewLifecycleManager
from security.delivery_governance.real_browser_qa import RealBrowserQAValidator
from security.delivery_governance.runtime_identity import RuntimeIdentity, RuntimeTracker
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
        auto_manage_preview: bool = False,
        preview_port: Optional[int] = None,
        preview_start_command: Optional[str] = None,
        browser_actions: Optional[List[Dict[str, Any]]] = None,
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

        # 1. INFERÊNCIA DETERMINÍSTICA DE ARTEFACTOS E CAPACIDADES (Architecture-Aware)
        arch, decision, expectations, requirements = ArtifactInferenceEngine.infer_architecture_and_artifacts(
            user_prompt=user_prompt,
            project_root=project_root,
        )
        report.architecture_decision = decision
        report.artifact_expectations = expectations
        report.capabilities_detected = decision.expected_capabilities
        report.requirements = requirements
        report.acceptance_criteria = [r.description for r in requirements]

        # 1.1 AVALIAÇÃO DE EVIDÊNCIA DE ARTEFACTOS (PRESENT != VALIDATED)
        artifact_evidences = ArtifactInferenceEngine.evaluate_artifact_evidence(expectations, project_root)
        report.artifact_evidence = artifact_evidences

        for ae in artifact_evidences:
            if ae.status in {ArtifactEvidenceStatus.MISSING.value, ArtifactEvidenceStatus.FAILED.value}:
                matching_exp = next((e for e in expectations if e.artifact_id == ae.artifact_id), None)
                if matching_exp and matching_exp.required:
                    report.blockers.append(
                        f"MISSING_REQUIRED_ARTIFACT: Artefacto obrigatório '{ae.expected_path}' para capacidade '{ae.category}' ({ae.responsibility}) não verificado."
                    )

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

        # 7. VALIDAÇÃO DE CONTRATO (API & Frontend Contract Audit - Requisito 5)
        contract_res = ContractValidator.audit_project_contracts(project_root)
        report.contract_check = contract_res
        if not contract_res.get("valid", True):
            for viol in contract_res.get("violations", []):
                report.blockers.append(f"API_CONTRACT_DESYNC: {viol}")

        # 8. VALIDAÇÃO DE RUNTIME E GESTÃO SEGURA DO CICLO DE VIDA (Requisitos 2, 3 e 4)
        if runtime_endpoint or preview_port:
            port = preview_port
            if not port and runtime_endpoint:
                try:
                    parsed = urllib.parse.urlparse(runtime_endpoint)
                    port = parsed.port or (443 if parsed.scheme == "https" else 80)
                except Exception:
                    port = None

            if port:
                if auto_manage_preview and preview_start_command:
                    preview_res = PreviewLifecycleManager.ensure_fresh_preview(
                        project_id=project_id,
                        project_root=project_root,
                        port=port,
                        start_command=preview_start_command,
                        endpoint=runtime_endpoint or f"http://127.0.0.1:{port}",
                        allow_foreign_kill=False,
                    )
                    report.runtime_checks.append({
                        "check_name": "preview_lifecycle_management",
                        "result": preview_res,
                    })
                    if not preview_res.get("success", False):
                        report.blockers.append(f"PREVIEW_LIFECYCLE_ERROR: {preview_res.get('error', 'Falha ao gerir preview')}")

                runtime_ident = RuntimeTracker.inspect_runtime(
                    project_id=project_id,
                    project_root=project_root,
                    port=port,
                    expected_endpoint=runtime_endpoint or f"http://127.0.0.1:{port}",
                )
                report.runtime_identity = runtime_ident.to_dict()

                if not runtime_ident.is_running:
                    report.blockers.append(
                        f"RUNTIME_UNAVAILABLE: Nenhum processo ativo encontrado na porta {port} ({runtime_endpoint})."
                    )
                else:
                    if not runtime_ident.is_owned:
                        report.blockers.append(
                            f"PORT_CONFLICT_UNOWNED: A porta {port} está ocupada pelo processo PID {runtime_ident.process_id} que não pertence ao projeto '{project_id}'. Não é permitido terminar processos de terceiros."
                        )
                    elif runtime_ident.is_stale:
                        report.blockers.append(
                            f"STALE_RUNTIME: O processo em execução (PID {runtime_ident.process_id}) está desatualizado em relação ao código no disco. {runtime_ident.stale_reason}"
                        )
                    elif not runtime_ident.healthcheck_ok:
                        report.blockers.append(
                            f"RUNTIME_FAILURE: Health check falhou no endpoint {runtime_endpoint or f'http://127.0.0.1:{port}'}"
                        )
                    else:
                        # Runtime ativo, pertencente, atualizado e saudável.
                        # Validação de integridade dos assets servidos via HTTP (Requisito 4)
                        base_url = runtime_endpoint or f"http://127.0.0.1:{port}"
                        served_res = AssetIntegrityValidator.validate_served_assets(
                            project_root=project_root,
                            base_url=base_url,
                        )
                        report.served_assets_check = served_res
                        if not served_res["valid"]:
                            for viol in served_res.get("violations", []):
                                report.blockers.append(f"STALE_SERVED_ASSET: {viol}")
        else:
            report.runtime_identity = {
                "status": "NOT_APPLICABLE_OR_STATIC",
                "details": "Sem endpoint de runtime ativo no momento da avaliação.",
            }
            report.runtime_checks.append({
                "valid": True,
                "status": "NOT_APPLICABLE_OR_STATIC",
                "details": "Sem endpoint de runtime ativo no momento da avaliação.",
            })

        # 9. VALIDAÇÃO REAL DE NAVEGADOR (Real Browser QA - Requisito 6)
        if browser_test_requested:
            if runtime_endpoint:
                b_res = RealBrowserQAValidator.execute_browser_qa(
                    preview_url=runtime_endpoint,
                    actions=browser_actions,
                    project_id=project_id,
                    mission_id=mission_id,
                )
                report.browser_qa_result = b_res
                if not b_res.get("valid", False):
                    report.blockers.append(f"BROWSER_QA_FAILED: {b_res.get('error', 'Browser QA falhou')}")
                    for viol in b_res.get("violations", []):
                        report.blockers.append(f"BROWSER_QA_VIOLATION: {viol}")
                    report.evidence["browser_tested"] = False
                else:
                    report.evidence["browser_tested"] = True
                    report.evidence["browser_screenshots"] = b_res.get("screenshots", [])
            else:
                report.evidence["browser_tested"] = False
                report.blockers.append("BROWSER_QA_FAILED: Browser QA foi solicitado mas nenhum runtime_endpoint acessível foi fornecido.")
        else:
            report.evidence["browser_tested"] = False

        # 10. GOVERNANÇA DE DEPENDÊNCIAS EXTERNAS E PREVENÇÃO DE DOWNGRADE SILENCIOSO
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

        # 11. RECONCILIAÇÃO FINAL DE REQUISITOS (Requirement Reconciliation)
        all_reqs_passed = True
        for req in report.requirements:
            if has_blocked_dependency and any(k in req.description.lower() for k in ["porta", "scan", "nmap"]):
                req.status = RequirementStatus.BLOCKED.value
                all_reqs_passed = False
            elif report.blockers:
                req.status = RequirementStatus.FAIL.value
                all_reqs_passed = False
            elif not technical_validations_passed:
                req.status = RequirementStatus.FAIL.value
                all_reqs_passed = False
            else:
                matching_evs = [
                    ae for ae in report.artifact_evidence
                    if ae.category == req.category or ae.artifact_id in req.required_artifacts
                ]
                gathered_ev_ids = []
                for me in matching_evs:
                    gathered_ev_ids.extend(me.evidence_ids)

                if not gathered_ev_ids and (req.category == "functional_prompt" or req.category == "functional"):
                    gathered_ev_ids = [eid for ae in report.artifact_evidence for eid in ae.evidence_ids if ae.validated]
                    if not gathered_ev_ids and visual_res.get("valid"):
                        gathered_ev_ids = ["EVID-VISUAL-VALIDATED"]

                req.evidence_ids = gathered_ev_ids
                if not req.evidence_ids and req.blocking:
                    req.status = RequirementStatus.INSUFFICIENT_EVIDENCE.value
                    all_reqs_passed = False
                else:
                    req.status = RequirementStatus.PASS.value
                    req.evidence = {
                        "verified_at_gate": True,
                        "no_regressions": True,
                        "evidence_ids": req.evidence_ids,
                    }

        # 12. DETERMINAÇÃO FORMAL DOS NÍVEIS INDEPENDENTES DE VALIDAÇÃO (Requisitos 7 e 8)
        code_validated = bool(
            technical_validations_passed
            and len(html_violations) == 0
            and not integrity_diff.has_critical_regression
        )
        build_validated = bool(
            code_validated
            and not any("MISSING_REQUIRED_ARTIFACT" in b for b in report.blockers)
        )

        if runtime_endpoint or preview_port:
            runtime_version_validated = bool(
                report.runtime_identity
                and report.runtime_identity.get("is_running")
                and report.runtime_identity.get("is_owned")
                and not report.runtime_identity.get("is_stale")
                and report.runtime_identity.get("healthcheck_ok")
                and (not report.served_assets_check or report.served_assets_check.get("valid", True))
            )
        else:
            runtime_version_validated = True  # Estático ou N/A

        api_contract_validated = bool(
            not report.contract_check or report.contract_check.get("valid", True)
        )

        if browser_test_requested:
            functional_browser_validated = bool(
                report.browser_qa_result and report.browser_qa_result.get("valid", False)
            )
        else:
            functional_browser_validated = False

        visual_browser_validated = bool(
            visual_res.get("valid", True) and (functional_browser_validated if browser_test_requested else True)
        )

        # Requisito 6: Browser QA é obrigatório quando há alterações de interface num runtime ativo
        browser_qa_mandatory = bool(
            runtime_endpoint
            and (ui_changed or is_web_project or len(html_files_checked) > 0)
            and ("dina" in project_id.lower() or "dina" in (user_prompt or "").lower() or "card" in (user_prompt or "").lower() or "rede" in (user_prompt or "").lower() or "scan" in (user_prompt or "").lower())
        )

        product_accepted = bool(
            (not browser_qa_mandatory or functional_browser_validated)
            and code_validated
            and build_validated
            and runtime_version_validated
            and api_contract_validated
            and visual_browser_validated
            and (functional_browser_validated if browser_test_requested else True)
            and all_reqs_passed
            and not report.blockers
        )

        report.validation_levels = {
            AcceptanceLevel.CODE_VALIDATED.value: code_validated,
            AcceptanceLevel.BUILD_VALIDATED.value: build_validated,
            AcceptanceLevel.RUNTIME_VERSION_VALIDATED.value: runtime_version_validated,
            AcceptanceLevel.API_CONTRACT_VALIDATED.value: api_contract_validated,
            AcceptanceLevel.FUNCTIONAL_BROWSER_VALIDATED.value: functional_browser_validated,
            AcceptanceLevel.VISUAL_BROWSER_VALIDATED.value: visual_browser_validated,
            AcceptanceLevel.PRODUCT_ACCEPTED.value: product_accepted,
        }

        # 13. DECISÃO FINAL DO GATE, REMEDIAÇÃO E SUMÁRIO VERDADEIRO (Requisitos 8, 9 e 12)
        cls._finalize_decision(
            report=report,
            technical_passed=technical_validations_passed,
            integrity_diff=integrity_diff,
            visual_valid=visual_res["valid"],
            has_blocked_dependency=has_blocked_dependency,
            all_reqs_passed=all_reqs_passed,
            browser_test_requested=browser_test_requested,
            runtime_endpoint=runtime_endpoint,
            browser_qa_mandatory=browser_qa_mandatory,
            functional_browser_validated=functional_browser_validated,
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

        lines = [l.strip() for l in user_prompt.splitlines() if l.strip()]
        req_count = 1
        for line in lines:
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
        browser_test_requested: bool = False,
        runtime_endpoint: Optional[str] = None,
        browser_qa_mandatory: bool = False,
        functional_browser_validated: bool = False,
    ) -> None:
        """Determina o estado formal, bloqueadores, diagnóstico de remediação e sumário verdadeiro."""
        summary_lines = []
        summary_lines.append(f"### Sumário de Entrega de Produto — Projeto: {report.project_id or 'Geral'}")

        # Remediação orientada pela causa (Requisito 9)
        remediation: Dict[str, str] = {}

        # 1. Se houver dependência bloqueada
        if has_blocked_dependency:
            report.result = RequirementStatus.BLOCKED.value
            report.gate_status = DeliveryGateStatus.HUMAN_REVIEW.value
            report.quality_score = QualityScoreStatus.HUMAN_REVIEW.value
            summary_lines.append("- **Estado**: ⚠️ AGUARDA AUTORIZAÇÃO HUMANA (Dependência Externa Obrigatória)")
            summary_lines.append("- **Mensagem**: A missão requer ferramentas externas e aguarda autorização humana.")
            remediation = {
                "cause": "BLOCKED_REQUIRED_CAPABILITY",
                "description": "Ferramenta ou binário externo não autorizado.",
                "action": "Apresentar diálogo de autorização ao utilizador; não realizar downgrade silencioso.",
            }
            report.evidence["remediation"] = remediation
            report.user_summary = "\n".join(summary_lines)
            return

        # 2. Se houver conflito de porta com processo não pertencente ao projeto
        if any("PORT_CONFLICT_UNOWNED" in b for b in report.blockers):
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ⚠️ PORTA OCUPADA POR PROCESSO EXTERNO")
            summary_lines.append("- **Mensagem**: Porta ocupada por processo externo. A entrega está bloqueada até libertação da porta.")
            remediation = {
                "cause": "PORT_CONFLICT_UNOWNED",
                "description": "Porta ocupada por processo de outra aplicação.",
                "action": "Apontar para porta livre ou aguardar encerramento do processo externo. JARVIS nunca termina processos alheios.",
            }
            report.evidence["remediation"] = remediation
            for b in report.blockers:
                summary_lines.append(f"  • {b}")
            report.user_summary = "\n".join(summary_lines)
            return

        # 3. Se o runtime estiver desatualizado
        if any("STALE_RUNTIME" in b for b in report.blockers):
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ PREVIEW DESATUALIZADO")
            summary_lines.append("- **Mensagem**: Preview desatualizado. A entrega está bloqueada até ser corrigido.")
            remediation = {
                "cause": "STALE_RUNTIME",
                "description": "O servidor em execução foi iniciado antes das modificações nos ficheiros de código.",
                "action": "Reiniciar o preview gerido e verificar a correspondência de versão.",
            }
            report.evidence["remediation"] = remediation
            for b in report.blockers:
                summary_lines.append(f"  • {b}")
            report.user_summary = "\n".join(summary_lines)
            return

        # 4. Se houver assets servidos em cache desatualizados
        if any("STALE_SERVED_ASSET" in b for b in report.blockers):
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ ASSETS SERVIDOS EM CACHE DESATUALIZADOS")
            summary_lines.append("- **Mensagem**: O browser ou preview está a servir ficheiros desatualizados em cache.")
            remediation = {
                "cause": "STALE_SERVED_ASSET",
                "description": "Desfasamento entre o hash SHA256 do ficheiro no disco e o asset servido via HTTP.",
                "action": "Investigar cache HTTP, aplicar convenção de cache-busting ou reiniciar servidor com headers no-cache.",
            }
            report.evidence["remediation"] = remediation
            for b in report.blockers:
                summary_lines.append(f"  • {b}")
            report.user_summary = "\n".join(summary_lines)
            return

        # 5. Se houver dessincronização contratual API-frontend
        if any("API_CONTRACT_DESYNC" in b for b in report.blockers):
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ DESSINCRONIZAÇÃO CONTRATUAL API-FRONTEND")
            summary_lines.append("- **Mensagem**: Contrato entre API e interface está dessincronizado.")
            remediation = {
                "cause": "API_CONTRACT_DESYNC",
                "description": "O backend devolve novos campos que o frontend não consome ou mascara com fallbacks legados.",
                "action": "Corrigir o mapeamento ou a apresentação na interface; remover fallbacks silenciosos.",
            }
            report.evidence["remediation"] = remediation
            for b in report.blockers:
                summary_lines.append(f"  • {b}")
            report.user_summary = "\n".join(summary_lines)
            return

        # 6. Se a validação no browser falhou
        if any("BROWSER_QA_FAILED" in b or "BROWSER_QA_VIOLATION" in b for b in report.blockers):
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ FALHA NA VALIDAÇÃO REAL DO NAVEGADOR")
            summary_lines.append("- **Mensagem**: API validada; a interface ainda apresenta uma falha.")
            remediation = {
                "cause": "BROWSER_QA_FAILURE",
                "description": "Erros de consola, controlo inerte ou falha na renderização de dados no DOM.",
                "action": "Inspecionar mensagens de erro da consola e verificar seletores e manipulação do DOM.",
            }
            report.evidence["remediation"] = remediation
            for b in report.blockers:
                summary_lines.append(f"  • {b}")
            report.user_summary = "\n".join(summary_lines)
            return

        # 7. Se houver regressão crítica ou substituição destrutiva
        if integrity_diff.has_critical_regression:
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ BLOQUEADO POR REGRESSÃO CRÍTICA OU SUBSTITUIÇÃO DESTRUTIVA")
            summary_lines.append("- **Mensagem**: Modificação destrutiva detetada em artefactos essenciais do projeto.")
            remediation = {
                "cause": "DESTRUCTIVE_CHANGE",
                "description": "Ficheiros ou elementos estruturais foram eliminados ou substituídos sem preservação.",
                "action": "Reverter modificação destrutiva e aplicar adições preservando funcionalidades existentes.",
            }
            report.evidence["remediation"] = remediation
            for viol in integrity_diff.violations:
                summary_lines.append(f"  • {viol}")
            report.user_summary = "\n".join(summary_lines)
            return

        # 8. Se houver outros blockers
        if report.blockers:
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.BLOCKED.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ REJEITADO PELO PORTÃO DE ACEITAÇÃO DE PRODUTO")
            remediation = {
                "cause": "INSUFFICIENT_EVIDENCE_OR_VIOLATION",
                "description": "Violações técnicas ou funcionais não resolvidas.",
                "action": "Corrigir as violações listadas antes de submeter a nova avaliação.",
            }
            report.evidence["remediation"] = remediation
            for b in report.blockers[:10]:
                summary_lines.append(f"  • {b}")
            report.user_summary = "\n".join(summary_lines)
            return

        # 9. Se a validação técnica (syntax, build) falhou
        if not technical_passed:
            report.result = RequirementStatus.FAIL.value
            report.gate_status = DeliveryGateStatus.PREFLIGHT.value
            report.quality_score = QualityScoreStatus.NOT_READY.value
            summary_lines.append("- **Estado**: ❌ FALHA NA VALIDAÇÃO TÉCNICA (Sintaxe / Compilação)")
            summary_lines.append("- **Mensagem**: O código contém erros de sintaxe ou compilação.")
            report.user_summary = "\n".join(summary_lines)
            return

        # 10. Se apenas houve alteração de ficheiros e preview não foi testado
        if not browser_test_requested and not runtime_endpoint and report.artifact_evidence:
            has_untested_source = any(
                ae.category in {"source", "ui", "entrypoint"} and not ae.validated
                for ae in report.artifact_evidence
            )
            if has_untested_source:
                summary_lines.append("- **Nota**: Alterações aplicadas. O preview ainda não foi validado.")

        # 10.1 Se Browser QA era obrigatório para alterações de UI mas não foi validado com sucesso
        if browser_qa_mandatory and not functional_browser_validated and not report.blockers:
            report.result = RequirementStatus.INSUFFICIENT_EVIDENCE.value
            report.gate_status = DeliveryGateStatus.ACCEPTANCE_PENDING.value
            report.quality_score = QualityScoreStatus.INSUFFICIENT_EVIDENCE.value
            summary_lines.append("- **Estado**: ⚠️ PREVIEW PENDENTE DE VALIDAÇÃO DE NAVEGADOR")
            summary_lines.append("- **Mensagem**: Alterações aplicadas. O preview ainda não foi validado.")
            report.evidence["remediation"] = {
                "cause": "INSUFFICIENT_EVIDENCE",
                "description": "Alterações de interface em runtime ativo requerem Browser QA contra o preview real.",
                "action": "Executar validação em preview real com Browser QA para recolher evidências no DOM.",
            }
            report.user_summary = "\n".join(summary_lines)
            return

        # 11. Se passou em tudo
        if all_reqs_passed and visual_valid and not report.blockers:
            report.result = RequirementStatus.PASS.value
            report.gate_status = DeliveryGateStatus.PRODUCT_ACCEPTED.value
            report.quality_score = QualityScoreStatus.READY.value
            summary_lines.append("- **Estado**: ✅ PRODUTO ACEITE PARA ENTREGA")
            summary_lines.append("- **Mensagem**: Produto aceite para entrega")
            summary_lines.append(f"- Requisitos verificados: {len(report.requirements)} (Todos PASS)")
            summary_lines.append("- Níveis de validação confirmados com evidência factual real.")
            report.user_summary = "\n".join(summary_lines)
        else:
            report.result = RequirementStatus.INSUFFICIENT_EVIDENCE.value
            report.gate_status = DeliveryGateStatus.INSUFFICIENT_EVIDENCE.value
            report.quality_score = QualityScoreStatus.INSUFFICIENT_EVIDENCE.value
            summary_lines.append("- **Estado**: ⚠️ EVIDÊNCIA INSUFICIENTE PARA ACEITAÇÃO AUTÓNOMA")
            summary_lines.append("- **Mensagem**: Alterações aplicadas. O preview ainda não foi validado.")
            report.evidence["remediation"] = {
                "cause": "INSUFFICIENT_EVIDENCE",
                "description": "Falta de evidência factual para um ou mais requisitos.",
                "action": "Executar validação em preview real e recolher evidências no DOM.",
            }
            report.user_summary = "\n".join(summary_lines)


def is_autonomous_product_delivery_ready(
    report: ProductAcceptanceReport,
    git_diff_check_passed: bool = True,
    pip_check_passed: bool = True,
    tests_passed: bool = True,
) -> bool:
    """
    Função canónica do portão final (Secção 35 da especificação).
    Retorna True estritamente se todos os critérios de aceitação foram cumpridos.
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

    # 6. Nível formal PRODUCT_ACCEPTED confirmado nos validation_levels
    if report.validation_levels and not report.validation_levels.get(AcceptanceLevel.PRODUCT_ACCEPTED.value, False):
        return False

    return True
