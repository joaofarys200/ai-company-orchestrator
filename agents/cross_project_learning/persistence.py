"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: persistence.py
SQLite persistence for cross-project engineering learning and verification governance.
Maintains relational tables for fingerprints, knowledge items, transfer decisions,
validation results, conflicts, freshness records, and harm telemetry.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ConflictRecord,
    EngineeringKnowledgeItem,
    FeedbackOutcome,
    HarmEvent,
    KnowledgeCategory,
    KnowledgeProvenance,
    KnowledgeState,
    KnowledgeTransferDecision,
    LocalValidationResult,
    ProjectFingerprint,
    TransferDecisionState,
)


class CrossProjectLearningStore:
    """SQLite-backed persistent store for cross-project engineering learning."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._persistent_mem_conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._persistent_mem_conn = sqlite3.connect(":memory:")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._persistent_mem_conn is not None:
            return self._persistent_mem_conn
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # 1. Projects & Fingerprints
            cur.execute("""
                CREATE TABLE IF NOT EXISTS project_fingerprints (
                    project_id TEXT PRIMARY KEY,
                    fingerprint_hash TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

            # 2. Knowledge Items
            cur.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    knowledge_id TEXT PRIMARY KEY,
                    source_project_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    state TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL
                )
            """)

            # 3. Transfer Decisions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transfer_decisions (
                    decision_id TEXT PRIMARY KEY,
                    target_project_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    rationale TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)

            # 4. Local Validation Results
            cur.execute("""
                CREATE TABLE IF NOT EXISTS local_validation_results (
                    validation_id TEXT PRIMARY KEY,
                    transfer_decision_id TEXT NOT NULL,
                    target_project_id TEXT NOT NULL,
                    validated INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    harm_detected INTEGER NOT NULL,
                    data_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)

            # 5. Conflicts
            cur.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    item_a_id TEXT NOT NULL,
                    item_b_id TEXT NOT NULL,
                    conflict_type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    resolution_status TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)

            # 6. Harm Telemetry
            cur.execute("""
                CREATE TABLE IF NOT EXISTS harm_events (
                    harm_id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    target_project_id TEXT NOT NULL,
                    harm_type TEXT NOT NULL,
                    details TEXT NOT NULL,
                    penalty_applied REAL NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)

            conn.commit()
        finally:
            if self._persistent_mem_conn is None:
                conn.close()

    def save_fingerprint(self, fp: ProjectFingerprint) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO project_fingerprints
                (project_id, fingerprint_hash, data_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (fp.project_id, fp.fingerprint_hash, json.dumps(fp.to_dict()), fp.created_at),
            )
            conn.commit()
        finally:
            if self._persistent_mem_conn is None:
                conn.close()

    def get_fingerprint(self, project_id: str) -> Optional[ProjectFingerprint]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT data_json FROM project_fingerprints WHERE project_id = ?", (project_id,))
            row = cur.fetchone()
            if not row:
                return None
            return ProjectFingerprint.from_dict(json.loads(row[0]))
        finally:
            if self._persistent_mem_conn is None:
                conn.close()

    def save_knowledge_item(self, item: EngineeringKnowledgeItem) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO knowledge_items
                (knowledge_id, source_project_id, category, state, confidence, data_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.knowledge_id,
                    item.source_project_id,
                    item.category.value,
                    item.state.value,
                    item.confidence,
                    json.dumps(item.to_dict()),
                    item.created_at,
                    item.expires_at,
                ),
            )
            conn.commit()
        finally:
            if self._persistent_mem_conn is None:
                conn.close()

    def get_knowledge_item(self, knowledge_id: str) -> Optional[EngineeringKnowledgeItem]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT data_json FROM knowledge_items WHERE knowledge_id = ?", (knowledge_id,))
            row = cur.fetchone()
            if not row:
                return None
            return EngineeringKnowledgeItem.from_dict(json.loads(row[0]))
        finally:
            if self._persistent_mem_conn is None:
                conn.close()

    def save_transfer_decision(self, dec: KnowledgeTransferDecision) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO transfer_decisions
                (decision_id, target_project_id, item_id, state, confidence, rationale, data_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dec.decision_id,
                    dec.target_project_id,
                    dec.item_id,
                    dec.state.value,
                    dec.confidence,
                    dec.rationale,
                    json.dumps(dec.to_dict()),
                    dec.timestamp,
                ),
            )
            conn.commit()
        finally:
            if self._persistent_mem_conn is None:
                conn.close()

    def save_validation_result(self, val: LocalValidationResult) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO local_validation_results
                (validation_id, transfer_decision_id, target_project_id, validated, outcome, harm_detected, data_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    val.validation_id,
                    val.transfer_decision_id,
                    val.target_project_id,
                    1 if val.validated else 0,
                    val.outcome.value,
                    1 if val.harm_detected else 0,
                    json.dumps(val.to_dict()),
                    val.timestamp,
                ),
            )
            conn.commit()
        finally:
            if self._persistent_mem_conn is None:
                conn.close()

    def save_conflict(self, conf: ConflictRecord) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO knowledge_conflicts
                (conflict_id, item_a_id, item_b_id, conflict_type, reason, resolution_status, data_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conf.conflict_id,
                    conf.pair_item_ids[0],
                    conf.pair_item_ids[1],
                    conf.conflict_type,
                    conf.reason,
                    conf.resolution_status,
                    json.dumps(conf.to_dict()),
                    conf.timestamp,
                ),
            )
            conn.commit()
        finally:
            if self._persistent_mem_conn is None:
                conn.close()

    def save_harm_event(self, harm: HarmEvent) -> None:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO harm_events
                (harm_id, knowledge_id, target_project_id, harm_type, details, penalty_applied, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    harm.harm_id,
                    harm.knowledge_id,
                    harm.target_project_id,
                    harm.harm_type,
                    harm.details,
                    harm.penalty_applied,
                    harm.timestamp,
                ),
            )
            conn.commit()
        finally:
            if self._persistent_mem_conn is None:
                conn.close()
