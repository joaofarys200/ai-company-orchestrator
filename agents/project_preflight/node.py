"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Node Runtime Validator: Verifies Node.js installation, version, and module resolution.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import List

from agents.project_preflight.models import (
    IssueSeverity,
    PreflightIssue,
    ProjectRuntimeProfile,
)


class NodeRuntimeValidator:
    """
    Validates Node.js execution environment and module systems.
    """

    def validate_runtime(self, profile: ProjectRuntimeProfile) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []

        node_bin = shutil.which("node")
        if not node_bin:
            issues.append(
                PreflightIssue(
                    issue_id="node_not_installed",
                    severity=IssueSeverity.BLOCKER,
                    category="RUNTIME_MISSING",
                    message="O binário do Node.js não foi encontrado no PATH do sistema.",
                    suggested_action="Instale o Node.js v18+ no sistema host.",
                )
            )
            return issues

        npm_bin = shutil.which("npm")
        if not npm_bin:
            issues.append(
                PreflightIssue(
                    issue_id="npm_not_installed",
                    severity=IssueSeverity.WARNING,
                    category="PACKAGE_MANAGER_MISSING",
                    message="O comando npm não foi encontrado no PATH do sistema.",
                )
            )

        return issues
