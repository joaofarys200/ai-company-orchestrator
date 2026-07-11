from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from agents import tools as ag_tools


PlanRequester = Callable[[str, str | None], Awaitable[str] | str | dict[str, Any]]
FileCallback = Callable[[str, str], None]
LogCallback = Callable[[str], None]

PROJECT_ROOT_REL = "workspace/projects"
MAX_FILES = 40
MAX_FILE_BYTES = 250_000
PROJECT_COMMAND_DENYLIST = [
    r"\bnpm\s+install\b",
    r"\bpnpm\s+install\b",
    r"\byarn\s+install\b",
    r"\bpython\s+-m\s+http\.server\b",
    r"\bhttp-server\b",
    r"\bnpm\s+run\s+dev\b",
    r"\bvite\b",
    r"\bflask\s+run\b",
    r"\buvicorn\b",
]

_preview_processes: list[subprocess.Popen] = []


class ProjectBuilderError(Exception):
    pass


@dataclass
class ProjectFile:
    path: str
    content: str


@dataclass
class ProjectPlan:
    project_name: str
    stack: str
    files: list[ProjectFile]
    validation_commands: list[str] = field(default_factory=list)
    preview_command: str = ""


@dataclass
class CommandResult:
    command: str
    ok: bool
    output: str


@dataclass
class SkippedCommand:
    command: str
    reason: str


@dataclass
class ProjectBuildResult:
    project_name: str
    project_dir: str
    project_rel_dir: str
    files_created: list[str]
    commands_executed: list[CommandResult]
    commands_skipped: list[SkippedCommand]
    preview_url: str = ""
    preview_started: bool = False
    obsidian_used: bool = False

    def report(self) -> str:
        files = "\n".join(f"- {path}" for path in self.files_created) or "- nenhum"
        executed = "\n".join(
            f"- {'OK' if item.ok else 'FALHOU'}: {item.command}" for item in self.commands_executed
        ) or "- nenhum"
        skipped = "\n".join(
            f"- {item.command}: {item.reason}" for item in self.commands_skipped
        ) or "- nenhum"
        preview = self.preview_url if self.preview_url else "nao iniciado"
        return (
            "[OK] Projeto criado pelo Project Builder.\n"
            f"Pasta: {self.project_rel_dir}\n"
            f"Preview: {preview}\n"
            f"Obsidian usado: {'sim' if self.obsidian_used else 'nao'}\n\n"
            "Ficheiros criados:\n"
            f"{files}\n\n"
            "Comandos executados:\n"
            f"{executed}\n\n"
            "Comandos ignorados:\n"
            f"{skipped}"
        )


def normalize_prompt(text: str) -> str:
    replacements = str.maketrans({
        "á": "a", "à": "a", "â": "a", "ã": "a",
        "é": "e", "ê": "e",
        "í": "i",
        "ó": "o", "ô": "o", "õ": "o",
        "ú": "u",
        "ç": "c",
    })
    return (text or "").lower().translate(replacements)


def is_project_creation_request(prompt: str) -> bool:
    text = normalize_prompt(prompt)
    if not text.strip():
        return False
    if any(term in text for term in ["obsidian", "vault", "cofre"]):
        return False
    action = any(term in text for term in [
        "cria", "criar", "gera", "gerar", "faz", "fazer", "desenvolve",
        "desenvolver", "constroi", "construir", "build", "create", "generate",
    ])
    target = any(term in text for term in [
        "ficheiro", "arquivo", ".txt", ".html", ".css", ".js", ".py",
        "pagina", "site", "website", "app", "aplicacao", "projeto",
        "frontend", "backend", "api", "dashboard", "tarefas", "todo",
    ])
    return action and target


def slugify(value: str, fallback: str = "project") -> str:
    normalized = normalize_prompt(value)
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return (slug or fallback)[:64].strip("-") or fallback


def unique_project_rel_dir(project_name: str, projects_root_rel: str = PROJECT_ROOT_REL) -> str:
    base_slug = slugify(project_name)
    root_abs = ag_tools.resolve_workspace_path(projects_root_rel)
    os.makedirs(root_abs, exist_ok=True)
    candidate = base_slug
    counter = 2
    while os.path.exists(os.path.join(root_abs, candidate)):
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return f"{projects_root_rel.rstrip('/')}/{candidate}".replace("\\", "/")


def extract_json_object(text: str) -> dict[str, Any]:
    if isinstance(text, dict):
        return text
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ProjectBuilderError("O LLM nao devolveu um objeto JSON.")
        parsed = json.loads(raw[start:end + 1])
    if not isinstance(parsed, dict):
        raise ProjectBuilderError("O plano JSON tem de ser um objeto.")
    return parsed


def _safe_relative_file_path(path_value: str) -> str:
    path = str(path_value or "").replace("\\", "/").strip().lstrip("/")
    if not path:
        raise ProjectBuilderError("Ficheiro sem path.")
    if re.match(r"^[a-zA-Z]:", path) or path.startswith("../") or "/../" in path or path == "..":
        raise ProjectBuilderError(f"Path recusado fora do projeto: {path_value}")
    lowered = path.lower()
    if lowered.startswith("obsidian_vault/") or "/obsidian_vault/" in lowered:
        raise ProjectBuilderError(f"Path recusado dentro do Obsidian: {path_value}")
    return path


def validate_project_plan(data: dict[str, Any]) -> ProjectPlan:
    project_name = str(data.get("project_name") or data.get("name") or "").strip()
    if not project_name:
        raise ProjectBuilderError("Plano sem project_name.")
    stack = str(data.get("stack") or "").strip() or "static"
    raw_files = data.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ProjectBuilderError("Plano sem lista de ficheiros.")
    if len(raw_files) > MAX_FILES:
        raise ProjectBuilderError(f"Plano tem ficheiros a mais ({len(raw_files)}>{MAX_FILES}).")

    files: list[ProjectFile] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise ProjectBuilderError("Cada ficheiro do plano tem de ser um objeto.")
        path = _safe_relative_file_path(item.get("path") or item.get("filename"))
        content = item.get("content")
        if not isinstance(content, str):
            raise ProjectBuilderError(f"Ficheiro sem content string: {path}")
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise ProjectBuilderError(f"Ficheiro excede o tamanho maximo: {path}")
        if path in seen:
            raise ProjectBuilderError(f"Ficheiro duplicado no plano: {path}")
        seen.add(path)
        files.append(ProjectFile(path=path, content=content))

    raw_commands = data.get("validation_commands") or []
    if isinstance(raw_commands, str):
        raw_commands = [raw_commands]
    if not isinstance(raw_commands, list):
        raise ProjectBuilderError("validation_commands tem de ser lista.")
    validation_commands = [str(command).strip() for command in raw_commands if str(command).strip()]

    preview_command = str(data.get("preview_command") or "").strip()
    return ProjectPlan(
        project_name=project_name,
        stack=stack,
        files=files,
        validation_commands=validation_commands,
        preview_command=preview_command,
    )


def _assert_project_child(project_rel_dir: str, relative_file: str) -> str:
    project_abs = ag_tools.resolve_workspace_path(project_rel_dir)
    file_abs = ag_tools.resolve_workspace_path(f"{project_rel_dir}/{relative_file}")
    if os.path.commonpath([project_abs, file_abs]) != project_abs:
        raise ProjectBuilderError(f"Ficheiro fora da pasta do projeto: {relative_file}")
    return file_abs


def _command_is_project_safe(command: str) -> tuple[bool, str]:
    allowed, reason = ag_tools.validate_local_command(command)
    if not allowed:
        return False, reason
    lowered = normalize_prompt(command)
    for pattern in PROJECT_COMMAND_DENYLIST:
        if re.search(pattern, lowered):
            return False, "comando long-running, instalacao ou preview nao permitido como validacao"
    if "obsidian_vault" in lowered:
        return False, "comando referencia Obsidian"
    return True, ""


def _result_ok(output: str) -> bool:
    text = normalize_prompt(output)
    if any(marker in text for marker in ["erro de seguranca", "erro ao executar", "excedeu o tempo limite"]):
        return False
    match = re.search(r"c[oó]digo\s+(\d+)", text)
    if match and match.group(1) != "0":
        return False
    return True


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _preview_python_executable() -> str:
    if os.name != "nt":
        return sys.executable
    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return sys.executable


def _project_has_previewable_file(project_dir: str) -> bool:
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [item for item in dirs if item not in {"node_modules", ".git", "__pycache__"}]
        if any(filename.lower() == "index.html" for filename in files):
            return True
    return False


def start_static_preview(project_dir: str) -> tuple[bool, str]:
    if not _project_has_previewable_file(project_dir):
        return False, ""
    port = _find_free_port()
    command = [
        _preview_python_executable(),
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
        "--directory",
        project_dir,
    ]
    kwargs: dict[str, Any] = {
        "cwd": project_dir,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        flags = 0
        for flag_name in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
            flags |= int(getattr(subprocess, flag_name, 0))
        if flags:
            kwargs["creationflags"] = flags
    else:
        kwargs["start_new_session"] = True
    process = subprocess.Popen(command, **kwargs)
    _preview_processes.append(process)
    return True, f"http://127.0.0.1:{port}/"


async def request_project_plan_from_ollama(prompt: str, correction: str | None = None) -> str:
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    correction_text = f"\nCorrige o erro anterior: {correction}" if correction else ""
    system = (
        "Es um gerador de planos de projeto. Responde apenas JSON valido, sem markdown. "
        "Nao chames ferramentas. Nao uses Obsidian. Nao escrevas ficheiros .md para codigo. "
        "Todos os paths dos ficheiros devem ser relativos a pasta do projeto, como index.html, src/app.js ou hello.txt."
    )
    user = (
        "Cria um plano JSON com esta estrutura exata:\n"
        "{"
        "\"project_name\":\"nome curto\","
        "\"stack\":\"stack escolhida\","
        "\"files\":[{\"path\":\"...\",\"content\":\"conteudo completo\"}],"
        "\"validation_commands\":[\"comandos seguros e finitos\"],"
        "\"preview_command\":\"comando sugerido, se aplicavel\""
        "}\n"
        "Regras: comandos de validacao devem terminar rapidamente; se for uma pagina estatica usa "
        "\"Get-ChildItem -LiteralPath workspace/projects\" como validacao. "
        f"Pedido do utilizador: {prompt}{correction_text}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "top_p": 0.8},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post("http://localhost:11434/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()
    return str((data.get("message") or {}).get("content") or "")


async def _maybe_await_plan(requester: PlanRequester, prompt: str, correction: str | None) -> str | dict[str, Any]:
    result = requester(prompt, correction)
    if asyncio.iscoroutine(result):
        return await result
    return result


async def get_valid_project_plan(prompt: str, requester: PlanRequester | None = None) -> ProjectPlan:
    selected_requester = requester or request_project_plan_from_ollama
    first_raw = await _maybe_await_plan(selected_requester, prompt, None)
    try:
        return validate_project_plan(extract_json_object(first_raw))
    except Exception as first_error:
        corrected_raw = await _maybe_await_plan(selected_requester, prompt, str(first_error))
        try:
            return validate_project_plan(extract_json_object(corrected_raw))
        except Exception as second_error:
            raise ProjectBuilderError(
                f"Plano JSON invalido depois de uma correcao. Primeiro erro: {first_error}. Segundo erro: {second_error}"
            ) from second_error


async def build_project(
    prompt: str,
    plan_requester: PlanRequester | None = None,
    projects_root_rel: str = PROJECT_ROOT_REL,
    start_preview: bool = True,
    on_file: FileCallback | None = None,
    on_log: LogCallback | None = None,
) -> ProjectBuildResult:
    if not is_project_creation_request(prompt):
        raise ProjectBuilderError("Pedido nao parece ser criacao de projeto.")

    plan = await get_valid_project_plan(prompt, plan_requester)
    project_rel_dir = unique_project_rel_dir(plan.project_name, projects_root_rel)
    project_dir = ag_tools.resolve_workspace_path(project_rel_dir)
    os.makedirs(project_dir, exist_ok=False)
    if on_log:
        on_log(f"[ProjectBuilder] Projeto: {project_rel_dir}\n")

    files_created: list[str] = []
    for file_item in plan.files:
        safe_path = _safe_relative_file_path(file_item.path)
        abs_path = _assert_project_child(project_rel_dir, safe_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        Path(abs_path).write_text(file_item.content, encoding="utf-8")
        rel_path = f"{project_rel_dir}/{safe_path}".replace("\\", "/")
        files_created.append(rel_path)
        if on_file:
            on_file(rel_path, file_item.content)

    executed: list[CommandResult] = []
    skipped: list[SkippedCommand] = []
    for command in plan.validation_commands:
        safe, reason = _command_is_project_safe(command)
        if not safe:
            skipped.append(SkippedCommand(command=command, reason=reason))
            continue
        output = await ag_tools.run_local_command(command)
        executed.append(CommandResult(command=command, ok=_result_ok(output), output=output[:4000]))

    preview_started = False
    preview_url = ""
    if start_preview:
        preview_started, preview_url = start_static_preview(project_dir)

    return ProjectBuildResult(
        project_name=plan.project_name,
        project_dir=project_dir,
        project_rel_dir=project_rel_dir,
        files_created=files_created,
        commands_executed=executed,
        commands_skipped=skipped,
        preview_url=preview_url,
        preview_started=preview_started,
        obsidian_used=False,
    )
