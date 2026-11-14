use serde_json::{json, Value};
use tauri::State;

use crate::commands::media::RuntimeServices;
use crate::error::AppError;
use crate::storage::sqlite::{
    ArchitectureMemoryRecord, CompoundingRuleRecord, EngineeringDecisionRecord, EventLogRecord,
    MessageRecord, ProjectRecord, SessionRecord, StrategicGoalRecord,
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
pub async fn sqlite_get_session(
    services: State<'_, RuntimeServices>,
    session_id: i64,
) -> Result<Option<SessionRecord>, AppError> {
    services
        .db
        .get_session(session_id)
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_update_session_status(
    services: State<'_, RuntimeServices>,
    session_id: i64,
    status: String,
) -> Result<bool, AppError> {
    services
        .db
        .update_session_status(session_id, status)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_save_project(
    services: State<'_, RuntimeServices>,
    session_id: i64,
    name: String,
    description: Option<String>,
    html_content: Option<String>,
    css_content: Option<String>,
    js_content: Option<String>,
) -> Result<ProjectRecord, AppError> {
    services
        .db
        .save_project(session_id, name, description, html_content, css_content, js_content)
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
pub async fn sqlite_add_compounding_rule(
    services: State<'_, RuntimeServices>,
    rule_key: String,
    description: String,
    correction: String,
) -> Result<Vec<Value>, AppError> {
    services
        .db
        .add_compounding_rule(rule_key, description, correction)
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
pub async fn sqlite_add_architecture_memory(
    services: State<'_, RuntimeServices>,
    module: String,
    purpose: String,
    dependencies: String,
    constraints: String,
) -> Result<Vec<Value>, AppError> {
    services
        .db
        .add_architecture_memory(module, purpose, dependencies, constraints)
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
pub async fn sqlite_add_engineering_decision(
    services: State<'_, RuntimeServices>,
    decision: String,
    reason: String,
    impact: String,
) -> Result<Vec<Value>, AppError> {
    services
        .db
        .add_engineering_decision(decision, reason, impact)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))?;
    let decisions = services
        .db
        .get_engineering_decisions()
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
    Ok(engineering_decisions_to_json(&decisions))
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

#[tauri::command]
pub async fn sqlite_list_strategic_goals(
    services: State<'_, RuntimeServices>,
) -> Result<Vec<StrategicGoalRecord>, AppError> {
    services
        .db
        .list_strategic_goals()
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_add_strategic_goal(
    services: State<'_, RuntimeServices>,
    goal: String,
    criteria: Option<String>,
    status: Option<String>,
) -> Result<StrategicGoalRecord, AppError> {
    services
        .db
        .add_strategic_goal(goal, criteria, status)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_list_event_logs(
    services: State<'_, RuntimeServices>,
    limit: Option<i64>,
) -> Result<Vec<EventLogRecord>, AppError> {
    services
        .db
        .list_event_logs(limit.unwrap_or(100))
        .await
        .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))
}

#[tauri::command]
pub async fn sqlite_append_event_log(
    services: State<'_, RuntimeServices>,
    event_type: String,
    details: Option<String>,
) -> Result<EventLogRecord, AppError> {
    services
        .db
        .append_event_log(event_type, details)
        .await
        .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))
}
