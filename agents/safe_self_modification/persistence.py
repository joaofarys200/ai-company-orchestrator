"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: persistence.py
SQLite-backed persistence for transactions, snapshots, checkpoints, patches,
and verification ledgers. Supports persistent connection for in-memory databases.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from .models import (
    ModificationCheckpoint,
    ModificationPatch,
    ModificationTransaction,
    TransactionalSnapshot,
    TransactionState,
)


class ModificationPersistenceStore:
    """Persists transactions, snapshots, checkpoints, and verification ledger to SQLite."""

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
                    CREATE TABLE IF NOT EXISTS transactions (
                        transaction_id TEXT PRIMARY KEY,
                        governance_decision_id TEXT,
                        snapshot_id TEXT,
                        current_state TEXT,
                        plan_id TEXT,
                        data_json TEXT,
                        created_at REAL,
                        updated_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        snapshot_id TEXT PRIMARY KEY,
                        snapshot_sha256 TEXT,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        transaction_id TEXT,
                        step_id TEXT,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS verification_ledger (
                        entry_id TEXT PRIMARY KEY,
                        transaction_id TEXT,
                        evidence_hash TEXT,
                        data_json TEXT,
                        created_at REAL
                    )
                """)
        finally:
            if self._connection is None:
                conn.close()

    def save_transaction(self, tx: ModificationTransaction) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO transactions
                    (transaction_id, governance_decision_id, snapshot_id, current_state, plan_id, data_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tx.transaction_id,
                    tx.governance_decision_id,
                    tx.snapshot_id,
                    tx.current_state.value,
                    tx.plan_id,
                    json.dumps(tx.to_dict()),
                    tx.created_at,
                    tx.updated_at,
                ))
        finally:
            if self._connection is None:
                conn.close()

    def load_transaction(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT data_json FROM transactions WHERE transaction_id = ?", (transaction_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row[0])
            return None
        finally:
            if self._connection is None:
                conn.close()

    def save_snapshot(self, snapshot: TransactionalSnapshot) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO snapshots
                    (snapshot_id, snapshot_sha256, data_json, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    snapshot.snapshot_id,
                    snapshot.snapshot_sha256,
                    json.dumps(snapshot.to_dict()),
                    snapshot.created_at,
                ))
        finally:
            if self._connection is None:
                conn.close()

    def save_checkpoint(self, checkpoint: ModificationCheckpoint) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT OR REPLACE INTO checkpoints
                    (checkpoint_id, transaction_id, step_id, data_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    checkpoint.checkpoint_id,
                    checkpoint.transaction_id,
                    checkpoint.step_id,
                    json.dumps(checkpoint.to_dict()),
                    checkpoint.timestamp,
                ))
        finally:
            if self._connection is None:
                conn.close()
