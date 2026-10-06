"""
JARVIS OS — Permission Gateway Capability Checker
Performs post-approval technical checks before execution:
executable existence, versions, OS compatibility, Windows Administrator elevation,
driver requirements, and installation prerequisites.
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
from typing import Any, Dict, Optional, Tuple

from security.permission_gateway.models import CapabilityStatus, PermissionRequest


class CapabilityChecker:
    """
    Verifica se o sistema anfitrião possui os pré-requisitos técnicos para executar a ferramenta.
    Dististingue USER_APPROVED de OS_ADMIN_GRANTED.
    """

    TOOLS_REQUIRING_ADMIN = {"nmap", "npcap", "wireshark", "tcpdump", "sc", "reg"}

    @classmethod
    def is_windows_admin(cls) -> bool:
        """Verifica se o processo atual possui privilégios de Administrador no Windows."""
        if platform.system() != "Windows":
            return os.geteuid() == 0 if hasattr(os, "geteuid") else False
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @classmethod
    def check_capability(
        cls,
        request: Union[PermissionRequest, str],
        mock_installed_tools: Optional[Dict[str, str]] = None,
        mock_is_admin: Optional[bool] = None,
        required_privileges: str = "",
    ) -> Tuple[CapabilityStatus, Dict[str, Any]]:
        if isinstance(request, str):
            tool_name = request.strip()
            priv_text = str(required_privileges or "")
        else:
            tool_name = request.tool_name.strip()
            priv_text = str(getattr(request, "required_privileges", "") or "")

        tool_normalized = tool_name.lower()
        is_admin = cls.is_windows_admin() if mock_is_admin is None else mock_is_admin

        details: Dict[str, Any] = {
            "tool_name": tool_name,
            "os": platform.system(),
            "architecture": platform.machine(),
            "admin_granted": is_admin,
            "executable_path": None,
            "version": None,
            "requires_admin": tool_normalized in cls.TOOLS_REQUIRING_ADMIN or "admin" in priv_text.lower(),
        }

        # 1. Procura se o binário/executável existe no PATH ou nos mocks
        exec_path: Optional[str] = None
        if mock_installed_tools and tool_name in mock_installed_tools:
            exec_path = mock_installed_tools[tool_name]
        elif mock_installed_tools and tool_normalized in mock_installed_tools:
            exec_path = mock_installed_tools[tool_normalized]
        else:
            exec_path = shutil.which(tool_name) or shutil.which(tool_normalized)

        # 2. Se o executável já existe
        if exec_path:
            details["executable_path"] = exec_path
            # Verifica se requer privilégios de Administrador que não foram concedidos no SO
            if details["requires_admin"] and not is_admin:
                details["message"] = "É necessária autorização administrativa do Windows para executar esta ferramenta de baixo nível."
                return CapabilityStatus.ADMIN_PRIVILEGE_REQUIRED, details

            details["message"] = f"Ferramenta '{tool_name}' encontrada e pronta para execução em '{exec_path}'."
            return CapabilityStatus.AVAILABLE, details

        # 3. Se o executável NÃO existe
        is_inst_req = getattr(request, "installation_required", True) if not isinstance(request, str) else True
        if is_inst_req:
            # Se for uma ferramenta com instalador declarado
            details["message"] = f"Ferramenta '{tool_name}' não está instalada no sistema. Instalação necessária."
            return CapabilityStatus.INSTALLATION_REQUIRED, details

        # 4. Caso a ferramenta não suporte este SO ou não exista instalador
        if tool_normalized in {"iptables", "ebpf"} and platform.system() == "Windows":
            details["message"] = f"A ferramenta '{tool_name}' é incompatível com o sistema operativo {platform.system()}."
            return CapabilityStatus.UNSUPPORTED, details

        details["message"] = f"Binário '{tool_name}' não encontrado e não há plano de instalação automática seguro."
        return CapabilityStatus.UNSUPPORTED, details
