"""
JARVIS OS — Phase 68: Quality Policy Configuration
Defines policy modes:
- STRICT: Zero debt tolerance, blocking on any non-trivial regression.
- GOVERNED: Balanced budget, permits manageable debt with tracking, blocks critical risks.
- LENIENT: Exploratory/experimental, flags warnings rather than blocking.
- CRITICAL_ONLY: Only blocks on critical security or catastrophic architecture violations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .models import QualityBudget


@dataclass
class QualityPolicy:
    name: str
    strict_mode: bool
    budget: QualityBudget
    allow_accepted_with_debt: bool
    require_human_review_on_uncertainty: bool
    uncertainty_threshold: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "strict_mode": self.strict_mode,
            "budget": self.budget.to_dict(),
            "allow_accepted_with_debt": self.allow_accepted_with_debt,
            "require_human_review_on_uncertainty": self.require_human_review_on_uncertainty,
            "uncertainty_threshold": self.uncertainty_threshold,
        }


POLICY_STRICT = QualityPolicy(
    name="STRICT",
    strict_mode=True,
    budget=QualityBudget(
        max_critical_debt=0,
        max_unresolved_contract_drift=0,
        max_security_debt=0,
        max_flaky_rate=0.01,
        max_regression_rate=0.0,
        max_architecture_degradation=0,
        max_quality_uncertainty=0.15,
        max_human_review_backlog=2,
    ),
    allow_accepted_with_debt=False,
    require_human_review_on_uncertainty=True,
    uncertainty_threshold=0.15,
)

POLICY_GOVERNED = QualityPolicy(
    name="GOVERNED",
    strict_mode=False,
    budget=QualityBudget(
        max_critical_debt=0,
        max_unresolved_contract_drift=0,
        max_security_debt=0,
        max_flaky_rate=0.05,
        max_regression_rate=0.02,
        max_architecture_degradation=0,
        max_quality_uncertainty=0.35,
        max_human_review_backlog=5,
    ),
    allow_accepted_with_debt=True,
    require_human_review_on_uncertainty=True,
    uncertainty_threshold=0.30,
)

POLICY_LENIENT = QualityPolicy(
    name="LENIENT",
    strict_mode=False,
    budget=QualityBudget(
        max_critical_debt=2,
        max_unresolved_contract_drift=2,
        max_security_debt=0,
        max_flaky_rate=0.15,
        max_regression_rate=0.10,
        max_architecture_degradation=2,
        max_quality_uncertainty=0.55,
        max_human_review_backlog=10,
    ),
    allow_accepted_with_debt=True,
    require_human_review_on_uncertainty=False,
    uncertainty_threshold=0.50,
)

POLICY_CRITICAL_ONLY = QualityPolicy(
    name="CRITICAL_ONLY",
    strict_mode=False,
    budget=QualityBudget(
        max_critical_debt=0,
        max_unresolved_contract_drift=5,
        max_security_debt=0,
        max_flaky_rate=0.30,
        max_regression_rate=0.20,
        max_architecture_degradation=5,
        max_quality_uncertainty=0.70,
        max_human_review_backlog=20,
    ),
    allow_accepted_with_debt=True,
    require_human_review_on_uncertainty=False,
    uncertainty_threshold=0.65,
)

POLICIES: Dict[str, QualityPolicy] = {
    "STRICT": POLICY_STRICT,
    "GOVERNED": POLICY_GOVERNED,
    "LENIENT": POLICY_LENIENT,
    "CRITICAL_ONLY": POLICY_CRITICAL_ONLY,
}


def get_policy(name: str = "GOVERNED") -> QualityPolicy:
    return POLICIES.get(name.upper(), POLICY_GOVERNED)
