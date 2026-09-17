from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set

from .graph import PartitionedGraphManager
from .index_manager import IndexManager
from .models import GraphEdge, TargetedSubgraph


class TargetedSubgraphExtractor:
    """Extracts mission-focused subgraphs on demand without loading full repository graph."""

    def __init__(self, index_manager: IndexManager, graph_manager: PartitionedGraphManager) -> None:
        self.indexes = index_manager
        self.graph = graph_manager

    def extract_subgraph(
        self,
        root_symbols: List[str],
        max_depth: int = 3,
        max_nodes: int = 200,
    ) -> TargetedSubgraph:
        start_time = time.perf_counter()
        subgraph_id = f"subgraph_{uuid.uuid4().hex[:8]}"

        visited_nodes: Set[str] = set(root_symbols)
        collected_edges: List[GraphEdge] = []
        direct_consumers: Set[str] = set()
        downstream_symbols: Set[str] = set()
        contracts: Set[str] = set()
        tasks: Set[str] = set()
        browser_scenarios: Set[str] = set()
        runtime_deps: Set[str] = set()

        # Step 1: Collect immediate consumers and contracts for root symbols
        for root in root_symbols:
            # Reverse index lookup in O(1)
            consumers = self.indexes.symbols.get_consumers(root)
            direct_consumers.update(consumers)

            root_contracts = self.indexes.symbols.get_contracts(root)
            contracts.update(root_contracts)

            file_path = self.indexes.files.get_file_for_symbol(root)
            if file_path:
                tasks.update(self.indexes.tasks.get_tasks_for_file(file_path))
                shard = self.indexes.files.get_file(file_path)
                if shard:
                    runtime_deps.add(shard.shard_id)

        # Step 2: Traverse graph relationships up to max_depth and max_nodes
        queue = [(sym, 0) for sym in root_symbols]
        while queue and len(visited_nodes) < max_nodes:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Outgoing edges
            for edge in self.graph.get_outgoing(current):
                collected_edges.append(edge)
                if edge.target not in visited_nodes:
                    visited_nodes.add(edge.target)
                    downstream_symbols.add(edge.target)
                    queue.append((edge.target, depth + 1))

                if edge.edge_type == "browser_validates" or "browser" in edge.target.lower():
                    browser_scenarios.add(edge.target)
                elif edge.edge_type in ("provides_contract", "consumes_contract"):
                    contracts.add(edge.target)

            # Incoming edges (consumers)
            for edge in self.graph.get_incoming(current):
                collected_edges.append(edge)
                if edge.source not in visited_nodes:
                    visited_nodes.add(edge.source)
                    downstream_symbols.add(edge.source)
                    queue.append((edge.source, depth + 1))

                if "browser" in edge.source.lower():
                    browser_scenarios.add(edge.source)

        # Step 3: Check browser scenario heuristics if none found via graph
        for root in root_symbols:
            sym = self.indexes.symbols.get_symbol(root)
            if sym and ("ui" in sym.kind.lower() or "component" in sym.kind.lower() or "page" in sym.kind.lower()):
                browser_scenarios.add(f"qa_{sym.name.lower()}_render")

        # Step 4: Resolve node metadata
        nodes_dict: Dict[str, Dict[str, Any]] = {}
        for nid in visited_nodes:
            sym_rec = self.indexes.symbols.get_symbol(nid)
            if sym_rec:
                nodes_dict[nid] = {
                    "type": "symbol",
                    "name": sym_rec.name,
                    "kind": sym_rec.kind,
                    "shard_id": sym_rec.shard_id,
                    "file_path": sym_rec.file_path,
                }
            elif nid in contracts:
                contract_rec = self.indexes.contracts.get_contract(nid)
                nodes_dict[nid] = {
                    "type": "contract",
                    "name": contract_rec.name if contract_rec else nid,
                    "shard_id": contract_rec.shard_id if contract_rec else "shared",
                }
            else:
                nodes_dict[nid] = {"type": "node", "id": nid}

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return TargetedSubgraph(
            subgraph_id=subgraph_id,
            root_symbols=root_symbols,
            nodes=nodes_dict,
            edges=collected_edges,
            direct_consumers=sorted(list(direct_consumers)),
            downstream_symbols=sorted(list(downstream_symbols)),
            contracts=sorted(list(contracts)),
            tasks=sorted(list(tasks)),
            browser_scenarios=sorted(list(browser_scenarios)),
            runtime_dependencies=sorted(list(runtime_deps)),
            extraction_time_ms=elapsed_ms,
        )
