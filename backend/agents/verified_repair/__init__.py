"""
JARVIS OS — Phase 54: Verified Repair Synthesis & Patch Validation
Public package exports.
"""

from agents.verified_repair.bridge import VerifiedRepairBridge
from agents.verified_repair.cache import RepairExperienceCache
from agents.verified_repair.candidate import RepairCandidateGenerator
from agents.verified_repair.cause import RootCauseEngine
from agents.verified_repair.impact import PatchImpactAnalyzer
from agents.verified_repair.index import VerifiedRepairIndex
from agents.verified_repair.metrics import RepairTelemetry
from agents.verified_repair.minimality import PatchMinimalityEvaluator
from agents.verified_repair.models import (
    Counterexample,
    FailureResolutionStatus,
    FilePatchDiff,
    PatchMinimalityMetrics,
    PredictedRepairImpact,
    RepairCandidate,
    RepairCandidateRanking,
    RepairConfidenceLevel,
    RepairProof,
    RepairProofResult,
    RootCauseCategory,
    RootCauseHypothesis,
    compute_deterministic_hash,
)
from agents.verified_repair.patch import PatchManager
from agents.verified_repair.proof import RepairProofEngine
from agents.verified_repair.ranking import RepairRankingEngine
from agents.verified_repair.regression import RegressionProofEngine
from agents.verified_repair.rollback import RepairRollbackEngine
from agents.verified_repair.security import RepairSecuritySentinel
from agents.verified_repair.synthesizer import RepairCodeSynthesizer
from agents.verified_repair.validator import FailureResolutionVerifier

__all__ = [
    "VerifiedRepairBridge",
    "RootCauseEngine",
    "RepairCandidateGenerator",
    "RepairRankingEngine",
    "PatchImpactAnalyzer",
    "PatchManager",
    "PatchMinimalityEvaluator",
    "FailureResolutionVerifier",
    "RegressionProofEngine",
    "RepairProofEngine",
    "RepairRollbackEngine",
    "RepairSecuritySentinel",
    "RepairCodeSynthesizer",
    "RepairTelemetry",
    "RepairExperienceCache",
    "VerifiedRepairIndex",
    "RootCauseCategory",
    "FailureResolutionStatus",
    "RepairProofResult",
    "RepairConfidenceLevel",
    "RootCauseHypothesis",
    "FilePatchDiff",
    "PatchMinimalityMetrics",
    "PredictedRepairImpact",
    "RepairCandidate",
    "RepairCandidateRanking",
    "Counterexample",
    "RepairProof",
    "compute_deterministic_hash",
]
