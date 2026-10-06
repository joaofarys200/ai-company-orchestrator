"""
JARVIS OS — External Dependency Governance & Anti-Silent-Downgrade Engine
Enforces explicit dependency classification (REQUIRED, OPTIONAL, ALTERNATIVE),
requirement traceability, and blocks silent fallbacks that fail acceptance criteria.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from security.permission_gateway.capability_checker import CapabilityChecker
from security.permission_gateway.gateway import (
    PermissionGatewayService,
    get_permission_gateway_service,
)
from security.permission_gateway.models import (
    ApprovalSemantics,
    CapabilityStatus,
    DependencyClassification,
    DependencyRequirement,
    DependencyResolutionReport,
    PermissionRequest,
    PermissionRequestStatus,
    PermissionRiskLevel,
)

logger = logging.getLogger("Jarvis.DependencyGovernance")


class DependencyGovernanceError(Exception):
    """Erro base de governança de dependências externas."""


class SilentDowngradePreventedError(DependencyGovernanceError):
    """Lançado quando uma dependência obrigatória tenta ser substituída silenciosamente por fallback insuficiente."""


class FallbackCriteriaViolationError(DependencyGovernanceError):
    """Lançado quando uma alternativa limitada não cumpre os acceptance criteria da tarefa."""


class DependencyGovernanceService:
    """
    Serviço central de classificação, rastreabilidade e governança de dependências externas.
    Garante que:
    1. Dependências REQUIRED nunca sofram downgrade silencioso.
    2. Fallbacks só sejam aplicados automaticamente se cumprirem 100% dos critérios (ALTERNATIVE).
    3. Dependências OPTIONAL não bloqueiem desnecessariamente.
    4. Ações de aprovação sejam decompostas em AUTHORIZE_USE vs AUTHORIZE_INSTALLATION.
    """

    def __init__(self, gateway: Optional[PermissionGatewayService] = None):
        self._gateway = gateway

    @property
    def gateway(self) -> PermissionGatewayService:
        if self._gateway is not None:
            return self._gateway
        return get_permission_gateway_service()

    def classify_dependency(
        self,
        tool_name: str,
        required_for: str,
        acceptance_criteria: Optional[List[str]] = None,
        fallback: Optional[str] = None,
        fallback_capability: Optional[str] = None,
        classification: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> DependencyRequirement:
        """
        Classifica formalmente uma dependência externa com base no objetivo e critérios.
        """
        criteria = acceptance_criteria or []
        lower_tool = tool_name.lower().strip()
        lower_rf = required_for.lower().strip()

        # Determina satisfação dos critérios pelo fallback
        satisfies = self.evaluate_fallback_satisfaction(criteria, fallback_capability or "")

        # Classificação padrão baseada na semântica
        if classification is None:
            if satisfies and fallback:
                resolved_class = DependencyClassification.ALTERNATIVE.value
            elif any(
                term in lower_rf or any(term in c.lower() for c in criteria)
                for term in ("active", "port", "porta", "sweep", "raw", "varredura ativa", "transcod", "ocr")
            ):
                resolved_class = DependencyClassification.REQUIRED.value
            else:
                resolved_class = DependencyClassification.OPTIONAL.value
        else:
            resolved_class = classification

        # Metadados e limitações específicas para ferramentas conhecidas
        risk = PermissionRiskLevel.LOW_RISK_MUTATION.value
        privs = "Userland"
        fallback_desc = fallback
        limitations = None

        if lower_tool == "nmap":
            risk = PermissionRiskLevel.HIGH_RISK_MUTATION.value
            privs = "Administrador / Npcap"
            if not fallback:
                fallback = "arp -a"
            if not fallback_capability:
                fallback_capability = "passive ARP discovery only"
            fallback_desc = "Usar tabela ARP do Windows (arp -a + netstat) e sockets TCP permitidos."
            limitations = "Não executa varredura ativa de portas nem fornece a mesma cobertura de rede."
            satisfies = False if any("port" in c.lower() or "active" in c.lower() or "varredura ativa" in c.lower() for c in criteria) else satisfies
        elif lower_tool == "ffmpeg":
            risk = PermissionRiskLevel.LOW_RISK_MUTATION.value
            privs = "Userland"
            if not fallback:
                fallback = "native_media"
            if not fallback_capability:
                fallback_capability = "standard media reader"
            fallback_desc = "Processamento nativo limitado sem transcodificação avançada."
            limitations = "Formatos não padrão ou codecs proprietários não são suportados nativamente."
        elif lower_tool in {"tesseract", "ocr"}:
            risk = PermissionRiskLevel.LOW_RISK_MUTATION.value
            privs = "Userland"
            if not fallback:
                fallback = "text_extractor"
            if not fallback_capability:
                fallback_capability = "plain text extractor"
            fallback_desc = "Extração de texto simples em ficheiros estruturados sem OCR."
            limitations = "Imagens rasterizadas ou PDFs escaneados não terão texto reconhecido."

        return DependencyRequirement(
            tool_name=tool_name,
            reason=reason or f"Necessário para {required_for}",
            required_for=required_for,
            acceptance_criteria=criteria,
            classification=resolved_class,
            risk_level=risk,
            required_privileges=privs,
            fallback=fallback,
            fallback_description=fallback_desc,
            fallback_capability=fallback_capability,
            fallback_satisfies_acceptance_criteria=satisfies,
            fallback_limitations=limitations,
        )

    def evaluate_fallback_satisfaction(
        self,
        acceptance_criteria: List[str],
        fallback_capability: str,
    ) -> bool:
        """
        Avalia se a capacidade do fallback cumpre TODOS os critérios de aceitação.
        Retorna False se houver qualquer discrepância essencial.
        """
        if not acceptance_criteria:
            return True

        lower_cap = fallback_capability.lower()
        strict_keywords = {
            "port": "porta",
            "open ports": "portas abertas",
            "active network discovery": "varredura ativa",
            "active scan": "varredura ativa",
            "raw socket": "socket de baixo nivel",
            "transcode": "transcodificacao",
            "ocr text recognition": "reconhecimento otico",
        }

        for crit in acceptance_criteria:
            lower_crit = crit.lower()
            # Se o critério exige varredura ativa / portas e o fallback é apenas ARP passivo:
            if any(k in lower_crit for k in ("port", "porta", "active", "ativa", "varredura")):
                if "passive" in lower_cap or "arp" in lower_cap or "cache" in lower_cap:
                    return False
            # Se exige OCR e o fallback é apenas leitor de texto simples:
            if "ocr" in lower_crit and "ocr" not in lower_cap:
                return False
            # Se exige transcodificação e o fallback é nativo sem transcode:
            if "transcode" in lower_crit and "sem transcod" in lower_cap:
                return False

        return True

    def analyze_dependencies(
        self,
        objective: str,
        proposed_tools: Optional[List[str]] = None,
        criteria: Optional[List[str]] = None,
        project_id: str = "",
        mission_id: str = "",
        execution_id: str = "",
    ) -> DependencyResolutionReport:
        """
        Analisa o plano de trabalho antes da execução.
        Se detetar uma dependência REQUIRED não disponível cujo fallback não satisfaz os critérios,
        gera o pedido de permissão Just-In-Time e coloca o relatório em AWAITING_HUMAN_APPROVAL.
        """
        report = DependencyResolutionReport()
        lower_obj = (objective or "").lower()

        detected_tools = list(proposed_tools or [])
        inferred_criteria = list(criteria or [])

        # Inferência de ferramentas e critérios com base no objetivo
        if re.search(r"\b(nmap|port scan|varredura de rede|network scan|portas abertas)\b", lower_obj):
            if "Nmap" not in detected_tools:
                detected_tools.append("Nmap")
            if not inferred_criteria:
                inferred_criteria.extend(["discover active hosts", "discover open ports"])

        if re.search(r"\b(ffmpeg|extrair audio|converter video|transcodific)\b", lower_obj):
            if "FFmpeg" not in detected_tools:
                detected_tools.append("FFmpeg")
            if not inferred_criteria:
                inferred_criteria.append("transcode media stream")

        if re.search(r"\b(ocr|tesseract|reconhecer texto de imagem)\b", lower_obj):
            if "Tesseract" not in detected_tools:
                detected_tools.append("Tesseract")
            if not inferred_criteria:
                inferred_criteria.append("extract text via OCR")

        for tool in detected_tools:
            # Classifica formalmente
            dep = self.classify_dependency(
                tool_name=tool,
                required_for=objective[:120],
                acceptance_criteria=inferred_criteria,
            )

            # Executa verificação técnica de capacidade
            cap_status, cap_details = CapabilityChecker.check_capability(
                dep.tool_name,
                required_privileges=dep.required_privileges,
            )

            if cap_status == CapabilityStatus.AVAILABLE:
                if dep.classification == DependencyClassification.REQUIRED.value:
                    report.required_dependencies.append(dep)
                elif dep.classification == DependencyClassification.OPTIONAL.value:
                    report.optional_dependencies.append(dep)
                else:
                    report.alternatives.append(dep)
            else:
                # Dependência não está disponível localmente
                if dep.classification == DependencyClassification.REQUIRED.value:
                    report.required_dependencies.append(dep)
                    report.unavailable_required.append(dep)

                    # INVARIANTE: Se o fallback NÃO cumpre os critérios, NUNCA fazer downgrade silencioso!
                    if not dep.fallback_satisfies_acceptance_criteria:
                        report.can_execute_immediately = False
                        report.status = PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value
                        report.blocked_reason = (
                            f"A ferramenta obrigatória '{dep.tool_name}' não está instalada. "
                            f"A alternativa '{dep.fallback}' não cumpre todos os requisitos (critérios não satisfeitos: {inferred_criteria})."
                        )

                        # Regista o pedido formal no Permission Gateway
                        perm_req = self.gateway.create_request(
                            tool_name=dep.tool_name,
                            requested_operation=f"Execução de {dep.tool_name} para {dep.required_for}",
                            reason=dep.reason,
                            risk_level=dep.risk_level,
                            required_privileges=dep.required_privileges,
                            affected_resources=[project_id or "local_system"],
                            project_id=project_id,
                            mission_id=mission_id,
                            execution_id=execution_id,
                            alternative_available=bool(dep.fallback),
                            fallback_description=dep.fallback_description,
                            dependency_id=dep.dependency_id,
                            classification=dep.classification,
                            required_for=dep.required_for,
                            acceptance_criteria=dep.acceptance_criteria,
                            fallback_capability=dep.fallback_capability,
                            fallback_satisfies_acceptance_criteria=dep.fallback_satisfies_acceptance_criteria,
                            fallback_limitations=dep.fallback_limitations,
                            approval_semantic=ApprovalSemantics.AUTHORIZE_USE.value,
                        )
                        report.approval_requests.append(perm_req.request_id)
                    else:
                        # Fallback cumpre critérios completamente
                        report.fallback_decisions[dep.tool_name] = {
                            "fallback": dep.fallback,
                            "reason": "Fallback satisfaz 100% dos critérios.",
                        }

                elif dep.classification == DependencyClassification.OPTIONAL.value:
                    # Opcional ausente não bloqueia execução
                    report.optional_dependencies.append(dep)
                    report.fallback_decisions[dep.tool_name] = {
                        "fallback": dep.fallback,
                        "reason": "Dependência opcional indisponível; usando implementação base.",
                    }

                elif dep.classification == DependencyClassification.ALTERNATIVE.value:
                    # Alternativa válida cumpre critérios
                    report.alternatives.append(dep)
                    report.fallback_decisions[dep.tool_name] = {
                        "fallback": dep.fallback,
                        "reason": "Alternativa equivalente disponível.",
                    }

        if report.unavailable_required and not report.can_execute_immediately:
            report.status = PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value
        else:
            report.status = PermissionRequestStatus.READY_TO_EXECUTE.value
            report.can_execute_immediately = True

        return report

    def resolve_user_decision(
        self,
        request_id: str,
        action: str,
        user_id: str = "user",
    ) -> Dict[str, Any]:
        """
        Processa a decisão explícita do utilizador no modal central:
        - AUTHORIZE_USE: Valida capacidade; se binário faltar, solicita AUTHORIZE_INSTALLATION.
        - AUTHORIZE_INSTALLATION: Executa verificação UAC / admin antes de prosseguir.
        - USE_LIMITED_FALLBACK: Bloqueia com aviso se critérios forem violados.
        - CANCEL: Cancela a operação e transiciona para DENIED.
        """
        req = self.gateway.get_request(request_id)
        if not req:
            raise DependencyGovernanceError(f"Pedido {request_id} não encontrado.")

        action_norm = action.upper().strip()

        # ----------------------------------------------------------------------
        # 1. Autorização de Uso
        # ----------------------------------------------------------------------
        if action_norm in {"AUTHORIZE_USE", "APPROVE", "AUTORIZAR"}:
            approved_req = self.gateway.approve_request(request_id, decided_by=user_id)
            cap_status, cap_details = CapabilityChecker.check_capability(
                approved_req.tool_name,
                required_privileges=approved_req.required_privileges,
            )

            if cap_status == CapabilityStatus.AVAILABLE:
                approved_req.status = PermissionRequestStatus.EXECUTION_READY.value
                approved_req.capability_status = CapabilityStatus.AVAILABLE.value
                return {
                    "request_id": request_id,
                    "status": "EXECUTION_READY",
                    "capability": "AVAILABLE",
                    "message": f"Ferramenta {approved_req.tool_name} aprovada e disponível para execução.",
                }

            if cap_status == CapabilityStatus.INSTALLATION_REQUIRED:
                # Transiciona para INSTALLATION_REQUIRED e cria pedido de instalação
                approved_req.status = PermissionRequestStatus.INSTALLATION_REQUIRED.value
                approved_req.capability_status = CapabilityStatus.INSTALLATION_REQUIRED.value
                install_req = self.gateway.create_request(
                    tool_name=approved_req.tool_name,
                    requested_operation=f"Instalação formal e auditada de {approved_req.tool_name}",
                    reason=f"Binário {approved_req.tool_name} ausente no sistema anfitrião. Instalação necessária.",
                    risk_level=approved_req.risk_level,
                    required_privileges=approved_req.required_privileges,
                    affected_resources=["system:binaries", approved_req.project_id or "system"],
                    project_id=approved_req.project_id,
                    mission_id=approved_req.mission_id,
                    execution_id=approved_req.execution_id,
                    tool_type="binary_installer",
                    installation_required=True,
                    installer_source=approved_req.installer_source or (
                        "https://nmap.org/dist/nmap-7.95-setup.exe"
                        if approved_req.tool_name.lower() == "nmap"
                        else "https://ffmpeg.org/download.html"
                    ),
                    installer_version=approved_req.installer_version or "official_stable",
                    alternative_available=approved_req.alternative_available,
                    fallback_description=approved_req.fallback_description,
                    dependency_id=approved_req.dependency_id,
                    classification=approved_req.classification,
                    approval_semantic=ApprovalSemantics.AUTHORIZE_INSTALLATION.value,
                )
                return {
                    "request_id": request_id,
                    "installation_request_id": install_req.request_id,
                    "status": "INSTALLATION_REQUIRED",
                    "capability": "INSTALLATION_REQUIRED",
                    "message": f"Ferramenta {approved_req.tool_name} aprovada, mas não instalada. Requer autorização de instalação.",
                }

            if cap_status == CapabilityStatus.ADMIN_PRIVILEGE_REQUIRED:
                approved_req.status = PermissionRequestStatus.ADMIN_PRIVILEGE_REQUIRED.value
                approved_req.capability_status = CapabilityStatus.ADMIN_PRIVILEGE_REQUIRED.value
                return {
                    "request_id": request_id,
                    "status": "ADMIN_PRIVILEGE_REQUIRED",
                    "capability": "ADMIN_PRIVILEGE_REQUIRED",
                    "message": "É necessária autorização administrativa do Windows para esta capacidade.",
                }

            return {
                "request_id": request_id,
                "status": approved_req.status,
                "capability": cap_status.value,
                "message": cap_details.get("message", ""),
            }

        # ----------------------------------------------------------------------
        # 2. Autorização de Instalação
        # ----------------------------------------------------------------------
        if action_norm in {"AUTHORIZE_INSTALLATION", "AUTORIZAR_INSTALACAO"}:
            approved_req = self.gateway.approve_request(request_id, decided_by=user_id)
            cap_status, cap_details = CapabilityChecker.check_capability(
                approved_req.tool_name,
                required_privileges=approved_req.required_privileges,
            )

            if cap_status == CapabilityStatus.ADMIN_PRIVILEGE_REQUIRED:
                approved_req.status = PermissionRequestStatus.ADMIN_PRIVILEGE_REQUIRED.value
                return {
                    "request_id": request_id,
                    "status": "ADMIN_PRIVILEGE_REQUIRED",
                    "message": "É necessária autorização administrativa do Windows. Não é possível elevar privilégios automaticamente.",
                }

            return {
                "request_id": request_id,
                "status": "INSTALLATION_AUTHORIZED",
                "message": f"Instalação de {approved_req.tool_name} autorizada pelo utilizador.",
            }

        # ----------------------------------------------------------------------
        # 3. Usar Alternativa Limitada
        # ----------------------------------------------------------------------
        if action_norm in {"USE_LIMITED_FALLBACK", "USAR_ALTERNATIVA_LIMITADA"}:
            if not req.fallback_satisfies_acceptance_criteria:
                # INVARIANTE: A alternativa NÃO cumpre todos os requisitos.
                # Não permitir contornar falsamente os critérios obrigatórios da missão.
                req.status = PermissionRequestStatus.BLOCKED_REQUIRED_CAPABILITY.value
                logger.warning(
                    f"Tentativa de usar fallback insuficiente para {req.tool_name}. "
                    f"Critérios: {req.acceptance_criteria}. Limitações: {req.fallback_limitations}"
                )
                return {
                    "request_id": request_id,
                    "status": "BLOCKED_REQUIRED_CAPABILITY",
                    "allowed": False,
                    "warning": "A alternativa não cumpre todos os requisitos.",
                    "message": (
                        f"A alternativa ({req.fallback_description}) não executa varredura ativa "
                        "nem satisfaz a totalidade dos critérios de aceitação. Missão permanece bloqueada."
                    ),
                }

            # Caso a alternativa cumpra os critérios:
            denied_req = self.gateway.deny_request(request_id, decided_by=user_id, reason="Utilizador optou por alternativa compatível")
            return {
                "request_id": request_id,
                "status": "FALLBACK_ACCEPTED",
                "allowed": True,
                "fallback": denied_req.fallback_description,
                "message": "Alternativa compatível aplicada com sucesso.",
            }

        # ----------------------------------------------------------------------
        # 4. Cancelar / Recusar
        # ----------------------------------------------------------------------
        if action_norm in {"CANCEL", "CANCELAR", "DENY", "RECUSAR"}:
            denied_req = self.gateway.deny_request(request_id, decided_by=user_id, reason="Operação cancelada pelo utilizador")
            return {
                "request_id": request_id,
                "status": "DENIED",
                "message": "Operação cancelada pelo utilizador.",
            }

        raise DependencyGovernanceError(f"Ação desconhecida: {action}")


_governor_instance: Optional[DependencyGovernanceService] = None


def get_dependency_governor() -> DependencyGovernanceService:
    global _governor_instance
    if _governor_instance is None:
        _governor_instance = DependencyGovernanceService()
    return _governor_instance


def reset_dependency_governor() -> None:
    global _governor_instance
    _governor_instance = None
