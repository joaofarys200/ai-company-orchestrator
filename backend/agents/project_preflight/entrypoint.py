"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Entrypoint Validator: Verifies existence, read permissions, and script resolution before start.
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


class EntrypointValidator:
    """
    Validates entrypoints and script commands before any process is spawned.
    """

    def validate_entrypoint(
        self, root: str, profile: ProjectRuntimeProfile
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []

        # 1. Validate script if package.json exists
        pkg_path = os.path.join(root, "package.json")
        if os.path.isfile(pkg_path):
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    scripts = json.load(f).get("scripts", {})
                has_start = any(k in scripts for k in ("start", "dev", "preview", "serve"))
                if not has_start and not profile.entrypoint:
                    issues.append(
                        PreflightIssue(
                            issue_id="missing_start_script",
                            severity=IssueSeverity.BLOCKER,
                            category="START_SCRIPT_MISSING",
                            message="package.json não possui nenhum script 'start', 'dev' ou 'preview' configurado.",
                            suggested_action="Adicione 'scripts.start' no package.json (ex: \"start\": \"node app.js\").",
                        )
                    )
            except Exception:
                pass

        # 2. Check physical entrypoint file
        if profile.entrypoint:
            entry_full = os.path.join(root, profile.entrypoint)
            if not os.path.isfile(entry_full):
                issues.append(
                    PreflightIssue(
                        issue_id="entrypoint_file_missing",
                        severity=IssueSeverity.BLOCKER,
                        category="ENTRYPOINT_MISSING",
                        message=f"Ponto de entrada '{profile.entrypoint}' não existe no diretório do projeto.",
                        file_path=entry_full,
                        suggested_action=f"Crie o ficheiro '{profile.entrypoint}' ou atualize a configuração 'main' do package.json.",
                    )
                )
            elif not os.access(entry_full, os.R_OK):
                issues.append(
                    PreflightIssue(
                        issue_id="entrypoint_not_readable",
                        severity=IssueSeverity.BLOCKER,
                        category="PERMISSION_DENIED",
                        message=f"Sem permissão de leitura para o ficheiro de entrada: {profile.entrypoint}",
                        file_path=entry_full,
                    )
                )

        return issues
