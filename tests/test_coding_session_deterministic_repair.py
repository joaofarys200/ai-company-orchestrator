"""
Testes de integracao para o motor de reparacao deterministica de artefactos no CodingSessionService.
"""

import json
import shutil
import pytest
from pathlib import Path
from intelligence.coding_session import CodingSessionService
from intelligence.project_context import ProjectContextService


@pytest.fixture
def workspace_with_web_project(tmp_path):
    source = Path(__file__).parents[1] / "workspace" / "projects" / "task-app"
    target = tmp_path / "workspace" / "projects" / "task-app"
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copytree(source, target)
    else:
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text("<!DOCTYPE html><html><body><h1>Task App</h1></body></html>", encoding="utf-8")
        (target / "styles.css").write_text("body { margin: 0; }", encoding="utf-8")
        (target / "app.js").write_text("function addTask() { return true; }", encoding="utf-8")
        (target / "package.json").write_text(json.dumps({"name": "task-app", "version": "1.0.0"}), encoding="utf-8")

    # Ensure styles.css exists in task-app fixture
    styles_file = target / "styles.css"
    if not styles_file.exists():
        styles_file.write_text("body { margin: 0; }", encoding="utf-8")

    projects = ProjectContextService(workspace_root=str(tmp_path))
    projects.index_project("task-app")
    return projects, "task-app"


@pytest.mark.anyio
async def test_coding_session_repairs_missing_index_html(workspace_with_web_project, tmp_path):
    projects, _ = workspace_with_web_project
    
    # Create project with web-app template then delete index.html
    projects.create_project("new-app", "New App", template="web-app")
    root_dir = Path(projects.project_root("new-app"))
    index_file = root_dir / "index.html"
    if index_file.exists():
        index_file.unlink()
    
    projects.index_project("new-app")
    sessions = CodingSessionService(projects)

    # Incomplete LLM plan: only proposed app.js and styles.css, missed index.html for a web app
    incomplete_plan = json.dumps({
        "changes": [
            {
                "file": "app.js",
                "operation": "replace_text",
                "old_text": "console.log('Iniciado New App');",
                "new_code": "console.log('Iniciado New App');\nconsole.log('Initialized');",
                "reason": "Logica da aplicacao",
            },
            {
                "file": "styles.css",
                "operation": "replace_text",
                "old_text": "body {",
                "new_code": "body {\n    background: #000;",
                "reason": "Estilos da aplicacao",
            },
        ],
        "risks": [],
    })

    async def fake_requester(payload, correction=None):
        return incomplete_plan

    session = await sessions.create_assisted_session(
        project_id="new-app",
        objective="Cria uma pagina web com dashboard e filtros de tarefas",
        requester=fake_requester,
    )

    # Verify that index.html was deterministically inferred and added to proposed_changes
    proposed_files = [c["file"] for c in session.proposed_changes]
    assert "index.html" in proposed_files
    assert "styles.css" in proposed_files

    # Verify content of repaired index.html
    index_change = next(c for c in session.proposed_changes if c["file"] == "index.html")
    assert "<!DOCTYPE html>" in index_change["proposed_excerpt"]
    assert "dashboard" in index_change["proposed_excerpt"]


@pytest.mark.anyio
async def test_coding_session_no_unnecessary_repairs_when_complete(workspace_with_web_project):
    projects, project_id = workspace_with_web_project
    sessions = CodingSessionService(projects)

    # Complete edit plan modifying existing app.js
    complete_plan = json.dumps({
        "changes": [
            {
                "file": "app.js",
                "operation": "replace_symbol",
                "symbol": "addTask",
                "new_code": "function addTask() { const task = 'new'; return task; }",
                "reason": "Atualizar funcao addTask",
            },
        ],
        "risks": [],
    })

    async def fake_requester(payload, correction=None):
        return complete_plan

    session = await sessions.create_assisted_session(
        project_id=project_id,
        objective="Atualizar logica de addTask",
        requester=fake_requester,
    )

    assert len(session.proposed_changes) == 1
    assert session.proposed_changes[0]["file"] == "app.js"
