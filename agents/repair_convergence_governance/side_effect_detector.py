"""
JARVIS OS — Phase 56: Side Effect Detector
Detects out-of-scope code modifications, unauthorized environmental alterations, and unintended system effects.
"""

from __future__ import annotations

from typing import Dict, List, Set
from agents.repair_convergence_governance.models import (
    RepairStepSnapshot,
    SideEffectReport,
)


class SideEffectDetector:
    """Monitors repair attempts to ensure modifications stay within permissible bounds."""

    def __init__(
        self,
        protected_files: Optional[Set[str]] = None,
        disallowed_path_patterns: Optional[List[str]] = None,
    ):
        self.protected_files = protected_files or {
            ".env",
            "docker-compose.yml",
            "production.json",
            "auth_secrets.pem",
            "sentinel_rules.json",
        }
        self.disallowed_path_patterns = disallowed_path_patterns or [
            "infra/",
            "keys/",
            ".git/",
            "billing/",
        ]

    def evaluate_side_effects(
        self,
        step: RepairStepSnapshot,
        allowed_scope_files: Optional[Set[str]] = None,
    ) -> SideEffectReport:
        """Evaluates whether the modified files and actions in this step exceed the authorized repair perimeter."""
        unintended_files: List[str] = []
        violations: List[str] = []

        modified_set = set(step.modified_files)

        # 1. Check for protected files
        for f in modified_set:
            if any(f.endswith(prot) for prot in self.protected_files):
                violations.append(f"Direct edit to critical protected asset: {f}")
                unintended_files.append(f)

            for pattern in self.disallowed_path_patterns:
                if pattern in f:
                    violations.append(f"Unauthorized path modification pattern '{pattern}' in {f}")
                    if f not in unintended_files:
                        unintended_files.append(f)

        # 2. Check out-of-scope files if an explicit allowlist was specified
        if allowed_scope_files:
            out_of_scope = modified_set - allowed_scope_files
            for f in out_of_scope:
                if f not in unintended_files:
                    unintended_files.append(f)
                    violations.append(f"Modification outside declared repair scope: {f}")

        has_side_effects = len(violations) > 0
        explanation = (
            f"Detected {len(violations)} out-of-scope side effects: " + "; ".join(violations)
            if has_side_effects
            else "All modifications fall strictly within verified repair perimeter."
        )

        return SideEffectReport(
            has_side_effects=has_side_effects,
            unintended_files=unintended_files,
            explanation=explanation,
        )
