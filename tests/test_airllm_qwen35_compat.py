from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.airllm_server.compat.qwen35 import (
    QWEN35_ARCHITECTURE,
    Qwen35CompatibilityError,
    classify_parameter_key,
    maybe_enable_patch,
    validate_parameter_keys,
)


CORE_KEYS = [
    "model.language_model.embed_tokens.weight",
    "model.language_model.layers.0.input_layernorm.weight",
    "model.language_model.layers.1.post_attention_layernorm.weight",
    "model.language_model.norm.weight",
    "lm_head.weight",
]


@pytest.mark.parametrize(
    ("key", "category", "index"),
    [
        ("model.language_model.embed_tokens.weight", "embedding", None),
        ("model.language_model.layers.12.input_layernorm.weight", "block", 12),
        ("model.language_model.norm.weight", "final_norm", None),
        ("lm_head.weight", "lm_head", None),
        (
            "model.language_model.layers.7.mlp.experts.gate_up_proj",
            "block",
            7,
        ),
        (
            "model.language_model.layers.8.linear_attn.conv1d.weight",
            "block",
            8,
        ),
        ("model.visual.blocks.0.attn.qkv.weight", "visual_unstreamed", None),
        ("mtp.layers.0.self_attn.q_proj.weight", "mtp_unstreamed", None),
    ],
)
def test_known_qwen35_keys_are_classified_strictly(key, category, index):
    assert classify_parameter_key(key) == (category, index)


@pytest.mark.parametrize(
    "key",
    [
        "model.language_model.layers.layers.0.self_attn.q_proj.weight",
        "model.language_model.layers.+1.self_attn.q_proj.weight",
        "model.language_model.layers.01.self_attn.q_proj.weight",
        "model.language_model.layers.-1.self_attn.q_proj.weight",
    ],
)
def test_non_decimal_layer_index_segments_are_rejected(key: str):
    with pytest.raises(Qwen35CompatibilityError, match="layer index segment"):
        classify_parameter_key(key)


def test_unknown_parameter_fails_instead_of_being_ignored():
    with pytest.raises(Qwen35CompatibilityError, match="Unclassified"):
        classify_parameter_key("model.some_future_module.weight")


def test_full_key_validation_requires_contiguous_declared_layers():
    counts = validate_parameter_keys(CORE_KEYS, expected_layer_count=2)

    assert counts["block"] == 2

    with pytest.raises(Qwen35CompatibilityError, match=r"missing=\[1\]"):
        validate_parameter_keys(
            [key for key in CORE_KEYS if ".layers.1." not in key],
            expected_layer_count=2,
        )


def test_patch_off_does_not_download_or_modify_modules():
    class FakeAirLLM:
        class AirLLMBaseModel:
            pass

    class FakeAutoModelModule:
        ARCH_OVERRIDES = {}

    def forbidden_download(_model_ref: str) -> str:
        raise AssertionError("Patch-off path must not inspect remote metadata.")

    result = maybe_enable_patch(
        enabled=False,
        model_ref="Qwen/Qwen3.5-35B-A3B",
        architecture=QWEN35_ARCHITECTURE,
        expected_layer_count=40,
        index_downloader=forbidden_download,
        airllm_module=FakeAirLLM,
        auto_model_module=FakeAutoModelModule,
    )

    assert result is None
    assert FakeAutoModelModule.ARCH_OVERRIDES == {}
    assert not hasattr(FakeAirLLM, "AirLLMQwen35Experimental")


def test_patch_on_validates_index_then_installs_local_override(
    tmp_path: Path,
):
    index_path = tmp_path / "model.safetensors.index.json"
    index_path.write_text(
        json.dumps({"weight_map": {key: "shard.safetensors" for key in CORE_KEYS}}),
        encoding="utf-8",
    )

    class FakeAirLLM:
        class AirLLMBaseModel:
            pass

    class FakeAutoModelModule:
        ARCH_OVERRIDES = {}

    with pytest.warns(RuntimeWarning, match="EXPERIMENTAL"):
        counts = maybe_enable_patch(
            enabled=True,
            model_ref="fake/repo",
            architecture=QWEN35_ARCHITECTURE,
            expected_layer_count=2,
            index_downloader=lambda _model_ref: str(index_path),
            airllm_module=FakeAirLLM,
            auto_model_module=FakeAutoModelModule,
        )

    assert counts is not None
    assert FakeAutoModelModule.ARCH_OVERRIDES[QWEN35_ARCHITECTURE] == (
        "AirLLMQwen35Experimental"
    )
    instance = FakeAirLLM.AirLLMQwen35Experimental()
    instance.set_layer_names_dict()
    assert instance.layer_names_dict["layer_prefix"] == (
        "model.language_model.layers"
    )


def test_patch_rejects_unclassified_key_before_modifying_runtime(tmp_path: Path):
    index_path = tmp_path / "model.safetensors.index.json"
    keys = [*CORE_KEYS, "model.unknown.weight"]
    index_path.write_text(
        json.dumps({"weight_map": {key: "shard.safetensors" for key in keys}}),
        encoding="utf-8",
    )

    class FakeAirLLM:
        class AirLLMBaseModel:
            pass

    class FakeAutoModelModule:
        ARCH_OVERRIDES = {}

    with pytest.raises(Qwen35CompatibilityError, match="Unclassified"):
        maybe_enable_patch(
            enabled=True,
            model_ref="fake/repo",
            architecture=QWEN35_ARCHITECTURE,
            expected_layer_count=2,
            index_downloader=lambda _model_ref: str(index_path),
            airllm_module=FakeAirLLM,
            auto_model_module=FakeAutoModelModule,
        )

    assert FakeAutoModelModule.ARCH_OVERRIDES == {}
