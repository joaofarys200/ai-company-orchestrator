use tauri::State;

use crate::commands::media::RuntimeServices;
use crate::error::AppError;
use crate::permissions::gateway::PermissionRequestRecord;
use crate::sentinel::scheduler::{SentinelObservation, SentinelStatusSnapshot};

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
