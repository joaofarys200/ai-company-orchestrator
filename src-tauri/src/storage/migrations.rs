//! Idempotent SQLite WAL configuration and `PRAGMA user_version` schema migrations.
//!
//! Targets `PROJECT_ROOT/database.db` (or disposable temp copies in tests). Preserves all
//! existing rows and any non-core tables (for example legacy RHO tables during transition).

use rusqlite::{Connection, TransactionBehavior};

pub const CURRENT_SCHEMA_VERSION: i64 = 1;

/// Applies WAL durability and concurrency pragmas on the single exclusive writer connection.
pub fn configure_writer_connection(conn: &Connection) -> Result<(), String> {
    conn.execute_batch(
        "
        PRAGMA journal_mode = WAL;
        PRAGMA synchronous = NORMAL;
        PRAGMA busy_timeout = 10000;
        PRAGMA foreign_keys = ON;
        PRAGMA temp_store = MEMORY;
        ",
    )
    .map_err(|e| format!("Failed to configure SQLite writer pragmas: {e}"))
}

/// Applies safe read-only pragmas for concurrent reader connections in WAL mode.
pub fn configure_reader_connection(conn: &Connection) -> Result<(), String> {
    conn.execute_batch(
        "
        PRAGMA query_only = ON;
        PRAGMA busy_timeout = 10000;
        PRAGMA foreign_keys = ON;
        PRAGMA temp_store = MEMORY;
        ",
    )
    .map_err(|e| format!("Failed to configure SQLite reader pragmas: {e}"))
}

/// Migrates the core JARVIS OS schema up to `CURRENT_SCHEMA_VERSION` without dropping
/// existing rows or unrecognized tables.
pub fn apply_migrations(conn: &mut Connection) -> Result<i64, String> {
    let current_version: i64 = conn
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|e| format!("Failed to read SQLite user_version: {e}"))?;

    if current_version > CURRENT_SCHEMA_VERSION {
        return Err(format!(
            "Database schema version {current_version} is newer than supported version {CURRENT_SCHEMA_VERSION}"
        ));
    }

    if current_version < 1 {
        let tx = conn
            .transaction_with_behavior(TransactionBehavior::Immediate)
            .map_err(|e| format!("Failed to begin migration transaction: {e}"))?;

        tx.execute_batch(
            "
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                html_content TEXT,
                css_content TEXT,
                js_content TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            );

            CREATE TABLE IF NOT EXISTS compounding_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_key TEXT UNIQUE,
                description TEXT,
                correction TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS architecture_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL UNIQUE,
                purpose TEXT,
                dependencies TEXT,
                constraints TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS engineering_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                impact TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS strategic_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                criteria TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS event_sourcing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session_id
            ON messages (session_id, id);

            CREATE INDEX IF NOT EXISTS idx_projects_session_id
            ON projects (session_id, id DESC);

            CREATE INDEX IF NOT EXISTS idx_event_sourcing_ts
            ON event_sourcing_log (id DESC);

            UPDATE messages
            SET sender = 'JARVIS'
            WHERE UPPER(sender) IN ('OPENCLAW', 'OPEN_CLAW');

            PRAGMA user_version = 1;
            ",
        )
        .map_err(|e| format!("Failed to apply v1 core schema migration: {e}"))?;

        tx.commit()
            .map_err(|e| format!("Failed to commit v1 schema migration: {e}"))?;
    }

    let final_version: i64 = conn
        .query_row("PRAGMA user_version", [], |row| row.get(0))
        .map_err(|e| format!("Failed to verify final SQLite user_version: {e}"))?;

    Ok(final_version)
}
