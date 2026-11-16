//! Read-only mission observer fast path.
//!
//! Per Stage-2 persistence ownership (`docs/decisions/ADR-005-sqlite-and-json-state-persistence.md`), Python
//! `MissionWorker` remains the exclusive writer of per-mission `state.db` files.
//! This module only serves read-only `mission_list` observations by inspecting
//! `workspace/.jarvis/projects/<project_id>/missions/*/mission.json` and falling
//! back to `SQLITE_OPEN_READ_ONLY` queries on `state.db` when needed.
//!
//! `mission_get`, `mission_resume_snapshot`, and all mission/work-package/governance
//! mutations intentionally return `Ok(None)` so `dispatch.rs` routes them to
//! Python `MissionWorker`.

use std::fs;
use std::path::{Path, PathBuf};

use rusqlite::{Connection, OpenFlags};
use serde_json::{json, Value};

use crate::error::AppError;
use crate::permissions::path_jail::{ensure_confined_existing_file, is_safe_identifier};

fn metadata_missions_dir(project_root: &Path, project_id: &str) -> PathBuf {
    project_root
        .join("workspace")
        .join(".jarvis")
        .join("projects")
        .join(project_id)
        .join("missions")
}

fn read_mission_json_summary(mission_dir: &Path) -> Option<Value> {
    let json_path = mission_dir.join("mission.json");
    let canon = ensure_confined_existing_file(mission_dir, &json_path).ok()?;
    let raw = fs::read_to_string(&canon).ok()?;
    let parsed: Value = serde_json::from_str(&raw).ok()?;
    if parsed.is_object() {
        Some(parsed)
    } else {
        None
    }
}

fn read_mission_sqlite_readonly(mission_dir: &Path) -> Option<Value> {
    let db_path = mission_dir.join("state.db");
    let canon = ensure_confined_existing_file(mission_dir, &db_path).ok()?;
    let conn = Connection::open_with_flags(
        &canon,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .ok()?;
    let _ = conn.busy_timeout(std::time::Duration::from_millis(500));

    let mut stmt = conn
        .prepare(
            "SELECT mission_id, project_id, title, objective, description, status, \
             current_phase, progress, metadata_json, created_at, updated_at, \
             started_at, completed_at, version \
             FROM missions ORDER BY updated_at DESC LIMIT 1",
        )
        .ok()?;

    let mut rows = stmt.query([]).ok()?;
    let row = rows.next().ok()??;

    let mission_id: String = row.get(0).ok()?;
    let project_id: String = row.get(1).ok()?;
    let title: String = row.get(2).ok()?;
    let objective: String = row.get(3).ok()?;
    let description: String = row
        .get::<_, Option<String>>(4)
        .ok()
        .flatten()
        .unwrap_or_default();
    let status: String = row.get(5).ok()?;
    let current_phase: String = row
        .get::<_, Option<String>>(6)
        .ok()
        .flatten()
        .unwrap_or_default();
    let progress: f64 = row.get::<_, Option<f64>>(7).ok().flatten().unwrap_or(0.0);
    let metadata_raw: String = row
        .get::<_, Option<String>>(8)
        .ok()
        .flatten()
        .unwrap_or_else(|| "{}".to_string());
    let created_at: String = row
        .get::<_, Option<String>>(9)
        .ok()
        .flatten()
        .unwrap_or_default();
    let updated_at: String = row
        .get::<_, Option<String>>(10)
        .ok()
        .flatten()
        .unwrap_or_default();
    let started_at: Option<String> = row.get::<_, Option<String>>(11).ok().flatten();
    let completed_at: Option<String> = row.get::<_, Option<String>>(12).ok().flatten();
    let version: i64 = row.get::<_, Option<i64>>(13).ok().flatten().unwrap_or(1);

    let metadata: Value = serde_json::from_str(&metadata_raw).unwrap_or_else(|_| json!({}));

    let mut record = json!({
        "mission_id": mission_id,
        "project_id": project_id,
        "title": title,
        "objective": objective,
        "description": description,
        "status": status,
        "current_phase": current_phase,
        "progress": progress,
        "metadata": metadata,
        "created_at": created_at,
        "updated_at": updated_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "version": version,
    });

    if let (Some(obj), Some(meta_obj)) = (record.as_object_mut(), metadata.as_object()) {
        for key in [
            "project_name",
            "project_path",
            "execution_id",
            "current_stage",
            "last_event_at",
            "last_event_sequence",
        ] {
            if let Some(v) = meta_obj.get(key) {
                obj.insert(key.to_string(), v.clone());
            }
        }
    }

    Some(record)
}

fn collect_missions_readonly(project_root: &Path, project_id: &str) -> Vec<Value> {
    let missions_dir = metadata_missions_dir(project_root, project_id);
    if !missions_dir.is_dir() {
        return Vec::new();
    }

    let Ok(entries) = fs::read_dir(&missions_dir) else {
        return Vec::new();
    };

    let mut items = Vec::new();
    for entry in entries.flatten() {
        let dir_path = entry.path();
        if !dir_path.is_dir() {
            continue;
        }
        // Prefer SQLite read-only view when available so pure SQLite mode stays current,
        // falling back to mission.json when SQLite is absent or sharded-only.
        let summary = read_mission_sqlite_readonly(&dir_path)
            .or_else(|| read_mission_json_summary(&dir_path));
        if let Some(m) = summary {
            items.push(m);
        }
    }

    items.sort_by(|a, b| {
        let ua = a
            .get("updated_at")
            .and_then(Value::as_str)
            .unwrap_or_default();
        let ub = b
            .get("updated_at")
            .and_then(Value::as_str)
            .unwrap_or_default();
        let ma = a
            .get("mission_id")
            .and_then(Value::as_str)
            .unwrap_or_default();
        let mb = b
            .get("mission_id")
            .and_then(Value::as_str)
            .unwrap_or_default();
        ub.cmp(ua).then_with(|| ma.cmp(mb))
    });
    items
}

/// Handles read-only mission observation routes natively in Rust.
pub async fn try_execute_mission_fast_path(
    project_root: &Path,
    msg_type: &str,
    message: &Value,
) -> Result<Option<Vec<Value>>, AppError> {
    if msg_type != "mission_list" {
        return Ok(None);
    }

    let project_id = message
        .get("project_id")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim()
        .to_string();

    if project_id.is_empty() || !is_safe_identifier(&project_id) {
        return Err(AppError::new(
            "INVALID_PROJECT_IDENTIFIER",
            "Invalid or missing project_id for mission_list",
        ));
    }

    let root = project_root.to_path_buf();
    let pid_for_task = project_id.clone();
    let missions =
        tokio::task::spawn_blocking(move || collect_missions_readonly(&root, &pid_for_task))
            .await
            .map_err(|err| {
                AppError::new(
                    "MISSION_LIST_TASK_FAILED",
                    format!("Read-only mission listing task panicked: {err}"),
                )
            })?;

    Ok(Some(vec![json!({
        "type": "mission_list",
        "project_id": project_id,
        "missions": missions,
    })]))
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn mission_list_reads_state_db_and_mission_json_readonly() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        let m_base = metadata_missions_dir(&root, "proj_alpha");
        let m1_dir = m_base.join("m_sqlite");
        let m2_dir = m_base.join("m_json");
        fs::create_dir_all(&m1_dir).unwrap();
        fs::create_dir_all(&m2_dir).unwrap();

        // Populate m1 via SQLite (simulating Python MissionWorker sqlite mode)
        let db_path = m1_dir.join("state.db");
        {
            let conn = Connection::open(&db_path).unwrap();
            conn.execute_batch(
                "CREATE TABLE missions (
                    mission_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    current_phase TEXT,
                    progress REAL DEFAULT 0.0,
                    metadata_json TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    version INTEGER DEFAULT 1
                );",
            )
            .unwrap();
            conn.execute(
                "INSERT INTO missions VALUES (?1, ?2, ?3, ?4, '', 'COMPLETED', 'DONE', 100.0, ?5, '2026-11-14T09:00:00Z', '2026-11-14T11:00:00Z', NULL, NULL, 2)",
                rusqlite::params![
                    "m_sqlite",
                    "proj_alpha",
                    "SQLite Mission",
                    "Verify RO listing",
                    r#"{"current_stage":"COMPLETED","execution_id":"exec_9"}"#,
                ],
            )
            .unwrap();
        }

        // Populate m2 via mission.json only (older timestamp)
        fs::write(
            m2_dir.join("mission.json"),
            json!({
                "mission_id": "m_json",
                "project_id": "proj_alpha",
                "title": "JSON Mission",
                "objective": "Verify fallback",
                "status": "CREATED",
                "progress": 0.0,
                "updated_at": "2026-11-14T10:00:00Z",
                "version": 1
            })
            .to_string(),
        )
        .unwrap();

        let events = try_execute_mission_fast_path(
            &root,
            "mission_list",
            &json!({"type": "mission_list", "project_id": "proj_alpha"}),
        )
        .await
        .unwrap()
        .unwrap();

        assert_eq!(events.len(), 1);
        assert_eq!(events[0]["type"], "mission_list");
        let list = events[0]["missions"].as_array().unwrap();
        assert_eq!(list.len(), 2);
        // Sorted by updated_at DESC: m_sqlite first, then m_json
        assert_eq!(list[0]["mission_id"], "m_sqlite");
        assert_eq!(list[0]["execution_id"], "exec_9");
        assert_eq!(list[1]["mission_id"], "m_json");

        // Ensure writes remain delegated to Python MissionWorker
        let pass = try_execute_mission_fast_path(
            &root,
            "mission_get",
            &json!({"project_id": "proj_alpha", "mission_id": "m_sqlite"}),
        )
        .await
        .unwrap();
        assert!(pass.is_none());
    }
}
