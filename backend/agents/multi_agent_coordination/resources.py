"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: resources.py
Multi-granularity resource model spanning files, symbols, contracts, behaviors,
services, architectures, configurations, and protected paths.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set

from .models import ResourceGranularity


class ResourceManager:
    """Manages discoverable codebase resource identifiers and their hierarchies."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.getcwd()
        self.registered_resources: Dict[str, Dict[str, Any]] = {}

    def register_resource(
        self,
        resource_id: str,
        granularity: ResourceGranularity,
        parent_resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a coordinated resource with hierarchical ancestry."""
        norm_id = self.normalize_id(resource_id)
        entry = {
            "resource_id": norm_id,
            "granularity": granularity.value if isinstance(granularity, ResourceGranularity) else str(granularity),
            "parent_id": self.normalize_id(parent_resource_id) if parent_resource_id else None,
            "metadata": metadata or {},
        }
        self.registered_resources[norm_id] = entry
        return entry

    def normalize_id(self, raw_id: str) -> str:
        return raw_id.replace("\\", "/").strip()

    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        return self.registered_resources.get(self.normalize_id(resource_id))

    def resolve_hierarchy(self, resource_id: str) -> List[str]:
        """Return resource and all its ancestors up to the root."""
        norm_id = self.normalize_id(resource_id)
        chain = [norm_id]
        curr = norm_id
        while curr in self.registered_resources and self.registered_resources[curr].get("parent_id"):
            curr = self.registered_resources[curr]["parent_id"]
            if curr in chain:
                break
            chain.append(curr)
        return chain

    def are_overlapping(self, res_a: str, res_b: str) -> bool:
        """Determine if two resources overlap hierarchically (e.g. file and a symbol within it)."""
        norm_a = self.normalize_id(res_a)
        norm_b = self.normalize_id(res_b)
        if norm_a == norm_b:
            return True

        chain_a = set(self.resolve_hierarchy(norm_a))
        chain_b = set(self.resolve_hierarchy(norm_b))
        return bool(chain_a.intersection(chain_b))
