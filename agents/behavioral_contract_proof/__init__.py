"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Public API and Canonical Module Exports.
"""

from agents.behavioral_contract_proof.baseline import (
    BaselineImmutableError,
    BaselineIntegrityError,
    BehaviorBaselineStore,
    compute_baseline_hash,
)
from agents.behavioral_contract_proof.behavior_model import (
    CANONICAL_STAGE_ORDER,
    BehavioralModelEngine,
)
from agents.behavioral_contract_proof.bridge import BehavioralContractProofBridge
from agents.behavioral_contract_proof.cache import BehaviorProofCache
from agents.behavioral_contract_proof.comparator import (
    BehaviorComparator,
    ComparisonResult,
)
from agents.behavioral_contract_proof.counterexample import CounterexampleGenerator
from agents.behavioral_contract_proof.index import BehavioralIndex
from agents.behavioral_contract_proof.invariants import (
    BehavioralInvariantEngine,
    InvariantEvaluationResult,
)
from agents.behavioral_contract_proof.metrics import (
    BehavioralProofTelemetry,
    BehavioralTelemetryEvent,
)
from agents.behavioral_contract_proof.migration import (
    BehavioralMigrationController,
    FinishGateStatus,
    RollbackRecord,
)
from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    BehavioralDelta,
    BehavioralInvariantType,
    BehavioralModel,
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
from agents.behavioral_contract_proof.normalizer import RuntimeTraceNormalizer
from agents.behavioral_contract_proof.proof import MigrationProofEngine
from agents.behavioral_contract_proof.security import (
    BehavioralSecuritySentinel,
    SecurityAuthDowngradeError,
    SecurityBaselineTamperedError,
    SecuritySecretLeakageError,
    SecurityTraceTamperedError,
)
from agents.behavioral_contract_proof.trace import (
    RuntimeTraceCollector,
    compute_trace_hash,
)
from agents.behavioral_contract_proof.validator import (
    BehavioralValidationError,
    BehavioralValidator,
)

__all__ = [
    # Models
    "BehaviorBaseline",
    "RuntimeTrace",
    "BehavioralModel",
    "Counterexample",
    "MigrationProof",
    "BehavioralDelta",
    "BehavioralStageExecution",
    "CompatibilityCategory",
    "EquivalenceLevel",
    "BehavioralInvariantType",
    "ProofResult",
    "ExecutionGateDecision",
    "LatencyClass",
    "BehavioralStage",
    # Baseline
    "BehaviorBaselineStore",
    "BaselineImmutableError",
    "BaselineIntegrityError",
    "compute_baseline_hash",
    # Behavior Model
    "BehavioralModelEngine",
    "CANONICAL_STAGE_ORDER",
    # Trace
    "RuntimeTraceCollector",
    "compute_trace_hash",
    # Normalizer
    "RuntimeTraceNormalizer",
    # Comparator
    "BehaviorComparator",
    "ComparisonResult",
    # Invariants
    "BehavioralInvariantEngine",
    "InvariantEvaluationResult",
    # Counterexample
    "CounterexampleGenerator",
    # Proof
    "MigrationProofEngine",
    # Migration
    "BehavioralMigrationController",
    "FinishGateStatus",
    "RollbackRecord",
    # Security
    "BehavioralSecuritySentinel",
    "SecurityBaselineTamperedError",
    "SecurityTraceTamperedError",
    "SecuritySecretLeakageError",
    "SecurityAuthDowngradeError",
    # Metrics
    "BehavioralProofTelemetry",
    "BehavioralTelemetryEvent",
    # Cache
    "BehaviorProofCache",
    # Bridge
    "BehavioralContractProofBridge",
    # Validator
    "BehavioralValidator",
    "BehavioralValidationError",
    # Index
    "BehavioralIndex",
]
