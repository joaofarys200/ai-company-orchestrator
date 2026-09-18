"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: persistence.py
SQLite-based persistence for verification runs, changes, plans, tests, executions,
coverage, regressions, flaky signals, evidence, and decisions.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .models import (
    BaselineSnapshot,
    ChangeSet,
    CoverageVector,
    FlakyAnalysisResult,
    RegressionComparisonResult,
    SelectedTestItem,
    TestSelectionPlan,
    VerificationDecision,
    VerificationSurface,
)
from .planner import VerificationPlan


class VerificationPersistenceStore:
    """Persistent storage for Continuous Verification records using SQLite."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            data_dir = os.path.join(os.getcwd(), "backend", "data")
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, "continuous_verification.db")
        else:
            self.db_path = db_path
            if db_path != ":memory:":
                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self._mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS verification_runs (
                    run_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    policy TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verification_changes (
                    change_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    changes_json TEXT NOT NULL,
                    deterministic_hash TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verification_plans (
                    plan_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    surface_json TEXT NOT NULL,
                    policy_json TEXT NOT NULL,
                    verification_required INTEGER NOT NULL,
                    status_signal TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verification_selected_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    is_synthesized INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verification_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS verification_coverage (
                    run_id TEXT PRIMARY KEY,
                    coverage_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verification_regressions (
                    run_id TEXT PRIMARY KEY,
                    classification TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verification_flaky_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    test_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    review_required INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verification_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    data_hash TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS verification_decisions (
                    decision_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    decision_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                );
            """)

    def record_run(self, run_id: str, state: str, policy: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO verification_runs (run_id, state, timestamp, policy) VALUES (?, ?, ?, ?)",
                (run_id, state, time.time(), policy),
            )

    def record_change_set(self, run_id: str, change_set: ChangeSet) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO verification_changes (change_id, run_id, changes_json, deterministic_hash, timestamp) VALUES (?, ?, ?, ?, ?)",
                (change_set.id, run_id, json.dumps(change_set.to_dict()), change_set.deterministic_hash(), change_set.timestamp),
            )

    def record_plan(self, run_id: str, plan: VerificationPlan) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO verification_plans (plan_id, run_id, surface_json, policy_json, verification_required, status_signal, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    plan.plan_id,
                    run_id,
                    json.dumps(plan.surface.to_dict()),
                    json.dumps(plan.policy.to_dict()),
                    1 if plan.verification_required else 0,
                    plan.status_signal,
                    plan.created_at,
                ),
            )

    def record_selected_tests(self, run_id: str, plan: TestSelectionPlan) -> None:
        with self._get_connection() as conn:
            for item in plan.selected:
                conn.execute(
                    "INSERT INTO verification_selected_tests (run_id, test_id, priority, reason, is_synthesized) VALUES (?, ?, ?, ?, ?)",
                    (run_id, item.test_id, int(item.priority), item.reason, 1 if item.is_synthesized else 0),
                )

    def record_coverage(self, run_id: str, coverage: CoverageVector) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO verification_coverage (run_id, coverage_json, timestamp) VALUES (?, ?, ?)",
                (run_id, json.dumps(coverage.to_dict()), time.time()),
            )

    def record_regression(self, run_id: str, regression: RegressionComparisonResult) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO verification_regressions (run_id, classification, details_json, timestamp) VALUES (?, ?, ?, ?)",
                (run_id, regression.classification.value, json.dumps(regression.to_dict()), time.time()),
            )

    def record_flaky(self, run_id: str, flaky_result: FlakyAnalysisResult) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO verification_flaky_signals (run_id, test_id, status, attempts, review_required) VALUES (?, ?, ?, ?, ?)",
                (run_id, flaky_result.test_id, flaky_result.status.value, flaky_result.attempts, 1 if flaky_result.review_required else 0),
            )

    def record_evidence(self, run_id: str, stage: str, data_hash: str, details: Dict[str, Any]) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO verification_evidence (run_id, stage, data_hash, details_json, timestamp) VALUES (?, ?, ?, ?, ?)",
                (run_id, stage, data_hash, json.dumps(details, default=str), time.time()),
            )

    def record_decision(self, run_id: str, decision: VerificationDecision) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO verification_decisions (decision_id, run_id, outcome, confidence, decision_json, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    decision.decision_id,
                    run_id,
                    decision.outcome.value if hasattr(decision.outcome, "value") else str(decision.outcome),
                    decision.confidence,
                    json.dumps(decision.to_dict()),
                    decision.timestamp,
                ),
            )

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT decision_json FROM verification_decisions WHERE decision_id = ?", (decision_id,)).fetchone()
            if row:
                return json.loads(row["decision_json"])
            return None
