"""
JARVIS OS — Security Sentinel Hosts File Telemetry Collector
Inventário read-only e integridade criptográfica do ficheiro hosts do Windows.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List

from security.sentinel.collectors.base import BaseCollector
from security.sentinel.contracts import EventCategory, HostsInfo, SecurityEvidence


class HostsCollector(BaseCollector):
    """Coletor de integridade e entradas do ficheiro hosts do sistema."""

    def __init__(self, hosts_path: str = r"C:\Windows\System32\drivers\etc\hosts") -> None:
        super().__init__(name="hosts_collector", category=EventCategory.HOSTS)
        self.hosts_path = hosts_path

    def collect(self) -> List[SecurityEvidence]:
        """Recolhe o estado, hash SHA-256 e entradas ativas do ficheiro hosts."""
        evidences: List[SecurityEvidence] = []

        exists = os.path.isfile(self.hosts_path)
        if not exists:
            info = HostsInfo(
                path=self.hosts_path,
                sha256="",
                exists=False,
                line_count=0,
                custom_entries=[],
            )
            evidence = self.create_evidence(
                asset="file:hosts",
                observation="Windows hosts file not found",
                normalized_data=info.to_dict(),
                raw_reference=self.hosts_path,
                confidence=1.0,
                source="file_system_hosts",
            )
            return [evidence]

        sha256_hash = self.compute_sha256(self.hosts_path)
        custom_entries: List[Dict[str, str]] = []
        raw_lines = []

        try:
            with open(self.hosts_path, "r", encoding="utf-8", errors="replace") as f:
                raw_lines = f.readlines()
        except Exception:
            pass

        standard_patterns = ["localhost", "broadcasthost", "local"]

        for line in raw_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            parts = re.split(r"\s+", stripped)
            if len(parts) >= 2:
                ip = parts[0]
                domains = parts[1:]
                for dom in domains:
                    is_standard = (
                        dom.lower() in standard_patterns
                        or (ip in ("127.0.0.1", "::1") and dom.lower() in ("localhost", "localhost.localdomain"))
                    )
                    custom_entries.append({
                        "ip": ip,
                        "domain": dom,
                        "is_standard": str(is_standard),
                    })

        info = HostsInfo(
            path=self.hosts_path,
            sha256=sha256_hash,
            exists=True,
            line_count=len(raw_lines),
            custom_entries=custom_entries,
        )

        obs = f"Hosts file parsed: {len(custom_entries)} active mappings (SHA-256: {sha256_hash[:12]}...)"
        evidence = self.create_evidence(
            asset="file:hosts",
            observation=obs,
            normalized_data=info.to_dict(),
            raw_reference=self.hosts_path,
            confidence=1.0,
            source="file_system_hosts",
        )
        evidences.append(evidence)

        return evidences
