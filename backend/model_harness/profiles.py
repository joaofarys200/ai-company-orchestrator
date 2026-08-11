from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from backend.model_harness.contracts import ExpectedOutput, OutputFormat
from backend.model_harness.errors import (
    DuplicateTaskProfileError,
    UnknownTaskProfileError,
)


TASK_PROFILE_NAMES = {
    "LOCAL_CHOICE",
    "STRUCTURED_EXTRACTION",
    "TOOL_SELECTION",
    "CODE_REASONING",
    "MISSION_PLANNING",
    "RESEARCH",
    "DOCUMENT",
    "DOCUMENT_REVIEW",
}


@dataclass(frozen=True)
class TaskProfile:
    name: str
    temperature: float
    max_context_tokens: int
    max_output_tokens: int
    expected_output: ExpectedOutput
    validation_pipeline: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    recovery_policy: str
    preferred_providers: tuple[str, ...] = ()
    preferred_models: tuple[str, ...] = ()
    streaming: bool = False
    thinking: bool = False

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("TaskProfile.name e obrigatorio.")
        if not 0 <= self.temperature <= 2:
            raise ValueError("TaskProfile.temperature deve estar entre 0 e 2.")
        if self.max_context_tokens < 1 or self.max_output_tokens < 1:
            raise ValueError("Os limites de tokens devem ser positivos.")
        if not self.validation_pipeline:
            raise ValueError("TaskProfile requer um pipeline de validacao.")
        if not str(self.recovery_policy or "").strip():
            raise ValueError("TaskProfile requer uma recovery_policy.")

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["expected_output"]["format"] = (
            self.expected_output.format.value
        )
        return payload


class TaskProfileRegistry:
    def __init__(self, profiles: Iterable[TaskProfile] | None = None):
        self._profiles: dict[str, TaskProfile] = {}
        for profile in profiles or ():
            self.register(profile)

    def register(self, profile: TaskProfile) -> None:
        name = self._normalize(profile.name)
        if name in self._profiles:
            raise DuplicateTaskProfileError(
                f"Task profile ja registado: {name}."
            )
        if profile.name != name:
            raise ValueError(
                "TaskProfile.name deve estar normalizado em maiusculas."
            )
        self._profiles[name] = profile

    def get(self, name: str) -> TaskProfile:
        normalized = self._normalize(name)
        try:
            return self._profiles[normalized]
        except KeyError as exc:
            raise UnknownTaskProfileError(
                f"Task profile desconhecido: {normalized}."
            ) from exc

    def describe(self) -> dict[str, dict]:
        return {
            name: profile.to_dict()
            for name, profile in self._profiles.items()
        }

    @staticmethod
    def _normalize(name: str) -> str:
        normalized = str(name or "").strip().upper()
        if not normalized:
            raise UnknownTaskProfileError("Task profile vazio.")
        return normalized


def create_default_task_profile_registry() -> TaskProfileRegistry:
    structured_stages = (
        "PARSING",
        "SCHEMA",
        "ENUMS",
        "REFERENCES",
        "PRECONDITIONS",
        "COMPATIBILITY",
        "ACCEPTANCE_CRITERIA",
    )
    text_stages = (
        "COMPATIBILITY",
        "ACCEPTANCE_CRITERIA",
    )
    profiles = (
        TaskProfile(
            name="LOCAL_CHOICE",
            temperature=0.0,
            max_context_tokens=8_192,
            max_output_tokens=512,
            expected_output=ExpectedOutput(format=OutputFormat.JSON),
            validation_pipeline=structured_stages,
            allowed_tools=(),
            recovery_policy="STRUCTURED_CONSERVATIVE",
            preferred_providers=("ollama",),
        ),
        TaskProfile(
            name="STRUCTURED_EXTRACTION",
            temperature=0.0,
            max_context_tokens=32_768,
            max_output_tokens=16_384,
            expected_output=ExpectedOutput(format=OutputFormat.JSON),
            validation_pipeline=structured_stages,
            allowed_tools=(),
            recovery_policy="STRUCTURED_CONSERVATIVE",
        ),
        TaskProfile(
            name="TOOL_SELECTION",
            temperature=0.0,
            max_context_tokens=32_768,
            max_output_tokens=4_096,
            expected_output=ExpectedOutput(format=OutputFormat.TOOL_CALLS),
            validation_pipeline=structured_stages,
            allowed_tools=("*",),
            recovery_policy="STRUCTURED_CONSERVATIVE",
        ),
        TaskProfile(
            name="CODE_REASONING",
            temperature=0.1,
            max_context_tokens=32_768,
            max_output_tokens=8_192,
            expected_output=ExpectedOutput(format=OutputFormat.TEXT),
            validation_pipeline=text_stages,
            allowed_tools=(),
            recovery_policy="SEMANTIC_CONSERVATIVE",
        ),
        TaskProfile(
            name="MISSION_PLANNING",
            temperature=0.0,
            max_context_tokens=32_768,
            max_output_tokens=8_192,
            expected_output=ExpectedOutput(format=OutputFormat.JSON),
            validation_pipeline=structured_stages,
            allowed_tools=(),
            recovery_policy="STRUCTURED_CONSERVATIVE",
        ),
        TaskProfile(
            name="RESEARCH",
            temperature=0.2,
            max_context_tokens=32_768,
            max_output_tokens=8_192,
            expected_output=ExpectedOutput(format=OutputFormat.TEXT),
            validation_pipeline=text_stages,
            allowed_tools=(),
            recovery_policy="SEMANTIC_CONSERVATIVE",
        ),
        TaskProfile(
            name="DOCUMENT",
            temperature=0.3,
            max_context_tokens=32_768,
            max_output_tokens=12_288,
            expected_output=ExpectedOutput(format=OutputFormat.TEXT),
            validation_pipeline=text_stages,
            allowed_tools=(),
            recovery_policy="SEMANTIC_CONSERVATIVE",
        ),
        TaskProfile(
            name="DOCUMENT_REVIEW",
            temperature=0.1,
            max_context_tokens=32_768,
            max_output_tokens=8_192,
            expected_output=ExpectedOutput(format=OutputFormat.JSON),
            validation_pipeline=structured_stages,
            allowed_tools=(),
            recovery_policy="STRUCTURED_CONSERVATIVE",
        ),
    )
    return TaskProfileRegistry(profiles)
