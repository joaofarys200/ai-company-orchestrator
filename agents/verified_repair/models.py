"""
JARVIS OS — Phase 54: Verified Repair Synthesis & Patch Validation
Data Models, Enums, and Immutable Proof Contracts.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


def compute_deterministic_hash(data: Any, prefix: str = "") -> str:
    """Computes a deterministic SHA-256 hash formatted with optional prefix."""
    raw = json.dumps(data, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}{digest}" if prefix else digest


class RootCauseCategory(str, Enum):
    MISSING_IMPORT = "MISSING_IMPORT"
    MISSING_SYMBOL = "MISSING_SYMBOL"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    INVALID_ENTRYPOINT = "INVALID_ENTRYPOINT"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    RUNTIME_SCOPE_ERROR = "RUNTIME_SCOPE_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    PORT_CONFLICT = "PORT_CONFLICT"
    STARTUP_FAILURE = "STARTUP_FAILURE"
    HEALTHCHECK_FAILURE = "HEALTHCHECK_FAILURE"
    UNKNOWN = "UNKNOWN"


class FailureResolutionStatus(str, Enum):
    ORIGINAL_FAILURE_RESOLVED = "ORIGINAL_FAILURE_RESOLVED"
    ORIGINAL_FAILURE_NOT_RESOLVED = "ORIGINAL_FAILURE_NOT_RESOLVED"
    UNKNOWN = "UNKNOWN"


class RepairProofResult(str, Enum):
    REPAIR_PROVEN = "REPAIR_PROVEN"
    REPAIR_REJECTED = "REPAIR_REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RepairConfidenceLevel(str, Enum):
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    MEDIUM_CONFIDENCE = "MEDIUM_CONFIDENCE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


@dataclass
class RootCauseHypothesis:
    """Represents a structured, evidence-backed hypothesis for a failure."""
    cause_id: str
    failure_id: str
    category: RootCauseCategory
    evidence: str
    source_locations: List[str] = field(default_factory=list)
    confidence: float = 0.5
    supporting_observations: List[str] = field(default_factory=list)
    contradicting_observations: List[str] = field(default_factory=list)
    predicted_effect: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "failure_id": self.failure_id,
            "category": self.category.value if hasattr(self.category, "value") else str(self.category),
            "evidence": self.evidence,
            "source_locations": self.source_locations,
            "confidence": round(self.confidence, 4),
            "supporting_observations": self.supporting_observations,
            "contradicting_observations": self.contradicting_observations,
            "predicted_effect": self.predicted_effect,
            "timestamp": self.timestamp,
        }


@dataclass
class FilePatchDiff:
    """Represents a surgical, single-file code mutation."""
    relative_path: str
    original_content: str
    patched_content: str
    reason: str
    lines_added: int = 0
    lines_removed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "original_content": self.original_content,
            "patched_content": self.patched_content,
            "reason": self.reason,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
        }


@dataclass
class PatchMinimalityMetrics:
    """Quantifies the blast radius and syntactic footprint of a repair patch."""
    files_changed: int
    lines_added: int
    lines_removed: int
    symbols_changed: int
    dependencies_changed: int
    config_changed: bool
    behavioral_surface_changed: bool
    minimality_score: float = 1.0  # 1.0 is minimal surgical; lower means broader blast radius

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_changed": self.files_changed,
            "lines_added": self.lines_added,
            "lines_removed": self.lines_removed,
            "symbols_changed": self.symbols_changed,
            "dependencies_changed": self.dependencies_changed,
            "config_changed": self.config_changed,
            "behavioral_surface_changed": self.behavioral_surface_changed,
            "minimality_score": round(self.minimality_score, 4),
        }


@dataclass
class PredictedRepairImpact:
    """Ex-ante predictive analysis of changes triggered by a repair patch."""
    predicted_files: List[str] = field(default_factory=list)
    predicted_symbols: List[str] = field(default_factory=list)
    predicted_tasks: List[str] = field(default_factory=list)
    predicted_contracts: List[str] = field(default_factory=list)
    predicted_consumers: List[str] = field(default_factory=list)
    predicted_behavior_changes: List[str] = field(default_factory=list)
    predicted_risk: float = 0.1
    confidence: float = 0.9

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predicted_files": self.predicted_files,
            "predicted_symbols": self.predicted_symbols,
            "predicted_tasks": self.predicted_tasks,
            "predicted_contracts": self.predicted_contracts,
            "predicted_consumers": self.predicted_consumers,
            "predicted_behavior_changes": self.predicted_behavior_changes,
            "predicted_risk": round(self.predicted_risk, 4),
            "confidence": round(self.confidence, 4),
        }


@dataclass
class RepairCandidate:
    """A generated candidate repair with expected effect, risk, and rollback plan."""
    repair_id: str
    cause_id: str
    strategy_name: str
    files: List[str]
    patches: List[FilePatchDiff]
    expected_effect: str
    risk: float
    confidence: float
    predicted_impact: PredictedRepairImpact
    rollback_plan: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    minimality: Optional[PatchMinimalityMetrics] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repair_id": self.repair_id,
            "cause_id": self.cause_id,
            "strategy_name": self.strategy_name,
            "files": self.files,
            "patches": [p.to_dict() for p in self.patches],
            "expected_effect": self.expected_effect,
            "risk": round(self.risk, 4),
            "confidence": round(self.confidence, 4),
            "predicted_impact": self.predicted_impact.to_dict(),
            "rollback_plan": self.rollback_plan,
            "provenance": self.provenance,
            "minimality": self.minimality.to_dict() if self.minimality else None,
            "created_at": self.created_at,
        }


@dataclass
class RepairCandidateRanking:
    """Multi-criteria ranking evaluation of a repair candidate."""
    repair_id: str
    rank: int
    score: float
    confidence_score: float
    root_cause_support: float
    risk_penalty: float
    blast_radius_penalty: float
    minimality_bonus: float
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repair_id": self.repair_id,
            "rank": self.rank,
            "score": round(self.score, 4),
            "confidence_score": round(self.confidence_score, 4),
            "root_cause_support": round(self.root_cause_support, 4),
            "risk_penalty": round(self.risk_penalty, 4),
            "blast_radius_penalty": round(self.blast_radius_penalty, 4),
            "minimality_bonus": round(self.minimality_bonus, 4),
            "rationale": self.rationale,
        }


@dataclass
class Counterexample:
    """Concrete failing execution trace or input that invalidates a patch."""
    counterexample_id: str
    route_or_entry: str
    input_payload: Dict[str, Any]
    expected_output: Any
    observed_output: Any
    severity: str = "HIGH"
    is_shrunk: bool = False
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counterexample_id": self.counterexample_id,
            "route_or_entry": self.route_or_entry,
            "input_payload": self.input_payload,
            "expected_output": self.expected_output,
            "observed_output": self.observed_output,
            "severity": self.severity,
            "is_shrunk": self.is_shrunk,
            "details": self.details,
        }


@dataclass
class RepairProof:
    """Comprehensive, immutable audit contract proving the validity and boundaries of a repair."""
    proof_id: str
    repair_id: str
    failure_id: str
    root_cause: str
    patch_hash: str
    before_hash: str
    after_hash: str
    original_failure_resolved: FailureResolutionStatus
    preflight_passed: bool
    startup_passed: bool
    healthcheck_passed: bool
    behavior_result: str
    regression_result: str
    coverage: float
    counterexamples: List[Counterexample] = field(default_factory=list)
    invariants: List[str] = field(default_factory=list)
    rollback_verified: bool = False
    proof_result: RepairProofResult = RepairProofResult.INSUFFICIENT_EVIDENCE
    scope: str = "LOCAL_MODULE"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "repair_id": self.repair_id,
            "failure_id": self.failure_id,
            "root_cause": self.root_cause,
            "patch_hash": self.patch_hash,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "original_failure_resolved": self.original_failure_resolved.value if hasattr(self.original_failure_resolved, "value") else str(self.original_failure_resolved),
            "preflight_passed": self.preflight_passed,
            "startup_passed": self.startup_passed,
            "healthcheck_passed": self.healthcheck_passed,
            "behavior_result": self.behavior_result,
            "regression_result": self.regression_result,
            "coverage": round(self.coverage, 4),
            "counterexamples": [c.to_dict() for c in self.counterexamples],
            "invariants": self.invariants,
            "rollback_verified": self.rollback_verified,
            "proof_result": self.proof_result.value if hasattr(self.proof_result, "value") else str(self.proof_result),
            "scope": self.scope,
            "timestamp": self.timestamp,
        }
