"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
TypeScript Preflight Analyzer: Validates tsconfig.json and TypeScript entrypoints.
"""

from __future__ import annotations

import json
import os
from typing import List

from agents.project_preflight.models import (
    IssueSeverity,
    PreflightIssue,
    ProjectRuntimeProfile,
)


class TypeScriptPreflightAnalyzer:
    """
    Validates TypeScript configuration and entrypoints.
    """

    def analyze(self, root: str, profile: ProjectRuntimeProfile) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []

        tsconfig_path = os.path.join(root, "tsconfig.json")
        if os.path.isfile(tsconfig_path):
            try:
                with open(tsconfig_path, "r", encoding="utf-8") as f:
                    # Strip comments if present (simple json with comments)
                    content = f.read()
                    # Basic JSON parse check
                    json.loads(content)
            except Exception as e:
                issues.append(
                    PreflightIssue(
                        issue_id="invalid_tsconfig",
                        severity=IssueSeverity.WARNING,
                        category="CONFIGURATION_ERROR",
                        message=f"tsconfig.json contém formato inválido: {e}",
                        file_path=tsconfig_path,
                        suggested_action="Verifique a formatação do tsconfig.json.",
                    )
                )

        if profile.entrypoint and profile.entrypoint.endswith((".ts", ".tsx")):
            entry_full = os.path.join(root, profile.entrypoint)
            if not os.path.isfile(entry_full):
                issues.append(
                    PreflightIssue(
                        issue_id="missing_ts_entrypoint",
                        severity=IssueSeverity.BLOCKER,
                        category="ENTRYPOINT_MISSING",
                        message=f"Ponto de entrada TypeScript não encontrado: {profile.entrypoint}",
                        file_path=entry_full,
                        suggested_action="Crie o ficheiro de entrada configurado ou ajuste o package.json.",
                    )
                )

        return issues
