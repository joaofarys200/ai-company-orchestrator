from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from .models import (
    CondensationDAG,
    CondensationDAGNode,
    SCCCouplingMetrics,
    StronglyConnectedComponent,
)


class SqliteSCCStorage:
    """Persistent storage adapter for SCCs, condensation DAGs, and coupling metrics."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            if self.db_path != ":memory:":
                cur.execute("PRAGMA journal_mode = WAL;")
            cur.execute("PRAGMA synchronous = NORMAL;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sccs (
                    scc_id TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    density REAL NOT NULL,
                    is_cycle INTEGER NOT NULL,
                    state_hash TEXT NOT NULL,
                    entry_points_json TEXT NOT NULL,
                    exit_points_json TEXT NOT NULL,
                    services_json TEXT NOT NULL,
                    languages_json TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS scc_members (
                    node_id TEXT PRIMARY KEY,
                    scc_id TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS condensation_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_scc TEXT NOT NULL,
                    target_scc TEXT NOT NULL,
                    raw_edge_count INTEGER NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS coupling_metrics (
                    scc_id TEXT PRIMARY KEY,
                    coupling_score REAL NOT NULL,
                    fan_in INTEGER NOT NULL,
                    fan_out INTEGER NOT NULL,
                    cross_service INTEGER NOT NULL,
                    cross_language INTEGER NOT NULL,
                    cycle_depth INTEGER NOT NULL,
                    explanation_json TEXT NOT NULL
                )
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_scc_members_scc ON scc_members(scc_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_cdag_edges_src ON condensation_edges(source_scc);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_cdag_edges_tgt ON condensation_edges(target_scc);")
            self._conn.commit()

    def save_sccs(self, sccs: List[StronglyConnectedComponent]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            for scc in sccs:
                cur.execute("""
                    INSERT OR REPLACE INTO sccs (
                        scc_id, size, density, is_cycle, state_hash,
                        entry_points_json, exit_points_json, services_json, languages_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scc.scc_id,
                    scc.size,
                    scc.density,
                    1 if scc.is_cycle else 0,
                    scc.state_hash,
                    json.dumps(scc.entry_points),
                    json.dumps(scc.exit_points),
                    json.dumps(scc.services),
                    json.dumps(scc.languages),
                ))
                for node in scc.nodes:
                    cur.execute("INSERT OR REPLACE INTO scc_members (node_id, scc_id) VALUES (?, ?)", (node, scc.scc_id))
            self._conn.commit()

    def save_dag(self, dag: CondensationDAG) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("DELETE FROM condensation_edges")
            for edge in dag.edges:
                cur.execute("""
                    INSERT INTO condensation_edges (source_scc, target_scc, raw_edge_count)
                    VALUES (?, ?, ?)
                """, (
                    edge["source_scc"],
                    edge["target_scc"],
                    edge.get("raw_edge_count", 1),
                ))
            self._conn.commit()

    def save_coupling(self, metrics: List[SCCCouplingMetrics]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            for m in metrics:
                cur.execute("""
                    INSERT OR REPLACE INTO coupling_metrics (
                        scc_id, coupling_score, fan_in, fan_out,
                        cross_service, cross_language, cycle_depth, explanation_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    m.scc_id,
                    m.coupling_score,
                    m.fan_in,
                    m.fan_out,
                    m.cross_service_edges,
                    m.cross_language_edges,
                    m.cycle_depth,
                    json.dumps(m.components_explanation),
                ))
            self._conn.commit()

    def get_scc_for_node(self, node_id: str) -> Optional[str]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT scc_id FROM scc_members WHERE node_id = ?", (node_id,))
            row = cur.fetchone()
            return row["scc_id"] if row else None

    def load_sccs(self) -> List[StronglyConnectedComponent]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM sccs ORDER BY scc_id")
            rows = cur.fetchall()
            sccs: List[StronglyConnectedComponent] = []
            for r in rows:
                sid = r["scc_id"]
                cur.execute("SELECT node_id FROM scc_members WHERE scc_id = ? ORDER BY node_id", (sid,))
                members = [m["node_id"] for m in cur.fetchall()]
                scc = StronglyConnectedComponent(
                    scc_id=sid,
                    nodes=members,
                    size=r["size"],
                    density=r["density"],
                    is_cycle=bool(r["is_cycle"]),
                    state_hash=r["state_hash"],
                    entry_points=json.loads(r["entry_points_json"]),
                    exit_points=json.loads(r["exit_points_json"]),
                    services=json.loads(r["services_json"]),
                    languages=json.loads(r["languages_json"]),
                )
                sccs.append(scc)
            return sccs

    def load_dag(self) -> CondensationDAG:
        from .condensation import GraphCondenser
        sccs = self.load_sccs()
        return GraphCondenser.condense(sccs)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

