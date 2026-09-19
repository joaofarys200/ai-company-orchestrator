"""
Release Readiness Persistence Module
Phase 70 — Autonomous Release Readiness & Production Governance

Thread-safe SQLite persistence layer storing candidates, baselines,
plans, human review tickets, and release decisions.
"""

from __future__ import annotations
import sqlite3
import json
import threading
from typing import Dict, Any, List, Optional
from .models import ReleaseCandidate, ReleaseBaseline, ReleasePlan, ReleaseGateDecision, HumanReviewTicket


class ReleaseReadinessStore:
    """Thread-safe SQLite store for release governance artifacts."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS release_candidates (
                    release_id TEXT PRIMARY KEY,
                    mission_id TEXT,
                    commit_sha TEXT,
                    workspace_snapshot TEXT,
                    version TEXT,
                    environment TEXT,
                    state TEXT,
                    created_at TEXT,
                    payload_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS release_baselines (
                    baseline_id TEXT PRIMARY KEY,
                    immutable_hash TEXT,
                    captured_at TEXT,
                    payload_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS release_plans (
                    plan_id TEXT PRIMARY KEY,
                    candidate_id TEXT,
                    status TEXT,
                    created_at TEXT,
                    payload_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS human_review_tickets (
                    ticket_id TEXT PRIMARY KEY,
                    candidate_id TEXT,
                    status TEXT,
                    created_at TEXT,
                    payload_json TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS release_gate_decisions (
                    decision_id TEXT PRIMARY KEY,
                    candidate_id TEXT,
                    state TEXT,
                    allowed_to_release INTEGER,
                    provenance_hash TEXT,
                    evaluated_at TEXT,
                    payload_json TEXT
                )
            """)
            self._conn.commit()

    def save_candidate(self, candidate: ReleaseCandidate) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO release_candidates
                (release_id, mission_id, commit_sha, workspace_snapshot, version, environment, state, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                candidate.release_id,
                candidate.mission_id,
                candidate.commit_sha,
                candidate.workspace_snapshot,
                candidate.version,
                candidate.environment,
                candidate.state.value if hasattr(candidate.state, "value") else str(candidate.state),
                candidate.created_at,
                json.dumps(candidate.to_dict())
            ))
            self._conn.commit()

    def save_baseline(self, baseline: ReleaseBaseline) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO release_baselines
                (baseline_id, immutable_hash, captured_at, payload_json)
                VALUES (?, ?, ?, ?)
            """, (
                baseline.baseline_id,
                baseline.immutable_hash,
                baseline.captured_at,
                json.dumps(baseline.to_dict())
            ))
            self._conn.commit()

    def save_plan(self, plan: ReleasePlan) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO release_plans
                (plan_id, candidate_id, status, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                plan.plan_id,
                plan.candidate_id,
                plan.status,
                plan.created_at,
                json.dumps(plan.to_dict())
            ))
            self._conn.commit()

    def save_ticket(self, ticket: HumanReviewTicket) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO human_review_tickets
                (ticket_id, candidate_id, status, created_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
            """, (
                ticket.ticket_id,
                ticket.candidate_id,
                ticket.status,
                ticket.created_at,
                json.dumps(ticket.to_dict())
            ))
            self._conn.commit()

    def save_decision(self, decision: ReleaseGateDecision) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO release_gate_decisions
                (decision_id, candidate_id, state, allowed_to_release, provenance_hash, evaluated_at, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.decision_id,
                decision.candidate_id,
                decision.state.value if hasattr(decision.state, "value") else str(decision.state),
                1 if decision.allowed_to_release else 0,
                decision.provenance_hash,
                decision.evaluated_at,
                json.dumps(decision.to_dict())
            ))
            self._conn.commit()

    def get_candidate(self, release_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT payload_json FROM release_candidates WHERE release_id = ?", (release_id,))
            row = cur.fetchone()
            return json.loads(row[0]) if row else None

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT payload_json FROM release_gate_decisions WHERE decision_id = ?", (decision_id,))
            row = cur.fetchone()
            return json.loads(row[0]) if row else None

    def list_decisions(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT payload_json FROM release_gate_decisions ORDER BY evaluated_at DESC")
            return [json.loads(r[0]) for r in cur.fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
