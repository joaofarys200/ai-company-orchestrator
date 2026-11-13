use std::sync::Arc;
use tauri::State;

use crate::error::AppError;
use crate::process::preview_server::PreviewServerHandle;
use crate::protocol::loopback::{LoopbackConfig, LoopbackHandle, MediaTicketResponse};
use crate::workers::supervisor::WorkerSupervisor;

/// Managed runtime services started during Tauri shell setup.
pub struct RuntimeServices {
    pub loopback: LoopbackHandle,
    pub preview: PreviewServerHandle,
    pub workers: Arc<WorkerSupervisor>,
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

