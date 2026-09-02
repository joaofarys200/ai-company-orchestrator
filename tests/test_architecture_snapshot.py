"""
JARVIS OS — Test Suite: Architecture Snapshot Serialization & Schema Validation (Fase 10.5)
Verifica a conformidade com o schema JSON Draft-07, persistência e carregamento de snapshots.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from intelligence.project_intake import ProjectIntakeService, ArchitectureSnapshot

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def intake_service(tmp_path: Path) -> ProjectIntakeService:
    from intelligence.project_context import ProjectContextService
    ctx_service = ProjectContextService(workspace_root=str(tmp_path))
    return ProjectIntakeService(project_context_service=ctx_service, workspace_root=str(tmp_path))


def test_architecture_snapshot_schema_conformance(tmp_path: Path, intake_service: ProjectIntakeService):
    """Gera um snapshot real e valida a conformidade estrita com schemas/project-architecture-snapshot.schema.json."""
    proj_dir = tmp_path / "workspace" / "projects" / "snapshot-test-app"
    proj_dir.mkdir(parents=True)

    (proj_dir / "main.py").write_text("class Calculator:\n    def add(self, a, b):\n        return a + b\n", encoding="utf-8")
    (proj_dir / "requirements.txt").write_text("pytest>=7.0.0\n", encoding="utf-8")

    snapshot = intake_service.build_snapshot("snapshot-test-app")
    snapshot_dict = snapshot.to_dict()

    schema_file = REPO_ROOT / "schemas" / "project-architecture-snapshot.schema.json"
    assert schema_file.exists(), "Schema file must exist"

    schema_data = json.loads(schema_file.read_text(encoding="utf-8"))

    # Validar campos obrigatórios declarados no schema
    for req_field in schema_data.get("required", []):
        assert req_field in snapshot_dict, f"Missing required field in snapshot: {req_field}"

    assert snapshot.project["project_id"] == "snapshot-test-app"
    assert "Python" in snapshot.stack["languages"]
    assert snapshot.symbols["classes_count"] >= 1
    assert snapshot.symbols["functions_count"] >= 1
    assert snapshot.snapshot_hash != ""
    assert snapshot.confidence > 0.0


def test_snapshot_persistence_and_roundtrip(tmp_path: Path, intake_service: ProjectIntakeService):
    """Testa a escrita e carregamento idêntico de um snapshot a partir do disco."""
    proj_dir = tmp_path / "workspace" / "projects" / "roundtrip-app"
    proj_dir.mkdir(parents=True)

    (proj_dir / "app.js").write_text("function start() { console.log('started'); }", encoding="utf-8")
    (proj_dir / "package.json").write_text(json.dumps({"name": "roundtrip-app", "version": "1.0.0"}), encoding="utf-8")

    snapshot = intake_service.build_snapshot("roundtrip-app")
    
    # Verificar se o ficheiro foi salvo em .jarvis
    expected_path = tmp_path / "workspace" / ".jarvis" / "projects" / "roundtrip-app" / "architecture_snapshot.json"
    assert expected_path.is_file(), f"Snapshot file not created at {expected_path}"

    loaded_snapshot = intake_service.load_snapshot("roundtrip-app")
    assert loaded_snapshot is not None
    assert loaded_snapshot.project["project_id"] == snapshot.project["project_id"]
    assert loaded_snapshot.snapshot_hash == snapshot.snapshot_hash
    assert loaded_snapshot.stack == snapshot.stack
    assert len(loaded_snapshot.files) == len(snapshot.files)


def test_architecture_summary_generation(tmp_path: Path, intake_service: ProjectIntakeService):
    """Verifica a geração da árvore de componentes PROJECT ├── FRONTEND ├── BACKEND..."""
    proj_dir = tmp_path / "workspace" / "projects" / "summary-app"
    proj_dir.mkdir(parents=True)

    backend_dir = proj_dir / "backend"
    backend_dir.mkdir()
    (backend_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()", encoding="utf-8")

    frontend_dir = proj_dir / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "App.tsx").write_text("export function App() {}", encoding="utf-8")

    snapshot = intake_service.build_snapshot("summary-app")
    arch_summary = snapshot.architecture

    assert "summary_tree" in arch_summary
    assert "data_flows" in arch_summary
    assert "SUMMARY-APP" in arch_summary["summary_tree"]
    assert "FRONTEND" in arch_summary["summary_tree"]
    assert "BACKEND" in arch_summary["summary_tree"]
    assert len(arch_summary["data_flows"]) > 0
