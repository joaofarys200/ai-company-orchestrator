"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Confidence Evaluator: Classifies repair proposals into HIGH, MEDIUM, or LOW confidence.
Guarantees that LOW confidence can NEVER execute auto-repair.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.project_preflight.models import (
    DiagnosticErrorClass,
    RepairCategory,
    RepairConfidence,
    RuntimeDiagnostic,
)


class RepairConfidenceEvaluator:
    """
    Evaluates evidence strength to categorize repair confidence.
    """

    def evaluate_confidence(
        self,
        diagnostic: RuntimeDiagnostic,
        category: RepairCategory,
        has_deterministic_target: bool,
        candidate_count: int,
        is_known_symbol: bool,
    ) -> RepairConfidence:
        # 1. High Confidence Criteria:
        # Deterministic single fix target + known symbol / standard idiom
        if (
            has_deterministic_target
            and candidate_count == 1
            and is_known_symbol
            and diagnostic.confidence >= 0.90
        ):
            return RepairConfidence.HIGH_CONFIDENCE

        # 2. Medium Confidence Criteria:
        # Clear category and deterministic file, but slightly lower confidence or minor ambiguity
        if (
            has_deterministic_target
            and candidate_count <= 2
            and diagnostic.confidence >= 0.70
        ):
            return RepairConfidence.MEDIUM_CONFIDENCE

        # 3. Low Confidence (Fallback for unknown symbols or multiple ambiguous interpretations):
        # LOW confidence is strictly BLOCKED from auto-repair.
        return RepairConfidence.LOW_CONFIDENCE
