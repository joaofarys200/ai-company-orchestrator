import hashlib
import json
import os
from pathlib import Path

import pytest

import sandbox
from intelligence.project_context import ProjectContextError, ProjectContextService


def make_service(tmp_path: Path) -> ProjectContextService:
    (tmp_path / "workspace" / "projects").mkdir(parents=True)
    return ProjectContextService(workspace_root=str(tmp_path))


def test_open_project_detects_html_javascript_and_entrypoints(tmp_path):
    service = make_service(tmp_path)
    project = tmp_path / "workspace" / "projects" / "web-app"
    project.mkdir()
    (project / "index.html").write_text('<script src="app.js"></script>', encoding="utf-8")
    (project / "app.js").write_text("function boot() {}", encoding="utf-8")

    context = service.open_project("web-app")

    assert context.project_id == "web-app"
    assert context.root_path == os.path.realpath(project)
    assert "HTML/JavaScript" in context.stack
    assert context.entrypoints == ["index.html", "app.js"]
    assert context.source_roots == ["."]
    assert Path(service.context_path("web-app")).is_file()


def test_detects_node_python_frameworks_scripts_and_package_managers(tmp_path):
    service = make_service(tmp_path)
    project = tmp_path / "workspace" / "projects" / "full-stack"
    project.mkdir()
    (project / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (project / "requirements.txt").write_text("fastapi==1.0\n", encoding="utf-8")
    (project / "package-lock.json").write_text("{}", encoding="utf-8")
    (project / "package.json").write_text(json.dumps({
        "name": "full-stack-app",
        "main": "src/main.js",
        "scripts": {"lint": "eslint .", "build": "vite build"},
        "dependencies": {"react": "latest"},
        "devDependencies": {"vite": "latest"},
    }), encoding="utf-8")
    (project / "src").mkdir()
    (project / "src" / "main.js").write_text("export function start() {}", encoding="utf-8")

    context = service.open_project("full-stack")

    assert context.project_name == "full-stack-app"
    assert {"Node", "Python"}.issubset(context.stack)
    assert {"React", "Vite", "FastAPI"}.issubset(context.frameworks)
    assert {"npm", "pip"}.issubset(context.package_managers)
    assert {"main.py", "src/main.js"}.issubset(context.entrypoints)
    assert context.package_scripts["lint"] == "eslint ."
    assert any(item["command"] == "npm run lint" for item in context.suggested_commands)


def test_project_index_finds_symbol_and_cross_file_reference_and_excludes_generated_dirs(tmp_path):
    service = make_service(tmp_path)
    project = tmp_path / "workspace" / "projects" / "indexed-app"
    project.mkdir()
    (project / "main.js").write_text("export function greet(name) { return `Hi ${name}`; }\n", encoding="utf-8")
    (project / "consumer.js").write_text("import { greet } from './main.js';\nconsole.log(greet('Jarvis'));\n", encoding="utf-8")
    for ignored in ("node_modules", "venv", "dist", "__pycache__"):
        ignored_dir = project / ignored
        ignored_dir.mkdir()
        (ignored_dir / "ignored.js").write_text("function greet() {}", encoding="utf-8")

    context = service.index_project("indexed-app")
    graph = service.load_index("indexed-app")
    definitions = service.locate_symbol("indexed-app", "greet")
    result = service.find_references("indexed-app", "greet")

    assert context.ast_index["path"] == "workspace/.jarvis/projects/indexed-app/symbols_index.json"
    assert set(graph) == {"consumer.js", "main.js"}
    assert definitions == [{
        "kind": "definition",
        "symbol_kind": "function",
        "file": "main.js",
        "line": 1,
        "confirmed": True,
        "text": "greet",
    }]
    assert any(reference["file"] == "consumer.js" and reference["confirmed"] for reference in result["references"])


def test_preview_uses_selected_project_root_without_installing_dependencies(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    project = tmp_path / "workspace" / "projects" / "preview-app"
    project.mkdir()
    (project / "index.html").write_text("<h1>Preview</h1>", encoding="utf-8")
    captured = {}

    def fake_run(callback, root_dir=None, allow_dependency_install=None):
        captured.update(root_dir=root_dir, allow_dependency_install=allow_dependency_install)
        return {"running": True, "preview_url": "http://127.0.0.1:54321/", "root": root_dir}

    monkeypatch.setattr(sandbox, "run_custom_project", fake_run)
    result = service.preview_project("preview-app", lambda _content: None)

    assert captured["root_dir"] == os.path.realpath(project)
    assert captured["allow_dependency_install"] is False
    assert result["root"] == os.path.realpath(project)


def test_index_reports_parse_errors_without_stopping_other_files(tmp_path):
    service = make_service(tmp_path)
    project = tmp_path / "workspace" / "projects" / "partial-index"
    project.mkdir()
    (project / "good.py").write_text("def healthy():\n    return True\n", encoding="utf-8")
    (project / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    context = service.index_project("partial-index")
    graph = service.load_index("partial-index")

    assert "good.py" in graph
    assert context.ast_index["status"] == "partial"
    assert context.ast_index["error_count"] >= 1
    assert any(item.get("file") == "broken.py" for item in context.diagnostics)


def test_obsidian_and_sandbox_are_not_available_as_projects(tmp_path):
    service = make_service(tmp_path)
    projects_root = tmp_path / "workspace" / "projects"
    (projects_root / "valid-app").mkdir()
    (projects_root / "obsidian_vault").mkdir()
    (projects_root / "sandbox_dir").mkdir()

    assert [item["project_id"] for item in service.list_projects()] == ["valid-app"]
    with pytest.raises(ProjectContextError):
        service.open_project("obsidian_vault")
    with pytest.raises(ProjectContextError):
        service.open_project("sandbox_dir")


def test_manual_project_file_save_is_atomic_and_preserves_crlf_and_bom(tmp_path):
    service = make_service(tmp_path)
    project = tmp_path / "workspace" / "projects" / "editor-app"
    project.mkdir()
    source = project / "app.js"
    original = b"\xef\xbb\xbffunction boot() {\r\n  return 1;\r\n}\r\n"
    source.write_bytes(original)
    original_hash = hashlib.sha256(original).hexdigest()

    payload = service.project_payload("editor-app")
    result = service.save_project_file(
        "editor-app",
        "app.js",
        "function boot() {\n  return 2;\n}\n",
        payload["file_hashes"]["app.js"],
    )

    expected = b"\xef\xbb\xbffunction boot() {\r\n  return 2;\r\n}\r\n"
    assert original_hash != result["sha256"]
    assert source.read_bytes() == expected
    assert result["sha256"] == hashlib.sha256(expected).hexdigest()
    assert not list(project.glob("*.jarvis-editor-tmp"))


def test_manual_project_file_save_rejects_stale_hash_and_paths_outside_project(tmp_path):
    service = make_service(tmp_path)
    project = tmp_path / "workspace" / "projects" / "editor-app"
    project.mkdir()
    source = project / "app.js"
    source.write_text("const value = 1;\n", encoding="utf-8")
    payload = service.project_payload("editor-app")
    expected_hash = payload["file_hashes"]["app.js"]
    source.write_text("const value = 2;\n", encoding="utf-8")

    with pytest.raises(ProjectContextError, match="mudou no disco"):
        service.save_project_file("editor-app", "app.js", "const value = 3;\n", expected_hash)
    with pytest.raises(ProjectContextError, match="Caminho"):
        service.save_project_file("editor-app", "../outside.js", "bad", expected_hash)

    assert source.read_text(encoding="utf-8") == "const value = 2;\n"


def test_task_app_smoke_uses_real_project_and_finds_add_task():
    service = ProjectContextService()
    context = service.index_project("task-app")
    result = service.find_references("task-app", "addTask")

    assert context.root_path.endswith(os.path.join("workspace", "projects", "task-app"))
    assert "HTML/JavaScript" in context.stack
    assert any(item["file"] == "app.js" for item in result["definitions"])
    assert any(item["file"] == "index.html" and not item["confirmed"] for item in result["references"])
    assert "obsidian" not in context.root_path.lower()


def test_delete_project_removes_project_dir_and_metadata(tmp_path):
    service = make_service(tmp_path)
    service.create_project("sample-to-delete", "Sample App")
    project_dir = tmp_path / "workspace" / "projects" / "sample-to-delete"
    meta_dir = tmp_path / "workspace" / ".jarvis" / "projects" / "sample-to-delete"

    assert project_dir.is_dir()

    result = service.delete_project("sample-to-delete")

    assert result["deleted"] is True
    assert not project_dir.exists()
    assert not meta_dir.exists()


def test_delete_project_file_removes_file_and_reindexes(tmp_path):
    service = make_service(tmp_path)
    service.create_project("file-delete-app", "File Delete App", template="web-app")
    project_dir = tmp_path / "workspace" / "projects" / "file-delete-app"
    js_file = project_dir / "app.js"

    assert js_file.is_file()
    assert "app.js" in service.read_project_files("file-delete-app")

    result = service.delete_project_file("file-delete-app", "app.js")

    assert result["deleted"] is True
    assert not js_file.exists()
    assert "app.js" not in service.read_project_files("file-delete-app")


def test_delete_project_file_rejects_paths_outside_project(tmp_path):
    service = make_service(tmp_path)
    service.create_project("safe-del-app", "Safe App")

    with pytest.raises(ProjectContextError, match="Caminho"):
        service.delete_project_file("safe-del-app", "../outside.js")
