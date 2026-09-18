"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: persistence.py
SQLite-backed persistence for intents, claims, conflicts, arbitrations, merges,
rebases, and provenance records.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .models import (
    AgentConflict,
    AgentEngineeringIntent,
    ArbitrationDecision,
    MergeResult,
    ProvenanceRecord,
    RebaseResult,
    ResourceClaim,
)


class CoordinationPersistenceStore:
    """Persists multi-agent coordination state, intents, claims, and arbitrations to SQLite."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._connection = sqlite3.connect(":memory:")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS intents (
                        intent_id TEXT PRIMARY KEY,
                        agent_id TEXT,
                        mission_id TEXT,
                        state TEXT,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS claims (
                        claim_id TEXT PRIMARY KEY,
                        agent_id TEXT,
                        intent_id TEXT,
                        resource_id TEXT,
                        claim_type TEXT,
                        is_active INTEGER,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conflicts (
                        conflict_id TEXT PRIMARY KEY,
                        intent_a TEXT,
                        intent_b TEXT,
                        conflict_type TEXT,
                        severity TEXT,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS arbitrations (
                        decision_id TEXT PRIMARY KEY,
                        conflict_id TEXT,
                        resolution TEXT,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS merges (
                        merge_id TEXT PRIMARY KEY,
                        success INTEGER,
                        base_snapshot TEXT,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS provenance (
                        record_id TEXT PRIMARY KEY,
                        agent_id TEXT,
                        intent_id TEXT,
                        record_hash TEXT,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
        finally:
            if self._connection is None:
                conn.close()

    def save_intent(self, intent: AgentEngineeringIntent) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO intents (intent_id, agent_id, mission_id, state, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    intent.intent_id,
                    intent.agent_id,
                    intent.mission_id,
                    intent.state.value if hasattr(intent.state, "value") else str(intent.state),
                    json.dumps(intent.to_dict()),
                    intent.timestamp,
                ))
        finally:
            if self._connection is None:
                conn.close()

    def save_claim(self, claim: ResourceClaim) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO claims (claim_id, agent_id, intent_id, resource_id, claim_type, is_active, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    claim.claim_id,
                    claim.agent_id,
                    claim.intent_id,
                    claim.resource_id,
                    claim.claim_type.value if hasattr(claim.claim_type, "value") else str(claim.claim_type),
                    1 if claim.is_active else 0,
                    json.dumps(claim.to_dict()),
                    claim.granted_at,
                ))
        finally:
            if self._connection is None:
                conn.close()

    def save_conflict(self, conflict: AgentConflict) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO conflicts (conflict_id, intent_a, intent_b, conflict_type, severity, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    conflict.conflict_id,
                    conflict.intent_a,
                    conflict.intent_b,
                    conflict.conflict_type.value if hasattr(conflict.conflict_type, "value") else str(conflict.conflict_type),
                    conflict.severity,
                    json.dumps(conflict.to_dict()),
                    conflict.timestamp,
                ))
        finally:
            if self._connection is None:
                conn.close()

    def save_arbitration(self, decision: ArbitrationDecision) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO arbitrations (decision_id, conflict_id, resolution, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    decision.decision_id,
                    decision.conflict_id,
                    decision.resolution.value if hasattr(decision.resolution, "value") else str(decision.resolution),
                    json.dumps(decision.to_dict()),
                    decision.timestamp,
                ))
        finally:
            if self._connection is None:
                conn.close()

    def save_merge(self, result: MergeResult) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO merges (merge_id, success, base_snapshot, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    result.merge_id,
                    1 if result.success else 0,
                    result.base_snapshot,
                    json.dumps(result.to_dict()),
                    time.time(),
                ))
        finally:
            if self._connection is None:
                conn.close()

    def save_provenance(self, record: ProvenanceRecord) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO provenance (record_id, agent_id, intent_id, record_hash, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    record.record_id,
                    record.agent_id,
                    record.intent_id,
                    record.compute_hash(),
                    json.dumps(record.to_dict()),
                    record.timestamp,
                ))
        finally:
            if self._connection is None:
                conn.close()
