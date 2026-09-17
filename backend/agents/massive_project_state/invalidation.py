from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Set

from .cache import DeterministicLRUCache
from .graph import PartitionedGraphManager
from .index_manager import IndexManager
from .models import FileRecord, SymbolRecord
from .partition import PartitionManager
from .storage import AbstractStateStorage


class IncrementalInvalidator:
    """Performs surgical, diff-based invalidation without rebuilding full state."""

    def __init__(
        self,
        indexes: IndexManager,
        graph: PartitionedGraphManager,
        partitions: PartitionManager,
        cache: DeterministicLRUCache,
        storage: Optional[AbstractStateStorage] = None,
    ) -> None:
        self.indexes = indexes
        self.graph = graph
        self.partitions = partitions
        self.cache = cache
        self.storage = storage

    def invalidate_file(
        self,
        file_path: str,
        new_content_hash: str,
        new_symbols: Optional[List[SymbolRecord]] = None,
    ) -> Dict[str, Any]:
        existing_file = self.indexes.files.get_file(file_path)
        shard_id = existing_file.shard_id if existing_file else self.partitions.detect_shard_for_path(file_path)
        shard = self.partitions.get_shard(shard_id)
        before_rev = shard.last_indexed_revision if shard else 1

        invalidated_symbols: List[str] = []
        invalidated_edges_count = 0

        # Step 1: Invalidate existing symbols
        if existing_file:
            for old_sym_id in existing_file.symbols:
                invalidated_symbols.append(old_sym_id)
                self.indexes.symbols.remove_symbol(old_sym_id)
                self.graph.remove_edges_for_node(old_sym_id)
                self.cache.invalidate(f"sym:{old_sym_id}")
                invalidated_edges_count += 1

            self.indexes.files.remove_file(file_path)
            self.cache.invalidate(f"file:{file_path}")

        # Step 2: Register new symbols if provided
        symbol_ids = []
        if new_symbols:
            for sym in new_symbols:
                symbol_ids.append(sym.symbol_id)
                self.indexes.symbols.add_symbol(sym)
                if self.storage:
                    self.storage.save_symbol(sym)

        # Step 3: Register updated file record
        updated_file = FileRecord(
            file_path=file_path,
            shard_id=shard_id,
            language="typescript" if file_path.endswith((".ts", ".tsx")) else "python",
            content_hash=new_content_hash,
            symbols=symbol_ids,
            loc=100,
            last_modified=time.time(),
        )
        self.indexes.files.add_file(updated_file)
        if self.storage:
            self.storage.save_file(updated_file)

        # Step 4: Advance shard revision and update shard hash
        if shard:
            shard.last_indexed_revision += 1
            shard.state_hash = hashlib.sha256(
                f"{shard_id}:{shard.last_indexed_revision}:{new_content_hash}".encode()
            ).hexdigest()[:16]
            shard.last_access = time.time()
            after_rev = shard.last_indexed_revision
            if self.storage:
                self.storage.save_shard(shard)
        else:
            after_rev = before_rev + 1

        return {
            "file_path": file_path,
            "shard_id": shard_id,
            "before_index_revision": before_rev,
            "after_index_revision": after_rev,
            "invalidated_symbols": invalidated_symbols,
            "invalidated_edges_count": invalidated_edges_count,
            "new_symbol_count": len(symbol_ids),
            "new_state_hash": shard.state_hash if shard else "",
            "timestamp": time.time(),
        }
