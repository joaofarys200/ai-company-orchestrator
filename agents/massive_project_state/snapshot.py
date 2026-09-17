from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional

from .graph import PartitionedGraphManager
from .index_manager import IndexManager
from .models import StateSnapshot
from .partition import PartitionManager
from .storage import AbstractStateStorage


class IncrementalSnapshotManager:
    """Creates lightweight point-in-time state snapshots and enables fast recovery."""

    def __init__(
        self,
        storage: AbstractStateStorage,
        partitions: PartitionManager,
        indexes: IndexManager,
        graph: PartitionedGraphManager,
    ) -> None:
        self.storage = storage
        self.partitions = partitions
        self.indexes = indexes
        self.graph = graph

    def create_snapshot(self, description: str = "") -> StateSnapshot:
        shards = self.partitions.list_shards()
        partition_hashes = {s.shard_id: s.state_hash for s in shards}

        hasher = hashlib.sha256()
        for sid in sorted(partition_hashes.keys()):
            hasher.update(f"{sid}:{partition_hashes[sid]}".encode())
        repo_hash = hasher.hexdigest()[:16]

        index_versions = self.indexes.get_index_versions()
        graph_versions = {"edges": self.graph.edge_count(), "revision": self.graph.revision}

        snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
        snapshot = StateSnapshot(
            snapshot_id=snapshot_id,
            repository_state_hash=repo_hash,
            partition_hashes=partition_hashes,
            index_versions=index_versions,
            graph_versions=graph_versions,
            timestamp=time.time(),
            provenance={"description": description, "shard_count": len(shards)},
        )

        self.storage.save_snapshot(snapshot)
        return snapshot

    def restore_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        snapshot = self.storage.get_snapshot(snapshot_id)
        if not snapshot:
            return None

        for shard_id, phash in snapshot.partition_hashes.items():
            shard = self.partitions.get_shard(shard_id)
            if shard:
                shard.state_hash = phash

        return snapshot
