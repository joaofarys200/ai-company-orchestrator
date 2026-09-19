"""
JARVIS OS — Phase 68: Engineering Quality Governance & Technical Debt Management
Package Index & Public Symbols
"""

from __future__ import annotations

from .architecture_quality import ArchitectureQualityEvaluator
from .baseline import QualityBaselineManager
from .behavior_quality import BehaviorQualityEvaluator
from .bridge import EngineeringQualityGovernanceBridge
from .cache import QualityEvaluationCache
from .code_quality import CodeQualityEvaluator
from .comparison import QualityRegressionDetector
from .contract_quality import ContractQualityEvaluator
from .debt_detection import TechnicalDebtDetector
from .debt_prioritization import DebtPrioritizer
from .maintainability import MaintainabilityQualityEvaluator
from .metrics import QualityMetricsEngine
from .models import (
    AgentQualityRecord,
    DebtCategory,
    DebtEvent,
    DebtSeverity,
    DebtStatus,
    DimensionChange,
    DimensionEvaluation,
    DimensionStatus,
    MissionQualityRecord,
    ObservationType,
    PriorityVector,
    QualityBudget,
    QualityDelta,
    QualityDimension,
    QualityGateDecision,
    QualityGateStatus,
    QualityHotspotItem,
    QualityObservation,
    QualityRegressionLevel,
    QualitySnapshot,
    QualityTrendDirection,
    TechnicalDebtItem,
)
from .performance_quality import PerformanceQualityEvaluator
from .persistence import QualityPersistenceStore
from .policy import (
    POLICIES,
    POLICY_CRITICAL_ONLY,
    POLICY_GOVERNED,
    POLICY_LENIENT,
    POLICY_STRICT,
    QualityPolicy,
    get_policy,
)
from .provenance import QualityProvenanceRegistry
from .quality_budget import QualityBudgetGovernor
from .quality_dimensions import QualityDimensionsOrchestrator
from .quality_gates import QualityGateEngine
from .reliability_quality import ReliabilityQualityEvaluator
from .security import QualityGovernanceSecurityViolation, QualitySecuritySentinel
from .security_quality import SecurityQualityEvaluator
from .test_quality import TestQualityEvaluator
from .trend import QualityTrendEngine
from .validator import QualityValidator

__all__ = [
    # Models & Enums
    "QualityDimension",
    "ObservationType",
    "DimensionChange",
    "DimensionStatus",
    "DebtCategory",
    "DebtStatus",
    "DebtSeverity",
    "QualityGateStatus",
    "QualityRegressionLevel",
    "QualityTrendDirection",
    "QualityObservation",
    "DimensionEvaluation",
    "QualitySnapshot",
    "QualityDelta",
    "TechnicalDebtItem",
    "DebtEvent",
    "PriorityVector",
    "QualityBudget",
    "QualityGateDecision",
    "QualityHotspotItem",
    "AgentQualityRecord",
    "MissionQualityRecord",
    # Core Evaluators & Managers
    "ArchitectureQualityEvaluator",
    "CodeQualityEvaluator",
    "TestQualityEvaluator",
    "ContractQualityEvaluator",
    "BehaviorQualityEvaluator",
    "SecurityQualityEvaluator",
    "PerformanceQualityEvaluator",
    "ReliabilityQualityEvaluator",
    "MaintainabilityQualityEvaluator",
    "QualityBaselineManager",
    "QualityDimensionsOrchestrator",
    "TechnicalDebtDetector",
    "DebtPrioritizer",
    "QualityBudgetGovernor",
    "QualityGateEngine",
    "QualityTrendEngine",
    "QualityRegressionDetector",
    "QualityProvenanceRegistry",
    "QualitySecuritySentinel",
    "QualityGovernanceSecurityViolation",
    "QualityMetricsEngine",
    "QualityEvaluationCache",
    "QualityPersistenceStore",
    "QualityValidator",
    "EngineeringQualityGovernanceBridge",
    # Policies
    "QualityPolicy",
    "POLICIES",
    "POLICY_STRICT",
    "POLICY_GOVERNED",
    "POLICY_LENIENT",
    "POLICY_CRITICAL_ONLY",
    "get_policy",
]
