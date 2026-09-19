"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Persistence store for Phase 69 technical debt remediation.
Thread-safe SQLite persistent store with JSON serialization.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional


class RemediationStore:
    """
    Thread-safe SQLite database storing all Phase 69 audit entities:
    validations, root causes, options, plans, missions, implementations,
    quality rescans, resolutions, deferments, gaming events, rollbacks, and provenance.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS debt_validations (
                    validation_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS root_causes (
                    cause_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS remediation_options (
                    option_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    option_type TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS remediation_plans (
                    plan_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS remediation_missions (
                    mission_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS implementation_results (
                    result_id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS quality_rescans (
                    rescan_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS resolution_results (
                    resolution_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS deferments (
                    deferment_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS gaming_events (
                    event_id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    gaming_type TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS rollback_results (
                    rollback_id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    debt_id TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS provenance (
                    record_id TEXT PRIMARY KEY,
                    debt_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    data JSON NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            self._conn.commit()

    PRIMARY_KEY_MAP = {
        "debt_validations": "validation_id",
        "root_causes": "cause_id",
        "remediation_options": "option_id",
        "remediation_plans": "plan_id",
        "remediation_missions": "mission_id",
        "implementation_results": "result_id",
        "quality_rescans": "rescan_id",
        "resolution_results": "resolution_id",
        "deferments": "deferment_id",
        "gaming_events": "event_id",
        "rollback_results": "rollback_id",
        "provenance": "record_id",
    }

    def save_entity(self, table: str, primary_id: str, data: Dict[str, Any], extra_fields: Dict[str, Any]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            pk_col = self.PRIMARY_KEY_MAP.get(table, "id")
            fields = {pk_col: primary_id}
            fields.update(extra_fields)
            fields["data"] = json.dumps(data, default=str)
            fields["created_at"] = time.time()

            col_names = ", ".join(fields.keys())
            placeholders = ", ".join("?" for _ in fields)
            sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"
            cur.execute(sql, list(fields.values()))
            self._conn.commit()

    def get_all(self, table: str) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(f"SELECT data FROM {table} ORDER BY created_at ASC")
            rows = cur.fetchall()
            return [json.loads(r["data"]) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
