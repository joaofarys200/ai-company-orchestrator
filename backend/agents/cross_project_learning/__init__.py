"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Package Initialization and Facade Exports.
"""

from .applicability import KnowledgeApplicabilityEngine
from .behavior import CrossProjectBehaviorAdapter
from .bridge import CrossProjectLearningBridge
from .cache import DeterministicTransferCache
from .conflicts import ConflictDetector
from .contracts import CrossProjectContractAdapter
from .index import KnowledgeReverseIndex
from .knowledge import KnowledgeManager
from .metrics import CrossProjectLearningMetrics
from .models import (
    ApplicabilityResult,
    ApplicabilityStatus,
    CandidateKnowledge,
    ConflictRecord,
    EngineeringKnowledgeItem,
    FeedbackOutcome,
    FreshnessState,
    HarmEvent,
    KnowledgeCategory,
    KnowledgeProvenance,
    KnowledgeState,
    KnowledgeTransferDecision,
    LocalValidationResult,
    ProjectFingerprint,
    TransferDecisionState,
    TransferPolicyName,
)
from .patterns import PatternLibrary
from .persistence import CrossProjectLearningStore
from .policy import PolicyProfile, PolicyRegistry
from .project_fingerprint import ProjectFingerprintExtractor
from .provenance import ProvenanceTracker
from .retrieval import HybridKnowledgeRetriever
from .risk import CrossProjectRiskAnalyzer
from .security import CrossProjectSecurityFilter
from .similarity import SimilarityEngine
from .tests import TestKnowledgeTransferEngine
from .validator import CrossProjectValidator
from .verification import VerificationKnowledgeTransferEngine

__all__ = [
    "ApplicabilityResult",
    "ApplicabilityStatus",
    "CandidateKnowledge",
    "ConflictDetector",
    "ConflictRecord",
    "CrossProjectBehaviorAdapter",
    "CrossProjectContractAdapter",
    "CrossProjectLearningBridge",
    "CrossProjectLearningMetrics",
    "CrossProjectLearningStore",
    "CrossProjectRiskAnalyzer",
    "CrossProjectSecurityFilter",
    "CrossProjectValidator",
    "DeterministicTransferCache",
    "EngineeringKnowledgeItem",
    "FeedbackOutcome",
    "FreshnessState",
    "HarmEvent",
    "HybridKnowledgeRetriever",
    "KnowledgeApplicabilityEngine",
    "KnowledgeCategory",
    "KnowledgeManager",
    "KnowledgeProvenance",
    "KnowledgeReverseIndex",
    "KnowledgeState",
    "KnowledgeTransferDecision",
    "LocalValidationResult",
    "PatternLibrary",
    "PolicyProfile",
    "PolicyRegistry",
    "ProjectFingerprint",
    "ProjectFingerprintExtractor",
    "ProvenanceTracker",
    "SimilarityEngine",
    "TestKnowledgeTransferEngine",
    "TransferDecisionState",
    "TransferPolicyName",
    "VerificationKnowledgeTransferEngine",
]
