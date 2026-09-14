"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Project Profile Detector: Infers ProjectRuntimeProfile from file layouts, manifests, and configs.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from agents.project_preflight.models import (
    LanguageType,
    ProjectRuntimeProfile,
    RuntimeType,
)


class ProjectProfileDetector:
    """
    Infers a strictly evidence-grounded ProjectRuntimeProfile for a given project directory.
    Emits UNKNOWN when evidence is ambiguous or incomplete.
    """

    def detect_profile(self, project_root: str, project_id: Optional[str] = None) -> ProjectRuntimeProfile:
        root = os.path.realpath(os.path.abspath(project_root))
        p_id = project_id or os.path.basename(root)

        profile = ProjectRuntimeProfile(
            project_id=p_id,
            workspace_root=root,
        )

        if not os.path.isdir(root):
            return profile

        # Discover config files
        for fname in os.listdir(root):
            if fname.startswith((".env", "tsconfig", "vite", "webpack", "babel", "Dockerfile")):
                profile.config_files.append(fname)

        # 1. Check Node.js / JavaScript / TypeScript manifest
        pkg_json_path = os.path.join(root, "package.json")
        if os.path.isfile(pkg_json_path):
            self._analyze_package_json(root, pkg_json_path, profile)
        elif self._has_python_files(root):
            self._analyze_python_project(root, profile)
        elif os.path.isfile(os.path.join(root, "index.html")):
            profile.language = LanguageType.HTML_JS
            profile.runtime = RuntimeType.STATIC_BROWSER
            profile.entrypoint = "index.html"
            profile.start_command = None
            profile.healthcheck_path = "/"
        else:
            profile.language = LanguageType.UNKNOWN
            profile.runtime = RuntimeType.UNKNOWN

        return profile

    def _analyze_package_json(
        self, root: str, pkg_path: str, profile: ProjectRuntimeProfile
    ) -> None:
        profile.dependency_manifest = "package.json"
        profile.package_manager = "npm"
        if os.path.isfile(os.path.join(root, "yarn.lock")):
            profile.package_manager = "yarn"
        elif os.path.isfile(os.path.join(root, "pnpm-lock.yaml")):
            profile.package_manager = "pnpm"

        profile.has_node_modules = os.path.isdir(os.path.join(root, "node_modules"))

        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
        except Exception:
            profile.language = LanguageType.JAVASCRIPT
            profile.runtime = RuntimeType.UNKNOWN
            return

        # Detect TypeScript
        deps = pkg_data.get("dependencies", {})
        dev_deps = pkg_data.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}
        is_ts = "typescript" in all_deps or os.path.isfile(os.path.join(root, "tsconfig.json"))

        profile.language = LanguageType.TYPESCRIPT if is_ts else LanguageType.JAVASCRIPT

        # Detect ESM vs CommonJS
        pkg_type = pkg_data.get("type", "commonjs").lower()
        if is_ts:
            profile.runtime = RuntimeType.NODE_ESM if pkg_type == "module" else RuntimeType.NODE_CJS
        else:
            profile.runtime = RuntimeType.NODE_ESM if pkg_type == "module" else RuntimeType.NODE_CJS

        # Scripts
        scripts = pkg_data.get("scripts", {})
        for start_key in ("dev", "start", "preview", "serve"):
            if start_key in scripts and isinstance(scripts[start_key], str):
                profile.start_command = f"{profile.package_manager} run {start_key}"
                break

        if "build" in scripts:
            profile.build_command = f"{profile.package_manager} run build"
        if "test" in scripts:
            profile.test_command = f"{profile.package_manager} test"

        # Entrypoint
        main_entry = pkg_data.get("main")
        if main_entry and os.path.isfile(os.path.join(root, main_entry)):
            profile.entrypoint = main_entry
        else:
            for candidate in ("app.js", "server.js", "index.js", "main.js", "src/index.ts", "src/index.js"):
                if os.path.isfile(os.path.join(root, candidate)):
                    profile.entrypoint = candidate
                    break

        # Check port heuristic
        profile.default_port = self._infer_port_from_files(root, profile.entrypoint)

    def _has_python_files(self, root: str) -> bool:
        if os.path.isfile(os.path.join(root, "requirements.txt")):
            return True
        if os.path.isfile(os.path.join(root, "pyproject.toml")):
            return True
        for f in os.listdir(root):
            if f.endswith(".py"):
                return True
        return False

    def _analyze_python_project(self, root: str, profile: ProjectRuntimeProfile) -> None:
        profile.language = LanguageType.PYTHON
        profile.runtime = RuntimeType.PYTHON_3
        profile.package_manager = "pip"
        profile.has_venv = os.path.isdir(os.path.join(root, "venv")) or os.path.isdir(os.path.join(root, ".venv"))

        if os.path.isfile(os.path.join(root, "requirements.txt")):
            profile.dependency_manifest = "requirements.txt"
        elif os.path.isfile(os.path.join(root, "pyproject.toml")):
            profile.dependency_manifest = "pyproject.toml"

        for candidate in ("app.py", "server.py", "main.py", "wsgi.py", "asgi.py"):
            if os.path.isfile(os.path.join(root, candidate)):
                profile.entrypoint = candidate
                break

        if profile.entrypoint:
            profile.start_command = f"python {profile.entrypoint}"
            profile.default_port = self._infer_port_from_files(root, profile.entrypoint)

    def _infer_port_from_files(self, root: str, entrypoint: Optional[str]) -> int:
        if not entrypoint:
            return 3000
        full_path = os.path.join(root, entrypoint)
        if not os.path.isfile(full_path):
            return 3000
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(10000)
            # Find PORT = 8080 or port 5000 or listen(3000)
            m = re.search(r'\b(?:PORT\s*=\s*|listen\s*\(\s*)(\d{4,5})\b', content)
            if m:
                return int(m.group(1))
        except Exception:
            pass
        return 3000
