from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple

from .condensation import SymbolCondensationDAG
from .graph import SymbolDependencyGraph
from .models import SymbolEdge, SymbolEdgeType, SymbolKind, SymbolNode, SymbolSCC


class SymbolSQLiteStorage:
    """Persistent, lazy-loadable storage backend for fine-grained symbol dependency graphs."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables according to Phase 60 specifications."""
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS symbols (
                    symbol_id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    module_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    qualified_name TEXT NOT NULL,
                    language TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    exported INTEGER NOT NULL,
                    imported INTEGER NOT NULL,
                    line INTEGER NOT NULL,
                    column INTEGER NOT NULL,
                    visibility TEXT NOT NULL,
                    signature_hash TEXT,
                    body_hash TEXT,
                    state_hash TEXT,
                    provenance_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_id);

                CREATE TABLE IF NOT EXISTS symbol_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_symbol TEXT NOT NULL,
                    target_symbol TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    provenance_json TEXT,
                    location_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_edges_source ON symbol_edges(source_symbol);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON symbol_edges(target_symbol);

                CREATE TABLE IF NOT EXISTS symbol_sccs (
                    scc_id TEXT PRIMARY KEY,
                    size INTEGER NOT NULL,
                    density REAL NOT NULL,
                    is_cycle INTEGER NOT NULL,
                    state_hash TEXT NOT NULL,
                    languages_json TEXT,
                    services_json TEXT
                );

                CREATE TABLE IF NOT EXISTS symbol_scc_members (
                    scc_id TEXT NOT NULL,
                    symbol_id TEXT NOT NULL,
                    PRIMARY KEY(scc_id, symbol_id)
                );

                CREATE INDEX IF NOT EXISTS idx_scc_members_sym ON symbol_scc_members(symbol_id);

                CREATE TABLE IF NOT EXISTS symbol_condensation_edges (
                    source_scc TEXT NOT NULL,
                    target_scc TEXT NOT NULL,
                    PRIMARY KEY(source_scc, target_scc)
                );

                CREATE TABLE IF NOT EXISTS symbol_coupling (
                    scc_id TEXT PRIMARY KEY,
                    afferent INTEGER NOT NULL,
                    efferent INTEGER NOT NULL,
                    instability REAL NOT NULL,
                    cohesion REAL NOT NULL,
                    barrel_reexports INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS symbol_revisions (
                    revision INTEGER PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    trigger_event TEXT NOT NULL,
                    details_json TEXT
                );
            """)

    def save_graph(
        self,
        graph: SymbolDependencyGraph,
        sccs: List[SymbolSCC],
        dag: SymbolCondensationDAG,
        revision: int = 1,
        trigger_event: str = "INITIAL_SCAN",
    ) -> None:
        """Persist symbols, edges, SCCs, and DAG meta-edges in a single transaction."""
        with self.conn:
            # 1. Save symbols
            sym_tuples = [
                (
                    s.symbol_id,
                    s.file_id,
                    s.module_id,
                    s.name,
                    s.qualified_name,
                    s.language,
                    s.kind.value if isinstance(s.kind, SymbolKind) else str(s.kind),
                    1 if s.exported else 0,
                    1 if s.imported else 0,
                    s.line,
                    s.column,
                    s.visibility,
                    s.signature_hash,
                    s.body_hash,
                    s.state_hash,
                    json.dumps(s.provenance),
                )
                for s in graph.nodes.values()
            ]
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO symbols VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                sym_tuples,
            )

            # 2. Save edges
            edge_tuples = [
                (
                    e.source_symbol,
                    e.target_symbol,
                    e.edge_type.value if isinstance(e.edge_type, SymbolEdgeType) else str(e.edge_type),
                    e.confidence,
                    json.dumps(e.provenance),
                    json.dumps(e.source_location),
                )
                for e in graph.edges
            ]
            self.conn.executemany(
                """
                INSERT INTO symbol_edges (source_symbol, target_symbol, edge_type, confidence, provenance_json, location_json)
                VALUES (?,?,?,?,?,?)
                """,
                edge_tuples,
            )

            # 3. Save SCCs and members
            scc_tuples = []
            scc_members = []
            for scc in sccs:
                scc_tuples.append((
                    scc.scc_id,
                    scc.size,
                    scc.density,
                    1 if scc.is_cycle else 0,
                    scc.state_hash,
                    json.dumps(scc.languages),
                    json.dumps(scc.services),
                ))
                for sym_id in scc.symbols:
                    scc_members.append((scc.scc_id, sym_id))

            self.conn.executemany(
                "INSERT OR REPLACE INTO symbol_sccs VALUES (?,?,?,?,?,?,?)",
                scc_tuples,
            )
            self.conn.executemany(
                "INSERT OR REPLACE INTO symbol_scc_members VALUES (?,?)",
                scc_members,
            )

            # 4. Save Condensation DAG meta-edges
            cond_tuples = [(e["source_scc"], e["target_scc"]) for e in dag.edges]
            self.conn.executemany(
                "INSERT OR REPLACE INTO symbol_condensation_edges VALUES (?,?)",
                cond_tuples,
            )

            # 5. Record revision
            self.conn.execute(
                "INSERT OR REPLACE INTO symbol_revisions VALUES (?,?,?,?)",
                (revision, 1726589000.0, trigger_event, json.dumps({"node_count": len(graph.nodes)})),
            )

    def load_symbol(self, symbol_id: str) -> Optional[SymbolNode]:
        """Lazy-load a single symbol from SQLite."""
        cur = self.conn.execute("SELECT * FROM symbols WHERE symbol_id = ?", (symbol_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_symbol(row)

    def load_symbols_for_file(self, file_id: str) -> List[SymbolNode]:
        """Lazy-load all symbols belonging to a specific file."""
        norm_file = file_id.replace("\\", "/")
        cur = self.conn.execute("SELECT * FROM symbols WHERE file_id = ?", (norm_file,))
        return [self._row_to_symbol(r) for r in cur.fetchall()]

    def load_outgoing_edges(self, symbol_id: str) -> List[SymbolEdge]:
        """Lazy-load outgoing edges for a given symbol."""
        cur = self.conn.execute("SELECT * FROM symbol_edges WHERE source_symbol = ?", (symbol_id,))
        return [self._row_to_edge(r) for r in cur.fetchall()]

    def load_scc_for_symbol(self, symbol_id: str) -> Optional[str]:
        """Retrieve the SCC ID containing a given symbol."""
        cur = self.conn.execute("SELECT scc_id FROM symbol_scc_members WHERE symbol_id = ?", (symbol_id,))
        row = cur.fetchone()
        return row["scc_id"] if row else None

    def _row_to_symbol(self, row: sqlite3.Row) -> SymbolNode:
        return SymbolNode(
            symbol_id=row["symbol_id"],
            file_id=row["file_id"],
            module_id=row["module_id"],
            name=row["name"],
            qualified_name=row["qualified_name"],
            language=row["language"],
            kind=SymbolKind(row["kind"]),
            exported=bool(row["exported"]),
            imported=bool(row["imported"]),
            line=row["line"],
            column=row["column"],
            visibility=row["visibility"],
            signature_hash=row["signature_hash"],
            body_hash=row["body_hash"],
            provenance=json.loads(row["provenance_json"] or "{}"),
            state_hash=row["state_hash"],
        )

    def _row_to_edge(self, row: sqlite3.Row) -> SymbolEdge:
        return SymbolEdge(
            source_symbol=row["source_symbol"],
            target_symbol=row["target_symbol"],
            edge_type=SymbolEdgeType(row["edge_type"]),
            confidence=row["confidence"],
            provenance=json.loads(row["provenance_json"] or "{}"),
            source_location=json.loads(row["location_json"] or "{}"),
        )

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
