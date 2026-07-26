from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .phase18_validation import (
    ADVERSARIAL_INSTRUCTIONS,
    MODEL_ID,
    evaluate_plan_text,
    orchestration_messages,
    safe_environment_summary,
    validate_phase18_environment,
)
from .prompting import render_chat_prompt
from .smoke_test import generation_kwargs, validate_airllm_version, validate_loader_kwargs
from .config import AirLLMSettings


_LAST_OBSERVATION: RuntimeObservation | None = None


SMOKE_MESSAGES = [
    {"role": "system", "content": "Responde apenas com a resposta pedida, sem explicações."},
    {"role": "user", "content": "Responde apenas com uma frase curta: qual é a capital de Portugal?"},
]


@dataclass
class RuntimeObservation:
    phase: str = "configuration"
    generation_started: float | None = None
    first_layer_started: float | None = None
    first_token_at: float | None = None
    last_layer_started: int | None = None
    last_layer_completed: int | None = None
    last_unit_loaded: str | None = None
    last_parameter: str | None = None
    expected_shape: tuple[int, ...] | None = None
    received_shape: tuple[int, ...] | None = None
    received_dtype: str | None = None
    target_device: str | None = None
    unit_visits: dict[str, int] = field(default_factory=dict)

    def visit(self, unit: str) -> None:
        self.unit_visits[unit] = self.unit_visits.get(unit, 0) + 1


class TimingStreamer:
    def __init__(self, observation: RuntimeObservation):
        self.observation = observation
        self._prompt_seen = False

    def put(self, value: object) -> None:
        if not self._prompt_seen:
            self._prompt_seen = True
        elif self.observation.first_token_at is None:
            self.observation.first_token_at = time.perf_counter()

    def end(self) -> None:
        return None


def _settings(environment: dict[str, str], model_path: Path, shards_path: Path) -> AirLLMSettings:
    return AirLLMSettings(
        model=str(model_path),
        shards_path=shards_path,
        compression="4bit",
        max_context=int(environment.get("AIRLLM_MAX_CONTEXT", "32768")),
        max_new_tokens=int(environment["AIRLLM_MAX_NEW_TOKENS"]),
        temperature=0.0,
        profiling_mode=False,
        diagnostic_mode=True,
        enable_qwen35_compat_patch=False,
    )


def _attach_forward_hooks(wrapper: object, observation: RuntimeObservation) -> None:
    """Observe public module hooks without replacing AirLLM methods or behavior."""
    causal_lm = wrapper.model
    base_model = causal_lm.model

    def pre_layer(index: int):
        def hook(_module: object, _args: object) -> None:
            now = time.perf_counter()
            if observation.first_layer_started is None:
                observation.first_layer_started = now
            observation.last_layer_started = index
            observation.visit(f"layer.{index}.started")

        return hook

    def post_layer(index: int):
        def hook(_module: object, _args: object, _output: object) -> None:
            observation.last_layer_completed = index
            observation.visit(f"layer.{index}.completed")

        return hook

    for index, layer in enumerate(base_model.layers):
        layer.register_forward_pre_hook(pre_layer(index))
        layer.register_forward_hook(post_layer(index))

    base_model.embed_tokens.register_forward_hook(
        lambda _module, _args, _output: observation.visit("embedding.completed")
    )
    base_model.norm.register_forward_hook(
        lambda _module, _args, _output: observation.visit("norm.completed")
    )
    causal_lm.lm_head.register_forward_hook(
        lambda _module, _args, _output: observation.visit("lm_head.completed")
    )


def _messages_for_mode(mode: str) -> list[dict[str, str]]:
    if mode == "smoke":
        return SMOKE_MESSAGES
    if mode == "plan":
        return orchestration_messages()
    key = mode.removeprefix("adversarial-")
    return orchestration_messages(ADVERSARIAL_INSTRUCTIONS[key])


def _max_tokens(mode: str) -> int:
    return 16 if mode == "smoke" else 1536


def _write_json(path_value: str | None, payload: dict[str, object]) -> None:
    if not path_value:
        return
    path = Path(path_value).expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(mode: str) -> int:
    global _LAST_OBSERVATION
    observation = RuntimeObservation()
    _LAST_OBSERVATION = observation
    started = time.perf_counter()
    environment = dict(os.environ)
    model_path = Path(environment["AIRLLM_LOCAL_MODEL_PATH"]).resolve(strict=True)
    shards_path = Path(environment["AIRLLM_SHARDS_PATH"]).resolve(strict=False)
    settings_values = {
        "AIRLLM_MODEL": environment.get("AIRLLM_MODEL", ""),
        "AIRLLM_COMPRESSION": environment.get("AIRLLM_COMPRESSION", ""),
        "AIRLLM_MAX_NEW_TOKENS": environment.get("AIRLLM_MAX_NEW_TOKENS", ""),
        "AIRLLM_TEMPERATURE": environment.get("AIRLLM_TEMPERATURE", ""),
        "AIRLLM_DO_SAMPLE": environment.get("AIRLLM_DO_SAMPLE", ""),
        "AIRLLM_ENABLE_QWEN35_COMPAT_PATCH": environment.get(
            "AIRLLM_ENABLE_QWEN35_COMPAT_PATCH", "false"
        ),
        "HF_TOKEN": environment.get("HF_TOKEN", ""),
    }
    validate_phase18_environment(settings_values)

    observation.phase = "imports"
    import torch
    from airllm import AutoModel
    from transformers import AutoConfig

    airllm_version = importlib.metadata.version("airllm")
    validate_airllm_version(airllm_version)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    observation.phase = "checkpoint_validation"
    config = AutoConfig.from_pretrained(model_path, local_files_only=True)
    architecture = (getattr(config, "architectures", None) or ["unknown"])[0]
    if architecture != "Qwen2ForCausalLM" or getattr(config, "num_hidden_layers", None) != 80:
        raise RuntimeError(
            f"Unexpected local checkpoint: architecture={architecture!r}, "
            f"layers={getattr(config, 'num_hidden_layers', None)!r}."
        )

    settings = _settings(environment, model_path, shards_path)
    settings = AirLLMSettings(
        **{**settings.__dict__, "max_new_tokens": _max_tokens(mode)}
    )
    shards_path.mkdir(parents=True, exist_ok=True)
    load_kwargs: dict[str, object] = {
        "layer_shards_saving_path": str(shards_path),
        "compression": "4bit",
        "delete_original": True,
    }
    validate_loader_kwargs(AutoModel.from_pretrained, load_kwargs)
    token = environment.get("HF_TOKEN", "").strip()
    if token:
        load_kwargs["hf_token"] = token

    print(f"Phase 1.8 mode: {mode}")
    print(f"Checkpoint: {MODEL_ID}")
    print(f"Local checkpoint: {model_path}")
    print(f"Architecture: {architecture}")
    print(f"AirLLM: {airllm_version}")
    print(f"Transformers: {importlib.metadata.version('transformers')}")
    print(f"Torch: {torch.__version__}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Load kwargs: {safe_environment_summary(load_kwargs)}")
    print("Qwen 3.5 patch: False")

    observation.phase = "model_loading_or_sharding"
    model = AutoModel.from_pretrained(str(model_path), **load_kwargs)
    preparation_finished = time.perf_counter()
    _attach_forward_hooks(model, observation)

    observation.phase = "prompt_rendering"
    messages = _messages_for_mode(mode)
    prompt = render_chat_prompt(model.tokenizer, messages)
    encoded = model.tokenizer(
        prompt,
        return_tensors="pt",
        return_attention_mask=True,
        truncation=False,
        padding=False,
    )
    input_ids = encoded["input_ids"]
    attention_mask = encoded["attention_mask"]
    prompt_tokens = int(input_ids.shape[-1])
    if prompt_tokens > settings.max_context:
        raise RuntimeError(
            f"Prompt exceeds context limit ({prompt_tokens} > {settings.max_context})."
        )

    observation.phase = "generation"
    streamer = TimingStreamer(observation)
    generation_options = generation_kwargs(settings)
    generation_options["streamer"] = streamer
    generation_options["attention_mask"] = attention_mask.to("cuda")
    cuda_input_ids = input_ids.to("cuda")
    torch.cuda.synchronize()
    observation.generation_started = time.perf_counter()
    output = model.generate(cuda_input_ids, **generation_options)
    torch.cuda.synchronize()
    generation_finished = time.perf_counter()

    sequences = getattr(output, "sequences", output)
    generated = sequences[0]
    completion_ids = generated[prompt_tokens:]
    completion_tokens = int(completion_ids.shape[-1])
    response = model.tokenizer.decode(completion_ids, skip_special_tokens=True).strip()
    generation_seconds = generation_finished - observation.generation_started
    result: dict[str, object] = {
        "mode": mode,
        "checkpoint": MODEL_ID,
        "architecture": architecture,
        "airllm_version": airllm_version,
        "transformers_version": importlib.metadata.version("transformers"),
        "preparation_seconds": preparation_finished - started,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "generation_seconds": generation_seconds,
        "time_to_first_layer_seconds": (
            observation.first_layer_started - observation.generation_started
            if observation.first_layer_started is not None
            else None
        ),
        "time_to_first_token_seconds": (
            observation.first_token_at - observation.generation_started
            if observation.first_token_at is not None
            else None
        ),
        "tokens_per_second": completion_tokens / max(generation_seconds, 1e-9),
        "last_layer_started": observation.last_layer_started,
        "last_layer_completed": observation.last_layer_completed,
        "norm_visits": observation.unit_visits.get("norm.completed", 0),
        "lm_head_visits": observation.unit_visits.get("lm_head.completed", 0),
        "response": response,
    }
    if mode != "smoke":
        result["evaluation"] = asdict(evaluate_plan_text(response))
    _write_json(environment.get("AIRLLM_PHASE18_OUTPUT"), result)
    print("PHASE18_RESULT=" + json.dumps(result, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("smoke", "plan", "adversarial-a", "adversarial-b", "adversarial-c"),
    )
    args = parser.parse_args(argv)
    try:
        return run(args.mode)
    except Exception as exc:
        observation_error: dict[str, Any] = (
            asdict(_LAST_OBSERVATION) if _LAST_OBSERVATION is not None else {}
        )
        failure = {
            "mode": args.mode,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "observation": observation_error,
            "traceback": traceback.format_exc(),
        }
        _write_json(os.environ.get("AIRLLM_PHASE18_OUTPUT"), failure)
        print("PHASE18_FAILURE=" + json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
