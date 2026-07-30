from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping

from backend.model_harness.benchmarking.contracts import sha256_json


REGISTRY_VERSION = "capability_registry_v1"
SHA256_LENGTH = 64


class CapabilityId(str, Enum):
    CONSTRAINT_BASED_CHOICE = "constraint_based_choice"
    STRUCTURED_EXTRACTION = "structured_extraction"
    REFERENCE_DISCIPLINE = "reference_discipline"
    BOUNDED_CONTEXT_USE = "bounded_context_use"
    LOCALIZED_CODE_REASONING = "localized_code_reasoning"
    NEGATIVE_CONSTRAINT_FOLLOWING = "negative_constraint_following"
    TOOL_SELECTION_WITHOUT_EXECUTION = "tool_selection_without_execution"
    INSTRUCTION_HIERARCHY = "instruction_hierarchy"
    STATEFUL_TOOL_USE = "stateful_tool_use"
    CONSTRAINT_RETENTION = "constraint_retention"
    EVIDENCE_ACCUMULATION = "evidence_accumulation"
    MULTI_FILE_REASONING = "multi_file_reasoning"
    CONTEXT_SCALING = "context_scaling"
    RECOVERY_AFTER_FAILURE = "recovery_after_failure"
    SHORT_HORIZON_PLANNING = "short_horizon_planning"
    CLOSED_SOURCE_RESEARCH = "closed_source_research"
    EVIDENCE_BASED_DOCUMENT_GENERATION = (
        "evidence_based_document_generation"
    )
    VISION = "vision"
    THINKING = "thinking"
    LONG_CONTEXT_REASONING = "long_context_reasoning"
    LONG_RUNNING_EXECUTION = "long_running_execution"


class CapabilityStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
    DEMONSTRATED_PRELIMINARY = "DEMONSTRATED_PRELIMINARY"
    DEMONSTRATED = "DEMONSTRATED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


SUPPORTED_CAPABILITY_STATUSES = frozenset({
    CapabilityStatus.DEMONSTRATED_PRELIMINARY,
    CapabilityStatus.DEMONSTRATED,
    CapabilityStatus.DEGRADED,
})


class BenchmarkEvidenceKind(str, Enum):
    BOUNDED = "BOUNDED"
    STATEFUL = "STATEFUL"
    PROVIDER_DIAGNOSTIC = "PROVIDER_DIAGNOSTIC"


class BenchmarkOutcome(str, Enum):
    PASSED = "PASSED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    DIAGNOSTIC = "DIAGNOSTIC"
    UNKNOWN = "UNKNOWN"


class CompatibilityTarget(str, Enum):
    RESEARCH_EXECUTOR = "RESEARCH_EXECUTOR"
    DOCUMENT_EXECUTOR = "DOCUMENT_EXECUTOR"
    MISSION_PLANNER = "MISSION_PLANNER"
    TOOL_EXECUTOR = "TOOL_EXECUTOR"


class SelectionReason(str, Enum):
    SUPPORTED = "SUPPORTED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"
    NO_BENCHMARK_EVIDENCE = "NO_BENCHMARK_EVIDENCE"
    STATUS_NOT_SUPPORTED = "STATUS_NOT_SUPPORTED"
    CONFIGURATION_NOT_TESTED = "CONFIGURATION_NOT_TESTED"
    COMPATIBILITY_REQUIREMENT_FAILED = (
        "COMPATIBILITY_REQUIREMENT_FAILED"
    )


class ConstraintOperator(str, Enum):
    EQUALS = "EQUALS"
    IN = "IN"
    AT_LEAST = "AT_LEAST"


class LimitationSeverity(str, Enum):
    INFORMATIONAL = "INFORMATIONAL"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class CapabilityConstraint:
    field: str
    operator: ConstraintOperator
    expected: Any

    def __post_init__(self) -> None:
        if not str(self.field or "").strip():
            raise ValueError("CapabilityConstraint.field e obrigatorio.")


@dataclass(frozen=True)
class CapabilityRequirement:
    capability_id: CapabilityId
    accepted_statuses: tuple[CapabilityStatus, ...] = (
        CapabilityStatus.DEMONSTRATED_PRELIMINARY,
        CapabilityStatus.DEMONSTRATED,
        CapabilityStatus.DEGRADED,
    )
    constraints: tuple[CapabilityConstraint, ...] = ()

    def __post_init__(self) -> None:
        if not self.accepted_statuses:
            raise ValueError(
                "CapabilityRequirement requer pelo menos um status aceite."
            )

    def accepts(self, status: CapabilityStatus) -> bool:
        return status in self.accepted_statuses


@dataclass(frozen=True)
class CapabilityLimitation:
    code: str
    description: str
    severity: LimitationSeverity
    source_artifact: str

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("CapabilityLimitation.code e obrigatorio.")
        if not str(self.description or "").strip():
            raise ValueError(
                "CapabilityLimitation.description e obrigatorio."
            )
        if not str(self.source_artifact or "").strip():
            raise ValueError(
                "CapabilityLimitation.source_artifact e obrigatorio."
            )


@dataclass(frozen=True)
class CapabilityMetrics:
    calls: int
    cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    repetitions: int
    mean_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    context_range: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        integer_values = (
            self.calls,
            self.cases,
            self.passed_cases,
            self.failed_cases,
            self.repetitions,
        )
        if any(value < 0 for value in integer_values):
            raise ValueError("CapabilityMetrics nao aceita valores negativos.")
        if not 0.0 <= self.pass_rate <= 1.0:
            raise ValueError("CapabilityMetrics.pass_rate deve estar em [0,1].")


@dataclass(frozen=True)
class CapabilityConfiguration:
    configuration_hash: str
    model: str
    provider: str
    mode: str
    context_tokens: int | None
    max_output_tokens: int | None
    temperature: float | None
    top_p: float | None
    thinking: bool | None
    streaming: bool | None
    timeout_seconds: float | None
    seed: int | None
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_sha256(
            self.configuration_hash,
            "CapabilityConfiguration.configuration_hash",
        )
        if not str(self.model or "").strip():
            raise ValueError("CapabilityConfiguration.model e obrigatorio.")
        for name, value in (
            ("context_tokens", self.context_tokens),
            ("max_output_tokens", self.max_output_tokens),
        ):
            if value is not None and value < 1:
                raise ValueError(f"{name} deve ser positivo.")


@dataclass(frozen=True)
class BenchmarkEvidence:
    benchmark_id: str
    run_id: str
    kind: BenchmarkEvidenceKind
    artifact: str
    artifact_sha256: str
    timestamp: str
    configuration_hash: str
    outcome: BenchmarkOutcome
    metrics: CapabilityMetrics
    configuration: CapabilityConfiguration
    cases: tuple[str, ...] = ()
    limitations: tuple[CapabilityLimitation, ...] = ()
    decision: str = ""
    report_artifact: str = ""
    report_sha256: str = ""
    artifact_hashes: Mapping[str, str] = field(default_factory=dict)
    declared_hash_verified: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("benchmark_id", self.benchmark_id),
            ("run_id", self.run_id),
            ("artifact", self.artifact),
            ("timestamp", self.timestamp),
        ):
            if not str(value or "").strip():
                raise ValueError(f"BenchmarkEvidence.{name} e obrigatorio.")
        _validate_sha256(
            self.artifact_sha256,
            "BenchmarkEvidence.artifact_sha256",
        )
        _validate_sha256(
            self.configuration_hash,
            "BenchmarkEvidence.configuration_hash",
        )
        if bool(self.report_artifact) != bool(self.report_sha256):
            raise ValueError(
                "BenchmarkEvidence report requer path e hash em conjunto."
            )
        if self.report_sha256:
            _validate_sha256(
                self.report_sha256,
                "BenchmarkEvidence.report_sha256",
            )
        for artifact, artifact_hash in self.artifact_hashes.items():
            if not str(artifact or "").strip():
                raise ValueError(
                    "BenchmarkEvidence.artifact_hashes contem path vazio."
                )
            _validate_sha256(
                artifact_hash,
                f"BenchmarkEvidence.artifact_hashes[{artifact}]",
            )


@dataclass(frozen=True)
class CapabilityEvidence:
    capability_id: CapabilityId
    status: CapabilityStatus
    confidence: float
    benchmark: BenchmarkEvidence

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("CapabilityEvidence.confidence deve estar em [0,1].")


@dataclass(frozen=True)
class CapabilityDefinition:
    id: CapabilityId
    display_name: str
    description: str
    source: str = REGISTRY_VERSION
    requirements: tuple[CapabilityRequirement, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.display_name or "").strip():
            raise ValueError("CapabilityDefinition.display_name e obrigatorio.")
        if not str(self.description or "").strip():
            raise ValueError("CapabilityDefinition.description e obrigatorio.")
        if not str(self.source or "").strip():
            raise ValueError("CapabilityDefinition.source e obrigatorio.")


@dataclass(frozen=True)
class Capability:
    id: CapabilityId
    display_name: str
    description: str
    status: CapabilityStatus
    confidence: float
    limitations: tuple[CapabilityLimitation, ...]
    requirements: tuple[CapabilityRequirement, ...]
    evidence: tuple[CapabilityEvidence, ...]
    configurations: tuple[CapabilityConfiguration, ...]
    last_verified: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Capability.confidence deve estar em [0,1].")
        if not self.evidence:
            raise ValueError(
                "Capability persistida requer evidencia de benchmark."
            )
        if not str(self.last_verified or "").strip():
            raise ValueError("Capability.last_verified e obrigatorio.")


@dataclass(frozen=True)
class ModelCapabilityProfile:
    model_name: str
    provider: str
    architecture: str
    parameter_count: int | None
    quantization: str
    context_length: int | None
    capabilities: tuple[Capability, ...]
    limitations: tuple[CapabilityLimitation, ...]
    benchmarks: tuple[BenchmarkEvidence, ...]
    configurations: tuple[CapabilityConfiguration, ...]
    advertised_features: tuple[str, ...]
    last_validation: str

    def __post_init__(self) -> None:
        if not str(self.model_name or "").strip():
            raise ValueError("ModelCapabilityProfile.model_name e obrigatorio.")
        if self.parameter_count is not None and self.parameter_count < 1:
            raise ValueError("parameter_count deve ser positivo.")
        if self.context_length is not None and self.context_length < 1:
            raise ValueError("context_length deve ser positivo.")

    def capability(self, capability_id: CapabilityId) -> Capability | None:
        return next(
            (
                item
                for item in self.capabilities
                if item.id is capability_id
            ),
            None,
        )


@dataclass(frozen=True)
class CompatibilityRule:
    target: CompatibilityTarget
    requirements: tuple[CapabilityRequirement, ...]
    source: str = REGISTRY_VERSION

    def __post_init__(self) -> None:
        if not self.requirements:
            raise ValueError("CompatibilityRule requer capabilities.")


@dataclass(frozen=True)
class CapabilityDecision:
    model_name: str
    capability_id: CapabilityId
    supported: bool
    status: CapabilityStatus
    reason: SelectionReason
    configuration_hash: str = ""
    evidence_artifacts: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityCompatibility:
    model_name: str
    target: CompatibilityTarget
    compatible: bool
    requirements: tuple[CapabilityRequirement, ...]
    decisions: tuple[CapabilityDecision, ...]


@dataclass(frozen=True)
class CapabilitySelection:
    requested_capabilities: tuple[CapabilityId, ...]
    selected_models: tuple[str, ...]
    rejected_models: tuple[str, ...]
    decisions: tuple[CapabilityDecision, ...]
    compatibility_target: CompatibilityTarget | None = None
    configuration_hash: str = ""


@dataclass(frozen=True)
class CapabilityRegistrySnapshot:
    registry_version: str
    snapshot_version: str
    generated_at: str
    models: tuple[ModelCapabilityProfile, ...]
    compatibility_rules: tuple[CompatibilityRule, ...]
    source_sha256: str
    content_sha256: str

    def payload_without_content_hash(self) -> dict[str, Any]:
        payload = to_jsonable(self)
        payload.pop("content_sha256", None)
        return payload

    def computed_content_sha256(self) -> str:
        return sha256_json(self.payload_without_content_hash())

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class RegistryValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity
    location: str


@dataclass(frozen=True)
class RegistryValidationResult:
    valid: bool
    issues: tuple[RegistryValidationIssue, ...] = ()


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {
            key: to_jsonable(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, Mapping):
        return {
            str(key): to_jsonable(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }
    if isinstance(value, (set, frozenset)):
        return sorted(
            (to_jsonable(item) for item in value),
            key=canonical_json,
        )
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_sha256(value: str, field_name: str) -> None:
    normalized = str(value or "").strip().lower()
    if (
        len(normalized) != SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in normalized)
    ):
        raise ValueError(f"{field_name} deve ser SHA-256 hexadecimal.")
