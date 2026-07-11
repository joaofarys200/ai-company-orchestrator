from __future__ import annotations

from typing import Any, Mapping, TypedDict


class WsMessage(TypedDict, total=False):
    type: str
    content: str
    sender: str
    role: str
    audio: str
    value: str
    filename: str
    card_id: str
    status: str
    action: str
    theme: str
    result: str
    running: bool
    data: Any


SERVER_MESSAGE_TYPES = {
    "system",
    "chat",
    "state",
    "voice_status",
    "file",
    "kanban",
    "template_changed",
    "arena_update",
    "project_output",
    "project_status",
    "complete",
    "notes_list",
    "note_content",
    "note_saved",
    "rules_list",
    "rules_updated",
    "architecture_list",
    "architecture_updated",
    "decisions_list",
    "decisions_updated",
    "planner_state",
    "ast_state",
    "projects_list",
    "project_context",
    "project_references",
    "semantic_results",
    "coding_session",
    "ui",
    "ui_action",
    "ui_theme",
}


CLIENT_MESSAGE_TYPES = {
    "directive",
    "select_template",
    "toggle_voice",
    "run_project",
    "stop_project",
    "get_notes",
    "read_note",
    "save_note",
    "delete_rule",
    "delete_architecture",
    "delete_decision",
    "get_rules",
    "get_planner_state",
    "get_ast_state",
    "list_projects",
    "open_project",
    "index_project",
    "find_references",
    "semantic_search",
    "create_coding_session",
    "apply_coding_session",
    "rollback_coding_session",
    "get_coding_session",
}

_logged_unknown_types: set[str] = set()


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_bool(value: Any) -> bool:
    return bool(value)


def _log_unknown_message_type(message_type: str) -> None:
    if message_type not in _logged_unknown_types:
        print(f"[WebSocketSchema] Unknown outbound message type: {message_type}")
        _logged_unknown_types.add(message_type)


def normalize_ws_message(message: Mapping[str, Any]) -> dict[str, Any]:
    message_type = _as_str(message.get("type"), "unknown")
    if message_type not in SERVER_MESSAGE_TYPES:
        _log_unknown_message_type(message_type)
        return dict(message)

    if message_type == "system":
        return {"type": "system", "content": _as_str(message.get("content"))}

    if message_type == "chat":
        normalized = {
            "type": "chat",
            "sender": _as_str(message.get("sender"), "SISTEMA"),
            "role": _as_str(message.get("role"), "System"),
            "content": _as_str(message.get("content")),
        }
        if message.get("audio"):
            normalized["audio"] = _as_str(message.get("audio"))
        return normalized

    if message_type == "state":
        return {"type": "state", "value": _as_str(message.get("value"), "idle")}

    if message_type == "voice_status":
        normalized = {"type": "voice_status", "status": _as_str(message.get("status"), "offline")}
        if message.get("text") is not None:
            normalized["text"] = _as_str(message.get("text"))
        return normalized

    if message_type == "file":
        return {
            "type": "file",
            "filename": _as_str(message.get("filename")),
            "content": _as_str(message.get("content")),
        }

    if message_type == "kanban":
        return {
            "type": "kanban",
            "card_id": _as_str(message.get("card_id")),
            "status": _as_str(message.get("status"), "backlog"),
        }

    if message_type == "project_output":
        return {"type": "project_output", "content": _as_str(message.get("content"))}

    if message_type == "project_status":
        return {
            "type": "project_status",
            "running": _as_bool(message.get("running")),
            "preview_url": _as_str(message.get("preview_url")),
        }

    if message_type in {"rules_list", "rules_updated"}:
        return {"type": message_type, "rules": _as_list(message.get("rules"))}

    if message_type in {"architecture_list", "architecture_updated"}:
        return {"type": message_type, "architecture": _as_list(message.get("architecture"))}

    if message_type in {"decisions_list", "decisions_updated"}:
        return {"type": message_type, "decisions": _as_list(message.get("decisions"))}

    if message_type == "planner_state":
        data = message.get("data")
        return {"type": "planner_state", "data": data if isinstance(data, dict) or data is None else None}

    if message_type == "ast_state":
        data = message.get("data")
        return {"type": "ast_state", "data": data if isinstance(data, dict) or data is None else None}

    if message_type == "projects_list":
        return {"type": "projects_list", "projects": _as_list(message.get("projects"))}

    if message_type == "project_context":
        return {
            "type": "project_context",
            "context": message.get("context") if isinstance(message.get("context"), dict) else None,
            "files": message.get("files") if isinstance(message.get("files"), dict) else {},
            "symbols": message.get("symbols") if isinstance(message.get("symbols"), dict) else {},
        }

    if message_type == "project_references":
        return {
            "type": "project_references",
            "data": message.get("data") if isinstance(message.get("data"), dict) else {},
        }

    if message_type == "semantic_results":
        return {"type": "semantic_results", "query": _as_str(message.get("query")), "content": _as_str(message.get("content"))}

    if message_type == "coding_session":
        return {
            "type": "coding_session",
            "data": message.get("data") if isinstance(message.get("data"), dict) or message.get("data") is None else None,
        }

    if message_type in {"ui", "ui_action"}:
        return {"type": message_type, "action": _as_str(message.get("action"))}

    if message_type == "ui_theme":
        return {"type": "ui_theme", "theme": _as_str(message.get("theme"))}

    if message_type == "template_changed":
        return {
            "type": "template_changed",
            "template_name": _as_str(message.get("template_name")),
            "name": _as_str(message.get("name")),
            "description": _as_str(message.get("description")),
            "agents": _as_list(message.get("agents")),
            "tasks": _as_list(message.get("tasks")),
            "suggestions": _as_list(message.get("suggestions")),
        }

    if message_type == "arena_update":
        return {
            "type": "arena_update",
            "model_id": _as_str(message.get("model_id")),
            "status": _as_str(message.get("status")),
            "content": _as_str(message.get("content")),
            "time": message.get("time", "-"),
            "tokens": message.get("tokens", "-"),
        }

    if message_type == "complete":
        return {"type": "complete", "result": _as_str(message.get("result"), "Sucesso")}

    if message_type == "notes_list":
        return {"type": "notes_list", "notes": _as_list(message.get("notes"))}

    if message_type == "note_content":
        return {
            "type": "note_content",
            "filename": _as_str(message.get("filename")),
            "content": _as_str(message.get("content")),
        }

    if message_type == "note_saved":
        return {
            "type": "note_saved",
            "filename": _as_str(message.get("filename")),
            "result": _as_str(message.get("result")),
        }

    return dict(message)


def system_message(content: Any) -> dict[str, Any]:
    return normalize_ws_message({"type": "system", "content": content})


def chat_message(sender: Any, role: Any, content: Any, audio: Any = None) -> dict[str, Any]:
    message: dict[str, Any] = {"type": "chat", "sender": sender, "role": role, "content": content}
    if audio:
        message["audio"] = audio
    return normalize_ws_message(message)


def state_message(value: Any) -> dict[str, Any]:
    return normalize_ws_message({"type": "state", "value": value})


def file_message(filename: Any, content: Any) -> dict[str, Any]:
    return normalize_ws_message({"type": "file", "filename": filename, "content": content})


def kanban_message(card_id: Any, status: Any) -> dict[str, Any]:
    return normalize_ws_message({"type": "kanban", "card_id": card_id, "status": status})


def project_output_message(content: Any) -> dict[str, Any]:
    return normalize_ws_message({"type": "project_output", "content": content})


def rules_message(rules: Any, updated: bool = False) -> dict[str, Any]:
    return normalize_ws_message({"type": "rules_updated" if updated else "rules_list", "rules": rules})


def planner_state_message(data: Any) -> dict[str, Any]:
    return normalize_ws_message({"type": "planner_state", "data": data})


def ui_message(action: Any, kind: str = "ui") -> dict[str, Any]:
    return normalize_ws_message({"type": kind, "action": action})


def ui_theme_message(theme: Any) -> dict[str, Any]:
    return normalize_ws_message({"type": "ui_theme", "theme": theme})
