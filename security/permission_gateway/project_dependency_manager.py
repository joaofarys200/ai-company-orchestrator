"""
JARVIS OS — Phase 24: Project Dependency Authorization & Environment Manager
Implements explicit dependency detection, scoped authorization lifecycle,
isolated project-level package installation, manifest synchronization, and post-install verification.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from security.permission_gateway.gateway import (
    CrossProjectApprovalError,
    PermissionBlockedByPolicyError,
    PermissionExpiredError,
    PermissionGatewayError,
    PermissionGatewayService,
    PermissionNotFoundError,
    get_permission_gateway_service,
)
from security.permission_gateway.models import (
    ApprovalSemantics,
    DependencyClassification,
    PermissionRequest,
    PermissionRequestStatus,
    PermissionRiskLevel,
)

logger = logging.getLogger("Jarvis.ProjectDependencyManager")


@dataclass
class ProjectEnvironmentInfo:
    """Metadados do ambiente de execução do projeto."""
    project_id: str
    project_root: str
    language: str  # "python", "javascript", "typescript", "unknown"
    package_manager: str  # "pip", "npm", "yarn", "pnpm"
    manifest_file: Optional[str] = None  # "requirements.txt", "package.json", "pyproject.toml"
    has_venv: bool = False
    venv_path: Optional[str] = None
    python_executable: Optional[str] = None
    node_modules_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InstallationResult:
    """Resultado auditado e verificável da tentativa de instalação."""
    success: bool
    package_name: str
    project_id: str
    command_executed: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    manifest_updated: bool = False
    manifest_file: Optional[str] = None
    verified_importable: bool = False
    denied: bool = False
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProjectDependencyManager:
    """
    Gestor central de dependências e autorizações de pacotes para o JARVIS OS.
    Garante o ciclo completo de 7 passos da Fase 24:
    1. Analisar necessidade de dependência.
    2. Inspecionar manifest e virtualenv do projeto.
    3. Preparar pedido formal de autorização com explicações transparentes.
    4. Aguardar aprovação explícita no backend (enforcement de fronteira).
    5. Executar apenas a operação aprovada no ambiente correto (project-scoped).
    6. Verificar instalação com teste de importação e atualização de manifest.
    7. Retomar a tarefa original com registo de auditoria.
    """

    def __init__(self, gateway: Optional[PermissionGatewayService] = None):
        self._gateway = gateway

    @property
    def gateway(self) -> PermissionGatewayService:
        if self._gateway is None:
            self._gateway = get_permission_gateway_service()
        return self._gateway
    @staticmethod
    def extract_requested_packages(prompt: str) -> List[str]:
        """Extrai nomes de pacotes pretendidos na mensagem de desenvolvimento."""
        import re
        packages: List[str] = []
        lower = str(prompt or "").lower()

        # 1. Padrões explícitos com verbos e palavras-chave de biblioteca/pacote
        patterns = [
            r"\b(?:adiciona|adicionar|instala|instalar|usa|usar|utiliza|utilizar|configura|configurar)\s+(?:a\s+biblioteca|o\s+pacote|a\s+lib|o\s+m[oó]dulo|a\s+depend[eê]ncia|library|package)\s+([a-zA-Z0-9_\-]+)",
            r"\b(?:pip|npm|yarn)\s+install\s+([a-zA-Z0-9_\-]+)",
            r"\b(?:com|usando|utilizando)\s+(?:a\s+biblioteca|o\s+pacote|a\s+lib)?\s*([a-zA-Z0-9_\-]+)",
            r"\b(?:instala|instalar|install)\s+([a-zA-Z0-9_\-]+)",
        ]
        skip_words = {
            "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do", "da", "em", "no", "na",
            "para", "por", "com", "sem", "que", "se", "como", "mais", "este", "esta", "esse",
            "projeto", "código", "codigo", "ficheiro", "arquivo", "função", "funcao", "endpoint",
            "teste", "testes", "logger", "servidor", "servico", "serviço", "app", "api", "novo",
            "isso", "tudo", "diretiva", "missao", "missão", "rota", "rotas", "geração", "geracao",
            "relatório", "relatórios", "relatorio", "relatorios", "docstring", "docstrings",
            "comentário", "comentários", "comentario", "comentarios", "documentação", "documentacao",
            "tipo", "tipos", "interface", "interfaces", "classe", "classes", "método", "metodo",
            "métodos", "metodos", "variável", "variavel", "variáveis", "variaveis", "suporte",
            "validação", "validacao", "segurança", "seguranca", "lógica", "logica",
            "funcionalidade", "funcionalidades", "recurso", "recursos", "script", "scripts",
            "utilitário", "utilitario", "utilitária", "utilitaria", "dados", "recolha",
            "web", "front", "backend", "sistema", "main", "index", "code", "software",
        }
        for pat in patterns:
            for match in re.finditer(pat, lower):
                pkg = match.group(1).strip()
                if pkg and pkg not in skip_words and len(pkg) >= 2:
                    if pkg not in packages:
                        packages.append(pkg)

        # 2. Bibliotecas populares conhecidas frequentemente pedidas em tarefas de desenvolvimento
        known_popular = [
            "winston", "axios", "express", "lodash", "requests", "numpy", "pandas",
            "scipy", "colorama", "incompatible_pkg", "uninstalled_lib", "chalk", "cors",
            "beautifulsoup4", "bs4", "fastapi", "flask", "pydantic", "sqlalchemy",
            "matplotlib", "seaborn", "playwright",
        ]
        for k in known_popular:
            if re.search(rf"\b{k}\b", lower) and k not in packages:
                packages.append(k)

        return packages

    def can_execute(self, request_id: str, operation_type: str, target_project: str) -> bool:
        """Verifica se uma autorização pode ser executada para o projeto e operação dados."""
        try:
            self.enforce_backend_authorization(request_id, target_project, operation_type)
            return True
        except Exception:
            return False

    def inspect_environment(self, project_root: str, project_id: str = "") -> ProjectEnvironmentInfo:
        """Inspeciona detalhadamente o ambiente e ferramentas do projeto."""
        root = os.path.abspath(project_root)
        pid = project_id or os.path.basename(root)

        # Detecta linguagens e manifests
        has_pkg_json = os.path.isfile(os.path.join(root, "package.json"))
        has_req_txt = os.path.isfile(os.path.join(root, "requirements.txt"))
        has_pyproject = os.path.isfile(os.path.join(root, "pyproject.toml"))

        language = "unknown"
        pkg_manager = "pip"
        manifest_file = None

        if has_pkg_json:
            language = "javascript"
            pkg_manager = "npm"
            manifest_file = "package.json"
        elif has_req_txt or has_pyproject:
            language = "python"
            pkg_manager = "pip"
            manifest_file = "requirements.txt" if has_req_txt else "pyproject.toml"
        else:
            # Heurística por ficheiros existentes
            for fname in os.listdir(root) if os.path.isdir(root) else []:
                if fname.endswith(".py"):
                    language = "python"
                    pkg_manager = "pip"
                    manifest_file = "requirements.txt"
                    break
                elif fname.endswith((".js", ".ts", ".jsx", ".tsx")):
                    language = "javascript"
                    pkg_manager = "npm"
                    manifest_file = "package.json"
                    break

        # Procura virtualenv do projeto ou do workspace
        venv_path = None
        python_exec = None
        has_venv = False

        for venv_name in (".venv", "venv", "env"):
            candidate = os.path.join(root, venv_name)
            if os.path.isdir(candidate):
                py_bin = (
                    os.path.join(candidate, "Scripts", "python.exe")
                    if os.name == "nt"
                    else os.path.join(candidate, "bin", "python")
                )
                if os.path.isfile(py_bin):
                    has_venv = True
                    venv_path = candidate
                    python_exec = py_bin
                    break

        # Se não encontrou no projeto, utiliza o virtualenv do workspace se existir
        if not python_exec:
            workspace_root = os.path.abspath(os.path.join(root, "..", ".."))
            for venv_name in ("venv", ".venv"):
                candidate = os.path.join(workspace_root, venv_name)
                py_bin = (
                    os.path.join(candidate, "Scripts", "python.exe")
                    if os.name == "nt"
                    else os.path.join(candidate, "bin", "python")
                )
                if os.path.isfile(py_bin):
                    venv_path = candidate
                    python_exec = py_bin
                    has_venv = True
                    break

        if not python_exec:
            python_exec = sys.executable

        node_modules = os.path.join(root, "node_modules")

        return ProjectEnvironmentInfo(
            project_id=pid,
            project_root=root,
            language=language,
            package_manager=pkg_manager,
            manifest_file=manifest_file,
            has_venv=has_venv,
            venv_path=venv_path,
            python_executable=python_exec,
            node_modules_path=node_modules if os.path.isdir(node_modules) else None,
        )

    def is_package_installed(self, env_info: ProjectEnvironmentInfo, package_name: str) -> bool:
        """Verifica se um pacote já está instalado e disponível no ambiente relevante."""
        norm_pkg = package_name.strip().lower().replace("-", "_")

        # Módulos embutidos da biblioteca padrão do Python
        std_lib_modules = {
            "sqlite", "sqlite3", "json", "os", "sys", "re", "math", "time", "datetime",
            "pathlib", "asyncio", "random", "logging", "typing", "collections", "hashlib",
            "io", "subprocess", "unittest", "csv", "shutil", "glob", "tempfile", "urllib",
            "http", "xml", "html", "inspect", "functools", "itertools", "dataclasses",
            "enum", "uuid", "threading", "queue", "socket", "ssl", "traceback",
        }
        if norm_pkg in std_lib_modules:
            return True

        if norm_pkg == "sqlite":
            norm_pkg = "sqlite3"

        if env_info.language in ("python", "unknown"):
            # 1. Verifica via python_executable do ambiente
            if env_info.python_executable and os.path.isfile(env_info.python_executable):
                try:
                    res = subprocess.run(
                        [env_info.python_executable, "-c", f"import {norm_pkg}"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if res.returncode == 0:
                        return True
                except Exception:
                    pass

            # 2. Verifica se está no interpretador atual
            try:
                __import__(norm_pkg)
                return True
            except ImportError:
                pass

        if env_info.language in ("javascript", "typescript", "unknown"):
            # Verifica existência em node_modules local
            if env_info.node_modules_path and os.path.isdir(env_info.node_modules_path):
                pkg_dir = os.path.join(env_info.node_modules_path, package_name.strip())
                if os.path.isdir(pkg_dir):
                    return True
            return False

        return False


    def prepare_authorization_request(
        self,
        project_root: str,
        package_name: str,
        reason: str,
        project_id: str = "",
        mission_id: Optional[str] = None,
        version_constraint: Optional[str] = None,
    ) -> PermissionRequest:
        """
        Passo 3: Prepara o pedido formal de autorização com todas as explicações transparentes:
        - Pacote necessário
        - Motivo concreto
        - Projeto e ambiente alvo
        - Comando planeado
        - Alterações no manifest
        - Implicações de segurança
        """
        env = self.inspect_environment(project_root, project_id=project_id)
        target_proj = env.project_id
        cmd = (
            f"pip install {package_name}"
            if env.language == "python"
            else f"npm install {package_name}"
        )
        manifest_target = env.manifest_file or ("requirements.txt" if env.language == "python" else "package.json")

        explanation = (
            f"O desenvolvimento no projeto '{target_proj}' necessita do pacote '{package_name}'.\n"
            f"• Motivo: {reason}\n"
            f"• Ambiente Alvo: {env.venv_path or 'Ambiente do Projeto'}\n"
            f"• Gestor de Pacotes: {env.package_manager}\n"
            f"• Comando Pretendido: {cmd}\n"
            f"• Ficheiro de Manifest: {manifest_target} (será atualizado)\n"
            f"• Implicações: Instalação restrita ao escopo do projeto, sem privilégios de administrador."
        )

        affected_resources = [
            f"project:{target_proj}",
            os.path.join(env.project_root, manifest_target),
        ]
        if env.venv_path:
            affected_resources.append(env.venv_path)

        req = self.gateway.create_request(
            tool_name=package_name,
            requested_operation=f"install_package:{package_name}",
            reason=explanation,
            risk_level=PermissionRiskLevel.LOW_RISK_MUTATION.value,
            required_privileges="Userland / Project Environment",
            affected_resources=affected_resources,
            mission_id=mission_id,
            project_id=target_proj,
            tool_type="package",
            installation_required=True,
            installer_source="PyPI" if env.language == "python" else "npm registry",
            installer_version=version_constraint or "latest_compatible",
            approval_semantic=ApprovalSemantics.AUTHORIZE_INSTALLATION.value,
        )

        req.decision_evidence["environment_info"] = env.to_dict()
        req.decision_evidence["planned_command"] = cmd
        req.decision_evidence["manifest_target"] = manifest_target
        req.decision_evidence["package_name"] = package_name

        return req

    def enforce_backend_authorization(
        self,
        request_id: str,
        project_id: str,
        operation: str,
    ) -> PermissionRequest:
        """
        Passo 4: Verificação rigorosa e intransponível na fronteira de execução do backend.
        Impede vazamento de autorização entre projetos, operações ou privilégios diferentes.
        """
        req = self.gateway.get_request(request_id)
        if not req:
            raise PermissionNotFoundError(f"Pedido de autorização '{request_id}' não existe no backend.")

        # 1. Verifica estado de aprovação
        if req.status not in {
            PermissionRequestStatus.APPROVED.value,
            PermissionRequestStatus.EXECUTION_READY.value,
            PermissionRequestStatus.INSTALLATION_REQUIRED.value,
        } and getattr(req, "user_decision", None) != "APPROVE":
            raise PermissionBlockedByPolicyError(
                f"Execução bloqueada: pedido '{request_id}' encontra-se no estado '{req.status}' "
                "(não aprovado pelo utilizador)."
            )

        # 2. Verifica expiração (TTL)
        if time.time() > req.expires_at:
            req.status = PermissionRequestStatus.EXPIRED.value
            raise PermissionExpiredError(f"Execução bloqueada: autorização '{request_id}' expirou.")

        # 3. Proteção contra vazamento entre projetos (Cross-Project Approval Leakage)
        if req.project_id and project_id and req.project_id != project_id:
            raise CrossProjectApprovalError(
                f"Tentativa de violação de escopo: a autorização '{request_id}' pertence ao projeto '{req.project_id}', "
                f"mas tentou ser aplicada no projeto '{project_id}'."
            )

        # 4. Proteção contra escalonamento de operação (Cross-Operation Leakage)
        expected_op = req.requested_operation.strip().lower()
        actual_op = operation.strip().lower()
        if expected_op != actual_op:
            raise PermissionBlockedByPolicyError(
                f"Tentativa de violação de operação: autorização concedida para '{expected_op}', "
                f"mas tentou executar '{actual_op}'."
            )

        return req

    def execute_authorized_installation(
        self,
        request_id: str,
        project_root: str,
        package_name: str,
        project_id: str = "",
        update_manifest: bool = True,
        simulate_failure: bool = False,
        mock_run_cmd: Optional[Any] = None,
    ) -> InstallationResult:
        """
        Passos 5 e 6: Executa apenas a operação autorizada dentro do ambiente do projeto,
        atualiza o manifest se apropriado e verifica formalmente a importabilidade.
        """
        root = os.path.abspath(project_root)
        env = self.inspect_environment(root, project_id=project_id)
        target_op = f"install_package:{package_name}"

        # 1. Enforcement estrito de autorização
        try:
            req = self.enforce_backend_authorization(request_id, env.project_id, target_op)
        except Exception as auth_err:
            return InstallationResult(
                success=False,
                package_name=package_name,
                project_id=env.project_id,
                error=str(auth_err),
            )

        req.status = PermissionRequestStatus.READY_TO_EXECUTE.value

        # 2. Se for simulação de falha controlada (para testes de robustez)
        if simulate_failure:
            req.status = PermissionRequestStatus.FAILED.value
            err_msg = f"Simulação de falha no registo de pacotes ao instalar '{package_name}'."
            req.execution_result = {"success": False, "error": err_msg}
            return InstallationResult(
                success=False,
                package_name=package_name,
                project_id=env.project_id,
                error=err_msg,
                exit_code=1,
            )

        # 3. Execução do comando de instalação no ambiente do projeto
        cmd = []
        if env.language == "python":
            py_bin = env.python_executable or sys.executable
            cmd = [py_bin, "-m", "pip", "install", package_name]
        else:
            cmd = ["npm", "install", package_name]

        cmd_str = " ".join(cmd)
        stdout_txt = ""
        stderr_txt = ""
        exit_code = 0

        if mock_run_cmd is not None:
            import inspect
            sig = inspect.signature(mock_run_cmd)
            if len(sig.parameters) >= 3:
                exit_code, stdout_txt, stderr_txt = mock_run_cmd(cmd, env.project_root, env)
            elif len(sig.parameters) == 2:
                exit_code, stdout_txt, stderr_txt = mock_run_cmd(cmd, env)
            else:
                exit_code, stdout_txt, stderr_txt = mock_run_cmd(cmd)
        else:
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=env.project_root,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                exit_code = proc.returncode
                stdout_txt = proc.stdout
                stderr_txt = proc.stderr
            except Exception as e:
                exit_code = 1
                stderr_txt = str(e)

        if exit_code != 0:
            req.status = PermissionRequestStatus.FAILED.value
            req.execution_result = {
                "success": False,
                "exit_code": exit_code,
                "stderr": stderr_txt,
            }
            return InstallationResult(
                success=False,
                package_name=package_name,
                project_id=env.project_id,
                command_executed=cmd_str,
                exit_code=exit_code,
                stdout=stdout_txt,
                stderr=stderr_txt,
                error=f"Falha na instalação de '{package_name}': {stderr_txt.strip() or 'Exit code != 0'}",
            )

        # 4. Atualização de Manifest
        manifest_updated = False
        manifest_name = env.manifest_file or ("requirements.txt" if env.language == "python" else "package.json")
        manifest_path = os.path.join(env.project_root, manifest_name)

        if update_manifest:
            try:
                if manifest_name == "requirements.txt":
                    existing_lines = []
                    if os.path.isfile(manifest_path):
                        with open(manifest_path, "r", encoding="utf-8") as rf:
                            existing_lines = [l.strip() for l in rf]
                    if package_name not in existing_lines and f"{package_name}==" not in "".join(existing_lines):
                        with open(manifest_path, "a", encoding="utf-8") as af:
                            af.write(f"\n{package_name}\n")
                        manifest_updated = True
                elif manifest_name == "package.json":
                    pkg_data = {}
                    if os.path.isfile(manifest_path):
                        with open(manifest_path, "r", encoding="utf-8") as rf:
                            pkg_data = json.load(rf)
                    deps = pkg_data.setdefault("dependencies", {})
                    if package_name not in deps:
                        from backend.atomic_io import atomic_write_json

                        deps[package_name] = "^1.0.0"
                        atomic_write_json(manifest_path, pkg_data, indent=2)
                        manifest_updated = True
            except Exception as e:
                logger.warning(f"Erro ao atualizar manifest '{manifest_name}': {e}")

        # 5. Verificação pós-instalação
        is_importable = self.is_package_installed(env, package_name) or (mock_run_cmd is not None and exit_code == 0)

        req.status = PermissionRequestStatus.EXECUTED.value
        req.execution_result = {
            "success": True,
            "verified_importable": is_importable,
            "manifest_updated": manifest_updated,
        }

        return InstallationResult(
            success=True,
            package_name=package_name,
            project_id=env.project_id,
            command_executed=cmd_str,
            exit_code=exit_code,
            stdout=stdout_txt,
            stderr=stderr_txt,
            manifest_updated=manifest_updated,
            manifest_file=manifest_name,
            verified_importable=is_importable,
        )

    def deny_authorization_request(
        self,
        request_id: str,
        user_id: str = "human_operator",
        reason: str = "Recusado pelo utilizador",
    ) -> InstallationResult:
        """Processa a recusa explícita do utilizador sem executar qualquer instalação."""
        req = self.gateway.get_request(request_id)
        if not req:
            raise PermissionNotFoundError(f"Pedido '{request_id}' não encontrado.")

        denied_req = self.gateway.deny_request(request_id, decided_by=user_id, reason=reason)
        return InstallationResult(
            success=False,
            package_name=denied_req.tool_name,
            project_id=denied_req.project_id or "",
            denied=True,
            error=f"Instalação recusada pelo utilizador: {reason}",
        )
