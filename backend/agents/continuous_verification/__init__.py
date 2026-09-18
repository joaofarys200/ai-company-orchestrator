"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Package Initialization
"""

from .baseline import BaselineStore
from .bridge import ContinuousVerificationBridge
from .cache import VerificationCache
from .change_detection import ChangeDetector
from .counterexample import CounterexamplePromotionManager
from .coverage import MultidimensionalCoverageEvaluator
from .evidence import VerificationEvidenceLedger
from .executor import ContinuousTestExecutor, ExecutionResultItem
from .flaky import FlakyTestDetector
from .impact import ImpactToVerificationPlanner
from .index import VerificationIndex
from .metrics import ContinuousVerificationMetrics
from .models import (
    BaselineSnapshot,
    ChangeItem,
    ChangeSet,
    ChangeSource,
    ChangeType,
    CoverageVector,
    FlakyAnalysisResult,
    FlakyStatus,
    RegressionClassification,
    RegressionComparisonResult,
    SelectedTestItem,
    TestSelectionPlan,
    TestSelectionPriority,
    VerificationDecision,
    VerificationDecisionOutcome,
    VerificationPolicy,
    VerificationPolicyName,
    VerificationState,
    VerificationSurface,
)
from .persistence import VerificationPersistenceStore
from .planner import ContinuousVerificationPlanner, VerificationPlan
from .policy import VerificationPolicyEngine
from .security import VerificationSecuritySentinel
from .selector import ContinuousTestSelector
from .synthesis_bridge import ContinuousSynthesisBridge
from .validator import VerificationDecisionValidator

__all__ = [
    "ContinuousVerificationBridge",
    "ChangeDetector",
    "ChangeItem",
    "ChangeSet",
    "ChangeType",
    "ChangeSource",
    "VerificationSurface",
    "VerificationState",
    "TestSelectionPriority",
    "SelectedTestItem",
    "TestSelectionPlan",
    "CoverageVector",
    "BaselineSnapshot",
    "BaselineStore",
    "RegressionClassification",
    "RegressionComparisonResult",
    "FlakyStatus",
    "FlakyAnalysisResult",
    "FlakyTestDetector",
    "CounterexamplePromotionManager",
    "VerificationDecisionOutcome",
    "VerificationDecision",
    "VerificationDecisionValidator",
    "VerificationPolicyName",
    "VerificationPolicy",
    "VerificationPolicyEngine",
    "ContinuousVerificationPlanner",
    "VerificationPlan",
    "ContinuousTestSelector",
    "ContinuousSynthesisBridge",
    "ContinuousTestExecutor",
    "ExecutionResultItem",
    "MultidimensionalCoverageEvaluator",
    "RegressionComparator",
    "VerificationEvidenceLedger",
    "VerificationSecuritySentinel",
    "VerificationCache",
    "VerificationPersistenceStore",
    "VerificationIndex",
    "ContinuousVerificationMetrics",
]
