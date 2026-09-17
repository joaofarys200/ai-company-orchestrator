from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .contract_index import ContractReverseIndex
from .dependency_index import DependencyReverseIndex
from .file_index import FileReverseIndex
from .models import ContractRecord, FileRecord, RuntimeRecord, SymbolRecord, TaskRecord
from .runtime_index import RuntimeReverseIndex
from .symbol_index import SymbolReverseIndex
from .task_index import TaskReverseIndex


class IndexManager:
    """Coordinates all reverse indexes for cross-index queries without full scans."""

    def __init__(self) -> None:
        self.symbols = SymbolReverseIndex()
        self.files = FileReverseIndex()
        self.dependencies = DependencyReverseIndex()
        self.contracts = ContractReverseIndex()
        self.tasks = TaskReverseIndex()
        self.runtimes = RuntimeReverseIndex()

    def index_file(self, file_rec: FileRecord, symbols: Optional[List[SymbolRecord]] = None) -> None:
        self.files.add_file(file_rec)
        if symbols:
            for sym in symbols:
                self.symbols.add_symbol(sym)

    def find_consumers_for_file(self, file_path: str) -> List[str]:
        file_rec = self.files.get_file(file_path)
        if not file_rec:
            return []
        all_consumers: Set[str] = set()
        for sym_id in file_rec.symbols:
            all_consumers.update(self.symbols.get_consumers(sym_id))
        return sorted(list(all_consumers))

    def find_contracts_impacted_by_symbol(self, symbol_id: str) -> List[str]:
        direct = set(self.symbols.get_contracts(symbol_id))
        consumers = self.symbols.get_consumers(symbol_id)
        for c in consumers:
            direct.update(self.symbols.get_contracts(c))
        return sorted(list(direct))

    def find_tasks_for_file(self, file_path: str) -> List[str]:
        return self.tasks.get_tasks_for_file(file_path)

    def find_affected_services_for_symbols(self, symbol_ids: List[str]) -> List[str]:
        services: Set[str] = set()
        for sid in symbol_ids:
            sym = self.symbols.get_symbol(sid)
            if sym:
                services.add(sym.shard_id)
            for consumer_id in self.symbols.get_consumers(sid):
                csym = self.symbols.get_symbol(consumer_id)
                if csym:
                    services.add(csym.shard_id)
        return sorted(list(services))

    def get_index_versions(self) -> Dict[str, int]:
        return {
            "symbols": self.symbols.revision,
            "files": self.files.revision,
            "dependencies": self.dependencies.revision,
            "contracts": self.contracts.revision,
            "tasks": self.tasks.revision,
            "runtimes": self.runtimes.revision,
        }

    def get_index_summary(self) -> Dict[str, Any]:
        return {
            "total_symbols": self.symbols.size(),
            "total_files": self.files.size(),
            "total_dependencies": self.dependencies.size(),
            "total_contracts": self.contracts.size(),
            "total_tasks": self.tasks.size(),
            "total_runtimes": self.runtimes.size(),
            "revisions": self.get_index_versions(),
        }

    def clear_all(self) -> None:
        self.symbols.clear()
        self.files.clear()
        self.dependencies.clear()
        self.contracts.clear()
        self.tasks.clear()
        self.runtimes.clear()
