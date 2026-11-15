use chrono::DateTime;
use serde_json::{json, Value};
use tauri::State;

use crate::commands::media::RuntimeServices;
use crate::error::AppError;
use crate::permissions::gateway::PermissionRequestRecord;
use crate::sentinel::scheduler::{SentinelObservation, SentinelStatusSnapshot};

/// Converts an internal Rust HITL `PermissionRequestRecord` into the snake_case
/// `PermissionRequestData` payload expected by the React permission store/modal.
pub fn permission_record_to_frontend_json(record: &PermissionRequestRecord) -> Value {
    let created_at_secs = DateTime::parse_from_rfc3339(&record.created_at)
        .map(|dt| dt.timestamp() as f64)
        .unwrap_or(0.0);
    let expires_at_secs = created_at_secs + (record.expires_in_ms as f64 / 1000.0);
    json!({
        "request_id": record.request_id,
        "tool_name": record.tool_name,
        "requested_operation": record.requested_operation,
        "reason": record.reason,
        "risk_level": record.risk_level,
        "required_privileges": "standard",
        "affected_resources": record.affected_resources,
        "mission_id": record.mission_id,
        "project_id": record.project_id,
        "agent_id": record.agent_id,
        "tool_type": "worker_reverse_rpc",
        "installation_required": false,
        "alternative_available": false,
        "created_at": created_at_secs,
        "expires_at": expires_at_secs,
        "status": record.status,
        "policy_reason": record.policy_reason,
        "decided_by": record.decided_by,
        "decision_evidence": {},
    })
}

#[tauri::command]
pub async fn list_pending_permissions(
    services: State<'_, RuntimeServices>,
) -> Result<Vec<PermissionRequestRecord>, AppError> {
    Ok(services.permissions.pending_requests().await)
}

#[tauri::command]
pub async fn approve_permission_request(
    services: State<'_, RuntimeServices>,
    request_id: String,
    decided_by: Option<String>,
    grant_type: Option<String>,
    project_id: Option<String>,
    mission_id: Option<String>,
) -> Result<PermissionRequestRecord, AppError> {
    services
        .permissions
        .approve_request(
            &request_id,
            decided_by.as_deref().unwrap_or("operator"),
            grant_type.as_deref().unwrap_or("allow_once"),
            project_id.as_deref(),
            mission_id.as_deref(),
        )
        .await
        .map_err(|err| AppError::new("PERMISSION_APPROVE_FAILED", err))
}

#[tauri::command]
pub async fn deny_permission_request(
    services: State<'_, RuntimeServices>,
    request_id: String,
    decided_by: Option<String>,
    reason: Option<String>,
    project_id: Option<String>,
    mission_id: Option<String>,
) -> Result<PermissionRequestRecord, AppError> {
    services
        .permissions
        .deny_request(
            &request_id,
            decided_by.as_deref().unwrap_or("operator"),
            reason.as_deref().unwrap_or("Denied by operator"),
            project_id.as_deref(),
            mission_id.as_deref(),
        )
        .await
        .map_err(|err| AppError::new("PERMISSION_DENY_FAILED", err))
}

#[tauri::command]
pub async fn sentinel_status(
    services: State<'_, RuntimeServices>,
) -> Result<SentinelStatusSnapshot, AppError> {
    Ok(services.sentinel.status_snapshot().await)
}

#[tauri::command]
pub async fn sentinel_tick_shadow(
    services: State<'_, RuntimeServices>,
) -> Result<SentinelObservation, AppError> {
    services
        .sentinel
        .tick_once()
        .await
        .map_err(|err| AppError::new("SENTINEL_TICK_FAILED", err))
}
