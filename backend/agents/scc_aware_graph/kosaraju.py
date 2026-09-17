from __future__ import annotations

from typing import Dict, List, Set


class KosarajuSCC:
    """Deterministic implementation of Kosaraju's two-pass algorithm for SCC detection."""

    @classmethod
    def find_sccs(cls, adjacency: Dict[str, List[str]]) -> List[List[str]]:
        # Ensure all referenced nodes exist
        full_adj: Dict[str, List[str]] = {k: list(v) for k, v in adjacency.items()}
        for targets in adjacency.values():
            for t in targets:
                if t not in full_adj:
                    full_adj[t] = []

        sorted_nodes = sorted(full_adj.keys())
        for k in sorted_nodes:
            full_adj[k] = sorted(list(set(full_adj[k])))

        # Step 1: Forward DFS to record finish order
        visited: Set[str] = set()
        order: List[str] = []

        def forward_dfs(u: str) -> None:
            visited.add(u)
            for v in full_adj[u]:
                if v not in visited:
                    forward_dfs(v)
            order.append(u)

        for node in sorted_nodes:
            if node not in visited:
                forward_dfs(node)

        # Step 2: Transpose graph (reverse edges)
        transposed: Dict[str, List[str]] = {k: [] for k in sorted_nodes}
        for u, neighbors in full_adj.items():
            for v in neighbors:
                transposed[v].append(u)
        for k in transposed:
            transposed[k].sort()

        # Step 3: Reverse DFS in reverse finishing order
        visited.clear()
        sccs: List[List[str]] = []

        def reverse_dfs(u: str, comp: List[str]) -> None:
            visited.add(u)
            comp.append(u)
            for v in transposed[u]:
                if v not in visited:
                    reverse_dfs(v, comp)

        while order:
            node = order.pop()
            if node not in visited:
                comp: List[str] = []
                reverse_dfs(node, comp)
                sccs.append(sorted(comp))

        sccs.sort(key=lambda c: c[0])
        return sccs
