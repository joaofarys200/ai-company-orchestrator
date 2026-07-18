from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import dotenv_values


SUPPORTED_COMPRESSIONS = frozenset({"4bit", "8bit"})
_TRUE_VALUES = frozenset({"1", "true", "yes"})
_FALSE_VALUES = frozenset({"0", "false", "no"})


class AirLLMConfigurationError(ValueError):
    """Raised when the experimental AirLLM configuration is invalid."""


def _required_text(values: Mapping[str, object], name: str) -> str:
    value = str(values.get(name) or "").strip()
    if not value:
        raise AirLLMConfigurationError(f"{name} must not be empty.")
    return value


def _positive_integer(values: Mapping[str, object], name: str, default: int) -> int:
    raw = str(values.get(name, default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise AirLLMConfigurationError(
            f"{name} must be a positive integer; received {raw!r}."
        ) from exc
    if value <= 0:
        raise AirLLMConfigurationError(
            f"{name} must be a positive integer; received {value}."
        )
    return value


def _temperature(values: Mapping[str, object], default: float = 0.0) -> float:
    raw = str(values.get("AIRLLM_TEMPERATURE", default)).strip()
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise AirLLMConfigurationError(
            f"AIRLLM_TEMPERATURE must be a number between 0 and 2; received {raw!r}."
        ) from exc
    if not math.isfinite(value) or not 0.0 <= value <= 2.0:
        raise AirLLMConfigurationError(
            f"AIRLLM_TEMPERATURE must be between 0 and 2; received {raw!r}."
        )
    return value


def parse_boolean(value: object, name: str) -> bool:
    normalized = str(value).strip().casefold()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    accepted = "true/false, 1/0, or yes/no"
    raise AirLLMConfigurationError(
        f"{name} must use one of {accepted}; received {value!r}."
    )


def _absolute_path(value: str, name: str) -> Path:
    if not value.strip():
        raise AirLLMConfigurationError(f"{name} must not be empty.")
    return Path(value).expanduser().resolve(strict=False)


def _optional_absolute_path(values: Mapping[str, object], name: str) -> Path | None:
    raw = str(values.get(name) or "").strip()
    return _absolute_path(raw, name) if raw else None


def _compression(values: Mapping[str, object]) -> str | None:
    raw = str(values.get("AIRLLM_COMPRESSION") or "none").strip().casefold()
    if raw in {"", "none", "null", "off"}:
        return None
    if raw not in SUPPORTED_COMPRESSIONS:
        accepted = ", ".join(["none", *sorted(SUPPORTED_COMPRESSIONS)])
        raise AirLLMConfigurationError(
            f"AIRLLM_COMPRESSION must be one of {accepted}; received {raw!r}."
        )
    return raw


@dataclass(frozen=True)
class AirLLMSettings:
    model: str
    shards_path: Path
    compression: str | None
    max_context: int
    max_new_tokens: int
    temperature: float
    profiling_mode: bool
    hf_home: Path | None = None
    huggingface_hub_cache: Path | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "AirLLMSettings":
        model = _required_text(values, "AIRLLM_MODEL")
        shards_path = _absolute_path(
            _required_text(values, "AIRLLM_SHARDS_PATH"),
            "AIRLLM_SHARDS_PATH",
        )
        max_context = _positive_integer(values, "AIRLLM_MAX_CONTEXT", 8192)
        max_new_tokens = _positive_integer(
            values, "AIRLLM_MAX_NEW_TOKENS", 256
        )
        if max_new_tokens > max_context:
            raise AirLLMConfigurationError(
                "AIRLLM_MAX_NEW_TOKENS must not exceed AIRLLM_MAX_CONTEXT "
                f"({max_new_tokens} > {max_context})."
            )
        return cls(
            model=model,
            shards_path=shards_path,
            compression=_compression(values),
            max_context=max_context,
            max_new_tokens=max_new_tokens,
            temperature=_temperature(values),
            profiling_mode=parse_boolean(
                values.get("AIRLLM_PROFILING_MODE", "false"),
                "AIRLLM_PROFILING_MODE",
            ),
            hf_home=_optional_absolute_path(values, "HF_HOME"),
            huggingface_hub_cache=_optional_absolute_path(
                values, "HUGGINGFACE_HUB_CACHE"
            ),
        )

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, object] | None = None,
        env_file: str | os.PathLike[str] | None = None,
    ) -> "AirLLMSettings":
        if environment is not None:
            return cls.from_mapping(environment)

        selected_env_file = (
            Path(env_file)
            if env_file is not None
            else Path(__file__).with_name(".env")
        )
        values: dict[str, object] = {}
        if selected_env_file.is_file():
            values.update({
                key: value
                for key, value in dotenv_values(selected_env_file).items()
                if value is not None
            })
        values.update(os.environ)
        return cls.from_mapping(values)

    def apply_cache_environment(self) -> None:
        if self.hf_home is not None:
            os.environ["HF_HOME"] = str(self.hf_home)
        if self.huggingface_hub_cache is not None:
            os.environ["HUGGINGFACE_HUB_CACHE"] = str(
                self.huggingface_hub_cache
            )

