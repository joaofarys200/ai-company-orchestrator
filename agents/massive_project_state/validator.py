from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .index_manager import IndexManager
from .partition import PartitionManager


class StateFabricValidator:
    """Validates structural consistency and contract coherence across partitions."""

    def __init__(self, partitions: PartitionManager, indexes: IndexManager) -> None:
        self.partitions = partitions
        self.indexes = indexes

    def validate_fabric_integrity(self) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        shards = self.partitions.list_shards()
        if not shards:
            errors.append("State fabric has no registered shards")

        for shard in shards:
            if not shard.state_hash:
                errors.append(f"Shard {shard.shard_id} missing state hash")
            if shard.last_indexed_revision < 1:
                errors.append(f"Shard {shard.shard_id} invalid revision")

        # Validate symbol-to-file mapping
        for sym_id, file_path in self.indexes.files._symbol_to_file.items():
            if not self.indexes.files.get_file(file_path):
                errors.append(f"Symbol {sym_id} mapped to non-existent file {file_path}")

        return (len(errors) == 0), errors

    def check_circular_dependency(self, entity_id: str, visited: Optional[set] = None) -> bool:
        if visited is None:
            visited = set()
        if entity_id in visited:
            return True
        visited.add(entity_id)

        deps = self.indexes.dependencies.get_dependencies(entity_id)
        for dep in deps:
            if self.check_circular_dependency(dep, set(visited)):
                return True
        return False
