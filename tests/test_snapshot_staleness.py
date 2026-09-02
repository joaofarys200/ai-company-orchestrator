"""
JARVIS OS — Test Suite: Snapshot Staleness & Freshness Detection Engine (Fase 10.5)
Verifica os estados FRESH, PARTIALLY_STALE e STALE sob diferentes cenários de mutação.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from intelligence.project_intake import (
    ProjectIntakeService,
    StalenessStatus,
)


@pytest.fixture
def intake_service(tmp_path: Path) -> ProjectIntakeService:
    from intelligence.project_context import ProjectContextService
    ctx_service = ProjectContextService(workspace_root=str(tmp_path))
    return ProjectIntakeService(project_context_service=ctx_service, workspace_root=str(tmp_path))


def test_staleness_missing_snapshot(intake_service: ProjectIntakeService):
    """Snapshot ausente retorna STALE."""
    res = intake_service.check_staleness("nonexistent-app")
    assert res.status == StalenessStatus.STALE.value
    assert res.reason == "snapshot_missing"


def test_staleness_fresh_project(tmp_path: Path, intake_service: ProjectIntakeService):
    """Projeto acabado de indexar deve retornar FRESH."""
    proj_dir = tmp_path / "workspace" / "projects" / "fresh-app"
    proj_dir.mkdir(parents=True)

    (proj_dir / "calc.py").write_text("def mul(a, b): return a * b\n", encoding="utf-8")
    (proj_dir / "requirements.txt").write_text("pytest\n", encoding="utf-8")

    intake_service.build_snapshot("fresh-app")

    res = intake_service.check_staleness("fresh-app")
    assert res.status == StalenessStatus.FRESH.value
    assert res.changed_files == []
    assert not res.config_changed


def test_staleness_single_source_file_modification(tmp_path: Path, intake_service: ProjectIntakeService):
    """Alteração num único ficheiro de código deve retornar PARTIALLY_STALE."""
    proj_dir = tmp_path / "workspace" / "projects" / "partial-app"
    proj_dir.mkdir(parents=True)

    (proj_dir / "file1.py").write_text("def f1(): pass\n", encoding="utf-8")
    (proj_dir / "file2.py").write_text("def f2(): pass\n", encoding="utf-8")
    (proj_dir / "file3.py").write_text("def f3(): pass\n", encoding="utf-8")
    (proj_dir / "file4.py").write_text("def f4(): pass\n", encoding="utf-8")
    (proj_dir / "file5.py").write_text("def f5(): pass\n", encoding="utf-8")

    intake_service.build_snapshot("partial-app")

    # Modificar apenas file1.py
    (proj_dir / "file1.py").write_text("def f1(): return 42\n", encoding="utf-8")

    res = intake_service.check_staleness("partial-app")
    assert res.status == StalenessStatus.PARTIALLY_STALE.value
    assert "file1.py" in res.changed_files
    assert not res.config_changed


def test_staleness_config_manifest_modification(tmp_path: Path, intake_service: ProjectIntakeService):
    """Alteração em package.json ou pyproject.toml deve forçar STALE para reindexação completa."""
    proj_dir = tmp_path / "workspace" / "projects" / "config-stale-app"
    proj_dir.mkdir(parents=True)

    (proj_dir / "index.js").write_text("console.log('hi');", encoding="utf-8")
    (proj_dir / "package.json").write_text(json.dumps({"name": "app", "dependencies": {}}), encoding="utf-8")

    intake_service.build_snapshot("config-stale-app")

    # Modificar o manifesto package.json
    (proj_dir / "package.json").write_text(json.dumps({"name": "app", "dependencies": {"express": "^4.18.2"}}), encoding="utf-8")

    res = intake_service.check_staleness("config-stale-app")
    assert res.status == StalenessStatus.STALE.value
    assert res.config_changed is True
    assert res.reason == "configuration_manifest_changed"
