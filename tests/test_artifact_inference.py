"""
Testes unitários para o motor de Inferência Determinística de Artefactos e Reparação Estrutural (Fase 9.2).
"""

import pytest
from intelligence.artifact_inference import (
    Capability,
    CapabilityDetector,
    ArtifactInferenceEngine,
    DeterministicRepairEngine,
)


def test_capability_detector_basic_web():
    detector = CapabilityDetector()
    caps = detector.detect("faz uma pagina web simples")
    assert Capability.FRONTEND in caps
    assert Capability.PREVIEW in caps


def test_capability_detector_frontend_and_backend():
    detector = CapabilityDetector()
    caps = detector.detect("cria uma aplicacao com frontend e backend")
    assert Capability.FRONTEND in caps
    assert Capability.BACKEND in caps
    assert Capability.PREVIEW in caps


def test_capability_detector_storage():
    detector = CapabilityDetector()
    caps = detector.detect("guarda os dados localmente no browser")
    assert Capability.STORAGE in caps
    assert Capability.FRONTEND in caps


def test_capability_detector_crud_dashboard_search():
    detector = CapabilityDetector()
    caps = detector.detect("dashboard CRUD com pesquisa e filtros para gestao de tarefas")
    assert Capability.DASHBOARD in caps
    assert Capability.CRUD in caps
    assert Capability.SEARCH in caps
    assert Capability.STORAGE in caps
    assert Capability.FRONTEND in caps


def test_capability_detector_explicit_negation():
    detector = CapabilityDetector()
    caps = detector.detect("cria um servidor backend em python sem frontend e sem login")
    assert Capability.BACKEND in caps
    assert Capability.FRONTEND not in caps
    assert Capability.AUTH not in caps


def test_artifact_inference_frontend_artifacts():
    engine = ArtifactInferenceEngine()
    result = engine.infer("cria uma pagina web simples de tarefas", project_name="todo-app")

    assert result.has_capability(Capability.FRONTEND)
    assert result.has_capability(Capability.CRUD)

    paths = result.required_paths()
    assert "index.html" in paths
    assert "styles.css" in paths
    assert "app.js" in paths

    html_art = result.get_artifact("index.html")
    assert html_art is not None
    assert "<!DOCTYPE html>" in html_art.default_content
    assert "Todo App" in html_art.default_content
    assert "styles.css" in html_art.default_content

    js_art = result.get_artifact("app.js")
    assert js_art is not None
    assert "addEventListener" in js_art.default_content
    assert "localStorage" in js_art.default_content


def test_artifact_inference_backend_artifacts():
    engine = ArtifactInferenceEngine()
    result = engine.infer("cria um backend api com servidor python", project_name="api-service")

    assert result.has_capability(Capability.BACKEND)
    paths = result.required_paths()
    assert "server.py" in paths

    server_art = result.get_artifact("server.py")
    assert server_art is not None
    assert "/health" in server_art.default_content
    assert "HTTPServer" in server_art.default_content


def test_deterministic_repair_missing_index_html():
    repair_engine = DeterministicRepairEngine()
    planned_files = {
        "styles.css": "body { background: #000; }",
        "app.js": "console.log('running');",
    }

    result = repair_engine.repair_plan(
        prompt="cria uma pagina web com estilo",
        planned_files=planned_files,
        project_name="test-web",
    )

    assert result.repaired is True
    assert "index.html" in result.missing_before
    assert "index.html" in result.repaired_files
    assert "<!DOCTYPE html>" in result.repaired_files["index.html"]
    assert any(a.action_type == "CREATE_FILE" and a.relative_path == "index.html" for a in result.actions)


def test_deterministic_repair_missing_css_and_js():
    repair_engine = DeterministicRepairEngine()
    planned_files = {
        "index.html": "<!DOCTYPE html><html><body><h1>Teste</h1></body></html>",
    }

    result = repair_engine.repair_plan(
        prompt="faz uma app web completa",
        planned_files=planned_files,
        project_name="my-app",
    )

    assert result.repaired is True
    assert "styles.css" in result.missing_before
    assert "app.js" in result.missing_before
    assert "styles.css" in result.repaired_files
    assert "app.js" in result.repaired_files


def test_deterministic_repair_patch_contracts():
    repair_engine = DeterministicRepairEngine()
    planned_files = {
        "index.html": "<html><head><title>App</title></head><body><h1>Ola</h1></body></html>",
        "styles.css": "body { margin: 0; box-sizing: border-box; }",
        "app.js": "document.addEventListener('DOMContentLoaded', () => { console.log('ok'); });",
    }

    result = repair_engine.repair_plan(
        prompt="guarda os dados da pagina com persistencia local",
        planned_files=planned_files,
        project_name="storage-app",
    )

    assert result.repaired is True
    # Verify <!DOCTYPE html> was injected
    assert "<!DOCTYPE html>" in result.repaired_files["index.html"]
    # Verify localStorage helpers were injected into app.js
    assert "localStorage" in result.repaired_files["app.js"]


def test_deterministic_repair_no_op_when_complete():
    repair_engine = DeterministicRepairEngine()
    engine = ArtifactInferenceEngine()
    inference = engine.infer("pagina web simples", project_name="complete-app")

    planned_files = {
        art.relative_path: art.default_content
        for art in inference.required_artifacts
    }

    result = repair_engine.repair_plan(
        prompt="pagina web simples",
        planned_files=planned_files,
        project_name="complete-app",
    )

    assert result.repaired is False
    assert len(result.actions) == 0
    assert len(result.missing_before) == 0
