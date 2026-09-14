"""
JARVIS OS — Phase 48: Contract-Aware Autonomous Change Management
Domain Models, Data Contracts, and Operational Enums.

Core Principles:
1. PREDICTED_CONTRACT_CHANGE != OBSERVED_CONTRACT_CHANGE != VERIFIED_CONTRACT_CHANGE
2. Contract versions are immutable (vN -> proposed vN+1 -> validated vN+1 -> active vN+1)
3. Preflight analysis is read-only (state_before == state_after)
4. Breaking changes cannot silently execute without migration plan and approval
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple


class ContractChangeState(str, enum.Enum):
    PREDICTED = "PREDICTED"
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    UNCERTAIN = "UNCERTAIN"


class ContractRiskLevel(str, enum.Enum):
    SAFE = "SAFE"
    NON_BREAKING = "NON_BREAKING"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    BREAKING = "BREAKING"
    UNCERTAIN = "UNCERTAIN"


class MigrationStrategy(str, enum.Enum):
    BACKWARD_COMPATIBLE = "BACKWARD_COMPATIBLE"
    MIGRATE_THEN_SWITCH = "MIGRATE_THEN_SWITCH"
    DUAL_READ = "DUAL_READ"
    DUAL_WRITE = "DUAL_WRITE"
    VERSIONED_ENDPOINT = "VERSIONED_ENDPOINT"
    BREAKING_CHANGE = "BREAKING_CHANGE"
    BLOCKED = "BLOCKED"


class RolloutSafetyStrategy(str, enum.Enum):
    PREPARE_VALIDATE_MIGRATE_SWITCH = "PREPARE_VALIDATE_MIGRATE_SWITCH"
    DIRECT_ATOMIC_SWITCH = "DIRECT_ATOMIC_SWITCH"
    BLOCKED_REQUIRING_OPERATOR = "BLOCKED_REQUIRING_OPERATOR"


class ConsumerCategory(str, enum.Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    TEST = "TEST"
    BROWSER_SCENARIO = "BROWSER_SCENARIO"
    DOWNSTREAM_TASK = "DOWNSTREAM_TASK"


class ConsumerPatternMatching(str, enum.Enum):
    CLOSED_EXHAUSTIVE = "CLOSED_EXHAUSTIVE"  # switch/case or exhaustive enum match without fallback
    OPEN_WITH_FALLBACK = "OPEN_WITH_FALLBACK"  # has default / fallback / tolerant parser
    UNKNOWN = "UNKNOWN"


class ContractChangeType(str, enum.Enum):
    ADD_OPTIONAL_FIELD = "ADD_OPTIONAL_FIELD"
    REMOVE_FIELD = "REMOVE_FIELD"
    CHANGE_FIELD_TYPE = "CHANGE_FIELD_TYPE"
    ADD_REQUIRED_FIELD = "ADD_REQUIRED_FIELD"
    ADD_VARIANT = "ADD_VARIANT"
    REMOVE_VARIANT = "REMOVE_VARIANT"
    CHANGE_DISCRIMINATOR = "CHANGE_DISCRIMINATOR"
    CHANGE_VARIANT_REQUIREDNESS = "CHANGE_VARIANT_REQUIREDNESS"
    CHANGE_AUTH = "CHANGE_AUTH"
    CHANGE_STATUS = "CHANGE_STATUS"
    NO_CHANGE = "NO_CHANGE"


class GateDecision(str, enum.Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_MIGRATION = "REQUIRE_MIGRATION"
    REQUIRE_HUMAN_APPROVAL = "REQUIRE_HUMAN_APPROVAL"


@dataclass
class ContractConsumerTrace:
    consumer_id: str
    name: str
    file_path: str
    category: ConsumerCategory
    pattern_matching: ConsumerPatternMatching
    impact_reason: str
    required_action: str
    language: str = "TypeScript"
    line_ref: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PredictedContractDiff:
    diff_id: str
    contract_id: str
    contract_version: str
    proposed_version: str
    change_type: ContractChangeType
    field_path: str
    old_definition: Any
    new_definition: Any
    risk_level: ContractRiskLevel
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContractMigrationTask:
    task_id: str
    title: str
    target_component: str
    category: str  # BACKEND, FRONTEND, TEST, BROWSER
    description: str
    dependencies: list[str] = field(default_factory=list)
    status: str = "PENDING"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContractMigrationPlan:
    migration_id: str
    source_contract_version: str
    target_contract_version: str
    contract_id: str
    affected_consumers: list[ContractConsumerTrace] = field(default_factory=list)
    required_tasks: list[ContractMigrationTask] = field(default_factory=list)
    compatibility_strategy: MigrationStrategy = MigrationStrategy.BACKWARD_COMPATIBLE
    rollout_strategy: RolloutSafetyStrategy = RolloutSafetyStrategy.PREPARE_VALIDATE_MIGRATE_SWITCH
    rollback_strategy: str = "RESTORE_PREVIOUS_ACTIVE_VERSION_PRESERVE_HISTORY"
    validation_plan: list[str] = field(default_factory=list)
    approval_required: bool = False
    status: str = "PROPOSED"  # PROPOSED, APPROVED, IN_PROGRESS, COMPLETED, REJECTED, ROLLED_BACK
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContractChangePrediction:
    prediction_id: str
    task_id: str
    predicted_files: list[str] = field(default_factory=list)
    affected_contracts: list[str] = field(default_factory=list)
    predicted_diffs: list[PredictedContractDiff] = field(default_factory=list)
    affected_consumers: list[ContractConsumerTrace] = field(default_factory=list)
    breaking_risk: ContractRiskLevel = ContractRiskLevel.SAFE
    migration_required: bool = False
    revalidation_required: bool = False
    approval_required: bool = False
    evidence_required: list[str] = field(default_factory=list)
    migration_plan: Optional[ContractMigrationPlan] = None
    state: ContractChangeState = ContractChangeState.PREDICTED
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        res = asdict(self)
        return res


@dataclass
class ContractPreflightSimulation:
    simulation_id: str
    state_before_hash: str
    state_after_hash: str
    is_read_only: bool
    diff_verdict: ContractRiskLevel
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContractVerificationResult:
    contract_id: str
    baseline_version: str
    observed_version: str
    matches_predicted: bool
    consumer_compatibility_verified: bool
    tests_verified: bool
    browser_qa_verified: bool
    all_evidence_verified: bool
    passed: bool
    failure_reasons: list[str] = field(default_factory=list)
    verified_at: float = field(default_factory=time.time)
    verification_id: str = field(default_factory=lambda: f"verif_{uuid.uuid4().hex[:10]}")

    @property
    def contract_verified(self) -> bool:
        return self.matches_predicted

    @property
    def consumers_verified(self) -> bool:
        return self.consumer_compatibility_verified

    @property
    def evidence_complete(self) -> bool:
        return self.all_evidence_verified

    @property
    def overall_status(self) -> Any:
        class StatusWrapper:
            def __init__(self, val: str):
                self.value = val
            def __str__(self) -> str:
                return self.value
        return StatusWrapper("VERIFIED" if self.passed else "MISMATCH")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["contract_verified"] = self.contract_verified
        d["consumers_verified"] = self.consumers_verified
        d["evidence_complete"] = self.evidence_complete
        d["overall_status"] = self.overall_status.value
        return d
