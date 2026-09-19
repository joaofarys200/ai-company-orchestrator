"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Remediation policy engine. Defines STRICT, GOVERNED, and LENIENT policy profiles and enforces constraints.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict


class RemediationPolicyLevel(str, Enum):
    STRICT = "STRICT"
    GOVERNED = "GOVERNED"
    LENIENT = "LENIENT"


@dataclass
class RemediationPolicyConfig:
    level: RemediationPolicyLevel
    max_cost_limit: float
    max_risk_threshold: float
    max_blast_radius_files: int
    require_human_on_contract_change: bool
    require_human_on_security_debt: bool
    allow_partial_remediation: bool
    allow_deferment: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value if isinstance(self.level, RemediationPolicyLevel) else str(self.level),
            "max_cost_limit": self.max_cost_limit,
            "max_risk_threshold": self.max_risk_threshold,
            "max_blast_radius_files": self.max_blast_radius_files,
            "require_human_on_contract_change": self.require_human_on_contract_change,
            "require_human_on_security_debt": self.require_human_on_security_debt,
            "allow_partial_remediation": self.allow_partial_remediation,
            "allow_deferment": self.allow_deferment,
        }


class RemediationPolicyEngine:
    """
    Supplies policy configurations based on desired operational rigor.
    """

    POLICIES = {
        RemediationPolicyLevel.STRICT: RemediationPolicyConfig(
            level=RemediationPolicyLevel.STRICT,
            max_cost_limit=4.0,
            max_risk_threshold=0.30,
            max_blast_radius_files=3,
            require_human_on_contract_change=True,
            require_human_on_security_debt=True,
            allow_partial_remediation=True,
            allow_deferment=True,
        ),
        RemediationPolicyLevel.GOVERNED: RemediationPolicyConfig(
            level=RemediationPolicyLevel.GOVERNED,
            max_cost_limit=8.0,
            max_risk_threshold=0.50,
            max_blast_radius_files=8,
            require_human_on_contract_change=True,
            require_human_on_security_debt=True,
            allow_partial_remediation=True,
            allow_deferment=True,
        ),
        RemediationPolicyLevel.LENIENT: RemediationPolicyConfig(
            level=RemediationPolicyLevel.LENIENT,
            max_cost_limit=15.0,
            max_risk_threshold=0.75,
            max_blast_radius_files=20,
            require_human_on_contract_change=False,
            require_human_on_security_debt=False,
            allow_partial_remediation=True,
            allow_deferment=True,
        ),
    }

    def get_policy(self, level: RemediationPolicyLevel = RemediationPolicyLevel.GOVERNED) -> RemediationPolicyConfig:
        return self.POLICIES.get(level, self.POLICIES[RemediationPolicyLevel.GOVERNED])
