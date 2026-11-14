use std::collections::HashSet;
use std::sync::Arc;
use std::time::Duration;

use serde_json::{json, Value};
use tauri::{AppHandle, Emitter, State};

use crate::commands::media::{ActiveDispatch, RuntimeServices};
use crate::commands::security::permission_record_to_frontend_json;
use crate::error::AppError;
use crate::permissions::gateway::PermissionGateway;
use crate::workers::rpc_client::WorkerStreamEvent;
use crate::workers::supervisor::WorkerPoolRole;

pub const JARVIS_EVENT_NAME: &str = "jarvis:event";
pub const JARVIS_WORKER_PROGRESS_EVENT: &str = "jarvis:worker_progress";

/// Maps each `CLIENT_MESSAGE_TYPES` message name to its owning domain worker pool role.
pub fn route_message_to_worker_role(msg_type: &str) -> Option<WorkerPoolRole> {
    if msg_type.starts_with("study_") {
        return Some(WorkerPoolRole::Study);
    }
    if matches!(
        msg_type,
        "start_lecture_recording"
            | "stop_lecture_recording"
            | "get_lecture_status"
            | "list_lecture_history"
            | "generate_lecture_lesson"
            | "submit_lecture_quiz"
    ) {
        return Some(WorkerPoolRole::Study);
    }

    if msg_type == "toggle_voice" || msg_type.starts_with("voice_") {
        return Some(WorkerPoolRole::Voice);
    }

    if msg_type.starts_with("mission_")
        || msg_type.starts_with("work_package_")
        || msg_type.starts_with("deliverable_")
        || msg_type.starts_with("criterion_")
        || msg_type.starts_with("evidence_")
        || msg_type.starts_with("sentinel_")
        || msg_type.starts_with("permission_")
        || msg_type == "action_confirm_response"
    {
        return Some(WorkerPoolRole::Mission);
    }

    if matches!(
        msg_type,
        "directive"
            | "select_template"
            | "get_planner_state"
            | "get_ast_state"
            | "run_project"
            | "stop_project"
            | "list_projects"
            | "create_project"
            | "delete_project"
            | "open_project"
            | "save_project_file"
            | "create_project_file"
            | "rename_project_file"
            | "delete_project_file"
            | "index_project"
            | "find_references"
            | "semantic_search"
            | "create_coding_session"
            | "apply_coding_session"
            | "rollback_coding_session"
            | "get_coding_session"
    ) {
        return Some(WorkerPoolRole::Ai);
    }

    None
}

fn timeout_for_message(msg_type: &str) -> Duration {
    if msg_type == "directive"
        || msg_type.contains("_run")
        || msg_type.contains("_execute")
        || msg_type.contains("_generate")
        || msg_type.contains("_synthesize")
        || msg_type.contains("_ingest")
        || msg_type == "start_improvement_batch"
        || msg_type == "apply_coding_session"
    {
        Duration::from_secs(900)
    } else {
        Duration::from_secs(120)
    }
}

fn attach_request_id(mut event: Value, client_request_id: Option<&str>, worker_req_id: &str) -> Value {
    if let (Some(obj), Some(cid)) = (event.as_object_mut(), client_request_id) {
        let should_replace = match obj.get("request_id").and_then(Value::as_str) {
            None => true,
            Some(existing) => existing.trim().is_empty() || existing == worker_req_id,
        };
        if should_replace {
            obj.insert("request_id".to_string(), Value::String(cid.to_string()));
        }
    }
    event
}

fn parse_worker_chunk_event(
    delta: &str,
    client_request_id: Option<&str>,
    worker_req_id: &str,
) -> Option<Value> {
    let parsed = serde_json::from_str::<Value>(delta).ok()?;
    let ev = parsed.get("event")?.clone();
    if !ev.is_object() {
        return None;
    }
    Some(attach_request_id(ev, client_request_id, worker_req_id))
}

fn emit_jarvis_event(app: &AppHandle, event: Value, client_request_id: Option<&str>) {
    let stamped = attach_request_id(event, client_request_id, "");
    let _ = app.emit(JARVIS_EVENT_NAME, &stamped);
}

fn build_error_event(msg_type: &str, err_text: &str, client_request_id: Option<&str>) -> Value {
    let mut ev = if msg_type.starts_with("study_") {
        json!({
            "type": "study_error",
            "error": err_text,
            "message": err_text,
        })
    } else {
        json!({
            "type": "system",
            "content": err_text,
        })
    };
    if let Some(cid) = client_request_id {
        if let Some(obj) = ev.as_object_mut() {
            obj.insert("request_id".to_string(), Value::String(cid.to_string()));
        }
    }
    ev
}

fn emit_fast_path_events(app: &AppHandle, events: Vec<Value>, client_request_id: Option<&str>) {
    for ev in events {
        emit_jarvis_event(app, ev, client_request_id);
    }
}

/// Executes minimal Rust-native fast-path control operations (`ping`).
async fn try_execute_native_fast_path_events(msg_type: &str) -> Result<Option<Vec<Value>>, AppError> {
    match msg_type {
        "ping" => Ok(Some(vec![json!({ "type": "pong" })])),
        _ => Ok(None),
    }
}

async fn merge_native_pending_permissions(mut event: Value, permissions: &PermissionGateway) -> Value {
    if event.get("type").and_then(Value::as_str) != Some("permission_pending_list") {
        return event;
    }
    let native_pending = permissions.pending_requests().await;
    if native_pending.is_empty() {
        return event;
    }
    if let Some(arr) = event.get_mut("data").and_then(Value::as_array_mut) {
        let mut seen: HashSet<String> = arr
            .iter()
            .filter_map(|item| item.get("request_id").and_then(Value::as_str).map(String::from))
            .collect();
        for rec in native_pending {
            if seen.insert(rec.request_id.clone()) {
                arr.push(permission_record_to_frontend_json(&rec));
            }
        }
    }
    event
}

fn spawn_worker_stream_forwarder(
    app: AppHandle,
    permissions: Arc<PermissionGateway>,
    active_dispatches: Arc<tokio::sync::Mutex<std::collections::HashMap<String, ActiveDispatch>>>,
    correlation_key: String,
    client_request_id: Option<String>,
    worker_req_id: String,
    msg_type: String,
    mut stream_rx: tokio::sync::mpsc::Receiver<WorkerStreamEvent>,
    response_fut: std::pin::Pin<
        Box<dyn std::future::Future<Output = Result<Value, crate::workers::rpc_client::RpcCallError>> + Send>,
    >,
) {
    tauri::async_runtime::spawn(async move {
        let app_for_stream = app.clone();
        let req_id_for_stream = client_request_id.clone();
        let worker_id_for_stream = worker_req_id.clone();
        let perms_for_stream = Arc::clone(&permissions);

        let stream_task = tauri::async_runtime::spawn(async move {
            while let Some(item) = stream_rx.recv().await {
                match item {
                    WorkerStreamEvent::Chunk { delta, .. } => {
                        if let Some(ev) = parse_worker_chunk_event(
                            &delta,
                            req_id_for_stream.as_deref(),
                            &worker_id_for_stream,
                        ) {
                            let enriched = merge_native_pending_permissions(ev, &perms_for_stream).await;
                            let _ = app_for_stream.emit(JARVIS_EVENT_NAME, &enriched);
                        }
                    }
                    WorkerStreamEvent::Progress {
                        request_id,
                        stage,
                        progress,
                        message,
                        eta_seconds,
                    } => {
                        let _ = app_for_stream.emit(
                            JARVIS_WORKER_PROGRESS_EVENT,
                            json!({
                                "request_id": req_id_for_stream.as_deref().unwrap_or(&request_id),
                                "stage": stage,
                                "progress": progress,
                                "message": message,
                                "eta_seconds": eta_seconds,
                            }),
                        );
                    }
                }
            }
        });

        let rpc_res = response_fut.await;
        let _ = stream_task.await;
        active_dispatches.lock().await.remove(&correlation_key);

        if let Err(err) = rpc_res {
            let err_event = build_error_event(&msg_type, &err.to_string(), client_request_id.as_deref());
            let _ = app.emit(JARVIS_EVENT_NAME, &err_event);
        }
    });
}

#[tauri::command]
pub async fn dispatch_client_message(
    app: AppHandle,
    services: State<'_, RuntimeServices>,
    message: Value,
) -> Result<Value, AppError> {
    let msg_type = message
        .get("type")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .ok_or_else(|| AppError::new("INVALID_MESSAGE", "ClientMessage must include a non-empty `type` field"))?
        .to_string();

    let client_request_id = message
        .get("request_id")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(String::from);

    if msg_type == "cancel_task" {
        let target_id = message
            .get("target_request_id")
            .or_else(|| message.get("request_id"))
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|s| !s.is_empty());
        if let Some(tid) = target_id {
            let reason = message
                .get("reason")
                .and_then(Value::as_str)
                .unwrap_or("user_cancelled");
            let active = services.active_dispatches.lock().await.get(tid).cloned();
            if let Some(entry) = active {
                let _ = services
                    .workers
                    .cancel_task(entry.role, &entry.worker_request_id, reason)
                    .await;
            }
        }
        return Ok(Value::Null);
    }

    if let Some(events) = try_execute_native_fast_path_events(&msg_type).await? {
        emit_fast_path_events(&app, events, client_request_id.as_deref());
        return Ok(Value::Null);
    }

    if let Some(events) = crate::knowledge::dispatch::try_execute_knowledge_fast_path(
        &services.project_root,
        &services.db,
        &msg_type,
        &message,
    )
    .await?
    {
        emit_fast_path_events(&app, events, client_request_id.as_deref());
        return Ok(Value::Null);
    }

    if let Some(events) = crate::commands::permission_dispatch::try_execute_permission_fast_path(
        &services.project_root,
        &services.permissions,
        &msg_type,
        &message,
    )
    .await?
    {
        emit_fast_path_events(&app, events, client_request_id.as_deref());
        return Ok(Value::Null);
    }

    if let Some(events) = crate::storage::study_catalog_ops::try_execute_study_fast_path(
        &services.project_root,
        &services.study_store,
        &msg_type,
        &message,
    )
    .await?
    {
        emit_fast_path_events(&app, events, client_request_id.as_deref());
        return Ok(Value::Null);
    }

    if let Some(events) = crate::commands::project_dispatch::try_execute_project_fast_path(
        &app,
        &*services,
        &msg_type,
        &message,
    )
    .await?
    {
        emit_fast_path_events(&app, events, client_request_id.as_deref());
        return Ok(Value::Null);
    }

    let role = route_message_to_worker_role(&msg_type).ok_or_else(|| {
        AppError::new(
            "UNKNOWN_MESSAGE_TYPE",
            format!("Unsupported client message type `{msg_type}`"),
        )
    })?;

    let timeout = timeout_for_message(&msg_type);
    let (worker_req_id, stream_rx, response_fut) = services
        .workers
        .start_streaming(
            role,
            "domain.dispatch",
            json!({ "message": message }),
            timeout,
        )
        .await
        .map_err(|err| AppError::new("WORKER_DISPATCH_FAILED", err.to_string()))?;

    let correlation_key = client_request_id
        .clone()
        .unwrap_or_else(|| worker_req_id.clone());

    services.active_dispatches.lock().await.insert(
        correlation_key.clone(),
        ActiveDispatch {
            role,
            worker_request_id: worker_req_id.clone(),
        },
    );

    spawn_worker_stream_forwarder(
        app,
        Arc::clone(&services.permissions),
        Arc::clone(&services.active_dispatches),
        correlation_key,
        client_request_id,
        worker_req_id,
        msg_type,
        stream_rx,
        response_fut,
    );

    Ok(Value::Null)
}

#[tauri::command]
pub async fn cancel_client_request(
    services: State<'_, RuntimeServices>,
    request_id: String,
    reason: Option<String>,
) -> Result<bool, AppError> {
    let cleaned = request_id.trim();
    if cleaned.is_empty() {
        return Ok(false);
    }
    let active = services.active_dispatches.lock().await.get(cleaned).cloned();
    let Some(entry) = active else {
        return Ok(false);
    };
    services
        .workers
        .cancel_task(
            entry.role,
            &entry.worker_request_id,
            reason.as_deref().unwrap_or("user_cancelled"),
        )
        .await
        .map_err(|err| AppError::new("WORKER_CANCEL_FAILED", err.to_string()))?;
    Ok(true)
}

#[tauri::command]
pub async fn trigger_initial_sync(
    app: AppHandle,
    services: State<'_, RuntimeServices>,
    project_id: Option<String>,
) -> Result<Value, AppError> {
    // Emit Rust-owned Knowledge snapshots (`rules_list` + `notes_list`) immediately without a worker.
    for init_msg in ["get_rules", "get_notes"] {
        if let Some(events) = crate::knowledge::dispatch::try_execute_knowledge_fast_path(
            &services.project_root,
            &services.db,
            init_msg,
            &json!({}),
        )
        .await?
        {
            emit_fast_path_events(&app, events, None);
        }
    }

    // Emit any already-pending Rust HITL permission requests immediately.
    let native_pending: Vec<Value> = services
        .permissions
        .pending_requests()
        .await
        .iter()
        .map(permission_record_to_frontend_json)
        .collect();
    if !native_pending.is_empty() {
        emit_jarvis_event(
            &app,
            json!({
                "type": "permission_pending_list",
                "data": native_pending,
            }),
            None,
        );
    }

    let proj = project_id.unwrap_or_else(|| "ALL".to_string());
    for role in [
        WorkerPoolRole::Ai,
        WorkerPoolRole::Study,
        WorkerPoolRole::Mission,
    ] {
        let params = if role == WorkerPoolRole::Mission {
            json!({ "project_id": proj })
        } else {
            json!({})
        };
        if let Ok((worker_req_id, stream_rx, response_fut)) = services
            .workers
            .start_streaming(role, "domain.initial_sync", params, Duration::from_secs(60))
            .await
        {
            spawn_worker_stream_forwarder(
                app.clone(),
                Arc::clone(&services.permissions),
                Arc::clone(&services.active_dispatches),
                worker_req_id.clone(),
                None,
                worker_req_id,
                "initial_sync".to_string(),
                stream_rx,
                response_fut,
            );
        }
    }

    Ok(json!({ "status": "ok" }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::storage::sqlite::SqliteDatabase;
    use tempfile::TempDir;

    #[test]
    fn route_message_covers_all_production_domains() {
        assert_eq!(route_message_to_worker_role("directive"), Some(WorkerPoolRole::Ai));
        assert_eq!(route_message_to_worker_role("select_template"), Some(WorkerPoolRole::Ai));
        assert_eq!(route_message_to_worker_role("get_planner_state"), Some(WorkerPoolRole::Ai));
        assert_eq!(route_message_to_worker_role("list_projects"), Some(WorkerPoolRole::Ai));
        assert_eq!(route_message_to_worker_role("save_project_file"), Some(WorkerPoolRole::Ai));
        assert_eq!(route_message_to_worker_role("create_coding_session"), Some(WorkerPoolRole::Ai));

        assert_eq!(route_message_to_worker_role("study_list_documents"), Some(WorkerPoolRole::Study));
        assert_eq!(route_message_to_worker_role("study_mode_get_flashcards"), Some(WorkerPoolRole::Study));
        assert_eq!(route_message_to_worker_role("start_lecture_recording"), Some(WorkerPoolRole::Study));
        assert_eq!(route_message_to_worker_role("submit_lecture_quiz"), Some(WorkerPoolRole::Study));

        for retired_knowledge_msg in [
            "get_notes",
            "read_note",
            "save_note",
            "get_rules",
            "delete_rule",
            "delete_architecture",
            "delete_decision",
            "get_vault_diagnostics",
            "audit_note_quality",
            "enrich_note",
            "rollback_note",
            "get_queue_status",
            "pause_queue_worker",
            "resume_queue_worker",
            "start_improvement_batch",
        ] {
            assert_eq!(
                route_message_to_worker_role(retired_knowledge_msg),
                None,
                "Knowledge route {retired_knowledge_msg} must stay native in Rust and never route to a Python worker"
            );
        }
        assert!(
            !WorkerPoolRole::production_roles().contains(&WorkerPoolRole::Knowledge),
            "WorkerPoolRole::Knowledge must remain retired from production_roles()"
        );

        assert_eq!(route_message_to_worker_role("mission_list"), Some(WorkerPoolRole::Mission));
        assert_eq!(route_message_to_worker_role("work_package_create"), Some(WorkerPoolRole::Mission));
        assert_eq!(route_message_to_worker_role("sentinel_get_status"), Some(WorkerPoolRole::Mission));
        assert_eq!(route_message_to_worker_role("permission_approve"), Some(WorkerPoolRole::Mission));
        assert_eq!(route_message_to_worker_role("action_confirm_response"), Some(WorkerPoolRole::Mission));

        assert_eq!(route_message_to_worker_role("toggle_voice"), Some(WorkerPoolRole::Voice));
        assert_eq!(route_message_to_worker_role("nonexistent_command"), None);
    }

    #[test]
    fn parse_worker_stream_chunk_preserves_client_request_id() {
        let delta = r#"{"event":{"type":"study_documents_list","documents":[],"request_id":"req-worker-internal"}}"#;
        let parsed = parse_worker_chunk_event(delta, Some("corr-client-99"), "req-worker-internal")
            .expect("chunk must parse");
        assert_eq!(parsed["type"], "study_documents_list");
        assert_eq!(parsed["request_id"], "corr-client-99");

        let delta_missing = r#"{"event":{"type":"rules_list","rules":[]}}"#;
        let parsed2 = parse_worker_chunk_event(delta_missing, Some("corr-client-100"), "req-w2")
            .expect("chunk must backfill request_id");
        assert_eq!(parsed2["request_id"], "corr-client-100");
    }

    #[tokio::test]
    async fn native_fast_path_executes_sqlite_rule_architecture_and_decision_flows() {
        let dir = TempDir::new().unwrap();
        let db = SqliteDatabase::open(dir.path().join("database.db")).unwrap();

        let ping_ev = try_execute_native_fast_path_events("ping")
            .await
            .unwrap()
            .expect("ping handled natively");
        assert_eq!(ping_ev, vec![json!({ "type": "pong" })]);

        db.add_compounding_rule("k1", "desc", "corr").await.unwrap();
        db.add_architecture_memory("mod_a", "purpose", "dep", "cons")
            .await
            .unwrap();
        db.add_engineering_decision("dec_1", "reason", "high")
            .await
            .unwrap();

        let rules_ev = crate::knowledge::dispatch::try_execute_knowledge_fast_path(
            dir.path(),
            &db,
            "get_rules",
            &json!({ "type": "get_rules" }),
        )
        .await
        .unwrap()
        .expect("get_rules handled natively");
        assert_eq!(rules_ev.len(), 1);
        assert_eq!(rules_ev[0]["type"], "rules_list");
        assert_eq!(rules_ev[0]["rules"][0]["rule_key"], "k1");

        let del_rule = crate::knowledge::dispatch::try_execute_knowledge_fast_path(
            dir.path(),
            &db,
            "delete_rule",
            &json!({ "type": "delete_rule", "key": "k1" }),
        )
        .await
        .unwrap()
        .expect("delete_rule handled natively");
        assert_eq!(del_rule.len(), 2);
        assert_eq!(del_rule[0]["type"], "rules_list");
        assert_eq!(del_rule[1]["type"], "rules_updated");
        assert!(del_rule[1]["rules"].as_array().unwrap().is_empty());

        let del_arch = crate::knowledge::dispatch::try_execute_knowledge_fast_path(
            dir.path(),
            &db,
            "delete_architecture",
            &json!({ "type": "delete_architecture", "module": "mod_a" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(del_arch[0]["type"], "architecture_updated");
        assert!(del_arch[0]["architecture"].as_array().unwrap().is_empty());

        let del_dec = crate::knowledge::dispatch::try_execute_knowledge_fast_path(
            dir.path(),
            &db,
            "delete_decision",
            &json!({ "type": "delete_decision", "decision": "dec_1" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(del_dec[0]["type"], "decisions_updated");
        assert!(del_dec[0]["decisions"].as_array().unwrap().is_empty());
    }
}
