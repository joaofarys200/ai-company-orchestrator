"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Core Data Models, Types, and Enums for Bounded Behavioral Exploration.
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
    BehavioralDelta,
    BehavioralInvariantType,
    BehavioralStage,
    BehavioralStageExecution,
    CompatibilityCategory,
    Counterexample,
    EquivalenceLevel,
    ExecutionGateDecision,
    LatencyClass,
    MigrationProof,
    ProofResult,
    RuntimeTrace,
)


class ExplorationStrategy(str, enum.Enum):
    """Supported scenario exploration strategies."""
    BOUNDARY_EXPLORATION = "BOUNDARY_EXPLORATION"
    SCHEMA_MUTATION = "SCHEMA_MUTATION"
    TRACE_REPLAY = "TRACE_REPLAY"
    COUNTEREXAMPLE_REPLAY = "COUNTEREXAMPLE_REPLAY"
    POLYMORPHIC_EXPLORATION = "POLYMORPHIC_EXPLORATION"
    ERROR_PATH_EXPLORATION = "ERROR_PATH_EXPLORATION"
    RETRY_EXPLORATION = "RETRY_EXPLORATION"
    CONCURRENCY_EXPLORATION = "CONCURRENCY_EXPLORATION"


class MutationCategory(str, enum.Enum):
    """Categorization of deterministic mutations."""
    SCHEMA = "SCHEMA"
    DATA = "DATA"
    FLOW = "FLOW"
    TIMING = "TIMING"
    AUTH = "AUTH"
    ECONOMIC = "ECONOMIC"


class CoverageDimension(str, enum.Enum):
    """The 10 mandatory dimensions of behavioral coverage."""
    INPUT = "input"
    FIELD = "field"
    BRANCH = "branch"
    VARIANT = "variant"
    ERROR_PATH = "error_path"
    INVARIANT = "invariant"
    CONSUMER = "consumer"
    EVENT = "event"
    SIDE_EFFECT = "side_effect"
    AUTHORIZATION = "authorization"


class CoverageThresholdPolicy(str, enum.Enum):
    """Configurable coverage threshold policies."""
    STANDARD = "STANDARD"    # 80% coverage
    STRICT = "STRICT"        # 95% coverage
    CRITICAL = "CRITICAL"    # 100% of relevant dimensions


def compute_deterministic_id(data: Any, prefix: str = "") -> str:
    """Compute deterministic SHA-256 hash for structured payload."""
    serialized = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}" if prefix else digest


@dataclass
class ExplorationBudget:
    """
    Strict explicit budget for bounded scenario exploration.
    The proof scope must never hide its limits.
    """
    max_scenarios: int = 100
    max_depth: int = 3
    max_runtime: float = 5.0  # seconds
    max_branching: int = 5
    max_trace_size: int = 1000
    max_concurrency_variants: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_scenarios": self.max_scenarios,
            "max_depth": self.max_depth,
            "max_runtime": self.max_runtime,
            "max_branching": self.max_branching,
            "max_trace_size": self.max_trace_size,
            "max_concurrency_variants": self.max_concurrency_variants,
        }


@dataclass
class ProofScope:
    """
    Explicit scope definition for bounded behavioral exploration.
    Every proof is evaluated strictly WITHIN its recorded scope.
    """
    scope_id: str
    contract_id: str
    before_version: str
    after_version: str
    budget: ExplorationBudget
    strategies: List[ExplorationStrategy] = field(default_factory=list)
    seed: int = 42
    environment: str = "sandbox"
    max_interleavings: int = 10
    invariants: List[BehavioralInvariantType] = field(default_factory=list)
    coverage_threshold_policy: CoverageThresholdPolicy = CoverageThresholdPolicy.STANDARD
    provenance: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "contract_id": self.contract_id,
            "before_version": self.before_version,
            "after_version": self.after_version,
            "budget": self.budget.to_dict(),
            "strategies": [s.value for s in self.strategies],
            "seed": self.seed,
            "environment": self.environment,
            "max_interleavings": self.max_interleavings,
            "invariants": [i.value for i in self.invariants],
            "coverage_threshold_policy": self.coverage_threshold_policy.value,
            "provenance": self.provenance,
            "created_at": self.created_at,
        }


@dataclass
class BehavioralScenario:
    """
    Unit of bounded behavioral scenario exploration.
    Guaranteed deterministic scenario_id when all canonical inputs match.
    """
    scenario_id: str
    consumer_id: str
    contract_id: str
    input: Dict[str, Any]
    expected_behavior: Dict[str, Any]
    mutation: Optional[Dict[str, Any]] = None
    preconditions: List[str] = field(default_factory=list)
    environment: str = "sandbox"
    seed: int = 42
    parent_scenario: Optional[str] = None
    coverage_target: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)
    budget: Dict[str, Any] = field(default_factory=dict)
    strategy: ExplorationStrategy = ExplorationStrategy.SCHEMA_MUTATION
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        consumer_id: str,
        contract_id: str,
        input_payload: Dict[str, Any],
        expected_behavior: Dict[str, Any],
        mutation: Optional[Dict[str, Any]] = None,
        preconditions: Optional[List[str]] = None,
        environment: str = "sandbox",
        seed: int = 42,
        parent_scenario: Optional[str] = None,
        coverage_target: str = "",
        provenance: Optional[Dict[str, Any]] = None,
        budget: Optional[Dict[str, Any]] = None,
        strategy: ExplorationStrategy = ExplorationStrategy.SCHEMA_MUTATION,
    ) -> BehavioralScenario:
        hash_payload = {
            "consumer_id": consumer_id,
            "contract_id": contract_id,
            "input": input_payload,
            "expected_behavior": expected_behavior,
            "mutation": mutation,
            "preconditions": sorted(preconditions or []),
            "environment": environment,
            "seed": seed,
            "parent_scenario": parent_scenario,
            "coverage_target": coverage_target,
            "strategy": strategy.value,
        }
        scenario_id = compute_deterministic_id(hash_payload, prefix="scen_")
        return cls(
            scenario_id=scenario_id,
            consumer_id=consumer_id,
            contract_id=contract_id,
            input=input_payload,
            expected_behavior=expected_behavior,
            mutation=mutation,
            preconditions=preconditions or [],
            environment=environment,
            seed=seed,
            parent_scenario=parent_scenario,
            coverage_target=coverage_target,
            provenance=provenance or {"generator": "ScenarioGenerator", "seed": seed},
            budget=budget or {},
            strategy=strategy,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "consumer_id": self.consumer_id,
            "contract_id": self.contract_id,
            "input": self.input,
            "expected_behavior": self.expected_behavior,
            "mutation": self.mutation,
            "preconditions": self.preconditions,
            "environment": self.environment,
            "seed": self.seed,
            "parent_scenario": self.parent_scenario,
            "coverage_target": self.coverage_target,
            "provenance": self.provenance,
            "budget": self.budget,
            "strategy": self.strategy.value,
            "created_at": self.created_at,
        }


@dataclass
class ScenarioExecutionResult:
    """Telemetry and outcome of running a scenario against before & after targets."""
    scenario_id: str
    success: bool
    before_trace: Optional[RuntimeTrace] = None
    after_trace: Optional[RuntimeTrace] = None
    is_divergent: bool = False
    divergence_reason: Optional[str] = None
    invariants_violated: List[BehavioralInvariantType] = field(default_factory=list)
    latency_ms: float = 0.0
    execution_error: Optional[str] = None
    side_effects_before: List[Dict[str, Any]] = field(default_factory=list)
    side_effects_after: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "success": self.success,
            "is_divergent": self.is_divergent,
            "divergence_reason": self.divergence_reason,
            "invariants_violated": [i.value for i in self.invariants_violated],
            "latency_ms": self.latency_ms,
            "execution_error": self.execution_error,
            "before_trace_id": self.before_trace.trace_id if self.before_trace else None,
            "after_trace_id": self.after_trace.trace_id if self.after_trace else None,
            "side_effects_before": self.side_effects_before,
            "side_effects_after": self.side_effects_after,
            "metadata": self.metadata,
        }


@dataclass
class ShrunkCounterexample:
    """
    Minimized counterexample produced via Delta Debugging / shrinking.
    Reduces large payloads down to the minimal subset preserving divergence.
    """
    counterexample_id: str
    scenario_id: str
    consumer_id: str
    contract_id: str
    original_input: Dict[str, Any]
    minimal_input: Dict[str, Any]
    difference: str
    original_field_count: int
    minimal_field_count: int
    shrink_steps: int
    trace_id: str
    proof_scope_id: str
    reproducible_seed: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counterexample_id": self.counterexample_id,
            "scenario_id": self.scenario_id,
            "consumer_id": self.consumer_id,
            "contract_id": self.contract_id,
            "original_input": self.original_input,
            "minimal_input": self.minimal_input,
            "difference": self.difference,
            "original_field_count": self.original_field_count,
            "minimal_field_count": self.minimal_field_count,
            "shrink_steps": self.shrink_steps,
            "trace_id": self.trace_id,
            "proof_scope_id": self.proof_scope_id,
            "reproducible_seed": self.reproducible_seed,
            "timestamp": self.timestamp,
        }


@dataclass
class CoverageDimensionReport:
    """Report for a single behavioral coverage dimension."""
    dimension: CoverageDimension
    total: int
    covered: int
    uncovered: int
    unknown: int
    not_applicable: int
    percentage: float
    covered_items: List[str] = field(default_factory=list)
    uncovered_items: List[str] = field(default_factory=list)
    unknown_items: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "total": self.total,
            "covered": self.covered,
            "uncovered": self.uncovered,
            "unknown": self.unknown,
            "not_applicable": self.not_applicable,
            "percentage": round(self.percentage, 4),
            "covered_items": self.covered_items,
            "uncovered_items": self.uncovered_items,
            "unknown_items": self.unknown_items,
        }


@dataclass
class BehavioralCoverage:
    """
    Multi-dimensional behavioral coverage report.
    Guarantees that 'uncovered' is never converted into 'compatible'.
    """
    coverage_id: str
    scope_id: str
    dimensions: Dict[CoverageDimension, CoverageDimensionReport] = field(default_factory=dict)
    overall_percentage: float = 0.0
    threshold_policy: CoverageThresholdPolicy = CoverageThresholdPolicy.STANDARD
    threshold_met: bool = False
    uncovered_items: List[str] = field(default_factory=list)
    unknown_items: List[str] = field(default_factory=list)
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coverage_id": self.coverage_id,
            "scope_id": self.scope_id,
            "dimensions": {k.value: v.to_dict() for k, v in self.dimensions.items()},
            "overall_percentage": round(self.overall_percentage, 4),
            "threshold_policy": self.threshold_policy.value,
            "threshold_met": self.threshold_met,
            "uncovered_items": self.uncovered_items,
            "unknown_items": self.unknown_items,
            "evaluated_at": self.evaluated_at,
        }


@dataclass
class BoundedExplorationProof:
    """
    Cryptographic certificate of bounded behavioral proof exploration.
    Integrates scope, budget, coverage, counterexamples, and invariants.
    """
    proof_id: str
    migration_id: str
    scope: ProofScope
    coverage: BehavioralCoverage
    result: ProofResult
    counterexamples: List[Counterexample] = field(default_factory=list)
    shrunk_counterexamples: List[ShrunkCounterexample] = field(default_factory=list)
    invariants_checked: List[BehavioralInvariantType] = field(default_factory=list)
    invariants_preserved: bool = True
    unexplored_interleavings: List[str] = field(default_factory=list)
    consumer_uncertainties: List[str] = field(default_factory=list)
    confidence: float = 1.0
    gate_decision: ExecutionGateDecision = ExecutionGateDecision.GATE_CLEARED
    provenance: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    proof_hash: str = ""

    def compute_hash(self) -> str:
        data = {
            "proof_id": self.proof_id,
            "migration_id": self.migration_id,
            "scope_id": self.scope.scope_id,
            "coverage_id": self.coverage.coverage_id,
            "result": self.result.value,
            "counterexamples_count": len(self.counterexamples),
            "invariants_preserved": self.invariants_preserved,
            "unexplored_interleavings": sorted(self.unexplored_interleavings),
            "consumer_uncertainties": sorted(self.consumer_uncertainties),
            "seed": self.scope.seed,
        }
        return compute_deterministic_id(data, prefix="prf_")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "migration_id": self.migration_id,
            "scope": self.scope.to_dict(),
            "coverage": self.coverage.to_dict(),
            "result": self.result.value,
            "counterexamples": [c.to_dict() for c in self.counterexamples],
            "shrunk_counterexamples": [s.to_dict() for s in self.shrunk_counterexamples],
            "invariants_checked": [i.value for i in self.invariants_checked],
            "invariants_preserved": self.invariants_preserved,
            "unexplored_interleavings": self.unexplored_interleavings,
            "consumer_uncertainties": self.consumer_uncertainties,
            "confidence": self.confidence,
            "gate_decision": self.gate_decision.value,
            "provenance": self.provenance,
            "timestamp": self.timestamp,
            "proof_hash": self.proof_hash or self.compute_hash(),
        }
