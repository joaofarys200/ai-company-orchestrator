from __future__ import annotations

from typing import Any, Dict, List, Optional

from .cache import DeterministicLRUCache
from .index_manager import IndexManager
from .models import ContractRecord, FileRecord, StateTier, SymbolRecord
from .partition import PartitionManager
from .storage import AbstractStateStorage


class LazyStateLoader:
    """Provides lazy loading of cold persisted state into warm/hot memory tiers on demand."""

    def __init__(
        self,
        storage: AbstractStateStorage,
        cache: DeterministicLRUCache,
        indexes: IndexManager,
        partition_manager: PartitionManager,
    ) -> None:
        self.storage = storage
        self.cache = cache
        self.indexes = indexes
        self.partitions = partition_manager
        self.load_operations = 0
        self.cold_fetches = 0

    def load_file_state(self, file_path: str) -> Optional[FileRecord]:
        self.load_operations += 1
        cache_key = f"file:{file_path}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        # Check memory indexes first
        indexed = self.indexes.files.get_file(file_path)
        if indexed:
            self.cache.put(cache_key, indexed, size=indexed.loc or 10)
            return indexed

        # Fetch from cold storage
        self.cold_fetches += 1
        stored = self.storage.get_file(file_path)
        if stored:
            self.cache.put(cache_key, stored, size=stored.loc or 10, state_hash=stored.content_hash)
            self.indexes.files.add_file(stored)
            # Activate shard to warm tier
            self.partitions.activate_shard(stored.shard_id, tier=StateTier.WARM)
            return stored

        return None

    def load_symbol(self, symbol_id: str) -> Optional[SymbolRecord]:
        self.load_operations += 1
        cache_key = f"sym:{symbol_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        indexed = self.indexes.symbols.get_symbol(symbol_id)
        if indexed:
            self.cache.put(cache_key, indexed, size=1)
            return indexed

        self.cold_fetches += 1
        stored = self.storage.get_symbol(symbol_id)
        if stored:
            self.cache.put(cache_key, stored, size=1, state_hash=stored.signature_hash)
            self.indexes.symbols.add_symbol(stored)
            return stored

        return None

    def load_contract(self, contract_id: str) -> Optional[ContractRecord]:
        self.load_operations += 1
        cache_key = f"contract:{contract_id}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        indexed = self.indexes.contracts.get_contract(contract_id)
        if indexed:
            self.cache.put(cache_key, indexed, size=2)
            return indexed

        self.cold_fetches += 1
        stored = self.storage.get_contract(contract_id)
        if stored:
            self.cache.put(cache_key, stored, size=2, state_hash=stored.schema_hash)
            self.indexes.contracts.add_contract(stored)
            return stored

        return None

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "load_operations": self.load_operations,
            "cold_fetches": self.cold_fetches,
            "cache_stats": self.cache.get_stats(),
        }
