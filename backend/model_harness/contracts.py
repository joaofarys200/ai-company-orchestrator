from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class OutputFormat(str, Enum):
    TEXT = "TEXT"
    JSON = "JSON"
    JSON_SCHEMA = "JSON_SCHEMA"
    TOOL_CALLS = "TOOL_CALLS"


class ModelResponseStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PROVIDER_FAILED = "PROVIDER_FAILED"
    STOPPED = "STOPPED"


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    DEFERRED = "DEFERRED"
    NOT_RUN = "NOT_RUN"


class ValidationStage(str, Enum):
    PARSING = "PARSING"
    SCHEMA = "SCHEMA"
    ENUMS = "ENUMS"
    REFERENCES = "REFERENCES"
    PRECONDITIONS = "PRECONDITIONS"
    COMPATIBILITY = "COMPATIBILITY"
    ACCEPTANCE_CRITERIA = "ACCEPTANCE_CRITERIA"


class RecoveryAction(str, Enum):
    NONE = "NONE"
    PARSE_RECOVERY = "PARSE_RECOVERY"
    MECHANICAL_COMPLETION = "MECHANICAL_COMPLETION"
    SEMANTIC_RETRY = "SEMANTIC_RETRY"
    CONTRADICTION_RETRY = "CONTRADICTION_RETRY"
    STOP = "STOP"
    ESCALATION = "ESCALATION"


class ProgressCondition(str, Enum):
    NO_PROGRESS = "NO_PROGRESS"
    REPEATED_REASONING = "REPEATED_REASONING"
    REPEATED_TOOL_CALLS = "REPEATED_TOOL_CALLS"
    REPEATED_FAILURES = "REPEATED_FAILURES"


@dataclass(frozen=True)
class ContextItem:
    source: str
    kind: str
    content: str
    inclusion_reason: str
    relevance_score: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def content_sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContextDecision:
    source: str
    kind: str
    included: bool
    reason: str
    content_sha256: str
    size_chars: int


@dataclass(frozen=True)
class TaskContext:
    items: tuple[ContextItem, ...] = ()
    decisions: tuple[ContextDecision, ...] = ()
    total_chars: int = 0

    def contents(self, kind: str | None = None) -> tuple[str, ...]:
        return tuple(
            item.content
            for item in self.items
            if kind is None or item.kind == kind
        )


@dataclass(frozen=True)
class EnumConstraint:
    field_path: str
    allowed_values: tuple[Any, ...]


@dataclass(frozen=True)
class ReferenceConstraint:
    field_path: str
    allowed_references: tuple[str, ...]
    allow_empty: bool = False


@dataclass(frozen=True)
class ExpectedOutput:
    format: OutputFormat = OutputFormat.TEXT
    schema: Mapping[str, Any] | None = None
    enum_constraints: tuple[EnumConstraint, ...] = ()
    reference_constraints: tuple[ReferenceConstraint, ...] = ()
    defer_validation: bool = False
    validation_owner: str = "model_harness"


@dataclass(frozen=True)
class ModelPreferences:
    providers: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    mode: str = "chat"


@dataclass(frozen=True)
class ExecutionConstraints:
    max_attempts: int = 1
    timeout_seconds: float | None = None
    streaming: bool | None = None
    thinking: bool | None = None
    allow_recovery: bool = False
    stop_on_no_progress: bool = True
    provider_payload: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or self.max_attempts < 1:
            raise ValueError("max_attempts deve ser um inteiro positivo.")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser positivo.")


@dataclass(frozen=True)
class ModelRequest:
    task_profile: str
    system_prompt: str
    user_prompt: str
    context: TaskContext = field(default_factory=TaskContext)
    allowed_tools: tuple[str, ...] = ()
    expected_output: ExpectedOutput | None = None
    temperature: float | None = None
    max_context_tokens: int | None = None
    max_output_tokens: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    model_preferences: ModelPreferences = field(default_factory=ModelPreferences)
    execution_constraints: ExecutionConstraints = field(
        default_factory=ExecutionConstraints
    )
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self) -> None:
        if not str(self.task_profile or "").strip():
            raise ValueError("task_profile e obrigatorio.")
        if not isinstance(self.system_prompt, str):
            raise TypeError("system_prompt deve ser texto.")
        if not isinstance(self.user_prompt, str):
            raise TypeError("user_prompt deve ser texto.")
        if not str(self.request_id or "").strip():
            raise ValueError("request_id e obrigatorio.")
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("temperature deve estar entre 0 e 2.")
        for name, value in (
            ("max_context_tokens", self.max_context_tokens),
            ("max_output_tokens", self.max_output_tokens),
        ):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
            ):
                raise ValueError(f"{name} deve ser um inteiro positivo.")

    def fingerprint(self) -> str:
        payload = {
            "task_profile": self.task_profile,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "context": [
                {
                    "source": item.source,
                    "kind": item.kind,
                    "content_sha256": item.content_sha256,
                }
                for item in self.context.items
            ],
            "allowed_tools": list(self.allowed_tools),
            "expected_output": (
                self.expected_output.format.value
                if self.expected_output is not None
                else None
            ),
            "providers": list(self.model_preferences.providers),
            "models": list(self.model_preferences.models),
            "mode": self.model_preferences.mode,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    call_id: str = ""


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str
    mode: str
    streaming: bool
    thinking: bool


@dataclass(frozen=True)
class ProviderResult:
    raw_text: str
    usage: ModelUsage = field(default_factory=ModelUsage)
    tool_calls: tuple[ToolCall, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationIssue:
    stage: ValidationStage
    code: str
    location: str
    message: str
    recoverable: bool
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        return payload


@dataclass(frozen=True)
class ValidationResult:
    status: ValidationStatus
    issues: tuple[ValidationIssue, ...] = ()
    structured_output: Any = None
    completed_stages: tuple[ValidationStage, ...] = ()
    delegated_to: str = ""

    @property
    def is_valid(self) -> bool:
        return self.status in {
            ValidationStatus.PASSED,
            ValidationStatus.DEFERRED,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "issues": [item.to_dict() for item in self.issues],
            "structured_output": self.structured_output,
            "completed_stages": [
                stage.value for stage in self.completed_stages
            ],
            "delegated_to": self.delegated_to,
        }


@dataclass(frozen=True)
class RecoveryRecord:
    action: RecoveryAction
    reason: str
    recoverable: bool
    retry_requested: bool = False
    input_changed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action"] = self.action.value
        return payload


@dataclass
class ModelResponse:
    request_id: str
    status: ModelResponseStatus
    raw_text: str = ""
    structured_output: Any = None
    usage: ModelUsage = field(default_factory=ModelUsage)
    provider: str = ""
    model: str = ""
    latency_ms: int = 0
    validation: ValidationResult = field(
        default_factory=lambda: ValidationResult(
            status=ValidationStatus.NOT_RUN
        )
    )
    recovery: tuple[RecoveryRecord, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[Mapping[str, Any], ...] = ()
    provider_exception: Exception | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "raw_text": self.raw_text,
            "structured_output": self.structured_output,
            "usage": asdict(self.usage),
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "validation": self.validation.to_dict(),
            "recovery": [item.to_dict() for item in self.recovery],
            "tool_calls": [asdict(item) for item in self.tool_calls],
            "warnings": list(self.warnings),
            "errors": [dict(item) for item in self.errors],
        }
