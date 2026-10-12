"""
Detector de Arquitetura e Stack do JARVIS.
Implementa o Princípio Arquitetural: EXISTING ARCHITECTURE FIRST.

Antes de qualquer inferência de artefactos:
1. Analisa a árvore do projeto
2. Deteta a stack (React+Vite, Next.js, Vanilla, Python FastAPI/Flask, Node/TS, etc.)
3. Deteta a framework e o bundler
4. Deteta os entrypoints reais
5. Deteta as convenções do projeto (TypeScript/JS, pasta src, etc.)
6. Deteta o runtime e dependências
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class DetectedArchitecture:
    """Metadados completos da arquitetura detetada no projeto."""
    is_existing: bool
    stack: str  # 'react_vite', 'nextjs', 'vanilla_web', 'python_fastapi', 'python_flask', 'node_typescript', 'node_express', 'custom_existing', 'empty'
    framework: str = "None"
    bundler: str = "None"
    runtime: str = "unknown"  # 'browser', 'node', 'python', 'unknown'
    entrypoints: Dict[str, List[str]] = field(default_factory=dict)
    conventions: Dict[str, Any] = field(default_factory=dict)
    existing_files: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_existing": self.is_existing,
            "stack": self.stack,
            "framework": self.framework,
            "bundler": self.bundler,
            "runtime": self.runtime,
            "entrypoints": self.entrypoints,
            "conventions": self.conventions,
            "existing_files": self.existing_files,
            "dependencies": self.dependencies,
        }


class ArchitectureDetector:
    """Analisa a estrutura do projeto para identificar stack, convenções e entrypoints."""

    IGNORE_DIRS: Set[str] = {
        "node_modules", ".git", ".gemini", "dist", "build", ".next",
        "__pycache__", ".pytest_cache", ".venv", "venv", ".idea", ".vscode"
    }

    @classmethod
    def detect_architecture(cls, project_root: str) -> DetectedArchitecture:
        """Audita a árvore do projeto e deduz a arquitetura existente."""
        if not os.path.exists(project_root):
            return DetectedArchitecture(is_existing=False, stack="empty", runtime="unknown")

        # 1. Coleta lista de ficheiros relativos
        existing_files: List[str] = []
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in cls.IGNORE_DIRS]
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), project_root).replace("\\", "/")
                existing_files.append(rel)

        if not existing_files or all(f in {".gitignore", "README.md", ".gitkeep"} for f in existing_files):
            return DetectedArchitecture(
                is_existing=False,
                stack="empty",
                runtime="unknown",
                existing_files=existing_files,
            )

        files_set = set(existing_files)
        files_lower = {f.lower(): f for f in existing_files}

        # 2. Inspeciona package.json se existir
        pkg_json_path = os.path.join(project_root, "package.json")
        pkg_data: Dict[str, Any] = {}
        all_deps: Dict[str, str] = {}
        if os.path.exists(pkg_json_path):
            try:
                pkg_data = json.loads(Path(pkg_json_path).read_text(encoding="utf-8", errors="ignore"))
                all_deps.update(pkg_data.get("dependencies", {}))
                all_deps.update(pkg_data.get("devDependencies", {}))
            except Exception:
                pass

        # 3. Inspeciona ficheiros Python (requirements.txt, pyproject.toml, ficheiros .py)
        has_python_files = any(f.endswith(".py") for f in existing_files)
        has_ts_files = any(f.endswith((".ts", ".tsx")) for f in existing_files)
        has_js_files = any(f.endswith((".js", ".jsx", ".mjs")) for f in existing_files)
        has_src_dir = any(f.startswith("src/") for f in existing_files)
        has_app_dir = any(f.startswith("app/") for f in existing_files)
        has_pages_dir = any(f.startswith("pages/") for f in existing_files)

        # 4. Deteta Next.js
        if "next" in all_deps or any(f.startswith("app/") or f.startswith("pages/") for f in existing_files) and ("next.config.js" in files_set or "next.config.mjs" in files_set or "next.config.ts" in files_set or "next" in all_deps):
            entrypoints: Dict[str, List[str]] = {"frontend": [], "styling": [], "backend": []}
            for candidate in ["app/layout.tsx", "app/layout.jsx", "app/page.tsx", "app/page.jsx", "pages/_app.tsx", "pages/_app.js", "pages/index.tsx", "pages/index.js", "src/app/page.tsx", "src/app/layout.tsx"]:
                if candidate in files_set:
                    entrypoints["frontend"].append(candidate)
            for candidate in ["app/globals.css", "styles/globals.css", "src/app/globals.css"]:
                if candidate in files_set:
                    entrypoints["styling"].append(candidate)
            for f in existing_files:
                if f.startswith("app/api/") or f.startswith("pages/api/"):
                    entrypoints["backend"].append(f)

            return DetectedArchitecture(
                is_existing=True,
                stack="nextjs",
                framework="Next.js",
                bundler="Next.js",
                runtime="node",
                entrypoints=entrypoints,
                conventions={"typescript": has_ts_files, "has_app_dir": has_app_dir, "has_pages_dir": has_pages_dir},
                existing_files=existing_files,
                dependencies=all_deps,
            )

        # 5. Deteta React + Vite / React SPA
        has_react_dep = "react" in all_deps
        has_react_files = any(f.endswith((".tsx", ".jsx")) for f in existing_files) or any(f in ("src/App.tsx", "src/App.jsx") for f in files_set)
        if (has_react_dep or has_react_files) and not any("next" in d for d in all_deps):
            entrypoints = {"frontend": [], "bootstrap": [], "styling": []}
            for candidate in ["src/App.tsx", "src/App.jsx", "src/app.tsx", "src/app.jsx"]:
                if candidate in files_set:
                    entrypoints["frontend"].append(candidate)
            for candidate in ["src/main.tsx", "src/main.jsx", "src/index.tsx", "src/index.jsx"]:
                if candidate in files_set:
                    entrypoints["bootstrap"].append(candidate)
            for candidate in ["src/index.css", "src/App.css", "src/main.css", "src/styles.css"]:
                if candidate in files_set:
                    entrypoints["styling"].append(candidate)
            if "index.html" in files_set:
                entrypoints.setdefault("html_host", []).append("index.html")

            return DetectedArchitecture(
                is_existing=True,
                stack="react_vite",
                framework="React",
                bundler="Vite",
                runtime="browser",
                entrypoints=entrypoints,
                conventions={"typescript": has_ts_files, "has_src": has_src_dir},
                existing_files=existing_files,
                dependencies=all_deps,
            )

        # 6. Deteta Vue + Vite
        if ("vite" in all_deps or "vite.config.ts" in files_set or "vite.config.js" in files_set) and ("vue" in all_deps or any(f.endswith(".vue") for f in existing_files)):
            entrypoints = {"frontend": [], "bootstrap": []}
            for candidate in ["src/App.vue", "src/app.vue"]:
                if candidate in files_set:
                    entrypoints["frontend"].append(candidate)
            for candidate in ["src/main.ts", "src/main.js"]:
                if candidate in files_set:
                    entrypoints["bootstrap"].append(candidate)
            return DetectedArchitecture(
                is_existing=True,
                stack="vue_vite",
                framework="Vue",
                bundler="Vite",
                runtime="browser",
                entrypoints=entrypoints,
                conventions={"typescript": has_ts_files, "has_src": has_src_dir},
                existing_files=existing_files,
                dependencies=all_deps,
            )

        # 7. Deteta Python Backend (FastAPI / Flask / Django)
        if has_python_files:
            framework = "Python"
            stack = "python_backend"
            # Inspeciona ficheiros py para identificar frameworks
            py_code_samples = ""
            py_entrypoints: List[str] = []
            for f in existing_files:
                if f.endswith(".py"):
                    if f in {"main.py", "app.py", "server.py", "api.py", "run.py", "src/main.py", "src/app.py", "backend/main.py", "backend/app.py"}:
                        py_entrypoints.append(f)
                    try:
                        content = Path(os.path.join(project_root, f)).read_text(encoding="utf-8", errors="ignore")
                        py_code_samples += content[:1000] + "\n"
                    except Exception:
                        pass

            if "fastapi" in py_code_samples.lower() or "from fastapi" in py_code_samples:
                framework = "FastAPI"
                stack = "python_fastapi"
            elif "flask" in py_code_samples.lower() or "from flask" in py_code_samples:
                framework = "Flask"
                stack = "python_flask"
            elif "django" in py_code_samples.lower():
                framework = "Django"
                stack = "python_django"

            entrypoints = {"backend": py_entrypoints or [f for f in existing_files if f.endswith(".py")][:3]}
            return DetectedArchitecture(
                is_existing=True,
                stack=stack,
                framework=framework,
                bundler="None",
                runtime="python",
                entrypoints=entrypoints,
                conventions={"has_src": has_src_dir, "python_files": len([f for f in existing_files if f.endswith('.py')])},
                existing_files=existing_files,
                dependencies={},
            )

        # 8. Deteta Node Backend (Express / TypeScript / Fastify)
        if "express" in all_deps or "fastify" in all_deps or (pkg_data and not any(f.endswith(".html") for f in existing_files)):
            entrypoints = {"backend": []}
            for candidate in ["src/index.ts", "src/server.ts", "src/app.ts", "index.ts", "server.ts", "index.js", "server.js", "app.js"]:
                if candidate in files_set:
                    entrypoints["backend"].append(candidate)
            stack = "node_typescript" if has_ts_files else "node_express"
            return DetectedArchitecture(
                is_existing=True,
                stack=stack,
                framework="Express" if "express" in all_deps else "Node",
                bundler="tsc" if has_ts_files else "None",
                runtime="node",
                entrypoints=entrypoints,
                conventions={"typescript": has_ts_files, "has_src": has_src_dir},
                existing_files=existing_files,
                dependencies=all_deps,
            )

        # 9. Deteta Vanilla Web
        if "index.html" in files_set or any(f.endswith((".html", ".htm")) for f in existing_files):
            entrypoints = {"frontend": [], "styling": [], "scripts": []}
            for f in existing_files:
                if f.endswith((".html", ".htm")):
                    entrypoints["frontend"].append(f)
                elif f.endswith(".css"):
                    entrypoints["styling"].append(f)
                elif f.endswith(".js"):
                    entrypoints["scripts"].append(f)
            return DetectedArchitecture(
                is_existing=True,
                stack="vanilla_web",
                framework="Vanilla",
                bundler="None",
                runtime="browser",
                entrypoints=entrypoints,
                conventions={"has_src": has_src_dir},
                existing_files=existing_files,
                dependencies=all_deps,
            )

        # 10. Projeto com arquitetura existente personalizada (Custom Existing)
        entrypoints = {"files": existing_files[:10]}
        return DetectedArchitecture(
            is_existing=True,
            stack="custom_existing",
            framework="Custom",
            bundler="None",
            runtime="unknown",
            entrypoints=entrypoints,
            conventions={"files_count": len(existing_files), "has_src": has_src_dir},
            existing_files=existing_files,
            dependencies=all_deps,
        )
