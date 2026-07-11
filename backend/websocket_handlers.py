from typing import Any, Mapping


def message_type(message: Mapping[str, Any]) -> str:
    return str(message.get("type", ""))
