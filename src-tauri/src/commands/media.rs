use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use tauri::State;
use tokio::sync::Mutex;

use crate::error::AppError;
use crate::permissions::gateway::PermissionGateway;
use crate::process::preview_server::PreviewServerHandle;
use crate::protocol::loopback::{LoopbackConfig, LoopbackHandle, MediaTicketResponse};
use crate::sentinel::scheduler::SentinelScheduler;
use crate::storage::sqlite::SqliteDatabase;
use crate::storage::study_store::StudyStore;
use crate::workers::supervisor::{WorkerPoolRole, WorkerSupervisor};

#[derive(Debug, Clone)]
pub struct ActiveDispatch {
    pub role: WorkerPoolRole,
    pub worker_request_id: String,
}

/// Managed runtime services started during Tauri shell setup.
pub struct RuntimeServices {
    pub project_root: PathBuf,
    pub db: Arc<SqliteDatabase>,
    pub study_store: Arc<StudyStore>,
    pub loopback: LoopbackHandle,
    pub preview: PreviewServerHandle,
    pub workers: Arc<WorkerSupervisor>,
    pub permissions: Arc<PermissionGateway>,
    pub sentinel: Arc<SentinelScheduler>,
    pub active_dispatches: Arc<Mutex<HashMap<String, ActiveDispatch>>>,
}

#[tauri::command]
pub fn get_loopback_config(services: State<'_, RuntimeServices>) -> LoopbackConfig {
    services
        .loopback
        .config(Some(services.preview.base_url().to_string()))
}

#[tauri::command]
pub fn get_media_ticket(
    services: State<'_, RuntimeServices>,
    doc_id: String,
) -> Result<MediaTicketResponse, AppError> {
    services.loopback.issue_media_ticket(&doc_id, None)
}

