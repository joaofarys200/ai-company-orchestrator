"""
JARVIS OS — Phase 68: Quality Governance Persistence
Persists:
- quality_snapshots
- quality_dimensions
- quality_deltas
- technical_debt
- debt_events
- quality_gates
- quality_trends
- quality_hotspots
- agent_quality_history
- mission_quality_history
- provenance

SQLite-backed persistent store with thread-safe connection pooling.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional


class QualityPersistenceStore:
    """
    Thread-safe SQLite persistent store for engineering quality governance artifacts.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        # Keep a single shared connection for :memory: databases to avoid table loss across calls
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS quality_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    architecture_hash TEXT,
                    contract_hash TEXT,
                    behavior_hash TEXT,
                    test_hash TEXT,
                    security_hash TEXT,
                    timestamp REAL,
                    sealed INTEGER DEFAULT 0,
                    data TEXT
                );

                CREATE TABLE IF NOT EXISTS quality_deltas (
                    delta_id TEXT PRIMARY KEY,
                    baseline_id TEXT,
                    after_id TEXT,
                    mission_id TEXT,
                    evidence_efficiency REAL,
                    timestamp REAL,
                    data TEXT
                );

                CREATE TABLE IF NOT EXISTS technical_debt (
                    debt_id TEXT PRIMARY KEY,
                    category TEXT,
                    affected_surface TEXT,
                    origin_mission TEXT,
                    severity TEXT,
                    status TEXT,
                    risk REAL,
                    recurrence_count INTEGER,
                    created_at REAL,
                    updated_at REAL,
                    data TEXT
                );

                CREATE TABLE IF NOT EXISTS debt_events (
                    event_id TEXT PRIMARY KEY,
                    debt_id TEXT,
                    event_type TEXT,
                    timestamp REAL,
                    details TEXT
                );

                CREATE TABLE IF NOT EXISTS quality_gates (
                    gate_id TEXT PRIMARY KEY,
                    mission_id TEXT,
                    decision TEXT,
                    scope TEXT,
                    uncertainty REAL,
                    timestamp REAL,
                    data TEXT
                );

                CREATE TABLE IF NOT EXISTS quality_trends (
                    trend_id TEXT PRIMARY KEY,
                    mission_id TEXT,
                    direction TEXT,
                    timestamp REAL,
                    data TEXT
                );

                CREATE TABLE IF NOT EXISTS quality_hotspots (
                    hotspot_id TEXT PRIMARY KEY,
                    entity_type TEXT,
                    entity_name TEXT,
                    risk_weight REAL,
                    data TEXT
                );

                CREATE TABLE IF NOT EXISTS agent_quality_history (
                    record_id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    mission_id TEXT,
                    regressions_count INTEGER,
                    timestamp REAL,
                    data TEXT
                );

                CREATE TABLE IF NOT EXISTS mission_quality_history (
                    mission_id TEXT PRIMARY KEY,
                    baseline_id TEXT,
                    after_id TEXT,
                    gate_decision TEXT,
                    unresolved_debt_count INTEGER,
                    quality_improved INTEGER,
                    timestamp REAL,
                    data TEXT
                );

                CREATE TABLE IF NOT EXISTS provenance (
                    record_id TEXT PRIMARY KEY,
                    entity_id TEXT,
                    actor TEXT,
                    action TEXT,
                    signature TEXT,
                    timestamp REAL,
                    data TEXT
                );
            """)
            self._conn.commit()

    def save_snapshot(self, snapshot_dict: Dict[str, Any]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO quality_snapshots
                (snapshot_id, mission_id, architecture_hash, contract_hash, behavior_hash, test_hash, security_hash, timestamp, sealed, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot_dict["snapshot_id"],
                snapshot_dict["mission_id"],
                snapshot_dict.get("architecture_hash", ""),
                snapshot_dict.get("contract_hash", ""),
                snapshot_dict.get("behavior_hash", ""),
                snapshot_dict.get("test_hash", ""),
                snapshot_dict.get("security_hash", ""),
                snapshot_dict.get("timestamp", 0.0),
                1 if snapshot_dict.get("sealed") else 0,
                json.dumps(snapshot_dict),
            ))
            self._conn.commit()

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data FROM quality_snapshots WHERE snapshot_id = ?", (snapshot_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row["data"])
            return None

    def save_delta(self, delta_dict: Dict[str, Any]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            delta_id = f"delta_{delta_dict['baseline_snapshot_id']}_{delta_dict['after_snapshot_id']}"
            cur.execute("""
                INSERT OR REPLACE INTO quality_deltas
                (delta_id, baseline_id, after_id, mission_id, evidence_efficiency, timestamp, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                delta_id,
                delta_dict["baseline_snapshot_id"],
                delta_dict["after_snapshot_id"],
                delta_dict["mission_id"],
                delta_dict.get("evidence_efficiency", 1.0),
                delta_dict.get("timestamp", 0.0),
                json.dumps(delta_dict),
            ))
            self._conn.commit()

    def save_debt_item(self, debt_dict: Dict[str, Any]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO technical_debt
                (debt_id, category, affected_surface, origin_mission, severity, status, risk, recurrence_count, created_at, updated_at, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                debt_dict["debt_id"],
                debt_dict["category"],
                debt_dict["affected_surface"],
                debt_dict["origin_mission"],
                debt_dict["severity"],
                debt_dict["status"],
                debt_dict.get("risk", 0.5),
                debt_dict.get("recurrence_count", 1),
                debt_dict.get("created_at", 0.0),
                debt_dict.get("updated_at", 0.0),
                json.dumps(debt_dict),
            ))
            self._conn.commit()

    def list_debt_items(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data FROM technical_debt ORDER BY risk DESC")
            return [json.loads(r["data"]) for r in cur.fetchall()]

    def save_gate_decision(self, gate_id: str, mission_id: str, decision_dict: Dict[str, Any]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO quality_gates
                (gate_id, mission_id, decision, scope, uncertainty, timestamp, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                gate_id,
                mission_id,
                decision_dict["decision"],
                decision_dict.get("scope", "global"),
                decision_dict.get("uncertainty", 0.0),
                decision_dict.get("timestamp", 0.0),
                json.dumps(decision_dict),
            ))
            self._conn.commit()

    def save_hotspot(self, hotspot_dict: Dict[str, Any]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            h_id = f"hs_{hotspot_dict['entity_type']}_{hotspot_dict['entity_name']}"
            cur.execute("""
                INSERT OR REPLACE INTO quality_hotspots
                (hotspot_id, entity_type, entity_name, risk_weight, data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                h_id,
                hotspot_dict["entity_type"],
                hotspot_dict["entity_name"],
                hotspot_dict.get("risk_weight", 0.0),
                json.dumps(hotspot_dict),
            ))
            self._conn.commit()

    def list_hotspots(self) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT data FROM quality_hotspots ORDER BY risk_weight DESC")
            return [json.loads(r["data"]) for r in cur.fetchall()]

    def save_mission_quality(self, mission_record: Dict[str, Any]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO mission_quality_history
                (mission_id, baseline_id, after_id, gate_decision, unresolved_debt_count, quality_improved, timestamp, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mission_record["mission_id"],
                mission_record["baseline_id"],
                mission_record["after_id"],
                mission_record["gate_decision"],
                mission_record.get("unresolved_debt_count", 0),
                1 if mission_record.get("quality_improved") else 0,
                mission_record.get("timestamp", 0.0),
                json.dumps(mission_record),
            ))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
