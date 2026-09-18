"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: policy.py
Governance policies governing framework selection, execution sandboxing, economic constraints,
and repair verification requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from .models import TestFramework


@dataclass
class TestSynthesisPolicy:
    """Policy rules governing Phase 61."""

    allowed_frameworks: Set[TestFramework] = field(
        default_factory=lambda: {
            TestFramework.PYTEST,
            TestFramework.VITEST,
            TestFramework.JEST,
            TestFramework.PLAYWRIGHT,
        }
    )
    max_candidates_per_cycle: int = 100
    max_execution_timeout_seconds: float = 30.0
    min_composite_coverage: float = 0.75
    enforce_economic_sandbox: bool = True
    enforce_security_sentinel: bool = True
    require_zero_mutants_survived_in_critical: bool = True

    def validate_framework(self, framework: TestFramework) -> bool:
        return framework in self.allowed_frameworks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed_frameworks": [f.value for f in self.allowed_frameworks],
            "max_candidates_per_cycle": self.max_candidates_per_cycle,
            "max_execution_timeout_seconds": self.max_execution_timeout_seconds,
            "min_composite_coverage": self.min_composite_coverage,
            "enforce_economic_sandbox": self.enforce_economic_sandbox,
            "enforce_security_sentinel": self.enforce_security_sentinel,
            "require_zero_mutants_survived_in_critical": self.require_zero_mutants_survived_in_critical,
        }
