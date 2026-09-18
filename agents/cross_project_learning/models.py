"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: models.py
Domain models, enums, dataclasses, and immutability structures for cross-project
engineering knowledge, fingerprints, transfer governance, and validation evidence.

Core Invariant:
    KNOWLEDGE TRANSFER != EVIDENCE TRANSFER
    External knowledge yields hypotheses, test patterns, risk models, and repair hints.
    Never marks a target project artifact as VERIFIED without new local validation.
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class KnowledgeCategory(str, enum.Enum):
    """The 10 mandatory cross-project engineering knowledge categories."""
    ARCHITECTURE_PATTERN = "ARCHITECTURE_PATTERN"
    TEST_PATTERN = "TEST_PATTERN"
    REPAIR_PATTERN = "REPAIR_PATTERN"
    FAILURE_PATTERN = "FAILURE_PATTERN"
    CONTRACT_PATTERN = "CONTRACT_PATTERN"
    BEHAVIOR_PATTERN = "BEHAVIOR_PATTERN"
    RISK_PATTERN = "RISK_PATTERN"
    PERFORMANCE_PATTERN = "PERFORMANCE_PATTERN"
    BROWSER_PATTERN = "BROWSER_PATTERN"
    RECOVERY_PATTERN = "RECOVERY_PATTERN"


class KnowledgeState(str, enum.Enum):
    """
    Lifecycle state for an engineering knowledge item.
    Invariant: OBSERVED never transitions to TRANSFERABLE automatically without validation.
    """
    OBSERVED = "OBSERVED"
    VALIDATED = "VALIDATED"
    TRANSFERABLE = "TRANSFERABLE"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    REJECTED = "REJECTED"


class ApplicabilityStatus(str, enum.Enum):
    """Fine-grained applicability classification with natural language explanation."""
    DIRECTLY_APPLICABLE = "DIRECTLY_APPLICABLE"
    PARTIALLY_APPLICABLE = "PARTIALLY_APPLICABLE"
    CONTEXT_REQUIRED = "CONTEXT_REQUIRED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class TransferDecisionState(str, enum.Enum):
    """
    Governance state of a knowledge transfer request.
    TRANSFERRED_KNOWLEDGE -> NEW_LOCAL_VALIDATION is mandatory.
    """
    TRANSFER_FOR_CONSIDERATION = "TRANSFER_FOR_CONSIDERATION"
    TRANSFER_AS_HYPOTHESIS = "TRANSFER_AS_HYPOTHESIS"
    TRANSFER_TO_TEST_GENERATION = "TRANSFER_TO_TEST_GENERATION"
    TRANSFER_TO_RISK_MODEL = "TRANSFER_TO_RISK_MODEL"
    TRANSFER_TO_REPAIR_SEARCH = "TRANSFER_TO_REPAIR_SEARCH"
    REJECT_TRANSFER = "REJECT_TRANSFER"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class FreshnessState(str, enum.Enum):
    """Temporal and structural validity state of engineering knowledge."""
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"


class FeedbackOutcome(str, enum.Enum):
    """Observed local validation result after transferring knowledge."""
    TRANSFER_SUCCESS = "TRANSFER_SUCCESS"
    TRANSFER_NEUTRAL = "TRANSFER_NEUTRAL"
    TRANSFER_HARM = "TRANSFER_HARM"
    TRANSFER_REJECTED = "TRANSFER_REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class TransferPolicyName(str, enum.Enum):
    """Policy profiles governing transfer thresholds and validation rigor."""
    CONSERVATIVE = "CONSERVATIVE"
    STANDARD = "STANDARD"
    STRICT = "STRICT"
    AGGRESSIVE = "AGGRESSIVE"
    SECURITY_FIRST = "SECURITY_FIRST"
    ECONOMIC = "ECONOMIC"


@dataclass
class ProjectFingerprint:
    """
    Deterministic structural signature of a software repository or mission.
    Contains no secrets, credentials, personal data, or raw source code.
    """
    project_id: str
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    architecture_style: str = "modular_monolith"
    package_topology: str = "single_package"
    service_topology: str = "standalone"
    contract_types: List[str] = field(default_factory=list)
    symbol_graph_statistics: Dict[str, Any] = field(default_factory=dict)
    scc_statistics: Dict[str, Any] = field(default_factory=dict)
    test_framework: List[str] = field(default_factory=list)
    browser_framework: List[str] = field(default_factory=list)
    persistence_technologies: List[str] = field(default_factory=list)
    communication_mechanisms: List[str] = field(default_factory=list)
    risk_classes: List[str] = field(default_factory=list)
    domain_category: str = "general_engineering"
    repository_scale: str = "medium"
    verification_history: Dict[str, Any] = field(default_factory=dict)
    fingerprint_hash: str = ""
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.fingerprint_hash:
            self.fingerprint_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Compute reproducible SHA-256 over canonicalized structural properties."""
        canonical_dict = {
            "languages": sorted([x.lower() for x in self.languages]),
            "frameworks": sorted([x.lower() for x in self.frameworks]),
            "architecture_style": self.architecture_style.lower(),
            "package_topology": self.package_topology.lower(),
            "service_topology": self.service_topology.lower(),
            "contract_types": sorted([x.lower() for x in self.contract_types]),
            "test_framework": sorted([x.lower() for x in self.test_framework]),
            "browser_framework": sorted([x.lower() for x in self.browser_framework]),
            "persistence_technologies": sorted([x.lower() for x in self.persistence_technologies]),
            "communication_mechanisms": sorted([x.lower() for x in self.communication_mechanisms]),
            "risk_classes": sorted([x.lower() for x in self.risk_classes]),
            "domain_category": self.domain_category.lower(),
            "repository_scale": self.repository_scale.lower(),
        }
        encoded = json.dumps(canonical_dict, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectFingerprint:
        clean_data = dict(data)
        return cls(**clean_data)


@dataclass
class KnowledgeProvenance:
    """Full lineage, audit trail, and origin tracking for an engineering item."""
    source_project_id: str
    source_file: str = ""
    author_mission_id: str = ""
    transformation_chain: List[str] = field(default_factory=list)
    original_validation_hash: str = ""
    security_checked: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EngineeringKnowledgeItem:
    """
    Standardized unit of reusable engineering knowledge.
    Contains preconditions, observed effects, and evidence boundaries.
    """
    knowledge_id: str
    source_project_id: str
    source_project_fingerprint: str
    category: KnowledgeCategory
    pattern: Dict[str, Any]
    context: Dict[str, Any]
    preconditions: List[str]
    observed_effect: Dict[str, Any]
    evidence_scope: Dict[str, Any]
    confidence: float
    provenance: KnowledgeProvenance
    created_at: float = field(default_factory=time.time)
    supersedes: Optional[str] = None
    expires_at: Optional[float] = None
    security_classification: str = "INTERNAL"
    state: KnowledgeState = KnowledgeState.OBSERVED
    harm_count: int = 0
    success_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["category"] = self.category.value
        res["state"] = self.state.value
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EngineeringKnowledgeItem:
        d = dict(data)
        d["category"] = KnowledgeCategory(d["category"])
        d["state"] = KnowledgeState(d["state"])
        if isinstance(d.get("provenance"), dict):
            d["provenance"] = KnowledgeProvenance(**d["provenance"])
        return cls(**d)


@dataclass
class CandidateKnowledge:
    """Ranked knowledge candidate with matching dimensions and contradiction checks."""
    item: EngineeringKnowledgeItem
    score: float
    matching_dimensions: List[str]
    missing_dimensions: List[str]
    contradictions: List[str]
    provenance: KnowledgeProvenance
    applicability_confidence: float

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["item"] = self.item.to_dict()
        return res


@dataclass
class ApplicabilityResult:
    """Evaluation result detailing why knowledge is or is not applicable."""
    status: ApplicabilityStatus
    confidence: float
    why_applicable: List[str] = field(default_factory=list)
    why_not_applicable: List[str] = field(default_factory=list)
    required_transformations: List[str] = field(default_factory=list)
    adapter_needed: bool = False
    target_language: str = ""

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["status"] = self.status.value
        return res


@dataclass
class KnowledgeTransferDecision:
    """Formal governance record for a transfer attempt."""
    decision_id: str
    state: TransferDecisionState
    target_project_id: str
    item_id: str
    category: KnowledgeCategory
    rationale: str
    local_validation_plan: Dict[str, Any] = field(default_factory=dict)
    requires_human_review: bool = False
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["state"] = self.state.value
        res["category"] = self.category.value
        return res


@dataclass
class LocalValidationResult:
    """Closed-loop local verification results for transferred knowledge."""
    validation_id: str
    transfer_decision_id: str
    target_project_id: str
    validated: bool
    outcome: FeedbackOutcome
    tests_executed: List[str] = field(default_factory=list)
    coverage_delta: float = 0.0
    harm_detected: bool = False
    harm_details: Optional[str] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["outcome"] = self.outcome.value
        return res


@dataclass
class ConflictRecord:
    """Record of contradictory engineering knowledge."""
    conflict_id: str
    pair_item_ids: Tuple[str, str]
    conflict_type: str
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    resolution_status: str = "OPEN"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class HarmEvent:
    """Telemetry record when transferred knowledge degraded local performance."""
    harm_id: str
    knowledge_id: str
    target_project_id: str
    harm_type: str
    details: str
    penalty_applied: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
