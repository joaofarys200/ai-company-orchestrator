from __future__ import annotations

import platform
import sys
import traceback
from dataclasses import dataclass, field
from typing import Mapping, TextIO


PHASES = (
    "configuration",
    "imports",
    "cuda_check",
    "path_preparation",
    "model_configuration_download",
    "model_loading_or_sharding",
    "tokenizer_loading",
    "prompt_rendering",
    "tokenization",
    "generation",
    "decoding",
)

_SENSITIVE_FRAGMENTS = ("token", "secret", "password", "credential")


def sanitize_kwargs(values: Mapping[str, object]) -> dict[str, object]:
    """Return diagnostic kwargs without exposing credential-like values."""
    return {
        str(key): (
            "<redacted>"
            if any(fragment in str(key).casefold() for fragment in _SENSITIVE_FRAGMENTS)
            else value
        )
        for key, value in values.items()
    }


@dataclass
class DiagnosticState:
    phase: str = PHASES[0]
    python_version: str = field(default_factory=platform.python_version)
    airllm_version: str = "unavailable"
    torch_version: str = "unavailable"
    architecture: str = "unavailable"
    load_kwargs: dict[str, object] = field(default_factory=dict)

    def set_phase(self, phase: str) -> None:
        if phase not in PHASES:
            raise ValueError(f"Unknown AirLLM smoke-test phase: {phase!r}.")
        self.phase = phase


def emit_failure(
    exc: BaseException,
    state: DiagnosticState,
    *,
    diagnostic_mode: bool,
    stream: TextIO | None = None,
) -> None:
    """Emit either the legacy short failure or the bounded diagnostic report."""
    output = stream or sys.stderr
    print(
        f"AirLLM smoke test failed: {type(exc).__name__}: {exc}",
        file=output,
    )
    if not diagnostic_mode:
        return

    print("AirLLM diagnostic details:", file=output)
    print(f"Failure phase: {state.phase}", file=output)
    print(f"Exception type: {type(exc).__name__}", file=output)
    print(f"Exception repr: {exc!r}", file=output)
    print(f"Python version: {state.python_version}", file=output)
    print(f"AirLLM version: {state.airllm_version}", file=output)
    print(f"Torch version: {state.torch_version}", file=output)
    print(f"Declared architecture: {state.architecture}", file=output)
    print(
        f"Model load kwargs: {sanitize_kwargs(state.load_kwargs)!r}",
        file=output,
    )
    print("Full traceback:", file=output)
    traceback.print_exception(type(exc), exc, exc.__traceback__, file=output)
