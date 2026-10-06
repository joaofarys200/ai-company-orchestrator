"""
Suíte Abrangente de Testes de Governança de Dependências Externas (>= 25 Testes)
Garante:
1. NUNCA fazer downgrade silencioso de ferramentas externas necessárias.
2. Não declarar falso sucesso se o fallback falhar os critérios de aceitação.
3. Rastreabilidade estrita de dependências (REQUIRED, OPTIONAL, ALTERNATIVE).
4. Separação de AUTHORIZE_USE vs AUTHORIZE_INSTALLATION vs UAC Admin.
5. Integração com Planner, CodingSession, ProjectBuilder e PermissionGateway.
"""

import sys
import time
from unittest.mock import MagicMock, patch

for mod in [
    "jsonschema",
    "jsonschema.validators",
    "httpx",
    "psutil",
    "dotenv",
    "tree_sitter",
    "tree_sitter_javascript",
    "yaml",
    "aiohttp",
    "websockets",
    "cryptography",
    "PIL",
    "PIL.ImageGrab",
    "PIL.Image",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from security.permission_gateway.models import (
    PermissionRiskLevel,
    PermissionRequestStatus,
    CapabilityStatus,
    DependencyClassification,
    ApprovalSemantics,
    DependencyRequirement,
    DependencyResolutionReport,
    PermissionRequest,
)
from security.permission_gateway.gateway import (
    PermissionGatewayService,
    get_permission_gateway_service,
    reset_permission_gateway_service,
    PermissionNotFoundError,
    PermissionExpiredError,
)
from security.permission_gateway.capability_checker import CapabilityChecker
from security.permission_gateway.dependency_governance import (
    DependencyGovernanceService,
    get_dependency_governor,
    reset_dependency_governor,
    SilentDowngradePreventedError,
    FallbackCriteriaViolationError,
)
from intelligence.coding_session import detect_dependency_requirements
from agents.orchestrator.project_builder import build_project


@pytest.fixture(autouse=True)
def clean_gateway_and_governor():
    """Reinicia o gateway e o governador para cada teste."""
    reset_permission_gateway_service()
    reset_dependency_governor()
    yield
    reset_permission_gateway_service()
    reset_dependency_governor()


# ==============================================================================
# 1. REQUIRED DEPENDENCY
# ==============================================================================
def test_01_required_dependency():
    governor = get_dependency_governor()
    dep = governor.classify_dependency(
        tool_name="nmap",
        required_for="active network discovery",
        acceptance_criteria=["discover active hosts", "discover open ports"],
    )
    assert dep.classification == DependencyClassification.REQUIRED.value
    assert dep.tool_name.lower() == "nmap"
    assert "open ports" in " ".join(dep.acceptance_criteria)
    assert dep.fallback_satisfies_acceptance_criteria is False
    assert "arp -a" in dep.fallback
    assert "ativa" in dep.fallback_limitations.lower() or "não executa" in dep.fallback_limitations.lower()


# ==============================================================================
# 2. OPTIONAL DEPENDENCY
# ==============================================================================
def test_02_optional_dependency():
    governor = get_dependency_governor()
    dep = governor.classify_dependency(
        tool_name="cowsay",
        required_for="banner decorativo no terminal",
        acceptance_criteria=["mostrar mensagem"],
    )
    assert dep.classification == DependencyClassification.OPTIONAL.value
    assert dep.fallback_satisfies_acceptance_criteria is True


# ==============================================================================
# 3. TRUE ALTERNATIVE
# ==============================================================================
def test_03_true_alternative():
    governor = get_dependency_governor()
    dep = governor.classify_dependency(
        tool_name="wget",
        required_for="download de ficheiro",
        acceptance_criteria=["download file over http"],
        fallback="curl",
        fallback_capability="download file over http",
    )
    assert dep.classification == DependencyClassification.ALTERNATIVE.value
    assert dep.fallback_satisfies_acceptance_criteria is True
    assert "curl" in dep.fallback.lower()


# ==============================================================================
# 4. UNAVAILABLE REQUIRED
# ==============================================================================
def test_04_unavailable_required():
    governor = get_dependency_governor()
    with patch("shutil.which", return_value=None):
        report = governor.analyze_dependencies(
            objective="Analisa a rede local e descobre portas abertas",
            proposed_tools=["Nmap"],
            criteria=["discover open ports"],
        )
    assert report.can_execute_immediately is False
    assert report.status == PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value
    assert len(report.unavailable_required) == 1
    assert report.unavailable_required[0].tool_name.lower() == "nmap"
    assert len(report.approval_requests) == 1


# ==============================================================================
# 5. UNAVAILABLE OPTIONAL
# ==============================================================================
def test_05_unavailable_optional():
    governor = get_dependency_governor()
    with patch("shutil.which", return_value=None):
        report = governor.analyze_dependencies(
            objective="Formatar texto decorativo",
            proposed_tools=["cowsay"],
            criteria=["mostrar mensagem"],
        )
    # Dependência opcional indisponível NÃO bloqueia a execução
    assert report.can_execute_immediately is True
    assert len(report.approval_requests) == 0


# ==============================================================================
# 6. FALLBACK SATISFIES CRITERIA
# ==============================================================================
def test_06_fallback_satisfies_criteria():
    governor = get_dependency_governor()
    criteria = ["download payload from remote server"]
    fallback_cap = "HTTP GET request client using curl or invoke-webrequest"
    satisfies = governor.evaluate_fallback_satisfaction(criteria, fallback_cap)
    assert satisfies is True


# ==============================================================================
# 7. FALLBACK FAILS CRITERIA
# ==============================================================================
def test_07_fallback_fails_criteria():
    governor = get_dependency_governor()
    criteria = ["discover active hosts", "discover open ports"]
    fallback_cap = "passive ARP cache inspection only"
    satisfies = governor.evaluate_fallback_satisfaction(criteria, fallback_cap)
    assert satisfies is False


# ==============================================================================
# 8. PERMISSION REQUEST
# ==============================================================================
def test_08_permission_request():
    gateway = get_permission_gateway_service()
    req = gateway.create_request(
        tool_name="Nmap",
        requested_operation="active network discovery",
        reason="Necessário varredura ativa de hosts e portas",
        risk_level=PermissionRiskLevel.HIGH_RISK_MUTATION,
        required_privileges="Administrador / Npcap",
        affected_resources=["network:interface", "host:arp"],
        dependency_id="dep-nmap-01",
        acceptance_criteria=["discover active hosts", "discover open ports"],
        fallback_description="arp -a",
        fallback_capability="passive ARP cache inspection",
        fallback_limitations="Não faz varredura ativa de portas",
        fallback_satisfies_acceptance_criteria=False,
        classification=DependencyClassification.REQUIRED.value,
        approval_semantic=ApprovalSemantics.AUTHORIZE_USE.value,
    )
    assert req.request_id.startswith("perm-")
    assert req.status in {
        PermissionRequestStatus.WAITING_FOR_USER.value,
        PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value,
    }
    assert req.dependency_id == "dep-nmap-01"
    assert req.fallback_satisfies_acceptance_criteria is False
    assert req.tool_name == "Nmap"


# ==============================================================================
# 9. USE APPROVAL (WITH BINARY PRESENT)
# ==============================================================================
def test_09_use_approval():
    gateway = get_permission_gateway_service()
    governor = get_dependency_governor()

    req = gateway.create_request(
        tool_name="Nmap",
        requested_operation="scan",
        reason="Scan de rede",
        risk_level=PermissionRiskLevel.HIGH_RISK_MUTATION,
        required_privileges="Normal",
        affected_resources=["net"],
    )

    with patch("shutil.which", return_value="C:\\Program Files\\Nmap\\nmap.exe"), \
         patch.object(CapabilityChecker, "is_windows_admin", return_value=True):
        res = governor.resolve_user_decision(req.request_id, "AUTHORIZE_USE", user_id="admin_user")

    assert res["status"] == "EXECUTION_READY"
    assert res["capability"] == "AVAILABLE"


# ==============================================================================
# 10. INSTALLATION APPROVAL (WHEN BINARY ABSENT)
# ==============================================================================
def test_10_installation_approval():
    gateway = get_permission_gateway_service()
    governor = get_dependency_governor()

    req = gateway.create_request(
        tool_name="Nmap",
        requested_operation="scan",
        reason="Scan de rede",
        risk_level=PermissionRiskLevel.HIGH_RISK_MUTATION,
        required_privileges="Administrador / Npcap",
        affected_resources=["net"],
    )

    with patch("shutil.which", return_value=None):
        # Quando o utilizador autoriza o USO mas o binário não está instalado
        res = governor.resolve_user_decision(req.request_id, "AUTHORIZE_USE", user_id="operator")

    assert res["status"] == "INSTALLATION_REQUIRED"
    assert "installation_request_id" in res
    inst_req_id = res["installation_request_id"]

    # Agora o utilizador autoriza a INSTALAÇÃO formal
    with patch("shutil.which", return_value=None):
        inst_res = governor.resolve_user_decision(inst_req_id, "AUTHORIZE_INSTALLATION", user_id="operator")

    assert inst_res["status"] == "INSTALLATION_AUTHORIZED"


# ==============================================================================
# 11. CAPABILITY CHECK
# ==============================================================================
def test_11_capability_check():
    status, details = CapabilityChecker.check_capability(
        "nmap",
        mock_installed_tools={"nmap": "C:\\Tools\\nmap.exe"},
        mock_is_admin=True,
    )
    assert status == CapabilityStatus.AVAILABLE
    assert details["executable_path"] == "C:\\Tools\\nmap.exe"


# ==============================================================================
# 12. ADMIN REQUIRED DISTINGUISHES UAC
# ==============================================================================
def test_12_admin_required_distinguishes_uac():
    status, details = CapabilityChecker.check_capability(
        "nmap",
        mock_installed_tools={"nmap": "C:\\Tools\\nmap.exe"},
        mock_is_admin=False, # Não possui UAC elevado
        required_privileges="Administrador / Npcap",
    )
    assert status == CapabilityStatus.ADMIN_PRIVILEGE_REQUIRED
    assert details["admin_granted"] is False
    assert "administrativa" in details["message"].lower()


# ==============================================================================
# 13. POLICY BLOCKED
# ==============================================================================
def test_13_policy_blocked():
    gateway = get_permission_gateway_service()
    req = gateway.create_request(
        tool_name="format",
        requested_operation="disk format",
        reason="Formatar disco",
        risk_level=PermissionRiskLevel.CRITICAL_MUTATION,
        required_privileges="SYSTEM",
        affected_resources=["C:\\"],
    )
    assert req.risk_level == PermissionRiskLevel.CRITICAL_MUTATION.value


# ==============================================================================
# 14. USER DENIAL
# ==============================================================================
def test_14_user_denial():
    gateway = get_permission_gateway_service()
    governor = get_dependency_governor()

    req = gateway.create_request(
        tool_name="Nmap",
        requested_operation="scan",
        reason="Scan de portas",
        risk_level=PermissionRiskLevel.HIGH_RISK_MUTATION,
        required_privileges="Administrador",
        affected_resources=["network"],
    )

    res = governor.resolve_user_decision(req.request_id, "CANCEL", user_id="operator")
    assert res["status"] == "DENIED"

    refreshed = gateway.get_request(req.request_id)
    assert refreshed.status == PermissionRequestStatus.DENIED.value


# ==============================================================================
# 15. FALLBACK REJECTION WHEN CRITERIA FAIL
# ==============================================================================
def test_15_fallback_rejection_when_criteria_fail():
    gateway = get_permission_gateway_service()
    governor = get_dependency_governor()

    req = gateway.create_request(
        tool_name="Nmap",
        requested_operation="active network discovery",
        reason="Descoberta de portas",
        risk_level=PermissionRiskLevel.HIGH_RISK_MUTATION,
        required_privileges="Administrador",
        affected_resources=["network"],
        acceptance_criteria=["discover active hosts", "discover open ports"],
        fallback_description="arp -a",
        fallback_satisfies_acceptance_criteria=False, # Não satisfaz!
    )

    res = governor.resolve_user_decision(req.request_id, "USE_LIMITED_FALLBACK", user_id="operator")
    assert res["status"] == "BLOCKED_REQUIRED_CAPABILITY"
    assert res["allowed"] is False
    assert "A alternativa não cumpre todos os requisitos." in res["warning"]

    refreshed = gateway.get_request(req.request_id)
    assert refreshed.status == PermissionRequestStatus.BLOCKED_REQUIRED_CAPABILITY.value


# ==============================================================================
# 16. NO SILENT DOWNGRADE
# ==============================================================================
def test_16_no_silent_downgrade():
    governor = get_dependency_governor()
    with patch("shutil.which", return_value=None):
        report = governor.analyze_dependencies(
            objective="Varredura de portas abertas na rede local",
            proposed_tools=["Nmap"],
            criteria=["discover open ports"],
        )
    # Não pode trocar silenciosamente para arp -a
    assert report.can_execute_immediately is False
    assert any(d.tool_name.lower() == "nmap" for d in report.unavailable_required)
    assert report.status == PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value


# ==============================================================================
# 17. FALSE COMPLETION PREVENTION
# ==============================================================================
def test_17_false_completion_prevention():
    governor = get_dependency_governor()
    criteria = ["discover active hosts", "discover open ports"]
    with patch("shutil.which", return_value=None):
        report = governor.analyze_dependencies(
            objective="Descobrir hosts e portas abertas",
            proposed_tools=["Nmap"],
            criteria=criteria,
        )

    # Se a dependência obrigatória não foi resolvida, a conclusão da missão é bloqueada
    assert report.can_execute_immediately is False
    assert report.status != "COMPLETED"
    assert report.status == PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value


# ==============================================================================
# 18. MISSION WAITING STATE
# ==============================================================================
def test_18_mission_waiting_state():
    governor = get_dependency_governor()
    with patch("shutil.which", return_value=None):
        report = governor.analyze_dependencies(
            objective="Scan com Nmap",
            proposed_tools=["Nmap"],
            criteria=["discover open ports"],
        )
    # A missão deve transitar para AWAITING_HUMAN_APPROVAL e NÃO FAILED
    assert report.status == PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value
    assert report.status != "FAILED"


# ==============================================================================
# 19. IDEMPOTENT APPROVAL
# ==============================================================================
def test_19_idempotent_approval():
    gateway = get_permission_gateway_service()
    req = gateway.create_request(
        tool_name="git",
        requested_operation="commit",
        reason="Versionar",
        risk_level=PermissionRiskLevel.LOW_RISK_MUTATION,
        required_privileges="Normal",
        affected_resources=["workspace"],
    )
    first = gateway.approve_request(req.request_id, user="dev")
    second = gateway.approve_request(req.request_id, user="dev")
    assert first.status in {PermissionRequestStatus.APPROVED.value, PermissionRequestStatus.EXECUTION_READY.value}
    assert second.status in {PermissionRequestStatus.APPROVED.value, PermissionRequestStatus.EXECUTION_READY.value}


# ==============================================================================
# 20. EXPIRY
# ==============================================================================
def test_20_expiry():
    gateway = get_permission_gateway_service()
    req = gateway.create_request(
        tool_name="Nmap",
        requested_operation="scan",
        reason="Scan",
        risk_level=PermissionRiskLevel.HIGH_RISK_MUTATION,
        required_privileges="Admin",
        affected_resources=["net"],
        ttl_seconds=1,
    )
    time.sleep(1.1)
    with pytest.raises(PermissionExpiredError):
        gateway.approve_request(req.request_id, user="dev")


# ==============================================================================
# 21. AUDIT TRAIL
# ==============================================================================
def test_21_audit_trail():
    gateway = get_permission_gateway_service()
    req = gateway.create_request(
        tool_name="Nmap",
        requested_operation="audit_scan",
        reason="Auditoria",
        risk_level=PermissionRiskLevel.HIGH_RISK_MUTATION,
        required_privileges="Admin",
        affected_resources=["net"],
    )
    events = gateway.get_audit_events(req.request_id)
    assert len(events) >= 1
    action_types = [e.action for e in events]
    assert "request_created" in action_types or "shown_to_user" in action_types


# ==============================================================================
# 22. PLANNER INTEGRATION
# ==============================================================================
def test_22_planner_integration():
    governor = get_dependency_governor()
    # Simula chamada do Planner antes da execução
    plan_text = "Fazer varredura com nmap na subnet 192.168.1.0/24"
    with patch("shutil.which", return_value=None):
        report = governor.analyze_dependencies(
            objective=plan_text,
            criteria=["discover open ports"],
        )
    assert report.can_execute_immediately is False
    assert len(report.unavailable_required) == 1
    assert report.unavailable_required[0].tool_name.lower() == "nmap"


# ==============================================================================
# 23. CODING SESSION INTEGRATION
# ==============================================================================
def test_23_coding_session_integration():
    reqs = detect_dependency_requirements("Analisa a rede local e descobre portas abertas com nmap")
    assert len(reqs) > 0
    assert reqs[0].tool_name.lower() == "nmap"
    assert reqs[0].classification == DependencyClassification.REQUIRED.value
    assert reqs[0].fallback_satisfies_acceptance_criteria is False
    assert "arp -a" in reqs[0].fallback_description
    assert "portas" in reqs[0].fallback_limitations.lower() or "passiva" in reqs[0].fallback_limitations.lower()


# ==============================================================================
# 24. PROJECT BUILDER INTEGRATION
# ==============================================================================
def test_24_project_builder_integration():
    import asyncio
    mock_plan = MagicMock()
    mock_plan.project_name = "network_monitor"
    mock_plan.files = []
    mock_plan.components = []
    mock_plan.entrypoints = []
    mock_plan.dependencies = ["nmap"]

    with patch("agents.orchestrator.project_builder.get_valid_project_plan", return_value=mock_plan), \
         patch("shutil.which", return_value=None):
        result = asyncio.run(build_project(
            "Cria um app com scanner nmap para a rede",
            plan_requester=MagicMock(),
            project_id="proj_net",
            mission_id="m_net",
        ))

    assert result.technical_success is False
    assert result.status == "AWAITING_HUMAN_APPROVAL"
    assert result.permission_request_id is not None
    assert "nmap" in result.suggested_fix.lower()


# ==============================================================================
# 25. NMAP SCENARIO FULL LIFECYCLE
# ==============================================================================
def test_25_nmap_scenario_full_lifecycle():
    governor = get_dependency_governor()
    gateway = get_permission_gateway_service()

    # Pedido: "Analisa a rede local e identifica hosts e portas abertas"
    objective = "Analisa a rede local e identifica hosts e portas abertas"

    with patch("shutil.which", return_value=None):
        report = governor.analyze_dependencies(
            objective=objective,
            criteria=["discover active hosts", "discover open ports"],
        )

    # 1. Nmap detectado como REQUIRED
    assert len(report.required_dependencies) == 1
    dep = report.required_dependencies[0]
    assert dep.tool_name.lower() == "nmap"
    assert dep.classification == DependencyClassification.REQUIRED.value

    # 2. Ausente no SO -> AWAITING_HUMAN_APPROVAL (Não executa arp -a silenciosamente)
    assert report.can_execute_immediately is False
    assert report.status == PermissionRequestStatus.AWAITING_HUMAN_APPROVAL.value
    assert len(report.approval_requests) == 1

    req_id = report.approval_requests[0]

    # 3. Utilizador tenta "Usar alternativa limitada"
    # Como não satisfaz os critérios, deve ser estritamente bloqueado!
    fallback_res = governor.resolve_user_decision(req_id, "USE_LIMITED_FALLBACK", user_id="operator")
    assert fallback_res["allowed"] is False
    assert "A alternativa não cumpre todos os requisitos." in fallback_res["warning"]

    # 4. Utilizador seleciona "Autorizar Nmap"
    with patch("shutil.which", return_value=None):
        auth_res = governor.resolve_user_decision(req_id, "AUTHORIZE_USE", user_id="operator")

    # 5. Como o Nmap não está instalado, não declara execução; exige autorização de instalação!
    assert auth_res["status"] == "INSTALLATION_REQUIRED"
    assert "installation_request_id" in auth_res
    inst_req_id = auth_res["installation_request_id"]
    inst_req = gateway.get_request(inst_req_id)
    assert inst_req.installation_required is True
    assert "nmap" in inst_req.tool_name.lower()
