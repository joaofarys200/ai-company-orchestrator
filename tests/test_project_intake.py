"""
JARVIS OS — Test Suite: Project Intake & Stack Discovery Engine (Fase 10.5)
Verifica a deteção determinística de stacks, entrypoints, packages, dependências e evidências.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
import tempfile
import shutil

from intelligence.project_intake import (
    ProjectIntakeService,
    EvidenceStatus,
    EntrypointInfo,
)


@pytest.fixture
def intake_service(tmp_path: Path) -> ProjectIntakeService:
    from intelligence.project_context import ProjectContextService
    ctx_service = ProjectContextService(workspace_root=str(tmp_path))
    return ProjectIntakeService(project_context_service=ctx_service, workspace_root=str(tmp_path))


def test_detect_stack_python_fastapi(tmp_path: Path, intake_service: ProjectIntakeService):
    """Testa a deteção de stack Python com FastAPI e Pytest com evidências declaradas."""
    proj_dir = tmp_path / "workspace" / "projects" / "fastapi-demo"
    proj_dir.mkdir(parents=True)

    pyproject_content = """[project]
name = "fastapi-demo"
version = "0.1.0"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "pydantic>=2.0"
]

[project.scripts]
api-server = "fastapi_demo.main:run"
"""
    (proj_dir / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")
    (proj_dir / "requirements.txt").write_text("pytest>=7.0.0\npytest-asyncio\n", encoding="utf-8")
    (proj_dir / "server.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")

    stack = intake_service.detect_stack(proj_dir)

    assert "Python" in stack["languages"]
    assert "FastAPI" in stack["frameworks"]
    assert "pip" in stack["package_managers"]
    assert "Pytest" in stack["test_frameworks"]

    # Verificar evidências
    evidence = stack["evidence"]
    assert "Python" in evidence
    assert evidence["Python"]["confidence"] == 1.0
    assert evidence["Python"]["status"] == EvidenceStatus.VERIFIED.value
    assert "FastAPI" in evidence
    assert evidence["FastAPI"]["confidence"] == 1.0


def test_detect_stack_typescript_react_vite(tmp_path: Path, intake_service: ProjectIntakeService):
    """Testa a deteção de stack TypeScript com React, Tailwind, Vite, Vitest e Docker."""
    proj_dir = tmp_path / "workspace" / "projects" / "react-vite-app"
    proj_dir.mkdir(parents=True)

    pkg_json = {
        "name": "react-vite-app",
        "version": "1.0.0",
        "main": "dist/index.js",
        "scripts": {
            "dev": "vite",
            "build": "tsc && vite build",
            "test": "vitest"
        },
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "tailwindcss": "^3.3.0"
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "vite": "^4.4.0",
            "vitest": "^0.34.0"
        }
    }
    (proj_dir / "package.json").write_text(json.dumps(pkg_json), encoding="utf-8")
    (proj_dir / "tsconfig.json").write_text("{}", encoding="utf-8")
    (proj_dir / "vite.config.ts").write_text("export default {}", encoding="utf-8")
    (proj_dir / "Dockerfile").write_text("FROM node:20\nWORKDIR /app\n", encoding="utf-8")

    src_dir = proj_dir / "src"
    src_dir.mkdir()
    (src_dir / "main.tsx").write_text("import React from 'react';", encoding="utf-8")
    (src_dir / "App.tsx").write_text("export function App() { return <div>Hello</div>; }", encoding="utf-8")

    stack = intake_service.detect_stack(proj_dir)

    assert "TypeScript" in stack["languages"]
    assert "React" in stack["frameworks"]
    assert "TailwindCSS" in stack["frameworks"]
    assert "Vite" in stack["build_tools"]
    assert "tsc" in stack["build_tools"]
    assert "Vitest" in stack["test_frameworks"]
    assert "Docker" in stack["containerization"]

    # Entrypoints
    files = ["package.json", "tsconfig.json", "vite.config.ts", "Dockerfile", "src/main.tsx", "src/App.tsx"]
    entrypoints = intake_service.discover_entrypoints(proj_dir, stack, files)
    
    ep_paths = [ep.path for ep in entrypoints]
    assert "src/main.tsx" in ep_paths
    
    main_ep = next(ep for ep in entrypoints if ep.path == "src/main.tsx")
    assert main_ep.kind == "FRONTEND"
    assert main_ep.confidence >= 0.85


def test_discover_monorepo_packages(tmp_path: Path, intake_service: ProjectIntakeService):
    """Testa a descoberta de workspaces e topologia em monorepos."""
    proj_dir = tmp_path / "workspace" / "projects" / "monorepo-app"
    proj_dir.mkdir(parents=True)

    root_pkg = {
        "name": "root-monorepo",
        "private": True,
        "workspaces": ["packages/*", "apps/*"]
    }
    (proj_dir / "package.json").write_text(json.dumps(root_pkg), encoding="utf-8")

    pkg_core = proj_dir / "packages" / "core"
    pkg_core.mkdir(parents=True)
    (pkg_core / "package.json").write_text(json.dumps({"name": "@mono/core", "version": "1.0.0"}), encoding="utf-8")

    app_web = proj_dir / "apps" / "web"
    app_web.mkdir(parents=True)
    (app_web / "package.json").write_text(json.dumps({
        "name": "@mono/web",
        "version": "1.0.0",
        "dependencies": {"@mono/core": "1.0.0"}
    }), encoding="utf-8")

    packages = intake_service.discover_packages(proj_dir)
    pkg_names = [p.name for p in packages]
    
    assert "@mono/core" in pkg_names
    assert "@mono/web" in pkg_names


def test_discover_services_classification(tmp_path: Path, intake_service: ProjectIntakeService):
    """Testa o agrupamento correto de ficheiros nas categorias canónicas do sistema."""
    proj_dir = tmp_path / "workspace" / "projects" / "fullstack-service"
    proj_dir.mkdir(parents=True)

    files = [
        "frontend/src/App.tsx",
        "frontend/src/index.css",
        "backend/main.py",
        "backend/database.py",
        "tests/test_api.py",
        "package.json",
        "shared/types.ts",
    ]

    entrypoints = [
        EntrypointInfo(path="frontend/src/App.tsx", kind="FRONTEND", source="react", confidence=0.9, resolution_method="convention"),
        EntrypointInfo(path="backend/main.py", kind="BACKEND", source="fastapi", confidence=0.9, resolution_method="convention"),
    ]

    services = intake_service.discover_services(proj_dir, files, entrypoints)
    cats = {s.category: s for s in services}

    assert "FRONTEND" in cats
    assert "BACKEND" in cats
    assert "DATABASE" in cats
    assert "TESTS" in cats
    assert "BUILD" in cats
    assert "SHARED" in cats
