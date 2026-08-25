"""
JARVIS OS — Network Endpoint Firewall Block Executor (Fase S3)
Defensive isolation of malicious remote endpoints via explicit named Windows Firewall rules with clean rollback.
"""

from __future__ import annotations

import ipaddress
import re
import subprocess
import time
from typing import Any, Dict, Optional, Tuple

from security.sentinel.contracts import ResponseActionType, SecurityResponseAction
from security.sentinel.response.executors.base import BaseActionExecutor


class FirewallBlockExecutor(BaseActionExecutor):
    """Executor defensivo para bloqueio de endpoints de rede suspeitos na Firewall do Windows."""

    def __init__(self) -> None:
        super().__init__(ResponseActionType.BLOCK_NETWORK_ENDPOINT)

    def _parse_target(self, target: str) -> Tuple[str, Optional[int]]:
        """Extrai IP e porta opcional a partir do target (ex: '198.51.100.42', 'endpoint:198.51.100.42:443')."""
        cleaned = target.replace("endpoint:", "").replace("ip:", "").replace("network:", "").strip()
        
        # Separa porta se fornecida
        port: Optional[int] = None
        if ":" in cleaned and not ("[" in cleaned or "/" in cleaned):
            parts = cleaned.split(":")
            if len(parts) == 2 and parts[1].isdigit():
                cleaned = parts[0]
                port = int(parts[1])

        # Validação de formato de IP
        try:
            ipaddress.ip_address(cleaned)
        except ValueError:
            try:
                ipaddress.ip_network(cleaned, strict=False)
            except ValueError:
                raise ValueError(f"Formato de endereço IP/rede inválido para regra de firewall: '{target}'")

        return cleaned, port

    def _rule_name_for_action(self, action_id: str) -> str:
        # Sanitização do action_id para nome de regra de firewall
        safe_id = re.sub(r"[^A-Za-z0-9\-_]", "", action_id)
        return f"JARVIS-SENTINEL-{safe_id}"

    def _rule_exists(self, rule_name: str) -> bool:
        cmd = ["netsh.exe", "advfirewall", "firewall", "show", "rule", f"name={rule_name}"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=False)
        return res.returncode == 0 and "No rules match" not in res.stdout and "Nenhuma regra correspondente" not in res.stdout

    def capture_pre_state(self, action: SecurityResponseAction) -> Dict[str, Any]:
        try:
            ip, port = self._parse_target(action.target)
            rule_name = self._rule_name_for_action(action.action_id)
            exists = self._rule_exists(rule_name)
            return {
                "target_ip": ip,
                "target_port": port,
                "rule_name": rule_name,
                "rule_already_exists": exists,
                "captured_at": time.time(),
            }
        except Exception as e:
            return {"target": action.target, "error": str(e), "captured_at": time.time()}

    def pre_check(self, action: SecurityResponseAction) -> Tuple[bool, str]:
        try:
            ip, port = self._parse_target(action.target)
        except ValueError as e:
            return False, str(e)

        # Não permitir bloquear localhost ou loopback
        if ip in ("127.0.0.1", "::1", "0.0.0.0"):
            return False, "Bloqueado: Não é permitido bloquear o endereço de loopback/localhost"

        rule_name = self._rule_name_for_action(action.action_id)
        if self._rule_exists(rule_name):
            return False, f"A regra de firewall '{rule_name}' já existe previamente"

        return True, f"Target de rede validado: {ip}" + (f":{port}" if port else "")

    def execute(self, action: SecurityResponseAction) -> Dict[str, Any]:
        ip, port = self._parse_target(action.target)
        rule_name = self._rule_name_for_action(action.action_id)

        cmd = [
            "netsh.exe", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}",
            "dir=out",
            "action=block",
            f"remoteip={ip}",
            "enable=yes",
        ]
        if port is not None:
            cmd.extend(["protocol=TCP", f"remoteport={port}"])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=False)
        if res.returncode != 0:
            raise RuntimeError(f"Falha ao criar regra de firewall: {res.stderr.strip() or res.stdout.strip()}")

        return {
            "rule_name": rule_name,
            "target_ip": ip,
            "target_port": port,
            "direction": "out",
            "action": "block",
            "executed_at": time.time(),
            "stdout": res.stdout.strip(),
        }

    def verify(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        rule_name = self._rule_name_for_action(action.action_id)
        exists = self._rule_exists(rule_name)

        if not exists:
            return False, {
                "verified": False,
                "reason": f"Regra de firewall '{rule_name}' não foi encontrada após execução",
                "post_state": {"rule_exists": False},
            }

        return True, {
            "verified": True,
            "reason": f"Regra de firewall '{rule_name}' ativa e verificada no subsistema do Windows",
            "post_state": {"rule_name": rule_name, "rule_exists": True},
        }

    def rollback(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        rule_name = self._rule_name_for_action(action.action_id)
        if not self._rule_exists(rule_name):
            return True, {
                "rollback_applied": True,
                "message": f"Regra de firewall '{rule_name}' já se encontrava ausente",
            }

        cmd = ["netsh.exe", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=False)

        if res.returncode != 0:
            return False, {
                "rollback_applied": False,
                "error": f"Falha ao remover regra de firewall '{rule_name}': {res.stderr.strip()}",
            }

        return True, {
            "rollback_applied": True,
            "message": f"Regra de firewall '{rule_name}' removida com sucesso. Regras pré-existentes intactas.",
        }
