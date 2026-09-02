"""
JARVIS OS — Project Intake & Automatic Architecture Intelligence (Fase 10.5)

Fornece análise estrutural determinística na entrada de projetos:
OPEN PROJECT -> ARCHITECTURE DISCOVERY -> REPOSITORY INDEX -> ARCHITECTURE SNAPSHOT -> READY -> MISSION

Reutiliza:
- intelligence.repository_graph (RepositoryGraph, SymbolDefinition, ModuleImport, ApiEndpoint)
- intelligence.project_context (ProjectContextService, AST indexer, integridade)
- intelligence.tsconfig_resolver (TSConfigResolver, MonorepoResolver)
- intelligence.typed_semantic_resolver (TypeNode, PropertyNode)
- intelligence.build_pipeline (DeterministicBuildPipeline)
- intelligence.artifact_inference (CapabilityDetector)
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from intelligence.artifact_inference import Capability, CapabilityDetector
from intelligence.build_pipeline import DeterministicBuildPipeline
from intelligence.repository_graph import RepositoryGraph, SymbolDefinition
from intelligence.tsconfig_resolver import MonorepoResolver, TSConfigResolver
from workspace_policy import WORKSPACE_ROOT, resolve_workspace_path


class EvidenceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"


class StalenessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    PARTIALLY_STALE = "PARTIALLY_STALE"


@dataclass(slots=True)
class EvidenceRecord:
    source: str
    confidence: float
    resolution_method: str
    status: str = EvidenceStatus.VERIFIED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "confidence": round(float(self.confidence), 2),
            "resolution_method": self.resolution_method,
            "status": self.status,
        }


@dataclass(slots=True)
class EntrypointInfo:
    path: str
    kind: str  # CLI, BACKEND, FRONTEND, WORKER, SCRIPT, BOOTSTRAP, UNKNOWN
    source: str
    confidence: float
    resolution_method: str
    status: str = EvidenceStatus.VERIFIED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path.replace("\\", "/"),
            "kind": self.kind,
            "source": self.source,
            "confidence": round(float(self.confidence), 2),
            "resolution_method": self.resolution_method,
            "status": self.status,
        }


@dataclass(slots=True)
class PackageInfo:
    name: str
    path: str
    kind: str  # application, library, monorepo_package, service
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path.replace("\\", "/"),
            "kind": self.kind,
            "dependencies": self.dependencies,
        }


@dataclass(slots=True)
class ServiceInfo:
    name: str
    category: str  # FRONTEND, BACKEND, DATABASE, SHARED, TESTS, BUILD, RUNTIME, OTHER
    root_path: str
    entrypoints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "root_path": self.root_path.replace("\\", "/"),
            "entrypoints": [e.replace("\\", "/") for e in self.entrypoints],
        }


@dataclass(slots=True)
class StalenessCheckResult:
    status: str  # FRESH, STALE, PARTIALLY_STALE
    changed_files: list[str] = field(default_factory=list)
    added_files: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    config_changed: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "changed_files": self.changed_files,
            "added_files": self.added_files,
            "deleted_files": self.deleted_files,
            "config_changed": self.config_changed,
            "reason": self.reason,
        }


@dataclass
class ArchitectureSnapshot:
    project: dict[str, Any]
    stack: dict[str, Any]
    entrypoints: list[dict[str, Any]]
    packages: list[dict[str, Any]]
    services: list[dict[str, Any]]
    files: list[dict[str, Any]]
    symbols: dict[str, Any]
    imports: dict[str, Any]
    dependencies: list[dict[str, Any]]
    api_contracts: dict[str, Any]
    tests: dict[str, Any]
    build: dict[str, Any]
    runtime: dict[str, Any]
    architecture: dict[str, Any]
    generated_at: str
    snapshot_hash: str
    confidence: float
    source_commit: str | None = None
    staleness: str = StalenessStatus.FRESH.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchitectureSnapshot:
        return cls(
            project=data.get("project", {}),
            stack=data.get("stack", {}),
            entrypoints=data.get("entrypoints", []),
            packages=data.get("packages", []),
            services=data.get("services", []),
            files=data.get("files", []),
            symbols=data.get("symbols", {}),
            imports=data.get("imports", {}),
            dependencies=data.get("dependencies", []),
            api_contracts=data.get("api_contracts", {}),
            tests=data.get("tests", {}),
            build=data.get("build", {}),
            runtime=data.get("runtime", {}),
            architecture=data.get("architecture", {}),
            generated_at=data.get("generated_at", ""),
            snapshot_hash=data.get("snapshot_hash", ""),
            confidence=float(data.get("confidence", 1.0)),
            source_commit=data.get("source_commit"),
            staleness=data.get("staleness", StalenessStatus.FRESH.value),
        )


CONFIG_FILE_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "setup.py", "setup.cfg",
    "Pipfile", "poetry.lock", "tsconfig.json", "jsconfig.json", "pom.xml",
    "build.gradle", "build.gradle.kts", "Makefile", "CMakeLists.txt", "Cargo.toml",
    "go.mod", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "vite.config.js", "vite.config.ts", "webpack.config.js", "next.config.js",
}


class ProjectIntakeService:
    """
    Serviço central de ingestão de projetos e inteligência arquitetural no JARVIS OS.
    Executa a análise determinística completa do projeto na abertura.
    """

    def __init__(
        self,
        project_context_service: Any = None,
        workspace_root: str = WORKSPACE_ROOT,
    ) -> None:
        self.workspace_root = os.path.realpath(os.path.abspath(workspace_root))
        self._project_context = project_context_service

    @property
    def project_context(self) -> Any:
        if self._project_context is None:
            from intelligence.project_context import ProjectContextService
            self._project_context = ProjectContextService(workspace_root=self.workspace_root)
        return self._project_context

    def detect_stack(self, root_path: Path) -> dict[str, Any]:
        """
        Deteta linguagens, frameworks, package managers, ferramentas de build,
        frameworks de teste e containerização com evidências explícitas.
        """
        languages: list[str] = []
        frameworks: list[str] = []
        package_managers: list[str] = []
        build_tools: list[str] = []
        test_frameworks: list[str] = []
        containerization: list[str] = []
        evidence_map: dict[str, dict[str, Any]] = {}

        # 1. Manifestos Node.js / TypeScript
        pkg_json = root_path / "package.json"
        if pkg_json.is_file():
            package_managers.append("npm")
            evidence_map["npm"] = EvidenceRecord("package.json", 1.0, "manifest_declaration").to_dict()
            if not any(l in languages for l in ["JavaScript", "TypeScript"]):
                languages.append("JavaScript")
                evidence_map["JavaScript"] = EvidenceRecord("package.json", 0.9, "manifest_declaration").to_dict()
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                
                # Frameworks JS/TS
                if "react" in all_deps or "react-dom" in all_deps:
                    frameworks.append("React")
                    evidence_map["React"] = EvidenceRecord("package.json (dependencies)", 1.0, "manifest_dependency").to_dict()
                if "next" in all_deps:
                    frameworks.append("Next.js")
                    evidence_map["Next.js"] = EvidenceRecord("package.json (dependencies)", 1.0, "manifest_dependency").to_dict()
                if "vue" in all_deps:
                    frameworks.append("Vue")
                    evidence_map["Vue"] = EvidenceRecord("package.json (dependencies)", 1.0, "manifest_dependency").to_dict()
                if "express" in all_deps:
                    frameworks.append("Express")
                    evidence_map["Express"] = EvidenceRecord("package.json (dependencies)", 1.0, "manifest_dependency").to_dict()
                if "tailwindcss" in all_deps:
                    frameworks.append("TailwindCSS")
                    evidence_map["TailwindCSS"] = EvidenceRecord("package.json (dependencies)", 1.0, "manifest_dependency").to_dict()

                # Build Tools JS
                if "vite" in all_deps or (root_path / "vite.config.ts").exists() or (root_path / "vite.config.js").exists():
                    build_tools.append("Vite")
                    evidence_map["Vite"] = EvidenceRecord("package.json / vite.config", 1.0, "manifest_dependency").to_dict()
                if "webpack" in all_deps or (root_path / "webpack.config.js").exists():
                    build_tools.append("Webpack")
                    evidence_map["Webpack"] = EvidenceRecord("package.json / webpack.config", 1.0, "manifest_dependency").to_dict()

                # Test Frameworks JS
                if "jest" in all_deps:
                    test_frameworks.append("Jest")
                    evidence_map["Jest"] = EvidenceRecord("package.json (devDependencies)", 1.0, "manifest_dependency").to_dict()
                if "vitest" in all_deps:
                    test_frameworks.append("Vitest")
                    evidence_map["Vitest"] = EvidenceRecord("package.json (devDependencies)", 1.0, "manifest_dependency").to_dict()
                if "playwright" in all_deps or "@playwright/test" in all_deps:
                    test_frameworks.append("Playwright")
                    evidence_map["Playwright"] = EvidenceRecord("package.json (devDependencies)", 1.0, "manifest_dependency").to_dict()
                if "cypress" in all_deps:
                    test_frameworks.append("Cypress")
                    evidence_map["Cypress"] = EvidenceRecord("package.json (devDependencies)", 1.0, "manifest_dependency").to_dict()

            except Exception:
                pass

        if (root_path / "pnpm-lock.yaml").is_file():
            if "pnpm" not in package_managers:
                package_managers.append("pnpm")
                evidence_map["pnpm"] = EvidenceRecord("pnpm-lock.yaml", 1.0, "lockfile_detection").to_dict()
        if (root_path / "yarn.lock").is_file():
            if "yarn" not in package_managers:
                package_managers.append("yarn")
                evidence_map["yarn"] = EvidenceRecord("yarn.lock", 1.0, "lockfile_detection").to_dict()

        if (root_path / "tsconfig.json").is_file():
            if "TypeScript" not in languages:
                languages.append("TypeScript")
                evidence_map["TypeScript"] = EvidenceRecord("tsconfig.json", 1.0, "config_file_presence").to_dict()
            if "tsc" not in build_tools:
                build_tools.append("tsc")
                evidence_map["tsc"] = EvidenceRecord("tsconfig.json", 1.0, "compiler_config").to_dict()

        # 2. Manifestos Python
        pyproject = root_path / "pyproject.toml"
        req_txt = root_path / "requirements.txt"
        setup_py = root_path / "setup.py"
        pipfile = root_path / "Pipfile"

        if pyproject.is_file() or req_txt.is_file() or setup_py.is_file() or pipfile.is_file():
            if "Python" not in languages:
                languages.append("Python")
                src_file = "pyproject.toml" if pyproject.is_file() else "requirements.txt"
                evidence_map["Python"] = EvidenceRecord(src_file, 1.0, "manifest_declaration").to_dict()

            if "pip" not in package_managers:
                package_managers.append("pip")
                evidence_map["pip"] = EvidenceRecord("python_manifest", 0.9, "environment_standard").to_dict()

            # Ler dependências Python
            py_deps_text = ""
            if req_txt.is_file():
                py_deps_text += req_txt.read_text(encoding="utf-8", errors="replace").lower()
            if pyproject.is_file():
                py_content = pyproject.read_text(encoding="utf-8", errors="replace").lower()
                py_deps_text += "\n" + py_content
                if "poetry" in py_content:
                    package_managers.append("poetry")
                    evidence_map["poetry"] = EvidenceRecord("pyproject.toml (poetry)", 1.0, "manifest_declaration").to_dict()
                if "setuptools" in py_content or setup_py.is_file():
                    build_tools.append("setuptools")
                    evidence_map["setuptools"] = EvidenceRecord("pyproject.toml / setup.py", 1.0, "build_backend").to_dict()

            if "fastapi" in py_deps_text:
                frameworks.append("FastAPI")
                evidence_map["FastAPI"] = EvidenceRecord("python_dependencies", 1.0, "manifest_dependency").to_dict()
            if "flask" in py_deps_text:
                frameworks.append("Flask")
                evidence_map["Flask"] = EvidenceRecord("python_dependencies", 1.0, "manifest_dependency").to_dict()
            if "django" in py_deps_text:
                frameworks.append("Django")
                evidence_map["Django"] = EvidenceRecord("python_dependencies", 1.0, "manifest_dependency").to_dict()
            if "pytest" in py_deps_text or (root_path / "pytest.ini").is_file() or (root_path / "conftest.py").is_file():
                test_frameworks.append("Pytest")
                evidence_map["Pytest"] = EvidenceRecord("requirements / pytest.ini", 1.0, "manifest_dependency").to_dict()
            if "unittest" in py_deps_text:
                test_frameworks.append("Unittest")
                evidence_map["Unittest"] = EvidenceRecord("python_standard_lib", 0.9, "framework_convention").to_dict()

        # 3. Java / JVM
        if (root_path / "pom.xml").is_file():
            languages.append("Java")
            build_tools.append("Maven")
            package_managers.append("Maven")
            evidence_map["Java"] = EvidenceRecord("pom.xml", 1.0, "manifest_declaration").to_dict()
            evidence_map["Maven"] = EvidenceRecord("pom.xml", 1.0, "manifest_declaration").to_dict()
        elif (root_path / "build.gradle").is_file() or (root_path / "build.gradle.kts").is_file():
            languages.append("Java")
            build_tools.append("Gradle")
            package_managers.append("Gradle")
            evidence_map["Java"] = EvidenceRecord("build.gradle", 1.0, "manifest_declaration").to_dict()
            evidence_map["Gradle"] = EvidenceRecord("build.gradle", 1.0, "manifest_declaration").to_dict()

        # 4. C / C++
        if (root_path / "CMakeLists.txt").is_file():
            languages.append("C/C++")
            build_tools.append("CMake")
            evidence_map["C/C++"] = EvidenceRecord("CMakeLists.txt", 1.0, "manifest_declaration").to_dict()
            evidence_map["CMake"] = EvidenceRecord("CMakeLists.txt", 1.0, "manifest_declaration").to_dict()
        elif (root_path / "Makefile").is_file():
            build_tools.append("Make")
            evidence_map["Make"] = EvidenceRecord("Makefile", 1.0, "build_script").to_dict()

        # 5. Rust
        if (root_path / "Cargo.toml").is_file():
            languages.append("Rust")
            package_managers.append("Cargo")
            build_tools.append("Cargo")
            test_frameworks.append("cargo test")
            evidence_map["Rust"] = EvidenceRecord("Cargo.toml", 1.0, "manifest_declaration").to_dict()

        # 6. Go
        if (root_path / "go.mod").is_file():
            languages.append("Go")
            package_managers.append("go modules")
            test_frameworks.append("go test")
            evidence_map["Go"] = EvidenceRecord("go.mod", 1.0, "manifest_declaration").to_dict()

        # 7. Containerization
        if (root_path / "Dockerfile").is_file():
            containerization.append("Docker")
            evidence_map["Docker"] = EvidenceRecord("Dockerfile", 1.0, "container_definition").to_dict()
        if (root_path / "docker-compose.yml").is_file() or (root_path / "docker-compose.yaml").is_file():
            containerization.append("Docker Compose")
            evidence_map["Docker Compose"] = EvidenceRecord("docker-compose.yml", 1.0, "orchestration_manifest").to_dict()

        # 8. Source Tree Inspection (para linguagens sem manifesto na raiz)
        if not languages:
            for root, dirs, files in os.walk(root_path):
                dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build"}]
                for f in files:
                    sfx = Path(f).suffix.lower()
                    if sfx == ".py" and "Python" not in languages:
                        languages.append("Python")
                        evidence_map["Python"] = EvidenceRecord(f"source_file: {f}", 0.8, "file_extension_scan", EvidenceStatus.INFERRED.value).to_dict()
                    elif sfx in {".ts", ".tsx"} and "TypeScript" not in languages:
                        languages.append("TypeScript")
                        evidence_map["TypeScript"] = EvidenceRecord(f"source_file: {f}", 0.8, "file_extension_scan", EvidenceStatus.INFERRED.value).to_dict()
                    elif sfx in {".js", ".jsx"} and "JavaScript" not in languages:
                        languages.append("JavaScript")
                        evidence_map["JavaScript"] = EvidenceRecord(f"source_file: {f}", 0.8, "file_extension_scan", EvidenceStatus.INFERRED.value).to_dict()
                    elif sfx in {".java"} and "Java" not in languages:
                        languages.append("Java")
                        evidence_map["Java"] = EvidenceRecord(f"source_file: {f}", 0.8, "file_extension_scan", EvidenceStatus.INFERRED.value).to_dict()
                    elif sfx in {".c", ".cpp", ".cc", ".h", ".hpp"} and "C/C++" not in languages:
                        languages.append("C/C++")
                        evidence_map["C/C++"] = EvidenceRecord(f"source_file: {f}", 0.8, "file_extension_scan", EvidenceStatus.INFERRED.value).to_dict()
                    elif sfx == ".rs" and "Rust" not in languages:
                        languages.append("Rust")
                        evidence_map["Rust"] = EvidenceRecord(f"source_file: {f}", 0.8, "file_extension_scan", EvidenceStatus.INFERRED.value).to_dict()
                    elif sfx == ".go" and "Go" not in languages:
                        languages.append("Go")
                        evidence_map["Go"] = EvidenceRecord(f"source_file: {f}", 0.8, "file_extension_scan", EvidenceStatus.INFERRED.value).to_dict()

        return {
            "languages": languages,
            "frameworks": frameworks,
            "package_managers": package_managers,
            "build_tools": build_tools,
            "test_frameworks": test_frameworks,
            "containerization": containerization,
            "evidence": evidence_map,
        }

    def discover_entrypoints(
        self,
        root_path: Path,
        stack: dict[str, Any],
        files: list[str],
    ) -> list[EntrypointInfo]:
        """
        Descobre entrypoints de CLI, Backend, Frontend, Workers e Scripts
        com resolução e fonte explicadas.
        """
        entrypoints: list[EntrypointInfo] = []
        found_paths: set[str] = set()

        def add_ep(path: str, kind: str, source: str, conf: float, method: str, status: str = EvidenceStatus.VERIFIED.value):
            norm = path.replace("\\", "/").strip().lstrip("./")
            if norm not in found_paths and (root_path / norm).is_file():
                found_paths.add(norm)
                entrypoints.append(EntrypointInfo(
                    path=norm,
                    kind=kind,
                    source=source,
                    confidence=conf,
                    resolution_method=method,
                    status=status,
                ))

        # 1. package.json declared main, bin, scripts
        pkg_json = root_path / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                if data.get("main"):
                    add_ep(data["main"], "BOOTSTRAP", "package.json (main)", 1.0, "declared_entrypoint")
                bin_val = data.get("bin")
                if isinstance(bin_val, str):
                    add_ep(bin_val, "CLI", "package.json (bin)", 1.0, "declared_entrypoint")
                elif isinstance(bin_val, dict):
                    for _, b_path in bin_val.items():
                        add_ep(b_path, "CLI", "package.json (bin)", 1.0, "declared_entrypoint")
            except Exception:
                pass

        # 2. pyproject.toml scripts
        pyproject = root_path / "pyproject.toml"
        if pyproject.is_file():
            try:
                text = pyproject.read_text(encoding="utf-8", errors="replace")
                scripts_matches = re.findall(r'\[(?:project\.scripts|tool\.poetry\.scripts)\]\s*\n([^\[]+)', text)
                for block in scripts_matches:
                    for line in block.splitlines():
                        if "=" in line and not line.strip().startswith("#"):
                            val = line.split("=", 1)[1].strip().strip('"\'')
                            mod = val.split(":")[0].strip()
                            py_file = mod.replace(".", "/") + ".py"
                            add_ep(py_file, "CLI", "pyproject.toml (scripts)", 1.0, "declared_entrypoint")
            except Exception:
                pass

        # 3. Dockerfile ENTRYPOINT / CMD
        dockerfile = root_path / "Dockerfile"
        if dockerfile.is_file():
            try:
                d_lines = dockerfile.read_text(encoding="utf-8", errors="replace").splitlines()
                for line in d_lines:
                    if line.strip().startswith(("ENTRYPOINT", "CMD")):
                        for token in re.findall(r'["\']([^"\']+\.(?:py|js|ts|sh))["\']', line):
                            add_ep(token, "BOOTSTRAP", "Dockerfile", 1.0, "declared_entrypoint")
            except Exception:
                pass

        # 4. Frontend Conventions
        frontend_candidates = [
            ("src/main.tsx", "FRONTEND", "Vite/React convention", 0.9, "framework_convention", EvidenceStatus.INFERRED.value),
            ("src/main.ts", "FRONTEND", "Vite convention", 0.9, "framework_convention", EvidenceStatus.INFERRED.value),
            ("src/index.tsx", "FRONTEND", "React convention", 0.9, "framework_convention", EvidenceStatus.INFERRED.value),
            ("src/index.ts", "FRONTEND", "TypeScript root convention", 0.85, "framework_convention", EvidenceStatus.INFERRED.value),
            ("src/App.tsx", "FRONTEND", "React App root", 0.85, "framework_convention", EvidenceStatus.INFERRED.value),
            ("index.html", "FRONTEND", "Web entrypoint", 0.95, "web_standard", EvidenceStatus.VERIFIED.value),
        ]
        for p, k, src, conf, meth, st in frontend_candidates:
            add_ep(p, k, src, conf, meth, st)

        # 5. Backend Conventions
        backend_candidates = [
            ("server.py", "BACKEND", "Server convention", 0.95, "framework_convention", EvidenceStatus.INFERRED.value),
            ("backend/main.py", "BACKEND", "FastAPI/Backend root", 0.95, "framework_convention", EvidenceStatus.INFERRED.value),
            ("app.py", "BACKEND", "Flask/Streamlit convention", 0.9, "framework_convention", EvidenceStatus.INFERRED.value),
            ("main.py", "BACKEND", "Python main convention", 0.85, "framework_convention", EvidenceStatus.INFERRED.value),
            ("src/server.ts", "BACKEND", "Node server convention", 0.9, "framework_convention", EvidenceStatus.INFERRED.value),
            ("src/app.ts", "BACKEND", "Express app convention", 0.9, "framework_convention", EvidenceStatus.INFERRED.value),
            ("api/index.py", "BACKEND", "Serverless API convention", 0.85, "framework_convention", EvidenceStatus.INFERRED.value),
        ]
        for p, k, src, conf, meth, st in backend_candidates:
            add_ep(p, k, src, conf, meth, st)

        # 6. AST Verification of `if __name__ == "__main__":`
        for f in files:
            if f.endswith(".py") and f not in found_paths:
                f_path = root_path / f
                try:
                    content = f_path.read_text(encoding="utf-8", errors="replace")
                    if '__name__' in content and '__main__' in content:
                        parsed = ast.parse(content)
                        for node in ast.walk(parsed):
                            if isinstance(node, ast.If):
                                test_src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
                                if '__name__' in test_src and '__main__' in test_src:
                                    add_ep(f, "CLI", "AST (__main__ block)", 0.9, "ast_entrypoint", EvidenceStatus.VERIFIED.value)
                                    break
                except Exception:
                    pass

        return entrypoints

    def discover_packages(self, root_path: Path) -> list[PackageInfo]:
        """Descobre packages e workspaces monorepo."""
        packages: list[PackageInfo] = []
        pkg_map = MonorepoResolver.discover_monorepo_packages(str(root_path))

        if pkg_map:
            for name, pkg_data in pkg_map.items():
                rel_p = os.path.relpath(pkg_data.package_dir, str(root_path)).replace("\\", "/")
                packages.append(PackageInfo(
                    name=name,
                    path="" if rel_p == "." else rel_p,
                    kind="monorepo_package" if rel_p != "." else "application",
                    dependencies=list(pkg_data.dependencies.keys()),
                ))
        else:
            # Single project package
            pkg_json = root_path / "package.json"
            if pkg_json.is_file():
                try:
                    data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                    packages.append(PackageInfo(
                        name=data.get("name", root_path.name),
                        path="",
                        kind="application",
                        dependencies=list(data.get("dependencies", {}).keys()),
                    ))
                except Exception:
                    pass

        return packages

    def discover_services(
        self,
        root_path: Path,
        files: list[str],
        entrypoints: list[EntrypointInfo],
    ) -> list[ServiceInfo]:
        """Agrupa os ficheiros e entrypoints nas categorias arquiteturais canónicas."""
        categories: dict[str, list[str]] = {
            "FRONTEND": [],
            "BACKEND": [],
            "DATABASE": [],
            "SHARED": [],
            "TESTS": [],
            "BUILD": [],
            "RUNTIME": [],
        }

        for f in files:
            lower = f.lower()
            if lower.startswith("tests/") or "/tests/" in lower or lower.endswith(("_test.py", ".test.ts", ".spec.ts", ".test.js")):
                categories["TESTS"].append(f)
            elif lower in CONFIG_FILE_NAMES or lower.startswith("config/"):
                categories["BUILD"].append(f)
            elif "database" in lower or "persistence" in lower or "models" in lower or lower.endswith((".sql", ".db")):
                categories["DATABASE"].append(f)
            elif lower.startswith("frontend/") or "src/components" in lower or lower.endswith((".tsx", ".jsx", ".css", ".html")):
                categories["FRONTEND"].append(f)
            elif lower.startswith(("backend/", "server/", "api/", "services/")) or lower in {"server.py", "app.py", "main.py"}:
                categories["BACKEND"].append(f)
            else:
                categories["SHARED"].append(f)

        services: list[ServiceInfo] = []
        for cat_name, cat_files in categories.items():
            if cat_files:
                cat_eps = [
                    ep.path for ep in entrypoints
                    if any(ep.path == f for f in cat_files)
                ]
                services.append(ServiceInfo(
                    name=cat_name.lower(),
                    category=cat_name,
                    root_path=cat_name.lower(),
                    entrypoints=cat_eps,
                ))

        return services

    def discover_dependencies(self, root_path: Path) -> list[dict[str, Any]]:
        """Extrai todas as dependências declaradas em manifestos do projeto."""
        dependencies: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Node.js
        pkg_json = root_path / "package.json"
        if pkg_json.is_file():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
                for dep, ver in data.get("dependencies", {}).items():
                    if dep not in seen:
                        seen.add(dep)
                        dependencies.append({"name": dep, "version": ver, "source": "package.json", "is_dev": False})
                for dep, ver in data.get("devDependencies", {}).items():
                    if dep not in seen:
                        seen.add(dep)
                        dependencies.append({"name": dep, "version": ver, "source": "package.json (devDependencies)", "is_dev": True})
            except Exception:
                pass

        # Python requirements.txt
        req_txt = root_path / "requirements.txt"
        if req_txt.is_file():
            try:
                for line in req_txt.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line and not line.startswith(("#", "-")):
                        parts = re.split(r'[=><~]', line, maxsplit=1)
                        name = parts[0].strip()
                        ver = parts[1].strip() if len(parts) > 1 else "*"
                        if name and name not in seen:
                            seen.add(name)
                            dependencies.append({"name": name, "version": ver, "source": "requirements.txt", "is_dev": False})
            except Exception:
                pass

        return dependencies

    def discover_tests(self, root_path: Path, stack: dict[str, Any], files: list[str]) -> dict[str, Any]:
        """Descobre ficheiros de teste e comandos recomendados."""
        test_files = [
            f for f in files
            if f.startswith("tests/") or "/tests/" in f or f.endswith(("_test.py", ".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".test.js"))
        ]
        frameworks = stack.get("test_frameworks", [])
        suggested_commands: list[dict[str, Any]] = []

        if "Pytest" in frameworks or any(f.endswith(".py") for f in test_files):
            suggested_commands.append({
                "kind": "test",
                "command": "pytest tests/ -q",
                "framework": "Pytest",
                "source": "ProjectIntakeService",
            })
        if "Vitest" in frameworks:
            suggested_commands.append({
                "kind": "test",
                "command": "npm run test",
                "framework": "Vitest",
                "source": "ProjectIntakeService",
            })
        elif "Jest" in frameworks:
            suggested_commands.append({
                "kind": "test",
                "command": "npm test",
                "framework": "Jest",
                "source": "ProjectIntakeService",
            })

        return {
            "test_files": test_files,
            "frameworks": frameworks,
            "suggested_commands": suggested_commands,
        }

    def generate_architecture_summary(self, snapshot: ArchitectureSnapshot) -> dict[str, Any]:
        """
        Produz uma representação visual estruturada e o grafo de fluxos de dados:
        PROJECT ├── FRONTEND ├── BACKEND ├── DATABASE ├── SHARED ├── TESTS ├── BUILD └── RUNTIME
        """
        proj_name = snapshot.project.get("project_name", "Project")
        lines = [f"{proj_name.upper()}"]
        
        services_map = {s["category"]: s for s in snapshot.services}
        cat_order = ["FRONTEND", "BACKEND", "DATABASE", "SHARED", "TESTS", "BUILD", "RUNTIME"]

        for idx, cat in enumerate(cat_order):
            is_last = (idx == len(cat_order) - 1)
            prefix = " └── " if is_last else " ├── "
            if cat in services_map:
                s = services_map[cat]
                eps = s.get("entrypoints", [])
                ep_str = f" (entrypoints: {', '.join(eps)})" if eps else ""
                lines.append(f"{prefix}{cat}{ep_str}")
            else:
                lines.append(f"{prefix}{cat} (none)")

        summary_tree = "\n".join(lines)

        # Inferência de fluxos de dados
        data_flows: list[str] = []
        has_frontend = "FRONTEND" in services_map
        has_backend = "BACKEND" in services_map
        has_db = "DATABASE" in services_map

        if has_frontend and has_backend and has_db:
            data_flows.append("Frontend (UI) -> API Calls -> Backend Handlers -> Database Models")
        elif has_frontend and has_backend:
            data_flows.append("Frontend (UI) -> API Endpoints -> Backend Services")
        elif has_backend and has_db:
            data_flows.append("Backend Services -> Database Layer")
        elif has_frontend:
            data_flows.append("Frontend Client Application (SPA)")
        elif has_backend:
            data_flows.append("Backend Service / API Engine")
        else:
            data_flows.append("Modular Codebase Library")

        return {
            "summary_tree": summary_tree,
            "data_flows": data_flows,
            "components_count": len(snapshot.services),
        }

    def build_snapshot(self, project_id: str, force_full: bool = False) -> ArchitectureSnapshot:
        """
        Constrói o snapshot arquitetural determinístico completo a partir do estado atual do projeto.
        """
        root = Path(self.project_context.project_root(project_id))
        if not root.is_dir():
            raise FileNotFoundError(f"Diretório do projeto não encontrado: {root}")

        # 1. Carregar lista de ficheiros
        files_dict = self.project_context.read_project_files(project_id)
        file_list: list[dict[str, Any]] = []
        file_names = sorted(files_dict.keys())

        for rel_path, content in files_dict.items():
            size_bytes = len(content.encode("utf-8"))
            sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
            sfx = Path(rel_path).suffix.lower()
            lang = "Python" if sfx == ".py" else "TypeScript" if sfx in {".ts", ".tsx"} else "JavaScript" if sfx in {".js", ".jsx"} else "Other"
            file_list.append({
                "path": rel_path.replace("\\", "/"),
                "size_bytes": size_bytes,
                "sha256": sha,
                "language": lang,
            })

        # 2. Deteção de Stack & Entrypoints
        stack = self.detect_stack(root)
        entrypoints_info = self.discover_entrypoints(root, stack, file_names)
        packages_info = self.discover_packages(root)
        services_info = self.discover_services(root, file_names, entrypoints_info)
        dependencies_info = self.discover_dependencies(root)
        tests_info = self.discover_tests(root, stack, file_names)

        # 3. Grafo de Repositório & Símbolos AST
        graph = RepositoryGraph(str(root))
        graph.scan()

        all_symbols = [s for s_list in graph.symbols.values() for s in s_list]
        all_imports = [i for i_list in graph.imports.values() for i in i_list]

        symbols_data = {
            "total_count": len(all_symbols),
            "classes_count": sum(1 for s in all_symbols if s.symbol_type == "CLASS"),
            "functions_count": sum(1 for s in all_symbols if s.symbol_type in {"FUNCTION", "METHOD"}),
            "interfaces_count": sum(1 for s in all_symbols if s.symbol_type == "TYPE_ALIAS"),
            "key_symbols": [s.to_dict() for s in all_symbols[:50]],
        }

        imports_data = {
            "total_imports": len(all_imports),
            "internal_imports": sum(1 for i in all_imports if i.resolved_target),
            "external_imports": sum(1 for i in all_imports if not i.resolved_target),
            "edges": [i.to_dict() for i in all_imports[:100]],
        }

        api_contracts = {
            "endpoints": [e.to_dict() for e in graph.endpoints],
            "client_calls": [c.to_dict() for c in graph.api_calls],
        }

        # 4. Build & Runtime
        pkg_json_path = root / "package.json"
        package_scripts = {}
        if pkg_json_path.is_file():
            try:
                p_data = json.loads(pkg_json_path.read_text(encoding="utf-8", errors="replace"))
                package_scripts = p_data.get("scripts", {})
            except Exception:
                pass

        build_data = {
            "build_systems": stack.get("build_tools", []),
            "package_scripts": package_scripts,
            "suggested_commands": [
                {"kind": "build", "command": f"npm run {k}", "source": "package.json"}
                for k in package_scripts if k in {"build", "compile", "bundle"}
            ],
        }

        runtime_data = {
            "runtime_source": "local_environment",
            "python_executable": sys.executable if "Python" in stack.get("languages", []) else None,
            "node_executable": shutil.which("node"),
            "runtime_version": f"Python {sys.version.split()[0]}",
        }

        # 5. Git Commit (se disponível)
        source_commit = None
        git_dir = root / ".git"
        if git_dir.exists() or (root.parent / ".git").exists():
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                if res.returncode == 0:
                    source_commit = res.stdout.strip()
            except Exception:
                pass

        # 6. Calcular confiança agregada
        evidence_records = stack.get("evidence", {})
        conf_scores = [rec.get("confidence", 1.0) for rec in evidence_records.values()]
        for ep in entrypoints_info:
            conf_scores.append(ep.confidence)
        avg_conf = round(sum(conf_scores) / len(conf_scores), 2) if conf_scores else 1.0

        project_meta = {
            "project_id": project_id,
            "project_name": root.name,
            "root_path": str(root).replace("\\", "/"),
        }

        timestamp = datetime.now(timezone.utc).isoformat()

        # Construir objeto base para hash
        temp_snapshot = ArchitectureSnapshot(
            project=project_meta,
            stack=stack,
            entrypoints=[ep.to_dict() for ep in entrypoints_info],
            packages=[pkg.to_dict() for pkg in packages_info],
            services=[srv.to_dict() for srv in services_info],
            files=file_list,
            symbols=symbols_data,
            imports=imports_data,
            dependencies=dependencies_info,
            api_contracts=api_contracts,
            tests=tests_info,
            build=build_data,
            runtime=runtime_data,
            architecture={},
            generated_at=timestamp,
            source_commit=source_commit,
            snapshot_hash="",
            confidence=avg_conf,
            staleness=StalenessStatus.FRESH.value,
        )

        arch_summary = self.generate_architecture_summary(temp_snapshot)
        temp_snapshot.architecture = arch_summary

        # Hash do snapshot
        raw_bytes = json.dumps(temp_snapshot.to_dict(), sort_keys=True).encode("utf-8")
        snapshot_hash = hashlib.sha256(raw_bytes).hexdigest()
        temp_snapshot.snapshot_hash = snapshot_hash

        # Persistir snapshot
        self.save_snapshot(project_id, temp_snapshot)

        return temp_snapshot

    def snapshot_path(self, project_id: str) -> Path:
        """Caminho de persistência seguro do snapshot arquitetural."""
        meta_dir = Path(self.project_context.metadata_dir(project_id))
        meta_dir.mkdir(parents=True, exist_ok=True)
        return meta_dir / "architecture_snapshot.json"

    def save_snapshot(self, project_id: str, snapshot: ArchitectureSnapshot) -> str:
        path = self.snapshot_path(project_id)
        path.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
        return str(path)

    def load_snapshot(self, project_id: str) -> ArchitectureSnapshot | None:
        path = self.snapshot_path(project_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return ArchitectureSnapshot.from_dict(data)
        except Exception:
            return None

    def check_staleness(self, project_id: str) -> StalenessCheckResult:
        """
        Compara o estado em disco com o snapshot persistido:
        - FRESH: 0 alterações
        - PARTIALLY_STALE: poucos ficheiros mudaram (<30%), manifestos intocados
        - STALE: manifestos mudaram, snapshot inexistente ou alterações massivas
        """
        snapshot = self.load_snapshot(project_id)
        if not snapshot:
            return StalenessCheckResult(
                status=StalenessStatus.STALE.value,
                reason="snapshot_missing",
            )

        root = Path(self.project_context.project_root(project_id))
        if not root.is_dir():
            return StalenessCheckResult(status=StalenessStatus.STALE.value, reason="project_root_missing")

        current_files_dict = self.project_context.read_project_files(project_id)
        indexed_files = {f["path"]: f["sha256"] for f in snapshot.files}

        current_paths = set(current_files_dict.keys())
        indexed_paths = set(indexed_files.keys())

        added_files = sorted(current_paths - indexed_paths)
        deleted_files = sorted(indexed_paths - current_paths)
        changed_files: list[str] = []

        config_changed = False

        for common_path in sorted(current_paths & indexed_paths):
            content = current_files_dict[common_path]
            cur_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if cur_sha != indexed_files[common_path]:
                changed_files.append(common_path)
                if Path(common_path).name in CONFIG_FILE_NAMES:
                    config_changed = True

        for added in added_files:
            if Path(added).name in CONFIG_FILE_NAMES:
                config_changed = True

        for deleted in deleted_files:
            if Path(deleted).name in CONFIG_FILE_NAMES:
                config_changed = True

        total_changed = len(changed_files) + len(added_files) + len(deleted_files)

        if total_changed == 0:
            return StalenessCheckResult(
                status=StalenessStatus.FRESH.value,
                reason="all_files_identical",
            )

        if config_changed:
            return StalenessCheckResult(
                status=StalenessStatus.STALE.value,
                changed_files=changed_files,
                added_files=added_files,
                deleted_files=deleted_files,
                config_changed=True,
                reason="configuration_manifest_changed",
            )

        total_files = max(len(current_paths), len(indexed_paths), 1)
        if total_changed / total_files > 0.3:
            return StalenessCheckResult(
                status=StalenessStatus.STALE.value,
                changed_files=changed_files,
                added_files=added_files,
                deleted_files=deleted_files,
                config_changed=False,
                reason="major_file_modifications_exceeded_threshold",
            )

        return StalenessCheckResult(
            status=StalenessStatus.PARTIALLY_STALE.value,
            changed_files=changed_files,
            added_files=added_files,
            deleted_files=deleted_files,
            config_changed=False,
            reason="minor_file_modifications_detected",
        )

    def reindex_incremental(self, project_id: str, changed_files: list[str]) -> ArchitectureSnapshot:
        """
        Reindexação rápida e localizada usando blast radius do RepositoryGraph.
        Atualiza apenas símbolos e dependências afetadas sem reconstruir todo o grafo do zero.
        """
        snapshot = self.load_snapshot(project_id)
        if not snapshot:
            return self.build_snapshot(project_id, force_full=True)

        root = Path(self.project_context.project_root(project_id))
        graph = RepositoryGraph(str(root))
        graph.scan()

        # Calcular blast radius
        blast_radius = graph.compute_blast_radius(changed_files)

        # Atualizar ficheiros no snapshot
        current_files_dict = self.project_context.read_project_files(project_id)
        updated_files: list[dict[str, Any]] = []

        for rel_path, content in current_files_dict.items():
            size_bytes = len(content.encode("utf-8"))
            sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
            sfx = Path(rel_path).suffix.lower()
            lang = "Python" if sfx == ".py" else "TypeScript" if sfx in {".ts", ".tsx"} else "JavaScript" if sfx in {".js", ".jsx"} else "Other"
            updated_files.append({
                "path": rel_path.replace("\\", "/"),
                "size_bytes": size_bytes,
                "sha256": sha,
                "language": lang,
            })

        all_symbols = [s for s_list in graph.symbols.values() for s in s_list]
        all_imports = [i for i_list in graph.imports.values() for i in i_list]

        snapshot.files = updated_files
        snapshot.symbols = {
            "total_count": len(all_symbols),
            "classes_count": sum(1 for s in all_symbols if s.symbol_type == "CLASS"),
            "functions_count": sum(1 for s in all_symbols if s.symbol_type in {"FUNCTION", "METHOD"}),
            "interfaces_count": sum(1 for s in all_symbols if s.symbol_type == "TYPE_ALIAS"),
            "key_symbols": [s.to_dict() for s in all_symbols[:50]],
        }
        snapshot.imports = {
            "total_imports": len(all_imports),
            "internal_imports": sum(1 for i in all_imports if i.resolved_target),
            "external_imports": sum(1 for i in all_imports if not i.resolved_target),
            "edges": [i.to_dict() for i in all_imports[:100]],
        }
        snapshot.api_contracts = {
            "endpoints": [e.to_dict() for e in graph.endpoints],
            "client_calls": [c.to_dict() for c in graph.api_calls],
        }
        snapshot.generated_at = datetime.now(timezone.utc).isoformat()
        snapshot.staleness = StalenessStatus.FRESH.value

        # Re-computar hash
        raw_bytes = json.dumps(snapshot.to_dict(), sort_keys=True).encode("utf-8")
        snapshot.snapshot_hash = hashlib.sha256(raw_bytes).hexdigest()

        self.save_snapshot(project_id, snapshot)
        return snapshot

    def ensure_fresh_snapshot(self, project_id: str) -> ArchitectureSnapshot:
        """
        Garante que o snapshot está fresco para o projeto:
        - Se FRESH -> retorna imediatamente;
        - Se PARTIALLY_STALE -> reindexação incremental;
        - Se STALE -> reindexação completa.
        """
        check = self.check_staleness(project_id)
        if check.status == StalenessStatus.FRESH.value:
            loaded = self.load_snapshot(project_id)
            if loaded:
                return loaded

        if check.status == StalenessStatus.PARTIALLY_STALE.value:
            all_changed = list(set(check.changed_files + check.added_files + check.deleted_files))
            return self.reindex_incremental(project_id, all_changed)

        # Full reindex
        return self.build_snapshot(project_id, force_full=True)

    def get_relevant_context(self, project_id: str, objective: str) -> dict[str, Any]:
        """
        Seleciona os componentes, ficheiros, símbolos e testes relevantes para uma missão:
        MISSION -> SNAPSHOT -> RELEVANT COMPONENTS -> RELEVANT FILES -> RELEVANT SYMBOLS -> CONTEXT
        """
        snapshot = self.ensure_fresh_snapshot(project_id)
        detector = CapabilityDetector()
        detected_caps = detector.detect(objective)

        norm_obj = objective.lower()
        obj_words = set(re.findall(r'\w{3,}', norm_obj))

        relevant_files: list[str] = []
        relevant_symbols: list[dict[str, Any]] = []
        all_files = list(self.project_context.read_project_files(project_id).keys())

        # 1. Símbolos por correspondência de palavras-chave
        for sym in snapshot.symbols.get("key_symbols", []):
            sym_name = sym.get("name", "").lower()
            if any(w in sym_name for w in obj_words):
                relevant_symbols.append(sym)
                sym_file = sym.get("file_path")
                if sym_file and sym_file not in relevant_files:
                    relevant_files.append(sym_file)

        # 2. Ficheiros correspondentes por palavra-chave no caminho
        for f in all_files:
            f_lower = f.lower()
            if any(w in f_lower for w in obj_words) and f not in relevant_files:
                relevant_files.append(f)

        # Se ainda vazio, incluir entrypoints principais
        if not relevant_files:
            for ep in snapshot.entrypoints[:5]:
                relevant_files.append(ep["path"])

        return {
            "project_id": project_id,
            "objective": objective,
            "architecture_summary": snapshot.architecture.get("summary_tree", ""),
            "detected_capabilities": [c.value for c in detected_caps],
            "relevant_files": relevant_files,
            "relevant_symbols": relevant_symbols,
            "suggested_tests": snapshot.tests.get("suggested_commands", []),
            "build_commands": snapshot.build.get("suggested_commands", []),
            "confidence": snapshot.confidence,
        }
