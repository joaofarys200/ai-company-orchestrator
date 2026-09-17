from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional, Set, Tuple

from .graph import SymbolDependencyGraph
from .models import SymbolEdge, SymbolNode, SymbolSCC


class SymbolSCCDetector:
    """Detects Strongly Connected Components (SCCs) at the atomic symbol level.

    Uses an iterative version of Tarjan's algorithm with deterministic ordering
    to prevent recursion limit crashes on large codebases.
    """

    def detect_sccs(self, graph: SymbolDependencyGraph) -> List[SymbolSCC]:
        """Detect all symbol-level SCCs deterministically."""
        index = 0
        indices: Dict[str, int] = {}
        lowlinks: Dict[str, int] = {}
        on_stack: Dict[str, bool] = {}
        stack: List[str] = []
        sccs_raw: List[List[str]] = []

        # Deterministic node order
        sorted_nodes = sorted(graph.nodes.keys())

        for root in sorted_nodes:
            if root not in indices:
                # Iterative DFS simulation
                # Call stack stores (node, neighbor_index, list_of_neighbors)
                neighbors = sorted([
                    e.target_symbol for e in graph.get_outgoing_edges(root)
                    if e.target_symbol in graph.nodes
                ])
                call_stack = [(root, 0, neighbors)]
                indices[root] = index
                lowlinks[root] = index
                index += 1
                stack.append(root)
                on_stack[root] = True

                while call_stack:
                    u, i, u_neighbors = call_stack[-1]

                    if i < len(u_neighbors):
                        v = u_neighbors[i]
                        # Advance iterator for node u
                        call_stack[-1] = (u, i + 1, u_neighbors)

                        if v not in indices:
                            # Forward edge to unvisited node v
                            v_neighbors = sorted([
                                e.target_symbol for e in graph.get_outgoing_edges(v)
                                if e.target_symbol in graph.nodes
                            ])
                            indices[v] = index
                            lowlinks[v] = index
                            index += 1
                            stack.append(v)
                            on_stack[v] = True
                            call_stack.append((v, 0, v_neighbors))
                        elif on_stack.get(v, False):
                            # Back edge to node currently on stack
                            lowlinks[u] = min(lowlinks[u], indices[v])
                    else:
                        # Post-visit completion for u
                        call_stack.pop()

                        # Propagate lowlink to caller if exists
                        if call_stack:
                            caller = call_stack[-1][0]
                            lowlinks[caller] = min(lowlinks[caller], lowlinks[u])

                        # If u is root of an SCC, pop the component
                        if lowlinks[u] == indices[u]:
                            component: List[str] = []
                            while stack:
                                w = stack.pop()
                                on_stack[w] = False
                                component.append(w)
                                if w == u:
                                    break
                            sccs_raw.append(component)

        # Build fully qualified SymbolSCC objects
        return self._build_scc_objects(graph, sccs_raw)

    def _build_scc_objects(self, graph: SymbolDependencyGraph, raw_sccs: List[List[str]]) -> List[SymbolSCC]:
        """Convert raw symbol ID groupings into rich, deterministically hashed SymbolSCC entities."""
        results: List[SymbolSCC] = []

        for raw_members in raw_sccs:
            symbols = sorted(raw_members)
            symbol_set = set(symbols)

            # Files involved
            files_set: Set[str] = set()
            languages_set: Set[str] = set()
            services_set: Set[str] = set()

            for sym_id in symbols:
                node = graph.nodes.get(sym_id)
                if node:
                    norm_file = node.file_id.replace("\\", "/")
                    files_set.add(norm_file)
                    if node.language:
                        languages_set.add(node.language)
                    # Inferred service: e.g. "backend", "frontend", or top directory
                    parts = norm_file.split("/")
                    service = parts[0] if parts else "default"
                    services_set.add(service)

            # Edges classification
            edges_internal: List[Dict[str, Any]] = []
            edges_external: List[Dict[str, Any]] = []
            has_self_loop = False

            for sym_id in symbols:
                for edge in graph.get_outgoing_edges(sym_id):
                    edge_dict = edge.to_dict()
                    if edge.target_symbol in symbol_set:
                        edges_internal.append(edge_dict)
                        if edge.source_symbol == edge.target_symbol:
                            has_self_loop = True
                    else:
                        edges_external.append(edge_dict)

            size = len(symbols)
            is_cycle = size > 1 or has_self_loop

            # Density
            if size > 1:
                density = len(edges_internal) / (size * (size - 1))
            else:
                density = 1.0 if has_self_loop else 0.0

            # Deterministic state hash
            canonical_repr = json.dumps(
                {
                    "symbols": symbols,
                    "edges_internal": sorted(
                        [f"{e['source_symbol']}->{e['target_symbol']}:{e['edge_type']}" for e in edges_internal]
                    ),
                },
                sort_keys=True,
            )
            state_hash = hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()
            scc_id = f"scc_sym_{state_hash[:12]}"

            results.append(
                SymbolSCC(
                    scc_id=scc_id,
                    symbols=symbols,
                    files=sorted(list(files_set)),
                    edges_internal=edges_internal,
                    edges_external=edges_external,
                    size=size,
                    density=round(density, 4),
                    languages=sorted(list(languages_set)),
                    services=sorted(list(services_set)),
                    state_hash=state_hash,
                    is_cycle=is_cycle,
                )
            )

        # Sort SCCs deterministically by size desc, then scc_id asc
        results.sort(key=lambda scc: (-scc.size, scc.scc_id))
        return results
