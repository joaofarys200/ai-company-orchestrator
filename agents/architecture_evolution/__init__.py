"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Package: backend.agents.architecture_evolution
"""

from .alternatives import ArchitectureAlternativeGenerator
from .behavior import ArchitectureBehaviorAnalyzer
from .bridge import ArchitectureEvolutionBridge
from .cache import ArchitectureCache
from .comparison import ArchitectureComparator
from .constraints import ArchitectureConstraintExtractor
from .contracts import ArchitectureContractAnalyzer
from .cost import ArchitectureCostModel
from .governance import ArchitectureGovernanceEngine
from .impact import ArchitectureImpactAnalyzer
from .index import ArchitectureIndex
from .metrics import ArchitectureMetricsCollector
from .migration import ArchitectureMigrationPlanner
from .models import (
    AlternativeType,
    ArchitectureAlternative,
    ArchitectureComparisonResult,
    ArchitectureConstraint,
    ArchitectureGovernanceDecision,
    ArchitectureMigrationPlan,
    ArchitectureProblem,
    ArchitectureProvenanceRecord,
    ArchitectureSnapshot,
    BehaviorAnalysisResult,
    BehaviorPreservationStatus,
    ContractAnalysisResult,
    ContractBreakStatus,
    CostCategory,
    CostEstimationResult,
    CostObservationStatus,
    GovernanceDecisionState,
    ImpactAnalysisResult,
    ImpactScope,
    MigrationStep,
    MigrationStepType,
    ObservationStatus,
    ProblemCategory,
    ProblemSeverity,
    ReversibilityStatus,
    RiskAnalysisResult,
    RiskCriticality,
    SimulationResult,
    SimulationStatus,
    VerificationPlan,
)
from .observation import ArchitectureObserver
from .patterns import ARCHITECTURE_PATTERNS, convert_f63_to_architecture_hypothesis
from .persistence import ArchitecturePersistenceStore
from .policy import ArchitecturePolicy, ArchitecturePolicyManager
from .problem_detection import ArchitectureProblemDetector
from .provenance import ArchitectureProvenanceManager
from .risk import ArchitectureRiskAnalyzer
from .security import ArchitectureSecurityFilter
from .simulation import ArchitectureSimulator
from .validator import ArchitectureValidator
from .verification import ArchitectureVerificationPlanner

__all__ = [
    "ArchitectureEvolutionBridge",
    "ArchitectureSnapshot",
    "ArchitectureProblem",
    "ArchitectureConstraint",
    "ArchitectureAlternative",
    "ImpactAnalysisResult",
    "ContractAnalysisResult",
    "BehaviorAnalysisResult",
    "RiskAnalysisResult",
    "CostEstimationResult",
    "MigrationStep",
    "ArchitectureMigrationPlan",
    "SimulationResult",
    "VerificationPlan",
    "ArchitectureComparisonResult",
    "ArchitectureGovernanceDecision",
    "ArchitectureProvenanceRecord",
    "ProblemCategory",
    "ProblemSeverity",
    "ObservationStatus",
    "AlternativeType",
    "ImpactScope",
    "ContractBreakStatus",
    "BehaviorPreservationStatus",
    "RiskCriticality",
    "CostCategory",
    "CostObservationStatus",
    "ReversibilityStatus",
    "SimulationStatus",
    "GovernanceDecisionState",
    "MigrationStepType",
    "ArchitectureObserver",
    "ArchitectureProblemDetector",
    "ArchitectureConstraintExtractor",
    "ArchitectureAlternativeGenerator",
    "ArchitectureImpactAnalyzer",
    "ArchitectureContractAnalyzer",
    "ArchitectureBehaviorAnalyzer",
    "ArchitectureRiskAnalyzer",
    "ArchitectureCostModel",
    "ArchitectureMigrationPlanner",
    "ArchitectureSimulator",
    "ArchitectureVerificationPlanner",
    "ArchitectureComparator",
    "ArchitectureGovernanceEngine",
    "ArchitectureProvenanceManager",
    "ArchitectureSecurityFilter",
    "ArchitecturePolicy",
    "ArchitecturePolicyManager",
    "ArchitectureMetricsCollector",
    "ArchitectureCache",
    "ArchitecturePersistenceStore",
    "ArchitectureValidator",
    "ArchitectureIndex",
    "ARCHITECTURE_PATTERNS",
    "convert_f63_to_architecture_hypothesis",
]
