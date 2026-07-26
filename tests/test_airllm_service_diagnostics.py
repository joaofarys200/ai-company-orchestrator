from __future__ import annotations

import io
from unittest.mock import patch

import pytest

from services.airllm_server.diagnostics import (
    DiagnosticState,
    emit_failure,
    sanitize_kwargs,
)
from services.airllm_server.config import AirLLMConfigurationError, AirLLMSettings
from services.airllm_server.smoke_test import main


def _render_failure(*, diagnostic_mode: bool) -> str:
    state = DiagnosticState(
        phase="model_loading_or_sharding",
        python_version="3.11.test",
        airllm_version="3.0.1",
        torch_version="2.11.0+cu128",
        architecture="Qwen3_5MoeForConditionalGeneration",
        load_kwargs={"compression": "4bit", "hf_token": "never-print-this"},
    )
    stream = io.StringIO()
    try:
        raise ValueError("invalid literal for int() with base 10: 'layers'")
    except ValueError as exc:
        emit_failure(
            exc,
            state,
            diagnostic_mode=diagnostic_mode,
            stream=stream,
        )
    return stream.getvalue()


def test_diagnostic_mode_off_preserves_short_output_without_traceback():
    output = _render_failure(diagnostic_mode=False)

    assert output == (
        "AirLLM smoke test failed: ValueError: "
        "invalid literal for int() with base 10: 'layers'\n"
    )
    assert "Traceback" not in output
    assert "Failure phase" not in output


def test_diagnostic_mode_on_reports_phase_versions_kwargs_and_traceback():
    output = _render_failure(diagnostic_mode=True)

    assert "Failure phase: model_loading_or_sharding" in output
    assert "Exception type: ValueError" in output
    assert "Exception repr: ValueError(" in output
    assert "Python version: 3.11.test" in output
    assert "AirLLM version: 3.0.1" in output
    assert "Torch version: 2.11.0+cu128" in output
    assert "Declared architecture: Qwen3_5MoeForConditionalGeneration" in output
    assert "'compression': '4bit'" in output
    assert "Full traceback:\nTraceback (most recent call last):" in output
    assert "raise ValueError" in output
    assert "never-print-this" not in output
    assert "<redacted>" in output


def test_failure_phase_is_validated_and_retained():
    state = DiagnosticState()

    state.set_phase("generation")

    assert state.phase == "generation"
    with pytest.raises(ValueError, match="Unknown AirLLM smoke-test phase"):
        state.set_phase("weight_guessing")


def test_sensitive_kwarg_names_are_redacted():
    sanitized = sanitize_kwargs(
        {
            "hf_token": "secret-token",
            "api_password": "secret-password",
            "compression": "4bit",
        }
    )

    assert sanitized == {
        "hf_token": "<redacted>",
        "api_password": "<redacted>",
        "compression": "4bit",
    }


def test_configuration_failure_is_attributed_without_heavy_imports(
    capsys,
    monkeypatch,
):
    monkeypatch.setenv("AIRLLM_DIAGNOSTIC_MODE", "true")
    with patch.object(
        AirLLMSettings,
        "from_environment",
        side_effect=AirLLMConfigurationError("bad configuration"),
    ):
        exit_code = main()

    output = capsys.readouterr().err
    assert exit_code == 1
    assert "Failure phase: configuration" in output
    assert "Full traceback:" in output
