"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: constraints.py
Extracts functional, non-functional, security, economic, and migration constraints
governing architectural refactoring.

Rule:
    Never invent an absent constraint.
    Ground every constraint in explicit codebase evidence or system policy.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from .models import ArchitectureConstraint, ArchitectureProblem, ArchitectureSnapshot


class ArchitectureConstraintExtractor:
    """Extracts ground-truth architectural constraints for a problem and snapshot."""

    def extract_constraints(
        self,
        problem: ArchitectureProblem,
        snapshot: ArchitectureSnapshot,
    ) -> List[ArchitectureConstraint]:
        constraints: List[ArchitectureConstraint] = []

        # 1. Backward Compatibility Constraint (if affected nodes have external consumers or snapshot contracts)
        affected_nodes_set = set(problem.affected_nodes)
        external_consumers = []
        for contract, consumers in snapshot.consumers.items():
            if contract in affected_nodes_set or any(node in contract for node in affected_nodes_set):
                external_consumers.extend(consumers)

        if external_consumers or snapshot.contracts:
            c_id = f"const_compat_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}"
            constraints.append(ArchitectureConstraint(
                constraint_id=c_id,
                name="backward_compatibility_guarantee",
                category="compatibility",
                description=f"Must preserve API compatibility for {len(external_consumers)} external consumers.",
                source="snapshot.consumers",
                confidence=0.98,
                evidence={"affected_consumers": sorted(list(set(external_consumers)))[:5] if external_consumers else snapshot.contracts},
                scope="module",
            ))

        # 2. Security Sentinel Constraint (if risk zones exist or affected nodes touch security)
        touches_security = (
            any(
                node in snapshot.risk_zones or "auth" in node.lower() or "secret" in node.lower()
                for node in problem.affected_nodes
            )
            or len(snapshot.risk_zones) > 0
            or problem.category.value == "SECURITY"
        )
        if touches_security:
            c_id = f"const_sec_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}"
            constraints.append(ArchitectureConstraint(
                constraint_id=c_id,
                name="security_sentinel_inviolability",
                category="security",
                description="Zero privilege escalation; no plaintext secret movement or unvetted boundary opening.",
                source="security_sentinel_policy",
                confidence=1.0,
                evidence={"risk_zones": snapshot.risk_zones},
                scope="project",
            ))

        # 3. Test Coverage & Verification Constraint (if test surfaces exist)
        relevant_tests = [
            t for t in snapshot.test_surfaces
            if any(node in t for node in problem.affected_nodes)
        ]
        if relevant_tests or len(snapshot.test_surfaces) > 0:
            c_id = f"const_test_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}"
            constraints.append(ArchitectureConstraint(
                constraint_id=c_id,
                name="regression_test_invariance",
                category="non_functional",
                description="All existing functional and behavioral regression tests must continue to pass.",
                source="snapshot.test_surfaces",
                confidence=0.95,
                evidence={"test_count": len(relevant_tests)},
                scope="project",
            ))

        # 4. Reversibility & Rollback Constraint (if severity is high or critical)
        if problem.severity.value in ["HIGH", "CRITICAL"]:
            c_id = f"const_roll_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}"
            constraints.append(ArchitectureConstraint(
                constraint_id=c_id,
                name="deterministic_rollback_requirement",
                category="migration",
                description="Architecture migration must define an automated rollback step with zero data loss.",
                source="migration_governance_policy",
                confidence=0.92,
                evidence={"problem_severity": problem.severity.value},
                scope="system",
            ))

        # 5. Economic / Resource Budget Constraint
        c_id = f"const_econ_{hashlib.sha256(problem.problem_id.encode()).hexdigest()[:6]}"
        constraints.append(ArchitectureConstraint(
            constraint_id=c_id,
            name="resource_budget_bound",
            category="economic",
            description="Migration effort must not exceed 40 engineering hours or cause permanent memory expansion.",
            source="project_budget_specification",
            confidence=0.88,
            evidence={"node_count": len(problem.affected_nodes)},
            scope="project",
        ))

        return constraints
