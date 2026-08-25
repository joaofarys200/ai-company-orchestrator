"""
JARVIS OS — Security Sentinel Baseline Engine
Geração de snapshots de segurança, integridade criptográfica e cálculo de diffs determinísticos.
"""

from __future__ import annotations

import json
import os
import platform
import time
from typing import Any, Dict, List, Optional

from security.sentinel.collectors.base import BaseCollector
from security.sentinel.collectors.processes import ProcessCollector
from security.sentinel.collectors.network import NetworkCollector
from security.sentinel.collectors.persistence import PersistenceCollector
from security.sentinel.collectors.hosts import HostsCollector
from security.sentinel.collectors.browser import BrowserCollector
from security.sentinel.collectors.security_events import WindowsSecurityEventsCollector
from security.sentinel.contracts import (
    BaselineDiff,
    SecurityEvidence,
    SystemBaseline,
)


class BaselineEngine:
    """Motor de captura, persistência e comparação de baselines de segurança."""

    def __init__(self, storage_dir: str = r"workspace\sentinel\baselines") -> None:
        self.storage_dir = storage_dir
        self._active_baseline: Optional[SystemBaseline] = None
        self.collectors: List[BaseCollector] = [
            ProcessCollector(),
            NetworkCollector(),
            PersistenceCollector(),
            HostsCollector(),
            BrowserCollector(),
            WindowsSecurityEventsCollector(),
        ]
        os.makedirs(self.storage_dir, exist_ok=True)

    def get_active_baseline(self) -> Optional[SystemBaseline]:
        """Obtém o baseline atualmente ativo na sessão."""
        return self._active_baseline

    def set_active_baseline(self, baseline: SystemBaseline) -> None:
        """Define o baseline ativo na sessão."""
        self._active_baseline = baseline

    def capture_baseline(
        self,
        baseline_id: Optional[str] = None,
        set_as_active: bool = False,
    ) -> SystemBaseline:
        """Executa todos os coletores e constrói o snapshot formal de baseline."""
        now = time.time()
        b_id = baseline_id or f"BASELINE-{int(now)}-{os.urandom(2).hex()}"

        processes: List[Dict[str, Any]] = []
        network: List[Dict[str, Any]] = []
        persistence: List[Dict[str, Any]] = []
        hosts_info: Dict[str, Any] = {}
        browser_extensions: List[Dict[str, Any]] = []
        windows_security: Dict[str, Any] = {}
        metrics: Dict[str, Any] = {}

        for collector in self.collectors:
            start_t = time.time()
            try:
                evidences = collector.collect()
                duration = time.time() - start_t
                metrics[collector.name] = {
                    "count": len(evidences),
                    "duration_seconds": round(duration, 3),
                    "status": "OK",
                }

                for ev in evidences:
                    data = ev.normalized_data
                    if collector.name == "process_collector":
                        processes.append(data)
                    elif collector.name == "network_collector":
                        network.append(data)
                    elif collector.name == "persistence_collector":
                        persistence.append(data)
                    elif collector.name == "hosts_collector":
                        hosts_info = data
                    elif collector.name == "browser_collector":
                        browser_extensions.append(data)
                    elif collector.name == "windows_security_events_collector":
                        windows_security = data

            except Exception as e:
                metrics[collector.name] = {
                    "count": 0,
                    "duration_seconds": round(time.time() - start_t, 3),
                    "status": f"ERROR: {str(e)}",
                }

        host_info = {
            "hostname": os.environ.get("COMPUTERNAME", "localhost"),
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
        }

        # Dicionário canónico para cálculo de hash
        raw_dict = {
            "baseline_id": b_id,
            "timestamp": now,
            "host_info": host_info,
            "processes": processes,
            "network": network,
            "persistence": persistence,
            "hosts_info": hosts_info,
            "browser_extensions": browser_extensions,
            "windows_security": windows_security,
            "collector_metrics": metrics,
        }

        integrity_hash = SystemBaseline.compute_hash(raw_dict)

        baseline = SystemBaseline(
            baseline_id=b_id,
            timestamp=now,
            integrity_hash=integrity_hash,
            host_info=host_info,
            processes=processes,
            network=network,
            persistence=persistence,
            hosts_info=hosts_info,
            browser_extensions=browser_extensions,
            windows_security=windows_security,
            collector_metrics=metrics,
        )

        if set_as_active:
            self._active_baseline = baseline

        return baseline

    def save_baseline(self, baseline: SystemBaseline) -> str:
        """Guarda o snapshot em ficheiro JSON no disco."""
        file_path = os.path.join(self.storage_dir, f"{baseline.baseline_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(baseline.to_dict(), f, indent=2, ensure_ascii=False)
        return file_path

    def load_baseline(self, baseline_id_or_path: str) -> Optional[SystemBaseline]:
        """Carrega um snapshot de baseline guardado."""
        if os.path.isfile(baseline_id_or_path):
            target_path = baseline_id_or_path
        else:
            target_path = os.path.join(self.storage_dir, f"{baseline_id_or_path}.json")

        if not os.path.isfile(target_path):
            return None

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SystemBaseline(**data)
        except Exception:
            return None

    def compare(self, base: SystemBaseline, current: SystemBaseline) -> BaselineDiff:
        """Calcula a diferença determinística entre dois snapshots de baseline."""
        now = time.time()

        # 1. Processos
        base_procs = {p.get("exe_path") or p.get("name"): p for p in base.processes}
        curr_procs = {p.get("exe_path") or p.get("name"): p for p in current.processes}
        new_procs = [p for key, p in curr_procs.items() if key not in base_procs]
        removed_procs = [p for key, p in base_procs.items() if key not in curr_procs]

        # 2. Portas em escuta (Listening Ports)
        base_ports = {
            f"{n.get('protocol')}:{n.get('local_port')}": n
            for n in base.network
            if n.get("status") == "LISTEN"
        }
        curr_ports = {
            f"{n.get('protocol')}:{n.get('local_port')}": n
            for n in current.network
            if n.get("status") == "LISTEN"
        }
        new_ports = [n for key, n in curr_ports.items() if key not in base_ports]
        removed_ports = [n for key, n in base_ports.items() if key not in curr_ports]

        # 3. Persistência
        base_persist = {f"{p.get('kind')}:{p.get('name')}": p for p in base.persistence}
        curr_persist = {f"{p.get('kind')}:{p.get('name')}": p for p in current.persistence}
        new_persist = [p for key, p in curr_persist.items() if key not in base_persist]
        removed_persist = [p for key, p in base_persist.items() if key not in curr_persist]

        # 4. Ficheiro Hosts
        hosts_changed = (
            base.hosts_info.get("sha256") != current.hosts_info.get("sha256")
            or base.hosts_info.get("custom_entries") != current.hosts_info.get("custom_entries")
        )
        hosts_diff = None
        if hosts_changed:
            hosts_diff = {
                "base_sha256": base.hosts_info.get("sha256"),
                "current_sha256": current.hosts_info.get("sha256"),
                "base_entries_count": len(base.hosts_info.get("custom_entries", [])),
                "current_entries_count": len(current.hosts_info.get("custom_entries", [])),
            }

        # 5. Extensões de Browser
        base_exts = {f"{e.get('browser')}:{e.get('extension_id')}": e for e in base.browser_extensions}
        curr_exts = {f"{e.get('browser')}:{e.get('extension_id')}": e for e in current.browser_extensions}
        new_exts = [e for key, e in curr_exts.items() if key not in base_exts]
        removed_exts = [e for key, e in base_exts.items() if key not in curr_exts]

        # 6. Estado de Segurança
        sec_changed = (base.windows_security != current.windows_security)

        return BaselineDiff(
            base_id=base.baseline_id,
            target_id=current.baseline_id,
            timestamp=now,
            new_processes=new_procs,
            removed_processes=removed_procs,
            new_listening_ports=new_ports,
            removed_listening_ports=removed_ports,
            new_persistence=new_persist,
            removed_persistence=removed_persist,
            hosts_changed=hosts_changed,
            hosts_diff=hosts_diff,
            new_browser_extensions=new_exts,
            removed_browser_extensions=removed_exts,
            security_status_changed=sec_changed,
        )
