from __future__ import annotations

from typing import Dict, List, Optional, Set

from .index import BaseReverseIndex
from .models import SymbolRecord


class SymbolReverseIndex(BaseReverseIndex):
    """Reverse index for symbol-to-consumer and dependency resolution in O(1)."""

    def __init__(self) -> None:
        super().__init__("SymbolReverseIndex")
        self._symbols: Dict[str, SymbolRecord] = {}
        self._consumers: Dict[str, Set[str]] = {}
        self._dependencies: Dict[str, Set[str]] = {}
        self._symbol_contracts: Dict[str, Set[str]] = {}
        self._name_to_ids: Dict[str, Set[str]] = {}

    def add_symbol(self, symbol: SymbolRecord) -> None:
        self._symbols[symbol.symbol_id] = symbol
        self._name_to_ids.setdefault(symbol.name, set()).add(symbol.symbol_id)

        if symbol.symbol_id not in self._consumers:
            self._consumers[symbol.symbol_id] = set()
        for c in symbol.consumers:
            self._consumers[symbol.symbol_id].add(c)

        if symbol.symbol_id not in self._dependencies:
            self._dependencies[symbol.symbol_id] = set()
        for d in symbol.dependencies:
            self._dependencies[symbol.symbol_id].add(d)

        if symbol.symbol_id not in self._symbol_contracts:
            self._symbol_contracts[symbol.symbol_id] = set()
        for ct in symbol.contracts:
            self._symbol_contracts[symbol.symbol_id].add(ct)

        self.bump_revision()

    def remove_symbol(self, symbol_id: str) -> bool:
        symbol = self._symbols.pop(symbol_id, None)
        if not symbol:
            return False

        if symbol.name in self._name_to_ids:
            self._name_to_ids[symbol.name].discard(symbol_id)
            if not self._name_to_ids[symbol.name]:
                del self._name_to_ids[symbol.name]

        self._consumers.pop(symbol_id, None)
        self._dependencies.pop(symbol_id, None)
        self._symbol_contracts.pop(symbol_id, None)

        # Remove from other symbols' consumer/dependency lists
        for cset in self._consumers.values():
            cset.discard(symbol_id)
        for dset in self._dependencies.values():
            dset.discard(symbol_id)

        self.bump_revision()
        return True

    def get_symbol(self, symbol_id: str) -> Optional[SymbolRecord]:
        return self._symbols.get(symbol_id)

    def get_symbols_by_name(self, name: str) -> List[SymbolRecord]:
        ids = self._name_to_ids.get(name, set())
        return [self._symbols[sid] for sid in ids if sid in self._symbols]

    def get_consumers(self, symbol_id: str) -> List[str]:
        return sorted(list(self._consumers.get(symbol_id, set())))

    def get_dependencies(self, symbol_id: str) -> List[str]:
        return sorted(list(self._dependencies.get(symbol_id, set())))

    def get_contracts(self, symbol_id: str) -> List[str]:
        return sorted(list(self._symbol_contracts.get(symbol_id, set())))

    def add_consumer(self, symbol_id: str, consumer_id: str) -> None:
        self._consumers.setdefault(symbol_id, set()).add(consumer_id)
        self.bump_revision()

    def clear(self) -> None:
        self._symbols.clear()
        self._consumers.clear()
        self._dependencies.clear()
        self._symbol_contracts.clear()
        self._name_to_ids.clear()
        self.bump_revision()

    def size(self) -> int:
        return len(self._symbols)
