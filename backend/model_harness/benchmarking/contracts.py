from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class BenchmarkMode(str, Enum):
    SMOKE = "smoke"
    STANDARD = "standard"
    FULL = "full"


class ScenarioGroup(str, Enum):
    TOOL_LOOP = "A"
    STATE_RETENTION = "B"
    PROJECT_REASONING = "C"
    CONTEXT_SCALING = "D"
    RECOVERY = "E"
    SHORT_PLANNING = "F"
    CLOSED_RESEARCH = "G"


class ScenarioStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_DEGRADATION = "PASS_WITH_DEGRADATION"
    FAIL = "FAIL"
    INVALID = "INVALID"


class CapabilityStatus(str, Enum):
    DEMONSTRATED_PRELIMINARY = "DEMONSTRATED_PRELIMINARY"
    DEMONSTRATED = "DEMONSTRATED"
    DEGRADED = "DEGRADED"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
    FAILED = "FAILED"


class StopReason(str, Enum):
    COMPLETED = "COMPLETED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    NO_PROGRESS = "NO_PROGRESS"
    REPEATED_TOOL_CALL = "REPEATED_TOOL_CALL"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    RECOVERY_EXHAUSTED = "RECOVERY_EXHAUSTED"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    TOOL_FAILED = "TOOL_FAILED"
    MAX_STEPS_REACHED = "MAX_STEPS_REACHED"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    UNSUPPORTED_CONCLUSION = "UNSUPPORTED_CONCLUSION"


class ToolStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Constraint:
    constraint_id: str
    text: str

    def __post_init__(self) -> None:
        if not self.constraint_id.strip() or not self.text.strip():
            raise ValueError("Constraint requer id e texto.")


@dataclass(frozen=True)
class FixtureFile:
    path: str
    content: str


@dataclass(frozen=True)
class FixtureSpec:
    fixture_id: str
    files: tuple[FixtureFile, ...]
    index_entries: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        paths = [item.path for item in self.files]
        if not self.fixture_id.strip():
            raise ValueError("FixtureSpec.fixture_id e obrigatorio.")
        if len(paths) != len(set(paths)):
            raise ValueError(f"Fixture com paths duplicados: {self.fixture_id}.")

    @property
    def content_sha256(self) -> str:
        payload = {
            "fixture_id": self.fixture_id,
            "files": [
                {"path": item.path, "content": item.content}
                for item in self.files
            ],
            "index_entries": {
                key: list(value)
                for key, value in sorted(self.index_entries.items())
            },
        }
        return sha256_json(payload)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: Mapping[str, Any]
    read_only: bool = True

    def public_contract(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": dict(self.input_schema),
            "read_only": self.read_only,
        }


@dataclass(frozen=True)
class ToolRequest:
    scenario_id: str
    step_number: int
    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class ToolObservation:
    tool_name: str
    status: ToolStatus
    result: Mapping[str, Any]
    references: tuple[str, ...]
    result_sha256: str
    summary: str
    error_code: str = ""
    raw_context: str = field(default="", repr=False, compare=False)

    def report_view(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "result": dict(self.result),
            "references": list(self.references),
            "result_sha256": self.result_sha256,
            "summary": self.summary,
            "error_code": self.error_code,
        }


@dataclass(frozen=True)
class PlanStep:
    step: str
    required_evidence: tuple[str, ...]
    dependencies: tuple[str, ...]
    completion_condition: str
    negative_constraints: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> PlanStep:
        return cls(
            step=str(value.get("step") or "").strip(),
            required_evidence=tuple(
                str(item).strip()
                for item in value.get("required_evidence") or ()
                if str(item).strip()
            ),
            dependencies=tuple(
                str(item).strip()
                for item in value.get("dependencies") or ()
                if str(item).strip()
            ),
            completion_condition=str(
                value.get("completion_condition") or ""
            ).strip(),
            negative_constraints=tuple(
                str(item).strip()
                for item in value.get("negative_constraints") or ()
                if str(item).strip()
            ),
        )


@dataclass(frozen=True)
class ModelDecision:
    decision: str
    tool_name: str
    arguments: Mapping[str, Any]
    conclusion: str
    stop_reason: str
    evidence_refs: tuple[str, ...]
    retained_constraint_ids: tuple[str, ...]
    plan: tuple[PlanStep, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ModelDecision:
        if not isinstance(value, Mapping):
            raise TypeError("Decisao do modelo deve ser um objeto.")
        return cls(
            decision=str(value.get("decision") or "").strip().upper(),
            tool_name=str(value.get("tool_name") or "").strip(),
            arguments=(
                dict(value.get("arguments"))
                if isinstance(value.get("arguments"), Mapping)
                else {}
            ),
            conclusion=str(value.get("conclusion") or "").strip(),
            stop_reason=str(value.get("stop_reason") or "").strip().upper(),
            evidence_refs=tuple(
                str(item).strip()
                for item in value.get("evidence_refs") or ()
                if str(item).strip()
            ),
            retained_constraint_ids=tuple(
                str(item).strip()
                for item in value.get("retained_constraint_ids") or ()
                if str(item).strip()
            ),
            plan=tuple(
                PlanStep.from_mapping(item)
                for item in value.get("plan") or ()
                if isinstance(item, Mapping)
            ),
        )

    @property
    def output_sha256(self) -> str:
        return sha256_json({
            "decision": self.decision,
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "conclusion": self.conclusion,
            "stop_reason": self.stop_reason,
            "evidence_refs": list(self.evidence_refs),
            "retained_constraint_ids": list(
                self.retained_constraint_ids
            ),
            "plan": [asdict(item) for item in self.plan],
        })


@dataclass(frozen=True)
class ExpectedTransition:
    allowed_tools: tuple[str, ...]
    allow_finish: bool
    minimum_evidence: int = 0
    require_new_evidence: bool = True


@dataclass(frozen=True)
class StopCondition:
    reason: StopReason
    description: str


@dataclass(frozen=True)
class BenchmarkStep:
    scenario_id: str
    step_number: int
    objective: str
    constraints: tuple[Constraint, ...]
    available_tools: tuple[str, ...]
    transition: ExpectedTransition


@dataclass(frozen=True)
class BenchmarkScenario:
    scenario_id: str
    title: str
    group: ScenarioGroup
    capability: str
    objective: str
    constraints: tuple[Constraint, ...]
    fixture: FixtureSpec
    available_tools: tuple[str, ...]
    max_steps: int
    expected_stop_reason: StopReason
    required_tools: tuple[str, ...] = ()
    required_references: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    minimum_evidence: int = 1
    evaluator: str = "default"
    context_target_tokens: int = 0
    smoke: bool = False
    fault_injection: str = ""
    variant: int = 1

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError("BenchmarkScenario.max_steps deve ser positivo.")
        if not self.scenario_id.strip() or not self.objective.strip():
            raise ValueError("Scenario requer id e objetivo.")
        if "finish" not in self.available_tools:
            raise ValueError("Todos os cenarios devem permitir finish.")


@dataclass
class StatefulContext:
    objective: str
    constraints: tuple[Constraint, ...]
    observations: list[ToolObservation] = field(default_factory=list)
    decisions: list[ModelDecision] = field(default_factory=list)
    known_references: set[str] = field(default_factory=set)
    context_hashes: list[str] = field(default_factory=list)
    no_new_evidence_steps: int = 0

    def add_observation(self, observation: ToolObservation) -> bool:
        existing = {item.result_sha256 for item in self.observations}
        is_new = observation.result_sha256 not in existing
        self.observations.append(observation)
        self.known_references.update(observation.references)
        self.no_new_evidence_steps = (
            0 if is_new else self.no_new_evidence_steps + 1
        )
        return is_new


@dataclass(frozen=True)
class StepResult:
    scenario_id: str
    repetition: int
    step_number: int
    objective: str
    current_constraints: tuple[str, ...]
    available_tools: tuple[str, ...]
    selected_tool: str
    tool_arguments: Mapping[str, Any]
    normalized_observation: Mapping[str, Any] | None
    model_output_hash: str
    context_hash: str
    context_chars: int
    context_items: int
    context_decisions: tuple[Mapping[str, Any], ...]
    validation_result: Mapping[str, Any]
    progress_result: Mapping[str, Any]
    recovery_result: tuple[Mapping[str, Any], ...]
    stop_reason: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    tokens_per_second: float | None
    request_fingerprint: str
    tool_result_hash: str = ""


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    repetition: int
    group: str
    capability: str
    status: ScenarioStatus
    stop_reason: StopReason
    step_count: int
    final_conclusion: str
    evidence_refs: tuple[str, ...]
    tools_called: tuple[str, ...]
    retained_constraints: tuple[str, ...]
    plan_steps: int
    criteria: tuple[Mapping[str, Any], ...]
    total_latency_ms: int
    input_tokens: int
    output_tokens: int
    response_hashes: tuple[str, ...]
    context_range_chars: tuple[int, int]
    recovery_used: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class CapabilityResult:
    capability: str
    status: CapabilityStatus
    confidence: float
    passed_cases: int
    failed_cases: int
    total_cases: int
    total_calls: int
    repetitions: int
    mean_latency_ms: float
    p95_latency_ms: float
    context_range: tuple[int, int]
    recovery_used: bool
    limitations: tuple[str, ...]
    configuration_hash: str


@dataclass(frozen=True)
class BenchmarkConfig:
    mode: BenchmarkMode
    model: str
    output_dir: str
    repetitions: int
    seed: int
    context_tokens: int
    max_steps: int
    keep_alive: str
    timeout_seconds: float
    temperature: float = 0.0
    top_p: float = 0.8
    think: bool = False
    stream: bool = False
    max_output_tokens: int = 1_024
    base_url: str = "http://127.0.0.1:11434"
    fault_injection: bool = True
    debug_prompts: bool = False

    def __post_init__(self) -> None:
        if self.repetitions < 1:
            raise ValueError("repetitions deve ser positivo.")
        if self.context_tokens < 1 or self.max_steps < 1:
            raise ValueError("context_tokens e max_steps devem ser positivos.")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout deve ser positivo.")

    @property
    def configuration_hash(self) -> str:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        payload.pop("output_dir", None)
        payload.pop("debug_prompts", None)
        return sha256_json(payload)


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
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list, set)):
        return [to_jsonable(item) for item in value]
    return value


def sha256_json(value: Any) -> str:
    encoded = json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
