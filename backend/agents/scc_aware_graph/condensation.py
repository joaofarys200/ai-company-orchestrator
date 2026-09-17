from __future__ import annotations

import heapq
import uuid
from typing import Any, Dict, List, Set, Tuple

from .models import CondensationDAG, CondensationDAGNode, StronglyConnectedComponent


class GraphCondenser:
    """Condenses strongly connected components into a formal acyclic meta-graph (Condensation DAG)."""

    @classmethod
    def condense(cls, sccs: List[StronglyConnectedComponent]) -> CondensationDAG:
        dag_id = f"cdag_{uuid.uuid4().hex[:8]}"

        # Node to SCC ID mapping
        node_to_scc: Dict[str, str] = {}
        for scc in sccs:
            for n in scc.nodes:
                node_to_scc[n] = scc.scc_id

        # Build meta-nodes
        nodes_dict: Dict[str, CondensationDAGNode] = {}
        for scc in sccs:
            nodes_dict[scc.scc_id] = CondensationDAGNode(
                scc_id=scc.scc_id,
                scc=scc,
                downstream_scc_ids=[],
                upstream_scc_ids=[],
            )

        # Build meta-edges
        meta_edges_set: Set[Tuple[str, str]] = set()
        meta_edges_details: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for scc in sccs:
            for out_edge in scc.outgoing_edges:
                src_node = out_edge.get("source") or out_edge.get("src")
                tgt_node = out_edge.get("target") or out_edge.get("dst")
                target_scc = node_to_scc.get(tgt_node)

                if target_scc and target_scc != scc.scc_id:
                    pair = (scc.scc_id, target_scc)
                    meta_edges_set.add(pair)
                    if pair not in meta_edges_details:
                        meta_edges_details[pair] = {
                            "source_scc": scc.scc_id,
                            "target_scc": target_scc,
                            "raw_edge_count": 0,
                            "sample_edges": [],
                        }
                    meta_edges_details[pair]["raw_edge_count"] += 1
                    if len(meta_edges_details[pair]["sample_edges"]) < 3:
                        meta_edges_details[pair]["sample_edges"].append(out_edge)

        # Update upstream and downstream lists
        for (u, v) in meta_edges_set:
            if v not in nodes_dict[u].downstream_scc_ids:
                nodes_dict[u].downstream_scc_ids.append(v)
            if u not in nodes_dict[v].upstream_scc_ids:
                nodes_dict[v].upstream_scc_ids.append(u)

        for n in nodes_dict.values():
            n.downstream_scc_ids.sort()
            n.upstream_scc_ids.sort()

        # Step 4: Topological Sort & Acyclicity verification via Kahn's algorithm (Heap-based O((V+E) log V))
        in_degree: Dict[str, int] = {sid: len(node.upstream_scc_ids) for sid, node in nodes_dict.items()}
        zero_in_degree = [sid for sid, deg in in_degree.items() if deg == 0]
        heapq.heapify(zero_in_degree)

        topological_order: List[str] = []
        while zero_in_degree:
            curr = heapq.heappop(zero_in_degree)
            topological_order.append(curr)

            for neighbor in nodes_dict[curr].downstream_scc_ids:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    heapq.heappush(zero_in_degree, neighbor)

        is_acyclic = (len(topological_order) == len(nodes_dict))

        # Assign topological order index
        for idx, sid in enumerate(topological_order):
            nodes_dict[sid].topological_order = idx

        edges_list = [
            meta_edges_details[(u, v)]
            for (u, v) in sorted(meta_edges_set)
        ]

        return CondensationDAG(
            dag_id=dag_id,
            nodes=nodes_dict,
            edges=edges_list,
            is_acyclic=is_acyclic,
            topological_ordering=topological_order,
            revision=1,
        )
