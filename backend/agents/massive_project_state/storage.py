from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .models import (
    ContractRecord,
    FileRecord,
    GraphEdge,
    PartitionType,
    RuntimeRecord,
    ShardStatus,
    StateShard,
    StateSnapshot,
    StateTier,
    SymbolRecord,
    TaskRecord,
)


class AbstractStateStorage(ABC):
    """Abstract contract for cold/persisted state storage."""

    @abstractmethod
    def save_shard(self, shard: StateShard) -> None:
        pass

    @abstractmethod
    def get_shard(self, shard_id: str) -> Optional[StateShard]:
        pass

    @abstractmethod
    def list_shards(self) -> List[StateShard]:
        pass

    @abstractmethod
    def save_symbol(self, symbol: SymbolRecord) -> None:
        pass

    @abstractmethod
    def get_symbol(self, symbol_id: str) -> Optional[SymbolRecord]:
        pass

    @abstractmethod
    def save_file(self, file_rec: FileRecord) -> None:
        pass

    @abstractmethod
    def get_file(self, file_path: str) -> Optional[FileRecord]:
        pass

    @abstractmethod
    def save_contract(self, contract: ContractRecord) -> None:
        pass

    @abstractmethod
    def get_contract(self, contract_id: str) -> Optional[ContractRecord]:
        pass

    @abstractmethod
    def save_task(self, task: TaskRecord) -> None:
        pass

    @abstractmethod
    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        pass

    @abstractmethod
    def save_edges(self, edges: List[GraphEdge]) -> None:
        pass

    @abstractmethod
    def get_edges(self, source: Optional[str] = None, target: Optional[str] = None) -> List[GraphEdge]:
        pass

    @abstractmethod
    def save_snapshot(self, snapshot: StateSnapshot) -> None:
        pass

    @abstractmethod
    def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class SqliteStateStorage(AbstractStateStorage):
    """High-performance SQLite WAL storage adapter for massive project state."""

    def __init__(self, db_path: str = ":memory:"):
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
            cur.execute("PRAGMA foreign_keys = ON;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS shards (
                    shard_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    partition_type TEXT NOT NULL,
                    state_hash TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    last_indexed_revision INTEGER NOT NULL,
                    dependencies_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    symbol_count INTEGER NOT NULL,
                    last_access REAL NOT NULL,
                    tier TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    symbol_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    shard_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    signature_hash TEXT NOT NULL,
                    consumers_json TEXT NOT NULL,
                    dependencies_json TEXT NOT NULL,
                    contracts_json TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    file_path TEXT PRIMARY KEY,
                    shard_id TEXT NOT NULL,
                    language TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    symbols_json TEXT NOT NULL,
                    imports_json TEXT NOT NULL,
                    exports_json TEXT NOT NULL,
                    loc INTEGER NOT NULL,
                    last_modified REAL NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS contracts (
                    contract_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    shard_id TEXT NOT NULL,
                    endpoints_json TEXT NOT NULL,
                    consumers_json TEXT NOT NULL,
                    providers_json TEXT NOT NULL,
                    schema_hash TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    affected_files_json TEXT NOT NULL,
                    contracts_json TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    weight REAL NOT NULL,
                    metadata_json TEXT NOT NULL
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    repository_state_hash TEXT NOT NULL,
                    partition_hashes_json TEXT NOT NULL,
                    index_versions_json TEXT NOT NULL,
                    graph_versions_json TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    provenance_json TEXT NOT NULL
                )
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_sym_file ON symbols(file_path);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sym_shard ON symbols(shard_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_files_shard ON files(shard_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(source);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_edges_tgt ON edges(target);")
            self._conn.commit()

    def save_shard(self, shard: StateShard) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO shards (
                    shard_id, name, partition_type, state_hash, schema_version,
                    last_indexed_revision, dependencies_json, status, file_count,
                    symbol_count, last_access, tier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                shard.shard_id,
                shard.name,
                shard.partition_type.value,
                shard.state_hash,
                shard.schema_version,
                shard.last_indexed_revision,
                json.dumps(shard.dependencies),
                shard.status.value,
                shard.file_count,
                shard.symbol_count,
                shard.last_access,
                shard.tier.value,
            ))
            self._conn.commit()

    def get_shard(self, shard_id: str) -> Optional[StateShard]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM shards WHERE shard_id = ?", (shard_id,))
            row = cur.fetchone()
            if not row:
                return None
            return StateShard(
                shard_id=row["shard_id"],
                name=row["name"],
                partition_type=PartitionType(row["partition_type"]),
                state_hash=row["state_hash"],
                schema_version=row["schema_version"],
                last_indexed_revision=row["last_indexed_revision"],
                dependencies=json.loads(row["dependencies_json"]),
                status=ShardStatus(row["status"]),
                file_count=row["file_count"],
                symbol_count=row["symbol_count"],
                last_access=row["last_access"],
                tier=StateTier(row["tier"]),
            )

    def list_shards(self) -> List[StateShard]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM shards ORDER BY name ASC")
            rows = cur.fetchall()
            return [
                StateShard(
                    shard_id=row["shard_id"],
                    name=row["name"],
                    partition_type=PartitionType(row["partition_type"]),
                    state_hash=row["state_hash"],
                    schema_version=row["schema_version"],
                    last_indexed_revision=row["last_indexed_revision"],
                    dependencies=json.loads(row["dependencies_json"]),
                    status=ShardStatus(row["status"]),
                    file_count=row["file_count"],
                    symbol_count=row["symbol_count"],
                    last_access=row["last_access"],
                    tier=StateTier(row["tier"]),
                )
                for row in rows
            ]

    def save_symbol(self, symbol: SymbolRecord) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO symbols (
                    symbol_id, name, kind, file_path, shard_id, language,
                    signature_hash, consumers_json, dependencies_json, contracts_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol.symbol_id,
                symbol.name,
                symbol.kind,
                symbol.file_path,
                symbol.shard_id,
                symbol.language,
                symbol.signature_hash,
                json.dumps(symbol.consumers),
                json.dumps(symbol.dependencies),
                json.dumps(symbol.contracts),
            ))
            self._conn.commit()

    def get_symbol(self, symbol_id: str) -> Optional[SymbolRecord]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM symbols WHERE symbol_id = ?", (symbol_id,))
            row = cur.fetchone()
            if not row:
                return None
            return SymbolRecord(
                symbol_id=row["symbol_id"],
                name=row["name"],
                kind=row["kind"],
                file_path=row["file_path"],
                shard_id=row["shard_id"],
                language=row["language"],
                signature_hash=row["signature_hash"],
                consumers=json.loads(row["consumers_json"]),
                dependencies=json.loads(row["dependencies_json"]),
                contracts=json.loads(row["contracts_json"]),
            )

    def save_file(self, file_rec: FileRecord) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO files (
                    file_path, shard_id, language, content_hash,
                    symbols_json, imports_json, exports_json, loc, last_modified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_rec.file_path,
                file_rec.shard_id,
                file_rec.language,
                file_rec.content_hash,
                json.dumps(file_rec.symbols),
                json.dumps(file_rec.imports),
                json.dumps(file_rec.exports),
                file_rec.loc,
                file_rec.last_modified,
            ))
            self._conn.commit()

    def get_file(self, file_path: str) -> Optional[FileRecord]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM files WHERE file_path = ?", (file_path,))
            row = cur.fetchone()
            if not row:
                return None
            return FileRecord(
                file_path=row["file_path"],
                shard_id=row["shard_id"],
                language=row["language"],
                content_hash=row["content_hash"],
                symbols=json.loads(row["symbols_json"]),
                imports=json.loads(row["imports_json"]),
                exports=json.loads(row["exports_json"]),
                loc=row["loc"],
                last_modified=row["last_modified"],
            )

    def save_contract(self, contract: ContractRecord) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO contracts (
                    contract_id, name, version, shard_id, endpoints_json,
                    consumers_json, providers_json, schema_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                contract.contract_id,
                contract.name,
                contract.version,
                contract.shard_id,
                json.dumps(contract.endpoints),
                json.dumps(contract.consumers),
                json.dumps(contract.providers),
                contract.schema_hash,
            ))
            self._conn.commit()

    def get_contract(self, contract_id: str) -> Optional[ContractRecord]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM contracts WHERE contract_id = ?", (contract_id,))
            row = cur.fetchone()
            if not row:
                return None
            return ContractRecord(
                contract_id=row["contract_id"],
                name=row["name"],
                version=row["version"],
                shard_id=row["shard_id"],
                endpoints=json.loads(row["endpoints_json"]),
                consumers=json.loads(row["consumers_json"]),
                providers=json.loads(row["providers_json"]),
                schema_hash=row["schema_hash"],
            )

    def save_task(self, task: TaskRecord) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO tasks (
                    task_id, objective, affected_files_json, contracts_json, status
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.objective,
                json.dumps(task.affected_files),
                json.dumps(task.contracts),
                task.status,
            ))
            self._conn.commit()

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cur.fetchone()
            if not row:
                return None
            return TaskRecord(
                task_id=row["task_id"],
                objective=row["objective"],
                affected_files=json.loads(row["affected_files_json"]),
                contracts=json.loads(row["contracts_json"]),
                status=row["status"],
            )

    def save_edges(self, edges: List[GraphEdge]) -> None:
        with self._lock:
            cur = self._conn.cursor()
            for edge in edges:
                cur.execute("""
                    INSERT INTO edges (source, target, edge_type, weight, metadata_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    edge.source,
                    edge.target,
                    edge.edge_type,
                    edge.weight,
                    json.dumps(edge.metadata),
                ))
            self._conn.commit()

    def get_edges(self, source: Optional[str] = None, target: Optional[str] = None) -> List[GraphEdge]:
        with self._lock:
            cur = self._conn.cursor()
            if source and target:
                cur.execute("SELECT * FROM edges WHERE source = ? AND target = ?", (source, target))
            elif source:
                cur.execute("SELECT * FROM edges WHERE source = ?", (source,))
            elif target:
                cur.execute("SELECT * FROM edges WHERE target = ?", (target,))
            else:
                cur.execute("SELECT * FROM edges LIMIT 1000")
            rows = cur.fetchall()
            return [
                GraphEdge(
                    source=row["source"],
                    target=row["target"],
                    edge_type=row["edge_type"],
                    weight=row["weight"],
                    metadata=json.loads(row["metadata_json"]),
                )
                for row in rows
            ]

    def save_snapshot(self, snapshot: StateSnapshot) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO snapshots (
                    snapshot_id, repository_state_hash, partition_hashes_json,
                    index_versions_json, graph_versions_json, timestamp, provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.snapshot_id,
                snapshot.repository_state_hash,
                json.dumps(snapshot.partition_hashes),
                json.dumps(snapshot.index_versions),
                json.dumps(snapshot.graph_versions),
                snapshot.timestamp,
                json.dumps(snapshot.provenance),
            ))
            self._conn.commit()

    def get_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
            row = cur.fetchone()
            if not row:
                return None
            return StateSnapshot(
                snapshot_id=row["snapshot_id"],
                repository_state_hash=row["repository_state_hash"],
                partition_hashes=json.loads(row["partition_hashes_json"]),
                index_versions=json.loads(row["index_versions_json"]),
                graph_versions=json.loads(row["graph_versions_json"]),
                timestamp=row["timestamp"],
                provenance=json.loads(row["provenance_json"]),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
