from __future__ import annotations

from typing import Dict, Optional, Tuple


class AliasResolver:
    """Tracks and resolves lexical symbol aliases across imports, re-exports, and local bindings."""

    def __init__(self) -> None:
        # file_id -> {alias_name: canonical_target}
        self.file_aliases: Dict[str, Dict[str, str]] = {}

    def register_alias(self, file_id: str, alias_name: str, canonical_target: str) -> None:
        """Register an alias mapping in a given file."""
        norm_file = file_id.replace("\\", "/")
        if norm_file not in self.file_aliases:
            self.file_aliases[norm_file] = {}
        self.file_aliases[norm_file][alias_name] = canonical_target

    def resolve_alias(self, file_id: str, symbol_name: str, max_hops: int = 10) -> str:
        """Trace an alias chain to its canonical representation."""
        norm_file = file_id.replace("\\", "/")
        current = symbol_name
        hops = 0

        while hops < max_hops:
            aliases = self.file_aliases.get(norm_file, {})
            if current in aliases:
                next_sym = aliases[current]
                if next_sym == current:
                    break
                current = next_sym
                hops += 1
            else:
                break

        return current

    def get_aliases_for_file(self, file_id: str) -> Dict[str, str]:
        """Return all registered aliases for a file."""
        return dict(self.file_aliases.get(file_id.replace("\\", "/"), {}))

    def clear(self) -> None:
        """Clear all registered aliases."""
        self.file_aliases.clear()
