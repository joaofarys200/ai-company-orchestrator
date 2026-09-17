from __future__ import annotations

from typing import Any, Dict, List, Optional

from .coupling import CouplingAnalyzer
from .dag import CondensationDAGManager
from .models import CondensationDAG, SCCCouplingMetrics, StronglyConnectedComponent


class SCCQueryEngine:
    """Provides rapid queries over SCC membership, condensation topology, and coupling metrics."""

    def __init__(
        self,
        dag: CondensationDAG,
        sccs: List[StronglyConnectedComponent],
        node_to_scc: Dict[str, str],
    ) -> None:
        self.dag = dag
        self.sccs_by_id = {s.scc_id: s for s in sccs}
        self.node_to_scc = node_to_scc
        self.dag_manager = CondensationDAGManager(dag)

    def get_scc_for_symbol(self, symbol_id: str) -> Optional[StronglyConnectedComponent]:
        scc_id = self.node_to_scc.get(symbol_id)
        if scc_id:
            return self.sccs_by_id.get(scc_id)
        return None

    def get_downstream_sccs(self, scc_id: str) -> List[str]:
        return self.dag_manager.get_downstream_sccs(scc_id)

    def get_upstream_sccs(self, scc_id: str) -> List[str]:
        return self.dag_manager.get_upstream_sccs(scc_id)

    def get_scc_members(self, scc_id: str) -> List[str]:
        scc = self.sccs_by_id.get(scc_id)
        return list(scc.nodes) if scc else []

    def get_scc_metrics(self, scc_id: str) -> Optional[SCCCouplingMetrics]:
        scc = self.sccs_by_id.get(scc_id)
        if scc:
            return CouplingAnalyzer.analyze_scc(scc)
        return None

    def list_all_sccs(self) -> List[StronglyConnectedComponent]:
        return list(self.sccs_by_id.values())

    def get_largest_scc(self) -> Optional[StronglyConnectedComponent]:
        if not self.sccs_by_id:
            return None
        return max(self.sccs_by_id.values(), key=lambda s: s.size)
