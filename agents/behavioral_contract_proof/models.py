"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Core Data Models, Enums, and Structured Types.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


class CompatibilityCategory(str, enum.Enum):
    """Categorical classification of compatibility across contract layers."""
    TYPE_COMPATIBLE = "TYPE_COMPATIBLE"
    CONTRACT_COMPATIBLE = "CONTRACT_COMPATIBLE"
    BEHAVIORALLY_COMPATIBLE = "BEHAVIORALLY_COMPATIBLE"
    BEHAVIORALLY_INCOMPATIBLE = "BEHAVIORALLY_INCOMPATIBLE"
    BEHAVIOR_UNKNOWN = "BEHAVIOR_UNKNOWN"


class EquivalenceLevel(str, enum.Enum):
    """Formal levels of behavioral and structural equivalence."""
    EXACT_EQUIVALENCE = "EXACT_EQUIVALENCE"
    SEMANTIC_EQUIVALENCE = "SEMANTIC_EQUIVALENCE"
    ALLOWED_CHANGE = "ALLOWED_CHANGE"
    BREAKING_CHANGE = "BREAKING_CHANGE"
    UNKNOWN = "UNKNOWN"


class BehavioralInvariantType(str, enum.Enum):
    """Supported behavioral invariant rules."""
    AUTHORIZATION_PRESERVED = "AUTHORIZATION_PRESERVED"
    ECONOMIC_VALUE_PRESERVED = "ECONOMIC_VALUE_PRESERVED"
    EVENT_SEMANTICS_PRESERVED = "EVENT_SEMANTICS_PRESERVED"
    REQUIRED_FIELDS_PRESERVED = "REQUIRED_FIELDS_PRESERVED"
    ERROR_SEMANTICS_PRESERVED = "ERROR_SEMANTICS_PRESERVED"
    SIDE_EFFECT_ORDER_PRESERVED = "SIDE_EFFECT_ORDER_PRESERVED"
    CONSUMER_EXPECTATION_PRESERVED = "CONSUMER_EXPECTATION_PRESERVED"


class ProofResult(str, enum.Enum):
    """Deterministic outcomes of a migration proof evaluation."""
    PROVEN_COMPATIBLE = "PROVEN_COMPATIBLE"
    PROVEN_COMPATIBLE_WITHIN_SCOPE = "PROVEN_COMPATIBLE_WITHIN_SCOPE"
    PROVEN_INCOMPATIBLE = "PROVEN_INCOMPATIBLE"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ExecutionGateDecision(str, enum.Enum):
    """Decisions issued by the behavioral mission gate."""
    EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
    GATE_CLEARED = "GATE_CLEARED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class LatencyClass(str, enum.Enum):
    """Observed latency classification."""
    ULTRA_FAST = "ULTRA_FAST"  # < 10ms
    FAST = "FAST"              # < 50ms
    NORMAL = "NORMAL"          # < 200ms
    DEGRADED = "DEGRADED"      # >= 200ms


class BehavioralStage(str, enum.Enum):
    """8-stage structural model of contract invocation behavior."""
    REQUEST = "REQUEST"
    AUTH = "AUTH"
    VALIDATION = "VALIDATION"
    BUSINESS_LOGIC = "BUSINESS_LOGIC"
    RESPONSE = "RESPONSE"
    EVENT = "EVENT"
    SIDE_EFFECT = "SIDE_EFFECT"
    ECONOMIC_EFFECT = "ECONOMIC_EFFECT"


@dataclass
class BehavioralStageExecution:
    """Telemetry of a single execution stage within a behavioral trace."""
    stage: BehavioralStage
    started_at: float
    duration_ms: float
    input_state: Dict[str, Any] = field(default_factory=dict)
    output_state: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "input_state": self.input_state,
            "output_state": self.output_state,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class BehaviorBaseline:
    """
    Immutable behavioral baseline for a contract, version, and consumer.
    Strictly protected against silent overwrite.
    """
    contract_id: str
    contract_version: str
    consumer_id: str
    operation: str
    input_shape: Dict[str, Any]
    output_shape: Dict[str, Any]
    status_code: int
    side_effects: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    economic_effects: List[Dict[str, Any]] = field(default_factory=list)
    authorization_state: Dict[str, Any] = field(default_factory=dict)
    latency_class: LatencyClass = LatencyClass.NORMAL
    trace_hash: str = ""
    timestamp: float = field(default_factory=time.time)
    source: str = "runtime_observation"
    provenance: Dict[str, Any] = field(default_factory=dict)
    baseline_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_version": self.contract_version,
            "consumer_id": self.consumer_id,
            "operation": self.operation,
            "input_shape": self.input_shape,
            "output_shape": self.output_shape,
            "status_code": self.status_code,
            "side_effects": self.side_effects,
            "events": self.events,
            "economic_effects": self.economic_effects,
            "authorization_state": self.authorization_state,
            "latency_class": self.latency_class.value,
            "trace_hash": self.trace_hash,
            "timestamp": self.timestamp,
            "source": self.source,
            "provenance": self.provenance,
            "baseline_hash": self.baseline_hash,
        }


@dataclass
class RuntimeTrace:
    """
    Observed execution trace before and after normalization.
    """
    trace_id: str
    source: str
    timestamp: float
    mission_id: str
    consumer_id: str
    contract_id: str
    operation: str
    input_payload: Dict[str, Any]
    output_payload: Dict[str, Any]
    status_code: int
    stages: List[BehavioralStageExecution] = field(default_factory=list)
    side_effects: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    economic_effects: List[Dict[str, Any]] = field(default_factory=list)
    authorization_state: Dict[str, Any] = field(default_factory=dict)
    trace_hash: str = ""
    parent_trace_hash: Optional[str] = None
    environment: str = "production"
    build_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "source": self.source,
            "timestamp": self.timestamp,
            "mission_id": self.mission_id,
            "consumer_id": self.consumer_id,
            "contract_id": self.contract_id,
            "operation": self.operation,
            "input_payload": self.input_payload,
            "output_payload": self.output_payload,
            "status_code": self.status_code,
            "stages": [s.to_dict() for s in self.stages],
            "side_effects": self.side_effects,
            "events": self.events,
            "economic_effects": self.economic_effects,
            "authorization_state": self.authorization_state,
            "trace_hash": self.trace_hash,
            "parent_trace_hash": self.parent_trace_hash,
            "environment": self.environment,
            "build_hash": self.build_hash,
        }


@dataclass
class BehavioralModel:
    """Structural behavioral model of an operation."""
    model_id: str
    contract_id: str
    version: str
    stages: List[BehavioralStage] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    invariants: List[BehavioralInvariantType] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "contract_id": self.contract_id,
            "version": self.version,
            "stages": [s.value for s in self.stages],
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "invariants": [i.value for i in self.invariants],
        }


@dataclass
class Counterexample:
    """
    Concrete counterexample generated when behavioral compatibility fails.
    """
    counterexample_id: str
    input_payload: Dict[str, Any]
    expected_behavior: Dict[str, Any]
    observed_behavior: Dict[str, Any]
    difference: str
    consumer_id: str
    contract_id: str
    trace_id: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counterexample_id": self.counterexample_id,
            "input_payload": self.input_payload,
            "expected_behavior": self.expected_behavior,
            "observed_behavior": self.observed_behavior,
            "difference": self.difference,
            "consumer_id": self.consumer_id,
            "contract_id": self.contract_id,
            "trace_id": self.trace_id,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }


@dataclass
class MigrationProof:
    """
    Formal certificate of behavioral compatibility proof between contract versions.
    """
    migration_id: str
    before_version: str
    after_version: str
    consumers: List[str]
    baseline_hash: str
    post_change_hash: str
    invariants_checked: List[BehavioralInvariantType] = field(default_factory=list)
    counterexamples: List[Counterexample] = field(default_factory=list)
    confidence: float = 1.0
    result: ProofResult = ProofResult.INSUFFICIENT_EVIDENCE
    provenance: Dict[str, Any] = field(default_factory=dict)
    compatibility_category: CompatibilityCategory = CompatibilityCategory.BEHAVIOR_UNKNOWN
    equivalence_level: EquivalenceLevel = EquivalenceLevel.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "migration_id": self.migration_id,
            "before_version": self.before_version,
            "after_version": self.after_version,
            "consumers": self.consumers,
            "baseline_hash": self.baseline_hash,
            "post_change_hash": self.post_change_hash,
            "invariants_checked": [i.value for i in self.invariants_checked],
            "counterexamples": [c.to_dict() for c in self.counterexamples],
            "confidence": self.confidence,
            "result": self.result.value,
            "provenance": self.provenance,
            "compatibility_category": self.compatibility_category.value,
            "equivalence_level": self.equivalence_level.value,
        }


@dataclass
class BehavioralDelta:
    """Preflight predicted delta compared against post-change observed delta."""
    delta_id: str
    contract_id: str
    consumer_id: str
    predicted_delta: Dict[str, Any]
    observed_delta: Dict[str, Any]
    is_predicted_match: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delta_id": self.delta_id,
            "contract_id": self.contract_id,
            "consumer_id": self.consumer_id,
            "predicted_delta": self.predicted_delta,
            "observed_delta": self.observed_delta,
            "is_predicted_match": self.is_predicted_match,
        }
