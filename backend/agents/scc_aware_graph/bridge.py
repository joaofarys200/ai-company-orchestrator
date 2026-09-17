from __future__ import annotations

from typing import Any, Dict, List, Optional

from .condensation import GraphCondenser
from .coupling import CouplingAnalyzer
from .dag import CondensationDAGManager
from .impact import SCCAwareImpactAnalyzer
from .index import SCCReverseIndex
from .invalidation import IncrementalSCCUpdater
from .metrics import SCCTelemetryMetrics
from .models import (
    CondensationDAG,
    SCCAwareImpactResult,
    SCCCouplingMetrics,
    StronglyConnectedComponent,
)
from .query import SCCQueryEngine
from .scc import SCCDetector
from .security import SCCSecuritySentinel
from .storage import SqliteSCCStorage
from .validator import SCCAwareValidator


class SCCAwareGraphBridge:
    """Unified bridge orchestrating SCC detection, condensation, impact analysis, and telemetry."""

    def __init__(
        self,
        nodes: List[str],
        edges: List[Dict[str, Any]],
        sccs: List[StronglyConnectedComponent],
        dag: CondensationDAG,
        storage: Optional[SqliteSCCStorage] = None,
    ) -> None:
        self.nodes = list(nodes)
        self.edges = list(edges)
        self.sccs = list(sccs)
        self.dag = dag
        self.storage = storage or SqliteSCCStorage(db_path=":memory:")

        # Indexing
        self.index = SCCReverseIndex()
        self.index.index_sccs(self.sccs)

        # Core engines
        self.dag_manager = CondensationDAGManager(self.dag)
        self.query_engine = SCCQueryEngine(self.dag, self.sccs, self.index.node_to_scc)
        self.impact_analyzer = SCCAwareImpactAnalyzer(self.dag, self.index.node_to_scc)
        self.updater = IncrementalSCCUpdater(self.nodes, self.edges, self.sccs, self.dag, self.index.node_to_scc)
        self.metrics = SCCTelemetryMetrics()
        self.security = SCCSecuritySentinel()

        # Telemetry
        self.metrics.record(
            event_type="scc_detected",
            node_count=len(self.nodes),
            edge_count=len(self.edges),
            scc_id=f"total_{len(self.sccs)}",
        )
        self.metrics.record(
            event_type="scc_condensed",
            node_count=len(self.dag.nodes),
            edge_count=len(self.dag.edges),
        )

    @classmethod
    def build_from_graph(
        cls,
        nodes: List[str],
        edges: List[Dict[str, Any]],
        node_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        storage_db_path: str = ":memory:",
    ) -> SCCAwareGraphBridge:
        sccs = SCCDetector.detect_sccs(nodes, edges, node_metadata=node_metadata)
        dag = GraphCondenser.condense(sccs)

        storage = SqliteSCCStorage(db_path=storage_db_path)
        storage.save_sccs(sccs)
        storage.save_dag(dag)

        return cls(nodes=nodes, edges=edges, sccs=sccs, dag=dag, storage=storage)

    def analyze_symbol_impact(
        self,
        root_symbols: List[str],
        max_sccs: int = 15,
        max_nodes: int = 250,
        contracts_map: Optional[Dict[str, List[str]]] = None,
        tasks_map: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        self.metrics.record(event_type="impact_query_started", node_count=len(root_symbols))
        result: SCCAwareImpactResult = self.impact_analyzer.analyze_impact(
            changed_symbols=root_symbols,
            max_sccs=max_sccs,
            max_nodes=max_nodes,
            contracts_map=contracts_map,
            tasks_map=tasks_map,
        )
        self.metrics.record(
            event_type="impact_query_completed",
            node_count=len(result.affected_symbols),
            confidence=result.confidence.value,
            latency_ms=result.extraction_ms,
        )
        return result.to_dict()

    def get_coupling_matrix(self) -> List[Dict[str, Any]]:
        matrix = []
        for scc in self.sccs:
            m: SCCCouplingMetrics = CouplingAnalyzer.analyze_scc(scc)
            matrix.append(m.to_dict())
        return matrix

    def get_overview(self) -> Dict[str, Any]:
        largest = self.query_engine.get_largest_scc()
        cyclic_count = sum(1 for s in self.sccs if s.is_cycle)
        matrix = self.get_coupling_matrix()
        avg_coupling = (sum(m["coupling_score"] for m in matrix) / len(matrix)) if matrix else 0.0

        return {
            "total_raw_nodes": len(self.nodes),
            "total_raw_edges": len(self.edges),
            "total_sccs": len(self.sccs),
            "cyclic_sccs_count": cyclic_count,
            "acyclic_sccs_count": len(self.sccs) - cyclic_count,
            "condensation_nodes": len(self.dag.nodes),
            "condensation_edges": len(self.dag.edges),
            "dag_is_acyclic": self.dag.is_acyclic,
            "largest_scc_size": largest.size if largest else 0,
            "largest_scc_id": largest.scc_id if largest else "",
            "average_coupling_score": round(avg_coupling, 4),
            "telemetry": self.metrics.get_summary(),
        }

    _instances: Dict[str, SCCAwareGraphBridge] = {}

    @classmethod
    def get_bridge(cls, project_id: str = "default") -> SCCAwareGraphBridge:
        if project_id not in cls._instances:
            cls._instances[project_id] = cls._build_default_repo_bridge()
        return cls._instances[project_id]

    @classmethod
    def reset_bridge(cls, project_id: str = "default") -> None:
        if project_id in cls._instances:
            del cls._instances[project_id]

    @classmethod
    def get_graph_status(cls, project_id: str = "default") -> Dict[str, Any]:
        bridge = cls.get_bridge(project_id)
        overview = bridge.get_overview()
        sccs_summary = [
            {
                "scc_id": s.scc_id,
                "size": s.size,
                "density": round(s.density, 3),
                "is_cycle": s.is_cycle,
                "nodes": s.nodes[:10],
                "services": s.services,
                "languages": s.languages,
                "entry_points": s.entry_points,
                "exit_points": s.exit_points,
            }
            for s in bridge.sccs
        ]
        return {
            "overview": overview,
            "sccs": sccs_summary,
            "dag": bridge.dag.to_dict(),
            "coupling_matrix": bridge.get_coupling_matrix(),
        }

    @classmethod
    def query_impact(
        cls,
        symbols: List[str],
        project_id: str = "default",
        max_sccs: int = 15,
        max_nodes: int = 250,
    ) -> Dict[str, Any]:
        bridge = cls.get_bridge(project_id)
        return bridge.analyze_symbol_impact(symbols, max_sccs=max_sccs, max_nodes=max_nodes)

    @classmethod
    def _build_default_repo_bridge(cls) -> SCCAwareGraphBridge:
        nodes = [
            "fe_mission_control", "fe_scc_panel", "fe_task_list", "fe_state_panel",
            "be_websocket_server", "be_mission_handler", "be_event_dispatcher",
            "sentinel_guard", "security_policy",
            "fabric_state_manager", "incremental_indexer", "sqlite_storage",
            "contract_mission_v1", "contract_scc_v1", "worker_pool"
        ]
        edges = [
            # UI Cycle (SCC 1)
            {"source": "fe_mission_control", "target": "fe_scc_panel", "edge_type": "renders"},
            {"source": "fe_scc_panel", "target": "fe_mission_control", "edge_type": "updates"},
            {"source": "fe_mission_control", "target": "fe_task_list", "edge_type": "embeds"},
            {"source": "fe_mission_control", "target": "fe_state_panel", "edge_type": "embeds"},

            # Contracts (Acyclic boundaries)
            {"source": "fe_scc_panel", "target": "contract_scc_v1", "edge_type": "consumes"},
            {"source": "contract_scc_v1", "target": "be_mission_handler", "edge_type": "implements"},
            {"source": "fe_mission_control", "target": "contract_mission_v1", "edge_type": "consumes"},
            {"source": "contract_mission_v1", "target": "be_mission_handler", "edge_type": "implements"},

            # Backend Cycle (SCC 2)
            {"source": "be_websocket_server", "target": "be_mission_handler", "edge_type": "dispatches"},
            {"source": "be_mission_handler", "target": "be_event_dispatcher", "edge_type": "publishes"},
            {"source": "be_event_dispatcher", "target": "be_websocket_server", "edge_type": "broadcasts"},

            # Security Sentinel Cycle (SCC 3)
            {"source": "sentinel_guard", "target": "security_policy", "edge_type": "evaluates"},
            {"source": "security_policy", "target": "sentinel_guard", "edge_type": "enforces"},

            # Cross links
            {"source": "be_mission_handler", "target": "sentinel_guard", "edge_type": "validates_with"},
            {"source": "be_mission_handler", "target": "fabric_state_manager", "edge_type": "queries"},
            {"source": "fabric_state_manager", "target": "incremental_indexer", "edge_type": "indexes"},
            {"source": "fabric_state_manager", "target": "sqlite_storage", "edge_type": "persists"},
            {"source": "be_mission_handler", "target": "worker_pool", "edge_type": "executes_on"},
        ]
        metadata = {
            "fe_mission_control": {"service": "frontend", "language": "typescript"},
            "fe_scc_panel": {"service": "frontend", "language": "typescript"},
            "fe_task_list": {"service": "frontend", "language": "typescript"},
            "fe_state_panel": {"service": "frontend", "language": "typescript"},
            "be_websocket_server": {"service": "backend", "language": "python"},
            "be_mission_handler": {"service": "backend", "language": "python"},
            "be_event_dispatcher": {"service": "backend", "language": "python"},
            "sentinel_guard": {"service": "security", "language": "python"},
            "security_policy": {"service": "security", "language": "python"},
            "fabric_state_manager": {"service": "backend", "language": "python"},
            "incremental_indexer": {"service": "backend", "language": "python"},
            "sqlite_storage": {"service": "infra", "language": "python"},
            "contract_mission_v1": {"service": "shared", "language": "json"},
            "contract_scc_v1": {"service": "shared", "language": "json"},
            "worker_pool": {"service": "workers", "language": "python"},
        }
        return cls.build_from_graph(nodes, edges, node_metadata=metadata)

