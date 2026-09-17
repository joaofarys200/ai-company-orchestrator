"""
JARVIS OS — Phase 54: Patch Minimality Evaluator
Calculates syntactic and blast-radius metrics to evaluate minimal valid repairs.
"""

from __future__ import annotations

import difflib
from typing import List

from agents.verified_repair.models import FilePatchDiff, PatchMinimalityMetrics


class PatchMinimalityEvaluator:
    """
    Evaluates whether a patch constitutes a minimal valid repair.
    Balances surgical change size against validity and behavioral blast radius.
    """

    def evaluate_minimality(
        self,
        patches: List[FilePatchDiff],
        is_config_changed: bool = False,
        dependencies_changed: int = 0,
        behavioral_surface_changed: bool = False,
    ) -> PatchMinimalityMetrics:
        files_changed = len(patches)
        total_added = sum(p.lines_added for p in patches)
        total_removed = sum(p.lines_removed for p in patches)

        # Estimate symbols changed by simple token diff
        symbols_count = 0
        for patch in patches:
            orig_lines = patch.original_content.splitlines()
            patch_lines = patch.patched_content.splitlines()
            diff = list(difflib.unified_diff(orig_lines, patch_lines))
            # Count modified lines starting with + or -
            for line in diff:
                if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                    # Simple heuristic: words that look like identifiers
                    words = [w for w in line[1:].split() if w.isidentifier()]
                    symbols_count += len(set(words))

        # Minimality scoring formula:
        # Starts at 1.0; penalized by file count, line churn, dependencies, and surface expansion
        penalty = (
            (files_changed - 1) * 0.15
            + (total_added * 0.01)
            + (total_removed * 0.015)
            + (dependencies_changed * 0.10)
            + (0.15 if is_config_changed else 0.0)
            + (0.20 if behavioral_surface_changed else 0.0)
        )
        score = max(0.1, min(1.0, 1.0 - penalty))

        return PatchMinimalityMetrics(
            files_changed=files_changed,
            lines_added=total_added,
            lines_removed=total_removed,
            symbols_changed=symbols_count,
            dependencies_changed=dependencies_changed,
            config_changed=is_config_changed,
            behavioral_surface_changed=behavioral_surface_changed,
            minimality_score=score,
        )
