from __future__ import annotations

from contextlib import closing
import json
import time
from dataclasses import dataclass
from pathlib import Path

from backend.model_harness.contracts import ModelRequest, ModelResponse, ModelResponseStatus
from persistence.db import (
    CANONICAL_DB_PATH,
    ensure_rho_schema,
    get_db_connection,
    write_transaction,
)


DB_PATH = CANONICAL_DB_PATH


@dataclass(frozen=True)
class TrajectoryRecord:
    request_id: str
    task_profile: str
    fingerprint: str
    status: str
    attempts_count: int
    failure_reason: str
    timestamp: float


class RetrospectiveEngine:
    """Retrospective Harness Optimization (RHO) — 2026 Paper Implementation.

    Records model execution trajectories in SQLite and automatically synthesizes
    compounding self-healing rules when validation failures repeat 2+ times.
    """

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with write_transaction(self.db_path) as conn:
            ensure_rho_schema(conn)

    def record_trajectory(self, request: ModelRequest, response: ModelResponse) -> None:
        """Stores trajectory record and triggers RHO rule synthesis if failures repeat."""
        failure_reason = ""
        if response.validation and response.validation.issues:
            failure_reason = f"{response.validation.issues[0].stage.value}:{response.validation.issues[0].code}"
        elif response.errors:
            failure_reason = str(response.errors[0].get("message", "unknown_error"))

        with write_transaction(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO model_trajectories (request_id, task_profile, fingerprint, status, attempts_count, failure_reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.request_id,
                    request.task_profile,
                    request.fingerprint(),
                    response.status.value,
                    len(response.recovery) + 1,
                    failure_reason,
                    time.time(),
                ),
            )

        if response.status != ModelResponseStatus.SUCCEEDED and failure_reason:
            self._evaluate_failure_pattern(request.task_profile, failure_reason)

    def _evaluate_failure_pattern(self, task_profile: str, failure_reason: str) -> None:
        """If 2 or more failures of the same pattern occur, synthesize a compounding rule."""
        with write_transaction(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*) FROM model_trajectories
                WHERE task_profile = ? AND failure_reason = ? AND created_at > ?
                """,
                (task_profile, failure_reason, time.time() - 3600),
            )
            count = cur.fetchone()[0]

            if count >= 2:
                rule_text = f"AUTO-RULE [RHO-{task_profile}]: Evita falha {failure_reason}. Garanta estrita conformidade com argumentos de ferramentas e formatos JSON."
                cur.execute(
                    """
                    INSERT INTO rho_compounding_rules (task_profile, rule_text, failure_trigger, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (task_profile, rule_text, failure_reason, time.time()),
                )

    def get_compounding_rules(self, task_profile: str) -> list[str]:
        """Fetches active RHO compounding rules for a task profile."""
        with closing(get_db_connection(self.db_path)) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT rule_text FROM rho_compounding_rules
                WHERE task_profile = ?
                ORDER BY id DESC LIMIT 5
                """,
                (task_profile,),
            )
            rows = cur.fetchall()
            return [row[0] for row in rows]


__all__ = ["RetrospectiveEngine", "TrajectoryRecord"]
