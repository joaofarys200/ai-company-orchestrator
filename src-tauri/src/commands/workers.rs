use serde_json::json;
use tauri::State;

use crate::commands::media::RuntimeServices;
use crate::error::AppError;
use crate::workers::supervisor::{WorkerPoolRole, WorkerStatusSnapshot};

#[tauri::command]
pub async fn get_worker_health(
    services: State<'_, RuntimeServices>,
) -> Result<Vec<WorkerStatusSnapshot>, AppError> {
    Ok(services.workers.status_snapshot().await)
}

#[tauri::command]
pub async fn restart_worker_role(
    services: State<'_, RuntimeServices>,
    role: WorkerPoolRole,
) -> Result<WorkerStatusSnapshot, AppError> {
    services.workers.shutdown_role(role).await;
    services
        .workers
        .ensure_worker(role)
        .await
        .map_err(|err| AppError::new("WORKER_START_FAILED", err.to_string()))?;

    services
        .workers
        .status_snapshot()
        .await
        .into_iter()
        .find(|snap| snap.role == role)
        .ok_or_else(|| AppError::new("WORKER_MISSING", "Worker status unavailable after restart"))
}

#[tauri::command]
pub async fn worker_system_health(
    services: State<'_, RuntimeServices>,
    role: WorkerPoolRole,
) -> Result<serde_json::Value, AppError> {
    services
        .workers
        .call(
            role,
            "system.health",
            json!({}),
            std::time::Duration::from_secs(10),
        )
        .await
        .map_err(|err| AppError::new("WORKER_RPC_FAILED", err.to_string()))
}

