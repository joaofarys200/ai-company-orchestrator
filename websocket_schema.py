from __future__ import annotations

import re
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
    "project_file_save_result",
    "project_deleted",
    "project_delete_error",
    "project_file_deleted",
    "project_file_delete_error",
    "project_references",
    "semantic_results",
    "coding_session",
    "mission_list",
    "mission_snapshot",
    "ui",
    "ui_action",
    "ui_theme",
    "sandbox_status",
    "lecture_status",
    "lecture_status_response",
    "lecture_history",
    "lecture_history_response",
    "lecture_started",
    "lecture_recording_started",
    "lecture_session_update",
    "lecture_transcribing_started",
    "lecture_synthesis_completed",
    "lecture_audio_level",
    "lecture_lesson_generated",
    "lecture_quiz_evaluated",
    "sentinel_status",
    "sentinel_audit_completed",
    "sentinel_event",
    "sentinel_baseline",
    "sentinel_known_good_updated",
    "sentinel_action_proposed",
    "sentinel_action_result",
    "sentinel_actions_list",
    "mission_subdag_proposal_result",
    "mission_subdag_history",
    "mission_subdag_proposed",
    "mission_subdag_applied",
    "mission_subdag_rejected",
    "mission_plan_evaluation_result",
    "mission_adaptation_proposal_result",
    "mission_adaptation_history",
    "mission_checkpoint_created",
    "mission_checkpoint_restored",
    "mission_plan_status",
    "mission_federation_status_response",
    "mission_federation_scale_response",
    "mission_federation_rebalance_response",
    "subswarm_created",
    "subswarm_scaled",
    "subswarm_rebalanced",
    "subswarm_recovered",
    "cross_swarm_conflict",
    "federated_arbitration",
    "federation_rebalanced",
    "execution_mode_selected",
    "execution_mode_changed",
    "worker_started",
    "worker_reused",
    "worker_replaced",
    "ipc_backpressure",
    "adaptive_scaling",
    "worker_pool_scaled",
    "mission_federation_switch_mode_response",
    "ipc_transport_selected",
    "ipc_transport_changed",
    "ipc_send_latency",
    "ipc_receive_latency",
    "ipc_roundtrip_latency",
    "shared_memory_allocated",
    "shared_memory_released",
    "shared_memory_status",
    # Phase 19 Distributed Multi-Host Federation events
    "node_joined",
    "node_failed",
    "node_recovered",
    "node_draining",
    "package_assigned",
    "cross_node_dependency",
    "lease_fenced",
    "network_retry",
    "network_timeout",
    "partition_detected",
    "partition_reconciled",
    "distributed_checkpoint",
    # Phase 19.1 Streaming Transport & Large Payload Resilience events
    "stream_started",
    "stream_progress",
    "stream_backpressure",
    "stream_retransmission",
    "stream_completed",
    "stream_failed",
    "stream_resumed",
    # Phase 20 Multithreaded I/O Dispatch & Stream Parallelism events
    "io_backend_selected",
    "io_backend_changed",
    "io_worker_started",
    "io_worker_replaced",
    "stream_group_created",
    "stream_group_rebalanced",
    "control_plane_latency",
    # Phase 21 QUIC/HTTP3 Transport & High-Concurrency Streams events
    "transport_selected",
    "connection_opened",
    "connection_closed",
    "stream_opened",
    "stream_closed",
    "stream_reset",
    "flow_control_backpressure",
    "transport_migrated",
    "quic_path_migrated",
    # Phase 42 Experience Memory & Cross-Mission Learning
    "mission_experience_memory_status_result",
    "mission_experience_curate_result",
    # Phase 44 Semantic Graph & Task Translation
    "mission_semantic_graph_status_result",
    # Phase 45 Runtime Contract Discovery & Schema Inference
    "mission_contract_discovery_status_result",
    "mission_contract_proposal_review_result",
    # Phase 46 Contract Drift Detection & Continuous Governance
    "mission_contract_health_status_result",
    "mission_contract_drift_review_result",
    "mission_contract_rollback_result",
    # Phase 47 Polymorphic Schema Semantics & Contract Compatibility
    "mission_polymorphic_schema_status_result",
    "mission_polymorphic_variant_review_result",
    "mission_polymorphic_compatibility_check_result",
    # Phase 48 Contract-Aware Autonomous Change Management
    "mission_contract_change_prediction_result",
    "mission_contract_migration_plan_result",
    "mission_contract_change_gate_action_result",
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
    "create_project",
    "delete_project",
    "open_project",
    "save_project_file",
    "delete_project_file",
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
    "mission_plan_decompose",
    "mission_checkpoint_create",
    "mission_checkpoint_restore",
    "mission_subdag_propose",
    "mission_subdag_get_history",
    "mission_plan_evaluate",
    "mission_adaptation_propose",
    "mission_adaptation_get_history",
    "mission_swarm_status",
    "mission_swarm_reassign",
    "mission_collaboration_status",
    "mission_collaboration_arbitrate",
    "mission_federation_status",
    "mission_federation_scale",
    "mission_federation_rebalance",
    "mission_federation_switch_mode",
    "mission_understanding_get",
    "mission_understanding_review",
    "mission_timeline_get",
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
    "mission_control_get",
    "mission_control_event_stream",
    "mission_control_command",
    "mission_intent_preview",
    "mission_intent_change",
    "mission_predict_impact",
    "mission_get_predictions",
    "mission_loop_status",
    "mission_loop_step",
    "mission_loop_run",
    "mission_loop_respond_human",
    "mission_decision_quality_status",
    "mission_policy_proposal_review",
    "mission_policy_rollback",
    # Phase 42
    "mission_experience_memory_status",
    "mission_experience_curate",
    # Phase 44
    "mission_semantic_graph_status",
    # Phase 45
    "mission_contract_discovery_status",
    "mission_contract_proposal_review",
    # Phase 46
    "mission_contract_health_status",
    "mission_contract_drift_review",
    "mission_contract_rollback",
    # Phase 47
    "mission_polymorphic_schema_status",
    "mission_polymorphic_variant_review",
    "mission_polymorphic_compatibility_check",
    # Phase 48
    "mission_contract_change_prediction",
    "mission_contract_migration_plan",
    "mission_contract_change_gate_action",
    # Phase 49
    "mission_build_contract_extraction_status",
    "mission_dynamic_consumer_resolution",
    "mission_build_contract_trigger_extract",
    # Phase 50
    "mission_behavioral_baseline_status",
    "mission_behavioral_proof_status",
    "mission_behavioral_proof_trigger",
}

MISSION_CLIENT_REQUIRED_FIELDS = {
    "mission_behavioral_baseline_status": (),
    "mission_behavioral_proof_status": (),
    "mission_behavioral_proof_trigger": (),
    "mission_build_contract_extraction_status": (),
    "mission_dynamic_consumer_resolution": (),
    "mission_build_contract_trigger_extract": (),
    "mission_contract_change_prediction": (),
    "mission_contract_migration_plan": ("migration_id",),
    "mission_contract_change_gate_action": ("action",),
    "mission_decision_quality_status": ("mission_id",),
    "mission_policy_proposal_review": ("proposal_id", "action"),
    "mission_policy_rollback": (),
    "mission_experience_memory_status": (),
    "mission_experience_curate": ("experience_id", "action"),
    "mission_semantic_graph_status": (),
    "mission_contract_discovery_status": (),
    "mission_contract_proposal_review": ("proposal_id", "action"),
    "mission_contract_health_status": (),
    "mission_contract_drift_review": ("drift_id", "action"),
    "mission_contract_rollback": ("contract_id", "target_version"),
    "mission_polymorphic_schema_status": (),
    "mission_polymorphic_variant_review": ("schema_id", "variant_id", "action"),
    "mission_polymorphic_compatibility_check": ("schema_id",),
    "mission_loop_status": ("mission_id",),
    "mission_loop_step": ("mission_id",),
    "mission_loop_run": ("mission_id",),
    "mission_loop_respond_human": ("mission_id", "action"),
    "mission_control_command": ("command_id", "mission_id", "command_type"),
    "mission_intent_preview": ("mission_id",),
    "mission_intent_change": ("mission_id",),
    "mission_predict_impact": ("mission_id",),
    "mission_get_predictions": ("mission_id",),
    "mission_list": ("project_id",),
    "mission_create": ("project_id", "title", "objective"),
    "mission_get": ("project_id", "mission_id"),
    "mission_update": ("project_id", "mission_id", "expected_version", "changes"),
    "mission_set_status": ("project_id", "mission_id", "expected_version", "status"),
    "work_package_create": ("project_id", "mission_id", "title"),
    "work_package_update": ("project_id", "mission_id", "work_package_id", "expected_version", "changes"),
    "work_package_set_status": ("project_id", "mission_id", "work_package_id", "expected_version", "status"),
    "work_package_add_dependency": (
        "project_id", "mission_id", "work_package_id", "dependency_id", "expected_version",
    ),
    "deliverable_create": ("project_id", "mission_id", "work_package_id", "name"),
    "deliverable_update": ("project_id", "mission_id", "deliverable_id", "expected_version", "changes"),
    "deliverable_set_status": ("project_id", "mission_id", "deliverable_id", "expected_version", "status"),
    "evidence_attach": ("project_id", "mission_id", "work_package_id", "kind", "source_ref"),
    "criterion_create": ("project_id", "mission_id", "owner_type", "owner_id", "description"),
    "criterion_set_status": ("project_id", "mission_id", "criterion_id", "expected_version", "status"),
    "mission_resume_snapshot": ("project_id", "mission_id"),
    "mission_execute_work_package": (
        "project_id", "mission_id", "work_package_id",
        "expected_mission_version", "expected_work_package_version",
    ),
    "mission_apply_execution": (
        "project_id", "mission_id", "execution_id", "expected_execution_version", "confirmed",
    ),
    "mission_review_execution": (
        "project_id", "mission_id", "execution_id", "decision", "review_note",
        "accepted_evidence_refs", "expected_execution_version",
    ),
    "mission_retry_execution": (
        "project_id", "mission_id", "execution_id", "expected_execution_version",
    ),
    "mission_cancel_execution": (
        "project_id", "mission_id", "execution_id", "expected_execution_version", "confirmed",
    ),
    "mission_release_stale_lock": (
        "project_id", "mission_id", "execution_id", "expected_execution_version", "confirmed",
    ),
    "mission_autonomy_run": (
        "project_id", "mission_id", "expected_mission_version", "confirmed",
    ),
    "mission_plan_decompose": (
        "project_id", "title", "objective",
    ),
    "mission_checkpoint_create": (
        "project_id", "mission_id",
    ),
    "mission_checkpoint_restore": (
        "project_id", "mission_id", "checkpoint_id",
    ),
    "mission_subdag_propose": (
        "project_id", "mission_id", "parent_task_id", "reason", "trigger",
    ),
    "mission_subdag_get_history": (
        "project_id", "mission_id",
    ),
    "mission_plan_evaluate": (
        "project_id", "mission_id",
    ),
    "mission_adaptation_propose": (
        "project_id", "mission_id", "proposal",
    ),
    "mission_adaptation_get_history": (
        "project_id", "mission_id",
    ),
    "mission_swarm_status": (
        "project_id", "mission_id",
    ),
    "mission_swarm_reassign": (
        "project_id", "mission_id", "task_id",
    ),
    "mission_collaboration_status": (
        "project_id", "mission_id",
    ),
    "mission_collaboration_arbitrate": (
        "project_id", "mission_id", "collaboration_id",
    ),
}


class WebSocketPayloadError(ValueError):
    pass


def validate_client_message(message: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(message, Mapping):
        raise WebSocketPayloadError("A mensagem WebSocket deve ser um objeto JSON.")
    payload = dict(message)
    message_type = _as_str(payload.get("type")).strip()
    if message_type not in CLIENT_MESSAGE_TYPES:
        raise WebSocketPayloadError(f"Operacao WebSocket desconhecida: {message_type or 'sem type'}.")
    required_fields = MISSION_CLIENT_REQUIRED_FIELDS.get(message_type, ())
    missing = [field for field in required_fields if field not in payload or payload[field] is None or payload[field] == ""]
    if missing:
        raise WebSocketPayloadError(f"Payload {message_type} incompleto; faltam: {', '.join(missing)}.")
    for version_field in (
        "expected_version",
        "expected_mission_version",
        "expected_work_package_version",
        "expected_execution_version",
    ):
        if version_field not in required_fields:
            continue
        version = payload.get(version_field)
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise WebSocketPayloadError(f"{version_field} deve ser um inteiro positivo.")
    if message_type.endswith("_update") and not isinstance(payload.get("changes"), dict):
        raise WebSocketPayloadError("changes deve ser um objeto JSON.")
    if message_type == "save_project_file":
        if not _as_str(payload.get("project_id")).strip() or not _as_str(payload.get("filename")).strip():
            raise WebSocketPayloadError("save_project_file exige project_id e filename.")
        if not isinstance(payload.get("content"), str):
            raise WebSocketPayloadError("content deve ser texto.")
        expected_sha256 = _as_str(payload.get("expected_sha256")).strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
            raise WebSocketPayloadError("expected_sha256 deve ser um SHA-256 valido.")
    if message_type in {
        "mission_apply_execution",
        "mission_cancel_execution",
        "mission_release_stale_lock",
        "mission_autonomy_run",
    }:
        if payload.get("confirmed") is not True:
            raise WebSocketPayloadError(f"{message_type} exige confirmed=true.")
    if message_type == "mission_autonomy_run":
        max_work_packages = payload.get("max_work_packages", 1)
        if (
            isinstance(max_work_packages, bool)
            or not isinstance(max_work_packages, int)
            or max_work_packages < 1
            or max_work_packages > 3
        ):
            raise WebSocketPayloadError(
                "max_work_packages deve ser um inteiro entre 1 e 3."
            )
        if "test_mode" in payload and not isinstance(
            payload.get("test_mode"),
            bool,
        ):
            raise WebSocketPayloadError("test_mode deve ser booleano.")
    if message_type == "mission_review_execution":
        decision = _as_str(payload.get("decision")).strip().upper()
        if decision not in {"ACCEPT", "REJECT"}:
            raise WebSocketPayloadError("decision deve ser ACCEPT ou REJECT.")
        if not isinstance(payload.get("accepted_evidence_refs"), list):
            raise WebSocketPayloadError("accepted_evidence_refs deve ser uma lista.")
    return payload

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


def normalize_canonical_sender(sender: Any) -> str:
    raw = _as_str(sender, "SISTEMA").strip()
    if not raw:
        return "SISTEMA"
    upper = raw.upper()
    if upper in {"OPENCLAW", "OPEN_CLAW", "JARVIS", "ASSISTANT", "AI", "ORCHESTRATOR", "ORQUESTRADOR"}:
        return "JARVIS"
    if upper in {"CLIENTE", "USER", "UTILIZADOR", "CEO"}:
        return "CLIENTE"
    if upper in {"SISTEMA", "SYSTEM"}:
        return "SISTEMA"
    return raw


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
            "sender": normalize_canonical_sender(message.get("sender")),
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
            "file_hashes": message.get("file_hashes") if isinstance(message.get("file_hashes"), dict) else {},
            "symbols": message.get("symbols") if isinstance(message.get("symbols"), dict) else {},
        }

    if message_type == "project_file_save_result":
        return {
            "type": "project_file_save_result",
            "ok": _as_bool(message.get("ok")),
            "project_id": _as_str(message.get("project_id")),
            "filename": _as_str(message.get("filename")),
            "sha256": _as_str(message.get("sha256")),
            "size_bytes": message.get("size_bytes", 0),
            "error": _as_str(message.get("error")),
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

    if message_type == "mission_list":
        return {"type": "mission_list", "project_id": _as_str(message.get("project_id")), "missions": _as_list(message.get("missions"))}

    if message_type == "mission_snapshot":
        return {
            "type": "mission_snapshot",
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

    if message_type == "lecture_lesson_generated":
        return {
            "type": "lecture_lesson_generated",
            "lesson": message.get("lesson") if isinstance(message.get("lesson"), dict) else {},
        }

    if message_type == "lecture_quiz_evaluated":
        return {
            "type": "lecture_quiz_evaluated",
            "topic": _as_str(message.get("topic")),
            "score": message.get("score", 100.0),
            "total_questions": message.get("total_questions", 3),
            "correct_answers": message.get("correct_answers", 3),
            "feedback": _as_str(message.get("feedback")),
            "transfer_passed": _as_bool(message.get("transfer_passed", True)),
            "transfer_feedback": _as_str(message.get("transfer_feedback")),
            "student_mastery": message.get("student_mastery", 0.95),
            "next_review_days": message.get("next_review_days", 3),
            "next_review_timestamp": message.get("next_review_timestamp", 0),
        }

    if message_type == "lecture_history_response":
        return {
            "type": "lecture_history_response",
            "history": _as_list(message.get("history")),
        }

    if message_type == "lecture_status_response":
        return {
            "type": "lecture_status_response",
            "is_recording": _as_bool(message.get("is_recording")),
            "session": message.get("session") if isinstance(message.get("session"), dict) else None,
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
