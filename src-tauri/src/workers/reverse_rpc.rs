//! Composite Reverse-RPC router bridging Python worker requests to Rust owners.
//!
//! Enforces strict domain ownership over bidirectional worker stdio RPC:
//! - `permission.*` -> [`PermissionGateway`] HITL policy/approval gate.
//! - `sqlite.*` -> [`SqliteDatabase`] exclusive single-writer actor for `database.db`.

use std::sync::Arc;

use serde_json::{json, Value};

use crate::commands::storage::{
    architecture_memory_to_json, compounding_rules_to_json, engineering_decisions_to_json,
};
use crate::permissions::gateway::PermissionGateway;
use crate::storage::sqlite::SqliteDatabase;
use crate::workers::rpc_client::{ReverseRequest, ReverseRpcHandler, RpcRemoteError};

fn invalid_params(message: impl Into<String>) -> RpcRemoteError {
    RpcRemoteError {
        code: -32602,
        message: message.into(),
        data: None,
    }
}

fn sqlite_failed(message: impl Into<String>) -> RpcRemoteError {
    RpcRemoteError {
        code: -32010,
        message: message.into(),
        data: None,
    }
}

fn req_str(params: &Value, field: &str) -> Result<String, RpcRemoteError> {
    params
        .get(field)
        .and_then(Value::as_str)
        .map(ToOwned::to_owned)
        .ok_or_else(|| invalid_params(format!("Missing or invalid string parameter '{field}'")))
}

fn opt_str(params: &Value, field: &str) -> Option<String> {
    params
        .get(field)
        .and_then(|v| if v.is_null() { None } else { v.as_str() })
        .map(ToOwned::to_owned)
}

fn req_i64(params: &Value, field: &str) -> Result<i64, RpcRemoteError> {
    params
        .get(field)
        .and_then(Value::as_i64)
        .ok_or_else(|| invalid_params(format!("Missing or invalid integer parameter '{field}'")))
}

fn opt_i64(params: &Value, field: &str) -> Option<i64> {
    params
        .get(field)
        .and_then(|v| if v.is_null() { None } else { v.as_i64() })
}

fn opt_f64(params: &Value, field: &str) -> Option<f64> {
    params
        .get(field)
        .and_then(|v| if v.is_null() { None } else { v.as_f64() })
}

fn to_json<T: serde::Serialize>(val: T) -> Result<Value, RpcRemoteError> {
    serde_json::to_value(val).map_err(|e| RpcRemoteError {
        code: -32603,
        message: format!("Failed to serialize Reverse-RPC response: {e}"),
        data: None,
    })
}

/// Dispatches one inbound worker `reverse_request` to the appropriate Rust owner.
pub async fn handle_composite_reverse_request(
    db: &SqliteDatabase,
    permissions: &PermissionGateway,
    req: ReverseRequest,
) -> Result<Value, RpcRemoteError> {
    if req.method.starts_with("permission.") {
        return permissions.handle_reverse_request(req).await;
    }

    let p = &req.params;
    match req.method.as_str() {
        "sqlite.init_db" | "sqlite.rho_ensure_schema" => {
            db.rho_ensure_schema().await.map_err(sqlite_failed)?;
            Ok(json!({ "ok": true }))
        }
        "sqlite.create_session" => {
            let name = req_str(p, "name")?;
            let rec = db.create_session(name).await.map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.get_session" => {
            let session_id = req_i64(p, "session_id")?;
            let rec = db.get_session(session_id).await.map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.list_sessions" => {
            let limit = opt_i64(p, "limit").unwrap_or(50);
            let list = db.list_sessions(limit).await.map_err(sqlite_failed)?;
            to_json(list)
        }
        "sqlite.update_session_status" => {
            let session_id = req_i64(p, "session_id")?;
            let status = req_str(p, "status")?;
            let updated = db
                .update_session_status(session_id, status)
                .await
                .map_err(sqlite_failed)?;
            Ok(json!({ "updated": updated }))
        }
        "sqlite.add_message" => {
            let session_id = req_i64(p, "session_id")?;
            let sender = req_str(p, "sender")?;
            let role = req_str(p, "role")?;
            let content = req_str(p, "content")?;
            let rec = db
                .add_message(session_id, &sender, role, content)
                .await
                .map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.list_messages" => {
            let session_id = req_i64(p, "session_id")?;
            let limit = opt_i64(p, "limit").unwrap_or(200);
            let list = db
                .list_messages(session_id, limit)
                .await
                .map_err(sqlite_failed)?;
            to_json(list)
        }
        "sqlite.save_project" => {
            let session_id = req_i64(p, "session_id")?;
            let name = req_str(p, "name")?;
            let description = opt_str(p, "description");
            let html = opt_str(p, "html_content").or_else(|| opt_str(p, "html"));
            let css = opt_str(p, "css_content").or_else(|| opt_str(p, "css"));
            let js = opt_str(p, "js_content").or_else(|| opt_str(p, "js"));
            let rec = db
                .save_project(session_id, name, description, html, css, js)
                .await
                .map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.list_projects" => {
            let limit = opt_i64(p, "limit").unwrap_or(100);
            let list = db.list_projects(limit).await.map_err(sqlite_failed)?;
            to_json(list)
        }
        "sqlite.get_project_by_session" => {
            let session_id = req_i64(p, "session_id")?;
            let rec = db
                .get_project_by_session(session_id)
                .await
                .map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.add_compounding_rule" => {
            let rule_key = req_str(p, "rule_key")?;
            let description = opt_str(p, "description").unwrap_or_default();
            let correction = opt_str(p, "correction").unwrap_or_default();
            db.add_compounding_rule(rule_key, description, correction)
                .await
                .map_err(sqlite_failed)?;
            Ok(json!({ "ok": true }))
        }
        "sqlite.get_compounding_rules" => {
            let rules = db.get_compounding_rules().await.map_err(sqlite_failed)?;
            Ok(Value::Array(compounding_rules_to_json(&rules)))
        }
        "sqlite.delete_compounding_rule" => {
            let rule_key = req_str(p, "rule_key")?;
            let deleted = db
                .delete_compounding_rule(rule_key)
                .await
                .map_err(sqlite_failed)?;
            Ok(json!({ "deleted": deleted }))
        }
        "sqlite.add_architecture_memory" => {
            let module = req_str(p, "module")?;
            let purpose = opt_str(p, "purpose").unwrap_or_default();
            let dependencies = opt_str(p, "dependencies").unwrap_or_default();
            let constraints = opt_str(p, "constraints").unwrap_or_default();
            let rec = db
                .add_architecture_memory(module, purpose, dependencies, constraints)
                .await
                .map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.get_architecture_memory" => {
            let records = db.get_architecture_memory().await.map_err(sqlite_failed)?;
            Ok(Value::Array(architecture_memory_to_json(&records)))
        }
        "sqlite.delete_architecture_memory" => {
            let module = req_str(p, "module")?;
            let deleted = db
                .delete_architecture_memory(module)
                .await
                .map_err(sqlite_failed)?;
            Ok(json!({ "deleted": deleted }))
        }
        "sqlite.add_engineering_decision" => {
            let decision = req_str(p, "decision")?;
            let reason = opt_str(p, "reason").unwrap_or_default();
            let impact = opt_str(p, "impact").unwrap_or_default();
            let rec = db
                .add_engineering_decision(decision, reason, impact)
                .await
                .map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.get_engineering_decisions" => {
            let records = db
                .get_engineering_decisions()
                .await
                .map_err(sqlite_failed)?;
            Ok(Value::Array(engineering_decisions_to_json(&records)))
        }
        "sqlite.delete_engineering_decision" => {
            let decision = req_str(p, "decision")?;
            let deleted = db
                .delete_engineering_decision(decision)
                .await
                .map_err(sqlite_failed)?;
            Ok(json!({ "deleted": deleted }))
        }
        "sqlite.add_strategic_goal" => {
            let goal = req_str(p, "goal")?;
            let criteria = opt_str(p, "criteria");
            let status = opt_str(p, "status");
            let rec = db
                .add_strategic_goal(goal, criteria, status)
                .await
                .map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.list_strategic_goals" => {
            let list = db.list_strategic_goals().await.map_err(sqlite_failed)?;
            to_json(list)
        }
        "sqlite.append_event_log" => {
            let event_type = req_str(p, "event_type")?;
            let details = opt_str(p, "details");
            let rec = db
                .append_event_log(event_type, details)
                .await
                .map_err(sqlite_failed)?;
            to_json(rec)
        }
        "sqlite.list_event_logs" => {
            let limit = opt_i64(p, "limit").unwrap_or(100);
            let list = db.list_event_logs(limit).await.map_err(sqlite_failed)?;
            to_json(list)
        }
        "sqlite.rho_record_trajectory" => {
            let request_id = req_str(p, "request_id")?;
            let task_profile = req_str(p, "task_profile")?;
            let fingerprint = req_str(p, "fingerprint")?;
            let status = req_str(p, "status")?;
            let attempts_count = req_i64(p, "attempts_count")?;
            let failure_reason = opt_str(p, "failure_reason").unwrap_or_default();
            let created_at = opt_f64(p, "created_at");
            let outcome = db
                .rho_record_trajectory(
                    request_id,
                    task_profile,
                    fingerprint,
                    status,
                    attempts_count,
                    failure_reason,
                    created_at,
                )
                .await
                .map_err(sqlite_failed)?;
            to_json(outcome)
        }
        "sqlite.rho_get_compounding_rules" => {
            let task_profile = req_str(p, "task_profile")?;
            let limit = opt_i64(p, "limit").unwrap_or(5);
            let rules = db
                .rho_get_compounding_rules(task_profile, limit)
                .await
                .map_err(sqlite_failed)?;
            to_json(rules)
        }
        "sqlite.runtime_db_metrics" => {
            let metrics = db.runtime_db_metrics().await.map_err(sqlite_failed)?;
            to_json(metrics)
        }
        _ => Err(RpcRemoteError {
            code: -32601,
            message: format!("Unsupported reverse RPC method: {}", req.method),
            data: None,
        }),
    }
}

/// Builds the single composite Reverse-RPC callback shared by all supervised workers.
pub fn build_composite_reverse_rpc_handler(
    db: Arc<SqliteDatabase>,
    permissions: Arc<PermissionGateway>,
) -> ReverseRpcHandler {
    Arc::new(move |req| {
        let db = Arc::clone(&db);
        let permissions = Arc::clone(&permissions);
        Box::pin(async move { handle_composite_reverse_request(&db, &permissions, req).await })
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    use tempfile::tempdir;

    fn make_req(method: &str, params: Value) -> ReverseRequest {
        ReverseRequest {
            id: "rev-test-1".to_string(),
            method: method.to_string(),
            params,
        }
    }

    #[tokio::test]
    async fn composite_reverse_rpc_routes_sqlite_and_permissions_exclusively() {
        let dir = tempdir().expect("tempdir");
        let db = Arc::new(SqliteDatabase::open(dir.path().join("composite.db")).expect("db open"));
        let permissions = Arc::new(PermissionGateway::new(Duration::from_secs(30)));
        let handler = build_composite_reverse_rpc_handler(Arc::clone(&db), permissions);

        // 1. Unknown method fails closed with -32601.
        let unknown = handler(make_req("fs.read_secret", json!({}))).await;
        assert_eq!(unknown.unwrap_err().code, -32601);

        // 2. Missing required parameter returns -32602.
        let bad_params = handler(make_req("sqlite.create_session", json!({}))).await;
        assert_eq!(bad_params.unwrap_err().code, -32602);

        // 3. Permission READ level auto-approves through PermissionGateway.
        let perm = handler(make_req(
            "permission.request_approval",
            json!({
                "action": "fs.read",
                "resource": "README.md",
                "security_level": "READ",
            }),
        ))
        .await
        .expect("permission read approval");
        assert_eq!(perm["decision"], "approved");

        // 4. Full SQLite + RHO flow executes exclusively inside Rust SqliteDatabase.
        let session = handler(make_req("sqlite.create_session", json!({ "name": "RPC Session" })))
            .await
            .expect("create session");
        let sid = session["id"].as_i64().unwrap();

        let msg = handler(make_req(
            "sqlite.add_message",
            json!({ "session_id": sid, "sender": "AI", "role": "assistant", "content": "Hello" }),
        ))
        .await
        .expect("add message");
        assert_eq!(msg["sender"], "JARVIS");

        handler(make_req(
            "sqlite.save_project",
            json!({ "session_id": sid, "name": "App", "html_content": "<p>ok</p>" }),
        ))
        .await
        .expect("save project");

        handler(make_req(
            "sqlite.add_compounding_rule",
            json!({ "rule_key": "R1", "description": "d", "correction": "Always validate" }),
        ))
        .await
        .expect("add compounding rule");
        let rules = handler(make_req("sqlite.get_compounding_rules", json!({})))
            .await
            .expect("get rules");
        assert_eq!(rules.as_array().unwrap().len(), 1);

        handler(make_req(
            "sqlite.add_engineering_decision",
            json!({ "decision": "Single writer", "reason": "Safety", "impact": "High" }),
        ))
        .await
        .expect("add engineering decision");

        handler(make_req(
            "sqlite.rho_record_trajectory",
            json!({
                "request_id": "t1",
                "task_profile": "coder",
                "fingerprint": "fp1",
                "status": "VALIDATION_FAILED",
                "attempts_count": 1,
                "failure_reason": "SCHEMA:bad",
                "created_at": 1000.0
            }),
        ))
        .await
        .expect("rho 1");
        let rho2 = handler(make_req(
            "sqlite.rho_record_trajectory",
            json!({
                "request_id": "t2",
                "task_profile": "coder",
                "fingerprint": "fp2",
                "status": "VALIDATION_FAILED",
                "attempts_count": 1,
                "failure_reason": "SCHEMA:bad",
                "created_at": 1020.0
            }),
        ))
        .await
        .expect("rho 2");
        assert!(rho2["synthesized_rule"]
            .as_str()
            .unwrap()
            .contains("AUTO-RULE [RHO-coder]"));

        let rho_rules = handler(make_req(
            "sqlite.rho_get_compounding_rules",
            json!({ "task_profile": "coder", "limit": 5 }),
        ))
        .await
        .expect("rho rules");
        assert_eq!(rho_rules.as_array().unwrap().len(), 1);

        let metrics = handler(make_req("sqlite.runtime_db_metrics", json!({})))
            .await
            .expect("metrics");
        assert_eq!(metrics["sqlite_online"], true);
        assert_eq!(metrics["total_sessions"], 1);
    }
}
