from __future__ import annotations

import os
import re


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.realpath(os.path.abspath(BASE_DIR))

COMMAND_BLOCKLIST = [
    (r"\b(remove-item|rm|rmdir|rd|del|erase)\b", "file deletion command"),
    (r"\b(taskkill|stop-process)\b", "process termination command"),
    (r"\b(shutdown|restart-computer)\b", "system shutdown/restart command"),
    (r"\b(format|diskpart|bcdedit)\b", "disk/system modification command"),
    (r"\b(reg\s+delete|sc\s+delete)\b", "registry/service deletion command"),
    (r"\b(takeown|icacls)\b", "permission ownership command"),
    (r"\bgit\s+reset\s+--hard\b", "destructive git reset"),
    (r"\bgit\s+clean\b", "destructive git clean"),
    (r"\bdocker\s+system\s+prune\b", "destructive docker prune"),
]


def resolve_workspace_path(path_value: str, default: str = ".") -> str:
    raw_path = path_value if path_value and isinstance(path_value, str) else default
    candidate = os.path.realpath(os.path.abspath(os.path.join(WORKSPACE_ROOT, raw_path)))
    try:
        if os.path.commonpath([WORKSPACE_ROOT, candidate]) != WORKSPACE_ROOT:
            raise ValueError("Acesso fora do workspace nao permitido.")
    except ValueError:
        raise ValueError("Acesso fora do workspace nao permitido.")
    return candidate


def validate_local_command(command: str) -> tuple[bool, str]:
    if not command or not isinstance(command, str):
        return False, "Comando vazio ou invalido."

    normalized = command.lower()
    if re.search(r"(^|[\\/\s'\"`])\.\.([\\/]|$)", normalized):
        return False, "Comando bloqueado por tentar navegar para fora do workspace."

    absolute_paths = re.findall(r"[a-zA-Z]:\\[^\s'\"`|;&]+", command)
    for path_match in absolute_paths:
        try:
            resolve_workspace_path(path_match)
        except ValueError:
            return False, f"Comando bloqueado por referenciar path fora do workspace: {path_match}"

    for pattern, reason in COMMAND_BLOCKLIST:
        if re.search(pattern, normalized):
            return False, f"Comando bloqueado por politica de seguranca: {reason}."

    return True, ""
