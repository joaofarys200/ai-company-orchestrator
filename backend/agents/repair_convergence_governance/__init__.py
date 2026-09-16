"""
JARVIS OS — Phase 56: Autonomous Repair Termination & Convergence Governance
Exported interfaces and core package declarations.
"""

from agents.repair_convergence_governance.models import (
    AdaptiveBudgetConfig,
    CanaryResult,
    ConvergenceCertificate,
    ConvergenceState,
    ConvergenceVerdict,
    CycleReport,
    CycleType,
    DegradationReport,
    DivergenceReport,
    DivergenceScore,
    DivergenceType,
    EscalationStatus,
    EscalationTier,
    EscalationTicket,
    GovernanceLedgerEntry,
    OscillationReport,
    ProgressDelta,
    ProgressVector,
    RegressionReport,
    RepairStepSnapshot,
    ReversionReceipt,
    SideEffectReport,
    StallReport,
    StallType,
    TerminationBudget,
    TerminationEscalationReason,
    TerminationReason,
    TerminationState,
    compute_deterministic_hash,
    compute_vector_delta,
)
from agents.repair_convergence_governance.cycle_detector import CycleDetector
from agents.repair_convergence_governance.oscillation_detector import OscillationDetector
from agents.repair_convergence_governance.stall_detector import StallDetector
from agents.repair_convergence_governance.divergence_detector import DivergenceDetector
from agents.repair_convergence_governance.divergence_monitor import DivergenceMonitor
from agents.repair_convergence_governance.progress_tracker import ProgressVectorTracker
from agents.repair_convergence_governance.budget_manager import TerminationBudgetManager
from agents.repair_convergence_governance.escalation import HumanEscalationManager
from agents.repair_convergence_governance.certificate import ConvergenceCertificateEngine
from agents.repair_convergence_governance.ledger import ProgressLedger
from agents.repair_convergence_governance.replay import DeterministicReplayEngine
from agents.repair_convergence_governance.recovery import CrashRecoveryEngine
from agents.repair_convergence_governance.predictive import PredictiveConvergenceEngine
from agents.repair_convergence_governance.security import ConvergenceSecuritySentinel
from agents.repair_convergence_governance.experience import ConvergenceExperienceStore
from agents.repair_convergence_governance.proof import CompositeConvergenceProofEngine
from agents.repair_convergence_governance.telemetry import ConvergenceTelemetry
from agents.repair_convergence_governance.bridge import AutonomousRepairConvergenceBridge
from agents.repair_convergence_governance.cache import ConvergenceCache
from agents.repair_convergence_governance.index import ConvergenceLedgerIndex
from agents.repair_convergence_governance.canary_evaluator import CanaryEvaluator
from agents.repair_convergence_governance.degradation_detector import DegradationDetector
from agents.repair_convergence_governance.regression_detector import RegressionDetector
from agents.repair_convergence_governance.reversion_manager import ReversionManager
from agents.repair_convergence_governance.side_effect_detector import SideEffectDetector

__all__ = [
    "AdaptiveBudgetConfig",
    "AutonomousRepairConvergenceBridge",
    "CanaryEvaluator",
    "CanaryResult",
    "CompositeConvergenceProofEngine",
    "ConvergenceCache",
    "ConvergenceCertificate",
    "ConvergenceCertificateEngine",
    "ConvergenceExperienceStore",
    "ConvergenceLedgerIndex",
    "ConvergenceSecuritySentinel",
    "ConvergenceState",
    "ConvergenceTelemetry",
    "ConvergenceVerdict",
    "CrashRecoveryEngine",
    "CycleDetector",
    "CycleReport",
    "CycleType",
    "DegradationDetector",
    "DegradationReport",
    "DeterministicReplayEngine",
    "DivergenceDetector",
    "DivergenceMonitor",
    "DivergenceReport",
    "DivergenceScore",
    "DivergenceType",
    "EscalationStatus",
    "EscalationTier",
    "EscalationTicket",
    "GovernanceLedgerEntry",
    "HumanEscalationManager",
    "OscillationDetector",
    "OscillationReport",
    "PredictiveConvergenceEngine",
    "ProgressDelta",
    "ProgressLedger",
    "ProgressVector",
    "ProgressVectorTracker",
    "RegressionDetector",
    "RegressionReport",
    "RepairStepSnapshot",
    "ReversionManager",
    "ReversionReceipt",
    "SideEffectDetector",
    "SideEffectReport",
    "StallDetector",
    "StallReport",
    "StallType",
    "TerminationBudget",
    "TerminationBudgetManager",
    "TerminationEscalationReason",
    "TerminationReason",
    "TerminationState",
    "compute_deterministic_hash",
    "compute_vector_delta",
]
