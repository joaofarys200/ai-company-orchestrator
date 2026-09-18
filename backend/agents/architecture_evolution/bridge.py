"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: bridge.py
Unified singleton facade orchestrating architectural observation, problem detection,
constraint extraction, alternative generation, multidimensional impact/contract/behavior/risk/cost
analyses, migration DAG planning, simulation, verification, and governance gating.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from .alternatives import ArchitectureAlternativeGenerator
from .behavior import ArchitectureBehaviorAnalyzer
from .cache import ArchitectureCache
from .comparison import ArchitectureComparator
from .constraints import ArchitectureConstraintExtractor
from .contracts import ArchitectureContractAnalyzer
from .cost import ArchitectureCostModel
from .governance import ArchitectureGovernanceEngine
from .impact import ArchitectureImpactAnalyzer
from .index import ArchitectureIndex
from .metrics import ArchitectureMetricsCollector
from .migration import ArchitectureMigrationPlanner
from .models import (
    ArchitectureAlternative,
    ArchitectureComparisonResult,
    ArchitectureConstraint,
    ArchitectureGovernanceDecision,
    ArchitectureMigrationPlan,
    ArchitectureProblem,
    ArchitectureSnapshot,
    BehaviorAnalysisResult,
    ContractAnalysisResult,
    CostEstimationResult,
    GovernanceDecisionState,
    ImpactAnalysisResult,
    RiskAnalysisResult,
    SimulationResult,
    VerificationPlan,
)
from .observation import ArchitectureObserver
from .patterns import convert_f63_to_architecture_hypothesis
from .persistence import ArchitecturePersistenceStore
from .policy import ArchitecturePolicyManager
from .problem_detection import ArchitectureProblemDetector
from .provenance import ArchitectureProvenanceManager
from .risk import ArchitectureRiskAnalyzer
from .security import ArchitectureSecurityFilter
from .simulation import ArchitectureSimulator
from .validator import ArchitectureValidator
from .verification import ArchitectureVerificationPlanner


class ArchitectureEvolutionBridge:
    """Singleton facade for autonomous architecture evolution."""

    _instance: Optional[ArchitectureEvolutionBridge] = None

    def __init__(self, db_path: str = ":memory:"):
        self.observer = ArchitectureObserver()
        self.detector = ArchitectureProblemDetector(self.observer)
        self.constraint_extractor = ArchitectureConstraintExtractor()
        self.alternative_generator = ArchitectureAlternativeGenerator()
        self.impact_analyzer = ArchitectureImpactAnalyzer()
        self.contract_analyzer = ArchitectureContractAnalyzer()
        self.behavior_analyzer = ArchitectureBehaviorAnalyzer()
        self.risk_analyzer = ArchitectureRiskAnalyzer()
        self.cost_model = ArchitectureCostModel()
        self.migration_planner = ArchitectureMigrationPlanner()
        self.simulator = ArchitectureSimulator()
        self.verification_planner = ArchitectureVerificationPlanner()
        self.comparator = ArchitectureComparator()
        self.governance_engine = ArchitectureGovernanceEngine()
        self.provenance = ArchitectureProvenanceManager()
        self.security_filter = ArchitectureSecurityFilter()
        self.policy_manager = ArchitecturePolicyManager()
        self.cache = ArchitectureCache()
        self.persistence = ArchitecturePersistenceStore(db_path)
        self.validator = ArchitectureValidator()
        self.index = ArchitectureIndex()
        self.metrics = ArchitectureMetricsCollector()

        self.snapshots: Dict[str, ArchitectureSnapshot] = {}
        self.problems: Dict[str, ArchitectureProblem] = {}
        self.alternatives: Dict[str, List[ArchitectureAlternative]] = {}
        self.decisions: Dict[str, ArchitectureGovernanceDecision] = {}

    @classmethod
    def get_instance(cls, db_path: str = ":memory:") -> ArchitectureEvolutionBridge:
        if cls._instance is None:
            cls._instance = ArchitectureEvolutionBridge(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def register_snapshot(self, snapshot: ArchitectureSnapshot) -> None:
        t0 = time.time()
        if not snapshot.snapshot_hash:
            snapshot.snapshot_hash = snapshot.compute_hash()
        self.validator.validate_snapshot(snapshot)
        self.snapshots[snapshot.snapshot_id] = snapshot
        self.persistence.save_snapshot(snapshot)
        self.provenance.record_event(
            target_id=snapshot.snapshot_id,
            source_type="ArchitectureSnapshot",
            action="SNAPSHOT_REGISTERED",
        )
        self.metrics.record_stage("snapshot_ms", (time.time() - t0) * 1000.0)

    def observe_and_detect_problems(self, snapshot_id: str) -> List[ArchitectureProblem]:
        snapshot = self.snapshots.get(snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot '{snapshot_id}' not found.")

        t0 = time.time()
        detected = self.detector.detect_problems(snapshot)
        for prob in detected:
            self.validator.validate_problem(prob)
            self.problems[prob.problem_id] = prob
            self.index.index_problem(prob)
            self.persistence.save_problem(prob)
            self.provenance.record_event(
                target_id=prob.problem_id,
                source_type="ArchitectureProblem",
                action="PROBLEM_DETECTED",
            )
        self.metrics.record_stage("problem_detection_ms", (time.time() - t0) * 1000.0)
        return detected

    def evaluate_problem(
        self,
        problem_id: str,
        snapshot_id: str,
        external_hint: Optional[Dict[str, Any]] = None,
        policy_name: str = "STANDARD",
    ) -> Dict[str, Any]:
        """Runs the complete 12-step architectural evaluation pipeline for a problem."""
        snapshot = self.snapshots.get(snapshot_id)
        problem = self.problems.get(problem_id)
        if not snapshot or not problem:
            raise ValueError(f"Snapshot '{snapshot_id}' or problem '{problem_id}' missing.")

        # 1. Constraint Extraction
        t0 = time.time()
        constraints = self.constraint_extractor.extract_constraints(problem, snapshot)
        self.metrics.record_stage("constraint_ms", (time.time() - t0) * 1000.0)

        # 2. Alternative Generation
        t0 = time.time()
        alts = self.alternative_generator.generate_alternatives(
            problem, constraints, external_hint=external_hint
        )
        self.alternatives[problem_id] = alts
        for a in alts:
            self.index.index_alternative(a)
            self.persistence.save_alternative(a)
        self.metrics.record_stage("alternative_generation_ms", (time.time() - t0) * 1000.0)

        # 3. Multidimensional Evaluation per Alternative
        impacts: Dict[str, ImpactAnalysisResult] = {}
        contracts: Dict[str, ContractAnalysisResult] = {}
        behaviors: Dict[str, BehaviorAnalysisResult] = {}
        risks: Dict[str, RiskAnalysisResult] = {}
        costs: Dict[str, CostEstimationResult] = {}
        migration_plans: Dict[str, ArchitectureMigrationPlan] = {}
        simulations: Dict[str, SimulationResult] = {}
        verification_plans: Dict[str, VerificationPlan] = {}
        decisions: Dict[str, ArchitectureGovernanceDecision] = {}

        t_impact_sum = 0.0
        t_contract_sum = 0.0
        t_behavior_sum = 0.0
        t_risk_sum = 0.0
        t_migration_sum = 0.0
        t_simulation_sum = 0.0

        for alt in alts:
            # Impact
            t = time.time()
            imp = self.impact_analyzer.analyze_impact(alt, snapshot)
            impacts[alt.alternative_id] = imp
            t_impact_sum += (time.time() - t)

            # Contract
            t = time.time()
            cnt = self.contract_analyzer.analyze_contracts(alt, snapshot)
            contracts[alt.alternative_id] = cnt
            t_contract_sum += (time.time() - t)

            # Behavior
            t = time.time()
            beh = self.behavior_analyzer.analyze_behavior(alt, snapshot)
            behaviors[alt.alternative_id] = beh
            t_behavior_sum += (time.time() - t)

            # Risk
            t = time.time()
            rsk = self.risk_analyzer.analyze_risk(alt, snapshot, contract_status=cnt.status)
            risks[alt.alternative_id] = rsk
            t_risk_sum += (time.time() - t)

            # Cost
            cst = self.cost_model.estimate_cost(alt, snapshot)
            costs[alt.alternative_id] = cst

            # Migration Plan
            t = time.time()
            mig = self.migration_planner.plan_migration(alt)
            self.validator.validate_migration_plan(mig)
            migration_plans[alt.alternative_id] = mig
            self.persistence.save_migration_plan(mig)
            t_migration_sum += (time.time() - t)

            # Simulation
            t = time.time()
            sim = self.simulator.simulate(alt, snapshot, mig, cnt)
            simulations[alt.alternative_id] = sim
            self.persistence.save_simulation(sim)
            t_simulation_sum += (time.time() - t)

            # Verification Plan
            ver = self.verification_planner.plan_verification(alt, imp, snapshot)
            verification_plans[alt.alternative_id] = ver

            # Security Sentinel Check
            is_secure, sec_violations = self.security_filter.validate_proposal(
                alt, context={"problem_id": problem.problem_id}
            )

            # Governance Decision Gate
            dec = self.governance_engine.evaluate_governance(
                problem=problem,
                alternative=alt,
                simulation_status=sim.status,
                risk_criticality=rsk.criticality,
                contract_status=cnt.status,
                sentinel_passed=is_secure,
                policy_mode=policy_name,
            )
            self.validator.validate_governance_decision(dec, alt)
            decisions[alt.alternative_id] = dec
            self.decisions[dec.decision_id] = dec
            self.persistence.save_governance_decision(dec)

            self.provenance.record_event(
                target_id=dec.decision_id,
                source_type="ArchitectureGovernanceDecision",
                action=f"GOVERNANCE_STATE_{dec.state.value}",
            )

        self.metrics.record_stage("impact_ms", t_impact_sum * 1000.0)
        self.metrics.record_stage("contract_ms", t_contract_sum * 1000.0)
        self.metrics.record_stage("behavior_ms", t_behavior_sum * 1000.0)
        self.metrics.record_stage("risk_ms", t_risk_sum * 1000.0)
        self.metrics.record_stage("migration_ms", t_migration_sum * 1000.0)
        self.metrics.record_stage("simulation_ms", t_simulation_sum * 1000.0)

        # 4. Multi-dimensional Trade-Off Comparison
        t0 = time.time()
        comparison = self.comparator.compare_alternatives(
            problem=problem,
            alternatives=alts,
            impacts=impacts,
            risks=risks,
            costs=costs,
        )
        self.metrics.record_stage("comparison_ms", (time.time() - t0) * 1000.0)

        return {
            "problem": problem.to_dict(),
            "constraints": [c.to_dict() for c in constraints],
            "alternatives": [a.to_dict() for a in alts],
            "comparison": comparison.to_dict(),
            "impacts": {k: v.to_dict() for k, v in impacts.items()},
            "contracts": {k: v.to_dict() for k, v in contracts.items()},
            "behaviors": {k: v.to_dict() for k, v in behaviors.items()},
            "risks": {k: v.to_dict() for k, v in risks.items()},
            "costs": {k: v.to_dict() for k, v in costs.items()},
            "migration_plans": {k: v.to_dict() for k, v in migration_plans.items()},
            "simulations": {k: v.to_dict() for k, v in simulations.items()},
            "verification_plans": {k: v.to_dict() for k, v in verification_plans.items()},
            "governance_decisions": {k: v.to_dict() for k, v in decisions.items()},
            "metrics": self.metrics.to_dict(),
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "ready",
            "snapshot_count": len(self.snapshots),
            "problem_count": len(self.problems),
            "indexed_items": self.index.size(),
            "cached_entries": self.cache.size(),
            "governance_decision_count": len(self.decisions),
            "provenance_chain_valid": self.provenance.verify_integrity(),
            "metrics": self.metrics.to_dict(),
        }
