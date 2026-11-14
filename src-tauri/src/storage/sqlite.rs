//! Exclusive Rust single-writer SQLite actor for `database.db`.
//!
//! Architecture:
//! - One dedicated OS thread (`jarvis-sqlite-writer`) owns the single read-write handle
//!   configured in WAL mode (`busy_timeout=10000`, `foreign_keys=ON`, `synchronous=NORMAL`).
//! - Bounded `mpsc::Sender<WriteJob>(512)` serializes all mutations without `SQLITE_BUSY`.
//! - Concurrent readers open read-only WAL handles (`query_only=ON`) via `spawn_blocking`.

use std::collections::BTreeSet;
use std::path::{Path, PathBuf};
use std::sync::Arc;

use chrono::{SecondsFormat, Utc};
use rusqlite::{params, Connection, OpenFlags, OptionalExtension};
use serde::{Deserialize, Serialize};
use tokio::sync::{mpsc, oneshot};

use crate::storage::migrations::{
    apply_migrations, configure_reader_connection, configure_writer_connection,
};

const WRITER_QUEUE_CAPACITY: usize = 512;

type WriteJob = Box<dyn FnOnce(&mut Connection) + Send + 'static>;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SessionRecord {
    pub id: i64,
    pub name: String,
    pub status: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MessageRecord {
    pub id: i64,
    pub session_id: i64,
    pub sender: String,
    pub role: String,
    pub content: String,
    pub timestamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProjectRecord {
    pub id: i64,
    pub session_id: i64,
    pub name: String,
    pub description: Option<String>,
    pub html_content: Option<String>,
    pub css_content: Option<String>,
    pub js_content: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct CompoundingRuleRecord {
    pub id: i64,
    pub rule_key: String,
    pub description: Option<String>,
    pub correction: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArchitectureMemoryRecord {
    pub id: i64,
    pub module: String,
    pub purpose: Option<String>,
    pub dependencies: Option<String>,
    pub constraints: Option<String>,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EngineeringDecisionRecord {
    pub id: i64,
    pub decision: String,
    pub reason: String,
    pub impact: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct StrategicGoalRecord {
    pub id: i64,
    pub goal: String,
    pub criteria: Option<String>,
    pub status: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct EventLogRecord {
    pub id: i64,
    pub event_type: String,
    pub details: Option<String>,
    pub timestamp: String,
}

/// Normalizes sender aliases identically to `backend/message_protocol.py`.
pub fn normalize_canonical_sender(sender: &str) -> String {
    let trimmed = sender.trim();
    if trimmed.is_empty() {
        return "SISTEMA".to_string();
    }
    match trimmed.to_ascii_uppercase().as_str() {
        "OPENCLAW" | "OPEN_CLAW" | "JARVIS" | "ASSISTANT" | "AI" | "ORCHESTRATOR"
        | "ORQUESTRADOR" => "JARVIS".to_string(),
        "CLIENTE" | "USER" | "UTILIZADOR" | "CEO" => "CLIENTE".to_string(),
        "SISTEMA" | "SYSTEM" => "SISTEMA".to_string(),
        _ => trimmed.to_string(),
    }
}

fn utc_now_iso() -> String {
    Utc::now().to_rfc3339_opts(SecondsFormat::Micros, true)
}

#[derive(Clone)]
pub struct SqliteDatabase {
    db_path: Arc<PathBuf>,
    write_tx: mpsc::Sender<WriteJob>,
}

impl std::fmt::Debug for SqliteDatabase {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SqliteDatabase")
            .field("db_path", &self.db_path)
            .finish()
    }
}

impl SqliteDatabase {
    /// Opens or initializes `db_path` using an exclusive WAL single-writer OS thread.
    pub fn open(db_path: impl AsRef<Path>) -> Result<Self, String> {
        let path = db_path.as_ref().to_path_buf();
        if let Some(parent) = path.parent() {
            if !parent.as_os_str().is_empty() {
                std::fs::create_dir_all(parent).map_err(|e| {
                    format!(
                        "Failed to create SQLite parent directory {}: {e}",
                        parent.display()
                    )
                })?;
            }
        }

        let (write_tx, mut write_rx) = mpsc::channel::<WriteJob>(WRITER_QUEUE_CAPACITY);
        let (init_tx, init_rx) = std::sync::mpsc::channel::<Result<(), String>>();
        let thread_path = path.clone();

        std::thread::Builder::new()
            .name("jarvis-sqlite-writer".to_string())
            .spawn(move || {
                let open_res = Connection::open_with_flags(
                    &thread_path,
                    OpenFlags::SQLITE_OPEN_READ_WRITE
                        | OpenFlags::SQLITE_OPEN_CREATE
                        | OpenFlags::SQLITE_OPEN_NO_MUTEX,
                )
                .map_err(|e| {
                    format!(
                        "Failed to open SQLite writer connection at {}: {e}",
                        thread_path.display()
                    )
                });

                let mut conn = match open_res {
                    Ok(mut c) => {
                        if let Err(err) = configure_writer_connection(&c)
                            .and_then(|_| apply_migrations(&mut c).map(|_| ()))
                        {
                            let _ = init_tx.send(Err(err));
                            return;
                        }
                        let _ = init_tx.send(Ok(()));
                        c
                    }
                    Err(err) => {
                        let _ = init_tx.send(Err(err));
                        return;
                    }
                };

                while let Some(job) = write_rx.blocking_recv() {
                    job(&mut conn);
                }
            })
            .map_err(|e| format!("Failed to spawn SQLite writer thread: {e}"))?;

        init_rx
            .recv()
            .map_err(|e| format!("SQLite writer thread aborted during startup: {e}"))??;

        Ok(Self {
            db_path: Arc::new(path),
            write_tx,
        })
    }

    pub fn database_path(&self) -> &Path {
        self.db_path.as_path()
    }

    /// Executes an exclusive write closure on the single-writer thread.
    pub async fn write_with<T, F>(&self, op: F) -> Result<T, String>
    where
        T: Send + 'static,
        F: FnOnce(&mut Connection) -> Result<T, String> + Send + 'static,
    {
        let (tx, rx) = oneshot::channel();
        let job: WriteJob = Box::new(move |conn| {
            let _ = tx.send(op(conn));
        });
        self.write_tx
            .send(job)
            .await
            .map_err(|_| "SQLite writer channel closed".to_string())?;
        rx.await
            .map_err(|_| "SQLite writer task dropped response".to_string())?
    }

    /// Executes a concurrent read-only WAL query via `tokio::task::spawn_blocking`.
    pub async fn read_with<T, F>(&self, op: F) -> Result<T, String>
    where
        T: Send + 'static,
        F: FnOnce(&Connection) -> Result<T, String> + Send + 'static,
    {
        let path = Arc::clone(&self.db_path);
        tokio::task::spawn_blocking(move || {
            let conn = Connection::open_with_flags(
                path.as_path(),
                OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
            )
            .map_err(|e| format!("Failed to open SQLite reader connection: {e}"))?;
            configure_reader_connection(&conn)?;
            op(&conn)
        })
        .await
        .map_err(|e| format!("SQLite reader task failed: {e}"))?
    }

    pub async fn schema_version(&self) -> Result<i64, String> {
        self.read_with(|conn| {
            conn.query_row("PRAGMA user_version", [], |row| row.get(0))
                .map_err(|e| e.to_string())
        })
        .await
    }

    pub async fn journal_mode(&self) -> Result<String, String> {
        self.read_with(|conn| {
            conn.query_row("PRAGMA journal_mode", [], |row| row.get(0))
                .map_err(|e| e.to_string())
        })
        .await
    }

    pub async fn integrity_check(&self) -> Result<String, String> {
        self.read_with(|conn| {
            conn.query_row("PRAGMA integrity_check", [], |row| row.get(0))
                .map_err(|e| e.to_string())
        })
        .await
    }

    pub async fn create_session(&self, name: impl Into<String>) -> Result<SessionRecord, String> {
        let name = name.into();
        let created_at = utc_now_iso();
        self.write_with(move |conn| {
            conn.execute(
                "INSERT INTO sessions (name, status, created_at) VALUES (?1, 'idle', ?2)",
                params![name, created_at],
            )
            .map_err(|e| format!("create_session failed: {e}"))?;
            let id = conn.last_insert_rowid();
            Ok(SessionRecord {
                id,
                name,
                status: "idle".to_string(),
                created_at,
            })
        })
        .await
    }

    pub async fn get_session(&self, session_id: i64) -> Result<Option<SessionRecord>, String> {
        self.read_with(move |conn| {
            conn.query_row(
                "SELECT id, name, COALESCE(status, 'idle'), created_at FROM sessions WHERE id = ?1",
                params![session_id],
                |row| {
                    Ok(SessionRecord {
                        id: row.get(0)?,
                        name: row.get(1)?,
                        status: row.get(2)?,
                        created_at: row.get(3)?,
                    })
                },
            )
            .optional()
            .map_err(|e| format!("get_session failed: {e}"))
        })
        .await
    }

    pub async fn list_sessions(&self, limit: i64) -> Result<Vec<SessionRecord>, String> {
        let clamped = limit.clamp(1, 500);
        self.read_with(move |conn| {
            let mut stmt = conn
                .prepare(
                    "SELECT id, name, COALESCE(status, 'idle'), created_at
                     FROM sessions ORDER BY id DESC LIMIT ?1",
                )
                .map_err(|e| format!("list_sessions prepare failed: {e}"))?;
            let rows = stmt
                .query_map(params![clamped], |row| {
                    Ok(SessionRecord {
                        id: row.get(0)?,
                        name: row.get(1)?,
                        status: row.get(2)?,
                        created_at: row.get(3)?,
                    })
                })
                .map_err(|e| format!("list_sessions query failed: {e}"))?;
            rows.collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("list_sessions collect failed: {e}"))
        })
        .await
    }

    pub async fn update_session_status(
        &self,
        session_id: i64,
        status: impl Into<String>,
    ) -> Result<bool, String> {
        let status = status.into();
        self.write_with(move |conn| {
            let changed = conn
                .execute(
                    "UPDATE sessions SET status = ?1 WHERE id = ?2",
                    params![status, session_id],
                )
                .map_err(|e| format!("update_session_status failed: {e}"))?;
            Ok(changed > 0)
        })
        .await
    }

    pub async fn add_message(
        &self,
        session_id: i64,
        sender: &str,
        role: impl Into<String>,
        content: impl Into<String>,
    ) -> Result<MessageRecord, String> {
        let canonical_sender = normalize_canonical_sender(sender);
        let role = role.into();
        let content = content.into();
        let timestamp = utc_now_iso();

        self.write_with(move |conn| {
            conn.execute(
                "INSERT INTO messages (session_id, sender, role, content, timestamp)
                 VALUES (?1, ?2, ?3, ?4, ?5)",
                params![session_id, canonical_sender, role, content, timestamp],
            )
            .map_err(|e| format!("add_message failed: {e}"))?;
            let id = conn.last_insert_rowid();
            Ok(MessageRecord {
                id,
                session_id,
                sender: canonical_sender,
                role,
                content,
                timestamp,
            })
        })
        .await
    }

    pub async fn list_messages(
        &self,
        session_id: i64,
        limit: i64,
    ) -> Result<Vec<MessageRecord>, String> {
        let clamped = limit.clamp(1, 2000);
        self.read_with(move |conn| {
            let mut stmt = conn
                .prepare(
                    "SELECT id, session_id, sender, role, content, timestamp
                     FROM messages WHERE session_id = ?1 ORDER BY id ASC LIMIT ?2",
                )
                .map_err(|e| format!("list_messages prepare failed: {e}"))?;
            let rows = stmt
                .query_map(params![session_id, clamped], |row| {
                    Ok(MessageRecord {
                        id: row.get(0)?,
                        session_id: row.get(1)?,
                        sender: row.get(2)?,
                        role: row.get(3)?,
                        content: row.get(4)?,
                        timestamp: row.get(5)?,
                    })
                })
                .map_err(|e| format!("list_messages query failed: {e}"))?;
            rows.collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("list_messages collect failed: {e}"))
        })
        .await
    }

    pub async fn save_project(
        &self,
        session_id: i64,
        name: impl Into<String>,
        description: Option<String>,
        html: Option<String>,
        css: Option<String>,
        js: Option<String>,
    ) -> Result<ProjectRecord, String> {
        let name = name.into();
        self.write_with(move |conn| {
            let existing_id: Option<i64> = conn
                .query_row(
                    "SELECT id FROM projects WHERE session_id = ?1 ORDER BY id DESC LIMIT 1",
                    params![session_id],
                    |row| row.get(0),
                )
                .optional()
                .map_err(|e| format!("save_project lookup failed: {e}"))?;

            if let Some(id) = existing_id {
                conn.execute(
                    "UPDATE projects
                     SET name = ?1, description = ?2, html_content = ?3, css_content = ?4, js_content = ?5
                     WHERE id = ?6",
                    params![name, description, html, css, js, id],
                )
                .map_err(|e| format!("save_project update failed: {e}"))?;

                let created_at: String = conn
                    .query_row(
                        "SELECT created_at FROM projects WHERE id = ?1",
                        params![id],
                        |row| row.get(0),
                    )
                    .map_err(|e| format!("save_project fetch created_at failed: {e}"))?;

                Ok(ProjectRecord {
                    id,
                    session_id,
                    name,
                    description,
                    html_content: html,
                    css_content: css,
                    js_content: js,
                    created_at,
                })
            } else {
                let created_at = utc_now_iso();
                conn.execute(
                    "INSERT INTO projects
                     (session_id, name, description, html_content, css_content, js_content, created_at)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
                    params![session_id, name, description, html, css, js, created_at],
                )
                .map_err(|e| format!("save_project insert failed: {e}"))?;
                let id = conn.last_insert_rowid();
                Ok(ProjectRecord {
                    id,
                    session_id,
                    name,
                    description,
                    html_content: html,
                    css_content: css,
                    js_content: js,
                    created_at,
                })
            }
        })
        .await
    }

    pub async fn get_project_by_session(
        &self,
        session_id: i64,
    ) -> Result<Option<ProjectRecord>, String> {
        self.read_with(move |conn| {
            conn.query_row(
                "SELECT id, session_id, name, description, html_content, css_content, js_content, created_at
                 FROM projects WHERE session_id = ?1 ORDER BY id DESC LIMIT 1",
                params![session_id],
                |row| {
                    Ok(ProjectRecord {
                        id: row.get(0)?,
                        session_id: row.get(1)?,
                        name: row.get(2)?,
                        description: row.get(3)?,
                        html_content: row.get(4)?,
                        css_content: row.get(5)?,
                        js_content: row.get(6)?,
                        created_at: row.get(7)?,
                    })
                },
            )
            .optional()
            .map_err(|e| format!("get_project_by_session failed: {e}"))
        })
        .await
    }

    pub async fn list_projects(&self, limit: i64) -> Result<Vec<ProjectRecord>, String> {
        let clamped = limit.clamp(1, 200);
        self.read_with(move |conn| {
            let mut stmt = conn
                .prepare(
                    "SELECT id, session_id, name, description, html_content, css_content, js_content, created_at
                     FROM projects ORDER BY id DESC LIMIT ?1",
                )
                .map_err(|e| format!("list_projects prepare failed: {e}"))?;
            let rows = stmt
                .query_map(params![clamped], |row| {
                    Ok(ProjectRecord {
                        id: row.get(0)?,
                        session_id: row.get(1)?,
                        name: row.get(2)?,
                        description: row.get(3)?,
                        html_content: row.get(4)?,
                        css_content: row.get(5)?,
                        js_content: row.get(6)?,
                        created_at: row.get(7)?,
                    })
                })
                .map_err(|e| format!("list_projects query failed: {e}"))?;
            rows.collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("list_projects collect failed: {e}"))
        })
        .await
    }

    pub async fn add_compounding_rule(
        &self,
        rule_key: impl Into<String>,
        description: impl Into<String>,
        correction: impl Into<String>,
    ) -> Result<(), String> {
        let rule_key = rule_key.into();
        let description = description.into();
        let correction = correction.into();
        let created_at = utc_now_iso();
        self.write_with(move |conn| {
            conn.execute(
                "INSERT INTO compounding_memory (rule_key, description, correction, created_at)
                 VALUES (?1, ?2, ?3, ?4)
                 ON CONFLICT(rule_key) DO UPDATE SET
                   description = excluded.description,
                   correction = excluded.correction",
                params![rule_key, description, correction, created_at],
            )
            .map_err(|e| format!("add_compounding_rule failed: {e}"))?;
            Ok(())
        })
        .await
    }

    pub async fn get_compounding_rules(&self) -> Result<Vec<CompoundingRuleRecord>, String> {
        self.read_with(|conn| {
            let mut stmt = conn
                .prepare(
                    "SELECT id, COALESCE(rule_key, ''), description, correction, created_at
                     FROM compounding_memory ORDER BY id DESC",
                )
                .map_err(|e| format!("get_compounding_rules prepare failed: {e}"))?;
            let rows = stmt
                .query_map([], |row| {
                    Ok(CompoundingRuleRecord {
                        id: row.get(0)?,
                        rule_key: row.get(1)?,
                        description: row.get(2)?,
                        correction: row.get(3)?,
                        created_at: row.get(4)?,
                    })
                })
                .map_err(|e| format!("get_compounding_rules query failed: {e}"))?;
            rows.collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("get_compounding_rules collect failed: {e}"))
        })
        .await
    }

    pub async fn delete_compounding_rule(&self, rule_key: impl Into<String>) -> Result<bool, String> {
        let rule_key = rule_key.into();
        self.write_with(move |conn| {
            let deleted = conn
                .execute(
                    "DELETE FROM compounding_memory WHERE rule_key = ?1",
                    params![rule_key],
                )
                .map_err(|e| format!("delete_compounding_rule failed: {e}"))?;
            Ok(deleted > 0)
        })
        .await
    }

    pub async fn add_architecture_memory(
        &self,
        module: impl Into<String>,
        purpose: impl Into<String>,
        dependencies: impl Into<String>,
        constraints: impl Into<String>,
    ) -> Result<(), String> {
        let module = module.into();
        let purpose = purpose.into();
        let dependencies = dependencies.into();
        let constraints = constraints.into();
        let updated_at = utc_now_iso();

        self.write_with(move |conn| {
            let existing: Option<(Option<String>, Option<String>, Option<String>)> = conn
                .query_row(
                    "SELECT purpose, dependencies, constraints FROM architecture_memory WHERE module = ?1",
                    params![module],
                    |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
                )
                .optional()
                .map_err(|e| format!("add_architecture_memory lookup failed: {e}"))?;

            if let Some((ext_purpose, ext_deps, ext_const)) = existing {
                let merged_purpose = if purpose.trim().is_empty() {
                    ext_purpose.unwrap_or_default()
                } else {
                    purpose
                };

                let mut deps_set = BTreeSet::new();
                for raw in ext_deps.unwrap_or_default().split(',') {
                    let s = raw.trim();
                    if !s.is_empty() {
                        deps_set.insert(s.to_string());
                    }
                }
                for raw in dependencies.split(',') {
                    let s = raw.trim();
                    if !s.is_empty() {
                        deps_set.insert(s.to_string());
                    }
                }
                let merged_deps = deps_set.into_iter().collect::<Vec<_>>().join(", ");

                let mut merged_const = ext_const.unwrap_or_default();
                if !constraints.trim().is_empty() && !merged_const.contains(constraints.trim()) {
                    if !merged_const.is_empty() {
                        merged_const.push_str("; ");
                    }
                    merged_const.push_str(constraints.trim());
                }

                conn.execute(
                    "UPDATE architecture_memory
                     SET purpose = ?1, dependencies = ?2, constraints = ?3, updated_at = ?4
                     WHERE module = ?5",
                    params![merged_purpose, merged_deps, merged_const, updated_at, module],
                )
                .map_err(|e| format!("add_architecture_memory update failed: {e}"))?;
            } else {
                conn.execute(
                    "INSERT INTO architecture_memory
                     (module, purpose, dependencies, constraints, updated_at)
                     VALUES (?1, ?2, ?3, ?4, ?5)",
                    params![module, purpose, dependencies, constraints, updated_at],
                )
                .map_err(|e| format!("add_architecture_memory insert failed: {e}"))?;
            }
            Ok(())
        })
        .await
    }

    pub async fn get_architecture_memory(&self) -> Result<Vec<ArchitectureMemoryRecord>, String> {
        self.read_with(|conn| {
            let mut stmt = conn
                .prepare(
                    "SELECT id, module, purpose, dependencies, constraints, updated_at
                     FROM architecture_memory ORDER BY module ASC",
                )
                .map_err(|e| format!("get_architecture_memory prepare failed: {e}"))?;
            let rows = stmt
                .query_map([], |row| {
                    Ok(ArchitectureMemoryRecord {
                        id: row.get(0)?,
                        module: row.get(1)?,
                        purpose: row.get(2)?,
                        dependencies: row.get(3)?,
                        constraints: row.get(4)?,
                        updated_at: row.get(5)?,
                    })
                })
                .map_err(|e| format!("get_architecture_memory query failed: {e}"))?;
            rows.collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("get_architecture_memory collect failed: {e}"))
        })
        .await
    }

    pub async fn delete_architecture_memory(&self, module: impl Into<String>) -> Result<bool, String> {
        let module = module.into();
        self.write_with(move |conn| {
            let deleted = conn
                .execute(
                    "DELETE FROM architecture_memory WHERE module = ?1",
                    params![module],
                )
                .map_err(|e| format!("delete_architecture_memory failed: {e}"))?;
            Ok(deleted > 0)
        })
        .await
    }

    pub async fn add_engineering_decision(
        &self,
        decision: impl Into<String>,
        reason: impl Into<String>,
        impact: impl Into<String>,
    ) -> Result<EngineeringDecisionRecord, String> {
        let decision = decision.into();
        let reason = reason.into();
        let impact_str = impact.into();
        let impact_opt = if impact_str.is_empty() {
            None
        } else {
            Some(impact_str)
        };
        let created_at = utc_now_iso();

        self.write_with(move |conn| {
            conn.execute(
                "INSERT INTO engineering_decisions (decision, reason, impact, created_at)
                 VALUES (?1, ?2, ?3, ?4)",
                params![decision, reason, impact_opt, created_at],
            )
            .map_err(|e| format!("add_engineering_decision failed: {e}"))?;
            let id = conn.last_insert_rowid();
            Ok(EngineeringDecisionRecord {
                id,
                decision,
                reason,
                impact: impact_opt,
                created_at,
            })
        })
        .await
    }

    pub async fn get_engineering_decisions(&self) -> Result<Vec<EngineeringDecisionRecord>, String> {
        self.read_with(|conn| {
            let mut stmt = conn
                .prepare(
                    "SELECT id, decision, reason, impact, created_at
                     FROM engineering_decisions ORDER BY id DESC",
                )
                .map_err(|e| format!("get_engineering_decisions prepare failed: {e}"))?;
            let rows = stmt
                .query_map([], |row| {
                    Ok(EngineeringDecisionRecord {
                        id: row.get(0)?,
                        decision: row.get(1)?,
                        reason: row.get(2)?,
                        impact: row.get(3)?,
                        created_at: row.get(4)?,
                    })
                })
                .map_err(|e| format!("get_engineering_decisions query failed: {e}"))?;
            rows.collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("get_engineering_decisions collect failed: {e}"))
        })
        .await
    }

    pub async fn delete_engineering_decision(
        &self,
        decision: impl Into<String>,
    ) -> Result<bool, String> {
        let decision = decision.into();
        self.write_with(move |conn| {
            let deleted = conn
                .execute(
                    "DELETE FROM engineering_decisions WHERE decision = ?1",
                    params![decision],
                )
                .map_err(|e| format!("delete_engineering_decision failed: {e}"))?;
            Ok(deleted > 0)
        })
        .await
    }

    pub async fn add_strategic_goal(
        &self,
        goal: impl Into<String>,
        criteria: Option<String>,
        status: Option<String>,
    ) -> Result<StrategicGoalRecord, String> {
        let goal = goal.into();
        let status = status.unwrap_or_else(|| "active".to_string());
        let created_at = utc_now_iso();
        self.write_with(move |conn| {
            conn.execute(
                "INSERT INTO strategic_goals (goal, criteria, status, created_at)
                 VALUES (?1, ?2, ?3, ?4)",
                params![goal, criteria, status, created_at],
            )
            .map_err(|e| format!("add_strategic_goal failed: {e}"))?;
            let id = conn.last_insert_rowid();
            Ok(StrategicGoalRecord {
                id,
                goal,
                criteria,
                status,
                created_at,
            })
        })
        .await
    }

    pub async fn list_strategic_goals(&self) -> Result<Vec<StrategicGoalRecord>, String> {
        self.read_with(|conn| {
            let mut stmt = conn
                .prepare(
                    "SELECT id, goal, criteria, COALESCE(status, 'active'), created_at
                     FROM strategic_goals ORDER BY id DESC",
                )
                .map_err(|e| format!("list_strategic_goals prepare failed: {e}"))?;
            let rows = stmt
                .query_map([], |row| {
                    Ok(StrategicGoalRecord {
                        id: row.get(0)?,
                        goal: row.get(1)?,
                        criteria: row.get(2)?,
                        status: row.get(3)?,
                        created_at: row.get(4)?,
                    })
                })
                .map_err(|e| format!("list_strategic_goals query failed: {e}"))?;
            rows.collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("list_strategic_goals collect failed: {e}"))
        })
        .await
    }

    pub async fn append_event_log(
        &self,
        event_type: impl Into<String>,
        details: Option<String>,
    ) -> Result<EventLogRecord, String> {
        let event_type = event_type.into();
        let timestamp = utc_now_iso();
        self.write_with(move |conn| {
            conn.execute(
                "INSERT INTO event_sourcing_log (event_type, details, timestamp)
                 VALUES (?1, ?2, ?3)",
                params![event_type, details, timestamp],
            )
            .map_err(|e| format!("append_event_log failed: {e}"))?;
            let id = conn.last_insert_rowid();
            Ok(EventLogRecord {
                id,
                event_type,
                details,
                timestamp,
            })
        })
        .await
    }

    pub async fn list_event_logs(&self, limit: i64) -> Result<Vec<EventLogRecord>, String> {
        let clamped = limit.clamp(1, 1000);
        self.read_with(move |conn| {
            let mut stmt = conn
                .prepare(
                    "SELECT id, event_type, details, timestamp
                     FROM event_sourcing_log ORDER BY id DESC LIMIT ?1",
                )
                .map_err(|e| format!("list_event_logs prepare failed: {e}"))?;
            let rows = stmt
                .query_map(params![clamped], |row| {
                    Ok(EventLogRecord {
                        id: row.get(0)?,
                        event_type: row.get(1)?,
                        details: row.get(2)?,
                        timestamp: row.get(3)?,
                    })
                })
                .map_err(|e| format!("list_event_logs query failed: {e}"))?;
            rows.collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("list_event_logs collect failed: {e}"))
        })
        .await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn migrations_preserve_existing_rows_and_legacy_rho_tables() {
        let dir = tempdir().expect("create tempdir");
        let db_path = dir.path().join("legacy_copy.db");

        // Pre-populate disposable database matching legacy Python database.py (`user_version=0`).
        {
            let conn = Connection::open(&db_path).expect("create seed sqlite");
            conn.execute_batch(
                "
                CREATE TABLE sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, status TEXT DEFAULT 'idle', created_at TEXT NOT NULL);
                CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, sender TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT NOT NULL, FOREIGN KEY (session_id) REFERENCES sessions (id));
                CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, name TEXT NOT NULL, description TEXT, html_content TEXT, css_content TEXT, js_content TEXT, created_at TEXT NOT NULL, FOREIGN KEY (session_id) REFERENCES sessions (id));
                CREATE TABLE model_trajectories (id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL, task_profile TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL, attempts_count INTEGER NOT NULL, failure_reason TEXT, created_at REAL NOT NULL);

                INSERT INTO sessions (id, name, status, created_at) VALUES (7, 'ExistingSession', 'active', '2026-01-01T00:00:00Z');
                INSERT INTO messages (session_id, sender, role, content, timestamp) VALUES (7, 'OPENCLAW', 'assistant', 'Legacy hello', '2026-01-01T00:00:01Z');
                INSERT INTO projects (session_id, name, description, html_content, css_content, js_content, created_at) VALUES (7, 'DemoApp', 'desc', '<h1>Hi</h1>', '', '', '2026-01-01T00:00:02Z');
                INSERT INTO model_trajectories (request_id, task_profile, fingerprint, status, attempts_count, failure_reason, created_at) VALUES ('r1', 'coding', 'fp1', 'failed', 1, 'none', 123.0);
                ",
            )
            .expect("seed legacy schema");
        }

        // Open twice to confirm migration + idempotency.
        for _ in 0..2 {
            let db = SqliteDatabase::open(&db_path).expect("open migrated db");
            assert_eq!(db.schema_version().await.unwrap(), 1);
            assert_eq!(db.journal_mode().await.unwrap().to_ascii_lowercase(), "wal");
            assert_eq!(db.integrity_check().await.unwrap(), "ok");

            let session = db.get_session(7).await.unwrap().expect("session preserved");
            assert_eq!(session.name, "ExistingSession");

            let msgs = db.list_messages(7, 50).await.unwrap();
            assert_eq!(msgs.len(), 1);
            assert_eq!(msgs[0].sender, "JARVIS");
            assert_eq!(msgs[0].content, "Legacy hello");

            let proj = db
                .get_project_by_session(7)
                .await
                .unwrap()
                .expect("project preserved");
            assert_eq!(proj.name, "DemoApp");

            // Legacy non-core RHO table untouched and preserved
            let rho_count: i64 = db
                .read_with(|conn| {
                    conn.query_row("SELECT COUNT(*) FROM model_trajectories", [], |r| r.get(0))
                        .map_err(|e| e.to_string())
                })
                .await
                .unwrap();
            assert_eq!(rho_count, 1);
        }
    }

    #[tokio::test]
    async fn single_writer_handles_concurrent_writes_and_reads_without_busy_errors() {
        let dir = tempdir().expect("create tempdir");
        let db = SqliteDatabase::open(dir.path().join("concurrent.db")).expect("open sqlite");

        let session = db.create_session("Concurrency").await.expect("create session");
        let mut handles = Vec::new();

        for writer_idx in 0..16 {
            let db_clone = db.clone();
            handles.push(tokio::spawn(async move {
                for msg_idx in 0..5 {
                    db_clone
                        .add_message(
                            session.id,
                            if msg_idx % 2 == 0 { "USER" } else { "AI" },
                            "user",
                            format!("w{writer_idx}-m{msg_idx}"),
                        )
                        .await
                        .expect("concurrent add_message");
                }
            }));
        }

        for _ in 0..16 {
            let db_clone = db.clone();
            handles.push(tokio::spawn(async move {
                let _ = db_clone.list_messages(session.id, 100).await.unwrap();
            }));
        }

        for h in handles {
            h.await.expect("task panicked");
        }

        let all_msgs = db.list_messages(session.id, 500).await.unwrap();
        assert_eq!(all_msgs.len(), 80);
        assert!(all_msgs.iter().all(|m| m.sender == "CLIENTE" || m.sender == "JARVIS"));
    }

    #[tokio::test]
    async fn crud_repositories_match_python_semantics() {
        let dir = tempdir().expect("create tempdir");
        let db = SqliteDatabase::open(dir.path().join("crud.db")).expect("open sqlite");

        let s = db.create_session("RepoParity").await.unwrap();
        assert!(db.update_session_status(s.id, "running").await.unwrap());
        assert_eq!(db.get_session(s.id).await.unwrap().unwrap().status, "running");

        // Project upsert on session_id
        let p1 = db
            .save_project(s.id, "V1", Some("d1".into()), Some("h1".into()), None, None)
            .await
            .unwrap();
        let p2 = db
            .save_project(s.id, "V2", Some("d2".into()), Some("h2".into()), None, None)
            .await
            .unwrap();
        assert_eq!(p1.id, p2.id);
        assert_eq!(db.list_projects(10).await.unwrap().len(), 1);

        // Architecture memory merges dependencies and constraints
        db.add_architecture_memory("core.rpc", "Transport", "tokio, serde", "no panic")
            .await
            .unwrap();
        db.add_architecture_memory("core.rpc", "", "axum, tokio", "16MiB max")
            .await
            .unwrap();
        let arch = db.get_architecture_memory().await.unwrap();
        assert_eq!(arch.len(), 1);
        assert_eq!(arch[0].purpose.as_deref(), Some("Transport"));
        assert_eq!(arch[0].dependencies.as_deref(), Some("axum, serde, tokio"));
        assert_eq!(arch[0].constraints.as_deref(), Some("no panic; 16MiB max"));
        assert!(db.delete_architecture_memory("core.rpc").await.unwrap());

        // Compounding rules, engineering decisions, strategic goals, event log
        db.add_compounding_rule("r1", "desc", "fix").await.unwrap();
        assert_eq!(db.get_compounding_rules().await.unwrap().len(), 1);
        assert!(db.delete_compounding_rule("r1").await.unwrap());

        db.add_engineering_decision("Use WAL", "Single writer", "High")
            .await
            .unwrap();
        assert_eq!(db.get_engineering_decisions().await.unwrap().len(), 1);
        assert!(db.delete_engineering_decision("Use WAL").await.unwrap());

        let goal = db
            .add_strategic_goal("Migrate to Rust", Some("100% pass".into()), None)
            .await
            .unwrap();
        assert_eq!(goal.status, "active");
        assert_eq!(db.list_strategic_goals().await.unwrap().len(), 1);

        db.append_event_log("PHASE_3", Some("ok".into())).await.unwrap();
        assert_eq!(db.list_event_logs(10).await.unwrap().len(), 1);
    }
}
