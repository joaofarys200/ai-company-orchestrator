from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.websocket.context import WebSocketHandlerContext


EXPECTED_MESSAGE_TYPES = frozenset(
    {
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
        "create_project",
        "open_project",
        "save_project_file",
        "index_project",
        "find_references",
        "semantic_search",
        "create_coding_session",
        "apply_coding_session",
        "rollback_coding_session",
        "get_coding_session",
        "mission_list",
        "mission_create",
        "mission_get",
        "mission_update",
        "mission_set_status",
        "work_package_create",
        "work_package_update",
        "work_package_set_status",
        "work_package_add_dependency",
        "deliverable_create",
        "deliverable_update",
        "deliverable_set_status",
        "evidence_attach",
        "criterion_create",
        "criterion_set_status",
        "mission_resume_snapshot",
        "mission_execute_work_package",
        "mission_apply_execution",
        "mission_review_execution",
        "mission_retry_execution",
        "mission_cancel_execution",
        "mission_release_stale_lock",
        "mission_autonomy_run",
        "start_lecture_recording",
        "stop_lecture_recording",
        "get_lecture_status",
        "list_lecture_history",
        "generate_lecture_lesson",
        "submit_lecture_quiz",
        "sentinel_get_status",
        "sentinel_run_audit",
        "sentinel_get_baseline",
        "sentinel_accept_known_good",
        "sentinel_get_actions",
        "sentinel_approve_action",
        "sentinel_reject_action",
        "sentinel_rollback_action",
        "sentinel_submit_review",
        "sentinel_get_shadow_telemetry",
    }
)


@dataclass(frozen=True, slots=True)
class HandlerResult:
    event_type: str
    payload: dict[str, Any]
    broadcast: bool = False

    def to_message(self) -> dict[str, Any]:
        return {"type": self.event_type, **self.payload}


MessageHandler = Callable[
    ["WebSocketHandlerContext", dict[str, Any]],
    Awaitable[HandlerResult | None],
]
