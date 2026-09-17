from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class SCCImpactScope(str, Enum):
    """Categorized scope of change propagation through SCC DAG."""
    LOCAL_SCC = "LOCAL_SCC"                      # Self-contained within single module/class cycle
    REGIONAL_SCC = "REGIONAL_SCC"                # Cycle touches multiple packages within one service
    CROSS_SERVICE_SCC = "CROSS_SERVICE_SCC"      # Cycle crosses architectural service boundaries
    REPOSITORY_WIDE_SCC = "REPOSITORY_WIDE_SCC"  # Cycle or its reach touches shared contracts or >3 services


class ImpactConfidence(str, Enum):
    """Epistemic certainty level of graph impact exploration."""
    FULL = "FULL"                                # All reachability traversed without boundary cuts
    PARTIAL = "PARTIAL"                          # Standard partial search
    BOUNDARY_LIMITED = "BOUNDARY_LIMITED"        # Stopped cleanly at explicit SCC boundaries
    UNKNOWN = "UNKNOWN"                          # Arbitrary cutoff / opaque truncation


@dataclass
class StronglyConnectedComponent:
    """Explicit model of a strongly connected component in the dependency graph."""
    scc_id: str
    nodes: List[str]
    edges_internal: List[Dict[str, Any]] = field(default_factory=list)
    incoming_edges: List[Dict[str, Any]] = field(default_factory=list)
    outgoing_edges: List[Dict[str, Any]] = field(default_factory=list)
    size: int = 0
    density: float = 0.0
    entry_points: List[str] = field(default_factory=list)
    exit_points: List[str] = field(default_factory=list)
    state_hash: str = ""
    partition_ids: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    is_cycle: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CondensationDAGNode:
    """Meta-node in the condensed directed acyclic graph representing an entire SCC."""
    scc_id: str
    scc: StronglyConnectedComponent
    downstream_scc_ids: List[str] = field(default_factory=list)
    upstream_scc_ids: List[str] = field(default_factory=list)
    topological_order: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scc_id": self.scc_id,
            "size": self.scc.size,
            "density": self.scc.density,
            "is_cycle": self.scc.is_cycle,
            "downstream_scc_ids": self.downstream_scc_ids,
            "upstream_scc_ids": self.upstream_scc_ids,
            "topological_order": self.topological_order,
            "services": self.scc.services,
            "languages": self.scc.languages,
        }


@dataclass
class CondensationDAG:
    """Acyclic meta-graph resulting from condensing all strongly connected components."""
    dag_id: str
    nodes: Dict[str, CondensationDAGNode] = field(default_factory=dict)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    is_acyclic: bool = True
    topological_ordering: List[str] = field(default_factory=list)
    revision: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dag_id": self.dag_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "is_acyclic": self.is_acyclic,
            "topological_ordering": self.topological_ordering,
            "revision": self.revision,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": self.edges,
        }


@dataclass
class SCCCouplingMetrics:
    """Transparent mathematical metrics describing coupling density and blast propagation."""
    scc_id: str
    size: int
    internal_edges_count: int
    external_edges_count: int
    density: float
    fan_in: int
    fan_out: int
    cross_service_edges: int
    cross_language_edges: int
    cycle_depth: int
    coupling_score: float
    components_explanation: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SCCBoundaryCut:
    """Explicit record of an unexpanded condensation frontier when budget is reached."""
    cut_scc_id: str
    cut_depth: int
    outgoing_edges_cut: int
    unexplored_node_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SCCAwareImpactResult:
    """Comprehensive impact analysis result backed by SCC condensation."""
    impact_id: str
    root_symbols: List[str]
    root_sccs: List[str]
    included_sccs: List[str]
    excluded_sccs: List[str]
    boundary_edges: List[Dict[str, Any]]
    scope: SCCImpactScope
    confidence: ImpactConfidence
    affected_symbols: List[str]
    internal_affected_symbols: List[str]
    external_affected_symbols: List[str]
    contracts: List[str]
    tasks: List[str]
    browser_scenarios: List[str]
    services: List[str]
    blast_radius_score: float
    truncated_at_boundary: bool
    extraction_ms: float

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scope"] = self.scope.value
        d["confidence"] = self.confidence.value
        return d


@dataclass
class SCCTelemetryEvent:
    """Structured telemetry event for SCC graph operations."""
    event_type: str
    repository_id: str = "jarvis_os"
    mission_id: str = ""
    graph_revision: int = 1
    scc_id: str = ""
    node_count: int = 0
    edge_count: int = 0
    latency_ms: float = 0.0
    confidence: str = "FULL"
    provenance: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
