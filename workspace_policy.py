from __future__ import annotations

import os
import re
import shlex


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

_BLOCKED_SHELL_EXECUTABLES = {
    "cmd",
    "powershell",
    "pwsh",
    "wscript",
    "cscript",
    "mshta",
    "rundll32",
    "regsvr32",
    "certutil",
    "bitsadmin",
    "bash",
    "sh",
    "zsh",
    "fish",
}

_SHELL_META_RE = re.compile(r"([|;&><`]|(\$\()|(\$\{)|\r|\n|\x00)")


def resolve_workspace_path(path_value: str, default: str = ".") -> str:
    raw_path = path_value if path_value and isinstance(path_value, str) else default
    candidate = os.path.realpath(os.path.abspath(os.path.join(WORKSPACE_ROOT, raw_path)))
    try:
        if os.path.commonpath([WORKSPACE_ROOT, candidate]) != WORKSPACE_ROOT:
            raise ValueError("Acesso fora do workspace nao permitido.")
    except ValueError:
        raise ValueError("Acesso fora do workspace nao permitido.")
    return candidate


def _normalize_exe_stem(token: str) -> str:
    cleaned = token.strip().strip("\"'")
    base = os.path.basename(cleaned).lower()
    for ext in (".exe", ".cmd", ".bat", ".ps1", ".com"):
        if base.endswith(ext):
            base = base[: -len(ext)]
            break
    return base


def validate_local_command(command: str) -> tuple[bool, str]:
    if not command or not isinstance(command, str):
        return False, "Comando vazio ou invalido."

    stripped = command.strip()
    if not stripped:
        return False, "Comando vazio ou invalido."

    if _SHELL_META_RE.search(stripped):
        return (
            False,
            "Comando bloqueado por conter operadores ou metacaracteres de shell.",
        )

    try:
        tokens = shlex.split(stripped, posix=(os.name != "nt"))
    except ValueError:
        return False, "Comando bloqueado por aspas nao fechadas."

    if not tokens:
        return False, "Comando vazio ou invalido."

    exe_stem = _normalize_exe_stem(tokens[0])
    if exe_stem in _BLOCKED_SHELL_EXECUTABLES:
        return (
            False,
            f"Comando bloqueado por invocar interpretador de shell '{exe_stem}'.",
        )

    if exe_stem in ("python", "python3"):
        for arg in tokens[1:]:
            arg_clean = arg.strip().strip("\"'").lower()
            if arg_clean == "-c" or arg_clean.startswith("-c="):
                return (
                    False,
                    "Comando bloqueado por execucao inline 'python -c'.",
                )

    normalized = stripped.lower()
    if re.search(r"(^|[\\/\s'\"`])\.\.([\\/]|$)", normalized):
        return False, "Comando bloqueado por tentar navegar para fora do workspace."

    for raw_tok in tokens:
        tok = raw_tok.strip("\"'")
        if re.match(r"^[a-zA-Z]:\\", tok):
            try:
                resolve_workspace_path(tok)
            except ValueError:
                return (
                    False,
                    f"Comando bloqueado por referenciar path fora do workspace: {tok}",
                )

    for pattern, reason in COMMAND_BLOCKLIST:
        if re.search(pattern, normalized):
            return False, f"Comando bloqueado por politica de seguranca: {reason}."

    return True, ""
