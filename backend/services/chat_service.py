def append_bounded_history(history: list[dict], role: str, content: str, limit: int) -> None:
    history.append({"role": role, "content": content})
    while len(history) > limit:
        history.pop(0)
