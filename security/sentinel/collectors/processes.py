"""
JARVIS OS — Security Sentinel Process Telemetry Collector
Inventário read-only de processos, árvores de execução, caminhos e hashes.
"""

from __future__ import annotations

import os
import psutil
from typing import List

from security.sentinel.collectors.base import BaseCollector
from security.sentinel.contracts import EventCategory, ProcessItem, SecurityEvidence


class ProcessCollector(BaseCollector):
    """Coletor de telemetria de processos do sistema."""

    def __init__(self) -> None:
        super().__init__(name="process_collector", category=EventCategory.PROCESS)

    def is_temp_path(self, path: str) -> bool:
        """Verifica se o caminho do executável está localizado em diretórios temporários."""
        if not path:
            return False
        lower = path.lower()
        temp_markers = [
            "\\temp\\",
            "\\tmp\\",
            "\\appdata\\local\\temp\\",
            "\\windows\\temp\\",
            "\\users\\public\\",
        ]
        return any(marker in lower for marker in temp_markers)

    def collect(self) -> List[SecurityEvidence]:
        """Recolhe a lista de processos ativos e respetivos metadados."""
        evidences: List[SecurityEvidence] = []
        temp_vars = [
            os.environ.get("TEMP", "").lower(),
            os.environ.get("TMP", "").lower(),
            os.environ.get("LOCALAPPDATA", "").lower() + "\\temp",
        ]

        for proc in psutil.process_iter(
            attrs=["pid", "ppid", "name", "exe", "cmdline", "username", "create_time", "status"]
        ):
            try:
                info = proc.info
                pid = info.get("pid") or 0
                ppid = info.get("ppid") or 0
                name = info.get("name") or "unknown"
                exe_path = info.get("exe") or ""
                raw_cmd = info.get("cmdline") or []
                cmdline = " ".join(raw_cmd) if isinstance(raw_cmd, list) else str(raw_cmd)
                username = info.get("username") or ""
                create_time = info.get("create_time") or 0.0
                status = info.get("status") or "running"

                is_temp = self.is_temp_path(exe_path)
                sha256_hash = self.compute_sha256(exe_path) if exe_path else ""

                item = ProcessItem(
                    pid=pid,
                    ppid=ppid,
                    name=name,
                    exe_path=exe_path,
                    cmdline=self.sanitize_cmdline(cmdline),
                    username=username,
                    create_time=create_time,
                    status=status,
                    sha256=sha256_hash,
                    is_temp_dir=is_temp,
                )

                obs = f"Active process {name} (PID: {pid}, PPID: {ppid})"
                if is_temp:
                    obs += " [RUNNING FROM TEMP DIRECTORY]"

                evidence = self.create_evidence(
                    asset=f"process:{pid}",
                    observation=obs,
                    normalized_data=item.to_dict(),
                    raw_reference=f"PID {pid}: {exe_path}",
                    confidence=1.0,
                    source="psutil_process_table",
                )
                evidences.append(evidence)

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue

        return evidences
