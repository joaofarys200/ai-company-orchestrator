from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


ALLOWED_ROLES = frozenset({"system", "user", "assistant"})
_MISSING = object()


class AirLLMPromptError(ValueError):
    """Raised when chat messages cannot form a safe deterministic prompt."""


def chat_template_payload(
    messages: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    if isinstance(messages, (str, bytes, Mapping)) or not isinstance(
        messages, Sequence
    ):
        raise AirLLMPromptError("Messages must be a non-empty sequence of objects.")
    if not messages:
        raise AirLLMPromptError("Messages must not be empty.")

    payload: list[dict[str, str]] = []
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            raise AirLLMPromptError(f"Message {index} must be an object.")
        role_value = message.get("role")
        content_value = message.get("content")
        if not isinstance(role_value, str):
            raise AirLLMPromptError(f"Message {index} has an invalid role.")
        role = role_value.strip().casefold()
        if role not in ALLOWED_ROLES:
            raise AirLLMPromptError(
                f"Message {index} role {role_value!r} is not allowed; "
                "use system, user, or assistant."
            )
        if not isinstance(content_value, str) or not content_value.strip():
            raise AirLLMPromptError(
                f"Message {index} content must be a non-empty string."
            )
        payload.append({"role": role, "content": content_value.strip()})
    return payload


def fallback_chat_prompt(
    messages: Sequence[Mapping[str, Any]],
    *,
    add_generation_prompt: bool = True,
) -> str:
    payload = chat_template_payload(messages)
    sections = [
        f"{message['role'].upper()}:\n{message['content']}"
        for message in payload
    ]
    if add_generation_prompt:
        sections.append("ASSISTANT:\n")
    return "\n\n".join(sections)


def render_chat_prompt(
    tokenizer: object,
    messages: Sequence[Mapping[str, Any]],
    *,
    add_generation_prompt: bool = True,
) -> str:
    payload = chat_template_payload(messages)
    apply_template = getattr(tokenizer, "apply_chat_template", None)
    declared_template = getattr(tokenizer, "chat_template", _MISSING)
    template_available = (
        callable(apply_template)
        and declared_template is not None
        and declared_template != ""
    )
    if template_available:
        try:
            rendered = apply_template(
                payload,
                tokenize=False,
                add_generation_prompt=add_generation_prompt,
            )
        except Exception as exc:
            raise AirLLMPromptError(
                f"Tokenizer chat template failed: {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(rendered, str) or not rendered.strip():
            raise AirLLMPromptError(
                "Tokenizer chat template returned an empty or non-text prompt."
            )
        return rendered
    return fallback_chat_prompt(
        payload,
        add_generation_prompt=add_generation_prompt,
    )
