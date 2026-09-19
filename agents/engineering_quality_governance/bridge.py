"""
JARVIS OS — Phase 68: Engineering Quality Governance Bridge
Central orchestration bridge unifying:
- Baseline capture (QUALITY_BASELINE)
- Post-mission capture (QUALITY_AFTER)
- Multi-dimensional evaluation across all 9 dimensions
- Technical debt detection & prioritization
- Quality gates & budget enforcement
- Quality regression detection
- Historical trend analysis & hotspot identification
- Cross-phase integrations:
  * F63: External patterns yield QUALITY_HINT, never QUALITY_EVIDENCE.
  * F64: Architecture alternatives evaluate quality_impact across dimensions.
  * F65: Self-modification quality diff (critical degradation -> COMMIT_BLOCKED).
  * F66: Multi-agent quality telemetry (per agent, intent, mission, workspace, merge).
  * F67: Mission lifecycle integration (COMPLETED_WITH_QUALITY_DEBT).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .architecture_quality import ArchitectureQualityEvaluator
from .baseline import QualityBaselineManager
from .behavior_quality import BehaviorQualityEvaluator
from .cache import QualityEvaluationCache
from .code_quality import CodeQualityEvaluator
from .comparison import QualityRegressionDetector
from .contract_quality import ContractQualityEvaluator
from .debt_detection import TechnicalDebtDetector
from .debt_prioritization import DebtPrioritizer
from .maintainability import MaintainabilityQualityEvaluator
from .models import (
    AgentQualityRecord,
    DebtCategory,
    DebtSeverity,
    DebtStatus,
    DimensionChange,
    DimensionEvaluation,
    MissionQualityRecord,
    PriorityVector,
    QualityDelta,
    QualityDimension,
    QualityGateDecision,
    QualityGateStatus,
    QualityHotspotItem,
    QualitySnapshot,
    QualityTrendDirection,
    TechnicalDebtItem,
)
from .performance_quality import PerformanceQualityEvaluator
from .persistence import QualityPersistenceStore
from .policy import POLICIES, QualityPolicy, get_policy
from .provenance import QualityProvenanceRegistry
from .quality_budget import QualityBudgetGovernor
from .quality_dimensions import QualityDimensionsOrchestrator
from .quality_gates import QualityGateEngine
from .reliability_quality import ReliabilityQualityEvaluator
from .security import QualitySecuritySentinel
from .security_quality import SecurityQualityEvaluator
from .test_quality import TestQualityEvaluator
from .trend import QualityTrendEngine


class EngineeringQualityGovernanceBridge:
    """
    Singleton bridge exposing the complete Engineering Quality Governance API.
    """

    _instance: Optional[EngineeringQualityGovernanceBridge] = None

    def __init__(self, db_path: str = ":memory:") -> None:
        self.persistence = QualityPersistenceStore(db_path=db_path)
        self.baseline_manager = QualityBaselineManager()
        self.orchestrator = QualityDimensionsOrchestrator()
        self.debt_manager = TechnicalDebtDetector().debt_manager
        self.debt_detector = TechnicalDebtDetector(debt_manager=self.debt_manager)
        self.debt_prioritizer = DebtPrioritizer()
        self.trend_engine = QualityTrendEngine()
        self.regression_detector = QualityRegressionDetector()
        self.provenance = QualityProvenanceRegistry()
        self.security_sentinel = QualitySecuritySentinel()
        self.cache = QualityEvaluationCache()

        # Specialized evaluators
        self.arch_eval = ArchitectureQualityEvaluator()
        self.code_eval = CodeQualityEvaluator()
        self.test_eval = TestQualityEvaluator()
        self.contract_eval = ContractQualityEvaluator()
        self.behavior_eval = BehaviorQualityEvaluator()
        self.sec_eval = SecurityQualityEvaluator()
        self.perf_eval = PerformanceQualityEvaluator()
        self.rel_eval = ReliabilityQualityEvaluator()
        self.maint_eval = MaintainabilityQualityEvaluator()

        # Register specialized evaluators with orchestrator
        self.orchestrator.register_evaluator(QualityDimension.ARCHITECTURE, self.arch_eval)
        self.orchestrator.register_evaluator(QualityDimension.CODE, self.code_eval)
        self.orchestrator.register_evaluator(QualityDimension.TEST, self.test_eval)
        self.orchestrator.register_evaluator(QualityDimension.CONTRACT, self.contract_eval)
        self.orchestrator.register_evaluator(QualityDimension.BEHAVIOR, self.behavior_eval)
        self.orchestrator.register_evaluator(QualityDimension.SECURITY, self.sec_eval)
        self.orchestrator.register_evaluator(QualityDimension.PERFORMANCE, self.perf_eval)
        self.orchestrator.register_evaluator(QualityDimension.RELIABILITY, self.rel_eval)
        self.orchestrator.register_evaluator(QualityDimension.MAINTAINABILITY, self.maint_eval)

        self._hotspots: Dict[str, QualityHotspotItem] = {}
        self._agent_records: List[AgentQualityRecord] = []
        self._mission_history: Dict[str, MissionQualityRecord] = {}

    @classmethod
    def get_instance(cls, db_path: str = ":memory:") -> EngineeringQualityGovernanceBridge:
        if cls._instance is None:
            cls._instance = cls(db_path=db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    # --------------------------------------------------------------------------
    # 1. Baseline & Snapshot Operations
    # --------------------------------------------------------------------------

    def capture_baseline(
        self,
        mission_id: str,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> QualitySnapshot:
        """Captures QUALITY_BASELINE before mission execution."""
        dimensions = self.orchestrator.evaluate_all_dimensions(context=context, scope=scope)
        hashes = {
            "architecture": context.get("architecture_hash", "arch_init") if context else "arch_init",
            "contract": context.get("contract_hash", "contract_init") if context else "contract_init",
            "behavior": context.get("behavior_hash", "behavior_init") if context else "behavior_init",
            "test": context.get("test_hash", "test_init") if context else "test_init",
            "security": context.get("security_hash", "sec_init") if context else "sec_init",
        }
        prov = self.provenance.record_provenance(
            entity_type="QualitySnapshot",
            entity_id=f"baseline_{mission_id}",
            actor="GovernanceEngine",
            action="CAPTURE_BASELINE",
            details={"mission_id": mission_id, "scope": scope},
        )
        snap = self.baseline_manager.capture_baseline(
            mission_id=mission_id,
            dimensions=dimensions,
            hashes=hashes,
            provenance=prov,
        )
        self.persistence.save_snapshot(snap.to_dict())
        return snap

    def capture_after(
        self,
        mission_id: str,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> QualitySnapshot:
        """Captures QUALITY_AFTER after mission execution."""
        dimensions = self.orchestrator.evaluate_all_dimensions(context=context, scope=scope)
        hashes = {
            "architecture": context.get("architecture_hash", "arch_post") if context else "arch_post",
            "contract": context.get("contract_hash", "contract_post") if context else "contract_post",
            "behavior": context.get("behavior_hash", "behavior_post") if context else "behavior_post",
            "test": context.get("test_hash", "test_post") if context else "test_post",
            "security": context.get("security_hash", "sec_post") if context else "sec_post",
        }
        prov = self.provenance.record_provenance(
            entity_type="QualitySnapshot",
            entity_id=f"after_{mission_id}",
            actor="GovernanceEngine",
            action="CAPTURE_AFTER",
            details={"mission_id": mission_id, "scope": scope},
        )
        snap = self.baseline_manager.capture_after(
            mission_id=mission_id,
            dimensions=dimensions,
            hashes=hashes,
            provenance=prov,
        )
        self.persistence.save_snapshot(snap.to_dict())
        return snap

    def compare_mission_quality(self, mission_id: str) -> QualityDelta:
        """Compares QUALITY_BASELINE vs QUALITY_AFTER for a mission."""
        baseline = self.baseline_manager.get_baseline(mission_id)
        after = self.baseline_manager.get_after(mission_id)
        if not baseline or not after:
            raise ValueError(f"Both baseline and after snapshots must exist for mission '{mission_id}'.")

        delta = self.regression_detector.compare_snapshots(baseline, after)
        self.persistence.save_delta(delta.to_dict())
        return delta

    # --------------------------------------------------------------------------
    # 2. Quality Gate Evaluation
    # --------------------------------------------------------------------------

    def evaluate_quality_gate(
        self,
        mission_id: str,
        policy_name: str = "GOVERNED",
        scope: str = "global",
    ) -> QualityGateDecision:
        """
        Evaluates post-mission snapshot and delta against quality policy and budget.
        """
        policy = get_policy(policy_name)
        after = self.baseline_manager.get_after(mission_id)
        baseline = self.baseline_manager.get_baseline(mission_id)

        if not after:
            # Fallback if evaluated on baseline
            after = baseline

        if not after:
            return QualityGateDecision(
                decision=QualityGateStatus.QUALITY_INCONCLUSIVE,
                scope=scope,
                evidence=[{"error": f"No quality snapshot found for mission {mission_id}"}],
                degradations=[],
                improvements=[],
                debt=[],
                uncertainty=1.0,
                policy=policy.to_dict(),
            )

        delta = None
        if baseline and after and baseline.snapshot_id != after.snapshot_id:
            delta = self.regression_detector.compare_snapshots(baseline, after)

        debts = self.debt_manager.list_unresolved()
        budget_gov = QualityBudgetGovernor(budget=policy.budget)
        gate_engine = QualityGateEngine(budget_governor=budget_gov)

        decision = gate_engine.evaluate_gate(
            snapshot=after,
            delta=delta,
            debt_items=debts,
            policy=policy.to_dict(),
            scope=scope,
        )

        gate_id = f"gate_{mission_id}_{int(time.time()*1000)}"
        self.persistence.save_gate_decision(gate_id, mission_id, decision.to_dict())
        return decision

    # --------------------------------------------------------------------------
    # 3. Technical Debt Management & Prioritization
    # --------------------------------------------------------------------------

    def detect_debt_from_history(
        self,
        mission_id: str,
        history: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TechnicalDebtItem]:
        items = self.debt_detector.analyze_signals(mission_id=mission_id, history=history, context=context)
        for item in items:
            self.persistence.save_debt_item(item.to_dict())
        return items

    def prioritize_debt(self) -> List[PriorityVector]:
        items = self.debt_manager.list_unresolved()
        vectors = self.debt_prioritizer.prioritize_all(items)
        return vectors

    # --------------------------------------------------------------------------
    # 4. Quality Hotspots
    # --------------------------------------------------------------------------

    def record_hotspot_event(
        self,
        entity_type: str,
        entity_name: str,
        event_type: str,
        evidence: Dict[str, Any],
    ) -> QualityHotspotItem:
        key = f"{entity_type}:{entity_name}"
        item = self._hotspots.get(key)
        if not item:
            item = QualityHotspotItem(
                entity_type=entity_type,
                entity_name=entity_name,
            )
            self._hotspots[key] = item

        if event_type == "failure":
            item.failure_count += 1
        elif event_type == "regression":
            item.regression_count += 1
        elif event_type == "debt":
            item.debt_count += 1
        elif event_type == "review":
            item.review_count += 1
        elif event_type == "rollback":
            item.rollback_count += 1
        elif event_type == "flaky":
            item.flakiness_score = min(1.0, item.flakiness_score + 0.2)

        item.evidence.append(evidence)
        from .metrics import QualityMetricsEngine
        item.risk_weight = QualityMetricsEngine.compute_hotspot_risk_weight(
            failure_count=item.failure_count,
            regression_count=item.regression_count,
            debt_count=item.debt_count,
            review_count=item.review_count,
            rollback_count=item.rollback_count,
            flakiness_score=item.flakiness_score,
        )

        self.persistence.save_hotspot(item.to_dict())
        return item

    def get_hotspots(self) -> List[QualityHotspotItem]:
        items = list(self._hotspots.values())
        items.sort(key=lambda h: h.risk_weight, reverse=True)
        return items

    # --------------------------------------------------------------------------
    # 5. Cross-Phase Integrations
    # --------------------------------------------------------------------------

    def integrate_f63_hint(self, external_pattern: Dict[str, Any]) -> Dict[str, Any]:
        """
        F63 Integration:
        External quality patterns produce QUALITY_HINT, NEVER QUALITY_EVIDENCE.
        Local validation is required before acceptance.
        """
        hint_id = f"hint_{uuid.uuid4().hex[:8]}"
        return {
            "type": "QUALITY_HINT",
            "hint_id": hint_id,
            "source_pattern": external_pattern.get("pattern_name", "generic_pattern"),
            "suggestion": external_pattern.get("suggestion", "Consider restructuring dependencies"),
            "confidence": min(0.60, float(external_pattern.get("confidence", 0.5))),
            "is_evidence": False,
            "requires_local_validation": True,
            "validation_status": "PENDING_LOCAL_BENCHMARK",
        }

    def evaluate_architecture_alternative_quality(
        self,
        alternative: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        F64 Integration:
        Architecture alternatives receive quality_impact across dimensions.
        Does NOT automatically pick alternative with lowest estimated debt.
        """
        alt_id = alternative.get("alternative_id", "alt_01")
        impacts = {
            "architecture": alternative.get("arch_impact", 0.1),
            "test": alternative.get("test_impact", 0.0),
            "contract": alternative.get("contract_impact", 0.0),
            "behavior": alternative.get("behavior_impact", 0.0),
            "security": alternative.get("security_impact", 0.0),
            "reliability": alternative.get("reliability_impact", 0.05),
            "maintainability": alternative.get("maint_impact", 0.15),
        }
        # Multi-dimensional risk score
        return {
            "alternative_id": alt_id,
            "quality_impact": impacts,
            "estimated_debt": alternative.get("estimated_debt", 1.0),
            "risk_profile": "BALANCED_MODULARITY",
            "auto_selected": False,
            "rationale": "Evaluated across 7 dimensions; not auto-selected solely on lowest debt.",
        }

    def evaluate_self_modification_quality_diff(
        self,
        patch: Dict[str, Any],
        policy_name: str = "GOVERNED",
    ) -> Dict[str, Any]:
        """
        F65 Integration:
        Produces QUALITY_DIFF before commit.
        If critical_quality_degradation -> COMMIT_BLOCKED.
        If quality_uncertainty > policy limit -> HUMAN_REVIEW.
        """
        pol = get_policy(policy_name)
        critical_deg = patch.get("critical_degradation", False)
        uncertainty = float(patch.get("quality_uncertainty", 0.10))

        if critical_deg:
            return {
                "decision": "COMMIT_BLOCKED",
                "reason": "Critical quality degradation detected in proposed patch.",
                "quality_diff": patch.get("diff_summary", {}),
                "uncertainty": uncertainty,
            }
        if uncertainty > pol.uncertainty_threshold:
            return {
                "decision": "HUMAN_REVIEW",
                "reason": f"Quality uncertainty ({uncertainty:.2f}) exceeds policy threshold ({pol.uncertainty_threshold:.2f}).",
                "quality_diff": patch.get("diff_summary", {}),
                "uncertainty": uncertainty,
            }

        return {
            "decision": "COMMIT_ALLOWED",
            "quality_diff": patch.get("diff_summary", {}),
            "uncertainty": uncertainty,
        }

    def record_multi_agent_quality(
        self,
        agent_id: str,
        intent_id: str,
        mission_id: str,
        workspace: str,
        changes: Dict[str, Any],
    ) -> AgentQualityRecord:
        """
        F66 Integration:
        Evaluates quality metrics per agent, intent, mission, workspace, and merge.
        Does NOT infer 'weak agent' from a single isolated failure.
        """
        record = AgentQualityRecord(
            agent_id=agent_id,
            intent_id=intent_id,
            mission_id=mission_id,
            workspace=workspace,
            regressions_count=int(changes.get("regressions_count", 0)),
            rollbacks_count=int(changes.get("rollbacks_count", 0)),
            debt_items_count=int(changes.get("debt_items_count", 0)),
            conflicts_count=int(changes.get("conflicts_count", 0)),
            merges_successful=int(changes.get("merges_successful", 1)),
            evidence=[{"context": "multi_agent_execution", "changes": changes}],
        )
        self._agent_records.append(record)
        return record

    def conclude_mission_with_quality(
        self,
        mission_id: str,
        objective_satisfied: bool,
        policy_name: str = "GOVERNED",
    ) -> Dict[str, Any]:
        """
        F67 Integration:
        Enforces MISSION_COMPLETED != QUALITY_IMPROVED.
        Mission can conclude as:
        - COMPLETED_WITH_QUALITY_DEBT (if objective is met but debt remains)
        - COMPLETED_WITH_QUALITY_IMPROVEMENT (if objective is met and quality improved)
        - BLOCKED_BY_QUALITY_GATE (if objective is met but critical degradation breaches gate)
        """
        gate = self.evaluate_quality_gate(mission_id, policy_name=policy_name)
        unresolved_debts = self.debt_manager.list_unresolved()

        delta = None
        quality_improved = False
        try:
            delta = self.compare_mission_quality(mission_id)
            quality_improved = (len(delta.improvements) > len(delta.degradations)) and not delta.degradations
        except Exception:
            pass

        if gate.decision == QualityGateStatus.QUALITY_BLOCKED:
            final_status = "BLOCKED_BY_QUALITY_GATE"
        elif not objective_satisfied:
            final_status = "FAILED_OBJECTIVE"
        elif unresolved_debts:
            final_status = "COMPLETED_WITH_QUALITY_DEBT"
        elif quality_improved:
            final_status = "COMPLETED_WITH_QUALITY_IMPROVEMENT"
        else:
            final_status = "COMPLETED_WITH_NEUTRAL_QUALITY"

        record = MissionQualityRecord(
            mission_id=mission_id,
            baseline_id=f"baseline_{mission_id}",
            after_id=f"after_{mission_id}",
            gate_decision=gate.decision,
            completion_status=final_status,
            unresolved_debt_count=len(unresolved_debts),
            quality_improved=quality_improved,
            evidence_efficiency=delta.evidence_efficiency if delta else 1.0,
        )
        self._mission_history[mission_id] = record
        self.persistence.save_mission_quality(record.to_dict())

        return {
            "mission_id": mission_id,
            "final_status": final_status,
            "objective_satisfied": objective_satisfied,
            "quality_improved": quality_improved,
            "unresolved_debt_count": len(unresolved_debts),
            "gate_decision": gate.to_dict(),
            "delta": delta.to_dict() if delta else None,
        }
