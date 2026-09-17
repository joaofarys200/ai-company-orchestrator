from __future__ import annotations

from typing import Dict, List, Optional, Set

from .models import SymbolKind, SymbolNode


class SymbolIndex:
    """In-memory multi-index for fast symbol lookups by name, kind, file, and export status."""

    def __init__(self) -> None:
        self.symbol_to_file: Dict[str, str] = {}
        self.name_to_symbols: Dict[str, List[str]] = {}
        self.kind_to_symbols: Dict[str, List[str]] = {}
        self.language_to_symbols: Dict[str, List[str]] = {}
        self.exported_symbols: Set[str] = set()

    def index_symbol(self, sym: SymbolNode) -> None:
        """Add a symbol to all indexed dimensions."""
        self.symbol_to_file[sym.symbol_id] = sym.file_id

        # Index by short name
        if sym.name not in self.name_to_symbols:
            self.name_to_symbols[sym.name] = []
        self.name_to_symbols[sym.name].append(sym.symbol_id)

        # Index by kind
        kind_str = sym.kind.value if isinstance(sym.kind, SymbolKind) else str(sym.kind)
        if kind_str not in self.kind_to_symbols:
            self.kind_to_symbols[kind_str] = []
        self.kind_to_symbols[kind_str].append(sym.symbol_id)

        # Index by language
        if sym.language not in self.language_to_symbols:
            self.language_to_symbols[sym.language] = []
        self.language_to_symbols[sym.language].append(sym.symbol_id)

        # Exported set
        if sym.exported:
            self.exported_symbols.add(sym.symbol_id)

    def find_by_name(self, name: str) -> List[str]:
        """Lookup symbol IDs matching name."""
        return self.name_to_symbols.get(name, [])

    def find_by_kind(self, kind: SymbolKind) -> List[str]:
        """Lookup symbol IDs matching kind."""
        kind_str = kind.value if isinstance(kind, SymbolKind) else str(kind)
        return self.kind_to_symbols.get(kind_str, [])

    def find_by_language(self, lang: str) -> List[str]:
        """Lookup symbol IDs by language."""
        return self.language_to_symbols.get(lang, [])

    def is_exported(self, symbol_id: str) -> bool:
        """Check if symbol is exported."""
        return symbol_id in self.exported_symbols

    def clear(self) -> None:
        """Clear all indexes."""
        self.symbol_to_file.clear()
        self.name_to_symbols.clear()
        self.kind_to_symbols.clear()
        self.language_to_symbols.clear()
        self.exported_symbols.clear()
