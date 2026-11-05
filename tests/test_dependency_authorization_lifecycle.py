"""
Phase 24: Comprehensive Regression Suite for Dependency Authorization Lifecycle
Validates:
1. Detection of missing dependencies.
2. Recognition of already installed dependencies.
3. Preparation of transparent authorization requests.
4. Backend boundary enforcement blocking execution on PENDING.
5. Backend boundary enforcement blocking execution on DENIED.
6. Scoped project-level execution upon approval.
7. Post-install verification and honest failure reporting.
8. Cross-project and cross-operation scope isolation (rejection of reused approvals).
9. Manifest synchronization (requirements.txt / package.json).
"""

import json
import os
import pytest
from unittest.mock import MagicMock

from security.permission_gateway.gateway import (
    CrossProjectApprovalError,
    PermissionBlockedByPolicyError,
    PermissionGatewayService,
    reset_permission_gateway_service,
)
from security.permission_gateway.models import PermissionRequestStatus
from security.permission_gateway.project_dependency_manager import (
    InstallationResult,
    ProjectDependencyManager,
    ProjectEnvironmentInfo,
)


@pytest.fixture
def clean_gateway():
    reset_permission_gateway_service()
    gw = PermissionGatewayService()
    yield gw
    reset_permission_gateway_service()


def test_missing_dependency_detection(tmp_path, clean_gateway):
    """1. Deve detetar que um pacote requerido está em falta no projeto."""
    proj = tmp_path / "proj_py"
    proj.mkdir()
    (proj / "app.py").write_text("import custom_uninstalled_pkg\n", encoding="utf-8")
    (proj / "requirements.txt").write_text("", encoding="utf-8")

    mgr = ProjectDependencyManager(gateway=clean_gateway)
    env = mgr.inspect_environment(str(proj), project_id="proj_py")

    assert env.language == "python"
    assert env.package_manager == "pip"
    assert env.manifest_file == "requirements.txt"
    assert mgr.is_package_installed(env, "custom_uninstalled_pkg") is False


def test_already_installed_dependency_recognized(tmp_path, clean_gateway):
    """2. Pacote já instalado no ambiente não deve ser marcado como ausente."""
    proj = tmp_path / "proj_py"
    proj.mkdir()
    mgr = ProjectDependencyManager(gateway=clean_gateway)
    env = mgr.inspect_environment(str(proj), project_id="proj_py")

    # 'json' e 'os' são built-in instalados
    assert mgr.is_package_installed(env, "json") is True
    assert mgr.is_package_installed(env, "os") is True


def test_prepare_authorization_request_transparency(tmp_path, clean_gateway):
    """3. Pedido de autorização deve conter explicações transparentes e escopo associado."""
    proj = tmp_path / "proj_node"
    proj.mkdir()
    (proj / "package.json").write_text('{"name": "proj_node"}', encoding="utf-8")

    mgr = ProjectDependencyManager(gateway=clean_gateway)
    req = mgr.prepare_authorization_request(
        project_root=str(proj),
        package_name="winston",
        reason="Necessário para logging estruturado em JSON",
        project_id="proj_node",
        mission_id="m_100",
    )

    assert req.tool_name == "winston"
    assert req.project_id == "proj_node"
    assert req.mission_id == "m_100"
    assert req.status == PermissionRequestStatus.WAITING_FOR_USER.value
    assert "winston" in req.reason
    assert "npm install winston" in req.decision_evidence["planned_command"]
    assert req.decision_evidence["manifest_target"] == "package.json"


def test_pending_approval_prevents_installation(tmp_path, clean_gateway):
    """4. Pedido com status WAITING_FOR_USER (pendente) deve ser bloqueado na fronteira de execução."""
    proj = tmp_path / "proj_py"
    proj.mkdir()
    (proj / "requirements.txt").write_text("", encoding="utf-8")

    mgr = ProjectDependencyManager(gateway=clean_gateway)
    req = mgr.prepare_authorization_request(
        project_root=str(proj),
        package_name="requests",
        reason="HTTP requests",
        project_id="proj_py",
    )

    # Tenta executar sem aprovação do utilizador
    res = mgr.execute_authorized_installation(
        request_id=req.request_id,
        project_root=str(proj),
        package_name="requests",
        project_id="proj_py",
    )

    assert res.success is False
    assert "bloqueada" in res.error.lower()
    assert res.verified_importable is False


def test_denied_approval_prevents_installation(tmp_path, clean_gateway):
    """5. Pedido explicitamente recusado deve impedir a instalação e registar a consequência."""
    proj = tmp_path / "proj_py"
    proj.mkdir()
    (proj / "requirements.txt").write_text("", encoding="utf-8")

    mgr = ProjectDependencyManager(gateway=clean_gateway)
    req = mgr.prepare_authorization_request(
        project_root=str(proj),
        package_name="requests",
        reason="HTTP requests",
        project_id="proj_py",
    )

    # Utilizador recusa
    deny_res = mgr.deny_authorization_request(
        request_id=req.request_id,
        user_id="user_admin",
        reason="Não pretendemos adicionar dependências externas nesta fase",
    )
    assert deny_res.success is False
    assert deny_res.denied is True

    # Tenta executar após recusa
    exec_res = mgr.execute_authorized_installation(
        request_id=req.request_id,
        project_root=str(proj),
        package_name="requests",
        project_id="proj_py",
    )
    assert exec_res.success is False
    assert "bloqueada" in exec_res.error.lower()


def test_approved_installation_executes_and_updates_manifest(tmp_path, clean_gateway):
    """6. Pedido aprovado executa no ambiente correto, atualiza manifest e valida importação."""
    proj = tmp_path / "proj_py"
    proj.mkdir()
    req_file = proj / "requirements.txt"
    req_file.write_text("pytest\n", encoding="utf-8")

    mgr = ProjectDependencyManager(gateway=clean_gateway)
    req = mgr.prepare_authorization_request(
        project_root=str(proj),
        package_name="colorama",
        reason="Suporte a cores no terminal",
        project_id="proj_py",
    )

    # Utilizador aprova
    clean_gateway.approve_request(req.request_id, decided_by="user_operator")

    def mock_install_cmd(cmd, env):
        # Simula execução bem-sucedida do comando de pacote
        return (0, "Successfully installed colorama-0.4.6", "")

    res = mgr.execute_authorized_installation(
        request_id=req.request_id,
        project_root=str(proj),
        package_name="colorama",
        project_id="proj_py",
        mock_run_cmd=mock_install_cmd,
    )

    assert res.success is True
    assert res.exit_code == 0
    assert res.manifest_updated is True
    assert "colorama" in req_file.read_text(encoding="utf-8")

    # Verifica status da requisição
    updated_req = clean_gateway.get_request(req.request_id)
    assert updated_req.status == PermissionRequestStatus.EXECUTED.value


def test_installation_failure_reported_honestly(tmp_path, clean_gateway):
    """7. Falha de instalação deve ser reportada fielmente sem fingir sucesso."""
    proj = tmp_path / "proj_py"
    proj.mkdir()

    mgr = ProjectDependencyManager(gateway=clean_gateway)
    req = mgr.prepare_authorization_request(
        project_root=str(proj),
        package_name="incompatible_pkg",
        reason="Teste de falha",
        project_id="proj_py",
    )
    clean_gateway.approve_request(req.request_id, decided_by="user_operator")

    def mock_failing_cmd(cmd, env):
        return (1, "", "ERROR: No matching distribution found for incompatible_pkg")

    res = mgr.execute_authorized_installation(
        request_id=req.request_id,
        project_root=str(proj),
        package_name="incompatible_pkg",
        project_id="proj_py",
        mock_run_cmd=mock_failing_cmd,
    )

    assert res.success is False
    assert res.exit_code == 1
    assert "Falha na instalação" in res.error
    assert "No matching distribution" in res.stderr

    updated_req = clean_gateway.get_request(req.request_id)
    assert updated_req.status == PermissionRequestStatus.FAILED.value


def test_scope_isolation_cross_project_and_operation(tmp_path, clean_gateway):
    """8. Aprovação concedida a um projeto ou operação NÃO pode ser reutilizada noutro projeto ou comando."""
    proj_a = tmp_path / "proj_a"
    proj_b = tmp_path / "proj_b"
    proj_a.mkdir()
    proj_b.mkdir()

    mgr = ProjectDependencyManager(gateway=clean_gateway)

    # Cria pedido para o projeto A
    req = mgr.prepare_authorization_request(
        project_root=str(proj_a),
        package_name="requests",
        reason="HTTP requests no projeto A",
        project_id="proj_a",
    )
    clean_gateway.approve_request(req.request_id, decided_by="user_operator")

    # 1. Tentativa de reutilizar a aprovação no Projeto B -> DEVE FALHAR
    with pytest.raises(CrossProjectApprovalError) as exc_proj:
        mgr.enforce_backend_authorization(
            request_id=req.request_id,
            project_id="proj_b",  # Projeto diferente!
            operation="install_package:requests",
        )
    assert "violação de escopo" in str(exc_proj.value).lower()

    # 2. Tentativa de reutilizar a aprovação para outra operação no Projeto A -> DEVE FALHAR
    with pytest.raises(PermissionBlockedByPolicyError) as exc_op:
        mgr.enforce_backend_authorization(
            request_id=req.request_id,
            project_id="proj_a",
            operation="install_package:malicious_tool",  # Operação diferente!
        )
    assert "violação de operação" in str(exc_op.value).lower()
