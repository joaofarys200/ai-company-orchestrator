from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from .index_manager import IndexManager
from .loader import LazyStateLoader
from .models import ContractRecord, FileRecord, SymbolRecord


class StateFabricQueryEngine:
    """Thread-safe, read-only query engine for modular state with lazy-loading fallbacks."""

    def __init__(self, index_manager: IndexManager, loader: LazyStateLoader, max_workers: int = 8) -> None:
        self.indexes = index_manager
        self.loader = loader
        self.max_workers = max_workers

    def query_symbol(self, symbol_id: str) -> Optional[SymbolRecord]:
        sym = self.indexes.symbols.get_symbol(symbol_id)
        if not sym:
            sym = self.loader.load_symbol(symbol_id)
        return sym

    def query_file(self, file_path: str) -> Optional[FileRecord]:
        f = self.indexes.files.get_file(file_path)
        if not f:
            f = self.loader.load_file_state(file_path)
        return f

    def query_consumers(self, symbol_id: str) -> List[str]:
        return self.indexes.symbols.get_consumers(symbol_id)

    def query_contracts(self, symbol_id: str) -> List[str]:
        return self.indexes.symbols.get_contracts(symbol_id)

    def query_tasks_for_file(self, file_path: str) -> List[str]:
        return self.indexes.tasks.get_tasks_for_file(file_path)

    def query_contract(self, contract_id: str) -> Optional[ContractRecord]:
        c = self.indexes.contracts.get_contract(contract_id)
        if not c:
            c = self.loader.load_contract(contract_id)
        return c

    def query_cross_service_impact(self, symbol_id: str) -> List[str]:
        return self.indexes.find_affected_services_for_symbols([symbol_id])

    def execute_concurrent_queries(self, queries: List[Tuple[str, str]]) -> List[Any]:
        """Execute a batch of read-only queries in parallel without lock contention."""
        def run_single(q: Tuple[str, str]) -> Any:
            q_type, param = q
            if q_type == "symbol":
                return self.query_symbol(param)
            elif q_type == "file":
                return self.query_file(param)
            elif q_type == "consumers":
                return self.query_consumers(param)
            elif q_type == "contract":
                return self.query_contract(param)
            elif q_type == "tasks":
                return self.query_tasks_for_file(param)
            return None

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(queries) or 1)) as executor:
            return list(executor.map(run_single, queries))
