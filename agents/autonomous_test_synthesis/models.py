"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: models.py
Domain models, enums, and cryptographic data structures.
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


class TestRequirementSource(str, enum.Enum):
    USER_ACCEPTANCE_CRITERION = "USER_ACCEPTANCE_CRITERION"
    CONTRACT = "CONTRACT"
    SYMBOL_IMPACT = "SYMBOL_IMPACT"
    BEHAVIORAL_INVARIANT = "BEHAVIORAL_INVARIANT"
    SECURITY_POLICY = "SECURITY_POLICY"
    ECONOMIC_POLICY = "ECONOMIC_POLICY"
    REGRESSION = "REGRESSION"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    COVERAGE_GAP = "COVERAGE_GAP"
    HISTORICAL_FAILURE = "HISTORICAL_FAILURE"


class CoverageGapType(str, enum.Enum):
    UNTESTED_SYMBOL = "UNTESTED_SYMBOL"
    UNTESTED_BRANCH = "UNTESTED_BRANCH"
    UNTESTED_ERROR_PATH = "UNTESTED_ERROR_PATH"
    UNTESTED_CONTRACT_VARIANT = "UNTESTED_CONTRACT_VARIANT"
    UNTESTED_CONSUMER = "UNTESTED_CONSUMER"
    UNTESTED_INVARIANT = "UNTESTED_INVARIANT"
    UNTESTED_BROWSER_FLOW = "UNTESTED_BROWSER_FLOW"
    UNTESTED_REPAIR_PATH = "UNTESTED_REPAIR_PATH"


class TestStrategy(str, enum.Enum):
    UNIT_TEST_SYNTHESIS = "UNIT_TEST_SYNTHESIS"
    INTEGRATION_TEST_SYNTHESIS = "INTEGRATION_TEST_SYNTHESIS"
    CONTRACT_TEST_SYNTHESIS = "CONTRACT_TEST_SYNTHESIS"
    REGRESSION_TEST_SYNTHESIS = "REGRESSION_TEST_SYNTHESIS"
    BEHAVIORAL_TEST_SYNTHESIS = "BEHAVIORAL_TEST_SYNTHESIS"
    PROPERTY_TEST_SYNTHESIS = "PROPERTY_TEST_SYNTHESIS"
    ERROR_PATH_TEST_SYNTHESIS = "ERROR_PATH_TEST_SYNTHESIS"
    BROWSER_TEST_SYNTHESIS = "BROWSER_TEST_SYNTHESIS"


class TestFramework(str, enum.Enum):
    PYTEST = "pytest"
    VITEST = "vitest"
    JEST = "jest"
    PLAYWRIGHT = "playwright"


class TestCandidateStatus(str, enum.Enum):
    GENERATED = "GENERATED"
    RANKED = "RANKED"
    EXECUTING = "EXECUTING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class MutationType(str, enum.Enum):
    OPERATOR_SWAP = "OPERATOR_SWAP"
    CONSTANT_REPLACEMENT = "CONSTANT_REPLACEMENT"
    CONDITION_INVERSION = "CONDITION_INVERSION"
    RETURN_VALUE_TAMPER = "RETURN_VALUE_TAMPER"
    BRANCH_DELETION = "BRANCH_DELETION"


@dataclass(frozen=True)
class CostEstimate:
    generation_cost: float = 0.01
    execution_cost: float = 0.02
    environment_cost: float = 0.005
    browser_cost: float = 0.0
    total_cost: float = 0.035

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TestRequirement:
    requirement_id: str
    source: TestRequirementSource
    symbol_id: str
    file_id: str
    contract_id: Optional[str] = None
    consumer_id: Optional[str] = None
    risk: float = 0.5
    coverage_gap: Optional[CoverageGapType] = None
    invariant: str = ""
    scenario_type: str = "functional"
    priority: float = 1.0
    provenance: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value if isinstance(self.source, enum.Enum) else self.source
        if self.coverage_gap:
            d["coverage_gap"] = (
                self.coverage_gap.value
                if isinstance(self.coverage_gap, enum.Enum)
                else self.coverage_gap
            )
        return d


@dataclass
class TestCandidate:
    test_id: str
    requirement_id: str
    target: str
    framework: TestFramework
    language: str
    files: List[str]
    inputs: Dict[str, Any]
    expected_outputs: Dict[str, Any]
    invariants: List[str]
    risk: float = 0.5
    estimated_cost: CostEstimate = field(default_factory=CostEstimate)
    predicted_coverage_gain: float = 0.1
    provenance: str = "autonomous_generator"
    code: str = ""
    status: TestCandidateStatus = TestCandidateStatus.GENERATED
    rejection_reason: Optional[str] = None

    def compute_hash(self) -> str:
        payload = f"{self.test_id}:{self.requirement_id}:{self.target}:{self.code}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "requirement_id": self.requirement_id,
            "target": self.target,
            "framework": self.framework.value if isinstance(self.framework, enum.Enum) else self.framework,
            "language": self.language,
            "files": self.files,
            "inputs": self.inputs,
            "expected_outputs": self.expected_outputs,
            "invariants": self.invariants,
            "risk": self.risk,
            "estimated_cost": self.estimated_cost.to_dict(),
            "predicted_coverage_gain": self.predicted_coverage_gain,
            "provenance": self.provenance,
            "code": self.code,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "rejection_reason": self.rejection_reason,
            "hash": self.compute_hash(),
        }


@dataclass
class CounterexampleEvidence:
    counterexample_id: str
    source_invariant: str
    violating_input: Dict[str, Any]
    observed_output: Any
    expected_property: str
    symbol_id: str
    file_id: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestExecutionResult:
    test_id: str
    passed: bool
    duration_ms: float
    coverage_delta: float
    risk_delta: float
    error_message: Optional[str] = None
    captured_output: str = ""
    counterexample: Optional[CounterexampleEvidence] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.counterexample:
            d["counterexample"] = self.counterexample.to_dict()
        return d


@dataclass
class TestEvidenceItem:
    test_id: str
    execution_id: str
    result: str  # "PASS" | "FAIL" | "ERROR"
    coverage_delta: float
    risk_delta: float
    provenance: str
    evidence_hash: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoverageMetrics:
    line_cov: float = 0.0
    branch_cov: float = 0.0
    symbol_cov: float = 0.0
    contract_cov: float = 0.0
    behavior_cov: float = 0.0
    invariant_cov: float = 0.0
    consumer_cov: float = 0.0
    browser_cov: float = 0.0

    def compute_composite_score(self) -> float:
        """Weighted average across all 8 dimensions."""
        weights = [0.10, 0.15, 0.15, 0.15, 0.15, 0.15, 0.10, 0.05]
        values = [
            self.line_cov,
            self.branch_cov,
            self.symbol_cov,
            self.contract_cov,
            self.behavior_cov,
            self.invariant_cov,
            self.consumer_cov,
            self.browser_cov,
        ]
        return round(sum(w * v for w, v in zip(weights, values)), 4)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["composite_score"] = self.compute_composite_score()
        return d


@dataclass
class MutationResult:
    mutant_id: str
    mutation_type: MutationType
    target_symbol: str
    target_file: str
    detected: bool
    killing_test_id: Optional[str] = None
    survived: bool = False
    original_snippet: str = ""
    mutated_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["mutation_type"] = self.mutation_type.value if isinstance(self.mutation_type, enum.Enum) else self.mutation_type
        return d
