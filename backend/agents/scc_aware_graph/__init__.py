"""Phase 59: SCC-Aware Graph Condensation & Bounded Impact Analysis Module.

Provides deterministic Tarjan/Kosaraju SCC detection, formal graph condensation
into a provably acyclic DAG, transparent coupling metrics, bounded impact analysis
halting at clean SCC boundaries, and incremental update support.
"""

from .models import (
    StronglyConnectedComponent,
    CondensationDAGNode,
    CondensationDAG,
    SCCCouplingMetrics,
    SCCImpactScope,
    ImpactConfidence,
    SCCBoundaryCut,
    SCCAwareImpactResult,
    SCCTelemetryEvent,
)
from .tarjan import TarjanSCC
from .kosaraju import KosarajuSCC
from .scc import SCCDetector
from .condensation import GraphCondenser
from .dag import CondensationDAGManager
from .coupling import CouplingAnalyzer
from .boundary import SCCBoundaryManager
from .subgraph import SCCAwareSubgraphExtractor
from .impact import SCCAwareImpactAnalyzer
from .query import SCCQueryEngine
from .cache import SCCDeterministicCache
from .invalidation import IncrementalSCCUpdater
from .storage import SqliteSCCStorage
from .metrics import SCCTelemetryMetrics
from .security import SCCSecuritySentinel
from .validator import SCCAwareValidator
from .index import SCCReverseIndex
from .bridge import SCCAwareGraphBridge

__all__ = [
    "StronglyConnectedComponent",
    "CondensationDAGNode",
    "CondensationDAG",
    "SCCCouplingMetrics",
    "SCCImpactScope",
    "ImpactConfidence",
    "SCCBoundaryCut",
    "SCCAwareImpactResult",
    "SCCTelemetryEvent",
    "TarjanSCC",
    "KosarajuSCC",
    "SCCDetector",
    "GraphCondenser",
    "CondensationDAGManager",
    "CouplingAnalyzer",
    "SCCBoundaryManager",
    "SCCAwareSubgraphExtractor",
    "SCCAwareImpactAnalyzer",
    "SCCQueryEngine",
    "SCCDeterministicCache",
    "IncrementalSCCUpdater",
    "SqliteSCCStorage",
    "SCCTelemetryMetrics",
    "SCCSecuritySentinel",
    "SCCAwareValidator",
    "SCCReverseIndex",
    "SCCAwareGraphBridge",
]
