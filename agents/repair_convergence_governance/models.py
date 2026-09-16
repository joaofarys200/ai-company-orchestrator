"""
JARVIS OS — Phase 56: Autonomous Repair Termination & Convergence Governance
Core domain models, formal states, progress vectors, cryptographic certificates, and ledgers.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


def compute_deterministic_hash(data: Any) -> str:
    """Computes a stable SHA-256 hash over arbitrary structured data."""
    if isinstance(data, (dict, list)):
        payload = json.dumps(data, sort_keys=True, default=str)
    else:
        payload = str(data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class TerminationState(str, Enum):
    INITIAL = "INITIAL"
    PLANNING = "PLANNING"
    CONVERGING = "CONVERGING"
    STABLE = "STABLE"
    STALLED = "STALLED"
    DIVERGING = "DIVERGING"
    OSCILLATING = "OSCILLATING"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    ROLLED_BACK = "ROLLED_BACK"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class TerminationReason(str, Enum):
    CONVERGED_VERIFIED = "CONVERGED_VERIFIED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    OSCILLATION_DETECTED = "OSCILLATION_DETECTED"
    STALL_DETECTED = "STALL_DETECTED"
    DIVERGENCE_DETECTED = "DIVERGENCE_DETECTED"
    SECURITY_SENTINEL_HALT = "SECURITY_SENTINEL_HALT"
    HUMAN_INTERVENTION_REQUIRED = "HUMAN_INTERVENTION_REQUIRED"
    MANUAL_TERMINATION = "MANUAL_TERMINATION"


class ConvergenceVerdict(str, Enum):
    CONVERGED = "CONVERGED"
    STALLED = "STALLED"
    DIVERGED = "DIVERGED"
    CYCLING = "CYCLING"
    OSCILLATING = "OSCILLATING"
    IN_PROGRESS = "IN_PROGRESS"
    SECURITY_HALTED = "SECURITY_HALTED"
    ESCALATED = "ESCALATED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class TerminationEscalationReason(str, Enum):
    REPEATED_FAILURE = "REPEATED_FAILURE"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    RISK_THRESHOLD = "RISK_THRESHOLD"
    INSUFFICIENT_PROGRESS = "INSUFFICIENT_PROGRESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
    ECONOMIC_RISK = "ECONOMIC_RISK"
    SECURITY_RISK = "SECURITY_RISK"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class StallType(str, Enum):
    PROGRESS_METRIC_ZERO = "PROGRESS_METRIC_ZERO"
    FAILURE_COUNT_UNCHANGED = "FAILURE_COUNT_UNCHANGED"
    MUTATION_PLATEAU = "MUTATION_PLATEAU"
    REPAIR_ATTEMPT_REPETITION = "REPAIR_ATTEMPT_REPETITION"
    COVERAGE_STAGNATION = "COVERAGE_STAGNATION"
    RISK_STAGNATION = "RISK_STAGNATION"


class CycleType(str, Enum):
    EXACT_STATE_CYCLE = "EXACT_STATE_CYCLE"
    PING_PONG_FAILURE_CYCLE = "PING_PONG_FAILURE_CYCLE"
    SUBSET_OSCILLATION_CYCLE = "SUBSET_OSCILLATION_CYCLE"
    PATCH_REGRESSION_CYCLE = "PATCH_REGRESSION_CYCLE"
    REPEATED_REPAIR_CYCLE = "REPEATED_REPAIR_CYCLE"


class DivergenceType(str, Enum):
    FAILURE_COUNT_EXPLOSION = "FAILURE_COUNT_EXPLOSION"
    REGRESSION_CASCADE = "REGRESSION_CASCADE"
    UNBOUNDED_COMPLEXITY = "UNBOUNDED_COMPLEXITY"
    ENTROPY_EXPANSION = "ENTROPY_EXPANSION"
    RISK_SPIKE = "RISK_SPIKE"
    BLAST_RADIUS_EXPANSION = "BLAST_RADIUS_EXPANSION"


class EscalationTier(str, Enum):
    TIER_1_AUTO_ASSIST = "TIER_1_AUTO_ASSIST"
    TIER_2_DEVELOPER_REVIEW = "TIER_2_DEVELOPER_REVIEW"
    TIER_3_SECURITY_LEAD = "TIER_3_SECURITY_LEAD"
    TIER_4_HUMAN_IN_THE_LOOP = "TIER_4_HUMAN_IN_THE_LOOP"


class EscalationStatus(str, Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"
    TIMED_OUT = "TIMED_OUT"


@dataclass
class ProgressVector:
    """Multidimensional progress metric vector P."""
    resolved_failures: int = 0
    new_failures: int = 0
    blocking_failures: int = 0
    coverage_gain: float = 0.0
    risk_reduction: float = 0.0
    uncertainty_reduction: float = 0.0
    proof_progress: float = 0.0
    repair_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_tuple(self) -> Tuple[float, ...]:
        return (
            float(self.resolved_failures),
            float(self.new_failures),
            float(self.blocking_failures),
            round(self.coverage_gain, 4),
            round(self.risk_reduction, 4),
            round(self.uncertainty_reduction, 4),
            round(self.proof_progress, 4),
            round(self.repair_cost, 4),
        )


@dataclass
class ProgressDelta:
    """Difference vector Delta P between consecutive states."""
    resolved_delta: int = 0
    new_delta: int = 0
    blocking_delta: int = 0
    coverage_delta: float = 0.0
    risk_delta: float = 0.0
    uncertainty_delta: float = 0.0
    proof_delta: float = 0.0
    cost_delta: float = 0.0
    score: float = 0.0
    is_positive: bool = False

    def __post_init__(self):
        # Progress score weighting:
        # +3 per resolved failure, -4 per new failure, -6 per blocking failure
        # +10 * coverage_delta, +15 * risk_delta, +5 * uncertainty_delta, +10 * proof_delta, -0.5 * cost_delta
        if self.score == 0.0:
            raw_score = (
                (self.resolved_delta * 3.0)
                - (self.new_delta * 4.0)
                - (self.blocking_delta * 6.0)
                + (self.coverage_delta * 10.0)
                + (self.risk_delta * 15.0)
                + (self.uncertainty_delta * 5.0)
                + (self.proof_delta * 10.0)
                - (self.cost_delta * 0.5)
            )
            self.score = round(raw_score, 4)
            self.is_positive = self.score > 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_vector_delta(p_before: ProgressVector, p_after: ProgressVector) -> ProgressDelta:
    """Computes delta P = p_after - p_before."""
    return ProgressDelta(
        resolved_delta=p_after.resolved_failures - p_before.resolved_failures,
        new_delta=p_after.new_failures - p_before.new_failures,
        blocking_delta=p_after.blocking_failures - p_before.blocking_failures,
        coverage_delta=round(p_after.coverage_gain - p_before.coverage_gain, 4),
        risk_delta=round(p_after.risk_reduction - p_before.risk_reduction, 4),
        uncertainty_delta=round(p_after.uncertainty_reduction - p_before.uncertainty_reduction, 4),
        proof_delta=round(p_after.proof_progress - p_before.proof_progress, 4),
        cost_delta=round(p_after.repair_cost - p_before.repair_cost, 4),
    )


@dataclass
class RepairStepSnapshot:
    """Snapshot of system state at a specific repair iteration."""
    iteration_id: int
    timestamp: float
    active_failures: List[str] = field(default_factory=list)
    fixed_failures: List[str] = field(default_factory=list)
    newly_introduced_failures: List[str] = field(default_factory=list)
    patches_applied: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    test_pass_rate: float = 0.0
    behavioral_proof_coverage: float = 0.0
    code_entropy: float = 0.0
    risk_score: float = 0.0
    latency_ms: float = 0.0
    memory_mb: float = 0.0
    cyclomatic_complexity: float = 0.0
    error_signatures: List[str] = field(default_factory=list)
    tests_failed: int = 0
    step_id: int = 0
    state_hash: str = ""

    def __post_init__(self):
        if self.step_id == 0:
            self.step_id = self.iteration_id
        if self.tests_failed == 0 and self.active_failures:
            self.tests_failed = len(self.active_failures)
        if not self.state_hash:
            self.state_hash = compute_deterministic_hash({
                "iteration": self.iteration_id,
                "active_failures": sorted(self.active_failures),
                "fixed_failures": sorted(self.fixed_failures),
                "new_failures": sorted(self.newly_introduced_failures),
                "patches": sorted(self.patches_applied),
                "files": sorted(self.modified_files),
                "pass_rate": round(self.test_pass_rate, 4),
                "entropy": round(self.code_entropy, 4),
                "risk": round(self.risk_score, 4)
            })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConvergenceState:
    """Aggregate state of a repair transaction."""
    state: TerminationState
    iteration: int
    failure_count: int
    blocking_failure_count: int
    risk_score: float
    coverage: float
    uncertainty: float
    proof_status: str
    repair_count: int
    revealed_failures: List[str] = field(default_factory=list)
    regressions: List[str] = field(default_factory=list)
    rollback_count: int = 0
    cycle_count: int = 0
    state_hash: str = ""
    previous_state_hash: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if not self.state_hash:
            self.state_hash = compute_deterministic_hash({
                "state": self.state.value,
                "iteration": self.iteration,
                "failure_count": self.failure_count,
                "blocking": self.blocking_failure_count,
                "risk": round(self.risk_score, 4),
                "coverage": round(self.coverage, 4),
                "proof_status": self.proof_status,
                "repair_count": self.repair_count,
                "rollback_count": self.rollback_count,
                "previous_hash": self.previous_state_hash
            })

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["state"] = self.state.value
        return res


@dataclass
class DivergenceScore:
    """Explicitly decomposed divergence metrics."""
    risk_growth: float = 0.0
    failure_growth: float = 0.0
    coverage_drop: float = 0.0
    regression_growth: float = 0.0
    rollback_rate: float = 0.0
    total_score: float = 0.0
    is_diverging: bool = False
    reasons: List[str] = field(default_factory=list)

    def compute_total(self, threshold: float = 1.0) -> float:
        self.total_score = round(
            (self.risk_growth * 0.30)
            + (self.failure_growth * 0.25)
            + (self.coverage_drop * 0.20)
            + (self.regression_growth * 0.15)
            + (self.rollback_rate * 0.10),
            4
        )
        self.is_diverging = self.total_score >= threshold
        return self.total_score

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TerminationBudget:
    """Enforceable bounded computational and operational bounds."""
    max_repairs: int = 25
    max_cycles: int = 2
    max_runtime: float = 300.0
    max_rollbacks: int = 3
    max_revealed_failures: int = 5
    max_risk: float = 0.85
    max_transaction_depth: int = 15
    consumed_repairs: int = 0
    consumed_cycles: int = 0
    consumed_runtime: float = 0.0
    consumed_rollbacks: int = 0
    consumed_revealed_failures: int = 0
    current_risk: float = 0.0
    current_depth: int = 0
    is_exhausted: bool = False
    exhausted_reasons: List[str] = field(default_factory=list)

    def consume(
        self,
        repairs: int = 0,
        cycles: int = 0,
        runtime_sec: float = 0.0,
        rollbacks: int = 0,
        revealed: int = 0,
        risk: float = 0.0,
        depth: int = 0,
    ) -> bool:
        self.consumed_repairs += repairs
        self.consumed_cycles += cycles
        self.consumed_runtime += runtime_sec
        self.consumed_rollbacks += rollbacks
        self.consumed_revealed_failures += revealed
        if risk > 0.0:
            self.current_risk = risk
        if depth > 0:
            self.current_depth = depth

        exhausted = []
        if self.consumed_repairs >= self.max_repairs:
            exhausted.append("max_repairs")
        if self.consumed_cycles > self.max_cycles:
            exhausted.append("max_cycles")
        if self.consumed_runtime >= self.max_runtime:
            exhausted.append("max_runtime")
        if self.consumed_rollbacks >= self.max_rollbacks:
            exhausted.append("max_rollbacks")
        if self.consumed_revealed_failures > self.max_revealed_failures:
            exhausted.append("max_revealed_failures")
        if self.current_risk >= self.max_risk:
            exhausted.append("max_risk")
        if self.current_depth >= self.max_transaction_depth:
            exhausted.append("max_transaction_depth")

        if exhausted:
            self.is_exhausted = True
            self.exhausted_reasons = exhausted
            return True
        return False

    def remaining_percentage(self) -> float:
        ratios = [
            1.0 - (self.consumed_repairs / max(1, self.max_repairs)),
            1.0 - (self.consumed_runtime / max(1.0, self.max_runtime)),
            1.0 - (self.consumed_rollbacks / max(1, self.max_rollbacks)),
        ]
        return max(0.0, min(100.0, min(ratios) * 100.0))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AdaptiveBudgetConfig:
    """Configures adaptive scaling of budget limits conditioned on risk."""
    risk_scale_factor: float = 0.5
    security_max_repairs_cap: int = 50
    security_max_runtime_cap: float = 600.0


@dataclass
class CycleReport:
    """Detailed report on detected cycle patterns."""
    cycle_detected: bool
    cycle_type: Optional[CycleType] = None
    cycle_period: int = 0
    repeating_states: List[str] = field(default_factory=list)
    repeating_failures: List[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.cycle_type:
            res["cycle_type"] = self.cycle_type.value
        return res


@dataclass
class OscillationReport:
    """Report on alternating failure patterns and ping-pong state bouncing."""
    oscillating: bool
    cycle_length: int = 0
    cycle_states: List[int] = field(default_factory=list)
    repeating_signatures: List[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StallReport:
    """Report on repair stagnation."""
    stalled: bool
    stall_type: Optional[StallType] = None
    consecutive_stagnant_iterations: int = 0
    metric_delta: float = 0.0
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.stall_type:
            res["stall_type"] = self.stall_type.value
        return res


@dataclass
class DivergenceReport:
    """Report on repair divergence or failure cascades."""
    diverging: bool
    divergence_type: Optional[DivergenceType] = None
    failure_count_trend: List[int] = field(default_factory=list)
    divergence_velocity: float = 0.0
    regressed_failures: List[str] = field(default_factory=list)
    blast_radius_files: List[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        if self.divergence_type:
            res["divergence_type"] = self.divergence_type.value
        return res


@dataclass
class RegressionReport:
    """Report on reintroduced or newly introduced bugs."""
    regressed: bool
    reintroduced_failures: List[str] = field(default_factory=list)
    new_failures: List[str] = field(default_factory=list)
    regression_severity: str = "NONE"
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DegradationReport:
    """Report on secondary system attributes degradation."""
    degraded: bool
    degraded_metrics: Dict[str, float] = field(default_factory=dict)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SideEffectReport:
    """Report on unauthorized or out-of-perimeter modifications."""
    has_side_effects: bool
    unintended_files: List[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanaryResult:
    """Result of sandboxed canary validation probe."""
    canary_passed: bool
    latency_ms: float = 0.0
    error_rate: float = 0.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReversionReceipt:
    """Cryptographic receipt of rollback operation."""
    reversion_id: str
    target_checkpoint_id: str
    trigger_reason: TerminationReason
    timestamp: float
    step_reverted_from: int
    restored_files: List[str]
    success: bool
    details: str

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["trigger_reason"] = self.trigger_reason.value
        return res


@dataclass
class EscalationTicket:
    """Ticket dispatched for human intervention or lead review."""
    ticket_id: str
    tier: EscalationTier
    status: EscalationStatus
    created_at: float
    mission_id: str
    repair_plan_id: str
    reason: str
    context_summary: Dict[str, Any]
    suggested_resolutions: List[str]
    assigned_to: Optional[str] = None
    resolved_at: Optional[float] = None
    resolution_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["tier"] = self.tier.value
        res["status"] = self.status.value
        return res


@dataclass
class ConvergenceCertificate:
    """Cryptographically signed formal certificate issued upon repair termination."""
    certificate_id: str
    mission_id: str
    transaction_id: str
    termination_reason: TerminationReason
    convergence_verdict: ConvergenceVerdict
    initial_state_hash: str
    final_state_hash: str
    repair_sequence: List[str]
    progress_history: List[Dict[str, Any]]
    risk_history: List[float]
    coverage_history: List[float]
    proof_history: List[str]
    cycles_detected: int
    rollbacks_count: int
    human_review_required: bool
    budget_summary: Dict[str, Any]
    total_iterations: int
    total_duration_seconds: float
    security_sentinel_approved: bool
    signature: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.signature:
            reason_str = self.termination_reason.value if hasattr(self.termination_reason, "value") else str(self.termination_reason)
            verdict_str = self.convergence_verdict.value if hasattr(self.convergence_verdict, "value") else str(self.convergence_verdict)
            payload = {
                "id": self.certificate_id,
                "mission_id": self.mission_id,
                "transaction_id": self.transaction_id,
                "reason": reason_str,
                "verdict": verdict_str,
                "initial_hash": self.initial_state_hash,
                "final_hash": self.final_state_hash,
                "repairs": sorted(self.repair_sequence),
                "iterations": self.total_iterations,
                "sentinel": self.security_sentinel_approved,
            }
            self.signature = "CERT_SIG_" + compute_deterministic_hash(payload)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["termination_reason"] = self.termination_reason.value if hasattr(self.termination_reason, "value") else str(self.termination_reason)
        res["convergence_verdict"] = self.convergence_verdict.value if hasattr(self.convergence_verdict, "value") else str(self.convergence_verdict)
        return res


@dataclass
class GovernanceLedgerEntry:
    """Append-only tamper-evident ledger entry."""
    entry_id: str
    sequence: int
    timestamp: float
    event_type: str
    payload: Dict[str, Any]
    previous_hash: str
    entry_hash: str = ""

    def __post_init__(self):
        if not self.entry_hash:
            data = {
                "entry_id": self.entry_id,
                "sequence": self.sequence,
                "timestamp": self.timestamp,
                "event_type": self.event_type,
                "payload": self.payload,
                "previous_hash": self.previous_hash
            }
            self.entry_hash = compute_deterministic_hash(data)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
