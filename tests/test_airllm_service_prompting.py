from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from services.airllm_server.config import (
    AirLLMConfigurationError,
    AirLLMSettings,
)
from services.airllm_server.prompting import (
    AirLLMPromptError,
    chat_template_payload,
    fallback_chat_prompt,
    render_chat_prompt,
)
from services.airllm_server.smoke_test import (
    AirLLMCompatibilityError,
    build_model_load_kwargs,
    generation_kwargs,
    main,
    validate_airllm_version,
)


MESSAGES = [
    {"role": "system", "content": "Answer briefly."},
    {"role": "user", "content": "Say hello."},
]


def settings(tmp_path: Path, *, compression: str | None = "4bit") -> AirLLMSettings:
    return AirLLMSettings(
        model="Qwen/Qwen3-32B",
        shards_path=(tmp_path / "shards").resolve(),
        compression=compression,
        max_context=8192,
        max_new_tokens=256,
        temperature=0,
        profiling_mode=True,
    )


def test_valid_messages_become_chat_template_payload():
    assert chat_template_payload(MESSAGES) == MESSAGES


@pytest.mark.parametrize("role", ["tool", "developer", "function", ""])
def test_invalid_role_is_rejected(role: str):
    with pytest.raises(AirLLMPromptError, match="role"):
        chat_template_payload([{"role": role, "content": "content"}])


@pytest.mark.parametrize("content", ["", "   ", None, 123])
def test_empty_or_non_text_message_is_rejected(content: object):
    with pytest.raises(AirLLMPromptError, match="content"):
        chat_template_payload([{"role": "user", "content": content}])


def test_empty_message_collection_is_rejected():
    with pytest.raises(AirLLMPromptError, match="must not be empty"):
        chat_template_payload([])


def test_available_chat_template_is_used():
    class FakeTokenizer:
        chat_template = "fake-template"

        def __init__(self):
            self.received = None

        def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
            self.received = (messages, tokenize, add_generation_prompt)
            return "<templated-chat>"

    tokenizer = FakeTokenizer()

    rendered = render_chat_prompt(tokenizer, MESSAGES)

    assert rendered == "<templated-chat>"
    assert tokenizer.received == (MESSAGES, False, True)


def test_fallback_is_deterministic_without_chat_template():
    class FakeTokenizer:
        chat_template = None

    first = render_chat_prompt(FakeTokenizer(), MESSAGES)
    second = fallback_chat_prompt(MESSAGES)

    assert first == second
    assert first == (
        "SYSTEM:\nAnswer briefly.\n\n"
        "USER:\nSay hello.\n\n"
        "ASSISTANT:\n"
    )


def test_model_load_kwargs_match_documented_airllm_arguments(tmp_path: Path):
    def loader(
        model_name,
        *,
        layer_shards_saving_path,
        profiling_mode,
        compression,
    ):
        return model_name

    observed = build_model_load_kwargs(settings(tmp_path), loader)

    assert observed == {
        "layer_shards_saving_path": str((tmp_path / "shards").resolve()),
        "profiling_mode": True,
        "compression": "4bit",
    }


def test_none_compression_is_not_sent_to_loader(tmp_path: Path):
    def loader(model_name, *, layer_shards_saving_path, profiling_mode):
        return model_name

    observed = build_model_load_kwargs(
        settings(tmp_path, compression=None),
        loader,
    )

    assert "compression" not in observed


def test_unsupported_loader_argument_fails_clearly(tmp_path: Path):
    def incompatible_loader(model_name, *, layer_shards_saving_path):
        return model_name

    with pytest.raises(AirLLMCompatibilityError, match="profiling_mode"):
        build_model_load_kwargs(settings(tmp_path), incompatible_loader)


def test_loader_with_var_kwargs_accepts_documented_arguments(tmp_path: Path):
    def airllm_style_loader(model_name, *inputs, **kwargs):
        return model_name, inputs, kwargs

    observed = build_model_load_kwargs(settings(tmp_path), airllm_style_loader)

    assert set(observed) == {
        "compression",
        "layer_shards_saving_path",
        "profiling_mode",
    }


def test_generation_sampling_follows_temperature(tmp_path: Path):
    deterministic = generation_kwargs(settings(tmp_path))
    sampled_settings = AirLLMSettings(
        **{
            **settings(tmp_path).__dict__,
            "temperature": 0.7,
        }
    )
    sampled = generation_kwargs(sampled_settings)

    assert deterministic["do_sample"] is False
    assert "temperature" not in deterministic
    assert sampled["do_sample"] is True
    assert sampled["temperature"] == 0.7


def test_only_validated_airllm_version_is_accepted():
    validate_airllm_version("3.0.1")

    with pytest.raises(AirLLMCompatibilityError, match="3.0.1"):
        validate_airllm_version("3.1.0")


def test_configuration_failure_returns_nonzero_without_importing_heavy_modules(
    capsys,
):
    with patch.object(
        AirLLMSettings,
        "from_environment",
        side_effect=AirLLMConfigurationError("AIRLLM_MODEL must not be empty."),
    ), patch("builtins.__import__", wraps=builtins.__import__) as import_spy:
        exit_code = main()

    imported_roots = {
        call.args[0].partition(".")[0]
        for call in import_spy.call_args_list
        if call.args and isinstance(call.args[0], str)
    }
    assert exit_code != 0
    assert {"airllm", "torch"}.isdisjoint(imported_roots)
    assert "AIRLLM_MODEL must not be empty" in capsys.readouterr().err


def test_loading_experimental_modules_does_not_import_airllm_torch_or_cuda():
    module_names = [
        "services.airllm_server.config",
        "services.airllm_server.prompting",
        "services.airllm_server.smoke_test",
    ]
    for module_name in module_names:
        sys.modules.pop(module_name, None)

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        root_name = name.partition(".")[0]
        if root_name in {"airllm", "torch"}:
            raise AssertionError(f"Unexpected heavy import while loading module: {name}")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=guarded_import):
        for module_name in module_names:
            importlib.import_module(module_name)
