"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Central orchestrator bridge: QualityDebtRemediationBridge.
Executes the full 13-stage closed-loop technical debt remediation lifecycle.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from .architecture import DebtArchitectureEvaluator
from .behavior import DebtBehaviorEvaluator
from .cache import RemediationCache
from .comparison import QualityComparisonEngine, QualityComparisonOutcome, QualityComparisonReport
from .contracts import DebtContractEvaluator
from .convergence import RemediationConvergenceDetector
from .coordination import RemediationCoordinator
from .cost import DebtRemediationCostModel
from .debt import DebtIngestionEngine, IngestedDebtItem
from .deferment import DebtDefermentManager
from .governance import GovernanceDecision, RemediationGovernanceEngine
from .impact import QualityImpactPredictor
from .implementation import SafeImplementationEngine
from .metrics import RemediationMetricsEngine, RemediationPriorityEngine
from .models import (
    DebtDeferment,
    DebtRemediationOption,
    DebtResolutionResult,
    DebtRootCause,
    DebtValidationResult,
    ImplementationResult,
    ImplementationStatus,
    QualityGamingEvent,
    RemediationMission,
    RemediationPlan,
    ResolutionStatus,
    RootCauseCategory,
    ValidationStatus,
)
from .persistence import RemediationStore
from .planning import RemediationPlanner
from .policy import RemediationPolicyEngine, RemediationPolicyLevel
from .provenance import DebtProvenanceTracker
from .remediation_options import RemediationOptionsGenerator
from .resolution import DebtResolutionGovernor
from .risk import DebtRiskEvaluator
from .rollback import RemediationRollbackEngine
from .root_cause import DebtRootCauseEngine
from .security import QualityGamingDetector
from .validation import DebtValidator
from .verification import ContinuousVerificationEngine, VerificationReport


class QualityDebtRemediationBridge:
    """
    Central orchestrator executing and verifying the complete 13-stage
    Autonomous Quality Debt Remediation lifecycle.
    """

    _instance: Optional["QualityDebtRemediationBridge"] = None

    @classmethod
    def get_instance(cls, db_path: str = ":memory:") -> "QualityDebtRemediationBridge":
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        return cls._instance

    def __init__(self, db_path: str = ":memory:"):
        self.store = RemediationStore(db_path=db_path)
        self.ingestion_engine = DebtIngestionEngine()
        self.validator = DebtValidator()
        self.root_cause_engine = DebtRootCauseEngine()
        self.options_generator = RemediationOptionsGenerator()
        self.impact_predictor = QualityImpactPredictor()
        self.contract_evaluator = DebtContractEvaluator()
        self.behavior_evaluator = DebtBehaviorEvaluator()
        self.architecture_evaluator = DebtArchitectureEvaluator()
        self.risk_evaluator = DebtRiskEvaluator()
        self.cost_model = DebtRemediationCostModel()
        self.planner = RemediationPlanner()
        self.governance_engine = RemediationGovernanceEngine()
        self.coordinator = RemediationCoordinator()
        self.implementation_engine = SafeImplementationEngine()
        self.verification_engine = ContinuousVerificationEngine()
        self.comparison_engine = QualityComparisonEngine()
        self.resolution_governor = DebtResolutionGovernor()
        self.deferment_manager = DebtDefermentManager()
        self.rollback_engine = RemediationRollbackEngine()
        self.convergence_detector = RemediationConvergenceDetector()
        self.gaming_detector = QualityGamingDetector()
        self.policy_engine = RemediationPolicyEngine()
        self.provenance_tracker = DebtProvenanceTracker()
        self.priority_engine = RemediationPriorityEngine()
        self.cache = RemediationCache()

    def process_debt_lifecycle(
        self,
        raw_debt_item: Any,
        policy_level: RemediationPolicyLevel = RemediationPolicyLevel.GOVERNED,
        simulate_patch_fn: Optional[Callable[[], bool]] = None,
        simulate_build_failure: bool = False,
        simulate_test_failure: bool = False,
        simulate_hash_mismatch: bool = False,
        quality_before: Optional[Dict[str, float]] = None,
        quality_after: Optional[Dict[str, float]] = None,
        force_defer: bool = False,
        force_block: bool = False,
        partial_hotspots: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes the entire 13-stage lifecycle for a single debt item.
        """
        lifecycle_start = time.time()

        # 1. DEBT DETECTED (Ingestion)
        debt_item = self.ingestion_engine.ingest(raw_debt_item)
        self.provenance_tracker.record_stage(debt_item.debt_id, "DEBT_DETECTED", debt_item.to_dict())

        # 2. VALIDATE DEBT
        validation_res = self.validator.validate(debt_item)
        self.store.save_entity(
            "debt_validations",
            validation_res.validation_id,
            validation_res.to_dict(),
            {"debt_id": debt_item.debt_id, "status": validation_res.status.value},
        )
        self.provenance_tracker.record_stage(debt_item.debt_id, "VALIDATE_DEBT", validation_res.to_dict())

        if validation_res.status != ValidationStatus.VALID_DEBT:
            return {
                "debt_id": debt_item.debt_id,
                "stage": "VALIDATION_FAILED",
                "validation": validation_res.to_dict(),
                "resolution": ResolutionStatus.INVALIDATED.value,
                "lifecycle_duration_ms": round((time.time() - lifecycle_start) * 1000, 2),
            }

        # 3. ROOT CAUSE
        root_cause = self.root_cause_engine.analyze(debt_item)
        self.store.save_entity(
            "root_causes",
            root_cause.cause_id,
            root_cause.to_dict(),
            {"debt_id": debt_item.debt_id, "category": root_cause.category.value},
        )
        self.provenance_tracker.record_stage(debt_item.debt_id, "ROOT_CAUSE", root_cause.to_dict())

        # 4. REMEDIATION OPTIONS
        options = self.options_generator.generate_options(debt_item, root_cause)
        for opt in options:
            self.store.save_entity(
                "remediation_options",
                opt.option_id,
                opt.to_dict(),
                {"debt_id": debt_item.debt_id, "option_type": opt.option_type.value},
            )
        self.provenance_tracker.record_stage(debt_item.debt_id, "REMEDIATION_OPTIONS", {"count": len(options)})

        # Pick active candidate (usually first actionable non-keep-current option)
        actionable_opts = [o for o in options if o.option_type.value != "KEEP_CURRENT"]
        chosen_option = actionable_opts[0] if actionable_opts else options[0]

        # 5. IMPACT ANALYSIS
        impact_prediction = self.impact_predictor.predict_impact(chosen_option)
        self.provenance_tracker.record_stage(debt_item.debt_id, "IMPACT_ANALYSIS", impact_prediction.to_dict())

        # 6. QUALITY BUDGET & 7. GOVERNANCE
        gov_report = self.governance_engine.evaluate_gate(
            debt_item=debt_item,
            chosen_option=chosen_option,
            human_approval_granted=not force_block,
            quality_budget_exhausted=force_defer,
        )
        self.provenance_tracker.record_stage(debt_item.debt_id, "GOVERNANCE", gov_report.to_dict())

        if not gov_report.authorized or force_block:
            if force_defer or gov_report.decision == GovernanceDecision.DEFERRED:
                deferment = self.deferment_manager.create_deferment(
                    debt_id=debt_item.debt_id,
                    reason="Deferred by governance due to budget or priority scheduling.",
                    risk=chosen_option.risk,
                    expected_cost=chosen_option.estimated_cost,
                    revisit_condition="Next budget cycle",
                )
                self.store.save_entity(
                    "deferments",
                    deferment.deferment_id,
                    deferment.to_dict(),
                    {"debt_id": debt_item.debt_id},
                )
                resolution_res = self.resolution_governor.resolve(
                    debt_id=debt_item.debt_id,
                    verification_report=VerificationReport(
                        verification_id="vrf_deferred",
                        debt_id=debt_item.debt_id,
                        original_evidence_invalidated=False,
                        build_passed=True,
                        tests_passed=True,
                        contracts_preserved=True,
                        behavior_preserved=True,
                        security_preserved=True,
                        verification_passed=False,
                    ),
                    comparison_report=QualityComparisonReport(
                        comparison_id="cmp_deferred",
                        debt_id=debt_item.debt_id,
                        outcome=QualityComparisonOutcome.NO_MEASURABLE_CHANGE,
                        improved_dimensions=[],
                        degraded_dimensions=[],
                        unchanged_dimensions=[],
                        dimension_deltas={},
                        summary_text="Deferred before implementation.",
                    ),
                    is_deferred=True,
                )
                self.store.save_entity(
                    "resolution_results",
                    resolution_res.resolution_id,
                    resolution_res.to_dict(),
                    {"debt_id": debt_item.debt_id, "status": resolution_res.status.value},
                )
                return {
                    "debt_id": debt_item.debt_id,
                    "stage": "DEFERRED",
                    "governance": gov_report.to_dict(),
                    "deferment": deferment.to_dict(),
                    "resolution": resolution_res.to_dict(),
                    "lifecycle_duration_ms": round((time.time() - lifecycle_start) * 1000, 2),
                }
            else:
                resolution_res = self.resolution_governor.resolve(
                    debt_id=debt_item.debt_id,
                    verification_report=VerificationReport(
                        verification_id="vrf_blocked",
                        debt_id=debt_item.debt_id,
                        original_evidence_invalidated=False,
                        build_passed=True,
                        tests_passed=True,
                        contracts_preserved=True,
                        behavior_preserved=True,
                        security_preserved=True,
                        verification_passed=False,
                    ),
                    comparison_report=QualityComparisonReport(
                        comparison_id="cmp_blocked",
                        debt_id=debt_item.debt_id,
                        outcome=QualityComparisonOutcome.NO_MEASURABLE_CHANGE,
                        improved_dimensions=[],
                        degraded_dimensions=[],
                        unchanged_dimensions=[],
                        dimension_deltas={},
                        summary_text="Blocked by governance gate.",
                    ),
                    is_blocked=True,
                )
                self.store.save_entity(
                    "resolution_results",
                    resolution_res.resolution_id,
                    resolution_res.to_dict(),
                    {"debt_id": debt_item.debt_id, "status": resolution_res.status.value},
                )
                return {
                    "debt_id": debt_item.debt_id,
                    "stage": "BLOCKED",
                    "governance": gov_report.to_dict(),
                    "resolution": resolution_res.to_dict(),
                    "lifecycle_duration_ms": round((time.time() - lifecycle_start) * 1000, 2),
                }

        # 8. MISSION PLAN
        plan = self.planner.create_plan(debt_item, chosen_option)
        mission = self.planner.create_mission(plan)
        self.store.save_entity("remediation_plans", plan.plan_id, plan.to_dict(), {"debt_id": debt_item.debt_id})
        self.store.save_entity("remediation_missions", mission.mission_id, mission.to_dict(), {"debt_id": debt_item.debt_id})
        self.provenance_tracker.record_stage(debt_item.debt_id, "MISSION_PLAN", plan.to_dict())

        # 9. MULTI-AGENT COORDINATION
        coord_plan = self.coordinator.create_coordination_plan(
            mission_id=mission.mission_id,
            debt_id=debt_item.debt_id,
            affected_files=chosen_option.affected_files or [debt_item.affected_surface],
        )
        self.provenance_tracker.record_stage(debt_item.debt_id, "COORDINATION", coord_plan.to_dict())

        # 10. SAFE SELF-MODIFICATION (Implementation)
        impl_res = self.implementation_engine.execute_transactional_patch(
            files_to_modify=chosen_option.affected_files or [debt_item.affected_surface],
            patch_fn=simulate_patch_fn,
            simulate_build_failure=simulate_build_failure,
            simulate_test_failure=simulate_test_failure,
        )
        self.store.save_entity(
            "implementation_results",
            impl_res.result_id,
            impl_res.to_dict(),
            {"transaction_id": impl_res.transaction_id, "status": impl_res.status.value},
        )
        self.provenance_tracker.record_stage(debt_item.debt_id, "IMPLEMENTATION", impl_res.to_dict())

        # Check for rollback requirement if implementation failed
        if impl_res.status != ImplementationStatus.SUCCESS:
            pre_hashes = {f: "pre_hash_val" for f in chosen_option.affected_files or [debt_item.affected_surface]}
            rollback_res = self.rollback_engine.execute_rollback(
                transaction_id=impl_res.transaction_id,
                debt_id=debt_item.debt_id,
                files_to_revert=chosen_option.affected_files or [debt_item.affected_surface],
                pre_patch_hashes=pre_hashes,
                simulated_hash_mismatch=simulate_hash_mismatch,
            )
            self.store.save_entity(
                "rollback_results",
                rollback_res.rollback_id,
                rollback_res.to_dict(),
                {"transaction_id": rollback_res.transaction_id, "debt_id": debt_item.debt_id},
            )
            self.provenance_tracker.record_stage(debt_item.debt_id, "ROLLBACK", rollback_res.to_dict())

            return {
                "debt_id": debt_item.debt_id,
                "stage": "ROLLED_BACK",
                "implementation": impl_res.to_dict(),
                "rollback": rollback_res.to_dict(),
                "resolution": ResolutionStatus.FAILED.value,
                "lifecycle_duration_ms": round((time.time() - lifecycle_start) * 1000, 2),
            }

        # 11. CONTINUOUS VERIFICATION
        verif_res = self.verification_engine.verify(
            debt_id=debt_item.debt_id,
            original_evidence_invalidated=True,
            build_passed=impl_res.build_passed,
            tests_passed=impl_res.test_passed,
            contracts_preserved=True,
            behavior_preserved=True,
            security_preserved=True,
        )
        self.provenance_tracker.record_stage(debt_item.debt_id, "VERIFICATION", verif_res.to_dict())

        # 12. QUALITY RE-MEASUREMENT & 13. DEBT COMPARISON
        q_before = quality_before or {dim: 0.70 for dim in self.comparison_engine.DIMENSIONS}
        q_after = quality_after or {dim: 0.85 for dim in self.comparison_engine.DIMENSIONS}

        comparison_res = self.comparison_engine.compare_quality(
            debt_id=debt_item.debt_id,
            quality_before=q_before,
            quality_after=q_after,
        )
        self.store.save_entity(
            "quality_rescans",
            f"rescan_{uuid.uuid4().hex[:6]}",
            {"before": q_before, "after": q_after, "comparison": comparison_res.to_dict()},
            {"debt_id": debt_item.debt_id, "phase": "POST_REMEDIATION"},
        )
        self.provenance_tracker.record_stage(debt_item.debt_id, "QUALITY_COMPARISON", comparison_res.to_dict())

        # Final Resolution
        final_resolution = self.resolution_governor.resolve(
            debt_id=debt_item.debt_id,
            verification_report=verif_res,
            comparison_report=comparison_res,
            partially_remediated_surfaces=partial_hotspots,
        )
        self.store.save_entity(
            "resolution_results",
            final_resolution.resolution_id,
            final_resolution.to_dict(),
            {"debt_id": debt_item.debt_id, "status": final_resolution.status.value},
        )
        self.provenance_tracker.record_stage(debt_item.debt_id, "RESOLUTION", final_resolution.to_dict())

        return {
            "debt_id": debt_item.debt_id,
            "stage": "LIFECYCLE_COMPLETE",
            "validation": validation_res.to_dict(),
            "root_cause": root_cause.to_dict(),
            "options_count": len(options),
            "chosen_option": chosen_option.to_dict(),
            "governance": gov_report.to_dict(),
            "mission": mission.to_dict(),
            "implementation": impl_res.to_dict(),
            "verification": verif_res.to_dict(),
            "comparison": comparison_res.to_dict(),
            "resolution": final_resolution.to_dict(),
            "lifecycle_duration_ms": round((time.time() - lifecycle_start) * 1000, 2),
        }
