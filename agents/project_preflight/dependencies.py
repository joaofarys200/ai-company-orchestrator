"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Dependency Validator: Verifies package manifests and installed dependencies without unauthorized installs.
"""

from __future__ import annotations

import json
import os
from typing import List

from agents.project_preflight.models import (
    IssueSeverity,
    LanguageType,
    PreflightIssue,
    ProjectRuntimeProfile,
)


class DependencyValidator:
    """
    Checks that manifests match installed directories and packages.
    Never runs package installations automatically without policy permission.
    """

    def validate_dependencies(
        self, root: str, profile: ProjectRuntimeProfile
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []

        if profile.language in (LanguageType.JAVASCRIPT, LanguageType.TYPESCRIPT):
            issues.extend(self._validate_node_dependencies(root, profile))
        elif profile.language == LanguageType.PYTHON:
            issues.extend(self._validate_python_dependencies(root, profile))

        return issues

    def _validate_node_dependencies(
        self, root: str, profile: ProjectRuntimeProfile
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []
        pkg_path = os.path.join(root, "package.json")
        if not os.path.isfile(pkg_path):
            return issues

        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
        except Exception as e:
            issues.append(
                PreflightIssue(
                    issue_id="corrupt_package_json",
                    severity=IssueSeverity.BLOCKER,
                    category="CONFIGURATION_ERROR",
                    message=f"package.json ilegível ou corrompido: {e}",
                    file_path=pkg_path,
                )
            )
            return issues

        declared_deps = pkg_data.get("dependencies", {})
        node_modules_dir = os.path.join(root, "node_modules")

        if declared_deps and not os.path.isdir(node_modules_dir):
            issues.append(
                PreflightIssue(
                    issue_id="missing_node_modules",
                    severity=IssueSeverity.BLOCKER,
                    category="DEPENDENCY_MISSING",
                    message=f"Diretório node_modules ausente. {len(declared_deps)} dependências declaradas não estão instaladas.",
                    suggested_action=f"Execute '{profile.package_manager or 'npm'} install' para instalar as dependências.",
                )
            )
            return issues

        # Check individual required packages if node_modules exists
        if os.path.isdir(node_modules_dir):
            missing_pkgs = []
            for pkg_name in declared_deps.keys():
                pkg_dir = os.path.join(node_modules_dir, pkg_name)
                if not os.path.isdir(pkg_dir):
                    missing_pkgs.append(pkg_name)

            if missing_pkgs:
                issues.append(
                    PreflightIssue(
                        issue_id="missing_installed_packages",
                        severity=IssueSeverity.BLOCKER,
                        category="DEPENDENCY_MISSING",
                        message=f"Dependências declaradas ausentes em node_modules: {', '.join(missing_pkgs[:5])}",
                        suggested_action=f"Execute '{profile.package_manager or 'npm'} install' para sincronizar os pacotes.",
                    )
                )

        return issues

    def _validate_python_dependencies(
        self, root: str, profile: ProjectRuntimeProfile
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []
        req_path = os.path.join(root, "requirements.txt")
        if not os.path.isfile(req_path):
            return issues

        try:
            with open(req_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        except Exception:
            return issues

        if lines and not profile.has_venv:
            issues.append(
                PreflightIssue(
                    issue_id="missing_python_venv",
                    severity=IssueSeverity.WARNING,
                    category="ENVIRONMENT_WARNING",
                    message=f"requirements.txt declara {len(lines)} pacotes mas nenhum virtualenv (venv/.venv) local foi encontrado.",
                    suggested_action="Recomenda-se criar um ambiente virtual isolado para o projeto.",
                )
            )

        return issues
