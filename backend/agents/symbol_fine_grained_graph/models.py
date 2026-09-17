from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class SymbolKind(str, Enum):
    """Categorization of symbols extracted from source ASTs."""
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    METHOD = "METHOD"
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"
    INTERFACE = "INTERFACE"
    TYPE = "TYPE"
    ENUM = "ENUM"
    MODULE = "MODULE"
    PROPERTY = "PROPERTY"
    PARAMETER = "PARAMETER"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"


class SymbolEdgeType(str, Enum):
    """Granular dependency edge semantics between individual symbols."""
    IMPORTS = "IMPORTS"
    REEXPORTS = "REEXPORTS"
    CALLS = "CALLS"
    REFERENCES = "REFERENCES"
    TYPE_USES = "TYPE_USES"
    VALUE_USES = "VALUE_USES"
    IMPLEMENTS = "IMPLEMENTS"
    EXTENDS = "EXTENDS"
    OVERRIDES = "OVERRIDES"
    CONSTRUCTS = "CONSTRUCTS"
    READS = "READS"
    WRITES = "WRITES"
    DYNAMIC = "DYNAMIC"
    UNKNOWN = "UNKNOWN"


class SymbolImpactScope(str, Enum):
    """Hierarchical reach of symbol changes."""
    SYMBOL_LOCAL = "SYMBOL_LOCAL"
    FILE_LOCAL = "FILE_LOCAL"
    MODULE = "MODULE"
    SERVICE = "SERVICE"
    CROSS_SERVICE = "CROSS_SERVICE"
    REPOSITORY_WIDE = "REPOSITORY_WIDE"


class BarrelClassification(str, Enum):
    """Classification of re-export barrel modules."""
    EXACT = "EXACT"
    OVER_APPROXIMATED = "OVER_APPROXIMATED"
    UNKNOWN = "UNKNOWN"


class ImpactConfidence(str, Enum):
    """Epistemic certainty level of graph exploration."""
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    BOUNDARY_LIMITED = "BOUNDARY_LIMITED"
    UNKNOWN = "UNKNOWN"


@dataclass
class SymbolNode:
    """Atomic symbol extracted from source AST."""
    symbol_id: str
    file_id: str
    module_id: str
    name: str
    qualified_name: str
    language: str
    kind: SymbolKind
    exported: bool = False
    imported: bool = False
    line: int = 1
    column: int = 1
    visibility: str = "public"
    signature_hash: str = ""
    body_hash: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)
    state_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value if isinstance(self.kind, SymbolKind) else str(self.kind)
        return d


@dataclass
class SymbolEdge:
    """Directed relationship between two symbols."""
    source_symbol: str
    target_symbol: str
    edge_type: SymbolEdgeType
    provenance: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    source_location: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["edge_type"] = self.edge_type.value if isinstance(self.edge_type, SymbolEdgeType) else str(self.edge_type)
        return d


@dataclass
class SymbolSCC:
    """Strongly connected component composed of atomic symbols."""
    scc_id: str
    symbols: List[str]
    files: List[str]
    edges_internal: List[Dict[str, Any]] = field(default_factory=list)
    edges_external: List[Dict[str, Any]] = field(default_factory=list)
    size: int = 0
    density: float = 0.0
    languages: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    state_hash: str = ""
    is_cycle: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BarrelAnalysisResult:
    """Result of analyzing an index or __init__ barrel file."""
    barrel_file: str
    reexported_symbols: List[str] = field(default_factory=list)
    resolution_map: Dict[str, str] = field(default_factory=dict)
    overapproximation_ratio: float = 1.0
    classification: BarrelClassification = BarrelClassification.EXACT
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["classification"] = self.classification.value if isinstance(self.classification, BarrelClassification) else str(self.classification)
        return d


@dataclass
class SymbolPrecisionComparison:
    """Comparative precision analysis: File-level SCC vs Symbol-level SCC."""
    file_scc_size: int
    symbol_scc_size: int
    file_impact_count: int
    symbol_impact_count: int
    precision_gain: float
    overapproximation_reduction: float
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SymbolCondensationDAGNode:
    """Meta-node in symbol condensation DAG."""
    scc_id: str
    scc: SymbolSCC
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
            "files": self.scc.files,
            "services": self.scc.services,
            "languages": self.scc.languages,
        }


@dataclass
class SymbolCondensationDAG:
    """Acyclic meta-graph resulting from condensing symbol SCCs."""
    dag_id: str
    nodes: Dict[str, SymbolCondensationDAGNode] = field(default_factory=dict)
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
class SymbolBoundaryCut:
    """Record of an explicit cutoff at a symbol SCC frontier."""
    cut_scc_id: str
    cut_depth: int
    outgoing_edges_cut: int
    unexplored_symbol_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SymbolAwareImpactResult:
    """Targeted impact analysis result originating from symbol_id."""
    impact_id: str
    root_symbols: List[str]
    root_sccs: List[str]
    included_sccs: List[str]
    excluded_sccs: List[str]
    boundary_edges: List[Dict[str, Any]]
    scope: SymbolImpactScope
    confidence: ImpactConfidence
    affected_symbols: List[str]
    internal_affected_symbols: List[str]
    external_affected_symbols: List[str]
    affected_files: List[str]
    contracts: List[str]
    tasks: List[str]
    browser_scenarios: List[str]
    services: List[str]
    blast_radius_score: float
    truncated_at_boundary: bool
    extraction_ms: float

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scope"] = self.scope.value if isinstance(self.scope, SymbolImpactScope) else str(self.scope)
        d["confidence"] = self.confidence.value if isinstance(self.confidence, ImpactConfidence) else str(self.confidence)
        return d
