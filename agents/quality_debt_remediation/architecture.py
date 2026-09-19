"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Architecture integration engine (Phase 64).
Evaluates architectural refactoring blast radius and blocks un-governed high-risk changes.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ArchitectureRefactoringEvaluation:
    eval_id: str
    surface: str
    problem_type: str
    alternatives: List[str]
    blast_radius_nodes: int
    breaking_contracts: bool
    behavior_drift: bool
    security_risk: bool
    is_irreversible: bool
    permitted_autonomous: bool
    governance_required: bool
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DebtArchitectureEvaluator:
    """
    Evaluates proposed architectural debt refactorings against Phase 64 SCC and dependency graphs.
    Blocks automated execution if contracts break, behavior drifts, or security policies are violated.
    """

    def evaluate_refactoring(
        self,
        surface: str,
        problem_type: str,
        alternatives: List[str],
        blast_radius_nodes: int,
        breaking_contracts: bool = False,
        behavior_drift: bool = False,
        security_risk: bool = False,
        is_irreversible: bool = False,
    ) -> ArchitectureRefactoringEvaluation:
        eval_id = f"arch_{uuid.uuid4().hex[:8]}"

        # Un-governed blocker conditions
        blockers = []
        if breaking_contracts:
            blockers.append("Breaking public contracts")
        if behavior_drift:
            blockers.append("Unresolved behavior drift")
        if security_risk:
            blockers.append("Unresolved security risk")
        if is_irreversible:
            blockers.append("Irreversible migration strategy")

        if blockers:
            permitted = False
            governance_required = True
            rationale = f"Automated refactoring blocked due to: {', '.join(blockers)}. Governance approval required."
        elif blast_radius_nodes > 15:
            permitted = False
            governance_required = True
            rationale = f"High blast radius ({blast_radius_nodes} nodes > 15 max autonomous limit). Architectural review required."
        else:
            permitted = True
            governance_required = False
            rationale = f"Architectural refactoring within safe autonomous limits ({blast_radius_nodes} nodes, zero contract/security breaks)."

        return ArchitectureRefactoringEvaluation(
            eval_id=eval_id,
            surface=surface,
            problem_type=problem_type,
            alternatives=alternatives,
            blast_radius_nodes=blast_radius_nodes,
            breaking_contracts=breaking_contracts,
            behavior_drift=behavior_drift,
            security_risk=security_risk,
            is_irreversible=is_irreversible,
            permitted_autonomous=permitted,
            governance_required=governance_required,
            rationale=rationale,
        )
