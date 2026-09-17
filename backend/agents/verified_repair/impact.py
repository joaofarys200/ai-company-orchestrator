"""
JARVIS OS — Phase 54: Patch Impact Analysis Engine
Forecasts affected files, symbols, tasks, contracts, and consumers prior to patch application.
"""

from __future__ import annotations

import os
from typing import List, Optional

from agents.verified_repair.models import FilePatchDiff, PredictedRepairImpact


class PatchImpactAnalyzer:
    """
    Ex-ante impact analysis engine predicting the blast radius of proposed patches.
    """

    def analyze_patch_impact(
        self,
        patches: List[FilePatchDiff],
        cause_category: str = "",
        workspace_dir: str = "",
    ) -> PredictedRepairImpact:
        predicted_files = [p.relative_path for p in patches]
        predicted_symbols: List[str] = []
        predicted_tasks: List[str] = []
        predicted_contracts: List[str] = []
        predicted_consumers: List[str] = []
        predicted_behavior_changes: List[str] = []

        # Analyze symbols added or referenced in patch
        for patch in patches:
            added_lines = [line for line in patch.patched_content.splitlines() if line not in patch.original_content]
            for line in added_lines:
                if "express" in line.lower():
                    predicted_symbols.append("express")
                if "app." in line:
                    predicted_symbols.append("app")
                if "axios" in line.lower():
                    predicted_symbols.append("axios")
                if "router" in line.lower():
                    predicted_symbols.append("router")

        # Associate affected tasks based on modified files
        for f in predicted_files:
            if "app.js" in f or "server.js" in f or "main.py" in f:
                predicted_tasks.append("TSK_PREFLIGHT_STARTUP_VERIFY")
                predicted_tasks.append("TSK_HEALTHCHECK_SMOKE")
                predicted_contracts.append("API_ROOT_ENDPOINT")
                predicted_consumers.append("web_frontend")
                predicted_consumers.append("external_api_clients")
            if "package.json" in f or "requirements.txt" in f:
                predicted_tasks.append("TSK_DEPENDENCY_AUDIT")

        # Determine predicted behavioral modifications
        if cause_category in ("RUNTIME_SCOPE_ERROR", "STARTUP_FAILURE"):
            predicted_behavior_changes.append("Process transitions from immediate exit to continuous listening socket.")
            predicted_behavior_changes.append("HTTP requests to exposed routes become serviceable.")
        elif cause_category == "PORT_CONFLICT":
            predicted_behavior_changes.append("Socket binding port is adjusted to free local port.")

        # Compute predicted risk
        base_risk = 0.05 * len(predicted_files)
        if "package.json" in predicted_files:
            base_risk += 0.15
        if len(predicted_symbols) > 5:
            base_risk += 0.10
        predicted_risk = min(0.95, max(0.05, base_risk))

        confidence = 0.95 if len(predicted_files) <= 2 else 0.80

        return PredictedRepairImpact(
            predicted_files=predicted_files,
            predicted_symbols=list(set(predicted_symbols)),
            predicted_tasks=list(set(predicted_tasks)),
            predicted_contracts=list(set(predicted_contracts)),
            predicted_consumers=list(set(predicted_consumers)),
            predicted_behavior_changes=predicted_behavior_changes,
            predicted_risk=predicted_risk,
            confidence=confidence,
        )
