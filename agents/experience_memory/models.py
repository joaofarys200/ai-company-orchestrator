"""
JARVIS OS — Phase 42: Experience Memory & Cross-Mission Learning Models
Defines immutable records, taxonomies, signatures, and metric contracts for
structured, causal, and verifiable cross-mission operational memory.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class ExperienceSourceType(str, Enum):
    REAL_MISSION = "REAL_MISSION"
    CONTROLLED_TEST = "CONTROLLED_TEST"
    REPLAY = "REPLAY"
    SHADOW = "SHADOW"
    SYNTHETIC = "SYNTHETIC"


class ExperienceTaxonomy(str, Enum):
    PLANNING = "PLANNING"
    PREDICTION = "PREDICTION"
    EXECUTION = "EXECUTION"
    REPAIR = "REPAIR"
    REPLAN = "REPLAN"
    OBSERVATION = "OBSERVATION"
    SECURITY = "SECURITY"
    RECOVERY = "RECOVERY"
    BROWSER = "BROWSER"
    BUILD = "BUILD"
    TEST = "TEST"
    DEPENDENCY = "DEPENDENCY"
    INTENT = "INTENT"
    PERFORMANCE = "PERFORMANCE"
    GOVERNANCE = "GOVERNANCE"


class ExperienceApplicabilityRating(str, Enum):
    RELEVANT = "RELEVANT"
    POSSIBLY_RELEVANT = "POSSIBLY_RELEVANT"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"
    INAPPLICABLE = "INAPPLICABLE"


class TemporalValidity(str, Enum):
    CURRENT = "CURRENT"
    AGING = "AGING"
    STALE = "STALE"


class MemoryInfluenceType(str, Enum):
    NONE = "NONE"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    DIAGNOSTIC = "DIAGNOSTIC"
    PLANNING_HINT = "PLANNING_HINT"
    PREDICTION_HINT = "PREDICTION_HINT"
    REPAIR_HINT = "REPAIR_HINT"
    ESCALATION_HINT = "ESCALATION_HINT"
    # DIRECT_AUTHORIZATION is intentionally excluded and strictly prohibited.


class HumanCurationAction(str, Enum):
    ACCEPT_MEMORY = "ACCEPT_MEMORY"
    MARK_IRRELEVANT = "MARK_IRRELEVANT"
    MARK_STALE = "MARK_STALE"
    MARK_MISLEADING = "MARK_MISLEADING"
    MARK_TRUSTED = "MARK_TRUSTED"
    MARK_CONTEXT_ONLY = "MARK_CONTEXT_ONLY"
    PIN_EXPERIENCE = "PIN_EXPERIENCE"
    HIDE_EXPERIENCE = "HIDE_EXPERIENCE"
    ARCHIVE = "ARCHIVE"


class NoveltyLevel(str, Enum):
    FAMILIAR = "FAMILIAR"
    RELATED = "RELATED"
    NOVEL = "NOVEL"
    HIGHLY_NOVEL = "HIGHLY_NOVEL"


class DatasetSplit(str, Enum):
    TRAIN_HISTORY = "TRAIN_HISTORY"
    VALIDATION = "VALIDATION"
    UNSEEN_TEST = "UNSEEN_TEST"


class MemoryBenefitCategory(str, Enum):
    NO_HARM = "NO_HARM"
    BENEFICIAL = "BENEFICIAL"
    NEUTRAL = "NEUTRAL"
    HARMFUL = "HARMFUL"


class PolicyCompatibilityStatus(str, Enum):
    CURRENT_POLICY_COMPATIBLE = "CURRENT_POLICY_COMPATIBLE"
    POLICY_MISMATCH = "POLICY_MISMATCH"
    POLICY_REQUIRES_VALIDATION = "POLICY_REQUIRES_VALIDATION"


class ExperiencePolarity(str, Enum):
    POSITIVE_EXPERIENCE = "POSITIVE_EXPERIENCE"
    NEGATIVE_EXPERIENCE = "NEGATIVE_EXPERIENCE"


@dataclass(frozen=True)
class ExperienceSignature:
    intent_category: str
    requirement_types: tuple[str, ...] = field(default_factory=tuple)
    affected_architecture: tuple[str, ...] = field(default_factory=tuple)
    task_categories: tuple[str, ...] = field(default_factory=tuple)
    observed_failure: str = "NONE"
    decision: str = "CONTINUE"
    environment: str = "LOCAL"
    technology: tuple[str, ...] = field(default_factory=tuple)
    scope: str = "MODULE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_category": self.intent_category,
            "requirement_types": list(self.requirement_types),
            "affected_architecture": list(self.affected_architecture),
            "task_categories": list(self.task_categories),
            "observed_failure": self.observed_failure,
            "decision": self.decision,
            "environment": self.environment,
            "technology": list(self.technology),
            "scope": self.scope,
        }


@dataclass(frozen=True)
class ExperienceRecord:
    experience_id: str
    mission_id: str
    cycle_id: str
    intent_signature: ExperienceSignature
    mission_context: dict[str, Any]
    decision: str
    policy_version: str
    observation: dict[str, Any]
    outcome: str
    root_cause: str
    severity: str
    prediction: dict[str, Any]
    actual_result: dict[str, Any]
    adaptation: dict[str, Any]
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    task_refs: tuple[str, ...] = field(default_factory=tuple)
    architecture_refs: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    applicability: str = "RELEVANT"
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    source_type: ExperienceSourceType = ExperienceSourceType.REAL_MISSION
    source_hash: str = ""
    # Causal memory preserving chain: REQUIREMENT -> PLAN -> TASK -> OBSERVATION -> FAILURE -> DIAGNOSIS -> REPAIR -> VALIDATION -> OUTCOME
    causal_chain: dict[str, Any] = field(default_factory=dict)
    temporal_validity: TemporalValidity = TemporalValidity.CURRENT
    curation_status: str = "NONE"
    polarity: ExperiencePolarity = ExperiencePolarity.POSITIVE_EXPERIENCE
    index_version: str = "43.0.0"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["intent_signature"] = self.intent_signature.to_dict()
        d["source_type"] = self.source_type.value
        d["temporal_validity"] = self.temporal_validity.value
        d["polarity"] = self.polarity.value
        d["evidence_refs"] = list(self.evidence_refs)
        d["task_refs"] = list(self.task_refs)
        d["architecture_refs"] = list(self.architecture_refs)
        d["tags"] = list(self.tags)
        return d


@dataclass
class RelevantExperience:
    experience: ExperienceRecord
    relevance_score: float
    applicability: ExperienceApplicabilityRating
    why_relevant: str
    matched_factors: list[str] = field(default_factory=list)
    influence_type: MemoryInfluenceType = MemoryInfluenceType.DIAGNOSTIC

    def to_dict(self) -> dict[str, Any]:
        return {
            "experience": self.experience.to_dict(),
            "relevance_score": round(self.relevance_score, 4),
            "applicability": self.applicability.value,
            "why_relevant": self.why_relevant,
            "matched_factors": self.matched_factors,
            "influence_type": self.influence_type.value,
        }


@dataclass
class ConflictingExperience:
    primary_experience_id: str
    conflicting_experience_id: str
    divergence_summary: str
    context_comparison: dict[str, Any]
    evidence_comparison: dict[str, Any]
    success_rate_comparison: dict[str, Any]
    policy_version_delta: str
    severity_delta: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperienceCorrection:
    correction_id: str
    original_experience_id: str
    corrected_fields: dict[str, Any]
    reason: str
    curator_id: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperienceReuseRecord:
    reuse_id: str
    source_experience_id: str
    target_mission_id: str
    target_cycle_id: str
    what_was_reused: str
    how_adapted: str
    experience_prediction: str
    actual_outcome: str
    successful_reuse: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperienceReuseOutcome:
    reuse_id: str
    source_mission_id: str
    source_experience_id: str
    target_mission_id: str
    novelty_level: NoveltyLevel = NoveltyLevel.FAMILIAR
    relevance_score: float = 1.0
    applicability_rating: str = "RELEVANT"
    influence_type: str = "DIAGNOSTIC"
    outcome_summary: str = ""
    benefit_category: MemoryBenefitCategory = MemoryBenefitCategory.BENEFICIAL
    is_false_transfer: bool = False
    root_cause_if_harmful: str = "NONE"
    corrective_action: str = "NONE"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["novelty_level"] = self.novelty_level.value
        d["benefit_category"] = self.benefit_category.value
        return d


@dataclass
class ExperienceQualityMetrics:
    reuse_count: int = 0
    successful_reuse_count: int = 0
    failed_reuse_count: int = 0
    contradicted_count: int = 0
    stale_count: int = 0
    applicability_accuracy: float = 1.0
    outcome_consistency: float = 1.0
    precision: float = 1.0
    recall: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GeneralizationMetrics:
    total_unseen_missions: int = 0
    cold_success_count: int = 0
    warm_success_count: int = 0
    cold_success_rate: float = 0.0
    warm_success_rate: float = 0.0
    warm_delta: float = 0.0
    memory_benefit_rate: float = 0.0
    memory_harm_rate: float = 0.0
    false_memory_transfer_rate: float = 0.0
    retrieval_precision: float = 1.0
    retrieval_recall: float = 1.0
    applicability_accuracy: float = 1.0
    stale_rejection_rate: float = 1.0
    conflict_resolution_accuracy: float = 1.0
    temporal_leakage_count: int = 0
    sample_counts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
