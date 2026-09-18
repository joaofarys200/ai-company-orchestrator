"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: project_fingerprint.py
Extracts, sanitizes, and canonicalizes project fingerprints.
Guarantees determinism, excludes credentials/secrets, and computes SHA-256 fingerprint hash.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from .models import ProjectFingerprint


class ProjectFingerprintExtractor:
    """
    Extracts structural metadata from repository configs, dependency manifests,
    and workspace topologies, producing an immutable ProjectFingerprint.
    """

    SECRET_KEY_PATTERN = re.compile(
        r"(secret|token|password|api[_-]?key|credential|private[_-]?key|auth|bearer)",
        re.IGNORECASE,
    )

    @classmethod
    def sanitize_dictionary(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deep sanitization eliminating any potential credential or secret leak."""
        clean: Dict[str, Any] = {}
        for k, v in data.items():
            if cls.SECRET_KEY_PATTERN.search(k):
                continue
            if isinstance(v, dict):
                clean[k] = cls.sanitize_dictionary(v)
            elif isinstance(v, list):
                clean[k] = [
                    cls.sanitize_dictionary(x) if isinstance(x, dict) else x
                    for x in v
                    if not (isinstance(x, str) and len(x) > 32 and bool(re.search(r"[A-Za-z0-9+/=]{20,}", x)))
                ]
            elif isinstance(v, str):
                if len(v) > 50 and bool(re.search(r"^[A-Za-z0-9_\-]{32,}$", v)):
                    continue
                clean[k] = v
            else:
                clean[k] = v
        return clean

    @classmethod
    def create_fingerprint(
        cls,
        project_id: str,
        languages: Optional[List[str]] = None,
        frameworks: Optional[List[str]] = None,
        architecture_style: str = "modular_monolith",
        package_topology: str = "single_package",
        service_topology: str = "standalone",
        contract_types: Optional[List[str]] = None,
        symbol_graph_statistics: Optional[Dict[str, Any]] = None,
        scc_statistics: Optional[Dict[str, Any]] = None,
        test_framework: Optional[List[str]] = None,
        browser_framework: Optional[List[str]] = None,
        persistence_technologies: Optional[List[str]] = None,
        communication_mechanisms: Optional[List[str]] = None,
        risk_classes: Optional[List[str]] = None,
        domain_category: str = "general_engineering",
        repository_scale: str = "medium",
        verification_history: Optional[Dict[str, Any]] = None,
    ) -> ProjectFingerprint:
        """Create a sanitized, canonicalized ProjectFingerprint."""
        langs = sorted(list(set([l.strip().lower() for l in (languages or ["python"])])))
        fws = sorted(list(set([f.strip().lower() for f in (frameworks or [])])))
        ctypes = sorted(list(set([c.strip().lower() for c in (contract_types or [])])))
        tfw = sorted(list(set([t.strip().lower() for t in (test_framework or ["pytest"])])))
        bfw = sorted(list(set([b.strip().lower() for b in (browser_framework or ["none"])])))
        pt = sorted(list(set([p.strip().lower() for p in (persistence_technologies or [])])))
        cm = sorted(list(set([m.strip().lower() for m in (communication_mechanisms or [])])))
        rc = sorted(list(set([r.strip().lower() for r in (risk_classes or [])])))

        clean_symbol_stats = cls.sanitize_dictionary(symbol_graph_statistics or {})
        clean_scc_stats = cls.sanitize_dictionary(scc_statistics or {})
        clean_history = cls.sanitize_dictionary(verification_history or {})

        fp = ProjectFingerprint(
            project_id=project_id,
            languages=langs,
            frameworks=fws,
            architecture_style=architecture_style.strip().lower(),
            package_topology=package_topology.strip().lower(),
            service_topology=service_topology.strip().lower(),
            contract_types=ctypes,
            symbol_graph_statistics=clean_symbol_stats,
            scc_statistics=clean_scc_stats,
            test_framework=tfw,
            browser_framework=bfw,
            persistence_technologies=pt,
            communication_mechanisms=cm,
            risk_classes=rc,
            domain_category=domain_category.strip().lower(),
            repository_scale=repository_scale.strip().lower(),
            verification_history=clean_history,
        )
        return fp

    @classmethod
    def extract_from_workspace(cls, project_id: str, workspace_root: str) -> ProjectFingerprint:
        """Heuristic inspection of repository root to build structural fingerprint."""
        languages: List[str] = []
        frameworks: List[str] = []
        test_framework: List[str] = []
        browser_framework: List[str] = []
        persistence_technologies: List[str] = []
        communication_mechanisms: List[str] = []
        contract_types: List[str] = []

        if os.path.exists(os.path.join(workspace_root, "pyproject.toml")) or any(
            f.endswith(".py") for f in os.listdir(workspace_root) if os.path.isfile(os.path.join(workspace_root, f))
        ):
            languages.append("python")
            test_framework.append("pytest")

        if os.path.exists(os.path.join(workspace_root, "package.json")):
            languages.append("typescript")
            languages.append("javascript")
            test_framework.append("vitest")
            frameworks.append("react")

        if os.path.exists(os.path.join(workspace_root, "playwright.config.ts")) or os.path.exists(
            os.path.join(workspace_root, "playwright.config.js")
        ):
            browser_framework.append("playwright")

        # Check server files or database
        for root, dirs, files in os.walk(workspace_root):
            if "node_modules" in dirs:
                dirs.remove("node_modules")
            if ".git" in dirs:
                dirs.remove(".git")
            for f in files:
                if f.endswith(".sqlite") or f.endswith(".db"):
                    if "sqlite" not in persistence_technologies:
                        persistence_technologies.append("sqlite")
                if "schema" in f.lower() or f.endswith(".proto") or f.endswith(".graphql"):
                    if "json_schema" not in contract_types:
                        contract_types.append("json_schema")
            break

        if not communication_mechanisms:
            communication_mechanisms.extend(["http_rest", "websocket"])

        return cls.create_fingerprint(
            project_id=project_id,
            languages=languages or ["python"],
            frameworks=frameworks or ["fastapi"],
            architecture_style="modular_monolith",
            package_topology="monorepo" if os.path.exists(os.path.join(workspace_root, "packages")) else "single_package",
            service_topology="client_server",
            contract_types=contract_types or ["openapi", "websocket"],
            test_framework=test_framework or ["pytest"],
            browser_framework=browser_framework or ["playwright"],
            persistence_technologies=persistence_technologies or ["sqlite"],
            communication_mechanisms=communication_mechanisms,
            risk_classes=["network_retry", "state_concurrency", "dynamic_dispatch"],
            domain_category="developer_tools",
            repository_scale="medium",
        )
