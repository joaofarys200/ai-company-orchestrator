from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .cache import DeterministicLRUCache
from .models import ProjectMemoryBudget, StateShard, StateTier
from .partition import PartitionManager


class ProjectMemoryBudgetManager:
    """Monitors memory boundaries, triggers eviction, and guards against OOM."""

    def __init__(
        self,
        budget: Optional[ProjectMemoryBudget] = None,
        cache: Optional[DeterministicLRUCache] = None,
        partitions: Optional[PartitionManager] = None,
    ) -> None:
        self.budget = budget or ProjectMemoryBudget()
        self.cache = cache
        self.partitions = partitions
        self.eviction_events: List[Dict[str, Any]] = []
        self._learned_hotspots: List[Dict[str, Any]] = []

    def check_and_enforce_budget(self, current_hot_files: int, current_hot_symbols: int) -> bool:
        """Enforce memory limits; evicts least recently used partitions/cache if exceeded."""
        exceeded = False
        reason = []

        if current_hot_files > self.budget.max_hot_files:
            exceeded = True
            reason.append(f"hot_files ({current_hot_files}) > limit ({self.budget.max_hot_files})")

        if current_hot_symbols > self.budget.max_hot_symbols:
            exceeded = True
            reason.append(f"hot_symbols ({current_hot_symbols}) > limit ({self.budget.max_hot_symbols})")

        if self.cache and self.cache._current_bytes > self.budget.max_ram_bytes:
            exceeded = True
            reason.append(f"ram_bytes ({self.cache._current_bytes}) > limit ({self.budget.max_ram_bytes})")

        if exceeded and self.partitions:
            # Evict oldest warm shard to cold storage
            shards = sorted(self.partitions.list_shards(), key=lambda s: s.last_access)
            for s in shards:
                if s.tier in (StateTier.WARM, StateTier.HOT):
                    self.partitions.evict_shard(s.shard_id)
                    event = {
                        "evicted_shard": s.shard_id,
                        "timestamp": time.time(),
                        "reason": ", ".join(reason),
                    }
                    self.eviction_events.append(event)
                    break

        return not exceeded

    def record_experience_hotspot(self, shard_id: str, change_frequency: int, avg_blast_radius: int) -> None:
        """Registers frequent dependency patterns for cross-mission experience memory."""
        self._learned_hotspots.append({
            "shard_id": shard_id,
            "change_frequency": change_frequency,
            "avg_blast_radius": avg_blast_radius,
            "recorded_at": time.time(),
        })

    def get_learned_hotspots(self) -> List[Dict[str, Any]]:
        return list(self._learned_hotspots)

    def get_status(self) -> Dict[str, Any]:
        return {
            "budget": self.budget.to_dict(),
            "eviction_count": len(self.eviction_events),
            "recent_evictions": self.eviction_events[-5:],
            "learned_hotspots_count": len(self._learned_hotspots),
        }
