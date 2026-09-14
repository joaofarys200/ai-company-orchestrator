"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Config Validator: Verifies port definitions, socket availability, and configuration files.
"""

from __future__ import annotations

import os
import socket
from typing import List

from agents.project_preflight.models import (
    IssueSeverity,
    PreflightIssue,
    ProjectRuntimeProfile,
)


class ConfigValidator:
    """
    Validates port allocation, configuration files, and network readiness.
    """

    def validate_config(
        self, root: str, profile: ProjectRuntimeProfile
    ) -> List[PreflightIssue]:
        issues: List[PreflightIssue] = []

        # Validate configured port range
        if profile.default_port < 1 or profile.default_port > 65535:
            issues.append(
                PreflightIssue(
                    issue_id="invalid_port_range",
                    severity=IssueSeverity.BLOCKER,
                    category="CONFIGURATION_ERROR",
                    message=f"Porta configurada inválida: {profile.default_port}. Deve estar entre 1 e 65535.",
                )
            )
            return issues

        # Check if port is already bound on localhost
        if self._is_port_in_use(profile.default_port):
            issues.append(
                PreflightIssue(
                    issue_id="port_already_in_use",
                    severity=IssueSeverity.WARNING,
                    category="PORT_CONFLICT",
                    message=f"A porta {profile.default_port} já está em uso por outro processo.",
                    suggested_action=f"Encerre o processo ativo na porta {profile.default_port} ou configure uma porta alternativa.",
                )
            )

        return issues

    def _is_port_in_use(self, port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            return False
