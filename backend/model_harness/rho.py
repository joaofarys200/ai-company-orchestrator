from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

from backend.model_harness.contracts import ModelRequest, ModelResponse, ModelResponseStatus
from backend.security.sanitizer import SensitiveDataSanitizer

DB_PATH = Path("config/rho.sqlite")


class RetrospectiveEngine:
    """
    RHO (Retrospective Heuristic Optimization) Engine.
    Records trajectory outcomes in SQLite and dynamically synthesizes
    compounding self-healing rules when validation failures repeat 2+ times.
    Enforces deduplication and top-5 bounded rule retrieval.
    """

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
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
                    created_at REAL NOT NULL,
                    UNIQUE(task_profile, failure_trigger)
                )
                """
            )
            conn.commit()

    def record_trajectory(self, request: ModelRequest, response: ModelResponse) -> None:
        """Stores trajectory record and triggers RHO rule synthesis if failures repeat."""
        failure_reason = ""
        if response.validation and response.validation.issues:
            failure_reason = "; ".join(f"{i.stage}:{i.message}" for i in response.validation.issues)
        elif response.errors:
            failure_reason = "; ".join(f"{e.get('stage')}:{e.get('message')}" for e in response.errors)

        # Apply Universal Secret Sanitizer before database insertion
        failure_reason = SensitiveDataSanitizer.sanitize_text(failure_reason)

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO model_trajectories 
                (request_id, task_profile, fingerprint, status, attempts_count, failure_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id,
                    request.task_profile,
                    request.fingerprint(),
                    response.status.value,
                    len(response.recovery) + 1 if response.recovery else 1,
                    failure_reason,
                    time.time(),
                ),
            )
            conn.commit()

        if response.status != ModelResponseStatus.SUCCEEDED and failure_reason:
            self._evaluate_and_synthesize_rules(request.task_profile, failure_reason)

    def _evaluate_and_synthesize_rules(self, task_profile: str, failure_trigger: str) -> None:
        """Synthesizes compounding heuristic rules with deduplication and frequency tracking."""
        sanitized_trigger = SensitiveDataSanitizer.sanitize_text(failure_trigger)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) FROM model_trajectories 
                WHERE task_profile = ? AND failure_reason = ? AND status != 'SUCCEEDED'
                """,
                (task_profile, sanitized_trigger),
            )
            count = cur.fetchone()[0]

            if count >= 2:
                rule_text = f"EVITAR FALHA EM {task_profile}: {sanitized_trigger}. Assegurar estrita conformidade de esquema e argumentos válidos."
                cur.execute(
                    """
                    INSERT INTO rho_compounding_rules (task_profile, rule_text, failure_trigger, occurrences, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(task_profile, failure_trigger) DO UPDATE SET
                        occurrences = excluded.occurrences,
                        created_at = excluded.created_at
                    """,
                    (task_profile, rule_text, sanitized_trigger, count, time.time()),
                )
                conn.commit()

    def get_compounding_rules(self, task_profile: str) -> list[str]:
        """Retrieves learned compounding rules for a specific task profile, strictly bounded to top 5."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT rule_text FROM rho_compounding_rules 
                WHERE task_profile = ? 
                ORDER BY occurrences DESC, created_at DESC LIMIT 5
                """,
                (task_profile,),
            )
            return [row[0] for row in cur.fetchall()]


__all__ = ["RetrospectiveEngine"]
