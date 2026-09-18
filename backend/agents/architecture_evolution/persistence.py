"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: persistence.py
Relational SQLite and JSON state fabric persistence for architectural snapshots,
problems, alternatives, migrations, simulations, and governance records.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .models import (
    ArchitectureAlternative,
    ArchitectureConstraint,
    ArchitectureGovernanceDecision,
    ArchitectureMigrationPlan,
    ArchitectureProblem,
    ArchitectureSnapshot,
    SimulationResult,
)


class ArchitecturePersistenceStore:
    """Manages SQLite storage for all architectural evolution entities."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        if db_path == ":memory:":
            self._connection = sqlite3.connect(":memory:", check_same_thread=False)
            self._connection.row_factory = sqlite3.Row
        else:
            self._connection = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    snapshot_hash TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS problems (
                    problem_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alternatives (
                    alternative_id TEXT PRIMARY KEY,
                    problem_id TEXT NOT NULL,
                    alternative_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migration_plans (
                    plan_id TEXT PRIMARY KEY,
                    alternative_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS simulations (
                    alternative_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS governance_decisions (
                    decision_id TEXT PRIMARY KEY,
                    problem_id TEXT NOT NULL,
                    alternative_id TEXT,
                    state TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()

    def save_snapshot(self, snapshot: ArchitectureSnapshot) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?)",
                (
                    snapshot.snapshot_id,
                    snapshot.snapshot_hash,
                    snapshot.source,
                    json.dumps(snapshot.to_dict()),
                    snapshot.timestamp,
                ),
            )
            conn.commit()

    def save_problem(self, problem: ArchitectureProblem) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO problems VALUES (?, ?, ?, ?, ?, ?)",
                (
                    problem.problem_id,
                    problem.category.value,
                    problem.severity.value,
                    problem.status.value,
                    json.dumps(problem.to_dict()),
                    time.time(),
                ),
            )
            conn.commit()

    def save_alternative(self, alternative: ArchitectureAlternative) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO alternatives VALUES (?, ?, ?, ?, ?, ?)",
                (
                    alternative.alternative_id,
                    alternative.problem_id,
                    alternative.alternative_type.value,
                    alternative.title,
                    json.dumps(alternative.to_dict()),
                    time.time(),
                ),
            )
            conn.commit()

    def save_migration_plan(self, plan: ArchitectureMigrationPlan) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO migration_plans VALUES (?, ?, ?, ?)",
                (
                    plan.plan_id,
                    plan.alternative_id,
                    json.dumps(plan.to_dict()),
                    time.time(),
                ),
            )
            conn.commit()

    def save_simulation(self, sim: SimulationResult) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO simulations VALUES (?, ?, ?, ?)",
                (
                    sim.alternative_id,
                    sim.status.value,
                    json.dumps(sim.to_dict()),
                    time.time(),
                ),
            )
            conn.commit()

    def save_governance_decision(self, decision: ArchitectureGovernanceDecision) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO governance_decisions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    decision.decision_id,
                    decision.problem_id,
                    decision.alternative_id,
                    decision.state.value,
                    json.dumps(decision.to_dict()),
                    decision.timestamp,
                ),
            )
            conn.commit()

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.cursor().execute("SELECT payload FROM snapshots WHERE snapshot_id = ?", (snapshot_id,)).fetchone()
            return json.loads(row["payload"]) if row else None

    def get_all_problems(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.cursor().execute("SELECT payload FROM problems").fetchall()
            return [json.loads(r["payload"]) for r in rows]

    def get_all_governance_decisions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.cursor().execute("SELECT payload FROM governance_decisions").fetchall()
            return [json.loads(r["payload"]) for r in rows]
