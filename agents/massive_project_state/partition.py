from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Set

from .models import PartitionType, ShardStatus, StateShard, StateTier


class PartitionManager:
    """Manages repository state partitioning into modular, decoupled shards."""

    DEFAULT_SHARDS = [
        ("frontend", "Frontend Web & UI Client", PartitionType.SERVICE, ["shared"]),
        ("backend", "Backend API & Orchestration Core", PartitionType.SERVICE, ["shared"]),
        ("workers", "Async Background Workers & Tasks", PartitionType.SERVICE, ["shared", "backend"]),
        ("infra", "Deployment, Infrastructure & CI/CD", PartitionType.DOMAIN, ["shared"]),
        ("shared", "Shared Contracts, Schemas & Protocols", PartitionType.PACKAGE, []),
    ]

    def __init__(self) -> None:
        self._shards: Dict[str, StateShard] = {}
        self._init_default_shards()

    def _init_default_shards(self) -> None:
        for shard_id, name, ptype, deps in self.DEFAULT_SHARDS:
            self.create_shard(shard_id=shard_id, name=name, partition_type=ptype, dependencies=deps)

    def create_shard(
        self,
        shard_id: str,
        name: str,
        partition_type: PartitionType,
        dependencies: Optional[List[str]] = None,
    ) -> StateShard:
        initial_hash = hashlib.sha256(f"shard:{shard_id}:v1:{time.time()}".encode()).hexdigest()[:16]
        shard = StateShard(
            shard_id=shard_id,
            name=name,
            partition_type=partition_type,
            state_hash=initial_hash,
            dependencies=dependencies or [],
            status=ShardStatus.ACTIVE,
            tier=StateTier.WARM,
        )
        self._shards[shard_id] = shard
        return shard

    def get_shard(self, shard_id: str) -> Optional[StateShard]:
        shard = self._shards.get(shard_id)
        if shard:
            shard.last_access = time.time()
        return shard

    def list_shards(self) -> List[StateShard]:
        return list(self._shards.values())

    def update_shard_metrics(self, shard_id: str, file_delta: int = 0, symbol_delta: int = 0) -> None:
        shard = self.get_shard(shard_id)
        if shard:
            shard.file_count = max(0, shard.file_count + file_delta)
            shard.symbol_count = max(0, shard.symbol_count + symbol_delta)
            shard.last_indexed_revision += 1
            shard.state_hash = hashlib.sha256(
                f"{shard_id}:{shard.last_indexed_revision}:{shard.file_count}:{shard.symbol_count}".encode()
            ).hexdigest()[:16]

    def evict_shard(self, shard_id: str) -> bool:
        shard = self.get_shard(shard_id)
        if shard:
            shard.tier = StateTier.COLD
            shard.status = ShardStatus.EVICTED
            return True
        return False

    def activate_shard(self, shard_id: str, tier: StateTier = StateTier.HOT) -> bool:
        shard = self.get_shard(shard_id)
        if shard:
            shard.tier = tier
            shard.status = ShardStatus.ACTIVE
            shard.last_access = time.time()
            return True
        return False

    def detect_shard_for_path(self, file_path: str) -> str:
        norm = file_path.replace("\\", "/").lower().strip("/")
        if norm.startswith("frontend") or "/frontend" in norm:
            return "frontend"
        if norm.startswith("backend") or norm.startswith("agents") or norm.startswith("intelligence"):
            return "backend"
        if "worker" in norm or "job" in norm:
            return "workers"
        if "infra" in norm or "docker" in norm or norm.startswith("scripts"):
            return "infra"
        return "shared"

    def get_cross_shard_dependents(self, shard_id: str) -> List[str]:
        """Find shards that depend on the specified shard."""
        dependents = []
        for sid, shard in self._shards.items():
            if shard_id in shard.dependencies:
                dependents.append(sid)
        return dependents
