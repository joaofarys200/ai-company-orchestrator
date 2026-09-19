"""
Release Readiness Bridge Module
Phase 70 — Autonomous Release Readiness & Production Governance

Unified service facade coordinating candidate lifecycles, baseline capture,
multi-domain evaluation, release plan execution, and persistence.
"""

from __future__ import annotations
import json
from typing import Dict, Any, Optional
from .models import ReleaseCandidateState, CanaryPolicyType
from .readiness import ReleaseCandidateLifecycleManager
from .baseline import ReleaseBaselineCapture
from .quality import QualityReadinessEvaluator
from .debt import TechnicalDebtGate
from .architecture import ArchitectureReadinessEvaluator
from .contracts import ContractReadinessEvaluator
from .behavior import BehaviorReadinessEvaluator
from .security import SecurityReadinessEvaluator
from .performance import PerformanceReadinessEvaluator
from .health import RuntimeHealthAnalyzer
from .observability import ObservabilityReadiness
from .dependencies import DependencyReadiness
from .configuration import ConfigurationReadinessEvaluator
from .rollback import RollbackReadinessEvaluator
from .release_plan import ReleasePlanBuilder
from .canary import CanaryEvaluator
from .verification import ReleaseVerificationRunner
from .governance import ReleaseGateGovernance
from .persistence import ReleaseReadinessStore
from .cache import ReleaseReadinessCache


class ReleaseReadinessBridge:
    """Facade for release governance operations."""

    def __init__(self, db_path: str = ":memory:"):
        self.store = ReleaseReadinessStore(db_path)
        self.cache = ReleaseReadinessCache()

    def create_candidate(
        self,
        mission_id: str,
        commit_sha: str,
        workspace_snapshot: str,
        artifact_hashes: Optional[Dict[str, str]] = None,
        version: str = "1.0.0",
        environment: str = "production",
        release_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates and persists a ReleaseCandidate."""
        candidate = ReleaseCandidateLifecycleManager.create_candidate(
            mission_id=mission_id,
            commit_sha=commit_sha,
            workspace_snapshot=workspace_snapshot,
            artifact_hashes=artifact_hashes,
            version=version,
            environment=environment,
            release_id=release_id
        )
        self.store.save_candidate(candidate)
        return candidate.to_dict()

    def capture_baseline(
        self,
        baseline_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Captures and seals a 13-dimensional release baseline."""
        data = baseline_data or {}
        baseline = ReleaseBaselineCapture.capture(
            architecture_hash=data.get("architecture_hash", "arch_hash_0000"),
            contract_hash=data.get("contract_hash", "contract_hash_0000"),
            behavior_hash=data.get("behavior_hash", "behavior_hash_0000"),
            quality_snapshot=data.get("quality_snapshot"),
            technical_debt_snapshot=data.get("technical_debt_snapshot"),
            test_results=data.get("test_results"),
            security_state=data.get("security_state"),
            performance_baseline=data.get("performance_baseline"),
            runtime_baseline=data.get("runtime_baseline"),
            configuration_baseline=data.get("configuration_baseline"),
            dependency_baseline=data.get("dependency_baseline"),
            observability_baseline=data.get("observability_baseline"),
            rollback_baseline=data.get("rollback_baseline")
        )
        self.store.save_baseline(baseline)
        return baseline.to_dict()

    def evaluate_readiness(
        self,
        release_id: str,
        evaluation_inputs: Optional[Dict[str, Any]] = None,
        deployment_available: bool = False
    ) -> Dict[str, Any]:
        """Runs the complete multi-domain evaluation sequence for a candidate."""
        inputs = evaluation_inputs or {}

        # 1. Evaluate Quality
        qual_res = QualityReadinessEvaluator.evaluate(
            quality_snapshot=inputs.get("quality_snapshot", {}),
            quality_deltas=inputs.get("quality_deltas", {}),
            unresolved_unknown_count=inputs.get("unresolved_unknown_count", 0)
        )

        # 2. Evaluate Technical Debt
        debt_res = TechnicalDebtGate.evaluate(
            technical_debt_snapshot=inputs.get("technical_debt_snapshot", {})
        )

        # 3. Evaluate Architecture
        arch_res = ArchitectureReadinessEvaluator.evaluate(
            architecture_snapshot=inputs.get("architecture_snapshot", {})
        )

        # 4. Evaluate Contracts
        contract_res = ContractReadinessEvaluator.evaluate(
            contract_snapshot=inputs.get("contract_snapshot", {})
        )

        # 5. Evaluate Behavior
        behavior_res = BehaviorReadinessEvaluator.evaluate(
            behavior_snapshot=inputs.get("behavior_snapshot", {})
        )

        # 6. Evaluate Security
        sec_res = SecurityReadinessEvaluator.evaluate(
            security_snapshot=inputs.get("security_snapshot", {})
        )

        # 7. Evaluate Performance
        perf_res = PerformanceReadinessEvaluator.evaluate(
            baseline_metrics=inputs.get("performance_baseline", {}),
            current_metrics=inputs.get("performance_current", {})
        )

        # 8. Evaluate Runtime Health
        rt_res = RuntimeHealthAnalyzer.analyze(
            runtime_evidence=inputs.get("runtime_evidence", {})
        )

        # 9. Evaluate Observability
        obs_res = ObservabilityReadiness.evaluate(
            observability_data=inputs.get("observability_data", {})
        )

        # 10. Evaluate Dependencies
        dep_res = DependencyReadiness.evaluate(
            dependency_data=inputs.get("dependency_data", {})
        )

        # 11. Evaluate Configuration
        cfg_res = ConfigurationReadinessEvaluator.evaluate(
            configuration_data=inputs.get("configuration_data", {})
        )

        # 12. Evaluate Rollback Readiness
        rb_res = RollbackReadinessEvaluator.evaluate(
            rollback_data=inputs.get("rollback_data", {}),
            rollback_mandatory=inputs.get("rollback_mandatory", True)
        )

        # Synthesize Release Gate Decision
        decision = ReleaseGateGovernance.evaluate_candidate(
            candidate_id=release_id,
            security_summary=sec_res,
            quality_summary=qual_res,
            debt_summary=debt_res,
            architecture_summary=arch_res,
            contract_summary=contract_res,
            behavior_summary=behavior_res,
            performance_summary=perf_res,
            runtime_summary=rt_res,
            observability_summary=obs_res,
            dependency_summary=dep_res,
            configuration_summary=cfg_res,
            rollback_summary=rb_res,
            deployment_available=deployment_available
        )

        self.store.save_decision(decision)
        if decision.human_review_ticket:
            self.store.save_ticket(decision.human_review_ticket)

        return decision.to_dict()

    def build_and_step_plan(
        self,
        candidate_id: str,
        deployment_available: bool = False
    ) -> Dict[str, Any]:
        """Builds and steps through the release plan DAG."""
        plan = ReleasePlanBuilder.build_plan(
            candidate_id=candidate_id,
            deployment_available=deployment_available
        )
        exec_res = ReleasePlanBuilder.execute_plan_stage(plan)
        self.store.save_plan(plan)
        return exec_res

    def resolve_ticket(
        self,
        decision_id: str,
        approved: bool,
        notes: str = "",
        timed_out: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Resolves an open human review ticket for a decision."""
        raw_decision = self.store.get_decision(decision_id)
        if not raw_decision:
            return None

        # Reconstruct decision
        # We can update decision record directly
        if raw_decision.get("human_review_ticket"):
            ticket = raw_decision["human_review_ticket"]
            if timed_out:
                ticket["status"] = "TIMED_OUT"
                ticket["decision_notes"] = f"Timed out. Automatic BLOCKED. {notes}".strip()
                raw_decision["state"] = "BLOCKED"
                raw_decision["allowed_to_release"] = False
            elif approved:
                ticket["status"] = "APPROVED"
                ticket["decision_notes"] = notes or "Approved"
                raw_decision["state"] = "RELEASE_READY_WITH_RISK"
                raw_decision["allowed_to_release"] = True
            else:
                ticket["status"] = "REJECTED"
                ticket["decision_notes"] = notes or "Rejected"
                raw_decision["state"] = "BLOCKED"
                raw_decision["allowed_to_release"] = False

            # Update store
            with self.store._lock:
                cur = self.store._conn.cursor()
                cur.execute("""
                    UPDATE release_gate_decisions
                    SET state = ?, allowed_to_release = ?, payload_json = ?
                    WHERE decision_id = ?
                """, (
                    raw_decision["state"],
                    1 if raw_decision["allowed_to_release"] else 0,
                    json.dumps(raw_decision),
                    decision_id
                ))
                self.store._conn.commit()

        return raw_decision
