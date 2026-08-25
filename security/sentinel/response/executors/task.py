"""
JARVIS OS — Scheduled Task Disable Executor (Fase S3)
Safe, defensive disabling (never deletion) of suspicious Windows Scheduled Tasks with rollback support.
"""

from __future__ import annotations

import re
import subprocess
import time
from typing import Any, Dict, Tuple

from security.sentinel.contracts import ResponseActionType, SecurityResponseAction
from security.sentinel.response.executors.base import BaseActionExecutor


class ScheduledTaskDisableExecutor(BaseActionExecutor):
    """Executor defensivo para desativação de Tarefas Agendadas no Windows."""

    def __init__(self) -> None:
        super().__init__(ResponseActionType.DISABLE_SCHEDULED_TASK)

    def _sanitize_task_name(self, target: str) -> str:
        """Limpa e valida o nome da tarefa contra injeção de comandos."""
        cleaned = target.replace("task:", "").replace("task_scheduler:", "").strip()
        if not cleaned:
            raise ValueError("Nome da tarefa agendada não pode ser vazio")
        # Previne injeção de comandos
        if any(c in cleaned for c in ["&", "|", ";", "`", "$", "<", ">", "\n", "\r", '"']):
            raise ValueError(f"Nome de tarefa agendada contém caracteres proibidos: {cleaned}")
        return cleaned

    def _query_task(self, task_name: str) -> Dict[str, Any]:
        """Consulta o estado atual da tarefa via schtasks."""
        cmd = ["schtasks.exe", "/Query", "/TN", task_name, "/FO", "LIST", "/V"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=False)
            if res.returncode != 0:
                return {"exists": False, "raw_output": res.stderr}

            output = res.stdout
            status = "UNKNOWN"
            task_to_run = ""
            author = ""

            for line in output.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    v = v.strip()
                    if "status" in k or "estado" in k:
                        status = v
                    elif "task to run" in k or "ação" in k or "acao" in k:
                        task_to_run = v
                    elif "author" in k or "autor" in k:
                        author = v

            return {
                "exists": True,
                "task_name": task_name,
                "status": status,
                "task_to_run": task_to_run,
                "author": author,
                "raw_output": output[:500],
            }
        except Exception as e:
            return {"exists": False, "error": str(e)}

    def capture_pre_state(self, action: SecurityResponseAction) -> Dict[str, Any]:
        try:
            task_name = self._sanitize_task_name(action.target)
            data = self._query_task(task_name)
            data["captured_at"] = time.time()
            return data
        except Exception as e:
            return {"task_name": action.target, "error": str(e), "captured_at": time.time()}

    def pre_check(self, action: SecurityResponseAction) -> Tuple[bool, str]:
        try:
            task_name = self._sanitize_task_name(action.target)
        except ValueError as e:
            return False, str(e)

        task_data = self._query_task(task_name)
        if not task_data.get("exists", False):
            return False, f"Tarefa agendada '{task_name}' não existe no Windows"

        current_status = task_data.get("status", "").lower()
        if "disabled" in current_status or "desativada" in current_status:
            return False, f"A tarefa agendada '{task_name}' já se encontra desativada"

        return True, f"Tarefa agendada '{task_name}' validada (Estado: {task_data.get('status')})"

    def execute(self, action: SecurityResponseAction) -> Dict[str, Any]:
        task_name = self._sanitize_task_name(action.target)
        cmd = ["schtasks.exe", "/Change", "/TN", task_name, "/DISABLE"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=False)

        if res.returncode != 0:
            raise RuntimeError(f"Falha ao desativar tarefa '{task_name}': {res.stderr.strip() or res.stdout.strip()}")

        return {
            "task_name": task_name,
            "action": "DISABLE",
            "executed_at": time.time(),
            "stdout": res.stdout.strip(),
        }

    def verify(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        task_name = self._sanitize_task_name(action.target)
        task_data = self._query_task(task_name)

        if not task_data.get("exists", False):
            return False, {
                "verified": False,
                "reason": f"Tarefa '{task_name}' não encontrada durante a verificação pós-execução",
                "post_state": task_data,
            }

        current_status = task_data.get("status", "").lower()
        is_disabled = "disabled" in current_status or "desativada" in current_status or "desabilitada" in current_status

        if not is_disabled:
            return False, {
                "verified": False,
                "reason": f"A tarefa '{task_name}' continua no estado ativo: '{task_data.get('status')}'",
                "post_state": task_data,
            }

        return True, {
            "verified": True,
            "reason": f"Tarefa '{task_name}' verificada com sucesso no estado DESATIVADA",
            "post_state": task_data,
        }

    def rollback(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        task_name = self._sanitize_task_name(action.target)
        cmd = ["schtasks.exe", "/Change", "/TN", task_name, "/ENABLE"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=False)

        if res.returncode != 0:
            return False, {
                "rollback_applied": False,
                "error": f"Falha ao reativar tarefa '{task_name}': {res.stderr.strip()}",
            }

        # Verifica se voltou ao estado ativo
        task_data = self._query_task(task_name)
        status = task_data.get("status", "")
        return True, {
            "rollback_applied": True,
            "message": f"Tarefa '{task_name}' reativada com sucesso (Estado: {status})",
            "post_rollback_state": task_data,
        }
