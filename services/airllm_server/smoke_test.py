from __future__ import annotations

import importlib.metadata
import inspect
import os
import sys
import time
from collections.abc import Callable

from .compat.qwen35 import maybe_enable_patch
from .config import AirLLMSettings, AirLLMConfigurationError, parse_boolean
from .diagnostics import DiagnosticState, emit_failure
from .prompting import render_chat_prompt


SUPPORTED_AIRLLM_VERSION = "3.0.1"


class AirLLMCompatibilityError(RuntimeError):
    """Raised when the installed AirLLM API does not match this experiment."""


def validate_airllm_version(version: str) -> None:
    if version != SUPPORTED_AIRLLM_VERSION:
        raise AirLLMCompatibilityError(
            "This experiment was validated against airllm "
            f"{SUPPORTED_AIRLLM_VERSION}, but {version!r} is installed. "
            "Install the experimental requirements or review the loader API "
            "before running it."
        )


def validate_loader_kwargs(
    loader: Callable[..., object],
    kwargs: dict[str, object],
) -> str:
    try:
        signature = inspect.signature(loader)
    except (TypeError, ValueError) as exc:
        raise AirLLMCompatibilityError(
            "Could not inspect AirLLM AutoModel.from_pretrained; refusing to "
            "ignore loader compatibility."
        ) from exc

    accepts_var_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    if not accepts_var_kwargs:
        unsupported = sorted(set(kwargs) - set(signature.parameters))
        if unsupported:
            raise AirLLMCompatibilityError(
                "Installed AirLLM loader does not accept required arguments: "
                f"{', '.join(unsupported)}. Observed signature: {signature}."
            )
    return str(signature)


def build_model_load_kwargs(
    settings: AirLLMSettings,
    loader: Callable[..., object] | None = None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "layer_shards_saving_path": str(settings.shards_path),
        "profiling_mode": settings.profiling_mode,
    }
    if settings.compression is not None:
        kwargs["compression"] = settings.compression
    if loader is not None:
        validate_loader_kwargs(loader, kwargs)
    return kwargs


def generation_kwargs(settings: AirLLMSettings) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "max_new_tokens": settings.max_new_tokens,
        "use_cache": True,
        "return_dict_in_generate": True,
        "do_sample": settings.temperature > 0,
    }
    if settings.temperature > 0:
        kwargs["temperature"] = settings.temperature
    return kwargs


def _token_count(input_ids: object) -> int:
    shape = getattr(input_ids, "shape", None)
    if shape is None or len(shape) < 1:
        raise RuntimeError("Tokenizer did not return tensor-shaped input_ids.")
    return int(shape[-1])


def _diagnostic_mode_hint() -> bool:
    """Read the process override early enough to diagnose configuration failures."""
    raw_value = os.environ.get("AIRLLM_DIAGNOSTIC_MODE", "false")
    try:
        return parse_boolean(raw_value, "AIRLLM_DIAGNOSTIC_MODE")
    except AirLLMConfigurationError:
        return False


def _declared_architecture(model_config: object) -> str:
    architectures = getattr(model_config, "architectures", None) or []
    return str(architectures[0]) if architectures else "unknown"


def _declared_layer_count(model_config: object) -> int | None:
    text_config = getattr(model_config, "text_config", model_config)
    value = getattr(text_config, "num_hidden_layers", None)
    return value if isinstance(value, int) and value > 0 else None


def main() -> int:
    state = DiagnosticState()
    diagnostic_mode = _diagnostic_mode_hint()
    try:
        preparation_started = time.perf_counter()
        state.set_phase("configuration")
        settings = AirLLMSettings.from_environment()
        diagnostic_mode = settings.diagnostic_mode
        settings.apply_cache_environment()

        state.set_phase("imports")
        import torch
        from airllm import AutoModel
        from transformers import AutoConfig

        installed_version = importlib.metadata.version("airllm")
        state.airllm_version = installed_version
        state.torch_version = str(torch.__version__)
        validate_airllm_version(installed_version)

        state.set_phase("cuda_check")
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA is not available. Install a CUDA-compatible Torch build "
                "and confirm that the NVIDIA driver can see the GPU."
            )

        print(f"Torch version: {torch.__version__}")
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"AirLLM version: {installed_version}")
        print(f"Model: {settings.model}")
        print(f"Compression: {settings.compression or 'none'}")
        print(f"Shards path: {settings.shards_path}")
        print(f"Maximum context tokens: {settings.max_context}")
        print(f"Maximum new tokens: {settings.max_new_tokens}")
        print(f"Temperature: {settings.temperature}")
        print(f"Profiling mode: {settings.profiling_mode}")
        print(f"Diagnostic mode: {settings.diagnostic_mode}")
        print(
            "Qwen 3.5 compatibility patch: "
            f"{settings.enable_qwen35_compat_patch}"
        )

        state.set_phase("path_preparation")
        settings.shards_path.mkdir(parents=True, exist_ok=True)
        load_kwargs = build_model_load_kwargs(
            settings,
            AutoModel.from_pretrained,
        )
        loader_signature = validate_loader_kwargs(
            AutoModel.from_pretrained,
            load_kwargs,
        )
        state.load_kwargs = dict(load_kwargs)
        print(f"AutoModel.from_pretrained signature: {loader_signature}")
        print(f"Model load kwargs: {sorted(load_kwargs)}")

        state.set_phase("model_configuration_download")
        model_config = AutoConfig.from_pretrained(
            settings.model,
            trust_remote_code=True,
        )
        state.architecture = _declared_architecture(model_config)
        print(f"Declared architecture: {state.architecture}")
        patch_counts = maybe_enable_patch(
            enabled=settings.enable_qwen35_compat_patch,
            model_ref=settings.model,
            architecture=state.architecture,
            expected_layer_count=_declared_layer_count(model_config),
        )
        if patch_counts is not None:
            print(f"Qwen 3.5 checkpoint categories: {dict(patch_counts)}")

        state.set_phase("model_loading_or_sharding")
        model = AutoModel.from_pretrained(settings.model, **load_kwargs)
        preparation_duration = time.perf_counter() - preparation_started

        messages = [
            {
                "role": "system",
                "content": "Answer briefly in plain text.",
            },
            {
                "role": "user",
                "content": "Reply with one short greeting.",
            },
        ]
        state.set_phase("tokenizer_loading")
        tokenizer = model.tokenizer

        state.set_phase("prompt_rendering")
        prompt = render_chat_prompt(tokenizer, messages)

        state.set_phase("tokenization")
        encoded = tokenizer(
            prompt,
            return_tensors="pt",
            return_attention_mask=False,
            truncation=False,
            padding=False,
        )
        if not isinstance(encoded, dict) and not hasattr(encoded, "__getitem__"):
            raise RuntimeError("Tokenizer returned an unsupported payload.")
        input_ids = encoded["input_ids"]
        prompt_tokens = _token_count(input_ids)
        if prompt_tokens > settings.max_context:
            raise RuntimeError(
                "Prompt exceeds AIRLLM_MAX_CONTEXT and was not truncated "
                f"({prompt_tokens} > {settings.max_context} tokens)."
            )

        state.set_phase("generation")
        cuda_input_ids = input_ids.to("cuda")
        torch.cuda.synchronize()
        generation_started = time.perf_counter()
        output = model.generate(
            cuda_input_ids,
            **generation_kwargs(settings),
        )
        torch.cuda.synchronize()
        generation_duration = time.perf_counter() - generation_started

        state.set_phase("decoding")
        sequences = getattr(output, "sequences", None)
        if sequences is None:
            raise RuntimeError("AirLLM generate() did not return sequences.")
        generated_sequence = sequences[0]
        completion_ids = generated_sequence[prompt_tokens:]
        completion_tokens = _token_count(completion_ids)
        if completion_tokens <= 0:
            raise RuntimeError("AirLLM generated no completion tokens.")
        response = tokenizer.decode(
            completion_ids,
            skip_special_tokens=True,
        ).strip()
        tokens_per_second = completion_tokens / max(generation_duration, 1e-9)

        print(f"Preparation/model loading duration: {preparation_duration:.3f}s")
        print(f"Prompt tokens: {prompt_tokens}")
        print(f"Generation duration: {generation_duration:.3f}s")
        print(f"Completion tokens: {completion_tokens}")
        print(f"Tokens per second: {tokens_per_second:.3f}")
        print("Response:")
        print(response)
        return 0
    except Exception as exc:
        emit_failure(
            exc,
            state,
            diagnostic_mode=diagnostic_mode,
            stream=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
