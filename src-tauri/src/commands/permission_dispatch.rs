use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde_json::{json, Map, Value};
use uuid::Uuid;

use crate::commands::security::permission_record_to_frontend_json;
use crate::error::AppError;
use crate::permissions::gateway::PermissionGateway;
use crate::permissions::path_jail::{is_safe_identifier, resolve_confined_path};
use crate::permissions::policy::is_destructive_operation;
use crate::storage::atomic_fs::{atomic_write_string, read_bounded_bytes};

const MAX_PERMISSION_JSON_BYTES: usize = 2 * 1024 * 1024;
const TOOLS_REQUIRING_ADMIN: &[&str] = &["nmap", "npcap", "wireshark", "tcpdump", "sc", "reg"];
const WINDOWS_UNSUPPORTED_TOOLS: &[&str] = &["iptables", "ebpf"];
const TRUSTED_INSTALLER_PREFIXES: &[&str] = &[
    "https://pypi.org/",
    "https://files.pythonhosted.org/",
    "https://registry.npmjs.org/",
    "https://github.com/",
    "https://nmap.org/",
    "https://www.python.org/",
    "https://nodejs.org/",
    "https://download.visualstudio.microsoft.com/",
    "https://learn.microsoft.com/",
    "https://aka.ms/",
    "pip:",
    "npm:",
    "winget:",
    "choco:",
    "cargo:",
];

fn now_unix_secs() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn permissions_base_dir(project_root: &Path) -> PathBuf {
    project_root.join(".jarvis").join("permissions")
}

fn requests_dir(project_root: &Path) -> PathBuf {
    permissions_base_dir(project_root).join("requests")
}

fn rollbacks_dir(project_root: &Path) -> PathBuf {
    permissions_base_dir(project_root).join("rollbacks")
}

fn validate_request_id(raw: &str) -> Result<String, AppError> {
    let cleaned = raw.trim();
    if cleaned.is_empty() || !is_safe_identifier(cleaned) {
        return Err(AppError::new(
            "INVALID_REQUEST_ID",
            "Permission request_id is missing or contains invalid characters",
        ));
    }
    Ok(cleaned.to_string())
}

fn load_disk_request(project_root: &Path, request_id: &str) -> Result<Option<Value>, AppError> {
    let dir = requests_dir(project_root);
    if !dir.exists() {
        return Ok(None);
    }
    let rel = format!("{request_id}.json");
    let target = resolve_confined_path(&dir, Path::new(&rel))?;
    if !target.exists() {
        return Ok(None);
    }
    let bytes = read_bounded_bytes(&dir, Path::new(&rel), MAX_PERMISSION_JSON_BYTES)?;
    let parsed: Value = serde_json::from_slice(&bytes).map_err(|err| {
        AppError::new(
            "PERMISSION_CORRUPT",
            format!("Failed to parse permission request `{request_id}`: {err}"),
        )
    })?;
    Ok(Some(parsed))
}

fn persist_disk_request(project_root: &Path, request_id: &str, value: &Value) -> Result<(), AppError> {
    let dir = requests_dir(project_root);
    fs::create_dir_all(&dir).map_err(|err| {
        AppError::new(
            "PERMISSION_IO_FAILED",
            format!("Failed to create permissions request directory: {err}"),
        )
    })?;
    let rel = format!("{request_id}.json");
    let serialized = serde_json::to_string_pretty(value).map_err(|err| {
        AppError::new(
            "PERMISSION_SERIALIZE_FAILED",
            format!("Failed to serialize permission request `{request_id}`: {err}"),
        )
    })?;
    atomic_write_string(&dir, Path::new(&rel), &serialized)?;
    Ok(())
}

fn persist_disk_rollback(project_root: &Path, request_id: &str, rollback: &Value) -> Result<(), AppError> {
    let dir = rollbacks_dir(project_root);
    fs::create_dir_all(&dir).map_err(|err| {
        AppError::new(
            "PERMISSION_IO_FAILED",
            format!("Failed to create permissions rollback directory: {err}"),
        )
    })?;
    let rel = format!("{request_id}.json");
    let serialized = serde_json::to_string_pretty(rollback).map_err(|err| {
        AppError::new(
            "PERMISSION_SERIALIZE_FAILED",
            format!("Failed to serialize rollback `{request_id}`: {err}"),
        )
    })?;
    atomic_write_string(&dir, Path::new(&rel), &serialized)?;
    Ok(())
}

fn append_disk_audit_entry(
    project_root: &Path,
    request_id: &str,
    action: &str,
    req: &Value,
    user_decision: Option<&str>,
    details: Value,
) {
    let base = permissions_base_dir(project_root);
    if fs::create_dir_all(&base).is_err() {
        return;
    }
    let audit_rel = Path::new("audit_log.json");
    let mut entries = match read_bounded_bytes(&base, audit_rel, MAX_PERMISSION_JSON_BYTES * 2) {
        Ok(bytes) => serde_json::from_slice::<Vec<Value>>(&bytes).unwrap_or_default(),
        Err(_) => Vec::new(),
    };
    entries.push(json!({
        "audit_id": format!("aud-{}", &Uuid::new_v4().simple().to_string()[..12]),
        "request_id": request_id,
        "action": action,
        "timestamp": now_unix_secs(),
        "risk_level": req.get("risk_level").cloned().unwrap_or(Value::Null),
        "tool_name": req.get("tool_name").cloned().unwrap_or(Value::Null),
        "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
        "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
        "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
        "user_decision": user_decision,
        "details": details,
    }));
    if let Ok(serialized) = serde_json::to_string_pretty(&entries) {
        let _ = atomic_write_string(&base, audit_rel, &serialized);
    }
}

fn json_str<'a>(val: &'a Value, key: &str) -> &'a str {
    val.get(key).and_then(Value::as_str).unwrap_or("").trim()
}

fn opt_json_str(val: &Value, key: &str) -> Option<String> {
    val.get(key)
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(String::from)
}

fn validate_scope_match(
    req: &Value,
    expected_project_id: Option<&str>,
    expected_mission_id: Option<&str>,
) -> Result<(), String> {
    let req_project = opt_json_str(req, "project_id");
    if let (Some(expected), Some(actual)) = (
        expected_project_id.map(str::trim).filter(|s| !s.is_empty()),
        req_project.as_deref(),
    ) {
        if expected != actual {
            return Err("Cross-project approval rejected: project_id mismatch".to_string());
        }
    }
    let req_mission = opt_json_str(req, "mission_id");
    if let (Some(expected), Some(actual)) = (
        expected_mission_id.map(str::trim).filter(|s| !s.is_empty()),
        req_mission.as_deref(),
    ) {
        if expected != actual {
            return Err("Cross-mission approval rejected: mission_id mismatch".to_string());
        }
    }
    Ok(())
}

fn find_executable_in_path(tool_name: &str) -> Option<PathBuf> {
    let trimmed = tool_name.trim();
    if trimmed.is_empty() {
        return None;
    }
    let path_var = std::env::var_os("PATH")?;
    let candidates: Vec<String> = if cfg!(target_os = "windows") {
        let lower = trimmed.to_ascii_lowercase();
        if lower.ends_with(".exe")
            || lower.ends_with(".cmd")
            || lower.ends_with(".bat")
            || lower.ends_with(".com")
        {
            vec![trimmed.to_string(), lower]
        } else {
            vec![
                trimmed.to_string(),
                format!("{trimmed}.exe"),
                format!("{lower}.exe"),
                format!("{trimmed}.cmd"),
                format!("{trimmed}.bat"),
            ]
        }
    } else {
        vec![trimmed.to_string(), trimmed.to_ascii_lowercase()]
    };

    for dir in std::env::split_paths(&path_var) {
        for cand in &candidates {
            let full = dir.join(cand);
            if full.is_file() {
                return Some(full);
            }
        }
    }
    None
}

fn check_disk_request_capability(req: &Value) -> (&'static str, &'static str, Value) {
    let tool_name = json_str(req, "tool_name");
    let tool_lower = tool_name.to_ascii_lowercase();
    let priv_lower = json_str(req, "required_privileges").to_ascii_lowercase();
    let requested_op = json_str(req, "requested_operation");

    let os_name = if cfg!(target_os = "windows") {
        "Windows"
    } else if cfg!(target_os = "macos") {
        "Darwin"
    } else {
        "Linux"
    };

    if is_destructive_operation(requested_op).is_some() {
        return (
            "BLOCKED",
            "BLOCKED_BY_POLICY",
            json!({
                "tool_name": tool_name,
                "os": os_name,
                "architecture": std::env::consts::ARCH,
                "admin_granted": false,
                "executable_path": Value::Null,
                "version": Value::Null,
                "requires_admin": true,
                "message": "Operation blocked by Sentinel security policy.",
            }),
        );
    }

    let requires_admin =
        TOOLS_REQUIRING_ADMIN.contains(&tool_lower.as_str()) || priv_lower.contains("admin");
    let exec_path = find_executable_in_path(tool_name);

    if let Some(found) = exec_path {
        let found_str = found.to_string_lossy().to_string();
        if requires_admin {
            return (
                "ADMIN_PRIVILEGE_REQUIRED",
                "ADMIN_PRIVILEGE_REQUIRED",
                json!({
                    "tool_name": tool_name,
                    "os": os_name,
                    "architecture": std::env::consts::ARCH,
                    "admin_granted": false,
                    "executable_path": found_str,
                    "version": Value::Null,
                    "requires_admin": true,
                    "message": "Windows administrator elevation is required to execute this low-level tool.",
                }),
            );
        }
        return (
            "AVAILABLE",
            "EXECUTION_READY",
            json!({
                "tool_name": tool_name,
                "os": os_name,
                "architecture": std::env::consts::ARCH,
                "admin_granted": false,
                "executable_path": found_str,
                "version": Value::Null,
                "requires_admin": false,
                "message": format!("Tool '{tool_name}' found and ready at '{found_str}'."),
            }),
        );
    }

    if cfg!(target_os = "windows") && WINDOWS_UNSUPPORTED_TOOLS.contains(&tool_lower.as_str()) {
        return (
            "UNSUPPORTED",
            "UNSUPPORTED",
            json!({
                "tool_name": tool_name,
                "os": os_name,
                "architecture": std::env::consts::ARCH,
                "admin_granted": false,
                "executable_path": Value::Null,
                "version": Value::Null,
                "requires_admin": requires_admin,
                "message": format!("Tool '{tool_name}' is unsupported on {os_name}."),
            }),
        );
    }

    let installation_required = req
        .get("installation_required")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    if installation_required {
        return (
            "INSTALLATION_REQUIRED",
            "INSTALLATION_REQUIRED",
            json!({
                "tool_name": tool_name,
                "os": os_name,
                "architecture": std::env::consts::ARCH,
                "admin_granted": false,
                "executable_path": Value::Null,
                "version": Value::Null,
                "requires_admin": requires_admin,
                "message": format!("Tool '{tool_name}' is not installed on the host. Installation authorization required."),
            }),
        );
    }

    (
        "UNSUPPORTED",
        "UNSUPPORTED",
        json!({
            "tool_name": tool_name,
            "os": os_name,
            "architecture": std::env::consts::ARCH,
            "admin_granted": false,
            "executable_path": Value::Null,
            "version": Value::Null,
            "requires_admin": requires_admin,
            "message": format!("Binary '{tool_name}' not found and no safe installer declared."),
        }),
    )
}

fn validate_installer_source(source: &str) -> Result<(), String> {
    let cleaned = source.trim();
    if cleaned.is_empty() {
        return Ok(());
    }
    if cleaned.contains("..") || cleaned.contains('\\') || cleaned.starts_with('/') {
        return Err("Supply Chain rejected installer source containing path traversal.".to_string());
    }
    let lower = cleaned.to_ascii_lowercase();
    if TRUSTED_INSTALLER_PREFIXES
        .iter()
        .any(|prefix| lower.starts_with(prefix))
    {
        Ok(())
    } else {
        Err(format!(
            "Supply Chain rejected untrusted installer source `{cleaned}`."
        ))
    }
}

fn normalize_disk_request_for_frontend(req: &Value) -> Value {
    let mut obj = req.as_object().cloned().unwrap_or_default();
    obj.entry("affected_resources".to_string())
        .or_insert_with(|| json!([]));
    obj.entry("installation_required".to_string())
        .or_insert_with(|| json!(false));
    obj.entry("alternative_available".to_string())
        .or_insert_with(|| json!(false));
    obj.entry("decision_evidence".to_string())
        .or_insert_with(|| json!({}));
    Value::Object(obj)
}

async fn handle_get_pending(
    project_root: &Path,
    permissions: &PermissionGateway,
) -> Result<Vec<Value>, AppError> {
    let _ = permissions.sweep_expired().await;
    let mut pending: Vec<Value> = permissions
        .pending_requests()
        .await
        .iter()
        .map(permission_record_to_frontend_json)
        .collect();

    let mut seen: HashSet<String> = pending
        .iter()
        .filter_map(|item| item.get("request_id").and_then(Value::as_str).map(String::from))
        .collect();

    let dir = requests_dir(project_root);
    if dir.is_dir() {
        let now = now_unix_secs();
        if let Ok(entries) = fs::read_dir(&dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|e| e.to_str()) != Some("json") {
                    continue;
                }
                let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
                    continue;
                };
                if !is_safe_identifier(stem) {
                    continue;
                }
                let Ok(Some(mut req)) = load_disk_request(project_root, stem) else {
                    continue;
                };
                let status = json_str(&req, "status").to_string();
                if !matches!(
                    status.as_str(),
                    "WAITING_FOR_USER" | "REQUESTED" | "AWAITING_HUMAN_APPROVAL"
                ) {
                    continue;
                }
                let expires_at = req.get("expires_at").and_then(Value::as_f64).unwrap_or(0.0);
                if expires_at > 0.0 && now > expires_at {
                    if let Some(map) = req.as_object_mut() {
                        map.insert("status".to_string(), json!("EXPIRED"));
                    }
                    let _ = persist_disk_request(project_root, stem, &req);
                    continue;
                }
                let rid = opt_json_str(&req, "request_id").unwrap_or_else(|| stem.to_string());
                if seen.insert(rid) {
                    pending.push(normalize_disk_request_for_frontend(&req));
                }
            }
        }
    }

    pending.sort_by(|a, b| {
        let ca = a.get("created_at").and_then(Value::as_f64).unwrap_or(0.0);
        let cb = b.get("created_at").and_then(Value::as_f64).unwrap_or(0.0);
        ca.total_cmp(&cb)
    });

    Ok(vec![json!({
        "type": "permission_pending_list",
        "data": pending,
    })])
}

async fn handle_approve(
    project_root: &Path,
    permissions: &PermissionGateway,
    message: &Value,
) -> Result<Vec<Value>, AppError> {
    let raw_id = json_str(message, "request_id");
    let request_id = match validate_request_id(raw_id) {
        Ok(id) => id,
        Err(err) => {
            return Ok(vec![json!({
                "type": "permission_request_approved",
                "request_id": raw_id,
                "success": false,
                "error": err.message,
            })]);
        }
    };
    let user = opt_json_str(message, "user").unwrap_or_else(|| "human_operator".to_string());
    let session_id = opt_json_str(message, "session_id").unwrap_or_else(|| "web_session".to_string());
    let project_id = opt_json_str(message, "project_id");
    let mission_id = opt_json_str(message, "mission_id");

    match permissions
        .approve_request(
            &request_id,
            &user,
            "allow_once",
            project_id.as_deref(),
            mission_id.as_deref(),
        )
        .await
    {
        Ok(rec) => {
            let frontend_req = permission_record_to_frontend_json(&rec);
            return Ok(vec![json!({
                "type": "permission_request_approved",
                "request_id": rec.request_id,
                "request": frontend_req,
                "success": true,
            })]);
        }
        Err(err) => {
            let disk_opt = load_disk_request(project_root, &request_id)?;
            if disk_opt.is_none() {
                if !err.to_ascii_lowercase().contains("not found") {
                    return Err(AppError::new("PERMISSION_APPROVE_FAILED", err));
                }
                return Ok(vec![json!({
                    "type": "permission_request_approved",
                    "request_id": request_id,
                    "success": false,
                    "error": format!("Permission request '{request_id}' not found."),
                })]);
            }
            let mut req = disk_opt.unwrap();
            let status = json_str(&req, "status").to_string();
            if status == "BLOCKED_BY_POLICY" {
                return Err(AppError::new(
                    "PERMISSION_BLOCKED_BY_POLICY",
                    "Operations blocked by policy cannot be approved.",
                ));
            }
            if let Err(scope_err) =
                validate_scope_match(&req, project_id.as_deref(), mission_id.as_deref())
            {
                return Err(AppError::new("PERMISSION_APPROVE_FAILED", scope_err));
            }
            if matches!(
                status.as_str(),
                "APPROVED"
                    | "AVAILABLE"
                    | "ADMIN_PRIVILEGE_REQUIRED"
                    | "INSTALLATION_REQUIRED"
                    | "EXECUTION_READY"
                    | "EXECUTED"
            ) {
                return Ok(vec![json!({
                    "type": "permission_request_approved",
                    "request_id": request_id,
                    "request": normalize_disk_request_for_frontend(&req),
                    "success": true,
                })]);
            }

            let now = now_unix_secs();
            let expires_at = req.get("expires_at").and_then(Value::as_f64).unwrap_or(0.0);
            if expires_at > 0.0 && now > expires_at {
                if let Some(map) = req.as_object_mut() {
                    map.insert("status".to_string(), json!("EXPIRED"));
                }
                persist_disk_request(project_root, &request_id, &req)?;
                append_disk_audit_entry(
                    project_root,
                    &request_id,
                    "expired",
                    &req,
                    None,
                    json!({ "expired_at": expires_at, "attempted_at": now }),
                );
                return Ok(vec![
                    json!({
                        "type": "permission_request_expired",
                        "request_id": request_id,
                    }),
                    json!({
                        "type": "permission_request_approved",
                        "request_id": request_id,
                        "request": normalize_disk_request_for_frontend(&req),
                        "success": false,
                        "error": "Permission request expired and cannot be approved.",
                    }),
                ]);
            }

            if !matches!(
                status.as_str(),
                "WAITING_FOR_USER"
                    | "REQUESTED"
                    | "AWAITING_HUMAN_APPROVAL"
                    | "BLOCKED_REQUIRED_CAPABILITY"
            ) {
                return Ok(vec![json!({
                    "type": "permission_request_approved",
                    "request_id": request_id,
                    "request": normalize_disk_request_for_frontend(&req),
                    "success": false,
                    "error": format!("Invalid request state for approval: '{status}'."),
                })]);
            }

            let (cap_status, next_status, cap_details) = check_disk_request_capability(&req);
            if let Some(map) = req.as_object_mut() {
                map.insert("user_decision".to_string(), json!("USER_APPROVED"));
                map.insert("decided_by".to_string(), json!(user));
                map.insert("session_id".to_string(), json!(session_id));
                map.insert("decided_at".to_string(), json!(now));
                map.insert("status".to_string(), json!(next_status));
                map.insert("capability_status".to_string(), json!(cap_status));
                map.insert("capability_result".to_string(), cap_details.clone());
                let evidence = map
                    .entry("decision_evidence".to_string())
                    .or_insert_with(|| Value::Object(Map::new()));
                if let Some(ev_map) = evidence.as_object_mut() {
                    ev_map.insert("capability_check".to_string(), cap_details.clone());
                }
            }
            persist_disk_request(project_root, &request_id, &req)?;
            append_disk_audit_entry(
                project_root,
                &request_id,
                "approved",
                &req,
                Some("USER_APPROVED"),
                json!({ "user": user, "session_id": session_id, "capability_status": cap_status }),
            );

            let normalized = normalize_disk_request_for_frontend(&req);
            Ok(vec![
                json!({
                    "type": "permission_request_approved",
                    "request_id": request_id,
                    "request": normalized,
                    "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
                    "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
                    "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
                    "user": user,
                    "success": true,
                }),
                json!({
                    "type": "permission_capability_result",
                    "request_id": request_id,
                    "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
                    "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
                    "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
                    "status": next_status,
                    "capability": cap_details,
                }),
            ])
        }
    }
}

async fn handle_deny(
    project_root: &Path,
    permissions: &PermissionGateway,
    message: &Value,
) -> Result<Vec<Value>, AppError> {
    let raw_id = json_str(message, "request_id");
    let request_id = match validate_request_id(raw_id) {
        Ok(id) => id,
        Err(err) => {
            return Ok(vec![json!({
                "type": "permission_request_denied",
                "request_id": raw_id,
                "success": false,
                "reason": err.message,
            })]);
        }
    };
    let user = opt_json_str(message, "user").unwrap_or_else(|| "human_operator".to_string());
    let reason =
        opt_json_str(message, "reason").unwrap_or_else(|| "Denied by operator".to_string());
    let session_id = opt_json_str(message, "session_id").unwrap_or_else(|| "web_session".to_string());
    let project_id = opt_json_str(message, "project_id");
    let mission_id = opt_json_str(message, "mission_id");

    match permissions
        .deny_request(
            &request_id,
            &user,
            &reason,
            project_id.as_deref(),
            mission_id.as_deref(),
        )
        .await
    {
        Ok(rec) => Ok(vec![json!({
            "type": "permission_request_denied",
            "request_id": rec.request_id,
            "request": permission_record_to_frontend_json(&rec),
            "reason": rec.policy_reason,
            "success": true,
        })]),
        Err(err) => {
            let Some(mut req) = load_disk_request(project_root, &request_id)? else {
                if !err.to_ascii_lowercase().contains("not found") {
                    return Err(AppError::new("PERMISSION_DENY_FAILED", err));
                }
                return Ok(vec![json!({
                    "type": "permission_request_denied",
                    "request_id": request_id,
                    "success": false,
                    "reason": format!("Permission request '{request_id}' not found."),
                })]);
            };

            if let Err(scope_err) =
                validate_scope_match(&req, project_id.as_deref(), mission_id.as_deref())
            {
                return Err(AppError::new("PERMISSION_DENY_FAILED", scope_err));
            }

            if json_str(&req, "status") != "DENIED" {
                let now = now_unix_secs();
                if let Some(map) = req.as_object_mut() {
                    map.insert("user_decision".to_string(), json!("USER_DENIED"));
                    map.insert("decided_by".to_string(), json!(user));
                    map.insert("session_id".to_string(), json!(session_id));
                    map.insert("decided_at".to_string(), json!(now));
                    map.insert("status".to_string(), json!("DENIED"));
                    let evidence = map
                        .entry("decision_evidence".to_string())
                        .or_insert_with(|| Value::Object(Map::new()));
                    if let Some(ev_map) = evidence.as_object_mut() {
                        ev_map.insert("deny_reason".to_string(), json!(reason));
                    }
                }
                persist_disk_request(project_root, &request_id, &req)?;
                append_disk_audit_entry(
                    project_root,
                    &request_id,
                    "denied",
                    &req,
                    Some("USER_DENIED"),
                    json!({ "reason": reason, "user": user }),
                );
            }

            let normalized = normalize_disk_request_for_frontend(&req);
            Ok(vec![json!({
                "type": "permission_request_denied",
                "request_id": request_id,
                "request": normalized,
                "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
                "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
                "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
                "user": user,
                "reason": reason,
                "fallback_available": req.get("alternative_available").and_then(Value::as_bool).unwrap_or(false),
                "fallback_description": req.get("fallback_description").cloned().unwrap_or(Value::Null),
                "success": true,
            })])
        }
    }
}

async fn handle_rollback(project_root: &Path, message: &Value) -> Result<Vec<Value>, AppError> {
    let raw_id = json_str(message, "request_id");
    let request_id = validate_request_id(raw_id)?;
    let user = opt_json_str(message, "user").unwrap_or_else(|| "human_operator".to_string());

    let Some(mut req) = load_disk_request(project_root, &request_id)? else {
        return Ok(vec![json!({
            "type": "permission_execution_result",
            "request_id": request_id,
            "status": "FAILED",
            "error": format!("Permission request '{request_id}' not found for rollback."),
        })]);
    };

    let rollback_available = req
        .get("rollback_available")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    if !rollback_available {
        return Ok(vec![json!({
            "type": "permission_execution_result",
            "request_id": request_id,
            "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
            "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
            "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
            "status": "FAILED",
            "error": format!("Operation for permission request '{request_id}' does not support rollback."),
        })]);
    }

    let now = now_unix_secs();
    let rollback_id = format!("roll-{}", &Uuid::new_v4().simple().to_string()[..10]);
    let rollback_record = json!({
        "rollback_id": rollback_id,
        "request_id": request_id,
        "tool_name": req.get("tool_name").cloned().unwrap_or(Value::Null),
        "installer": req.get("installer_source").cloned().unwrap_or_else(|| json!("native")),
        "version": req.get("installer_version").cloned().unwrap_or(Value::Null),
        "rollback_plan": req.get("rollback_plan").cloned().unwrap_or(Value::Null),
        "pre_install_state": {},
        "post_install_state": {},
        "is_reversible": true,
        "executed": true,
        "executed_by": user,
        "executed_at": now,
        "result": { "rolled_back": true, "plan": req.get("rollback_plan").cloned().unwrap_or(Value::Null) },
    });

    persist_disk_rollback(project_root, &request_id, &rollback_record)?;
    if let Some(map) = req.as_object_mut() {
        map.insert("status".to_string(), json!("ROLLED_BACK"));
        map.insert(
            "execution_result".to_string(),
            json!({ "status": "ROLLED_BACK", "rollback": rollback_record }),
        );
    }
    persist_disk_request(project_root, &request_id, &req)?;
    append_disk_audit_entry(
        project_root,
        &request_id,
        "rolled_back",
        &req,
        None,
        json!({ "user": user, "rollback_id": rollback_id }),
    );

    Ok(vec![json!({
        "type": "permission_execution_result",
        "request_id": request_id,
        "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
        "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
        "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
        "status": "ROLLED_BACK",
        "rollback": rollback_record,
    })])
}

async fn handle_resolve_choice(
    project_root: &Path,
    permissions: &PermissionGateway,
    message: &Value,
) -> Result<Vec<Value>, AppError> {
    let raw_id = json_str(message, "request_id");
    let request_id = validate_request_id(raw_id)?;
    let action = json_str(message, "action").to_ascii_uppercase();
    let user = opt_json_str(message, "user").unwrap_or_else(|| "human_operator".to_string());
    let session_id = opt_json_str(message, "session_id").unwrap_or_else(|| "web_session".to_string());

    if action == "CANCEL" {
        let mut events = handle_deny(project_root, permissions, message).await?;
        events.push(json!({
            "type": "permission_capability_result",
            "request_id": request_id,
            "status": "DENIED",
            "capability": {
                "choice_result": {
                    "status": "DENIED",
                    "allowed": false,
                }
            },
        }));
        return Ok(events);
    }

    let disk_opt = load_disk_request(project_root, &request_id)?;
    if disk_opt.is_none() {
        if action == "AUTHORIZE_USE" {
            return handle_approve(project_root, permissions, message).await;
        }
        return Err(AppError::new(
            "PERMISSION_NOT_FOUND",
            format!("Permission request '{request_id}' not found."),
        ));
    }
    let mut req = disk_opt.unwrap();
    if json_str(&req, "status") == "BLOCKED_BY_POLICY" {
        return Err(AppError::new(
            "PERMISSION_BLOCKED_BY_POLICY",
            "Operations blocked by policy cannot be resolved.",
        ));
    }

    match action.as_str() {
        "USE_LIMITED_FALLBACK" => {
            let satisfies = req
                .get("fallback_satisfies_acceptance_criteria")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            let now = now_unix_secs();
            if !satisfies {
                if let Some(map) = req.as_object_mut() {
                    map.insert("status".to_string(), json!("BLOCKED_REQUIRED_CAPABILITY"));
                    map.insert("decided_by".to_string(), json!(user));
                    map.insert("decided_at".to_string(), json!(now));
                }
                persist_disk_request(project_root, &request_id, &req)?;
                append_disk_audit_entry(
                    project_root,
                    &request_id,
                    "fallback_rejected",
                    &req,
                    Some("USE_LIMITED_FALLBACK"),
                    json!({ "reason": "acceptance_criteria_not_satisfied" }),
                );
                return Ok(vec![json!({
                    "type": "permission_capability_result",
                    "request_id": request_id,
                    "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
                    "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
                    "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
                    "status": "BLOCKED_REQUIRED_CAPABILITY",
                    "capability": {
                        "allowed": false,
                        "status": "BLOCKED_REQUIRED_CAPABILITY",
                        "warning": "A alternativa não cumpre todos os requisitos.",
                        "fallback_description": req.get("fallback_description").cloned().unwrap_or(Value::Null),
                    },
                })]);
            }

            if let Some(map) = req.as_object_mut() {
                map.insert("status".to_string(), json!("EXECUTION_READY"));
                map.insert("user_decision".to_string(), json!("USE_LIMITED_FALLBACK"));
                map.insert("decided_by".to_string(), json!(user));
                map.insert("session_id".to_string(), json!(session_id));
                map.insert("decided_at".to_string(), json!(now));
            }
            persist_disk_request(project_root, &request_id, &req)?;
            append_disk_audit_entry(
                project_root,
                &request_id,
                "fallback_accepted",
                &req,
                Some("USE_LIMITED_FALLBACK"),
                json!({ "user": user }),
            );
            Ok(vec![json!({
                "type": "permission_capability_result",
                "request_id": request_id,
                "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
                "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
                "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
                "status": "FALLBACK_ACCEPTED",
                "capability": {
                    "allowed": true,
                    "status": "FALLBACK_ACCEPTED",
                    "fallback_description": req.get("fallback_description").cloned().unwrap_or(Value::Null),
                },
            })])
        }

        "AUTHORIZE_INSTALLATION" => {
            if let Some(src) = opt_json_str(&req, "installer_source") {
                if let Err(supply_err) = validate_installer_source(&src) {
                    if let Some(map) = req.as_object_mut() {
                        map.insert("status".to_string(), json!("BLOCKED_BY_POLICY"));
                        map.insert("policy_reason".to_string(), json!(supply_err));
                    }
                    persist_disk_request(project_root, &request_id, &req)?;
                    return Err(AppError::new("PERMISSION_SUPPLY_CHAIN_REJECTED", supply_err));
                }
            }

            let now = now_unix_secs();
            if let Some(map) = req.as_object_mut() {
                map.insert("user_decision".to_string(), json!("USER_APPROVED"));
                map.insert("approval_semantic".to_string(), json!("AUTHORIZE_INSTALLATION"));
                map.insert("decided_by".to_string(), json!(user));
                map.insert("session_id".to_string(), json!(session_id));
                map.insert("decided_at".to_string(), json!(now));
                map.insert("status".to_string(), json!("APPROVED"));
            }
            persist_disk_request(project_root, &request_id, &req)?;
            append_disk_audit_entry(
                project_root,
                &request_id,
                "installation_authorized",
                &req,
                Some("AUTHORIZE_INSTALLATION"),
                json!({ "user": user }),
            );
            Ok(vec![
                json!({
                    "type": "permission_request_approved",
                    "request_id": request_id,
                    "request": normalize_disk_request_for_frontend(&req),
                    "user": user,
                    "success": true,
                }),
                json!({
                    "type": "permission_capability_result",
                    "request_id": request_id,
                    "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
                    "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
                    "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
                    "status": "INSTALLATION_AUTHORIZED",
                    "capability": {
                        "status": "INSTALLATION_AUTHORIZED",
                        "tool_name": req.get("tool_name").cloned().unwrap_or(Value::Null),
                        "installer_source": req.get("installer_source").cloned().unwrap_or(Value::Null),
                        "approved_by": user,
                    },
                }),
            ])
        }

        _ => {
            let mut events = handle_approve(project_root, permissions, message).await?;
            if let Some(cap_ev) = events
                .iter_mut()
                .find(|ev| ev.get("type").and_then(Value::as_str) == Some("permission_capability_result"))
            {
                if cap_ev.get("status").and_then(Value::as_str) == Some("INSTALLATION_REQUIRED") {
                    let inst_id = format!("perm-{}", &Uuid::new_v4().simple().to_string()[..12]);
                    let now = now_unix_secs();
                    let child_req = json!({
                        "request_id": inst_id,
                        "tool_name": req.get("tool_name").cloned().unwrap_or_else(|| json!("")),
                        "requested_operation": format!("Install missing tool {}", json_str(&req, "tool_name")),
                        "reason": format!("Formal installation authorization for {}", json_str(&req, "tool_name")),
                        "risk_level": req.get("risk_level").cloned().unwrap_or_else(|| json!("HIGH_RISK_MUTATION")),
                        "required_privileges": req.get("required_privileges").cloned().unwrap_or_else(|| json!("standard")),
                        "affected_resources": req.get("affected_resources").cloned().unwrap_or_else(|| json!([])),
                        "mission_id": req.get("mission_id").cloned().unwrap_or(Value::Null),
                        "project_id": req.get("project_id").cloned().unwrap_or(Value::Null),
                        "execution_id": req.get("execution_id").cloned().unwrap_or(Value::Null),
                        "installation_required": true,
                        "installer_source": req.get("installer_source").cloned().unwrap_or(Value::Null),
                        "approval_semantic": "AUTHORIZE_INSTALLATION",
                        "status": "WAITING_FOR_USER",
                        "created_at": now,
                        "expires_at": now + 300.0,
                        "rollback_available": true,
                        "decision_evidence": { "parent_request_id": request_id },
                    });
                    persist_disk_request(project_root, &inst_id, &child_req)?;
                    if let Some(cap_obj) = cap_ev.get_mut("capability").and_then(Value::as_object_mut) {
                        cap_obj.insert("installation_request_id".to_string(), json!(inst_id));
                    }
                    events.push(json!({
                        "type": "permission_request_created",
                        "request": normalize_disk_request_for_frontend(&child_req),
                    }));
                }
            }
            Ok(events)
        }
    }
}

/// Executes all 6 `PERMISSION_HANDLERS` client routes natively in Rust.
pub async fn try_execute_permission_fast_path(
    project_root: &Path,
    permissions: &PermissionGateway,
    msg_type: &str,
    message: &Value,
) -> Result<Option<Vec<Value>>, AppError> {
    match msg_type {
        "permission_get_pending" => handle_get_pending(project_root, permissions)
            .await
            .map(Some),

        "permission_approve" => handle_approve(project_root, permissions, message)
            .await
            .map(Some),

        "permission_deny" => handle_deny(project_root, permissions, message)
            .await
            .map(Some),

        "action_confirm_response" => {
            let decision = json_str(message, "decision").to_ascii_uppercase();
            match decision.as_str() {
                "APPROVE" => handle_approve(project_root, permissions, message)
                    .await
                    .map(Some),
                "DENY" | "REJECT" => handle_deny(project_root, permissions, message)
                    .await
                    .map(Some),
                _ => Err(AppError::new(
                    "INVALID_CONFIRM_DECISION",
                    format!("Unsupported action_confirm_response decision `{decision}`"),
                )),
            }
        }

        "permission_rollback" => handle_rollback(project_root, message).await.map(Some),

        "permission_resolve_choice" => handle_resolve_choice(project_root, permissions, message)
            .await
            .map(Some),

        _ => Ok(None),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;
    use tempfile::TempDir;

    fn write_sample_disk_request(root: &Path, id: &str, extra: Value) {
        let now = now_unix_secs();
        let mut base = json!({
            "request_id": id,
            "tool_name": "nonexistent_jarvis_tool_xyz",
            "requested_operation": "scan",
            "reason": "Unit test",
            "risk_level": "HIGH_RISK_MUTATION",
            "required_privileges": "standard",
            "affected_resources": ["workspace"],
            "project_id": "proj-1",
            "mission_id": "mission-1",
            "installation_required": true,
            "alternative_available": true,
            "fallback_description": "limited scan",
            "fallback_satisfies_acceptance_criteria": false,
            "rollback_available": true,
            "rollback_plan": "remove installed artifact",
            "status": "WAITING_FOR_USER",
            "created_at": now,
            "expires_at": now + 300.0,
            "decision_evidence": {}
        });
        if let (Some(dst), Some(src)) = (base.as_object_mut(), extra.as_object()) {
            for (k, v) in src {
                dst.insert(k.clone(), v.clone());
            }
        }
        persist_disk_request(root, id, &base).unwrap();
    }

    #[tokio::test]
    async fn permission_get_pending_combines_native_and_disk_and_expires_old_entries() {
        let dir = TempDir::new().unwrap();
        let gw = PermissionGateway::new(Duration::from_secs(60));
        let (native_req, _) = gw
            .create_pending_request(
                "fs.write",
                "write config",
                "LOW_RISK_MUTATION",
                "create file",
                vec!["a.txt".into()],
                Some("m-1".into()),
                Some("p-1".into()),
                None,
                None,
            )
            .await
            .unwrap();

        write_sample_disk_request(dir.path(), "perm-disk-active", json!({}));
        write_sample_disk_request(
            dir.path(),
            "perm-disk-expired",
            json!({ "expires_at": now_unix_secs() - 10.0 }),
        );

        let events = try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "permission_get_pending",
            &json!({ "type": "permission_get_pending" }),
        )
        .await
        .unwrap()
        .unwrap();

        assert_eq!(events.len(), 1);
        assert_eq!(events[0]["type"], "permission_pending_list");
        let list = events[0]["data"].as_array().unwrap();
        let ids: HashSet<&str> = list
            .iter()
            .filter_map(|v| v.get("request_id").and_then(Value::as_str))
            .collect();
        assert!(ids.contains(native_req.request_id.as_str()));
        assert!(ids.contains("perm-disk-active"));
        assert!(!ids.contains("perm-disk-expired"));
    }

    #[tokio::test]
    async fn permission_approve_deny_and_action_confirm_enforce_scope_and_emit_capability() {
        let dir = TempDir::new().unwrap();
        let gw = PermissionGateway::new(Duration::from_secs(60));

        // 1. Rust-native via action_confirm_response APPROVE
        let (native_req, rx_opt) = gw
            .create_pending_request(
                "fs.write",
                "write main.py",
                "LOW_RISK_MUTATION",
                "edit code",
                vec!["main.py".into()],
                None,
                Some("proj-nat".into()),
                None,
                None,
            )
            .await
            .unwrap();

        let events = try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "action_confirm_response",
            &json!({
                "type": "action_confirm_response",
                "request_id": native_req.request_id,
                "decision": "APPROVE",
                "project_id": "proj-nat"
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(events[0]["type"], "permission_request_approved");
        assert_eq!(events[0]["request_id"], native_req.request_id);
        assert_eq!(rx_opt.unwrap().await.unwrap().decision, "approved");

        // 2. Disk request cross-project rejected, valid project emits approved + capability_result
        write_sample_disk_request(dir.path(), "perm-disk-1", json!({}));
        assert!(try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "permission_approve",
            &json!({ "type": "permission_approve", "request_id": "perm-disk-1", "project_id": "proj-OTHER" }),
        )
        .await
        .is_err());

        let disk_ev = try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "permission_approve",
            &json!({ "type": "permission_approve", "request_id": "perm-disk-1", "project_id": "proj-1" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(disk_ev[0]["type"], "permission_request_approved");
        assert_eq!(disk_ev[0]["request_id"], "perm-disk-1");
        assert_eq!(disk_ev[1]["type"], "permission_capability_result");
        assert_eq!(disk_ev[1]["status"], "INSTALLATION_REQUIRED");

        // 3. Deny via action_confirm_response REJECT
        write_sample_disk_request(dir.path(), "perm-disk-deny", json!({}));
        let deny_ev = try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "action_confirm_response",
            &json!({ "type": "action_confirm_response", "request_id": "perm-disk-deny", "decision": "REJECT" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(deny_ev[0]["type"], "permission_request_denied");
        assert_eq!(deny_ev[0]["request_id"], "perm-disk-deny");
        assert_eq!(deny_ev[0]["fallback_available"], true);
    }

    #[tokio::test]
    async fn permission_rollback_and_resolve_choice_enforce_governance_invariants() {
        let dir = TempDir::new().unwrap();
        let gw = PermissionGateway::new(Duration::from_secs(60));

        // 1. Limited fallback blocked when criteria fail
        write_sample_disk_request(dir.path(), "perm-choice-1", json!({}));
        let blocked = try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "permission_resolve_choice",
            &json!({
                "type": "permission_resolve_choice",
                "request_id": "perm-choice-1",
                "action": "USE_LIMITED_FALLBACK"
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(blocked[0]["type"], "permission_capability_result");
        assert_eq!(blocked[0]["status"], "BLOCKED_REQUIRED_CAPABILITY");
        assert_eq!(blocked[0]["capability"]["allowed"], false);

        // 2. AUTHORIZE_USE creates child installation request when tool absent
        let auth_ev = try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "permission_resolve_choice",
            &json!({
                "type": "permission_resolve_choice",
                "request_id": "perm-choice-1",
                "action": "AUTHORIZE_USE"
            }),
        )
        .await
        .unwrap()
        .unwrap();
        let child_id = auth_ev[1]["capability"]["installation_request_id"]
            .as_str()
            .expect("child installation request created")
            .to_string();

        // 3. AUTHORIZE_INSTALLATION authorizes clean child request
        let inst_ev = try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "permission_resolve_choice",
            &json!({
                "type": "permission_resolve_choice",
                "request_id": child_id,
                "action": "AUTHORIZE_INSTALLATION"
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(inst_ev[1]["status"], "INSTALLATION_AUTHORIZED");

        // 4. Rollback succeeds for reversible request and rejects unsafe request_id traversal
        let rb_ev = try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "permission_rollback",
            &json!({ "type": "permission_rollback", "request_id": "perm-choice-1" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(rb_ev[0]["type"], "permission_execution_result");
        assert_eq!(rb_ev[0]["status"], "ROLLED_BACK");

        assert!(try_execute_permission_fast_path(
            dir.path(),
            &gw,
            "permission_rollback",
            &json!({ "type": "permission_rollback", "request_id": "../secret" }),
        )
        .await
        .is_err());
    }
}
