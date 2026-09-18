"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Persistence Engine (SQLite & JSON Store).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from backend.agents.long_horizon_missions.models import (
    LongHorizonMission,
    Milestone,
    MissionCheckpoint,
    MissionCompletionProof,
    MissionPlan,
)


class MissionPersistenceStore:
    """Provides resilient SQLite persistence for long-horizon mission lifecycles."""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                mission_id TEXT PRIMARY KEY,
                current_state TEXT,
                objective TEXT,
                data_json TEXT,
                created_at REAL,
                updated_at REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                mission_id TEXT,
                checkpoint_type TEXT,
                sha256_hash TEXT,
                data_json TEXT,
                timestamp REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS completion_proofs (
                mission_id TEXT PRIMARY KEY,
                result TEXT,
                proof_json TEXT,
                timestamp REAL
            )
        """)
        self._conn.commit()

    def save_mission(self, mission: LongHorizonMission) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO missions (mission_id, current_state, objective, data_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                mission.mission_id,
                mission.current_state.value,
                mission.objective,
                json.dumps(mission.to_dict()),
                mission.created_at,
                mission.updated_at,
            ))
            conn.commit()

    def load_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM missions WHERE mission_id = ?", (mission_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def save_checkpoint(self, checkpoint: MissionCheckpoint) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO checkpoints (checkpoint_id, mission_id, checkpoint_type, sha256_hash, data_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                checkpoint.checkpoint_id,
                checkpoint.mission_id,
                checkpoint.checkpoint_type.value,
                checkpoint.sha256_hash,
                json.dumps(checkpoint.to_dict()),
                checkpoint.timestamp,
            ))
            conn.commit()

    def load_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["data_json"])
            return None

    def save_completion_proof(self, proof: MissionCompletionProof) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO completion_proofs (mission_id, result, proof_json, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                proof.mission_id,
                proof.result.value,
                json.dumps(proof.to_dict()),
                proof.evaluation_timestamp,
            ))
            conn.commit()
