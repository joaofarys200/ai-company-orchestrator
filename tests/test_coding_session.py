import asyncio
import os
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from intelligence.coding_session import CodingSessionError, CodingSessionService, resolve_project_git_context
from intelligence.project_context import ProjectContextService


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


def parse_python_module_command(command: str) -> tuple[str, list[str]]:
    tokens = shlex.split(command, posix=os.name != "nt")
    if os.name == "nt":
        if len(tokens) < 4 or tokens[0] != "&":
            raise ValueError("Nao e um comando Python PowerShell estruturado.")
        executable = tokens[1].strip('"').replace('`"', '"')
        arguments = [token.strip('"') for token in tokens[2:]]
    else:
        if len(tokens) < 3:
            raise ValueError("Nao e um comando Python estruturado.")
        executable = tokens[0]
        arguments = tokens[1:]
    if arguments[0] != "-m":
        raise ValueError("O comando nao executa um modulo Python.")
    return executable, arguments


def assert_python_module_validation(
    results: list[dict],
    python_executable: str,
    module: str,
    relative_path: str,
) -> dict:
    matches = []
    for result in results:
        if result["kind"] != "syntax":
            continue
        try:
            executable, arguments = parse_python_module_command(result["command"])
        except ValueError:
            continue
        if arguments == ["-m", module, relative_path]:
            matches.append((result, executable))

    assert len(matches) == 1
    result, executable = matches[0]
    assert os.path.normcase(os.path.realpath(executable)) == os.path.normcase(os.path.realpath(python_executable))
    assert not result["command"].lstrip().startswith("python ")
    assert result["exit_code"] == 0
    return result


@pytest.fixture
def task_app_service(tmp_path):
    source = Path(__file__).parents[1] / "workspace" / "projects" / "task-app"
    target = tmp_path / "workspace" / "projects" / "task-app"
    target.parent.mkdir(parents=True)
    shutil.copytree(source, target)
    projects = ProjectContextService(workspace_root=str(tmp_path))
    projects.index_project("task-app")
    return CodingSessionService(projects), projects, target


def proposed_change(new_code: str):
    return [{
        "file": "app.js",
        "operation": "replace_symbol",
        "symbol": "addTask",
        "new_code": new_code,
        "reason": "Ignorar tarefas vazias depois de remover espacos.",
    }]


def test_a_applies_add_task_patch_and_runs_node_check(task_app_service):
    sessions, _projects, root = task_app_service
    original = (root / "app.js").read_bytes()

    session = sessions.create_session("task-app", "Ignorar input vazio", proposed_change(VALID_ADD_TASK))

    assert session.status == "PROPOSED"
    assert session.affected_files == ["app.js"]
    assert session.change_plan["affected_symbols"] == ["addTask"]
    assert "-  if (input.value)" in session.proposed_changes[0]["unified_diff"]
    assert "+  const task = input.value.trim();" in session.proposed_changes[0]["unified_diff"]

    applied = sessions.apply_session("task-app", session.session_id)

    assert applied.status == "SUCCEEDED"
    assert applied.checkpoint["type"] == "file_backup"
    node_check = next(result for result in applied.validation_results if result["command"] == 'node --check "app.js"')
    assert node_check["exit_code"] == 0
    assert node_check["required"] is True
    assert "input.value.trim()" in (root / "app.js").read_text(encoding="utf-8")

    rolled_back = sessions.rollback_session("task-app", session.session_id, confirmed=True)
    assert rolled_back.status == "ROLLED_BACK"
    assert (root / "app.js").read_bytes() == original


def test_b_syntax_failure_allows_exact_rollback(task_app_service):
    sessions, _projects, root = task_app_service
    original = (root / "app.js").read_bytes()
    session = sessions.create_session("task-app", "Introduzir erro sintatico controlado", proposed_change(INVALID_ADD_TASK))

    failed = sessions.apply_session("task-app", session.session_id)

    assert failed.status == "VALIDATION_FAILED"
    node_check = next(result for result in failed.validation_results if result["command"] == 'node --check "app.js"')
    assert node_check["exit_code"] != 0
    assert (root / "app.js").read_bytes() != original

    restored = sessions.rollback_session("task-app", session.session_id, confirmed=True)
    assert restored.status == "ROLLED_BACK"
    assert (root / "app.js").read_bytes() == original


def test_c_blocks_file_outside_project(task_app_service, tmp_path):
    sessions, _projects, _root = task_app_service

    with pytest.raises(CodingSessionError, match="fora do projeto|Path de alteracao"):
        sessions.create_session("task-app", "Tentar sair do projeto", [{
            "file": "../outside.js",
            "operation": "create_file",
            "new_code": "console.log('blocked');",
            "reason": "Teste de path policy.",
        }])

    assert not (tmp_path / "workspace" / "projects" / "outside.js").exists()


def test_d_unrelated_file_remains_identical(task_app_service):
    sessions, _projects, root = task_app_service
    unrelated_before = (root / "index.html").read_bytes()
    session = sessions.create_session("task-app", "Alterar apenas addTask", proposed_change(VALID_ADD_TASK))

    applied = sessions.apply_session("task-app", session.session_id)

    assert applied.status == "SUCCEEDED"
    assert (root / "index.html").read_bytes() == unrelated_before
    sessions.rollback_session("task-app", session.session_id, confirmed=True)
    assert (root / "index.html").read_bytes() == unrelated_before


def test_stale_index_blocks_application(task_app_service):
    sessions, _projects, root = task_app_service
    session = sessions.create_session("task-app", "Alterar addTask", proposed_change(VALID_ADD_TASK))
    with (root / "app.js").open("a", encoding="utf-8") as handle:
        handle.write("\n// external change\n")

    with pytest.raises(CodingSessionError, match="desatualizado"):
        sessions.apply_session("task-app", session.session_id)


def test_rollback_requires_explicit_confirmation(task_app_service):
    sessions, _projects, _root = task_app_service
    session = sessions.create_session("task-app", "Alterar addTask", proposed_change(VALID_ADD_TASK))
    applied = sessions.apply_session("task-app", session.session_id)
    assert applied.status == "SUCCEEDED"

    with pytest.raises(CodingSessionError, match="confirmacao explicita"):
        sessions.rollback_session("task-app", session.session_id)

    sessions.rollback_session("task-app", session.session_id, confirmed=True)


def test_python_symbol_change_reuses_patch_engine_and_py_compile(tmp_path):
    root = tmp_path / "workspace" / "projects" / "python-app"
    root.mkdir(parents=True)
    original = "def calculate(value):\n    return value + 1\n\nif __name__ == '__main__':\n    print(calculate(1))\n"
    (root / "main.py").write_text(original, encoding="utf-8")
    projects = ProjectContextService(workspace_root=str(tmp_path))
    context = projects.index_project("python-app")
    sessions = CodingSessionService(projects)
    session = sessions.create_session("python-app", "Somar dois", [{
        "file": "main.py",
        "operation": "replace_symbol",
        "symbol": "calculate",
        "new_code": "def calculate(value):\n    return value + 2",
        "reason": "Atualizar o calculo.",
    }])

    applied = sessions.apply_session("python-app", session.session_id)

    assert applied.status == "SUCCEEDED"
    assert context.python_executable
    assert_python_module_validation(
        applied.validation_results,
        context.python_executable,
        "py_compile",
        "main.py",
    )
    assert "return value + 2" in (root / "main.py").read_text(encoding="utf-8")
    sessions.rollback_session("python-app", session.session_id, confirmed=True)
    assert (root / "main.py").read_text(encoding="utf-8") == original


def test_new_file_uses_injected_write_file_path_and_is_removed_only_on_confirmed_rollback(task_app_service):
    _sessions, projects, root = task_app_service

    def write_file(path: str, content: str) -> str:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(content, encoding="utf-8")
        return "Ficheiro guardado com sucesso."

    sessions = CodingSessionService(projects, new_file_writer=write_file)
    session = sessions.create_session("task-app", "Adicionar helper", [{
        "file": "helper.js",
        "operation": "create_file",
        "new_code": "export function helper() { return true; }\n",
        "reason": "Adicionar helper isolado.",
    }])

    applied = sessions.apply_session("task-app", session.session_id)

    assert applied.status == "SUCCEEDED"
    assert (root / "helper.js").is_file()
    assert any(item["command"] == 'node --check "helper.js"' and item["exit_code"] == 0 for item in applied.validation_results)
    sessions.rollback_session("task-app", session.session_id, confirmed=True)
    assert not (root / "helper.js").exists()


def test_assisted_plan_receives_real_context_and_ast(task_app_service):
    sessions, _projects, _root = task_app_service
    captured = {}

    async def requester(payload, correction):
        captured.update(payload=payload, correction=correction)
        return {
            "changes": proposed_change(VALID_ADD_TASK),
            "risks": ["Alteracao do tratamento de input."],
        }

    session = asyncio.run(sessions.create_assisted_session("task-app", "Ignorar input vazio", requester=requester))

    assert captured["correction"] is None
    assert "app.js" in captured["payload"]["symbols"]
    assert captured["payload"]["project_context"]["root_path"].endswith("task-app")
    assert session.change_plan["risks"] == ["Alteracao do tratamento de input."]


@pytest.mark.skipif(shutil.which("git") is None, reason="git indisponivel")
def test_git_repository_uses_selective_blob_checkpoint(task_app_service, tmp_path):
    _sessions, projects, root = task_app_service
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    projects.index_project("task-app")
    sessions = CodingSessionService(projects)
    original = (root / "app.js").read_bytes()
    session = sessions.create_session("task-app", "Alterar com checkpoint Git", proposed_change(VALID_ADD_TASK))

    applied = sessions.apply_session("task-app", session.session_id)

    assert applied.status == "SUCCEEDED"
    assert applied.checkpoint["type"] == "git_blob"
    checkpoint_file = applied.checkpoint["files"]["app.js"]
    assert checkpoint_file["checkpoint_method"] == "git_blob"
    assert checkpoint_file["git_blob_oid"]
    assert checkpoint_file["original_sha256"]
    assert checkpoint_file["size_bytes"] == len(original)
    assert checkpoint_file["existed_before"] is True
    sessions.rollback_session("task-app", session.session_id, confirmed=True)
    assert (root / "app.js").read_bytes() == original


@pytest.mark.skipif(shutil.which("git") is None, reason="git indisponivel")
def test_nested_git_project_uses_file_backup_without_parent_blobs(task_app_service, tmp_path):
    _sessions, projects, root = task_app_service
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    projects.index_project("task-app")
    objects_dir = tmp_path / ".git" / "objects"
    objects_before = sorted(path.relative_to(objects_dir) for path in objects_dir.rglob("*") if path.is_file())
    sessions = CodingSessionService(projects)
    session = sessions.create_session("task-app", "Checkpoint nested", proposed_change(VALID_ADD_TASK))

    applied = sessions.apply_session("task-app", session.session_id)

    assert applied.status == "SUCCEEDED"
    assert applied.checkpoint["type"] == "file_backup"
    assert applied.checkpoint["strategy"] == "file_backup"
    assert applied.checkpoint["reason"] == "nested_project_uses_file_backup"
    assert applied.checkpoint["git_context"]["git_toplevel"] == os.path.realpath(tmp_path)
    objects_after = sorted(path.relative_to(objects_dir) for path in objects_dir.rglob("*") if path.is_file())
    assert objects_after == objects_before
    sessions.rollback_session("task-app", session.session_id, confirmed=True)


def test_non_git_project_uses_selective_file_backup(task_app_service):
    _sessions, projects, root = task_app_service
    context = resolve_project_git_context(str(root))
    sessions = CodingSessionService(projects)
    session = sessions.create_session("task-app", "Checkpoint sem Git", proposed_change(VALID_ADD_TASK))

    applied = sessions.apply_session("task-app", session.session_id)

    assert context["is_git_repository"] is False
    assert context["checkpoint_strategy"] == "file_backup"
    assert applied.checkpoint["type"] == "file_backup"
    assert applied.checkpoint["reason"] == "not_a_git_repository"
    sessions.rollback_session("task-app", session.session_id, confirmed=True)


def test_checkpoint_failure_preserves_primary_error_without_rollback(task_app_service, monkeypatch):
    sessions, _projects, root = task_app_service
    original = (root / "app.js").read_bytes()
    session = sessions.create_session("task-app", "Falhar checkpoint", proposed_change(VALID_ADD_TASK))

    def fail_checkpoint(_session, _root):
        raise RuntimeError("checkpoint original failure")

    monkeypatch.setattr(sessions, "_create_checkpoint", fail_checkpoint)
    failed = sessions.apply_session("task-app", session.session_id)

    assert failed.status == "ERROR"
    assert failed.primary_error["type"] == "RuntimeError"
    assert failed.primary_error["message"] == "checkpoint original failure"
    assert "fail_checkpoint" in failed.primary_error["traceback"]
    assert failed.checkpoint_created is False
    assert failed.writes_started is False
    assert failed.rollback_attempted is False
    assert failed.rollback_succeeded is False
    assert failed.rollback_error is None
    assert (root / "app.js").read_bytes() == original


def test_partial_write_failure_preserves_error_and_rolls_back(task_app_service, monkeypatch):
    sessions, _projects, root = task_app_service
    original = (root / "app.js").read_bytes()
    session = sessions.create_session("task-app", "Falhar depois da escrita", proposed_change(VALID_ADD_TASK))

    def fail_verification(_root, _changes):
        raise RuntimeError("post-write verification failure")

    monkeypatch.setattr(sessions, "_verify_applied_changes", fail_verification)
    failed = sessions.apply_session("task-app", session.session_id)

    assert failed.status == "ERROR_ROLLED_BACK"
    assert failed.primary_error["message"] == "post-write verification failure"
    assert failed.checkpoint_created is True
    assert failed.writes_started is True
    assert failed.rollback_attempted is True
    assert failed.rollback_succeeded is True
    assert failed.rollback_error is None
    assert (root / "app.js").read_bytes() == original


def test_rollback_failure_preserves_both_errors(task_app_service, monkeypatch):
    sessions, _projects, _root = task_app_service
    session = sessions.create_session("task-app", "Falhar rollback", proposed_change(VALID_ADD_TASK))

    def fail_verification(_root, _changes):
        raise RuntimeError("primary write failure")

    def fail_rollback(_session, _root):
        raise OSError("rollback storage failure")

    monkeypatch.setattr(sessions, "_verify_applied_changes", fail_verification)
    monkeypatch.setattr(sessions, "_restore_checkpoint", fail_rollback)
    failed = sessions.apply_session("task-app", session.session_id)

    assert failed.status == "ROLLBACK_FAILED"
    assert failed.primary_error["type"] == "RuntimeError"
    assert failed.primary_error["message"] == "primary write failure"
    assert failed.rollback_error["type"] == "OSError"
    assert failed.rollback_error["message"] == "rollback storage failure"
    assert failed.rollback_attempted is True
    assert failed.rollback_succeeded is False
