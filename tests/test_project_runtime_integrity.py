import os
import shutil
import sys
from pathlib import Path

import pytest

from intelligence.coding_session import CodingSessionError, CodingSessionService
from intelligence.project_context import MAX_VIEW_FILE_BYTES, ProjectContextService
from intelligence.project_intelligence import MAX_AST_FILE_BYTES


def make_project(tmp_path: Path, project_id: str = "python-app") -> tuple[ProjectContextService, Path]:
    root = tmp_path / "workspace" / "projects" / project_id
    root.mkdir(parents=True)
    (root / "main.py").write_text("def value():\n    return 1\n", encoding="utf-8")
    return ProjectContextService(workspace_root=str(tmp_path)), root


def fake_runtime(root: Path, directory: str) -> Path:
    executable = root / directory / "Scripts" / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"runtime-placeholder")
    return executable


def test_project_venv_runtime_has_priority(tmp_path, monkeypatch):
    service, root = make_project(tmp_path)
    executable = fake_runtime(root, "venv")
    monkeypatch.setattr(service, "_probe_python_runtime", lambda path: "Python 3.test" if path == os.path.realpath(executable) else None)

    context = service.open_project("python-app")

    assert context.python_executable == os.path.realpath(executable)
    assert context.runtime_source == "project_venv"
    assert context.runtime_version == "Python 3.test"


def test_project_dot_venv_runtime_is_detected(tmp_path, monkeypatch):
    service, root = make_project(tmp_path)
    executable = fake_runtime(root, ".venv")
    monkeypatch.setattr(service, "_probe_python_runtime", lambda path: "Python 3.dotvenv" if path == os.path.realpath(executable) else None)

    context = service.open_project("python-app")

    assert context.python_executable == os.path.realpath(executable)
    assert context.runtime_source == "project_.venv"


def test_runtime_falls_back_to_jarvis_process(tmp_path):
    service, _root = make_project(tmp_path)

    context = service.open_project("python-app")

    assert context.python_executable == os.path.realpath(sys.executable)
    assert context.runtime_source == "jarvis_process"
    assert context.runtime_version


def test_runtime_can_be_explicitly_unavailable(tmp_path):
    service, _root = make_project(tmp_path)
    service.process_python_executable = None

    context = service.open_project("python-app")

    assert context.python_executable is None
    assert context.runtime_source == "unavailable"
    assert not any("py_compile" in item["command"] for item in context.suggested_commands)


def test_python_validations_use_exact_runtime_and_ignore_path_python(tmp_path, monkeypatch):
    service, root = make_project(tmp_path)
    fake_path = tmp_path / "fake-path"
    fake_path.mkdir()
    (fake_path / "python.exe").write_text("not a python runtime", encoding="utf-8")
    monkeypatch.setenv("PATH", str(fake_path) + os.pathsep + os.environ.get("PATH", ""))
    context = service.index_project("python-app")
    expected = ProjectContextService.python_module_command(
        os.path.realpath(sys.executable),
        "py_compile",
        ["main.py"],
    )

    assert context.python_executable == os.path.realpath(sys.executable)
    assert any(item["command"] == expected for item in context.suggested_commands)
    assert all(not item["command"].startswith("python ") for item in context.suggested_commands)

    sessions = CodingSessionService(service)
    session = sessions.create_session("python-app", "Alterar value", [{
        "file": "main.py",
        "operation": "replace_symbol",
        "symbol": "value",
        "new_code": "def value():\n    return 2",
        "reason": "Validar runtime absoluto.",
    }])
    applied = sessions.apply_session("python-app", session.session_id)
    assert applied.status == "SUCCEEDED"
    assert any(item["command"] == expected and item["exit_code"] == 0 for item in applied.validation_results)
    sessions.rollback_session("python-app", session.session_id, confirmed=True)
    assert "return 1" in (root / "main.py").read_text(encoding="utf-8")


def test_integrity_hashes_files_below_and_above_display_limit(tmp_path):
    root = tmp_path / "workspace" / "projects" / "large-app"
    root.mkdir(parents=True)
    (root / "small.js").write_text("function small() { return 1; }\n", encoding="utf-8")
    large_content = "// padding\n" * ((MAX_VIEW_FILE_BYTES // 11) + 2000)
    (root / "large.js").write_text(large_content, encoding="utf-8")
    service = ProjectContextService(workspace_root=str(tmp_path))

    context = service.index_project("large-app")
    metadata = context.ast_index["files"]

    assert metadata["small.js"]["size_bytes"] < MAX_VIEW_FILE_BYTES
    assert metadata["small.js"]["hash_available"] is True
    assert metadata["large.js"]["size_bytes"] > MAX_VIEW_FILE_BYTES
    assert metadata["large.js"]["hash_available"] is True
    assert context.ast_index["source_hashes"]["large.js"]
    assert "large.js" not in service.read_project_files("large-app")


def test_file_above_ast_limit_is_hashed_but_not_indexed(tmp_path):
    root = tmp_path / "workspace" / "projects" / "ast-limit"
    root.mkdir(parents=True)
    content = "// large source\n" * ((MAX_AST_FILE_BYTES // 16) + 2000)
    (root / "huge.js").write_text(content, encoding="utf-8")
    service = ProjectContextService(workspace_root=str(tmp_path))

    context = service.index_project("ast-limit")
    graph = service.load_index("ast-limit")
    metadata = context.ast_index["files"]["huge.js"]

    assert metadata["size_bytes"] > MAX_AST_FILE_BYTES
    assert metadata["content_indexed"] is False
    assert metadata["hash_available"] is True
    assert metadata["source_hash"]
    assert "huge.js" not in graph
    assert "huge.js" not in service.read_project_files("ast-limit")


@pytest.mark.skipif(shutil.which("node") is None, reason="node indisponivel")
def test_large_file_stale_checkpoint_and_rollback(tmp_path):
    root = tmp_path / "workspace" / "projects" / "large-transaction"
    root.mkdir(parents=True)
    padding = "// context\n" * ((MAX_VIEW_FILE_BYTES // 11) + 1500)
    original = padding + "function compute(value) { return value + 1; }\n"
    (root / "app.js").write_text(original, encoding="utf-8")
    service = ProjectContextService(workspace_root=str(tmp_path))
    service.index_project("large-transaction")
    sessions = CodingSessionService(service)
    change = [{
        "file": "app.js",
        "operation": "replace_symbol",
        "symbol": "compute",
        "new_code": "function compute(value) { return value + 2; }",
        "reason": "Alteracao localizada.",
    }]

    stale_session = sessions.create_session("large-transaction", "Detetar stale", change)
    with (root / "app.js").open("a", encoding="utf-8") as handle:
        handle.write("// external\n")
    with pytest.raises(CodingSessionError, match="desatualizado"):
        sessions.apply_session("large-transaction", stale_session.session_id)

    (root / "app.js").write_text(original, encoding="utf-8")
    service.index_project("large-transaction")
    session = sessions.create_session("large-transaction", "Aplicar e reverter", change)
    applied = sessions.apply_session("large-transaction", session.session_id)
    assert applied.status == "SUCCEEDED"
    assert applied.checkpoint["files"]["app.js"]["before_hash"]
    restored = sessions.rollback_session("large-transaction", session.session_id, confirmed=True)
    assert restored.status == "ROLLED_BACK"
    assert (root / "app.js").read_text(encoding="utf-8") == original


def test_binary_files_are_not_hashed(tmp_path):
    root = tmp_path / "workspace" / "projects" / "binary-app"
    root.mkdir(parents=True)
    (root / "asset.bin").write_bytes(b"\x00\x01\x02")
    (root / "binary.js").write_bytes(b"function binary() {}\x00payload")
    service = ProjectContextService(workspace_root=str(tmp_path))

    context = service.index_project("binary-app")

    assert "asset.bin" not in context.ast_index["files"]
    assert context.ast_index["files"]["binary.js"]["hash_available"] is False
    assert context.ast_index["files"]["binary.js"]["reason"] == "binary_content"
    assert "binary.js" not in context.ast_index["source_hashes"]


def test_file_above_transaction_limit_is_rejected_clearly(tmp_path):
    root = tmp_path / "workspace" / "projects" / "too-large"
    root.mkdir(parents=True)
    content = "// padding\n" * 60_000 + "function compute() { return 1; }\n"
    (root / "app.js").write_text(content, encoding="utf-8")
    service = ProjectContextService(
        workspace_root=str(tmp_path),
        max_transaction_file_bytes=MAX_VIEW_FILE_BYTES + 10_000,
    )
    context = service.index_project("too-large")
    metadata = context.ast_index["files"]["app.js"]
    assert metadata["hash_available"] is False
    assert metadata["reason"] == "transaction_limit_exceeded"

    sessions = CodingSessionService(service)
    with pytest.raises(CodingSessionError, match="excede o limite transacional"):
        sessions.create_session("too-large", "Alterar ficheiro demasiado grande", [{
            "file": "app.js",
            "operation": "replace_symbol",
            "symbol": "compute",
            "new_code": "function compute() { return 2; }",
            "reason": "Deve ser rejeitado.",
        }])
