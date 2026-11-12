from contextlib import closing
import os
from pathlib import Path
import re
import difflib
from datetime import datetime, timezone

from backend.logging_config import get_logger, log_event
from persistence.db import (
    CANONICAL_DB_PATH,
    ensure_rho_schema,
    get_db_connection as open_db_connection,
    write_transaction,
)


logger = get_logger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def get_similarity(s1: str, s2: str) -> float:
    def clean(s):
        return re.sub(r'[^a-z0-9\u00C0-\u00FF]', '', s.lower())
    c1, c2 = clean(s1), clean(s2)
    if not c1 or not c2:
        return 0.0
    return difflib.SequenceMatcher(None, c1, c2).ratio()


PROJECT_ROOT = Path(__file__).resolve().parent
DB_FILE = str(CANONICAL_DB_PATH)


def get_db_connection(
    db_path: Path | str | None = None,
    *,
    timeout_seconds: float = 10.0,
    busy_timeout_ms: int = 10_000,
    check_same_thread: bool = True,
    read_only: bool = False,
):
    """Open an anchored WAL SQLite connection (centralized helper)."""
    return open_db_connection(
        db_path=db_path,
        timeout_seconds=timeout_seconds,
        busy_timeout_ms=busy_timeout_ms,
        check_same_thread=check_same_thread,
        read_only=read_only,
    )


def get_connection():
    return get_db_connection()


def init_db():
    with closing(get_connection()) as conn, write_transaction(conn=conn):
        cursor = conn.cursor()
        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status TEXT DEFAULT 'idle',
                created_at TEXT NOT NULL
            )
        """)
        # Create messages table for conversational history logging
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        """)
        # Create projects table to persist sandbox output files
        cursor.execute("""
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
            )
        """)
        # Create compounding_memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compounding_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_key TEXT UNIQUE,
                description TEXT,
                correction TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Create architecture_memory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS architecture_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL UNIQUE,
                purpose TEXT,
                dependencies TEXT,
                constraints TEXT,
                updated_at TEXT NOT NULL
            )
        """)

        # Create engineering_decisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS engineering_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision TEXT NOT NULL,
                reason TEXT NOT NULL,
                impact TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Create strategic_goals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategic_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal TEXT NOT NULL,
                criteria TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL
            )
        """)

        # Create event_sourcing_log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_sourcing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)

        # Ensure RHO telemetry schema & composite indexes
        ensure_rho_schema(conn)

        # Migration: Normalize legacy OPENCLAW sender in messages table
        cursor.execute("""
            UPDATE messages SET sender = 'JARVIS' WHERE UPPER(sender) = 'OPENCLAW'
        """)

def add_compounding_rule(rule_key: str, description: str, correction: str):
    created_at = utc_now_iso()
    try:
        with closing(get_connection()) as conn, write_transaction(conn=conn):
            cursor = conn.cursor()
            # Check similarity with existing rules
            cursor.execute("SELECT rule_key, description, correction FROM compounding_memory")
            existing = cursor.fetchall()

            for ext_key, ext_desc, ext_corr in existing:
                # Overwrite/update if key is exact match OR if correction is highly similar (similarity > 0.75)
                if (rule_key.lower() == ext_key.lower() or
                    get_similarity(correction, ext_corr) > 0.75 or
                    get_similarity(rule_key, ext_key) > 0.85):
                    log_event(logger, "database.rule.redundant_update", rule_key=ext_key)
                    cursor.execute("""
                        UPDATE compounding_memory
                        SET description = ?, correction = ?, created_at = ?
                        WHERE rule_key = ?
                    """, (description, correction, created_at, ext_key))
                    return

            cursor.execute("""
                INSERT INTO compounding_memory (rule_key, description, correction, created_at)
                VALUES (?, ?, ?, ?)
            """, (rule_key, description, correction, created_at))
    except Exception as e:
        log_event(logger, "database.rule.save_error", level="error", error=str(e))

def get_compounding_rules():
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rule_key, description, correction FROM compounding_memory ORDER BY id DESC")
            rows = cursor.fetchall()
            return [{"rule_key": r[0], "description": r[1], "correction": r[2]} for r in rows]
    except Exception as e:
        log_event(logger, "database.rule.read_error", level="error", error=str(e))
        return []

def delete_compounding_rule(rule_key: str) -> bool:
    try:
        with closing(get_connection()) as conn, write_transaction(conn=conn):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM compounding_memory WHERE rule_key = ?", (rule_key,))
            return cursor.rowcount > 0
    except Exception as e:
        log_event(logger, "database.rule.delete_error", level="error", rule_key=rule_key, error=str(e))
        return False


def create_session(name: str):
    created_at = utc_now_iso()
    with closing(get_connection()) as conn, write_transaction(conn=conn):
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (name, status, created_at) VALUES (?, ?, ?)",
            (name, "idle", created_at)
        )
        session_id = cursor.lastrowid

    class SessionObj:
        id = session_id
    return SessionObj()

def add_message(session_id: int, sender: str, role: str, content: str):
    from backend.message_protocol import normalize_canonical_sender
    canonical_sender = normalize_canonical_sender(sender)
    timestamp = utc_now_iso()
    with closing(get_connection()) as conn, write_transaction(conn=conn):
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (session_id, sender, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, canonical_sender, role, content, timestamp))

def save_project(session_id: int, name: str, description: str, html: str, css: str, js: str):
    with closing(get_connection()) as conn, write_transaction(conn=conn):
        cursor = conn.cursor()

        # Check if a project matching this session_id already exists
        cursor.execute("SELECT id FROM projects WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()

        if row:
            cursor.execute("""
                UPDATE projects
                SET name = ?, description = ?, html_content = ?, css_content = ?, js_content = ?
                WHERE session_id = ?
            """, (name, description, html, css, js, session_id))
        else:
            created_at = utc_now_iso()
            cursor.execute("""
                INSERT INTO projects (session_id, name, description, html_content, css_content, js_content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (session_id, name, description, html, css, js, created_at))

def get_architecture_memory():
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT module, purpose, dependencies, constraints, updated_at FROM architecture_memory ORDER BY module ASC")
            rows = cursor.fetchall()
            return [
                {
                    "module": r[0],
                    "purpose": r[1],
                    "dependencies": r[2],
                    "constraints": r[3],
                    "updated_at": r[4]
                }
                for r in rows
            ]
    except Exception as e:
        log_event(logger, "database.architecture.read_error", level="error", error=str(e))
        return []

def add_architecture_memory(module: str, purpose: str, dependencies: str, constraints: str):
    updated_at = utc_now_iso()
    try:
        with closing(get_connection()) as conn, write_transaction(conn=conn):
            cursor = conn.cursor()
            # Check if module already exists to merge constraints/dependencies instead of simple overwrite
            cursor.execute("SELECT purpose, dependencies, constraints FROM architecture_memory WHERE module = ?", (module,))
            existing = cursor.fetchone()

            if existing:
                ext_purpose, ext_deps, ext_const = existing
                merged_purpose = purpose if purpose else ext_purpose

                # Merge dependencies list
                deps_set = set(d.strip() for d in (ext_deps or "").split(",") if d.strip())
                new_deps = set(d.strip() for d in (dependencies or "").split(",") if d.strip())
                merged_deps = ", ".join(sorted(deps_set.union(new_deps)))

                # Merge constraints if not redundant
                merged_constraints = ext_const or ""
                if constraints and constraints not in merged_constraints:
                    if merged_constraints:
                        merged_constraints += "; " + constraints
                    else:
                        merged_constraints = constraints

                cursor.execute("""
                    UPDATE architecture_memory
                    SET purpose = ?, dependencies = ?, constraints = ?, updated_at = ?
                    WHERE module = ?
                """, (merged_purpose, merged_deps, merged_constraints, updated_at, module))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO architecture_memory (module, purpose, dependencies, constraints, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (module, purpose, dependencies, constraints, updated_at))
    except Exception as e:
        log_event(logger, "database.architecture.save_error", level="error", error=str(e))

def get_engineering_decisions():
    try:
        with closing(get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT decision, reason, impact, created_at FROM engineering_decisions ORDER BY id DESC")
            rows = cursor.fetchall()
            return [
                {
                    "decision": r[0],
                    "reason": r[1],
                    "impact": r[2],
                    "created_at": r[3]
                }
                for r in rows
            ]
    except Exception as e:
        log_event(logger, "database.decisions.read_error", level="error", error=str(e))
        return []

def add_engineering_decision(decision: str, reason: str, impact: str):
    created_at = utc_now_iso()
    try:
        with closing(get_connection()) as conn, write_transaction(conn=conn):
            cursor = conn.cursor()
            cursor.execute("SELECT decision, reason, impact FROM engineering_decisions")
            existing = cursor.fetchall()

            for ext_dec, ext_reason, ext_impact in existing:
                if get_similarity(decision, ext_dec) > 0.8:
                    log_event(logger, "database.decision.redundant_update", decision=ext_dec)
                    # Merge reason and impact if different
                    merged_reason = ext_reason
                    if reason and reason not in ext_reason:
                        merged_reason += " | " + reason
                    merged_impact = ext_impact or ""
                    if impact and impact not in merged_impact:
                        if merged_impact:
                            merged_impact += " | " + impact
                        else:
                            merged_impact = impact

                    cursor.execute("""
                        UPDATE engineering_decisions
                        SET reason = ?, impact = ?, created_at = ?
                        WHERE decision = ?
                    """, (merged_reason, merged_impact, created_at, ext_dec))
                    return

            cursor.execute("""
                INSERT INTO engineering_decisions (decision, reason, impact, created_at)
                VALUES (?, ?, ?, ?)
            """, (decision, reason, impact, created_at))
    except Exception as e:
        log_event(logger, "database.decision.save_error", level="error", error=str(e))

def delete_architecture_memory(module: str) -> bool:
    try:
        with closing(get_connection()) as conn, write_transaction(conn=conn):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM architecture_memory WHERE module = ?", (module,))
            return cursor.rowcount > 0
    except Exception as e:
        log_event(logger, "database.architecture.delete_error", level="error", module=module, error=str(e))
        return False

def delete_engineering_decision(decision: str) -> bool:
    try:
        with closing(get_connection()) as conn, write_transaction(conn=conn):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM engineering_decisions WHERE decision = ?", (decision,))
            return cursor.rowcount > 0
    except Exception as e:
        log_event(logger, "database.decision.delete_error", level="error", decision=decision, error=str(e))
        return False
