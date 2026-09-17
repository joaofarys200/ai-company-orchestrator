from __future__ import annotations

from typing import Any, Dict, List, Set



class TarjanSCC:
    """Iterative, deterministic implementation of Tarjan's strongly connected components algorithm.

    Uses an explicit heap call stack to handle massive cyclic graphs (up to 10M LOC / 100k+ nodes)
    without encountering Python recursion limits.
    """

    @classmethod
    def find_sccs(cls, adjacency: Dict[str, List[str]]) -> List[List[str]]:
        """Finds all strongly connected components in the directed graph with deterministic ordering."""
        # Ensure all referenced nodes exist in adjacency dictionary
        full_adj: Dict[str, List[str]] = {k: list(v) for k, v in adjacency.items()}
        for targets in adjacency.values():
            for t in targets:
                if t not in full_adj:
                    full_adj[t] = []

        # Sort nodes and edges lexicographically for platform-independent determinism
        sorted_nodes = sorted(full_adj.keys())
        for k in sorted_nodes:
            full_adj[k] = sorted(list(set(full_adj[k])))

        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        on_stack: Set[str] = set()
        stack: List[str] = []
        index_counter = 0
        sccs: List[List[str]] = []

        for root in sorted_nodes:
            if root in indices:
                continue

            # Call stack entry: [node, neighbors, neighbor_index]
            call_stack: List[List[Any]] = [[root, full_adj[root], 0]]
            indices[root] = index_counter
            lowlink[root] = index_counter
            index_counter += 1
            stack.append(root)
            on_stack.add(root)

            while call_stack:
                frame = call_stack[-1]
                v = frame[0]
                neighbors = frame[1]
                n_idx = frame[2]

                if n_idx < len(neighbors):
                    w = neighbors[n_idx]
                    frame[2] += 1

                    if w not in indices:
                        indices[w] = index_counter
                        lowlink[w] = index_counter
                        index_counter += 1
                        stack.append(w)
                        on_stack.add(w)
                        call_stack.append([w, full_adj[w], 0])
                    elif w in on_stack:
                        lowlink[v] = min(lowlink[v], indices[w])
                else:
                    call_stack.pop()

                    if lowlink[v] == indices[v]:
                        component: List[str] = []
                        while True:
                            w = stack.pop()
                            on_stack.remove(w)
                            component.append(w)
                            if w == v:
                                break
                        sccs.append(sorted(component))

                    if call_stack:
                        parent = call_stack[-1][0]
                        lowlink[parent] = min(lowlink[parent], lowlink[v])

        # Sort SCCs deterministically by their first (canonical) element
        sccs.sort(key=lambda comp: comp[0])
        return sccs
