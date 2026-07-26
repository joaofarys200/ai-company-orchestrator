from __future__ import annotations

import json
import re
import warnings
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Mapping


QWEN35_ARCHITECTURE = "Qwen3_5MoeForConditionalGeneration"
QWEN35_LAYER_NAMES = {
    "embed": "model.language_model.embed_tokens",
    "layer_prefix": "model.language_model.layers",
    "norm": "model.language_model.norm",
    "lm_head": "lm_head",
}

_BLOCK_KEY = re.compile(
    r"^model\.language_model\.layers\.(?P<index>0|[1-9][0-9]*)\.(?P<member>.+)$"
)


class Qwen35CompatibilityError(RuntimeError):
    """Raised when the experimental patch cannot prove its narrow preconditions."""


def classify_parameter_key(key: str) -> tuple[str, int | None]:
    """Classify one Qwen 3.5 checkpoint key without substring heuristics."""
    if not isinstance(key, str) or not key:
        raise Qwen35CompatibilityError("Checkpoint parameter keys must be non-empty strings.")
    if key.startswith("model.language_model.embed_tokens."):
        return "embedding", None
    match = _BLOCK_KEY.fullmatch(key)
    if match is not None:
        return "block", int(match.group("index"))
    if key.startswith("model.language_model.layers."):
        segment = key.removeprefix("model.language_model.layers.").split(".", 1)[0]
        raise Qwen35CompatibilityError(
            f"Invalid Qwen 3.5 layer index segment {segment!r} in parameter {key!r}."
        )
    if key.startswith("model.language_model.norm."):
        return "final_norm", None
    if key.startswith("lm_head."):
        return "lm_head", None
    if key.startswith("model.visual."):
        return "visual_unstreamed", None
    if key.startswith("mtp."):
        return "mtp_unstreamed", None
    raise Qwen35CompatibilityError(
        f"Unclassified Qwen 3.5 checkpoint parameter: {key!r}."
    )


def validate_parameter_keys(
    keys: Iterable[str],
    *,
    expected_layer_count: int | None = None,
) -> Counter[str]:
    """Fail closed unless every key and every decoder-layer index is accounted for."""
    counts: Counter[str] = Counter()
    layer_indices: set[int] = set()
    for key in keys:
        category, layer_index = classify_parameter_key(key)
        counts[category] += 1
        if layer_index is not None:
            layer_indices.add(layer_index)

    required = {"embedding", "block", "final_norm", "lm_head"}
    missing = sorted(required - counts.keys())
    if missing:
        raise Qwen35CompatibilityError(
            "Checkpoint is missing required Qwen 3.5 parameter categories: "
            + ", ".join(missing)
            + "."
        )
    expected_indices = (
        set(range(expected_layer_count))
        if expected_layer_count is not None
        else set(range(max(layer_indices) + 1))
    )
    if layer_indices != expected_indices:
        missing_indices = sorted(expected_indices - layer_indices)
        unexpected_indices = sorted(layer_indices - expected_indices)
        raise Qwen35CompatibilityError(
            "Qwen 3.5 decoder layer indices are not the expected contiguous set; "
            f"missing={missing_indices}, unexpected={unexpected_indices}."
        )
    return counts


def read_weight_map(index_path: Path) -> Mapping[str, str]:
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        weight_map = payload["weight_map"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError) as exc:
        raise Qwen35CompatibilityError(
            f"Could not read a safetensors weight map from {index_path}."
        ) from exc
    if not isinstance(weight_map, dict) or not weight_map:
        raise Qwen35CompatibilityError(
            f"Safetensors weight map is empty or invalid in {index_path}."
        )
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in weight_map.items()):
        raise Qwen35CompatibilityError(
            f"Safetensors weight map contains non-string entries in {index_path}."
        )
    return weight_map


def _locate_index(
    model_ref: str,
    *,
    index_downloader: Callable[[str], str] | None = None,
) -> Path:
    local_candidate = Path(model_ref)
    if local_candidate.is_dir():
        index_path = local_candidate / "model.safetensors.index.json"
    else:
        if index_downloader is None:
            from huggingface_hub import hf_hub_download

            index_downloader = lambda repo_id: hf_hub_download(
                repo_id=repo_id,
                filename="model.safetensors.index.json",
            )
        index_path = Path(index_downloader(model_ref))
    if not index_path.is_file():
        raise Qwen35CompatibilityError(
            "The experimental Qwen 3.5 patch requires model.safetensors.index.json."
        )
    return index_path


def _install_runtime_override(airllm_module: object, auto_model_module: object) -> None:
    base_class = getattr(airllm_module, "AirLLMBaseModel")

    class AirLLMQwen35Experimental(base_class):
        def set_layer_names_dict(self) -> None:
            self.layer_names_dict = dict(QWEN35_LAYER_NAMES)

    AirLLMQwen35Experimental.__name__ = "AirLLMQwen35Experimental"
    setattr(airllm_module, "AirLLMQwen35Experimental", AirLLMQwen35Experimental)
    overrides = getattr(auto_model_module, "ARCH_OVERRIDES")
    overrides[QWEN35_ARCHITECTURE] = "AirLLMQwen35Experimental"


def maybe_enable_patch(
    *,
    enabled: bool,
    model_ref: str,
    architecture: str,
    expected_layer_count: int | None,
    index_downloader: Callable[[str], str] | None = None,
    airllm_module: object | None = None,
    auto_model_module: object | None = None,
) -> Counter[str] | None:
    """Install the narrow runtime override only after validating the full index."""
    if not enabled:
        return None
    if architecture != QWEN35_ARCHITECTURE:
        raise Qwen35CompatibilityError(
            "AIRLLM_ENABLE_QWEN35_COMPAT_PATCH only supports "
            f"{QWEN35_ARCHITECTURE}; received {architecture!r}."
        )

    index_path = _locate_index(model_ref, index_downloader=index_downloader)
    counts = validate_parameter_keys(
        read_weight_map(index_path).keys(),
        expected_layer_count=expected_layer_count,
    )
    warnings.warn(
        "EXPERIMENTAL AirLLM Qwen 3.5 compatibility patch enabled. It corrects "
        "the nested text-layer paths only. The visual encoder and MTP parameters "
        "are recognized but not streamed, and functional generation remains unproven.",
        RuntimeWarning,
        stacklevel=2,
    )

    if airllm_module is None or auto_model_module is None:
        import airllm as installed_airllm
        from airllm import auto_model as installed_auto_model

        airllm_module = installed_airllm
        auto_model_module = installed_auto_model
    _install_runtime_override(airllm_module, auto_model_module)
    return counts
