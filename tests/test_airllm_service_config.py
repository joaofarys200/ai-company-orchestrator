from __future__ import annotations

from pathlib import Path

import pytest

from services.airllm_server.config import (
    AirLLMConfigurationError,
    AirLLMSettings,
    parse_boolean,
)


def valid_values(tmp_path: Path) -> dict[str, str]:
    return {
        "AIRLLM_MODEL": "Qwen/Qwen3-32B",
        "AIRLLM_SHARDS_PATH": str(tmp_path / "shards"),
        "AIRLLM_COMPRESSION": "4bit",
        "AIRLLM_MAX_CONTEXT": "8192",
        "AIRLLM_MAX_NEW_TOKENS": "256",
        "AIRLLM_TEMPERATURE": "0",
        "AIRLLM_PROFILING_MODE": "true",
        "HF_HOME": str(tmp_path / "huggingface"),
        "HUGGINGFACE_HUB_CACHE": str(tmp_path / "huggingface" / "hub"),
    }


def test_valid_configuration(tmp_path: Path):
    settings = AirLLMSettings.from_mapping(valid_values(tmp_path))

    assert settings.model == "Qwen/Qwen3-32B"
    assert settings.shards_path == (tmp_path / "shards").resolve()
    assert settings.compression == "4bit"
    assert settings.max_context == 8192
    assert settings.max_new_tokens == 256
    assert settings.temperature == 0
    assert settings.profiling_mode is True
    assert settings.hf_home == (tmp_path / "huggingface").resolve()
    assert settings.huggingface_hub_cache == (
        tmp_path / "huggingface" / "hub"
    ).resolve()


@pytest.mark.parametrize("model", ["", "   "])
def test_model_must_not_be_empty(tmp_path: Path, model: str):
    values = valid_values(tmp_path)
    values["AIRLLM_MODEL"] = model

    with pytest.raises(AirLLMConfigurationError, match="AIRLLM_MODEL"):
        AirLLMSettings.from_mapping(values)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("AIRLLM_MAX_CONTEXT", "not-an-integer"),
        ("AIRLLM_MAX_NEW_TOKENS", "2.5"),
    ],
)
def test_invalid_integer_is_rejected(tmp_path: Path, name: str, value: str):
    values = valid_values(tmp_path)
    values[name] = value

    with pytest.raises(AirLLMConfigurationError, match=name):
        AirLLMSettings.from_mapping(values)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_context_limit_must_be_positive(tmp_path: Path, value: str):
    values = valid_values(tmp_path)
    values["AIRLLM_MAX_CONTEXT"] = value

    with pytest.raises(AirLLMConfigurationError, match="AIRLLM_MAX_CONTEXT"):
        AirLLMSettings.from_mapping(values)


def test_max_new_tokens_cannot_exceed_context(tmp_path: Path):
    values = valid_values(tmp_path)
    values["AIRLLM_MAX_CONTEXT"] = "128"
    values["AIRLLM_MAX_NEW_TOKENS"] = "129"

    with pytest.raises(
        AirLLMConfigurationError,
        match="must not exceed AIRLLM_MAX_CONTEXT",
    ):
        AirLLMSettings.from_mapping(values)


@pytest.mark.parametrize("value", ["-0.01", "2.01", "nan", "infinite"])
def test_temperature_outside_range_is_rejected(tmp_path: Path, value: str):
    values = valid_values(tmp_path)
    values["AIRLLM_TEMPERATURE"] = value

    with pytest.raises(AirLLMConfigurationError, match="AIRLLM_TEMPERATURE"):
        AirLLMSettings.from_mapping(values)


@pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes", "YeS"])
def test_true_boolean_values(value: str):
    assert parse_boolean(value, "SETTING") is True


@pytest.mark.parametrize("value", ["false", "FALSE", "0", "no", "No"])
def test_false_boolean_values(value: str):
    assert parse_boolean(value, "SETTING") is False


@pytest.mark.parametrize("value", ["on", "off", "maybe", "", "2"])
def test_invalid_boolean_values(value: str):
    with pytest.raises(AirLLMConfigurationError, match="SETTING"):
        parse_boolean(value, "SETTING")


def test_shards_path_is_normalized_to_absolute(tmp_path: Path):
    values = valid_values(tmp_path)
    values["AIRLLM_SHARDS_PATH"] = str(tmp_path / "nested" / ".." / "shards")

    settings = AirLLMSettings.from_mapping(values)

    assert settings.shards_path.is_absolute()
    assert settings.shards_path == (tmp_path / "shards").resolve()


@pytest.mark.parametrize("value", ["3bit", "4", "int4", "gzip"])
def test_undocumented_compression_is_rejected(tmp_path: Path, value: str):
    values = valid_values(tmp_path)
    values["AIRLLM_COMPRESSION"] = value

    with pytest.raises(AirLLMConfigurationError, match="AIRLLM_COMPRESSION"):
        AirLLMSettings.from_mapping(values)


@pytest.mark.parametrize("value", ["", "none", "None", "off"])
def test_no_compression_values_are_normalized(tmp_path: Path, value: str):
    values = valid_values(tmp_path)
    values["AIRLLM_COMPRESSION"] = value

    assert AirLLMSettings.from_mapping(values).compression is None

