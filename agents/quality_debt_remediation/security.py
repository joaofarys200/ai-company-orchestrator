"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Quality gaming defense and security gate engine.
Actively detects metric gaming, scope manipulation, test deletion, and enforces non-bypassable security invariants.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .models import GamingType, QualityGamingEvent


class QualityGamingDetector:
    """
    Guards against superficial metric optimization and quality gaming behaviors:
    - deleting tests to increase velocity
    - excluding problematic files from scan scope
    - lowering thresholds to bypass gates
    - suppressing debt without addressing root causes
    - shifting problems into unmeasured modules
    """

    PROTECTED_PATHS = [
        "backend/security",
        "backend/sentinel",
        "backend/governance",
        "tests/test_security",
    ]

    def detect_gaming(
        self,
        actor: str,
        deleted_test_files: Optional[List[str]] = None,
        excluded_scope_paths: Optional[List[str]] = None,
        altered_thresholds: Optional[Dict[str, float]] = None,
        reclassified_unknown: bool = False,
        shifted_unmeasured_files: Optional[List[str]] = None,
    ) -> Optional[QualityGamingEvent]:
        # 1. Test Deletion Detection
        if deleted_test_files:
            return QualityGamingEvent(
                event_id=f"game_{uuid.uuid4().hex[:8]}",
                gaming_type=GamingType.TEST_DELETION,
                actor=actor,
                reason=f"Attempted deletion of test suite(s): {', '.join(deleted_test_files)} to artificially increase pass velocity.",
                blocked=True,
            )

        # 2. Scope Exclusion Detection
        if excluded_scope_paths:
            return QualityGamingEvent(
                event_id=f"game_{uuid.uuid4().hex[:8]}",
                gaming_type=GamingType.SCOPE_EXCLUSION,
                actor=actor,
                reason=f"Attempted exclusion of file paths from quality governance scope: {', '.join(excluded_scope_paths)}.",
                blocked=True,
            )

        # 3. Threshold Tampering Detection
        if altered_thresholds:
            lowered = [k for k, v in altered_thresholds.items() if v < 0.8]
            if lowered:
                return QualityGamingEvent(
                    event_id=f"game_{uuid.uuid4().hex[:8]}",
                    gaming_type=GamingType.THRESHOLD_TAMPERING,
                    actor=actor,
                    reason=f"Attempted lowering of quality threshold(s): {', '.join(lowered)} to bypass gate.",
                    blocked=True,
                )

        # 4. Unknown Reclassification Detection
        if reclassified_unknown:
            return QualityGamingEvent(
                event_id=f"game_{uuid.uuid4().hex[:8]}",
                gaming_type=GamingType.UNKNOWN_RECLASSIFICATION,
                actor=actor,
                reason="Attempted reclassification of UNKNOWN debt as NO_DEBT without root cause resolution.",
                blocked=True,
            )

        # 5. Shift to Unmeasured Zone
        if shifted_unmeasured_files:
            return QualityGamingEvent(
                event_id=f"game_{uuid.uuid4().hex[:8]}",
                gaming_type=GamingType.UNMEASURED_SHIFT,
                actor=actor,
                reason=f"Attempted relocation of problematic code to unmeasured surfaces: {', '.join(shifted_unmeasured_files)}.",
                blocked=True,
            )

        return None

    def validate_security_invariants(
        self,
        target_files: List[str],
        is_security_debt: bool = False,
        has_sentinel_mutation: bool = False,
    ) -> Dict[str, Any]:
        """
        Enforces non-negotiable security gates:
        - Sentinel deletion or mutation is strictly forbidden.
        - Critical security debt requires hard stop unless verified.
        """
        violations = []

        if has_sentinel_mutation:
            violations.append("Unauthorized mutation or deletion of Sentinel security infrastructure.")

        for f in target_files:
            for protected in self.PROTECTED_PATHS:
                if protected in f:
                    violations.append(f"Modification to protected security boundary '{f}' is restricted.")

        if violations:
            return {
                "security_gate_passed": False,
                "hard_blocked": True,
                "violations": violations,
            }

        return {
            "security_gate_passed": True,
            "hard_blocked": False,
            "violations": [],
        }
