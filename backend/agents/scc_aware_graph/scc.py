from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .kosaraju import KosarajuSCC
from .models import StronglyConnectedComponent
from .tarjan import TarjanSCC


class SCCDetector:
    """Detects strongly connected components and builds rich architectural metadata."""

    @classmethod
    def detect_sccs(
        cls,
        nodes: List[str],
        edges: List[Dict[str, Any]],
        algorithm: str = "tarjan",
        node_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[StronglyConnectedComponent]:
        node_meta = node_metadata or {}

        # Build adjacency
        adjacency: Dict[str, List[str]] = {n: [] for n in nodes}
        incoming_adj: Dict[str, List[str]] = {n: [] for n in nodes}
        edge_map: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for edge in edges:
            src = edge.get("source") or edge.get("src")
            tgt = edge.get("target") or edge.get("dst")
            if src and tgt:
                adjacency.setdefault(src, []).append(tgt)
                adjacency.setdefault(tgt, [])
                incoming_adj.setdefault(tgt, []).append(src)
                incoming_adj.setdefault(src, [])
                edge_map[(src, tgt)] = edge


        # Select algorithm
        if algorithm.lower() == "kosaraju":
            raw_components = KosarajuSCC.find_sccs(adjacency)
        else:
            raw_components = TarjanSCC.find_sccs(adjacency)

        # Build node to component ID mapping
        node_to_comp_idx: Dict[str, int] = {}
        for idx, comp in enumerate(raw_components):
            for n in comp:
                node_to_comp_idx[n] = idx

        scc_objects: List[StronglyConnectedComponent] = []

        for idx, comp_nodes in enumerate(raw_components):
            scc_id = f"scc_{idx:03d}_{comp_nodes[0]}"
            comp_set = set(comp_nodes)

            internal_edges: List[Dict[str, Any]] = []
            incoming_edges: List[Dict[str, Any]] = []
            outgoing_edges: List[Dict[str, Any]] = []

            entry_points: Set[str] = set()
            exit_points: Set[str] = set()

            services: Set[str] = set()
            languages: Set[str] = set()
            partitions: Set[str] = set()

            has_self_loop = False

            for n in comp_nodes:
                meta = node_meta.get(n, {})
                if "service" in meta:
                    services.add(meta["service"])
                elif "shard_id" in meta:
                    services.add(meta["shard_id"])
                else:
                    # Infer service from node prefix
                    if n.startswith(("fe_", "frontend")):
                        services.add("frontend")
                    elif n.startswith(("be_", "backend")):
                        services.add("backend")
                    elif n.startswith("worker"):
                        services.add("workers")
                    else:
                        services.add("shared")

                if "language" in meta:
                    languages.add(meta["language"])
                elif n.endswith((".ts", ".tsx")) or "ts" in n.lower():
                    languages.add("typescript")
                else:
                    languages.add("python")

                if "partition_id" in meta:
                    partitions.add(meta["partition_id"])

                # Check outgoing
                for tgt in adjacency.get(n, []):
                    edge_data = edge_map.get((n, tgt), {"source": n, "target": tgt, "edge_type": "depends"})
                    if tgt in comp_set:
                        internal_edges.append(edge_data)
                        if tgt == n:
                            has_self_loop = True
                    else:
                        outgoing_edges.append(edge_data)
                        exit_points.add(n)

            # Check incoming via precomputed incoming adjacency O(deg^-(comp))
            for n in comp_nodes:
                for src in incoming_adj.get(n, []):
                    if src not in comp_set:
                        edge_data = edge_map.get((src, n), {"source": src, "target": n, "edge_type": "depends"})
                        incoming_edges.append(edge_data)
                        entry_points.add(n)


            size = len(comp_nodes)
            max_possible_edges = size * (size - 1) if size > 1 else 1
            density = round(len(internal_edges) / max_possible_edges, 4) if size > 1 else (1.0 if has_self_loop else 0.0)
            is_cycle = size > 1 or has_self_loop

            # Hash for state integrity
            hash_input = f"{scc_id}:{sorted(comp_nodes)}:{len(internal_edges)}:{density}"
            state_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

            scc_obj = StronglyConnectedComponent(
                scc_id=scc_id,
                nodes=sorted(comp_nodes),
                edges_internal=internal_edges,
                incoming_edges=incoming_edges,
                outgoing_edges=outgoing_edges,
                size=size,
                density=density,
                entry_points=sorted(list(entry_points)),
                exit_points=sorted(list(exit_points)),
                state_hash=state_hash,
                partition_ids=sorted(list(partitions)),
                languages=sorted(list(languages)),
                services=sorted(list(services)),
                is_cycle=is_cycle,
            )
            scc_objects.append(scc_obj)

        return scc_objects
