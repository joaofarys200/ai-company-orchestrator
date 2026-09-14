"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Core Data Models, Types, Enums, and Structured State Containers.
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    BehavioralInvariantType,
    Counterexample,
    ExecutionGateDecision,
    ProofResult,
    RuntimeTrace,
)
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    CoverageDimension,
    CoverageThresholdPolicy,
    ExplorationBudget,
    ExplorationStrategy,
    ProofScope,
    ScenarioExecutionResult,
    ShrunkCounterexample,
    compute_deterministic_id,
)


class ExplorationPolicy(str, enum.Enum):
    """Exploration search policies for scenario prioritization and budgets."""
    STANDARD = "STANDARD"
    STRICT = "STRICT"
    CRITICAL = "CRITICAL"
    ECONOMIC_CRITICAL = "ECONOMIC_CRITICAL"
    SECURITY_CRITICAL = "SECURITY_CRITICAL"


@dataclass
class BehavioralExplorationRisk:
    """
    Multi-dimensional risk model for a contract change.
    All source dimensions are preserved transparently alongside the normalized score.
    """
    contract_risk: float = 0.0
    consumer_risk: float = 0.0
    economic_risk: float = 0.0
    security_risk: float = 0.0
    polymorphic_risk: float = 0.0
    dynamic_consumer_risk: float = 0.0
    behavioral_uncertainty: float = 0.0
    historical_failure_rate: float = 0.0
    blast_radius: float = 0.0
    change_magnitude: float = 0.0
    coverage_gap: float = 0.0
    risk_score: float = 0.0

    def compute_score(self) -> float:
        """
        Compute weighted normalized risk_score in [0.0, 1.0].
        Critical risk components (economic, security) carry dominant weights.
        """
        weights = {
            "economic_risk": 0.25,
            "security_risk": 0.22,
            "dynamic_consumer_risk": 0.12,
            "blast_radius": 0.12,
            "change_magnitude": 0.08,
            "contract_risk": 0.08,
            "coverage_gap": 0.05,
            "historical_failure_rate": 0.05,
            "consumer_risk": 0.05,
            "behavioral_uncertainty": 0.05,
            "polymorphic_risk": 0.02,
        }
        total = (
            self.economic_risk * weights["economic_risk"]
            + self.security_risk * weights["security_risk"]
            + self.dynamic_consumer_risk * weights["dynamic_consumer_risk"]
            + self.change_magnitude * weights["change_magnitude"]
            + self.behavioral_uncertainty * weights["behavioral_uncertainty"]
            + self.blast_radius * weights["blast_radius"]
            + self.historical_failure_rate * weights["historical_failure_rate"]
            + self.coverage_gap * weights["coverage_gap"]
            + self.contract_risk * weights["contract_risk"]
            + self.consumer_risk * weights["consumer_risk"]
            + self.polymorphic_risk * weights["polymorphic_risk"]
        )
        self.risk_score = round(min(1.0, max(0.0, total)), 4)
        return self.risk_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_risk": self.contract_risk,
            "consumer_risk": self.consumer_risk,
            "economic_risk": self.economic_risk,
            "security_risk": self.security_risk,
            "polymorphic_risk": self.polymorphic_risk,
            "dynamic_consumer_risk": self.dynamic_consumer_risk,
            "behavioral_uncertainty": self.behavioral_uncertainty,
            "historical_failure_rate": self.historical_failure_rate,
            "blast_radius": self.blast_radius,
            "change_magnitude": self.change_magnitude,
            "coverage_gap": self.coverage_gap,
            "risk_score": self.risk_score or self.compute_score(),
        }


@dataclass
class BehavioralUncertainty:
    """
    Continuous uncertainty model capturing epistemic and structural unknowns.
    """
    uncertain_consumer: float = 0.0
    insufficient_evidence: float = 0.0
    insufficient_coverage: float = 0.0
    unknown_variant: float = 0.0
    unexplored_branch: float = 0.0
    unknown_error_path: float = 0.0
    dynamic_dispatch: float = 0.0
    concurrency_gap: float = 0.0
    external_dependency: float = 0.0
    historical_failure: float = 0.0
    missing_baseline: float = 0.0
    uncertainty_score: float = 0.0

    def compute_score(self) -> float:
        """Aggregate continuous uncertainty score in [0.0, 1.0]."""
        components = [
            self.uncertain_consumer,
            self.insufficient_evidence,
            self.insufficient_coverage,
            self.unknown_variant,
            self.unexplored_branch,
            self.unknown_error_path,
            self.dynamic_dispatch,
            self.concurrency_gap,
            self.external_dependency,
            self.historical_failure,
            self.missing_baseline,
        ]
        # Quadratic mean / RMS to give prominence to severe isolated uncertainties
        rms = (sum(c ** 2 for c in components) / len(components)) ** 0.5
        self.uncertainty_score = round(min(1.0, max(0.0, rms * 1.5)), 4)
        return self.uncertainty_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uncertain_consumer": self.uncertain_consumer,
            "insufficient_evidence": self.insufficient_evidence,
            "insufficient_coverage": self.insufficient_coverage,
            "unknown_variant": self.unknown_variant,
            "unexplored_branch": self.unexplored_branch,
            "unknown_error_path": self.unknown_error_path,
            "dynamic_dispatch": self.dynamic_dispatch,
            "concurrency_gap": self.concurrency_gap,
            "external_dependency": self.external_dependency,
            "historical_failure": self.historical_failure,
            "missing_baseline": self.missing_baseline,
            "uncertainty_score": self.uncertainty_score or self.compute_score(),
        }


@dataclass
class ScenarioInformationValue:
    """
    Estimated information value of executing a scenario.
    Combines potential risk, coverage gain, uncertainty reduction, and invariant relevance.
    """
    scenario_id: str
    potential_risk: float = 0.0
    coverage_gain_estimate: float = 0.0
    uncertainty_reduction_estimate: float = 0.0
    blast_radius: float = 0.0
    novelty: float = 0.0
    historical_failure_weight: float = 0.0
    contract_delta_relevance: float = 0.0
    invariant_relevance: float = 0.0
    total_information_value: float = 0.0
    explanation: str = ""

    def compute_value(self) -> float:
        val = (
            self.potential_risk * 0.30
            + self.uncertainty_reduction_estimate * 0.25
            + self.coverage_gain_estimate * 0.20
            + self.invariant_relevance * 0.10
            + self.historical_failure_weight * 0.08
            + self.novelty * 0.07
        )
        self.total_information_value = round(min(1.0, max(0.0, val)), 4)
        return self.total_information_value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "potential_risk": self.potential_risk,
            "coverage_gain_estimate": self.coverage_gain_estimate,
            "uncertainty_reduction_estimate": self.uncertainty_reduction_estimate,
            "blast_radius": self.blast_radius,
            "novelty": self.novelty,
            "historical_failure_weight": self.historical_failure_weight,
            "contract_delta_relevance": self.contract_delta_relevance,
            "invariant_relevance": self.invariant_relevance,
            "total_information_value": self.total_information_value or self.compute_value(),
            "explanation": self.explanation,
        }


@dataclass
class ScenarioRanking:
    """
    Deterministic ranked priority entry for a scenario in the exploration queue.
    """
    scenario_id: str
    priority: float
    rank: int
    risk_score: float
    information_value: float
    uncertainty_reduction: float
    impact_weight: float
    policy_cap_applied: bool = False
    policy_override_applied: bool = False
    override_reason: Optional[str] = None
    target_field: str = ""
    strategy: ExplorationStrategy = ExplorationStrategy.SCHEMA_MUTATION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "priority": round(self.priority, 4),
            "rank": self.rank,
            "risk_score": round(self.risk_score, 4),
            "information_value": round(self.information_value, 4),
            "uncertainty_reduction": round(self.uncertainty_reduction, 4),
            "impact_weight": round(self.impact_weight, 4),
            "policy_cap_applied": self.policy_cap_applied,
            "policy_override_applied": self.policy_override_applied,
            "override_reason": self.override_reason,
            "target_field": self.target_field,
            "strategy": self.strategy.value,
        }


@dataclass
class NegativeEvidence:
    """
    Evidence recorded when a scenario passes without behavioral divergence.
    Diminishes risk and uncertainty without falsely claiming zero residual risk.
    """
    scenario_id: str
    execution_count: int = 1
    no_divergence_observed: bool = True
    risk_reduction_factor: float = 0.15
    uncertainty_reduction_factor: float = 0.20
    residual_risk: float = 0.05
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "execution_count": self.execution_count,
            "no_divergence_observed": self.no_divergence_observed,
            "risk_reduction_factor": self.risk_reduction_factor,
            "uncertainty_reduction_factor": self.uncertainty_reduction_factor,
            "residual_risk": self.residual_risk,
            "timestamp": self.timestamp,
        }


@dataclass
class RiskAdaptiveBudget:
    """
    Dynamic budget allocating resources proportionally to migration risk.
    """
    max_cost: float = 100.0
    max_runtime: float = 5.0
    max_scenarios: int = 100
    max_depth: int = 3
    risk_budget: float = 1.0
    cost_spent: float = 0.0
    runtime_spent: float = 0.0
    scenarios_executed: int = 0
    scenarios_skipped: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_cost": self.max_cost,
            "max_runtime": self.max_runtime,
            "max_scenarios": self.max_scenarios,
            "max_depth": self.max_depth,
            "risk_budget": round(self.risk_budget, 4),
            "cost_spent": round(self.cost_spent, 4),
            "runtime_spent": round(self.runtime_spent, 4),
            "scenarios_executed": self.scenarios_executed,
            "scenarios_skipped": self.scenarios_skipped,
        }


@dataclass
class ScenarioGraphEdge:
    """Relationship between two scenarios in the exploration scenario graph."""
    source_scenario_id: str
    target_scenario_id: str
    relation_type: str  # parent, child_mutation, related_scenario, same_contract_field, same_consumer, same_invariant, same_risk_dimension
    weight: float = 1.0


@dataclass
class ScenarioGraph:
    """
    Graph of scenario relationships enabling focused cluster exploration
    when a counterexample or failure is detected.
    """
    nodes: Dict[str, BehavioralScenario] = field(default_factory=dict)
    edges: List[ScenarioGraphEdge] = field(default_factory=list)

    def add_node(self, scenario: BehavioralScenario) -> None:
        self.nodes[scenario.scenario_id] = scenario

    def add_edge(self, source_id: str, target_id: str, relation: str, weight: float = 1.0) -> None:
        self.edges.append(ScenarioGraphEdge(source_id, target_id, relation, weight))

    def get_neighbors(self, scenario_id: str, relation_type: Optional[str] = None) -> List[str]:
        neighbors = []
        for e in self.edges:
            if e.source_scenario_id == scenario_id:
                if relation_type is None or e.relation_type == relation_type:
                    neighbors.append(e.target_scenario_id)
            elif e.target_scenario_id == scenario_id:
                if relation_type is None or e.relation_type == relation_type:
                    neighbors.append(e.source_scenario_id)
        return list(set(neighbors))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "edges": [
                {
                    "source": e.source_scenario_id,
                    "target": e.target_scenario_id,
                    "relation": e.relation_type,
                    "weight": e.weight,
                }
                for e in self.edges[:50]
            ],
        }


@dataclass
class AdaptiveProofResult:
    """
    Synthesis of an adaptive risk-directed behavioral proof execution.
    """
    proof_id: str
    migration_id: str
    contract_id: str
    policy: ExplorationPolicy
    result: ProofResult
    gate_decision: ExecutionGateDecision
    initial_risk: BehavioralExplorationRisk
    final_risk: BehavioralExplorationRisk
    initial_uncertainty: BehavioralUncertainty
    final_uncertainty: BehavioralUncertainty
    coverage: BehavioralCoverage
    budget: RiskAdaptiveBudget
    counterexamples: List[Counterexample] = field(default_factory=list)
    shrunk_counterexamples: List[ShrunkCounterexample] = field(default_factory=list)
    scenarios_ranked: int = 0
    scenarios_executed: int = 0
    scenarios_skipped: int = 0
    early_stopped: bool = False
    early_stop_reason: Optional[str] = None
    scenario_efficiency: float = 0.0  # risk_reduction / cost_spent
    provenance: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    proof_hash: str = ""

    def compute_hash(self) -> str:
        data = {
            "proof_id": self.proof_id,
            "migration_id": self.migration_id,
            "contract_id": self.contract_id,
            "policy": self.policy.value,
            "result": self.result.value,
            "final_risk_score": self.final_risk.risk_score,
            "final_uncertainty_score": self.final_uncertainty.uncertainty_score,
            "coverage_pct": self.coverage.overall_percentage,
            "counterexamples_count": len(self.counterexamples),
        }
        return compute_deterministic_id(data, prefix="apr_")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "migration_id": self.migration_id,
            "contract_id": self.contract_id,
            "policy": self.policy.value,
            "result": self.result.value,
            "gate_decision": self.gate_decision.value,
            "initial_risk": self.initial_risk.to_dict(),
            "final_risk": self.final_risk.to_dict(),
            "initial_uncertainty": self.initial_uncertainty.to_dict(),
            "final_uncertainty": self.final_uncertainty.to_dict(),
            "coverage": self.coverage.to_dict(),
            "budget": self.budget.to_dict(),
            "counterexamples": [c.to_dict() for c in self.counterexamples],
            "shrunk_counterexamples": [s.to_dict() for s in self.shrunk_counterexamples],
            "scenarios_ranked": self.scenarios_ranked,
            "scenarios_executed": self.scenarios_executed,
            "scenarios_skipped": self.scenarios_skipped,
            "early_stopped": self.early_stopped,
            "early_stop_reason": self.early_stop_reason,
            "scenario_efficiency": round(self.scenario_efficiency, 4),
            "provenance": self.provenance,
            "timestamp": self.timestamp,
            "proof_hash": self.proof_hash or self.compute_hash(),
        }
