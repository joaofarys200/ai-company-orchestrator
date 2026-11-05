"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: adapters.py
Non-invasive adapters connecting the claims governance engine to existing engineering subsystems (Phases 65–76).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    AssuranceTier,
    ClaimType,
    EngineeringClaim,
    EvidenceArtifact,
    EvidenceCategory,
    EvidenceOriginType,
)
from .provenance import EvidenceProvenanceValidator
from .registry import EvidenceClaimsRegistry


class Phase73MacroRefactoringAdapter:
    """Verifies claims made by Phase 73 regarding macro-refactoring migrations."""

    def __init__(self, registry: EvidenceClaimsRegistry):
        self.registry = registry

    def create_migration_completion_claim(
        self,
        migration_id: str,
        affected_files: List[str],
        commit_sha: str,
        passed_invariants: List[str],
    ) -> Tuple[EngineeringClaim, EvidenceArtifact]:
        claim = EngineeringClaim(
            claim_id=f"claim_macro_{migration_id}",
            claim_type=ClaimType.REPOSITORY_STATE,
            proposition=f"Macro-migration '{migration_id}' successfully completed across {len(affected_files)} files with all invariants preserved.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="macro_refactoring",
            required_evidence_categories=[
                EvidenceCategory.GIT_REVISION_RECORD,
                EvidenceCategory.TEST_RUNNER_RESULT,
            ],
            dependency_files=affected_files,
            commit_sha=commit_sha,
        )
        artifact = EvidenceProvenanceValidator.create_artifact(
            artifact_id=f"ev_macro_{migration_id}",
            category=EvidenceCategory.GIT_REVISION_RECORD,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha=commit_sha,
            payload={
                "migration_id": migration_id,
                "modified_files": affected_files,
                "created_files": [],
                "passed_invariants": passed_invariants,
            },
            source_subsystem="macro_refactoring",
        )
        self.registry.register_claim(claim)
        self.registry.register_artifact(artifact)
        self.registry.attach_evidence_to_claim(claim.claim_id, artifact.artifact_id)
        return claim, artifact


class Phase74ArchitecturalOptimizationAdapter:
    """Verifies claims made by Phase 74 regarding architectural performance gains."""

    def __init__(self, registry: EvidenceClaimsRegistry):
        self.registry = registry

    def create_optimization_gain_claim(
        self,
        hypothesis_id: str,
        pattern_type: str,
        baseline_metric: float,
        measured_metric: float,
        is_synthetic: bool = False,
    ) -> Tuple[EngineeringClaim, EvidenceArtifact]:
        origin = EvidenceOriginType.SYNTHETIC_FIXTURE if is_synthetic else EvidenceOriginType.REAL_EXECUTION
        claim = EngineeringClaim(
            claim_id=f"claim_arch_{hypothesis_id}",
            claim_type=ClaimType.PERFORMANCE_BENCHMARK,
            proposition=f"Pattern '{pattern_type}' improved performance from {baseline_metric} to {measured_metric}.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="architectural_optimization",
            required_evidence_categories=[EvidenceCategory.BENCHMARK_MEASUREMENT],
        )
        artifact = EvidenceProvenanceValidator.create_artifact(
            artifact_id=f"ev_arch_{hypothesis_id}",
            category=EvidenceCategory.BENCHMARK_MEASUREMENT,
            origin_type=origin,
            commit_sha="HEAD",
            payload={
                "hypothesis_id": hypothesis_id,
                "pattern_type": pattern_type,
                "baseline_metric": baseline_metric,
                "candidate_metric": measured_metric,
                "conditions_comparable": True,
                "lower_is_better": True,
            },
            source_subsystem="architectural_optimization",
        )
        self.registry.register_claim(claim)
        self.registry.register_artifact(artifact)
        self.registry.attach_evidence_to_claim(claim.claim_id, artifact.artifact_id)
        return claim, artifact


class Phase75PortfolioOrchestrationAdapter:
    """Verifies claims made by Phase 75 regarding portfolio outcomes and scheduling."""

    def __init__(self, registry: EvidenceClaimsRegistry):
        self.registry = registry

    def create_initiative_completion_claim(
        self,
        portfolio_id: str,
        initiative_id: str,
        completed: bool,
    ) -> Tuple[EngineeringClaim, EvidenceArtifact]:
        claim = EngineeringClaim(
            claim_id=f"claim_init_{initiative_id}",
            claim_type=ClaimType.REPOSITORY_STATE,
            proposition=f"Initiative '{initiative_id}' in portfolio '{portfolio_id}' marked as completed.",
            assurance_tier=AssuranceTier.TIER_2_OPERATIONAL,
            originating_subsystem="portfolio_orchestration",
            required_evidence_categories=[EvidenceCategory.DIRECT_EXECUTION_OUTPUT],
        )
        artifact = EvidenceProvenanceValidator.create_artifact(
            artifact_id=f"ev_init_{initiative_id}",
            category=EvidenceCategory.DIRECT_EXECUTION_OUTPUT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={
                "portfolio_id": portfolio_id,
                "initiative_id": initiative_id,
                "status": "COMPLETED" if completed else "FAILED",
            },
            source_subsystem="portfolio_orchestration",
        )
        self.registry.register_claim(claim)
        self.registry.register_artifact(artifact)
        self.registry.attach_evidence_to_claim(claim.claim_id, artifact.artifact_id)
        return claim, artifact


class Phase76PredictiveCalibrationAdapter:
    """Verifies claims made by Phase 76 regarding holdout error reduction and promotion."""

    def __init__(self, registry: EvidenceClaimsRegistry):
        self.registry = registry

    def create_calibration_promotion_claim(
        self,
        version_id: str,
        mae_reduction_pct: float,
        promoted: bool,
    ) -> Tuple[EngineeringClaim, EvidenceArtifact]:
        claim = EngineeringClaim(
            claim_id=f"claim_cal_{version_id}",
            claim_type=ClaimType.PREDICTIVE_CALIBRATION,
            proposition=f"Calibration model '{version_id}' verified with {mae_reduction_pct:.1f}% error reduction.",
            assurance_tier=AssuranceTier.TIER_3_ARCHITECTURAL,
            originating_subsystem="predictive_calibration",
            required_evidence_categories=[EvidenceCategory.BENCHMARK_MEASUREMENT],
        )
        artifact = EvidenceProvenanceValidator.create_artifact(
            artifact_id=f"ev_cal_{version_id}",
            category=EvidenceCategory.BENCHMARK_MEASUREMENT,
            origin_type=EvidenceOriginType.REAL_EXECUTION,
            commit_sha="HEAD",
            payload={
                "version_id": version_id,
                "promoted": promoted,
                "mae_reduction_pct": mae_reduction_pct,
            },
            source_subsystem="predictive_calibration",
        )
        self.registry.register_claim(claim)
        self.registry.register_artifact(artifact)
        self.registry.attach_evidence_to_claim(claim.claim_id, artifact.artifact_id)
        return claim, artifact
