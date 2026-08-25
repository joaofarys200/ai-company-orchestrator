"""
JARVIS OS — Process Termination Executor (Fase S3)
Safe, defensive termination of suspicious userland processes with pre/post-state verification.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, Set, Tuple
import psutil

from security.sentinel.contracts import ResponseActionType, SecurityResponseAction
from security.sentinel.response.executors.base import BaseActionExecutor

# Processos do Windows e do JARVIS protegidos contra finalização acidental
PROTECTED_PROCESSES: Set[str] = {
    "system",
    "system idle process",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "winlogon.exe",
    "explorer.exe",
    "dwm.exe",
    "spoolsv.exe",
    "fontdrvhost.exe",
    "python.exe",
    "electron.exe",
    "node.exe",
}


class ProcessTerminationExecutor(BaseActionExecutor):
    """Executor defensivo para finalização de processos suspeitos com verificação empírica."""

    def __init__(self) -> None:
        super().__init__(ResponseActionType.TERMINATE_PROCESS)

    def _extract_pid(self, target: str) -> int:
        """Extrai o PID numérico a partir do target (ex: '1234', 'pid:1234', 'process:1234')."""
        cleaned = target.lower().replace("pid:", "").replace("process:", "").strip()
        try:
            return int(cleaned)
        except ValueError:
            raise ValueError(f"Target inválido para terminação de processo: '{target}' (esperava PID inteiro)")

    def _compute_sha256(self, path: str) -> str:
        if not path or not os.path.isfile(path):
            return ""
        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def capture_pre_state(self, action: SecurityResponseAction) -> Dict[str, Any]:
        try:
            pid = self._extract_pid(action.target)
            proc = psutil.Process(pid)
            exe = ""
            try:
                exe = proc.exe()
            except Exception:
                pass

            return {
                "pid": pid,
                "name": proc.name().lower(),
                "exe_path": exe,
                "ppid": proc.ppid(),
                "create_time": proc.create_time(),
                "cmdline": proc.cmdline() if hasattr(proc, "cmdline") else [],
                "sha256": self._compute_sha256(exe) if exe else "",
                "captured_at": time.time(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError) as e:
            return {
                "pid": None,
                "error": str(e),
                "captured_at": time.time(),
            }

    def pre_check(self, action: SecurityResponseAction) -> Tuple[bool, str]:
        try:
            pid = self._extract_pid(action.target)
        except ValueError as e:
            return False, str(e)

        if pid == 0 or pid == 4:
            return False, "Bloqueado: PID de sistema protegido (System/Idle)"

        # Protege o próprio processo do JARVIS
        current_pid = os.getpid()
        if pid == current_pid:
            return False, "Bloqueado: Não é permitido terminar o processo do próprio servidor JARVIS"

        try:
            proc = psutil.Process(pid)
            name = proc.name().lower()
            if name in PROTECTED_PROCESSES:
                return False, f"Bloqueado: O processo '{name}' pertence à lista de proteção crítica do sistema"

            # Se o pre_state foi gravado previamente, valida se o processo não foi reciclado
            if action.pre_state and action.pre_state.get("name"):
                recorded_name = action.pre_state.get("name", "").lower()
                if recorded_name != name:
                    return False, f"Alvo reciclado: PID {pid} agora pertence a '{name}' (era '{recorded_name}')"

            return True, "Processo válido e passível de contenção defensiva"
        except psutil.NoSuchProcess:
            return False, f"Processo com PID {pid} já não se encontra em execução"
        except psutil.AccessDenied:
            return False, f"Permissão negada para aceder aos metadados do PID {pid}"

    def execute(self, action: SecurityResponseAction) -> Dict[str, Any]:
        pid = self._extract_pid(action.target)
        proc = psutil.Process(pid)
        name = proc.name()
        
        proc.terminate()
        try:
            proc.wait(timeout=1.5)
            killed_via = "terminate"
        except psutil.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1.5)
            killed_via = "kill_force"

        return {
            "pid": pid,
            "name": name,
            "terminated_at": time.time(),
            "method": killed_via,
            "status": "TERMINATED",
        }

    def verify(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        pid = self._extract_pid(action.target)
        is_running = psutil.pid_exists(pid)
        
        if is_running:
            try:
                proc = psutil.Process(pid)
                # Se existe com o mesmo create_time do pre-state, não morreu
                pre_create_time = action.pre_state.get("create_time")
                if pre_create_time and abs(proc.create_time() - pre_create_time) < 1.0:
                    return False, {
                        "verified": False,
                        "reason": f"Processo com PID {pid} continua ativo no sistema",
                        "post_state": {"pid": pid, "status": proc.status()},
                    }
            except psutil.NoSuchProcess:
                is_running = False

        return True, {
            "verified": True,
            "reason": f"PID {pid} confirmado ausente e terminado com sucesso",
            "post_state": {"pid": pid, "is_running": False},
        }

    def rollback(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        # Processos terminados não podem ser ressuscitados diretamente sem reexecução manual
        return True, {
            "rollback_applied": True,
            "action": "PROCESS_TERMINATION_RECORDED",
            "message": "Terminação de processo registada; estado irreversível por design de segurança",
        }
