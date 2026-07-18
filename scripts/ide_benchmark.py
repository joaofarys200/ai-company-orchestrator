from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import tracemalloc
import uuid
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.orchestrator.project_builder import build_project
from intelligence.coding_session import CodingSessionError, CodingSessionService
from intelligence.project_context import HASH_CHUNK_BYTES, MAX_VIEW_FILE_BYTES, ProjectContextError, ProjectContextService
from intelligence.project_intelligence import MAX_AST_FILE_BYTES


REPORT_PATH = REPO_ROOT / "logs" / "ide_benchmark" / "benchmark_latest.json"
SCRATCH_ROOT = REPO_ROOT / "scratch"

VALID_ADD_TASK = """function addTask() {
  const input = document.getElementById('taskInput');
  const list = document.getElementById('taskList');
  const task = input.value.trim();
  if (!task) return;
  const li = document.createElement('li');
  li.textContent = task;
  list.appendChild(li);
  input.value = '';
}"""

INVALID_ADD_TASK = """function addTask( {
  const input = document.getElementById('taskInput');
  return input.value;
}"""


class BenchmarkFailure(AssertionError):
    def __init__(self, message: str, category: str = "IDE"):
        super().__init__(message)
        self.category = category


def require(condition: bool, message: str, category: str = "IDE") -> None:
    if not condition:
        raise BenchmarkFailure(message, category)


def require_executable(name: str) -> None:
    require(shutil.which(name) is not None, f"Dependencia de ambiente ausente: {name}", "ENVIRONMENT")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def changed_bytes(old: str, new: str) -> int:
    old_bytes = old.encode("utf-8")
    new_bytes = new.encode("utf-8")
    shared = sum(1 for left, right in zip(old_bytes, new_bytes) if left == right)
    return max(len(old_bytes), len(new_bytes)) - shared


def new_metrics(test_id: str, name: str) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "name": name,
        "result": "RUNNING",
        "duration_seconds": 0.0,
        "files_read": 0,
        "files_changed": [],
        "bytes_modified": 0,
        "diff_size_bytes": 0,
        "commands_executed": [],
        "exit_codes": [],
        "rollback_executed": False,
        "final_state": "",
        "error": None,
        "failure_category": None,
        "trace": None,
        "peak_memory_bytes": 0,
        "details": {},
    }


def record_project_reads(metrics: dict[str, Any], projects: ProjectContextService, project_id: str) -> None:
    metrics["files_read"] = len(projects.read_project_files(project_id))


def record_session(metrics: dict[str, Any], session) -> None:
    metrics["files_changed"] = list(session.affected_files)
    metrics["bytes_modified"] = sum(
        changed_bytes(change.get("previous_excerpt", ""), change.get("proposed_excerpt", ""))
        for change in session.proposed_changes
    )
    metrics["diff_size_bytes"] = sum(
        len(change.get("unified_diff", "").encode("utf-8")) for change in session.proposed_changes
    )
    metrics["commands_executed"] = [result.get("command") for result in session.validation_results]
    metrics["exit_codes"] = [result.get("exit_code") for result in session.validation_results]
    metrics["final_state"] = session.status
    metrics["details"]["validation_results"] = list(session.validation_results)
    metrics["details"]["checkpoint_type"] = session.checkpoint.get("type") if session.checkpoint else None
    metrics["details"]["checkpoint_strategy"] = session.checkpoint.get("strategy") if session.checkpoint else None
    metrics["details"]["checkpoint_created"] = session.checkpoint_created
    metrics["details"]["primary_error"] = session.primary_error
    metrics["details"]["rollback_error"] = session.rollback_error
    metrics["details"]["rollback_attempted"] = session.rollback_attempted
    metrics["details"]["rollback_succeeded"] = session.rollback_succeeded


def rollback_session_if_needed(
    sessions: CodingSessionService,
    project_id: str,
    session,
) -> tuple[Any, bool]:
    if not session.checkpoint or not session.checkpoint_created:
        return session, False
    if session.status in {"ROLLED_BACK", "ERROR_ROLLED_BACK"} or session.rollback_succeeded:
        return session, False
    has_changes = bool(session.applied_changes) or session.writes_started
    state_requires_rollback = session.status in {"SUCCEEDED", "VALIDATION_FAILED", "APPLYING", "ROLLBACK_FAILED"}
    if not has_changes and not state_requires_rollback:
        return session, False
    return sessions.rollback_session(project_id, session.session_id, confirmed=True), True


def session_primary_error_message(session) -> str:
    if isinstance(session.primary_error, dict) and session.primary_error.get("message"):
        return str(session.primary_error["message"])
    return "; ".join(session.errors) if session.errors else f"estado {session.status}"


def write_html_fixture(workspace: Path, project_id: str = "task-app") -> tuple[ProjectContextService, CodingSessionService, Path]:
    root = workspace / "workspace" / "projects" / project_id
    root.mkdir(parents=True)
    (root / "index.html").write_text(
        "<!doctype html>\n<input id=\"taskInput\"><button onclick=\"addTask()\">Add</button>\n<script src=\"app.js\"></script>\n",
        encoding="utf-8",
    )
    (root / "app.js").write_text(
        "function addTask() {\n"
        "  const input = document.getElementById('taskInput');\n"
        "  const list = document.getElementById('taskList');\n"
        "  if (input.value) {\n"
        "    const li = document.createElement('li');\n"
        "    li.textContent = input.value;\n"
        "    list.appendChild(li);\n"
        "    input.value = '';\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )
    projects = ProjectContextService(workspace_root=str(workspace))
    projects.index_project(project_id)
    return projects, CodingSessionService(projects), root


def add_task_change(code: str) -> list[dict[str, Any]]:
    return [{
        "file": "app.js",
        "operation": "replace_symbol",
        "symbol": "addTask",
        "new_code": code,
        "reason": "Ignorar input vazio depois de trim.",
    }]


def run_i001(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("node")
    projects, sessions, root = write_html_fixture(workspace)
    before_app = (root / "app.js").read_bytes()
    before_index = (root / "index.html").read_bytes()
    context = projects.open_project("task-app")
    definitions = projects.locate_symbol("task-app", "addTask")
    references = projects.find_references("task-app", "addTask")
    require(context.root_path == os.path.realpath(root), "ProjectContext tem root incorreto.")
    require("HTML/JavaScript" in context.stack, "Stack HTML/JavaScript nao detetada.")
    require(any(item["file"] == "app.js" for item in definitions), "Simbolo addTask nao localizado.")
    require(any(item["file"] == "index.html" for item in references["references"]), "Referencia HTML nao localizada.")
    record_project_reads(metrics, projects, "task-app")

    session = sessions.create_session("task-app", "Ignorar input vazio", add_task_change(VALID_ADD_TASK))
    require((root / "app.js").read_bytes() == before_app, "O ficheiro mudou antes da confirmacao.")
    require(bool(session.change_plan), "Plano estruturado nao criado.")
    require(bool(session.proposed_changes[0]["unified_diff"]), "Diff nao gerado antes da escrita.")
    applied = sessions.apply_session("task-app", session.session_id)
    record_session(metrics, applied)
    require(bool(applied.checkpoint), "Checkpoint nao criado.")
    require(applied.status == "SUCCEEDED", f"Sessao terminou em {applied.status}.")
    require(any(item["exit_code"] == 0 for item in applied.validation_results), "Nenhuma validacao passou.")
    restored = sessions.rollback_session("task-app", session.session_id, confirmed=True)
    metrics["rollback_executed"] = True
    metrics["final_state"] = restored.status
    require((root / "app.js").read_bytes() == before_app, "Rollback nao restaurou app.js.")
    require((root / "index.html").read_bytes() == before_index, "Ficheiro nao relacionado foi alterado.")


def run_i002(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("node")
    projects, sessions, root = write_html_fixture(workspace)
    before = (root / "app.js").read_bytes()
    record_project_reads(metrics, projects, "task-app")
    session = sessions.create_session("task-app", "Introduzir erro sintatico", add_task_change(INVALID_ADD_TASK))
    failed = sessions.apply_session("task-app", session.session_id)
    record_session(metrics, failed)
    require((root / "app.js").read_bytes() != before, "Patch invalido nao chegou a ser aplicado.")
    require(failed.status == "VALIDATION_FAILED", f"Falso estado de sucesso: {failed.status}.")
    require(any(code not in {0, None} for code in metrics["exit_codes"]), "Validacao nao detetou o erro sintatico.")
    restored = sessions.rollback_session("task-app", session.session_id, confirmed=True)
    metrics["rollback_executed"] = True
    metrics["final_state"] = restored.status
    require((root / "app.js").read_bytes() == before, "Rollback nao restaurou bytes originais.")


def run_i003(metrics: dict[str, Any], workspace: Path) -> None:
    projects, sessions, root = write_html_fixture(workspace)
    attempts = [
        "../outside.js",
        str((workspace / "absolute.js").resolve()),
        "obsidian_vault/app.js",
        "nested/../../outside.js",
    ]
    blocked = []
    for path in attempts:
        try:
            sessions.create_session("task-app", f"Bloquear {path}", [{
                "file": path,
                "operation": "create_file",
                "new_code": "console.log('blocked');",
                "reason": "Path escape benchmark.",
            }])
        except CodingSessionError:
            blocked.append(path)
    metrics["files_read"] = len(projects.read_project_files("task-app"))
    metrics["details"]["blocked_paths"] = blocked
    metrics["final_state"] = "BLOCKED"
    require(len(blocked) == len(attempts), f"Paths nao bloqueados: {set(attempts) - set(blocked)}")
    require(not (workspace / "absolute.js").exists(), "Foi criado ficheiro fora do projeto.")
    require("obsidian" not in str(root).lower(), "Fixture usou Obsidian.", "FIXTURE")


def run_i004(metrics: dict[str, Any], workspace: Path) -> None:
    projects, sessions, root = write_html_fixture(workspace)
    session = sessions.create_session("task-app", "Plano concorrente stale", add_task_change(VALID_ADD_TASK))
    with (root / "app.js").open("a", encoding="utf-8") as handle:
        handle.write("// external mutation\n")
    try:
        sessions.apply_session("task-app", session.session_id)
    except CodingSessionError as exc:
        metrics["details"]["blocked_reason"] = str(exc)
    else:
        raise BenchmarkFailure("Aplicacao baseada em indice stale nao foi bloqueada.")
    metrics["files_read"] = len(projects.read_project_files("task-app"))
    metrics["files_changed"] = ["app.js"]
    metrics["final_state"] = "BLOCKED_STALE"
    require(session.status == "PROPOSED", "Sessao stale mudou de estado apesar do bloqueio.")


def run_i005(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("python")
    root = workspace / "workspace" / "projects" / "python-multi"
    (root / "package").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "package" / "__init__.py").write_text("", encoding="utf-8")
    (root / "package" / "math_utils.py").write_text("def increment(value):\n    return value + 1\n", encoding="utf-8")
    (root / "package" / "service.py").write_text("from .math_utils import increment\n\ndef run(value):\n    return increment(value)\n", encoding="utf-8")
    (root / "main.py").write_text("from package.service import run\n\nprint(run(1))\n", encoding="utf-8")
    (root / "tests" / "test_math_utils.py").write_text(
        "from package.math_utils import increment\n\ndef test_increment():\n    assert increment(1) == 3\n",
        encoding="utf-8",
    )
    projects = ProjectContextService(workspace_root=str(workspace))
    context = projects.index_project("python-multi")
    sessions = CodingSessionService(projects)
    before = (root / "package" / "math_utils.py").read_bytes()
    require("Python" in context.stack, "Stack Python nao detetada.")
    require("main.py" in context.entrypoints and "." in context.source_roots, "Entrypoint/source root Python incorretos.")
    require(projects.locate_symbol("python-multi", "increment"), "Simbolo Python nao localizado.")
    refs = projects.find_references("python-multi", "increment")
    require(any(item["file"] == "package/service.py" for item in refs["references"]), "Referencia Python nao localizada.")
    require(any(item["kind"] == "test" for item in context.suggested_commands), "pytest configurado nao foi sugerido.")
    record_project_reads(metrics, projects, "python-multi")
    session = sessions.create_session("python-multi", "Incrementar por dois", [{
        "file": "package/math_utils.py",
        "operation": "replace_symbol",
        "symbol": "increment",
        "new_code": "def increment(value):\n    return value + 2",
        "reason": "Atualizar incremento.",
    }])
    applied = sessions.apply_session("python-multi", session.session_id)
    record_session(metrics, applied)
    if applied.status != "SUCCEEDED":
        restored, rollback_executed = rollback_session_if_needed(sessions, "python-multi", applied)
        record_session(metrics, restored)
        metrics["rollback_executed"] = rollback_executed
        metrics["final_state"] = restored.status
        require(False, f"Patch Python falhou: {session_primary_error_message(applied)}")
    require(any("py_compile" in command for command in metrics["commands_executed"]), "py_compile nao executado.")
    require(any("pytest" in command for command in metrics["commands_executed"]), "pytest nao executado.")
    restored, rollback_executed = rollback_session_if_needed(sessions, "python-multi", applied)
    record_session(metrics, restored)
    metrics["rollback_executed"] = rollback_executed
    metrics["final_state"] = restored.status
    require(rollback_executed, "Rollback Python nao foi executado.")
    require((root / "package" / "math_utils.py").read_bytes() == before, "Rollback Python falhou.")


def run_i006(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("node")
    require_executable("npm")
    root = workspace / "workspace" / "projects" / "node-multi"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    package = {
        "name": "node-multi",
        "main": "src/index.js",
        "scripts": {
            "lint": "node --check src/math.js",
            "build": "node --check src/index.js",
            "test": "node tests/test.js",
        },
    }
    (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
    (root / "src" / "math.js").write_text("function add(a, b) { return a + b; }\nmodule.exports = { add };\n", encoding="utf-8")
    (root / "src" / "index.js").write_text("const { add } = require('./math');\nconsole.log(add(1, 2));\n", encoding="utf-8")
    (root / "tests" / "test.js").write_text("const { add } = require('../src/math');\nif (add(1, 2) !== 4) process.exit(1);\n", encoding="utf-8")
    projects = ProjectContextService(workspace_root=str(workspace))
    context = projects.index_project("node-multi")
    sessions = CodingSessionService(projects)
    before = (root / "src" / "math.js").read_bytes()
    require("Node" in context.stack, "Stack Node nao detetada.")
    require({"lint", "build", "test"}.issubset(context.package_scripts), "Scripts Node nao descobertos.")
    record_project_reads(metrics, projects, "node-multi")
    session = sessions.create_session("node-multi", "Alterar add", [{
        "file": "src/math.js",
        "operation": "replace_symbol",
        "symbol": "add",
        "new_code": "function add(a, b) { return a + b + 1; }",
        "reason": "Alterar comportamento de add.",
    }])
    require(session.affected_files == ["src/math.js"], "affected_files Node incorretos.")
    applied = sessions.apply_session("node-multi", session.session_id)
    record_session(metrics, applied)
    require(applied.status == "SUCCEEDED", f"Patch Node falhou: {applied.errors}")
    expected = {"npm run lint", "npm run build", "npm run test"}
    require(expected.issubset(set(metrics["commands_executed"])), "Validacoes package.json incompletas.")
    restored = sessions.rollback_session("node-multi", session.session_id, confirmed=True)
    metrics["rollback_executed"] = True
    metrics["final_state"] = restored.status
    require((root / "src" / "math.js").read_bytes() == before, "Rollback Node falhou.")


def run_i007(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("node")
    projects, sessions, root = write_html_fixture(workspace, "multi-change")
    (root / "view.js").write_text("function label(value) { return `Task: ${value}`; }\n", encoding="utf-8")
    projects.index_project("multi-change")
    originals = {name: (root / name).read_bytes() for name in ("app.js", "view.js", "index.html")}
    changes = add_task_change(VALID_ADD_TASK) + [{
        "file": "view.js",
        "operation": "replace_symbol",
        "symbol": "label",
        "new_code": "function label(value) { return `Todo: ${value}`; }",
        "reason": "Alinhar label.",
    }]
    session = sessions.create_session("multi-change", "Alterar tarefa e label", changes)
    require(set(session.affected_files) == {"app.js", "view.js"}, "affected_files multi-ficheiro incorretos.")
    require(len(session.proposed_changes) == 2 and all(item["unified_diff"] for item in session.proposed_changes), "Diffs individuais ausentes.")
    applied = sessions.apply_session("multi-change", session.session_id)
    record_session(metrics, applied)
    require(applied.status == "SUCCEEDED", f"Aplicacao multi-ficheiro falhou: {applied.errors}")
    require(set(applied.checkpoint["files"]) == {"app.js", "view.js"}, "Checkpoint nao cobre todos os ficheiros.")
    require(bool(applied.validation_results), "Validacoes nao executadas apos aplicacao completa.")
    sessions.rollback_session("multi-change", session.session_id, confirmed=True)

    projects.index_project("multi-change")
    injected = sessions.create_session("multi-change", "Falhar no segundo patch", changes)
    original_apply = sessions._apply_change
    calls = {"count": 0}

    def fail_second(active_session, active_root, change):
        calls["count"] += 1
        if calls["count"] == 2:
            raise CodingSessionError("Falha injetada no segundo patch.")
        return original_apply(active_session, active_root, change)

    sessions._apply_change = fail_second
    failed = sessions.apply_session("multi-change", injected.session_id)
    metrics["rollback_executed"] = failed.status == "ERROR_ROLLED_BACK"
    metrics["final_state"] = failed.status
    metrics["details"]["injected_failure"] = list(failed.errors)
    require(failed.status == "ERROR_ROLLED_BACK", f"Falha parcial nao acionou rollback atomico: {failed.status}")
    require(not failed.validation_results, "Validacoes executaram antes da aplicacao completa.")
    require(all((root / name).read_bytes() == data for name, data in originals.items()), "Estado parcial permaneceu apos falha.")


def run_i008(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("node")
    root = workspace / "workspace" / "projects" / "large-file"
    root.mkdir(parents=True)
    prefix = "\n".join(f"// generated context line {index}" for index in range(8000)) + "\n"
    target = "function compute(value) { return value + 1; }\n"
    suffix = "\n".join(f"// trailing context line {index}" for index in range(8000)) + "\n"
    (root / "app.js").write_text(prefix + target + suffix, encoding="utf-8")
    (root / "index.html").write_text("<script src=\"app.js\"></script>", encoding="utf-8")
    huge_content = "// ast-only context\n" * ((MAX_AST_FILE_BYTES // 20) + 1000)
    (root / "huge.js").write_text(huge_content, encoding="utf-8")
    projects = ProjectContextService(workspace_root=str(workspace))
    context = projects.index_project("large-file")
    graph = projects.load_index("large-file")
    displayed_files = projects.read_project_files("large-file")
    sessions = CodingSessionService(projects)
    before = (root / "app.js").read_bytes()
    before_sha256 = sha256(root / "app.js")
    unrelated_before_sha256 = sha256(root / "index.html")
    huge_before_sha256 = sha256(root / "huge.js")
    app_metadata = context.ast_index["files"]["app.js"]
    huge_metadata = context.ast_index["files"]["huge.js"]
    record_project_reads(metrics, projects, "large-file")
    metrics["details"].update({
        "source_size_bytes": len(before),
        "display_limit_bytes": MAX_VIEW_FILE_BYTES,
        "ast_limit_bytes": MAX_AST_FILE_BYTES,
        "transaction_limit_bytes": projects.max_transaction_file_bytes,
        "hash_chunk_bytes": HASH_CHUNK_BYTES,
        "display_content_available": "app.js" in displayed_files,
        "hash_available": app_metadata["hash_available"],
        "source_hash": app_metadata["source_hash"],
        "ast_indexed": app_metadata["content_indexed"] and "app.js" in graph,
        "above_ast_limit": {
            "file": "huge.js",
            "size_bytes": huge_metadata["size_bytes"],
            "display_content_available": "huge.js" in displayed_files,
            "hash_available": huge_metadata["hash_available"],
            "source_hash": huge_metadata["source_hash"],
            "ast_indexed": huge_metadata["content_indexed"] or "huge.js" in graph,
        },
        "original_sha256": before_sha256,
        "unrelated_sha256_before": unrelated_before_sha256,
    })
    require(len(before) > MAX_VIEW_FILE_BYTES, "Fixture nao excede o limite de visualizacao.", "FIXTURE")
    require("app.js" not in displayed_files, "Ficheiro grande apareceu integralmente na UI.")
    require(app_metadata["hash_available"] and app_metadata["source_hash"] == before_sha256, "Hash transacional indisponivel.")
    require(app_metadata["content_indexed"] and "app.js" in graph, "Ficheiro abaixo de 2 MiB nao entrou no AST.")
    require(huge_metadata["size_bytes"] > MAX_AST_FILE_BYTES, "Fixture AST nao excede 2 MiB.", "FIXTURE")
    require("huge.js" not in displayed_files, "Fixture acima do AST apareceu integralmente na UI.")
    require(huge_metadata["hash_available"] and huge_metadata["source_hash"] == huge_before_sha256, "Hash da fixture acima do AST indisponivel.")
    require(not huge_metadata["content_indexed"] and "huge.js" not in graph, "Fixture acima de 2 MiB entrou no AST.")

    stale_session = sessions.create_session("large-file", "Detetar mutacao stale", [{
        "file": "app.js",
        "operation": "replace_symbol",
        "symbol": "compute",
        "new_code": "function compute(value) { return value + 2; }",
        "reason": "Confirmar stale detection real.",
    }])
    with (root / "app.js").open("ab") as handle:
        handle.write(b"// external stale mutation\r\n")
    try:
        sessions.apply_session("large-file", stale_session.session_id)
    except CodingSessionError as exc:
        metrics["details"]["stale_detection"] = {"blocked": True, "reason": str(exc)}
    else:
        raise BenchmarkFailure("Mutacao stale do ficheiro grande nao foi bloqueada.")
    (root / "app.js").write_bytes(before)
    projects.index_project("large-file")

    session = sessions.create_session("large-file", "Alterar compute localmente", [{
        "file": "app.js",
        "operation": "replace_symbol",
        "symbol": "compute",
        "new_code": "function compute(value) { return value + 2; }",
        "reason": "Alterar apenas compute.",
    }])
    applied = sessions.apply_session("large-file", session.session_id)
    record_session(metrics, applied)
    require(applied.status == "SUCCEEDED", f"Patch em ficheiro grande falhou: {applied.errors}")
    after = (root / "app.js").read_bytes()
    after_sha256 = sha256(root / "app.js")
    unrelated_after_sha256 = sha256(root / "index.html")
    expected_after = before.replace(
        b"function compute(value) { return value + 1; }",
        b"function compute(value) { return value + 2; }",
        1,
    )
    applied_metadata = next(item for item in applied.applied_changes if item["file"] == "app.js")
    diff_lines = session.proposed_changes[0]["unified_diff"].splitlines()
    metrics["details"].update({
        "diff_lines": len(diff_lines),
        "logical_edit_scope": applied_metadata["logical_edit_scope"],
        "physical_write_strategy": applied_metadata["physical_write_strategy"],
        "full_file_logical_rewrite": applied_metadata["full_file_logical_rewrite"],
        "full_file_physical_write": applied_metadata["full_file_physical_write"],
        "resulting_sha256": after_sha256,
        "unrelated_sha256_after_apply": unrelated_after_sha256,
    })
    require(bool(applied.checkpoint), "Checkpoint do ficheiro grande nao foi criado.")
    require(after == expected_after, "Patch alterou bytes fora do simbolo compute.")
    require(applied_metadata["physical_write_strategy"] == "atomic_full_file_replace", "Escrita textual nao foi atomica.")
    require(not applied_metadata["full_file_logical_rewrite"], "Patch localizado foi classificado como rewrite logico total.")
    require(applied_metadata["changed_line_count"] <= 1, "Patch logico alterou linhas excessivas.")
    require(applied_metadata["logical_change_ratio"] < 0.001, "Ratio logico excessivo para alteracao localizada.")
    require(all(item["exit_code"] == 0 for item in applied.validation_results), "Validacao do ficheiro grande falhou.")
    require(unrelated_after_sha256 == unrelated_before_sha256, "Ficheiro nao relacionado mudou durante aplicacao.")
    restored = sessions.rollback_session("large-file", session.session_id, confirmed=True)
    record_session(metrics, restored)
    metrics["rollback_executed"] = True
    metrics["final_state"] = restored.status
    restored_sha256 = sha256(root / "app.js")
    unrelated_restored_sha256 = sha256(root / "index.html")
    metrics["details"]["restored_sha256"] = restored_sha256
    metrics["details"]["unrelated_sha256_after_rollback"] = unrelated_restored_sha256
    require((root / "app.js").read_bytes() == before and restored_sha256 == before_sha256, "Rollback do ficheiro grande falhou.")
    require(unrelated_restored_sha256 == unrelated_before_sha256, "Ficheiro nao relacionado mudou durante rollback.")
    require(len(diff_lines) < 20, f"Diff nao permaneceu localizado: {len(diff_lines)} linhas.")


def run_i009(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("node")
    projects, sessions, root = write_html_fixture(workspace)
    original = (root / "app.js").read_bytes()
    first = sessions.create_session("task-app", "Primeira sessao", add_task_change(VALID_ADD_TASK))
    second = sessions.create_session("task-app", "Segunda sessao", add_task_change("function addTask() { return false; }"))
    applied = sessions.apply_session("task-app", first.session_id)
    record_session(metrics, applied)
    require(applied.status == "SUCCEEDED", "Primeira sessao concorrente falhou.")
    try:
        sessions.apply_session("task-app", second.session_id)
    except CodingSessionError as exc:
        metrics["details"]["conflict"] = str(exc)
    else:
        raise BenchmarkFailure("Segunda sessao stale nao foi bloqueada.")
    restored = sessions.rollback_session("task-app", first.session_id, confirmed=True)
    metrics["rollback_executed"] = True
    metrics["files_read"] = len(projects.read_project_files("task-app"))
    metrics["final_state"] = "CONFLICT_BLOCKED"
    require(restored.status == "ROLLED_BACK" and (root / "app.js").read_bytes() == original, "Estado final concorrente incorreto.")


def run_i010(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("node")
    projects, sessions, root = write_html_fixture(workspace)
    original = (root / "app.js").read_bytes()
    session = sessions.create_session("task-app", "Persistir sessao", add_task_change(VALID_ADD_TASK))
    applied = sessions.apply_session("task-app", session.session_id)
    restarted = CodingSessionService(ProjectContextService(workspace_root=str(workspace)))
    loaded = restarted.load("task-app", session.session_id)
    record_project_reads(metrics, projects, "task-app")
    record_session(metrics, loaded)
    require(loaded.objective == session.objective, "Objetivo nao persistiu.")
    require(loaded.change_plan == applied.change_plan, "Plano nao persistiu.")
    require(loaded.proposed_changes == applied.proposed_changes, "Propostas/hashes nao persistiram.")
    require(loaded.checkpoint == applied.checkpoint, "Checkpoint nao persistiu.")
    require(loaded.validation_results == applied.validation_results, "Resultados de validacao nao persistiram.")
    require(loaded.status == "SUCCEEDED", f"Estado persistido incorreto: {loaded.status}")
    restored = restarted.rollback_session("task-app", session.session_id, confirmed=True)
    metrics["rollback_executed"] = True
    metrics["final_state"] = restored.status
    require((root / "app.js").read_bytes() == original, "Rollback apos restart falhou.")


def run_i011(metrics: dict[str, Any], _workspace: Path) -> None:
    require_executable("node")
    project_name = f"ide-benchmark-{uuid.uuid4().hex[:8]}"
    project_root = REPO_ROOT / "workspace" / "projects" / project_name
    metadata_root = REPO_ROOT / "workspace" / ".jarvis" / "projects" / project_name

    async def requester(_prompt, _correction):
        return {
            "project_name": project_name,
            "stack": "HTML/JavaScript",
            "files": [
                {"path": "index.html", "content": "<script src=\"app.js\"></script>"},
                {"path": "app.js", "content": "function greet(name) { return `Hello ${name}`; }\n"},
            ],
            "validation_commands": [],
            "preview_command": "",
        }

    try:
        result = asyncio.run(build_project(
            "cria um projeto benchmark integrado",
            plan_requester=requester,
            start_preview=False,
        ))
        require(Path(result.project_dir) == project_root, "ProjectBuilder criou projeto em root inesperado.")
        projects = ProjectContextService()
        context = projects.index_project(project_name)
        sessions = CodingSessionService(projects)
        original = (project_root / "app.js").read_bytes()
        require(context.project_id == project_name, "ProjectContext nao abriu projeto criado.")
        require(projects.locate_symbol(project_name, "greet"), "Projeto criado nao foi indexado.")
        session = sessions.create_session(project_name, "Alterar greeting", [{
            "file": "app.js",
            "operation": "replace_symbol",
            "symbol": "greet",
            "new_code": "function greet(name) { return `Hi ${name}`; }",
            "reason": "Alterar saudacao.",
        }])
        applied = sessions.apply_session(project_name, session.session_id)
        record_project_reads(metrics, projects, project_name)
        record_session(metrics, applied)
        require(applied.status == "SUCCEEDED", f"IDE nao editou projeto criado: {applied.errors}")
        restored = sessions.rollback_session(project_name, session.session_id, confirmed=True)
        metrics["rollback_executed"] = True
        metrics["final_state"] = restored.status
        require((project_root / "app.js").read_bytes() == original, "Rollback do projeto criado falhou.")
    finally:
        if project_root.is_dir() and project_root.name.startswith("ide-benchmark-"):
            shutil.rmtree(project_root)
        if metadata_root.is_dir() and metadata_root.name.startswith("ide-benchmark-"):
            shutil.rmtree(metadata_root)


def run_i012(metrics: dict[str, Any], workspace: Path) -> None:
    require_executable("node")
    projects, sessions, root = write_html_fixture(workspace, "stress-app")
    original_app = (root / "app.js").read_bytes()
    original_index = (root / "index.html").read_bytes()
    statuses = []
    checkpoint_ids = []
    commands = []
    exit_codes = []
    total_bytes_modified = 0
    total_diff_size = 0
    for index in range(20):
        projects.index_project("stress-app")
        code = VALID_ADD_TASK.replace("const task =", f"const task =") if index % 2 == 0 else INVALID_ADD_TASK
        session = sessions.create_session("stress-app", f"Stress session {index + 1}", add_task_change(code))
        total_bytes_modified += sum(
            changed_bytes(item["previous_excerpt"], item["proposed_excerpt"])
            for item in session.proposed_changes
        )
        total_diff_size += sum(len(item["unified_diff"].encode("utf-8")) for item in session.proposed_changes)
        applied = sessions.apply_session("stress-app", session.session_id)
        statuses.append(applied.status)
        checkpoint_ids.append(session.session_id if applied.checkpoint else None)
        commands.extend(item["command"] for item in applied.validation_results)
        exit_codes.extend(item["exit_code"] for item in applied.validation_results)
        if index % 2 == 0:
            require(applied.status == "SUCCEEDED", f"Sessao valida {index + 1} falhou.")
        else:
            require(applied.status == "VALIDATION_FAILED", f"Sessao invalida {index + 1} teve estado {applied.status}.")
        sessions.rollback_session("stress-app", session.session_id, confirmed=True)
        require((root / "app.js").read_bytes() == original_app, f"Corrupcao apos sessao {index + 1}.")
        require((root / "index.html").read_bytes() == original_index, f"Ficheiro externo ao patch mudou na sessao {index + 1}.")
    metrics["files_read"] = len(projects.read_project_files("stress-app"))
    metrics["files_changed"] = ["app.js"]
    metrics["bytes_modified"] = total_bytes_modified
    metrics["diff_size_bytes"] = total_diff_size
    metrics["commands_executed"] = commands
    metrics["exit_codes"] = exit_codes
    metrics["rollback_executed"] = True
    metrics["final_state"] = "DETERMINISTIC_ORIGINAL"
    metrics["details"] = {
        "sessions": 20,
        "succeeded": statuses.count("SUCCEEDED"),
        "validation_failed": statuses.count("VALIDATION_FAILED"),
        "checkpoints": sum(1 for item in checkpoint_ids if item),
        "final_app_hash": sha256(root / "app.js"),
    }
    require(len(set(checkpoint_ids)) == 20 and None not in checkpoint_ids, "Checkpoint perdido ou duplicado no stress.")


CASES: list[tuple[str, str, Callable[[dict[str, Any], Path], None]]] = [
    ("I001", "Projeto simples existente", run_i001),
    ("I002", "Erro sintatico", run_i002),
    ("I003", "Path escape", run_i003),
    ("I004", "Indice stale", run_i004),
    ("I005", "Projeto Python multi-ficheiro", run_i005),
    ("I006", "Projeto Node multi-ficheiro", run_i006),
    ("I007", "Alteracao multi-ficheiro", run_i007),
    ("I008", "Ficheiro grande", run_i008),
    ("I009", "Concorrencia", run_i009),
    ("I010", "Persistencia e restart", run_i010),
    ("I011", "Projeto criado pelo ProjectBuilder", run_i011),
    ("I012", "Stress sequencial", run_i012),
]


def run_case(test_id: str, name: str, function: Callable[[dict[str, Any], Path], None]) -> dict[str, Any]:
    metrics = new_metrics(test_id, name)
    started = time.perf_counter()
    tracemalloc.start()
    try:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f"ide-{test_id.lower()}-", dir=SCRATCH_ROOT) as temp_dir:
            function(metrics, Path(temp_dir))
        metrics["result"] = "PASS"
        if not metrics["final_state"]:
            metrics["final_state"] = "PASS"
    except Exception as exc:
        metrics["result"] = "FAIL"
        metrics["error"] = str(exc)
        metrics["failure_category"] = getattr(exc, "category", "IDE")
        metrics["trace"] = traceback.format_exc()
        if not metrics["final_state"]:
            metrics["final_state"] = "FAILED"
    finally:
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        metrics["peak_memory_bytes"] = peak
        metrics["duration_seconds"] = round(time.perf_counter() - started, 3)
    return metrics


def classification(results: list[dict[str, Any]]) -> str:
    passed = {item["test_id"] for item in results if item["result"] == "PASS"}
    if not all(f"I{index:03d}" in passed for index in range(1, 5)):
        return "NOT_READY"
    if all(f"I{index:03d}" in passed for index in range(1, 13)):
        return "STABLE_IDE"
    if all(f"I{index:03d}" in passed for index in range(1, 12)):
        return "INTEGRATED_IDE"
    if all(f"I{index:03d}" in passed for index in range(1, 11)):
        return "TRANSACTIONAL_IDE"
    return "BASIC_IDE"


def render_summary(results: list[dict[str, Any]]) -> str:
    headers = ["Teste", "Resultado", "Duracao", "Alteracoes", "Validacoes", "Rollback", "Motivo"]
    rows = [headers]
    for item in results:
        rows.append([
            item["test_id"],
            item["result"],
            f"{item['duration_seconds']:.3f}s",
            f"{len(item['files_changed'])} fich. / {item['bytes_modified']} B",
            str(len(item["commands_executed"])),
            "sim" if item["rollback_executed"] else "nao",
            item["error"] or "-",
        ])
    widths = [max(len(str(row[index])) for row in rows) for index in range(len(headers))]
    return "\n".join(" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)) for row in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="JARVIS IDE benchmark and stress test")
    parser.add_argument("--only", action="append", help="Executa apenas um ID, por exemplo I001")
    args = parser.parse_args()
    selected = {item.upper() for item in args.only} if args.only else None
    results = []
    for test_id, name, function in CASES:
        if selected and test_id not in selected:
            continue
        print(f"[{test_id}] {name}...", flush=True)
        result = run_case(test_id, name, function)
        results.append(result)
        print(f"[{test_id}] {result['result']} ({result['duration_seconds']:.3f}s)", flush=True)

    final_classification = classification(results) if not selected else "PARTIAL_RUN"
    first_failure = next((item for item in results if item["result"] == "FAIL"), None)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "classification": final_classification,
        "tests_run": len(results),
        "tests_passed": sum(item["result"] == "PASS" for item in results),
        "tests_failed": sum(item["result"] == "FAIL" for item in results),
        "first_failure": first_failure,
        "summary": render_summary(results),
        "results": results,
        "metric_definitions": {
            "files_read": "Numero de ficheiros fonte unicos expostos pelo ProjectContext durante o teste.",
            "bytes_modified": "Estimativa de bytes diferentes entre os trechos anterior e proposto.",
            "diff_size_bytes": "Tamanho UTF-8 dos diffs unificados gerados antes da escrita.",
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(report["summary"])
    print(f"\nClassificacao: {final_classification}")
    print(f"Relatorio: {REPORT_PATH}")
    if first_failure:
        print(f"Primeira falha: {first_failure['test_id']} [{first_failure['failure_category']}] {first_failure['error']}")
    return 1 if first_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
