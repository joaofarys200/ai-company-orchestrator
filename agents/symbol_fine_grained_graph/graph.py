from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .models import SymbolEdge, SymbolEdgeType, SymbolNode


class SymbolDependencyGraph:
    """Fine-grained graph of individual symbol nodes and their semantic edges.

    Maintains dual-layer compatibility with file-level graphs:
    every file edge (F1 -> F2) is dynamically grounded by the concrete
    set of symbol edges between symbols in F1 and F2.
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, SymbolNode] = {}
        self.edges: List[SymbolEdge] = []
        # Adjacency: source_symbol_id -> list of outgoing SymbolEdge
        self.adjacency: Dict[str, List[SymbolEdge]] = {}
        # Reverse adjacency: target_symbol_id -> list of incoming SymbolEdge
        self.reverse_adjacency: Dict[str, List[SymbolEdge]] = {}
        # file_id -> set of symbol_ids
        self.file_to_symbols: Dict[str, Set[str]] = {}
        # (src_file, dst_file) -> list of grounding SymbolEdge
        self._file_edge_index: Dict[Tuple[str, str], List[SymbolEdge]] = {}

    def add_node(self, node: SymbolNode) -> None:
        """Add or update a symbol node in the graph."""
        self.nodes[node.symbol_id] = node
        norm_file = node.file_id.replace("\\", "/")
        if norm_file not in self.file_to_symbols:
            self.file_to_symbols[norm_file] = set()
        self.file_to_symbols[norm_file].add(node.symbol_id)

        if node.symbol_id not in self.adjacency:
            self.adjacency[node.symbol_id] = []
        if node.symbol_id not in self.reverse_adjacency:
            self.reverse_adjacency[node.symbol_id] = []

    def add_edge(self, edge: SymbolEdge) -> None:
        """Add a directed symbol edge and update grounding file-edge index."""
        self.edges.append(edge)

        if edge.source_symbol not in self.adjacency:
            self.adjacency[edge.source_symbol] = []
        self.adjacency[edge.source_symbol].append(edge)

        if edge.target_symbol not in self.reverse_adjacency:
            self.reverse_adjacency[edge.target_symbol] = []
        self.reverse_adjacency[edge.target_symbol].append(edge)

        # Grounding file edge index
        src_file = self._get_file_for_symbol(edge.source_symbol)
        dst_file = self._get_file_for_symbol(edge.target_symbol)
        if src_file and dst_file and src_file != dst_file:
            pair = (src_file, dst_file)
            if pair not in self._file_edge_index:
                self._file_edge_index[pair] = []
            self._file_edge_index[pair].append(edge)

    def _get_file_for_symbol(self, symbol_id: str) -> Optional[str]:
        """Extract the canonical file_id from a symbol_id or registered node."""
        if symbol_id in self.nodes:
            return self.nodes[symbol_id].file_id.replace("\\", "/")
        if "::" in symbol_id:
            file_part = symbol_id.split("::")[0].replace("\\", "/")
            if file_part in self.file_to_symbols:
                return file_part
            # Try matching known file paths
            return file_part
        return None

    def remove_node(self, symbol_id: str) -> None:
        """Remove a symbol node and its associated edges."""
        if symbol_id not in self.nodes:
            return

        node = self.nodes.pop(symbol_id)
        norm_file = node.file_id.replace("\\", "/")
        if norm_file in self.file_to_symbols:
            self.file_to_symbols[norm_file].discard(symbol_id)

        # Remove outgoing edges
        outgoing = self.adjacency.pop(symbol_id, [])
        for edge in outgoing:
            if edge.target_symbol in self.reverse_adjacency:
                self.reverse_adjacency[edge.target_symbol] = [
                    e for e in self.reverse_adjacency[edge.target_symbol] if e.source_symbol != symbol_id
                ]

        # Remove incoming edges
        incoming = self.reverse_adjacency.pop(symbol_id, [])
        for edge in incoming:
            if edge.source_symbol in self.adjacency:
                self.adjacency[edge.source_symbol] = [
                    e for e in self.adjacency[edge.source_symbol] if e.target_symbol != symbol_id
                ]

        # Rebuild file edge index for touched files
        self._rebuild_file_edge_index()

    def remove_edge(self, source_symbol: str, target_symbol: str, edge_type: Optional[SymbolEdgeType] = None) -> None:
        """Remove a specific edge or edge type between two symbols."""
        if source_symbol in self.adjacency:
            self.adjacency[source_symbol] = [
                e for e in self.adjacency[source_symbol]
                if not (e.target_symbol == target_symbol and (edge_type is None or e.edge_type == edge_type))
            ]
        if target_symbol in self.reverse_adjacency:
            self.reverse_adjacency[target_symbol] = [
                e for e in self.reverse_adjacency[target_symbol]
                if not (e.source_symbol == source_symbol and (edge_type is None or e.edge_type == edge_type))
            ]
        self.edges = [
            e for e in self.edges
            if not (e.source_symbol == source_symbol and e.target_symbol == target_symbol and (edge_type is None or e.edge_type == edge_type))
        ]
        self._rebuild_file_edge_index()

    def _rebuild_file_edge_index(self) -> None:
        """Reconstruct the derived file-level dependency index."""
        self._file_edge_index.clear()
        for edge in self.edges:
            src_file = self._get_file_for_symbol(edge.source_symbol)
            dst_file = self._get_file_for_symbol(edge.target_symbol)
            if src_file and dst_file and src_file != dst_file:
                pair = (src_file, dst_file)
                if pair not in self._file_edge_index:
                    self._file_edge_index[pair] = []
                self._file_edge_index[pair].append(edge)

    def get_grounding_symbols(self, file_a: str, file_b: str) -> List[SymbolEdge]:
        """Return the concrete symbol edges that substantiate the file dependency file_a -> file_b."""
        norm_a = file_a.replace("\\", "/")
        norm_b = file_b.replace("\\", "/")
        return self._file_edge_index.get((norm_a, norm_b), [])

    def get_derived_file_edges(self) -> List[Tuple[str, str, int]]:
        """Return all derived file-level edges (source_file, target_file, grounding_edge_count)."""
        return [(src, dst, len(edges)) for (src, dst), edges in self._file_edge_index.items()]

    def get_file_dependencies(self, file_id: str) -> Set[str]:
        """Return all files that file_id depends on."""
        norm_file = file_id.replace("\\", "/")
        return {dst for (src, dst) in self._file_edge_index.keys() if src == norm_file}

    def get_file_dependents(self, file_id: str) -> Set[str]:
        """Return all files that depend on file_id."""
        norm_file = file_id.replace("\\", "/")
        return {src for (src, dst) in self._file_edge_index.keys() if dst == norm_file}

    def get_outgoing_edges(self, symbol_id: str) -> List[SymbolEdge]:
        """Get outgoing symbol edges."""
        return self.adjacency.get(symbol_id, [])

    def get_incoming_edges(self, symbol_id: str) -> List[SymbolEdge]:
        """Get incoming symbol edges."""
        return self.reverse_adjacency.get(symbol_id, [])

    def to_dict(self) -> Dict[str, Any]:
        """Serialize graph summary."""
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "file_count": len(self.file_to_symbols),
            "derived_file_edge_count": len(self._file_edge_index),
        }
