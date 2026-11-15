use serde_json::Value;
use tauri::State;

use crate::commands::media::RuntimeServices;
use crate::error::AppError;
use crate::storage::study_store::StudyCatalogSnapshot;

#[tauri::command]
pub async fn study_store_refresh(
    services: State<'_, RuntimeServices>,
) -> Result<StudyCatalogSnapshot, AppError> {
    services
        .study_store
        .refresh()
        .await
        .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))
}

#[tauri::command]
pub async fn study_store_list_documents(
    services: State<'_, RuntimeServices>,
    refresh: Option<bool>,
) -> Result<Vec<Value>, AppError> {
    if refresh.unwrap_or(true) {
        services
            .study_store
            .refresh()
            .await
            .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
    }
    Ok(services.study_store.list_documents().await)
}

#[tauri::command]
pub async fn study_store_get_document(
    services: State<'_, RuntimeServices>,
    document_id: String,
    refresh: Option<bool>,
) -> Result<Option<Value>, AppError> {
    if refresh.unwrap_or(true) {
        services
            .study_store
            .refresh()
            .await
            .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
    }
    services
        .study_store
        .get_document(&document_id)
        .await
        .map_err(|err| AppError::new("STUDY_STORE_READ_FAILED", err))
}

#[tauri::command]
pub async fn study_store_list_collections(
    services: State<'_, RuntimeServices>,
    refresh: Option<bool>,
) -> Result<Vec<Value>, AppError> {
    if refresh.unwrap_or(true) {
        services
            .study_store
            .refresh()
            .await
            .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
    }
    Ok(services.study_store.list_collections().await)
}

#[tauri::command]
pub async fn study_store_list_flashcards(
    services: State<'_, RuntimeServices>,
    document_id: Option<String>,
    refresh: Option<bool>,
) -> Result<Vec<Value>, AppError> {
    if refresh.unwrap_or(true) {
        services
            .study_store
            .refresh()
            .await
            .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
    }
    services
        .study_store
        .list_flashcards(document_id.as_deref())
        .await
        .map_err(|err| AppError::new("STUDY_STORE_READ_FAILED", err))
}
