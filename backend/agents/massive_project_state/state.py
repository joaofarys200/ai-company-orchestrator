from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

from .cache import DeterministicLRUCache
from .graph import PartitionedGraphManager
from .index_manager import IndexManager
from .invalidation import IncrementalInvalidator
from .loader import LazyStateLoader
from .memory import ProjectMemoryBudgetManager
from .metrics import StateFabricMetrics
from .models import (
    ChangePlan,
    ContractRecord,
    FileRecord,
    GraphEdge,
    ProjectMemoryBudget,
    RuntimeRecord,
    StateShard,
    StateSnapshot,
    StateTier,
    SymbolRecord,
    TargetedSubgraph,
    TaskRecord,
)
from .partition import PartitionManager
from .planner import RepositoryChangePlanner
from .query import StateFabricQueryEngine
from .security import StateFabricSecuritySentinel
from .snapshot import IncrementalSnapshotManager
from .storage import AbstractStateStorage, SqliteStateStorage
from .subgraph import TargetedSubgraphExtractor
from .validator import StateFabricValidator


class ProjectStateFabric:
    """The central Modular Project State Fabric orchestrating HOT/WARM/COLD tiers,

    indexes, targeted subgraphs, causal planning, and memory bounds.
    """

    def __init__(
        self,
        storage: Optional[AbstractStateStorage] = None,
        budget: Optional[ProjectMemoryBudget] = None,
        db_path: str = ":memory:",
        workspace_root: Optional[str] = None,
    ) -> None:
        self.storage = storage or SqliteStateStorage(db_path=db_path)
        self.budget = budget or ProjectMemoryBudget()
        self.partitions = PartitionManager()
        self.indexes = IndexManager()
        self.graph = PartitionedGraphManager()
        self.cache = DeterministicLRUCache(
            max_entries=self.budget.max_hot_files * 2,
            max_bytes=self.budget.max_ram_bytes // 2,
        )
        self.loader = LazyStateLoader(
            storage=self.storage,
            cache=self.cache,
            indexes=self.indexes,
            partition_manager=self.partitions,
        )
        self.invalidator = IncrementalInvalidator(
            indexes=self.indexes,
            graph=self.graph,
            partitions=self.partitions,
            cache=self.cache,
            storage=self.storage,
        )
        self.extractor = TargetedSubgraphExtractor(
            index_manager=self.indexes,
            graph_manager=self.graph,
        )
        self.planner = RepositoryChangePlanner(
            index_manager=self.indexes,
            extractor=self.extractor,
        )
        self.snapshots = IncrementalSnapshotManager(
            storage=self.storage,
            partitions=self.partitions,
            indexes=self.indexes,
            graph=self.graph,
        )
        self.memory = ProjectMemoryBudgetManager(
            budget=self.budget,
            cache=self.cache,
            partitions=self.partitions,
        )
        self.metrics = StateFabricMetrics()
        self.security = StateFabricSecuritySentinel(workspace_root=workspace_root)
        self.validator = StateFabricValidator(
            partitions=self.partitions,
            indexes=self.indexes,
        )
        self.query_engine = StateFabricQueryEngine(
            index_manager=self.indexes,
            loader=self.loader,
            max_workers=self.budget.max_concurrent_queries,
        )

        self.metrics.record(event_type="state_fabric_initialized", decision="READY")

    def register_file(
        self,
        file_path: str,
        content: str,
        symbols: Optional[List[SymbolRecord]] = None,
        shard_id: Optional[str] = None,
        loc: int = 100,
    ) -> FileRecord:
        valid, msg = self.security.validate_file_path(file_path)
        if not valid:
            raise PermissionError(f"Security Sentinel path rejection: {msg}")

        sid = shard_id or self.partitions.detect_shard_for_path(file_path)
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        sym_ids = [s.symbol_id for s in symbols] if symbols else []
        file_rec = FileRecord(
            file_path=file_path,
            shard_id=sid,
            language="typescript" if file_path.endswith((".ts", ".tsx")) else "python",
            content_hash=content_hash,
            symbols=sym_ids,
            loc=loc,
            last_modified=time.time(),
        )

        self.indexes.index_file(file_rec, symbols=symbols)
        self.storage.save_file(file_rec)
        if symbols:
            for s in symbols:
                self.storage.save_symbol(s)

        # Update shard metrics
        self.partitions.update_shard_metrics(sid, file_delta=1, symbol_delta=len(sym_ids))
        shard = self.partitions.get_shard(sid)
        if shard:
            self.storage.save_shard(shard)

        # Enforce memory budget
        self.memory.check_and_enforce_budget(
            current_hot_files=self.indexes.files.size(),
            current_hot_symbols=self.indexes.symbols.size(),
        )

        self.metrics.record(
            event_type="file_registered",
            partition=sid,
            state_hash=content_hash[:16],
            decision="REGISTERED",
        )
        return file_rec

    def register_contract(self, contract: ContractRecord) -> None:
        self.indexes.contracts.add_contract(contract)
        self.storage.save_contract(contract)
        self.metrics.record(
            event_type="contract_registered",
            partition=contract.shard_id,
            state_hash=contract.schema_hash,
            decision="REGISTERED",
        )

    def register_task(self, task: TaskRecord) -> None:
        self.indexes.tasks.add_task(task)
        self.storage.save_task(task)

    def register_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GraphEdge:
        edge = self.graph.add_edge(source, target, edge_type, weight, metadata)
        self.storage.save_edges([edge])
        return edge

    def invalidate_file(
        self,
        file_path: str,
        new_content: str,
        new_symbols: Optional[List[SymbolRecord]] = None,
    ) -> Dict[str, Any]:
        valid, msg = self.security.validate_file_path(file_path)
        if not valid:
            raise PermissionError(f"Security Sentinel path rejection: {msg}")

        new_hash = hashlib.sha256(new_content.encode()).hexdigest()
        report = self.invalidator.invalidate_file(file_path, new_hash, new_symbols)

        self.metrics.record(
            event_type="index_invalidated",
            partition=report.get("shard_id", ""),
            state_hash=report.get("new_state_hash", ""),
            index_version=report.get("after_index_revision", 1),
            decision="INVALIDATED",
        )
        return report

    def extract_targeted_subgraph(
        self,
        root_symbols: List[str],
        max_depth: int = 3,
        max_nodes: int = 150,
    ) -> TargetedSubgraph:
        subgraph = self.extractor.extract_subgraph(root_symbols, max_depth, max_nodes)
        self.metrics.record(
            event_type="subgraph_extracted",
            latency_ms=subgraph.extraction_time_ms,
            decision="EXTRACTED",
        )
        return subgraph

    def plan_repository_change(
        self,
        objective: str,
        changed_files: List[str],
        changed_contracts: Optional[List[str]] = None,
        risk: str = "LOW",
    ) -> ChangePlan:
        plan = self.planner.plan_change(objective, changed_files, changed_contracts, risk)

        # Enforce economic validation
        economic_valid, eco_msg = self.security.validate_economic_impact(plan.affected_symbols, plan.scope.value)
        if not economic_valid:
            plan.scope = plan.scope if plan.scope.value in ("CROSS_SERVICE", "REPOSITORY_WIDE") else plan.scope
            plan.required_validation.append(f"SECURITY_ALERT: {eco_msg}")
            plan.predicted_risk = "CRITICAL"

        self.metrics.record(
            event_type="change_plan_created",
            decision=plan.scope.value,
        )
        return plan

    def create_snapshot(self, description: str = "") -> StateSnapshot:
        snap = self.snapshots.create_snapshot(description=description)
        self.metrics.record(
            event_type="snapshot_created",
            state_hash=snap.repository_state_hash,
            decision="SNAPSHOT_SAVED",
        )
        return snap

    def restore_snapshot(self, snapshot_id: str) -> Optional[StateSnapshot]:
        snap = self.snapshots.restore_snapshot(snapshot_id)
        if snap:
            self.metrics.record(
                event_type="snapshot_restored",
                state_hash=snap.repository_state_hash,
                decision="SNAPSHOT_RESTORED",
            )
        return snap

    def get_state_overview(self) -> Dict[str, Any]:
        shards = self.partitions.list_shards()
        tier_counts = {t.value: 0 for t in StateTier}
        for s in shards:
            tier_counts[s.tier.value] += 1

        return {
            "total_shards": len(shards),
            "shards": [s.to_dict() for s in shards],
            "tier_distribution": tier_counts,
            "indexes": self.indexes.get_index_summary(),
            "graph_edges": self.graph.edge_count(),
            "cache": self.cache.get_stats(),
            "memory": self.memory.get_status(),
            "metrics": self.metrics.get_summary(),
        }
