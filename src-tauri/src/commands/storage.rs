use serde_json::{json, Value};
use tauri::State;

use crate::commands::media::RuntimeServices;
use crate::error::AppError;
use crate::storage::sqlite::{
    ArchitectureMemoryRecord, CompoundingRuleRecord, EngineeringDecisionRecord, MessageRecord,
    ProjectRecord, SessionRecord,
};

pub fn compounding_rules_to_json(records: &[CompoundingRuleRecord]) -> Vec<Value> {
    records
        .iter()
        .map(|r| {
            json!({
                "rule_key": r.rule_key,
                "description": r.description,
                "correction": r.correction,
            })
        })
        .collect()
}

pub fn architecture_memory_to_json(records: &[ArchitectureMemoryRecord]) -> Vec<Value> {
    records
        .iter()
        .map(|r| {
            json!({
                "module": r.module,
                "purpose": r.purpose,
                "dependencies": r.dependencies,
                "constraints": r.constraints,
                "updated_at": r.updated_at,
            })
        })
        .collect()
}

pub fn engineering_decisions_to_json(records: &[EngineeringDecisionRecord]) -> Vec<Value> {
    records
        .iter()
        .map(|r| {
            json!({
                "decision": r.decision,
                "reason": r.reason,
                "impact": r.impact,
                "created_at": r.created_at,
            })
        })
        .collect()
}

#[tauri::command]
pub async fn sqlite_list_sessions(
    services: State<'_, RuntimeServices>,
    limit: Option<i64>,
) -> Result<Vec<SessionRecord>, AppError> {
    services
        .db
        .list_sessions(limit.unwrap_or(50))
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_create_session(
    services: State<'_, RuntimeServices>,
    name: String,
) -> Result<SessionRecord, AppError> {
    services
        .db
        .create_session(name)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_list_messages(
    services: State<'_, RuntimeServices>,
    session_id: i64,
    limit: Option<i64>,
) -> Result<Vec<MessageRecord>, AppError> {
    services
        .db
        .list_messages(session_id, limit.unwrap_or(200))
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_add_message(
    services: State<'_, RuntimeServices>,
    session_id: i64,
    sender: String,
    role: String,
    content: String,
) -> Result<MessageRecord, AppError> {
    services
        .db
        .add_message(session_id, &sender, role, content)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_list_projects(
    services: State<'_, RuntimeServices>,
    limit: Option<i64>,
) -> Result<Vec<ProjectRecord>, AppError> {
    services
        .db
        .list_projects(limit.unwrap_or(100))
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_get_compounding_rules(
    services: State<'_, RuntimeServices>,
) -> Result<Vec<Value>, AppError> {
    let rules = services
        .db
        .get_compounding_rules()
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
    Ok(compounding_rules_to_json(&rules))
}

#[tauri::command]
pub async fn sqlite_delete_compounding_rule(
    services: State<'_, RuntimeServices>,
    rule_key: String,
) -> Result<Vec<Value>, AppError> {
    services
        .db
        .delete_compounding_rule(rule_key)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))?;
    let rules = services
        .db
        .get_compounding_rules()
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
    Ok(compounding_rules_to_json(&rules))
}

#[tauri::command]
pub async fn sqlite_get_architecture_memory(
    services: State<'_, RuntimeServices>,
) -> Result<Vec<Value>, AppError> {
    let arch = services
        .db
        .get_architecture_memory()
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
    Ok(architecture_memory_to_json(&arch))
}

#[tauri::command]
pub async fn sqlite_delete_architecture_memory(
    services: State<'_, RuntimeServices>,
    module: String,
) -> Result<Vec<Value>, AppError> {
    services
        .db
        .delete_architecture_memory(module)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))?;
    let arch = services
        .db
        .get_architecture_memory()
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
    Ok(architecture_memory_to_json(&arch))
}

#[tauri::command]
pub async fn sqlite_get_engineering_decisions(
    services: State<'_, RuntimeServices>,
) -> Result<Vec<Value>, AppError> {
    let decisions = services
        .db
        .get_engineering_decisions()
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
    Ok(engineering_decisions_to_json(&decisions))
}

#[tauri::command]
pub async fn sqlite_delete_engineering_decision(
    services: State<'_, RuntimeServices>,
    decision: String,
) -> Result<Vec<Value>, AppError> {
    services
        .db
        .delete_engineering_decision(decision)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))?;
    let decisions = services
        .db
        .get_engineering_decisions()
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
    Ok(engineering_decisions_to_json(&decisions))
}
