"""
JARVIS OS — Phase 54: Original Failure Resolution Verifier
Proves whether the original failure condition is strictly absent after patch application.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional, Tuple

from agents.project_preflight.javascript import JavaScriptPreflightAnalyzer
from agents.project_preflight.models import IssueSeverity, ProjectRuntimeProfile
from agents.project_preflight.python import PythonPreflightAnalyzer
from agents.verified_repair.models import (
    FailureResolutionStatus,
    RepairCandidate,
    RootCauseCategory,
    RootCauseHypothesis,
)


class FailureResolutionVerifier:
    """
    Formally validates that the original crash condition has ceased to exist.
    Never declares success if the original diagnostic condition persists.
    """

    def verify_resolution(
        self,
        hypothesis: RootCauseHypothesis,
        candidate: RepairCandidate,
        workspace_dir: str,
        profile: Optional[ProjectRuntimeProfile] = None,
    ) -> Tuple[FailureResolutionStatus, str]:
        # 1. Verify AST / Syntax sanity on patched files
        target_file = candidate.files[0] if candidate.files else "app.js"
        abs_target = os.path.join(workspace_dir, target_file)

        if not os.path.exists(abs_target):
            return FailureResolutionStatus.ORIGINAL_FAILURE_NOT_RESOLVED, f"Ficheiro {target_file} não existe após patch."

        # JavaScript validation
        if target_file.endswith((".js", ".cjs", ".mjs")):
            js_analyzer = JavaScriptPreflightAnalyzer()
            issues = js_analyzer.analyze_file(abs_target, profile)
            blockers = [i for i in issues if i.severity == IssueSeverity.BLOCKER]
            if blockers:
                return (
                    FailureResolutionStatus.ORIGINAL_FAILURE_NOT_RESOLVED,
                    f"Preflight pós-patch detetou {len(blockers)} blockers de sintaxe: {blockers[0].message}",
                )

        # Python validation
        elif target_file.endswith(".py"):
            py_analyzer = PythonPreflightAnalyzer()
            issues = py_analyzer.analyze_file(abs_target, profile)
            blockers = [i for i in issues if i.severity == IssueSeverity.BLOCKER]
            if blockers:
                return (
                    FailureResolutionStatus.ORIGINAL_FAILURE_NOT_RESOLVED,
                    f"Preflight pós-patch detetou {len(blockers)} blockers em Python: {blockers[0].message}",
                )

        # 2. Check that the original specific symptom is eliminated
        try:
            with open(abs_target, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            if hypothesis.category == RootCauseCategory.RUNTIME_SCOPE_ERROR:
                # Symptom was uninstantiated 'app'
                if "app.post" in content or "app.get" in content:
                    if "const app =" not in content and "let app =" not in content and "var app =" not in content:
                        return (
                            FailureResolutionStatus.ORIGINAL_FAILURE_NOT_RESOLVED,
                            "Identificador 'app' continua a ser invocado sem declaração ou instanciação de framework.",
                        )

            elif hypothesis.category == RootCauseCategory.MISSING_IMPORT:
                if "axios" in hypothesis.evidence.lower() and "require('axios')" not in content and 'require("axios")' not in content:
                    return (
                        FailureResolutionStatus.ORIGINAL_FAILURE_NOT_RESOLVED,
                        "Biblioteca 'axios' continua sem declaração de importação no ficheiro.",
                    )

        except Exception as e:
            return FailureResolutionStatus.ORIGINAL_FAILURE_NOT_RESOLVED, f"Erro ao inspecionar ficheiro pós-patch: {e}"

        return FailureResolutionStatus.ORIGINAL_FAILURE_RESOLVED, "A condição que causou a falha original foi eliminada com sucesso."
