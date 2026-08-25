"""
Tests for Phase 9.3: Automatic Dependency Management & Intelligent CDN Injection
"""

import json
import pytest
from intelligence.artifact_inference import (
    DependencyScanner,
    DeterministicRepairEngine,
    DiscoveredDependencies,
)


def test_dependency_scanner_detects_frontend_libraries():
    scanner = DependencyScanner()
    files = {
        "index.html": "<!DOCTYPE html><html><head></head><body><canvas id='myChart'></canvas><i data-lucide='activity'></i></body></html>",
        "app.js": "const chart = new Chart(ctx, {}); confetti(); axios.get('/api');",
    }
    deps = scanner.scan(files)

    assert any("chart.js" in tag for tag in deps.cdn_tags)
    assert any("lucide" in tag for tag in deps.cdn_tags)
    assert any("canvas-confetti" in tag for tag in deps.cdn_tags)
    assert any("axios" in tag for tag in deps.cdn_tags)
    assert "chart.js" in deps.npm_packages
    assert "lucide" in deps.npm_packages
    assert "canvas-confetti" in deps.npm_packages
    assert "axios" in deps.npm_packages


def test_dependency_scanner_detects_backend_python_packages():
    scanner = DependencyScanner()
    files = {
        "server.py": """
import fastapi
import uvicorn
from sqlalchemy import create_engine
import httpx
""",
    }
    deps = scanner.scan(files)

    assert "fastapi>=0.110.0" in deps.pip_packages
    assert "uvicorn>=0.28.0" in deps.pip_packages
    assert "sqlalchemy>=2.0.0" in deps.pip_packages
    assert "httpx>=0.27.0" in deps.pip_packages


def test_repair_engine_injects_cdn_into_index_html():
    engine = DeterministicRepairEngine()
    planned_files = {
        "index.html": "<!DOCTYPE html>\n<html>\n<head>\n    <title>App</title>\n</head>\n<body>\n    <canvas id='c'></canvas>\n    <script src='app.js'></script>\n</body>\n</html>",
        "app.js": "const chart = new Chart(document.getElementById('c'), {});",
        "styles.css": "body { margin: 0; box-sizing: border-box; }",
    }

    result = engine.repair_plan(
        prompt="cria dashboard com chart.js",
        planned_files=planned_files,
        project_name="dashboard",
    )

    repaired_html = result.repaired_files["index.html"]
    assert "https://cdn.jsdelivr.net/npm/chart.js" in repaired_html
    assert "</head>" in repaired_html


def test_repair_engine_creates_requirements_txt_for_python_backend():
    engine = DeterministicRepairEngine()
    planned_files = {
        "server.py": """
import fastapi
import uvicorn

app = fastapi.FastAPI()
@app.get('/health')
def health():
    return {'status': 'ok'}
""",
    }

    result = engine.repair_plan(
        prompt="cria api fastapi",
        planned_files=planned_files,
        project_name="fastapi-app",
    )

    assert "requirements.txt" in result.repaired_files
    req_content = result.repaired_files["requirements.txt"]
    assert "fastapi>=" in req_content
    assert "uvicorn>=" in req_content


def test_repair_engine_updates_package_json_with_npm_deps():
    engine = DeterministicRepairEngine()
    planned_files = {
        "index.html": "<!DOCTYPE html><html><head></head><body><i data-lucide='check'></i><script src='app.js'></script></body></html>",
        "app.js": "lucide.createIcons();",
        "styles.css": "body { margin: 0; box-sizing: border-box; }",
        "package.json": json.dumps({"name": "lucide-app", "version": "1.0.0", "dependencies": {}}),
    }

    result = engine.repair_plan(
        prompt="cria app com icones lucide",
        planned_files=planned_files,
        project_name="lucide-app",
    )

    pkg = json.loads(result.repaired_files["package.json"])
    assert "lucide" in pkg["dependencies"]


def test_repair_engine_no_op_when_no_dependencies():
    engine = DeterministicRepairEngine()
    planned_files = {
        "index.html": "<!DOCTYPE html>\n<html>\n<head>\n    <title>Simples</title>\n    <link rel='stylesheet' href='styles.css'>\n</head>\n<body>\n    <h1>Ola</h1>\n    <script src='app.js'></script>\n</body>\n</html>",
        "app.js": "document.addEventListener('DOMContentLoaded', () => { console.log('ok'); });",
        "styles.css": "body { margin: 0; box-sizing: border-box; }",
    }

    result = engine.repair_plan(
        prompt="cria pagina simples",
        planned_files=planned_files,
        project_name="simple-app",
    )

    assert "requirements.txt" not in result.repaired_files
    assert result.repaired_files["index.html"] == planned_files["index.html"]
