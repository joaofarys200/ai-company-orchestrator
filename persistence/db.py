from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Iterator

from workers.common.db_guard import (
    DatabaseWritePermissionError,
    assert_direct_write_allowed,
    get_active_canonical_db_path,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_DB_PATH = get_active_canonical_db_path()
DEFAULT_BUSY_TIMEOUT_MS = 10_000
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10.0


def resolve_db_path(db_path: Path | str | None = None) -> str:
    """Resolve the canonical SQLite database path, anchored at PROJECT_ROOT."""
    if db_path is None:
        import database

        candidate = getattr(database, "DB_FILE", "")
        text = str(candidate).strip() if candidate is not None else ""
        if not text or text == "database.db":
            return str(get_active_canonical_db_path())
        return text

    text = str(db_path).strip()
    if text == ":memory:":
        return ":memory:"
    if not text or text == "database.db":
        return str(get_active_canonical_db_path())
    return text


def get_db_file() -> str:
    """Preserve legacy API returning the active core SQLite path."""
    return resolve_db_path(None)


def apply_sqlite_pragmas(
    conn: sqlite3.Connection,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    enable_wal: bool = True,
    read_only: bool = False,
) -> None:
    """Apply Stage 1 SQLite durability, concurrency, and FK integrity PRAGMAs."""
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    if enable_wal and not read_only:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        current_mode = str(row[0]).lower() if row and row[0] is not None else ""
        if current_mode != "wal":
            conn.execute("PRAGMA journal_mode = WAL")


def get_db_connection(
    db_path: Path | str | None = None,
    *,
    timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    check_same_thread: bool = True,
    read_only: bool = False,
) -> sqlite3.Connection:
    """Open an anchored SQLite connection configured for WAL and busy_timeout."""
    target = resolve_db_path(db_path)
    if read_only and target != ":memory:":
        uri = f"file:{Path(target).resolve().as_posix()}?mode=ro"
        conn = sqlite3.connect(
            uri,
            uri=True,
            timeout=timeout_seconds,
            check_same_thread=check_same_thread,
        )
        conn.execute("PRAGMA query_only = ON")
        apply_sqlite_pragmas(
            conn,
            busy_timeout_ms=busy_timeout_ms,
            enable_wal=False,
            read_only=True,
        )
        return conn

    assert_direct_write_allowed(target, operation="get_db_connection(read_only=False)")
    conn = sqlite3.connect(
        target,
        timeout=timeout_seconds,
        check_same_thread=check_same_thread,
    )
    apply_sqlite_pragmas(
        conn,
        busy_timeout_ms=busy_timeout_ms,
        enable_wal=(target != ":memory:"),
        read_only=False,
    )
    return conn


def get_connection(
    db_path: Path | str | None = None,
    *,
    timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    check_same_thread: bool = True,
    read_only: bool = False,
) -> sqlite3.Connection:
    """Backwards-compatible alias delegating to centralized `get_db_connection`."""
    return get_db_connection(
        db_path=db_path,
        timeout_seconds=timeout_seconds,
        busy_timeout_ms=busy_timeout_ms,
        check_same_thread=check_same_thread,
        read_only=read_only,
    )


@contextmanager
def write_transaction(
    db_path: Path | str | None = None,
    *,
    conn: sqlite3.Connection | None = None,
    timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    check_same_thread: bool = True,
) -> Iterator[sqlite3.Connection]:
    """Execute a SQLite write transaction using explicit `BEGIN IMMEDIATE`."""
    owned = conn is None
    if owned:
        assert_direct_write_allowed(db_path, operation="write_transaction")
    elif getattr(conn, "_jarvis_readonly_locked", False):
        raise DatabaseWritePermissionError(
            "Direct Python write_transaction on read-only canonical database.db connection is forbidden."
        )
    active_conn = (
        get_db_connection(
            db_path=db_path,
            timeout_seconds=timeout_seconds,
            busy_timeout_ms=busy_timeout_ms,
            check_same_thread=check_same_thread,
        )
        if owned
        else conn
    )
    try:
        if not active_conn.in_transaction:
            active_conn.execute("BEGIN IMMEDIATE")
        yield active_conn
        active_conn.commit()
    except BaseException:
        if active_conn.in_transaction:
            active_conn.rollback()
        raise
    finally:
        if owned:
            active_conn.close()


def ensure_rho_schema(conn: sqlite3.Connection) -> None:
    """Ensure RHO telemetry tables and composite query indexes exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_trajectories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            task_profile TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts_count INTEGER NOT NULL,
            failure_reason TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rho_compounding_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_profile TEXT NOT NULL,
            rule_text TEXT NOT NULL,
            failure_trigger TEXT NOT NULL,
            occurrences INTEGER DEFAULT 1,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_model_trajectories_pattern
        ON model_trajectories (task_profile, failure_reason, created_at)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_rho_rules_task_profile_id
        ON rho_compounding_rules (task_profile, id DESC)
        """
    )
