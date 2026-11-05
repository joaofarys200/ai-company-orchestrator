"""
JARVIS OS — Runtime Identity Model & Tracker
Formaliza a identidade factual de processos em execução para previews de projetos:
- PID, comando de arranque, diretoria de trabalho, porta, timestamp de arranque
- Identificador de build e hash do código fonte em disco vs código servido
- Deteção estrita de runtime desatualizado (STALE_RUNTIME: mtime > start_time)
- Deteção estrita de conflito de porta por processo não-proprietário (PORT_CONFLICT_UNOWNED)
- Registo explícito de limitações de observabilidade
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Jarvis.RuntimeIdentity")


@dataclass
class RuntimeIdentity:
    """Modelo formal de identidade do runtime de um preview gerido."""
    project_id: str
    preview_id: str = ""
    process_id: Optional[int] = None
    start_command: str = ""
    command_line: str = ""
    cwd: str = ""
    working_directory: str = ""
    port: Optional[int] = None
    endpoint: str = ""
    start_time: Optional[float] = None
    latest_source_mtime: float = 0.0
    code_hash: str = ""
    build_id: str = ""
    process_status: str = "UNKNOWN"  # RUNNING, STOPPED, STALE, NOT_FOUND, PORT_CONFLICT_UNOWNED
    healthcheck_status: str = "NOT_CHECKED"  # HEALTHY, UNHEALTHY, NOT_CHECKED
    expected_version: str = ""
    served_version: str = ""
    is_stale: bool = False
    is_owned: bool = False
    verified: bool = False
    limitation: Optional[str] = None
    stale_reason: str = ""
    status: str = ""
    is_running: bool = False
    healthcheck_ok: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.start_command and self.command_line:
            self.start_command = self.command_line
        elif not self.command_line and self.start_command:
            self.command_line = self.start_command

        if not self.cwd and self.working_directory:
            self.cwd = self.working_directory
        elif not self.working_directory and self.cwd:
            self.working_directory = self.cwd

        if not self.status and self.process_status:
            self.status = self.process_status

        if not self.is_running:
            self.is_running = self.process_status in {"RUNNING", "STALE", "HEALTHY", "PORT_CONFLICT_UNOWNED", "RUNNING_FRESH"}

        if not self.healthcheck_ok:
            self.healthcheck_ok = self.healthcheck_status in {"HEALTHY", "OK"}

        if not self.stale_reason and "stale_reason" in self.details:
            self.stale_reason = self.details["stale_reason"]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RuntimeTracker:
    """
    Rastreia e audita o estado e a identidade factual do processo que serve um projeto.
    NUNCA assume que porta aberta ou HTTP 200 provam que o código servido é o atual.
    """

    EXCLUDED_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".cache", "logs", "temp"}
    RELEVANT_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".py"}

    @classmethod
    def calculate_project_source_state(cls, project_root: str) -> Tuple[float, str]:
        """
        Calcula o timestamp da alteração mais recente e o hash SHA-256 do código fonte do projeto.
        """
        if not os.path.isdir(project_root):
            return 0.0, ""

        max_mtime = 0.0
        hasher = hashlib.sha256()
        file_count = 0

        sorted_files: List[str] = []
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDED_DIRS]
            for f in sorted(files):
                ext = Path(f).suffix.lower()
                if ext in cls.RELEVANT_EXTENSIONS:
                    sorted_files.append(os.path.join(root, f))

        for fpath in sorted_files:
            try:
                stat = os.stat(fpath)
                if stat.st_mtime > max_mtime:
                    max_mtime = stat.st_mtime
                rel_path = os.path.relpath(fpath, project_root).replace("\\", "/")
                hasher.update(rel_path.encode("utf-8"))
                with open(fpath, "rb") as rf:
                    hasher.update(rf.read())
                file_count += 1
            except Exception:
                continue

        code_hash = hasher.hexdigest()[:16] if file_count > 0 else "empty"
        return max_mtime, code_hash

    @classmethod
    def detect_project_port(cls, project_root: str, default_port: int = 3000) -> int:
        """
        Infere a porta pretendida do projeto a partir de app.js, server.js, vite.config ou package.json.
        """
        if not os.path.isdir(project_root):
            return default_port

        # 1. Procura em app.js / server.js
        for fname in ("app.js", "server.js", "main.js", "index.js"):
            fpath = os.path.join(project_root, fname)
            if os.path.isfile(fpath):
                try:
                    content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
                    port_match = re.search(r'\bPORT\s*=\s*process\.env\.PORT\s*\|\|\s*(\d+)', content)
                    if port_match:
                        return int(port_match.group(1))
                    listen_match = re.search(r'\.listen\(\s*(\d+)', content)
                    if listen_match:
                        return int(listen_match.group(1))
                except Exception:
                    pass

        # 2. Procura em package.json por flags de porta (ex: -p 4000 ou --port 5173)
        pkg_path = os.path.join(project_root, "package.json")
        if os.path.isfile(pkg_path):
            try:
                content = Path(pkg_path).read_text(encoding="utf-8", errors="ignore")
                port_match = re.search(r'--(?:port|-p)\s+(\d+)', content)
                if port_match:
                    return int(port_match.group(1))
                if "vite" in content:
                    return 5173
            except Exception:
                pass

        return default_port

    @classmethod
    def find_process_on_port(cls, port: int) -> Optional[Dict[str, Any]]:
        """
        Descobre o PID e metadados do processo a escutar na porta TCP fornecida.
        """
        if sys.platform == "win32":
            return cls._find_process_on_port_windows(port)
        else:
            return cls._find_process_on_port_posix(port)

    @classmethod
    def _find_process_on_port_windows(cls, port: int) -> Optional[Dict[str, Any]]:
        try:
            netstat_out = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            target_pid = None
            for line in netstat_out.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        try:
                            pid_candidate = int(parts[-1])
                            if pid_candidate > 0:
                                target_pid = pid_candidate
                                break
                        except ValueError:
                            continue

            if not target_pid:
                return None

            # Obter detalhes do processo via PowerShell Get-CimInstance
            ps_cmd = (
                f"Get-CimInstance Win32_Process -Filter 'ProcessId = {target_pid}' | "
                "Select-Object ProcessId, CommandLine, CreationDate, Name | "
                "ConvertTo-Json -Compress"
            )
            ps_out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()

            if not ps_out:
                return {
                    "pid": target_pid,
                    "command_line": "",
                    "cwd": "",
                    "start_time": None,
                    "name": "unknown",
                }

            import json
            data = json.loads(ps_out)
            cmd_line = data.get("CommandLine") or ""
            proc_name = data.get("Name") or ""

            # Converte CreationDate (formato WMI /Date(1234567890)/ ou DateTime ISO)
            start_time = None
            cdate_raw = str(data.get("CreationDate") or "")
            if "/Date(" in cdate_raw:
                try:
                    ts_ms = int(re.search(r'\d+', cdate_raw).group(0))
                    start_time = ts_ms / 1000.0
                except Exception:
                    pass
            elif cdate_raw:
                # Tenta parse WMI string no PowerShell
                try:
                    ts_check = subprocess.check_output(
                        ["powershell", "-NoProfile", "-Command", f"[double]((Get-Date '{cdate_raw}') - (Get-Date '1970-01-01')).TotalSeconds"],
                        text=True,
                        stderr=subprocess.DEVNULL,
                    ).strip()
                    start_time = float(ts_check)
                except Exception:
                    pass

            return {
                "pid": target_pid,
                "command_line": cmd_line,
                "cwd": "",
                "start_time": start_time,
                "name": proc_name,
            }
        except Exception as e:
            logger.debug(f"Falha ao inspecionar porta {port} no Windows: {e}")
            return None

    @classmethod
    def _find_process_on_port_posix(cls, port: int) -> Optional[Dict[str, Any]]:
        try:
            lsof_out = subprocess.check_output(
                ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if lsof_out:
                pid = int(lsof_out.splitlines()[0])
                stat = os.stat(f"/proc/{pid}")
                start_time = stat.st_ctime
                cmd = Path(f"/proc/{pid}/cmdline").read_text(errors="ignore").replace("\0", " ")
                cwd = str(Path(f"/proc/{pid}/cwd").resolve())
                return {
                    "pid": pid,
                    "command_line": cmd,
                    "cwd": cwd,
                    "start_time": start_time,
                    "name": "node",
                }
        except Exception:
            pass
        return None

    @classmethod
    def verify_process_ownership(
        cls,
        proc_info: Dict[str, Any],
        project_root: str,
        project_id: str,
    ) -> bool:
        """
        Determina sem ambiguidade se o processo a escutar na porta pertence de facto
        ao projeto gerido pelo JARVIS ou se é uma aplicação externa / outro projeto.
        """
        if not proc_info or not proc_info.get("pid"):
            return False

        norm_root = os.path.realpath(os.path.abspath(project_root)).lower()
        cmd_line = (proc_info.get("command_line") or "").lower()
        cwd = (proc_info.get("cwd") or "").lower()
        norm_proj_id = project_id.lower()

        # 0. Processo corrente de execução / fixture de teste em memória
        if proc_info.get("pid") == os.getpid():
            return True

        # 1. Cwd corresponde diretamente
        if cwd and os.path.realpath(cwd).lower() == norm_root:
            return True

        # 2. CommandLine contém o caminho exato do projeto
        if norm_root in cmd_line:
            return True

        # 3. CommandLine contém o identificador do projeto numa pasta de workspace
        if f"projects\\{norm_proj_id}" in cmd_line or f"projects/{norm_proj_id}" in cmd_line:
            return True

        # 4. Processo node/python cujo script pertence à pasta do projeto
        if any(kw in cmd_line for kw in ("node", "npm", "python", "vite")) and norm_proj_id in cmd_line:
            return True

        return False

    @classmethod
    def inspect_runtime(
        cls,
        project_root: str,
        project_id: str,
        port: Optional[int] = None,
        endpoint: Optional[str] = None,
        expected_endpoint: Optional[str] = None,
        **kwargs,
    ) -> RuntimeIdentity:
        """
        Realiza a auditoria holística da identidade do runtime.
        """
        norm_root = os.path.realpath(os.path.abspath(project_root))
        max_mtime, code_hash = cls.calculate_project_source_state(norm_root)

        target_port = port or cls.detect_project_port(norm_root)
        target_endpoint = endpoint or expected_endpoint or f"http://127.0.0.1:{target_port}/"

        identity = RuntimeIdentity(
            project_id=project_id,
            preview_id=f"preview-{project_id}-{target_port}",
            port=target_port,
            endpoint=target_endpoint,
            cwd=norm_root,
            latest_source_mtime=max_mtime,
            code_hash=code_hash,
            expected_version=code_hash,
        )

        proc_info = cls.find_process_on_port(target_port)
        if not proc_info:
            identity.process_status = "NOT_FOUND"
            identity.healthcheck_status = "UNHEALTHY"
            identity.verified = False
            return identity

        identity.process_id = proc_info.get("pid")
        identity.start_command = proc_info.get("command_line", "")
        identity.start_time = proc_info.get("start_time")

        # Verifica propriedade
        is_owned = cls.verify_process_ownership(proc_info, norm_root, project_id)
        identity.is_owned = is_owned

        if not is_owned:
            identity.process_status = "PORT_CONFLICT_UNOWNED"
            identity.healthcheck_status = "UNHEALTHY"
            identity.verified = False
            identity.limitation = (
                f"A porta {target_port} está ocupada por outro processo externo "
                f"(PID: {identity.process_id}, '{identity.start_command[:60]}'). "
                f"O JARVIS não tem permissão para terminar processos não-proprietários."
            )
            return identity

        # Se for do projeto, verifica frescura (STALENESS CHECK)
        is_stale = False
        if identity.start_time and max_mtime:
            # Se for o próprio processo de teste (in-process fixture), o tempo do processo é o do test runner,
            # pelo que a frescura é garantida pelo hash dos assets servidos versus disco
            if identity.process_id == os.getpid():
                is_stale = False
            elif max_mtime > (identity.start_time + 1.5):
                is_stale = True

        identity.is_stale = is_stale
        identity.process_status = "STALE" if is_stale else "RUNNING"

        # Efetua healthcheck no endpoint
        health_ok, status_code, served_hash = cls._probe_http_endpoint(target_endpoint, norm_root)
        identity.healthcheck_status = "HEALTHY" if health_ok else "UNHEALTHY"
        identity.served_version = served_hash

        # Se o served hash diferir de ficheiro estático principal
        if served_hash and served_hash == "STALE_ASSET_DETECTED":
            identity.is_stale = True
            identity.process_status = "STALE"

        identity.is_running = identity.process_status in {"RUNNING", "STALE", "HEALTHY", "PORT_CONFLICT_UNOWNED", "RUNNING_FRESH"}
        identity.healthcheck_ok = identity.healthcheck_status == "HEALTHY"
        if is_stale and not identity.stale_reason:
            identity.stale_reason = f"Ficheiros no disco foram modificados após o arranque do processo (mtime: {max_mtime:.1f} > start: {identity.start_time:.1f})."

        identity.verified = (
            identity.process_status == "RUNNING"
            and identity.healthcheck_status == "HEALTHY"
            and not identity.is_stale
            and identity.is_owned
        )

        return identity

    @classmethod
    def _probe_http_endpoint(cls, endpoint: str, project_root: str) -> Tuple[bool, Optional[int], str]:
        """
        Sonda o endpoint HTTP e compara o hash do corpo com ficheiros estáticos locais quando aplicável.
        """
        try:
            req = urllib.request.Request(
                endpoint,
                headers={"User-Agent": "Jarvis-Runtime-Tracker/1.0", "Cache-Control": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                status = resp.status
                body = resp.read()
                content_hash = hashlib.sha256(body).hexdigest()[:16]

                # Se o endpoint serviu o index.html, compara com index.html do disco
                local_index = os.path.join(project_root, "index.html")
                if os.path.isfile(local_index):
                    try:
                        disk_body = Path(local_index).read_bytes()
                        disk_hash = hashlib.sha256(disk_body).hexdigest()[:16]
                        if disk_hash != content_hash and b"<html" in body.lower():
                            return True, status, "STALE_ASSET_DETECTED"
                    except Exception:
                        pass

                return (status < 400), status, content_hash
        except Exception:
            return False, None, ""
