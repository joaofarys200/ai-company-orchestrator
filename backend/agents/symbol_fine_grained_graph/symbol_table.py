from __future__ import annotations

from typing import Any, Dict, List, Optional


from .models import SymbolKind, SymbolNode


class SymbolScope:
    """Represents a lexical scope (file/module, class, or function)."""

    def __init__(self, name: str, parent: Optional[SymbolScope] = None) -> None:
        self.name = name
        self.parent = parent
        self.symbols: Dict[str, SymbolNode] = {}
        self.children: List[SymbolScope] = []

    def define(self, symbol: SymbolNode) -> None:
        self.symbols[symbol.name] = symbol

    def lookup(self, name: str) -> Optional[SymbolNode]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def lookup_local(self, name: str) -> Optional[SymbolNode]:
        return self.symbols.get(name)


class SymbolTable:
    """Scoped symbol table for a single source file."""

    def __init__(self, file_id: str) -> None:
        self.file_id = file_id.replace("\\", "/")
        self.global_scope = SymbolScope(name=f"file:{self.file_id}")
        self.current_scope = self.global_scope
        self.all_symbols: Dict[str, SymbolNode] = {}
        self.exports: Dict[str, SymbolNode] = {}
        self.imports: Dict[str, Dict[str, Any]] = {}

    def enter_scope(self, name: str) -> SymbolScope:
        new_scope = SymbolScope(name=name, parent=self.current_scope)
        self.current_scope.children.append(new_scope)
        self.current_scope = new_scope
        return new_scope

    def exit_scope(self) -> None:
        if self.current_scope.parent:
            self.current_scope = self.current_scope.parent

    def add_symbol(self, symbol: SymbolNode) -> None:
        self.current_scope.define(symbol)
        self.all_symbols[symbol.symbol_id] = symbol
        if symbol.exported:
            self.exports[symbol.name] = symbol

    def register_import(
        self,
        local_name: str,
        imported_name: str,
        source_module: str,
        is_type_only: bool = False,
    ) -> None:
        self.imports[local_name] = {
            "imported_name": imported_name,
            "source_module": source_module,
            "is_type_only": is_type_only,
        }

    def resolve(self, name: str) -> Optional[SymbolNode]:
        return self.current_scope.lookup(name)

    def get_exported_symbols(self) -> List[SymbolNode]:
        return list(self.exports.values())

    def get_all_symbols(self) -> List[SymbolNode]:
        return list(self.all_symbols.values())
