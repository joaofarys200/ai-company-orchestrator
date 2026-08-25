"""
JARVIS OS — Security Sentinel Persistence Telemetry Collector
Inventário read-only de mecanismos de persistência no Windows (Registry, Startup, Tasks, Services).
"""

from __future__ import annotations

import csv
import io
import os
import subprocess
from typing import List, Tuple
import psutil

try:
    import winreg
except ImportError:
    winreg = None

from security.sentinel.collectors.base import BaseCollector
from security.sentinel.contracts import EventCategory, PersistenceItem, SecurityEvidence


class PersistenceCollector(BaseCollector):
    """Coletor de telemetria de pontos de persistência do Windows."""

    def __init__(self) -> None:
        super().__init__(name="persistence_collector", category=EventCategory.PERSISTENCE)

    def _scan_registry_run(self) -> List[PersistenceItem]:
        """Audita chaves de arranque no Registo do Windows (HKCU e HKLM) em modo READ-ONLY."""
        items: List[PersistenceItem] = []
        if not winreg:
            return items

        targets: List[Tuple[Any, str, str]] = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU_RUN"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU_RUNONCE"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM_RUN"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM_RUNONCE"),
        ]

        for hkey, subkey, label in targets:
            try:
                with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ) as key:
                    index = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, index)
                            clean_val = str(value).strip().strip('"')
                            target_path = clean_val.split(".exe")[0] + ".exe" if ".exe" in clean_val.lower() else clean_val
                            sha256_hash = self.compute_sha256(target_path) if os.path.isfile(target_path) else ""

                            items.append(
                                PersistenceItem(
                                    kind="REGISTRY_RUN",
                                    name=name,
                                    target_path=str(value),
                                    location=f"{label}\\{name}",
                                    sha256=sha256_hash,
                                    is_active=True,
                                )
                            )
                            index += 1
                        except OSError:
                            break
            except (PermissionError, FileNotFoundError, OSError):
                continue

        return items

    def _scan_startup_folders(self) -> List[PersistenceItem]:
        """Audita atalhos e scripts presentes nas pastas Startup do Windows."""
        items: List[PersistenceItem] = []
        startup_dirs = [
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs\Startup"),
        ]

        for sdir in startup_dirs:
            if not os.path.isdir(sdir):
                continue
            try:
                for entry in os.listdir(sdir):
                    full_path = os.path.join(sdir, entry)
                    if os.path.isfile(full_path) and not entry.lower() == "desktop.ini":
                        sha256_hash = self.compute_sha256(full_path)
                        items.append(
                            PersistenceItem(
                                kind="STARTUP_FOLDER",
                                name=entry,
                                target_path=full_path,
                                location=sdir,
                                sha256=sha256_hash,
                                is_active=True,
                            )
                        )
            except Exception:
                continue

        return items

    def _scan_scheduled_tasks(self) -> List[PersistenceItem]:
        """Audita tarefas agendadas no Windows via schtasks (read-only query)."""
        items: List[PersistenceItem] = []
        try:
            res = subprocess.run(
                ["schtasks", "/query", "/fo", "CSV", "/nh"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0 and res.stdout:
                reader = csv.reader(io.StringIO(res.stdout))
                for row in reader:
                    if len(row) >= 2:
                        task_name = row[0].strip()
                        status = row[2].strip() if len(row) > 2 else "Unknown"
                        # Ignorar tarefas padrão da Microsoft se excessivas, mas catalogar
                        items.append(
                            PersistenceItem(
                                kind="SCHEDULED_TASK",
                                name=task_name,
                                target_path=status,
                                location=f"TaskScheduler\\{task_name}",
                                is_active=(status.lower() != "disabled"),
                            )
                        )
        except Exception:
            pass

        return items

    def _scan_services(self) -> List[PersistenceItem]:
        """Audita serviços do Windows via psutil (read-only)."""
        items: List[PersistenceItem] = []
        try:
            for service in psutil.win_service_iter():
                try:
                    s_info = service.as_dict()
                    name = s_info.get("name") or "unknown"
                    display = s_info.get("display_name") or name
                    bin_path = s_info.get("binpath") or ""
                    status = s_info.get("status") or "unknown"
                    start_type = s_info.get("start_type") or "unknown"

                    # Focar em serviços com inicialização automática ou em execução
                    if start_type in ("automatic", "manual") or status == "running":
                        clean_exe = bin_path.strip().strip('"').split(".exe")[0] + ".exe" if ".exe" in bin_path.lower() else ""
                        sha256_hash = self.compute_sha256(clean_exe) if clean_exe and os.path.isfile(clean_exe) else ""

                        items.append(
                            PersistenceItem(
                                kind="SERVICE",
                                name=name,
                                target_path=bin_path,
                                arguments=display,
                                location=f"Service\\{name}",
                                sha256=sha256_hash,
                                is_active=(status == "running"),
                            )
                        )
                except Exception:
                    continue
        except Exception:
            pass

        return items

    def collect(self) -> List[SecurityEvidence]:
        """Recolhe todas as entradas de persistência do sistema."""
        evidences: List[SecurityEvidence] = []

        all_items: List[PersistenceItem] = []
        all_items.extend(self._scan_registry_run())
        all_items.extend(self._scan_startup_folders())
        all_items.extend(self._scan_scheduled_tasks())
        all_items.extend(self._scan_services())

        for item in all_items:
            obs = f"Persistence entry ({item.kind}): '{item.name}' -> {item.target_path}"
            evidence = self.create_evidence(
                asset=f"persistence:{item.kind.lower()}:{item.name}",
                observation=obs,
                normalized_data=item.to_dict(),
                raw_reference=item.location,
                confidence=1.0,
                source=f"persistence_{item.kind.lower()}",
            )
            evidences.append(evidence)

        return evidences
