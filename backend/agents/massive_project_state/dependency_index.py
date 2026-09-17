from __future__ import annotations

from typing import Dict, List, Optional, Set

from .index import BaseReverseIndex


class DependencyReverseIndex(BaseReverseIndex):
    """Reverse index tracking inter-module and inter-service dependencies."""

    def __init__(self) -> None:
        super().__init__("DependencyReverseIndex")
        self._upstream: Dict[str, Set[str]] = {}    # entity -> dependencies
        self._downstream: Dict[str, Set[str]] = {}  # entity -> dependents

    def add_dependency(self, source: str, target: str) -> None:
        self._upstream.setdefault(source, set()).add(target)
        self._downstream.setdefault(target, set()).add(source)
        self.bump_revision()

    def remove_entity(self, entity: str) -> None:
        targets = self._upstream.pop(entity, set())
        for tgt in targets:
            if tgt in self._downstream:
                self._downstream[tgt].discard(entity)

        sources = self._downstream.pop(entity, set())
        for src in sources:
            if src in self._upstream:
                self._upstream[src].discard(entity)

        self.bump_revision()

    def get_dependencies(self, entity: str) -> List[str]:
        return sorted(list(self._upstream.get(entity, set())))

    def get_dependents(self, entity: str) -> List[str]:
        return sorted(list(self._downstream.get(entity, set())))

    def get_transitive_dependents(self, entity: str, max_depth: int = 5) -> List[str]:
        visited: Set[str] = set()
        queue = [(entity, 0)]

        while queue:
            current, depth = queue.pop(0)
            if depth >= max_depth:
                continue
            for downstream in self.get_dependents(current):
                if downstream not in visited and downstream != entity:
                    visited.add(downstream)
                    queue.append((downstream, depth + 1))

        return sorted(list(visited))

    def clear(self) -> None:
        self._upstream.clear()
        self._downstream.clear()
        self.bump_revision()

    def size(self) -> int:
        return len(self._upstream)
