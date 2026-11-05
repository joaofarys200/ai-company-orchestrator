"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Package exports.
"""

from .adapters import (
    Phase73MacroRefactoringAdapter,
    Phase74ArchitecturalOptimizationAdapter,
    Phase75PortfolioOrchestrationAdapter,
    Phase76PredictiveCalibrationAdapter,
)
from .bridge import EvidenceGovernanceBridge
from .contradiction import ContradictionDetector
from .enforcement import GovernanceEnforcementEngine
from .freshness import EvidenceFreshnessMonitor
from .models import (
    AssuranceTier,
    ClaimType,
    ContradictionRecord,
    ContradictoryEvidenceError,
    EngineeringClaim,
    EvidenceArtifact,
    EvidenceCategory,
    EvidenceGovernanceError,
    EvidenceOriginType,
    InconclusiveEvidenceError,
    InvalidEvidenceIntegrityError,
    ReportAuditResult,
    StaleEvidenceError,
    UnauthorizedPromotionError,
    VerificationResult,
    VerificationStatus,
)
from .persistence import EvidenceGovernanceStore
from .provenance import EvidenceProvenanceValidator
from .registry import EvidenceClaimsRegistry
from .report_auditor import CompletionReportAuditor
from .verifier import ClaimToEvidenceVerifier

__all__ = [
    "EvidenceGovernanceBridge",
    "EvidenceClaimsRegistry",
    "EvidenceProvenanceValidator",
    "ClaimToEvidenceVerifier",
    "EvidenceFreshnessMonitor",
    "ContradictionDetector",
    "GovernanceEnforcementEngine",
    "CompletionReportAuditor",
    "EvidenceGovernanceStore",
    "Phase73MacroRefactoringAdapter",
    "Phase74ArchitecturalOptimizationAdapter",
    "Phase75PortfolioOrchestrationAdapter",
    "Phase76PredictiveCalibrationAdapter",
    "ClaimType",
    "EvidenceCategory",
    "EvidenceOriginType",
    "VerificationStatus",
    "AssuranceTier",
    "EvidenceArtifact",
    "EngineeringClaim",
    "VerificationResult",
    "ContradictionRecord",
    "ReportAuditResult",
    "EvidenceGovernanceError",
    "InvalidEvidenceIntegrityError",
    "ContradictoryEvidenceError",
    "StaleEvidenceError",
    "UnauthorizedPromotionError",
    "InconclusiveEvidenceError",
]
