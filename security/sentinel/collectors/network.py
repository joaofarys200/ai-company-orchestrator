"""
JARVIS OS — Security Sentinel Network Telemetry Collector
Inventário read-only de conexões ativas, portas em escuta e mapeamento de processos.
"""

from __future__ import annotations

import psutil
from typing import Dict, List, Optional

from security.sentinel.collectors.base import BaseCollector
from security.sentinel.contracts import EventCategory, NetworkItem, SecurityEvidence


class NetworkCollector(BaseCollector):
    """Coletor de telemetria de rede e sockets locais."""

    def __init__(self) -> None:
        super().__init__(name="network_collector", category=EventCategory.NETWORK)

    def _get_process_name(self, pid: Optional[int], cache: Dict[int, str]) -> Optional[str]:
        """Obtém o nome do processo de forma segura e com cache em memória."""
        if not pid:
            return None
        if pid in cache:
            return cache[pid]
        try:
            name = psutil.Process(pid).name()
            cache[pid] = name
            return name
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            cache[pid] = "unknown"
            return "unknown"
        except Exception:
            return None

    def collect(self) -> List[SecurityEvidence]:
        """Recolhe conexões de rede e portas abertas em modo read-only."""
        evidences: List[SecurityEvidence] = []
        name_cache: Dict[int, str] = {}

        try:
            connections = psutil.net_connections(kind="inet")
        except (psutil.AccessDenied, PermissionError):
            # Fallback para sockets acessíveis pelo utilizador atual
            return evidences
        except Exception:
            return evidences

        for conn in connections:
            try:
                laddr = conn.laddr
                raddr = conn.raddr
                local_ip = laddr.ip if laddr else "0.0.0.0"
                local_port = laddr.port if laddr else 0
                remote_ip = raddr.ip if raddr else None
                remote_port = raddr.port if raddr else None
                status = conn.status or "NONE"
                protocol = "TCP" if conn.type == psutil.socket.SOCK_STREAM else "UDP"
                pid = conn.pid
                proc_name = self._get_process_name(pid, name_cache)

                item = NetworkItem(
                    protocol=protocol,
                    local_address=local_ip,
                    local_port=local_port,
                    remote_address=remote_ip,
                    remote_port=remote_port,
                    status=status,
                    pid=pid,
                    process_name=proc_name,
                )

                if status == "LISTEN":
                    obs = f"Listening {protocol} port {local_port} on {local_ip} (PID: {pid}, Process: {proc_name})"
                    asset = f"port:{protocol}:{local_port}"
                else:
                    obs = f"{protocol} connection {local_ip}:{local_port} -> {remote_ip}:{remote_port} ({status}) (PID: {pid}, Process: {proc_name})"
                    asset = f"conn:{protocol}:{local_ip}:{local_port}-{remote_ip}:{remote_port}"

                evidence = self.create_evidence(
                    asset=asset,
                    observation=obs,
                    normalized_data=item.to_dict(),
                    raw_reference=f"{protocol} {local_ip}:{local_port} -> {remote_ip}:{remote_port} [{status}]",
                    confidence=1.0,
                    source="psutil_net_connections",
                )
                evidences.append(evidence)

            except Exception:
                continue

        return evidences
