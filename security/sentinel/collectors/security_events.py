"""
JARVIS OS — Security Sentinel Windows Security & Defender Events Collector
Inventário read-only do estado do Defender, Firewall e eventos de segurança do sistema.
"""

from __future__ import annotations

import json
import subprocess
from typing import Dict, List

from security.sentinel.collectors.base import BaseCollector
from security.sentinel.contracts import EventCategory, SecurityEvidence, WindowsSecurityStatus


class WindowsSecurityEventsCollector(BaseCollector):
    """Coletor de telemetria do Defender, Firewall e logs do sistema."""

    def __init__(self) -> None:
        super().__init__(name="windows_security_events_collector", category=EventCategory.DEFENDER)

    def _query_defender_status(self) -> Dict[str, bool]:
        """Consulta o estado do Windows Defender via PowerShell em modo READ-ONLY."""
        result = {"realtime_enabled": True, "antivirus_enabled": True}
        cmd = "Get-MpComputerStatus | Select-Object RealTimeProtectionEnabled, AntivirusEnabled | ConvertTo-Json"
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                result["realtime_enabled"] = bool(data.get("RealTimeProtectionEnabled", True))
                result["antivirus_enabled"] = bool(data.get("AntivirusEnabled", True))
        except Exception:
            pass
        return result

    def _query_firewall_status(self) -> Dict[str, bool]:
        """Consulta o estado dos perfis da Firewall do Windows (Domain, Private, Public)."""
        result = {"domain_enabled": True, "private_enabled": True, "public_enabled": True}
        cmd = "Get-NetFirewallProfile | Select-Object Name, Enabled | ConvertTo-Json"
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, list):
                    for prof in data:
                        name = str(prof.get("Name", "")).lower()
                        enabled = (prof.get("Enabled") == 1 or prof.get("Enabled") is True or prof.get("Enabled") == "True")
                        if "domain" in name:
                            result["domain_enabled"] = enabled
                        elif "private" in name:
                            result["private_enabled"] = enabled
                        elif "public" in name:
                            result["public_enabled"] = enabled
        except Exception:
            pass
        return result

    def collect(self) -> List[SecurityEvidence]:
        """Recolhe o estado de proteção e integridade de segurança do Windows."""
        evidences: List[SecurityEvidence] = []

        defender = self._query_defender_status()
        firewall = self._query_firewall_status()

        status = WindowsSecurityStatus(
            defender_realtime_enabled=defender.get("realtime_enabled"),
            defender_antivirus_enabled=defender.get("antivirus_enabled"),
            firewall_domain_enabled=firewall.get("domain_enabled"),
            firewall_private_enabled=firewall.get("private_enabled"),
            firewall_public_enabled=firewall.get("public_enabled"),
        )

        obs = (
            f"Windows Security State: Defender RealTime={status.defender_realtime_enabled}, "
            f"Firewall Domain={status.firewall_domain_enabled}, "
            f"Private={status.firewall_private_enabled}, Public={status.firewall_public_enabled}"
        )

        evidence = self.create_evidence(
            asset="system:windows_security_subsystem",
            observation=obs,
            normalized_data=status.to_dict(),
            raw_reference="PowerShell MpComputerStatus & NetFirewallProfile",
            confidence=1.0,
            source="windows_security_wmi",
        )
        evidences.append(evidence)

        return evidences
