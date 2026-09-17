from __future__ import annotations

from typing import Dict, List, Optional, Set

from .models import StronglyConnectedComponent


class SCCReverseIndex:
    """Reverse index connecting nodes, services, and contracts to SCC IDs in O(1)."""

    def __init__(self) -> None:
        self.node_to_scc: Dict[str, str] = {}
        self.service_to_sccs: Dict[str, Set[str]] = {}
        self.contract_to_sccs: Dict[str, Set[str]] = {}
        self.sccs_by_id: Dict[str, StronglyConnectedComponent] = {}
        self.revision = 1

    def index_sccs(self, sccs: List[StronglyConnectedComponent], contract_node_map: Optional[Dict[str, List[str]]] = None) -> None:
        self.clear()
        c_map = contract_node_map or {}

        for scc in sccs:
            self.sccs_by_id[scc.scc_id] = scc
            for node in scc.nodes:
                self.node_to_scc[node] = scc.scc_id
                for c in c_map.get(node, []):
                    self.contract_to_sccs.setdefault(c, set()).add(scc.scc_id)

            for svc in scc.services:
                self.service_to_sccs.setdefault(svc, set()).add(scc.scc_id)

        self.revision += 1

    def get_scc_id(self, node_id: str) -> Optional[str]:
        return self.node_to_scc.get(node_id)

    def get_sccs_by_service(self, service_id: str) -> List[str]:
        return sorted(list(self.service_to_sccs.get(service_id, set())))

    def get_sccs_by_contract(self, contract_id: str) -> List[str]:
        return sorted(list(self.contract_to_sccs.get(contract_id, set())))

    def clear(self) -> None:
        self.node_to_scc.clear()
        self.service_to_sccs.clear()
        self.contract_to_sccs.clear()
        self.sccs_by_id.clear()
        self.revision += 1

    def size(self) -> int:
        return len(self.sccs_by_id)
