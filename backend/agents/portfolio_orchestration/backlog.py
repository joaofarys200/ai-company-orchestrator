"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: backlog.py
Unified strategic backlog: ingestion, normalization, deduplication, and query.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Callable, Dict, List, Optional, Set

from .models import (
    EngineeringInitiative,
    EvidenceProvenance,
    InitiativeState,
    InitiativeType,
)


class PortfolioBacklog:
    """
    Unified backlog aggregating and normalizing engineering initiatives across disparate
    subsystems (debt remediation, architectural optimization, macro-refactoring, reliability).
    """

    def __init__(self):
        self._initiatives: Dict[str, EngineeringInitiative] = {}
        self._dedup_keys: Dict[str, str] = {}  # semantic_fingerprint -> initiative_id

    def add_initiative(self, initiative: EngineeringInitiative) -> Tuple[bool, str]:
        """
        Add a normalized initiative to the backlog.
        Returns (success, message). If duplicate is detected, rejects or links duplicate.
        """
        fingerprint = self._compute_semantic_fingerprint(initiative)
        if fingerprint in self._dedup_keys:
            existing_id = self._dedup_keys[fingerprint]
            return False, f"DUPLICATE_OBJECTIVE: Initiative '{initiative.id}' matches existing '{existing_id}'"

        self._initiatives[initiative.id] = initiative
        self._dedup_keys[fingerprint] = initiative.id
        return True, f"INITIATIVE_INGESTED: {initiative.id}"

    def get_initiative(self, initiative_id: str) -> Optional[EngineeringInitiative]:
        """Retrieve an initiative by ID."""
        return self._initiatives.get(initiative_id)

    def list_initiatives(
        self,
        state: Optional[InitiativeState] = None,
        initiative_type: Optional[InitiativeType] = None,
    ) -> List[EngineeringInitiative]:
        """List all initiatives matching optional filters."""
        res = list(self._initiatives.values())
        if state is not None:
            res = [i for i in res if i.state == state]
        if initiative_type is not None:
            res = [i for i in res if i.initiative_type == initiative_type]
        return res

    def update_state(self, initiative_id: str, new_state: InitiativeState, error_msg: Optional[str] = None) -> bool:
        """Update the lifecycle state of an initiative."""
        if initiative_id not in self._initiatives:
            return False
        init = self._initiatives[initiative_id]
        init.state = new_state
        if error_msg:
            init.error_message = error_msg
        if new_state == InitiativeState.COMPLETED and not init.completed_at:
            init.completed_at = time.time()
        return True

    def ingest_from_architectural_optimization(
        self,
        opp_id: str,
        title: str,
        affected_files: List[str],
        predicted_benefit: float,
        cost: float,
        confidence: float = 0.85,
        prerequisites: Optional[List[str]] = None,
    ) -> EngineeringInitiative:
        """Ingestion adapter for Phase 74 Architectural Optimization opportunities."""
        init = EngineeringInitiative(
            id=opp_id,
            title=title,
            initiative_type=InitiativeType.ARCHITECTURAL_OPTIMIZATION,
            description=f"Phase 74 architectural evolution opportunity targeting {len(affected_files)} components.",
            affected_components=affected_files,
            effort_units=max(1.0, cost / 10.0),
            budget_cost=cost,
            expected_benefit=predicted_benefit,
            confidence=confidence,
            prerequisites=prerequisites or [],
            evidence=EvidenceProvenance(
                source_phase="Phase 74",
                artifact_path=f"docs/optimization_{opp_id}.json",
                confidence=confidence,
            ),
        )
        self.add_initiative(init)
        return init

    def ingest_from_macro_refactoring(
        self,
        migration_id: str,
        title: str,
        affected_components: List[str],
        estimated_steps: int,
        expected_benefit: float,
        requires_approval: bool = False,
        prerequisites: Optional[List[str]] = None,
    ) -> EngineeringInitiative:
        """Ingestion adapter for Phase 73 Macro-Refactoring migrations."""
        init = EngineeringInitiative(
            id=migration_id,
            title=title,
            initiative_type=InitiativeType.MACRO_REFACTORING,
            description=f"Phase 73 cross-component macro-refactoring with {estimated_steps} steps.",
            affected_components=affected_components,
            effort_units=float(estimated_steps),
            budget_cost=float(estimated_steps * 15),
            expected_benefit=expected_benefit,
            confidence=0.9,
            requires_approval=requires_approval,
            prerequisites=prerequisites or [],
            evidence=EvidenceProvenance(
                source_phase="Phase 73",
                artifact_path=f"docs/macro_migration_{migration_id}.json",
                confidence=0.9,
            ),
        )
        self.add_initiative(init)
        return init

    def ingest_from_quality_debt(
        self,
        debt_id: str,
        title: str,
        affected_files: List[str],
        severity_score: float,
        remediation_cost: float,
        prerequisites: Optional[List[str]] = None,
    ) -> EngineeringInitiative:
        """Ingestion adapter for Phase 68/69 Technical Debt remediation."""
        init = EngineeringInitiative(
            id=debt_id,
            title=title,
            initiative_type=InitiativeType.TECHNICAL_DEBT_REMEDIATION,
            description=f"Phase 68/69 technical debt remediation item.",
            affected_components=affected_files,
            effort_units=max(1.0, remediation_cost / 10.0),
            budget_cost=remediation_cost,
            expected_benefit=severity_score * 10.0,
            confidence=0.95,
            prerequisites=prerequisites or [],
            evidence=EvidenceProvenance(
                source_phase="Phase 68/69",
                baseline_metric="debt_severity",
                baseline_value=severity_score,
                confidence=0.95,
            ),
        )
        self.add_initiative(init)
        return init

    def ingest_from_reliability(
        self,
        incident_id: str,
        title: str,
        affected_components: List[str],
        risk_reduction: float,
        cost: float,
    ) -> EngineeringInitiative:
        """Ingestion adapter for Phase 72 Reliability Intelligence preventive operations."""
        init = EngineeringInitiative(
            id=incident_id,
            title=title,
            initiative_type=InitiativeType.RELIABILITY_IMPROVEMENT,
            description=f"Phase 72 preventive reliability hardening operation.",
            affected_components=affected_components,
            effort_units=max(1.0, cost / 8.0),
            budget_cost=cost,
            expected_benefit=risk_reduction * 25.0,
            confidence=0.88,
            evidence=EvidenceProvenance(
                source_phase="Phase 72",
                baseline_metric="recurrence_probability",
                baseline_value=risk_reduction,
                confidence=0.88,
            ),
        )
        self.add_initiative(init)
        return init

    def _compute_semantic_fingerprint(self, initiative: EngineeringInitiative) -> str:
        """
        Compute normalized semantic hash of title + type + sorted affected components
        to detect duplicate objectives across disparate triggers.
        """
        norm_title = " ".join(initiative.title.lower().split())
        norm_components = ",".join(sorted([c.replace("\\", "/").strip().lower() for c in initiative.affected_components]))
        raw = f"{initiative.initiative_type.value}:{norm_title}:{norm_components}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
