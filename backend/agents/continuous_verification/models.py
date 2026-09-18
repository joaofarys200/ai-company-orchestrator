"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Domain Models and Core Enums
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set


class ChangeType(str, Enum):
    CREATED = "CREATED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    SYMBOL_ADDED = "SYMBOL_ADDED"
    SYMBOL_CHANGED = "SYMBOL_CHANGED"
    SYMBOL_REMOVED = "SYMBOL_REMOVED"
    CONTRACT_CHANGED = "CONTRACT_CHANGED"
    TEST_CHANGED = "TEST_CHANGED"


class ChangeSource(str, Enum):
    GIT = "GIT"
    RUNTIME_MISSION = "RUNTIME_MISSION"
    REPAIR_RESULT = "REPAIR_RESULT"
    AUTONOMOUS_MODIFICATION = "AUTONOMOUS_MODIFICATION"
    WORKSPACE_MODIFICATION = "WORKSPACE_MODIFICATION"


@dataclass
class ChangeItem:
    file_path: str
    symbol_id: Optional[str] = None
    change_type: ChangeType = ChangeType.MODIFIED
    before_hash: str = ""
    after_hash: str = ""
    diff_metadata: Dict[str, Any] = field(default_factory=dict)
    source: ChangeSource = ChangeSource.WORKSPACE_MODIFICATION
    logical_timestamp: int = 0
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "symbol_id": self.symbol_id,
            "change_type": self.change_type.value if hasattr(self.change_type, "value") else str(self.change_type),
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "diff_metadata": self.diff_metadata,
            "source": self.source.value if hasattr(self.source, "value") else str(self.source),
            "logical_timestamp": self.logical_timestamp,
            "confidence": self.confidence,
        }


@dataclass
class ChangeSet:
    id: str
    changes: List[ChangeItem] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    source: str = "workspace"

    @property
    def total_files(self) -> int:
        return len({c.file_path for c in self.changes})

    @property
    def total_symbols(self) -> int:
        return len({c.symbol_id for c in self.changes if c.symbol_id})

    def deterministic_hash(self) -> str:
        serialized = json.dumps(
            [c.to_dict() for c in sorted(self.changes, key=lambda x: (x.file_path, x.symbol_id or "", str(x.change_type)))],
            sort_keys=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "deterministic_hash": self.deterministic_hash(),
            "total_files": self.total_files,
            "total_symbols": self.total_symbols,
            "timestamp": self.timestamp,
            "source": self.source,
            "changes": [c.to_dict() for c in self.changes],
        }


@dataclass
class VerificationSurface:
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    affected_contracts: List[str] = field(default_factory=list)
    affected_behaviors: List[str] = field(default_factory=list)
    affected_consumers: List[str] = field(default_factory=list)
    browser_surfaces: List[str] = field(default_factory=list)
    risk_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    uncertainty: float = 0.0  # 0.0 to 1.0
    dynamic_boundaries: List[str] = field(default_factory=list)
    scc_clusters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "affected_files": self.affected_files,
            "affected_symbols": self.affected_symbols,
            "affected_tests": self.affected_tests,
            "affected_contracts": self.affected_contracts,
            "affected_behaviors": self.affected_behaviors,
            "affected_consumers": self.affected_consumers,
            "browser_surfaces": self.browser_surfaces,
            "risk_level": self.risk_level,
            "uncertainty": self.uncertainty,
            "dynamic_boundaries": self.dynamic_boundaries,
            "scc_clusters": self.scc_clusters,
        }


class VerificationState(str, Enum):
    INITIAL = "INITIAL"
    CHANGE_DETECTED = "CHANGE_DETECTED"
    IMPACT_ANALYSIS = "IMPACT_ANALYSIS"
    PLANNING = "PLANNING"
    SELECTING = "SELECTING"
    SYNTHESIZING = "SYNTHESIZING"
    VALIDATING_TESTS = "VALIDATING_TESTS"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    COVERAGE = "COVERAGE"
    COMPARING = "COMPARING"
    FLAKY_ANALYSIS = "FLAKY_ANALYSIS"
    EVIDENCE_BUILDING = "EVIDENCE_BUILDING"
    VERIFIED_WITHIN_SCOPE = "VERIFIED_WITHIN_SCOPE"
    REGRESSION_FOUND = "REGRESSION_FOUND"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    FINISHED = "FINISHED"


class TestSelectionPriority(int, Enum):
    KNOWN_FAILURE_REGRESSION = 1
    DIRECTLY_AFFECTED_SYMBOL = 2
    DIRECT_CONSUMER = 3
    CONTRACT = 4
    BEHAVIORAL = 5
    HIGH_RISK = 6
    BROWSER = 7
    BROADER_REGRESSION = 8


@dataclass
class SelectedTestItem:
    __test__ = False  # Prevent pytest collection warning
    test_id: str
    priority: TestSelectionPriority
    reason: str
    is_synthesized: bool = False
    framework: str = "pytest"
    file_path: Optional[str] = None
    symbol_id: Optional[str] = None
    estimated_cost_ms: float = 10.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "priority": int(self.priority),
            "priority_name": self.priority.name,
            "reason": self.reason,
            "is_synthesized": self.is_synthesized,
            "framework": self.framework,
            "file_path": self.file_path,
            "symbol_id": self.symbol_id,
            "estimated_cost_ms": self.estimated_cost_ms,
        }


@dataclass
class TestSelectionPlan:
    __test__ = False  # Prevent pytest collection warning
    selected: List[SelectedTestItem] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    deferred: List[str] = field(default_factory=list)
    required_but_missing: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_selected(self) -> int:
        return len(self.selected)

    @property
    def total_skipped(self) -> int:
        return len(self.skipped)

    @property
    def total_deferred(self) -> int:
        return len(self.deferred)

    @property
    def total_missing(self) -> int:
        return len(self.required_but_missing)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected": [s.to_dict() for s in self.selected],
            "skipped": self.skipped,
            "deferred": self.deferred,
            "required_but_missing": self.required_but_missing,
            "total_selected": len(self.selected),
            "total_skipped": len(self.skipped),
            "total_deferred": len(self.deferred),
            "total_missing": len(self.required_but_missing),
        }


@dataclass
class CoverageVector:
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    symbol_coverage: float = 0.0
    contract_coverage: float = 0.0
    behavior_coverage: float = 0.0
    invariant_coverage: float = 0.0
    consumer_coverage: float = 0.0
    browser_coverage: float = 0.0
    mutation_coverage: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "line_coverage": round(self.line_coverage, 4),
            "branch_coverage": round(self.branch_coverage, 4),
            "symbol_coverage": round(self.symbol_coverage, 4),
            "contract_coverage": round(self.contract_coverage, 4),
            "behavior_coverage": round(self.behavior_coverage, 4),
            "invariant_coverage": round(self.invariant_coverage, 4),
            "consumer_coverage": round(self.consumer_coverage, 4),
            "browser_coverage": round(self.browser_coverage, 4),
            "mutation_coverage": round(self.mutation_coverage, 4),
        }


@dataclass
class BaselineSnapshot:
    snapshot_id: str
    version_id: str
    timestamp: float
    test_results: Dict[str, Any] = field(default_factory=dict)
    coverage_vector: CoverageVector = field(default_factory=CoverageVector)
    mutation_data: Dict[str, Any] = field(default_factory=dict)
    regression_state: str = "STABLE"
    flaky_status: Dict[str, Any] = field(default_factory=dict)
    execution_duration: float = 0.0
    evidence_hashes: List[str] = field(default_factory=list)
    environment_metadata: Dict[str, Any] = field(default_factory=dict)
    immutable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "version_id": self.version_id,
            "timestamp": self.timestamp,
            "test_results": self.test_results,
            "coverage_vector": self.coverage_vector.to_dict(),
            "mutation_data": self.mutation_data,
            "regression_state": self.regression_state,
            "flaky_status": self.flaky_status,
            "execution_duration": self.execution_duration,
            "evidence_hashes": self.evidence_hashes,
            "environment_metadata": self.environment_metadata,
            "immutable": self.immutable,
        }


class RegressionClassification(str, Enum):
    NO_REGRESSION = "NO_REGRESSION"
    REGRESSION = "REGRESSION"
    IMPROVEMENT = "IMPROVEMENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    ENVIRONMENTAL_FAILURE = "ENVIRONMENTAL_FAILURE"
    FLAKY_SIGNAL = "FLAKY_SIGNAL"


@dataclass
class RegressionComparisonResult:
    classification: RegressionClassification
    dimensions_evaluated: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    regressed_items: List[str] = field(default_factory=list)
    improved_items: List[str] = field(default_factory=list)
    explanation: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification.value if hasattr(self.classification, "value") else str(self.classification),
            "dimensions_evaluated": self.dimensions_evaluated,
            "regressed_items": self.regressed_items,
            "improved_items": self.improved_items,
            "explanation": self.explanation,
            "confidence": self.confidence,
        }


class FlakyStatus(str, Enum):
    STABLE_PASS = "STABLE_PASS"
    STABLE_FAIL = "STABLE_FAIL"
    FLAKY = "FLAKY"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class FlakyAnalysisResult:
    __test__ = False  # Prevent pytest collection warning
    test_id: str
    status: FlakyStatus
    attempts: int
    outcomes: List[str] = field(default_factory=list)
    timing_variance: float = 0.0
    environment_variance: float = 0.0
    failure_fingerprints: List[str] = field(default_factory=list)
    review_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "attempts": self.attempts,
            "outcomes": self.outcomes,
            "timing_variance": self.timing_variance,
            "environment_variance": self.environment_variance,
            "failure_fingerprints": self.failure_fingerprints,
            "review_required": self.review_required,
        }


class VerificationDecisionOutcome(str, Enum):
    VERIFIED_WITHIN_SCOPE = "VERIFIED_WITHIN_SCOPE"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    FLAKY = "FLAKY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass
class VerificationDecision:
    decision_id: str
    outcome: VerificationDecisionOutcome
    scope: Dict[str, Any] = field(default_factory=dict)
    tests_run: List[str] = field(default_factory=list)
    tests_missing: List[str] = field(default_factory=list)
    coverage_before: Optional[CoverageVector] = None
    coverage_after: Optional[CoverageVector] = None
    regressions: List[str] = field(default_factory=list)
    flaky_tests: List[str] = field(default_factory=list)
    dynamic_boundaries: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0
    reasons: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "outcome": self.outcome.value if hasattr(self.outcome, "value") else str(self.outcome),
            "scope": self.scope,
            "tests_run": self.tests_run,
            "tests_missing": self.tests_missing,
            "coverage_before": self.coverage_before.to_dict() if self.coverage_before else None,
            "coverage_after": self.coverage_after.to_dict() if self.coverage_after else None,
            "regressions": self.regressions,
            "flaky_tests": self.flaky_tests,
            "dynamic_boundaries": self.dynamic_boundaries,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "timestamp": self.timestamp,
        }


class VerificationPolicyName(str, Enum):
    LOCAL = "LOCAL"
    STANDARD = "STANDARD"
    STRICT = "STRICT"
    CRITICAL = "CRITICAL"
    ECONOMIC = "ECONOMIC"
    SECURITY = "SECURITY"


@dataclass
class VerificationPolicy:
    name: VerificationPolicyName = VerificationPolicyName.STANDARD
    max_tests: int = 50
    max_runtime: float = 60.0
    max_synthesis_attempts: int = 3
    max_mutation_scope: int = 10
    max_browser_tests: int = 5
    max_retries: int = 2
    max_memory_mb: int = 1024
    allow_synthesis: bool = True
    allow_retries: bool = True
    fail_on_flaky: bool = False
    enforce_sentinel: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name.value if hasattr(self.name, "value") else str(self.name),
            "max_tests": self.max_tests,
            "max_runtime": self.max_runtime,
            "max_synthesis_attempts": self.max_synthesis_attempts,
            "max_mutation_scope": self.max_mutation_scope,
            "max_browser_tests": self.max_browser_tests,
            "max_retries": self.max_retries,
            "max_memory_mb": self.max_memory_mb,
            "allow_synthesis": self.allow_synthesis,
            "allow_retries": self.allow_retries,
            "fail_on_flaky": self.fail_on_flaky,
            "enforce_sentinel": self.enforce_sentinel,
        }
