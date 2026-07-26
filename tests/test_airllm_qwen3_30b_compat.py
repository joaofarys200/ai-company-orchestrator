from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from accelerate import init_empty_weights
from airllm.airllm_base import AirLLMBaseModel
from airllm.auto_model import ARCH_OVERRIDES, AutoModel
from transformers import Qwen3MoeConfig, Qwen3MoeForCausalLM


ARCHITECTURE = "Qwen3MoeForCausalLM"
CHECKPOINT_KEYS = {
    "model.embed_tokens.weight",
    "model.layers.0.input_layernorm.weight",
    "model.layers.0.mlp.experts.0.gate_proj.weight",
    "model.layers.0.mlp.experts.0.up_proj.weight",
    "model.layers.0.mlp.experts.0.down_proj.weight",
    "model.layers.0.mlp.gate.weight",
    "model.layers.0.self_attn.q_proj.weight",
    "model.norm.weight",
    "lm_head.weight",
}


def test_qwen3_moe_uses_the_official_generic_airllm_dispatch() -> None:
    config = SimpleNamespace(architectures=[ARCHITECTURE])

    with patch("airllm.auto_model.AutoConfig.from_pretrained", return_value=config):
        module_name, class_name = AutoModel.get_module_class(
            "Qwen/Qwen3-30B-A3B"
        )

    assert ARCHITECTURE not in ARCH_OVERRIDES
    assert (module_name, class_name) == ("airllm", "AirLLMBaseModel")


def test_checkpoint_top_level_layout_matches_generic_airllm_prefixes() -> None:
    model = AirLLMBaseModel.__new__(AirLLMBaseModel)
    model.set_layer_names_dict()

    assert model.layer_names_dict == {
        "embed": "model.embed_tokens",
        "layer_prefix": "model.layers",
        "norm": "model.norm",
        "lm_head": "lm_head",
    }
    assert not any(key.startswith("model.language_model.") for key in CHECKPOINT_KEYS)
    assert not any(key.startswith("model.visual.") for key in CHECKPOINT_KEYS)
    assert not any(key.startswith("mtp.") for key in CHECKPOINT_KEYS)


def test_transformers_512_packs_experts_but_checkpoint_names_are_per_expert() -> None:
    config = Qwen3MoeConfig(
        vocab_size=128,
        hidden_size=64,
        intermediate_size=128,
        moe_intermediate_size=32,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=2,
        head_dim=16,
        num_experts=4,
        num_experts_per_tok=2,
    )
    with init_empty_weights(include_buffers=False):
        model = Qwen3MoeForCausalLM(config)

    parameter_names = dict(model.named_parameters())
    assert "model.layers.0.mlp.experts.gate_up_proj" in parameter_names
    assert "model.layers.0.mlp.experts.down_proj" in parameter_names
    assert "model.layers.0.mlp.experts.0.gate_proj.weight" not in parameter_names
    assert "model.layers.0.mlp.experts.0.up_proj.weight" not in parameter_names
    assert "model.layers.0.mlp.experts.0.down_proj.weight" not in parameter_names
