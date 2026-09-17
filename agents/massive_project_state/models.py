from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class StateTier(str, Enum):
    """Tiering for project state data to eliminate monolithic RAM usage."""
    HOT = "HOT"      # In-memory working set for active mission
    WARM = "WARM"    # In-memory LRU cache of recently accessed items
    COLD = "COLD"    # Persisted on disk (SQLite WAL), loaded on-demand


class PartitionType(str, Enum):
    """Hierarchy partition scopes."""
    REPOSITORY = "REPOSITORY"
    SERVICE = "SERVICE"
    PACKAGE = "PACKAGE"
    MODULE = "MODULE"
    LANGUAGE = "LANGUAGE"
    DOMAIN = "DOMAIN"
    WORKSPACE = "WORKSPACE"


class ImpactScope(str, Enum):
    """Classified blast radius for changes."""
    LOCAL = "LOCAL"
    REGIONAL = "REGIONAL"
    CROSS_SERVICE = "CROSS_SERVICE"
    REPOSITORY_WIDE = "REPOSITORY_WIDE"


class GraphPartitionLevel(str, Enum):
    """Graph resolution partitions."""
    GLOBAL_GRAPH = "GLOBAL_GRAPH"
    SERVICE_GRAPH = "SERVICE_GRAPH"
    PACKAGE_GRAPH = "PACKAGE_GRAPH"
    MODULE_GRAPH = "MODULE_GRAPH"
    MISSION_SUBGRAPH = "MISSION_SUBGRAPH"


class ShardStatus(str, Enum):
    """Lifecycle status of a state partition/shard."""
    ACTIVE = "ACTIVE"
    EVICTED = "EVICTED"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"


@dataclass
class ProjectMemoryBudget:
    """Rigorous memory guard preventing OOM by bounding in-memory structures."""
    max_hot_files: int = 500
    max_hot_symbols: int = 5000
    max_graph_edges: int = 20000
    max_ram_bytes: int = 256 * 1024 * 1024  # 256 MB soft-limit
    max_subgraph_size: int = 200
    max_concurrent_queries: int = 16

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StateShard:
    """Isolated, independently invalidatable partition of repository state."""
    shard_id: str
    name: str
    partition_type: PartitionType
    state_hash: str
    schema_version: str = "1.0.0"
    last_indexed_revision: int = 1
    dependencies: List[str] = field(default_factory=list)
    status: ShardStatus = ShardStatus.ACTIVE
    file_count: int = 0
    symbol_count: int = 0
    last_access: float = field(default_factory=time.time)
    tier: StateTier = StateTier.COLD

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["partition_type"] = self.partition_type.value
        d["status"] = self.status.value
        d["tier"] = self.tier.value
        return d


@dataclass
class SymbolRecord:
    """Indexed code symbol (function, class, endpoint, interface, etc.)."""
    symbol_id: str
    name: str
    kind: str  # function, class, interface, endpoint, variable, type
    file_path: str
    shard_id: str
    language: str
    signature_hash: str
    consumers: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    contracts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FileRecord:
    """Indexed file record with hash and structural metadata."""
    file_path: str
    shard_id: str
    language: str
    content_hash: str
    symbols: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    loc: int = 0
    last_modified: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContractRecord:
    """Contract specification record connecting services/components."""
    contract_id: str
    name: str
    version: str
    shard_id: str
    endpoints: List[str] = field(default_factory=list)
    consumers: List[str] = field(default_factory=list)
    providers: List[str] = field(default_factory=list)
    schema_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskRecord:
    """Task association record linking tasks to files and contracts."""
    task_id: str
    objective: str
    affected_files: List[str] = field(default_factory=list)
    contracts: List[str] = field(default_factory=list)
    status: str = "PENDING"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuntimeRecord:
    """Runtime artifact record for deployed or executed services."""
    service_id: str
    port: int = 8000
    artifacts: List[str] = field(default_factory=list)
    health_endpoint: str = "/health"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    """Typed relationship edge between code, contract, or task entities."""
    source: str
    target: str
    edge_type: str  # imports, calls, implements, provides_contract, consumes_contract, tested_by, browser_validates
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TargetedSubgraph:
    """Targeted, mission-scoped slice of the global dependency & contract graph."""
    subgraph_id: str
    root_symbols: List[str] = field(default_factory=list)
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    direct_consumers: List[str] = field(default_factory=list)
    downstream_symbols: List[str] = field(default_factory=list)
    contracts: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)
    browser_scenarios: List[str] = field(default_factory=list)
    runtime_dependencies: List[str] = field(default_factory=list)
    extraction_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subgraph_id": self.subgraph_id,
            "root_symbols": self.root_symbols,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": self.nodes,
            "edges": [e.to_dict() for e in self.edges],
            "direct_consumers": self.direct_consumers,
            "downstream_symbols": self.downstream_symbols,
            "contracts": self.contracts,
            "tasks": self.tasks,
            "browser_scenarios": self.browser_scenarios,
            "runtime_dependencies": self.runtime_dependencies,
            "extraction_time_ms": self.extraction_time_ms,
        }


@dataclass
class ChangePlan:
    """Structured plan predicting blast radius, impacted contracts, and tests."""
    plan_id: str
    objective: str
    scope: ImpactScope
    changed_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    affected_tasks: List[str] = field(default_factory=list)
    affected_contracts: List[str] = field(default_factory=list)
    affected_consumers: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    required_tests: List[str] = field(default_factory=list)
    browser_scenarios: List[str] = field(default_factory=list)
    predicted_risk: str = "LOW"
    required_validation: List[str] = field(default_factory=list)
    subgraph_id: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scope"] = self.scope.value
        return d


@dataclass
class StateSnapshot:
    """Point-in-time incremental state snapshot for recovery and comparison."""
    snapshot_id: str
    repository_state_hash: str
    partition_hashes: Dict[str, str] = field(default_factory=dict)
    index_versions: Dict[str, int] = field(default_factory=dict)
    graph_versions: Dict[str, int] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StateTelemetryEvent:
    """Structured telemetry event for state fabric observability."""
    event_type: str
    repository_id: str
    mission_id: str = ""
    partition: str = ""
    state_hash: str = ""
    index_version: int = 1
    memory_bytes: int = 0
    latency_ms: float = 0.0
    decision: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
