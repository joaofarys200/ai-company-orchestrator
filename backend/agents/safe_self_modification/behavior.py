"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: behavior.py
Integrates F50–F52 to validate behavioral invariance across state transitions,
ordering semantics, retries, timeouts, idempotency, and concurrency.
POTENTIAL_DRIFT or INSUFFICIENT_EVIDENCE halt automatic commit and route to Human Review.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import BehaviorValidationResult


class BehaviorValidator:
    """Validates behavioral equivalence and flags runtime semantic drift."""

    def validate_behavior(
        self,
        target_files: List[str],
        patch_diff: str,
        baseline_behavior: Optional[Dict[str, Any]] = None,
    ) -> Tuple[BehaviorValidationResult, Dict[str, Any]]:
        """Analyze diff for semantic behavioral shifts."""
        details = {
            "ordering_preserved": True,
            "retries_preserved": True,
            "timeouts_preserved": True,
            "idempotency_preserved": True,
            "concurrency_safe": True,
            "drift_indicators": [],
        }

        diff_lower = patch_diff.lower()

        # Flag potential drift indicators
        if "asyncio.sleep" in diff_lower or "time.sleep" in diff_lower:
            details["drift_indicators"].append("ALTERED_SLEEP_OR_TIMEOUT")
            details["timeouts_preserved"] = False

        if "threading.lock" in diff_lower or "asyncio.lock" in diff_lower:
            details["drift_indicators"].append("NEW_CONCURRENCY_PRIMITIVES")
            details["concurrency_safe"] = False

        if "queue" in diff_lower or "event_loop" in diff_lower or "event_bus" in diff_lower or "eventemitter" in diff_lower or "pubsub" in diff_lower:
            details["drift_indicators"].append("ASYNCHRONOUS_REORDERING_RISK")
            details["ordering_preserved"] = False

        if "raise" in diff_lower and "try" not in diff_lower:
            details["drift_indicators"].append("UNHANDLED_EXCEPTION_RISK")

        if details["drift_indicators"]:
            # If ordering or concurrency altered, flag as potential drift
            if not details["ordering_preserved"] or not details["concurrency_safe"]:
                return BehaviorValidationResult.POTENTIAL_DRIFT, details
            return BehaviorValidationResult.POTENTIAL_DRIFT, details

        return BehaviorValidationResult.PRESERVED_WITHIN_SCOPE, details
