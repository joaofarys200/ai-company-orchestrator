use std::time::{SystemTime, UNIX_EPOCH};

use serde::Serialize;
use tauri_plugin_opener::OpenerExt;

use crate::error::AppError;
use crate::permissions::path_jail::{
    default_open_roots, resolve_project_root, validate_open_target, ValidatedOpenTarget,
};
use crate::{APP_DISPLAY_NAME, SHELL_NAME};

#[derive(Debug, Clone, Serialize)]
pub struct PingResponse {
    pub status: String,
    pub shell: String,
    pub app_version: String,
    pub timestamp_ms: u128,
}

#[derive(Debug, Clone, Serialize)]
pub struct SystemInfo {
    pub shell: String,
    pub app_name: String,
    pub app_version: String,
    pub os: String,
    pub arch: String,
    pub project_root: String,
    pub dialog_supported: bool,
    pub native_open_supported: bool,
}

pub fn build_ping_response(app_version: &str) -> PingResponse {
    let timestamp_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    PingResponse {
        status: "ok".to_string(),
        shell: SHELL_NAME.to_string(),
        app_version: app_version.to_string(),
        timestamp_ms,
    }
}

pub fn build_system_info(app_version: &str) -> SystemInfo {
    let root = resolve_project_root();
    SystemInfo {
        shell: SHELL_NAME.to_string(),
        app_name: APP_DISPLAY_NAME.to_string(),
        app_version: app_version.to_string(),
        os: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
        project_root: root.to_string_lossy().to_string(),
        dialog_supported: true,
        native_open_supported: true,
    }
}

#[tauri::command]
pub fn system_ping(app: tauri::AppHandle) -> PingResponse {
    let version = app.package_info().version.to_string();
    build_ping_response(&version)
}

#[tauri::command]
pub fn system_info(app: tauri::AppHandle) -> SystemInfo {
    let version = app.package_info().version.to_string();
    build_system_info(&version)
}

#[tauri::command]
pub fn system_open_path(app: tauri::AppHandle, target: String) -> Result<(), AppError> {
    let root = resolve_project_root();
    let allowed_roots = default_open_roots(&root);
    match validate_open_target(&allowed_roots, &target)? {
        ValidatedOpenTarget::Url(url) => app
            .opener()
            .open_url(url, None::<&str>)
            .map_err(|err| AppError::new("OPENER_URL_FAILED", err.to_string())),
        ValidatedOpenTarget::LocalPath(path) => app
            .opener()
            .open_path(path.to_string_lossy().to_string(), None::<&str>)
            .map_err(|err| AppError::new("OPENER_PATH_FAILED", err.to_string())),
    }
}

