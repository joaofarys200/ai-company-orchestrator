from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from .models import SymbolEdge, SymbolNode


class SymbolSecurityViolation(Exception):
    """Raised when an untrusted or poisoned symbol / edge payload is detected."""
    pass


class SymbolSecuritySentinel:
    """Enforces provenance, validates against fake symbol injection, poisoned ASTs, and traversal attacks."""

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = (workspace_root or os.getcwd()).replace("\\", "/").rstrip("/")
        self.violations: List[Dict[str, Any]] = []

    def validate_file_path(self, file_path: str) -> bool:
        """Prevent path traversal and directory escape."""
        norm = file_path.replace("\\", "/")
        if ".." in norm.split("/"):
            self._record_violation("PATH_TRAVERSAL_DETECTED", {"path": file_path})
            return False

        if os.path.isabs(norm):
            # If absolute, verify it stays within workspace_root
            if not norm.startswith(self.workspace_root):
                self._record_violation("WORKSPACE_ESCAPE_DETECTED", {"path": file_path, "root": self.workspace_root})
                return False

        return True

    def validate_symbol_node(self, node: SymbolNode) -> bool:
        """Validate atomic symbol node integrity and provenance."""
        # 1. Path check
        if not self.validate_file_path(node.file_id):
            return False

        # 2. Check symbol_id format: expected 'file_id::qualified_name'
        if "::" not in node.symbol_id:
            self._record_violation("MALFORMED_SYMBOL_ID", {"symbol_id": node.symbol_id})
            return False

        # 3. Check for fake symbol injection / malicious script injection in symbol name
        dangerous_tokens = ["<script", "javascript:", "__proto__", "constructor.prototype", ";--", "DROP TABLE"]
        for token in dangerous_tokens:
            if token in node.name.lower() or token in node.qualified_name.lower():
                self._record_violation("DANGEROUS_SYMBOL_INJECTION", {"symbol_id": node.symbol_id, "token": token})
                return False

        # 4. Provenance check
        if not isinstance(node.provenance, dict):
            self._record_violation("INVALID_PROVENANCE_STRUCTURE", {"symbol_id": node.symbol_id})
            return False

        return True

    def validate_symbol_edge(self, edge: SymbolEdge) -> bool:
        """Validate edge provenance, target integrity, and confidence bounds."""
        # 1. Source and Target must not be empty
        if not edge.source_symbol or not edge.target_symbol:
            self._record_violation("EMPTY_EDGE_SYMBOLS", {"edge": str(edge)})
            return False

        # 2. Confidence must be in [0.0, 1.0]
        if not (0.0 <= edge.confidence <= 1.0):
            self._record_violation("INVALID_CONFIDENCE_VALUE", {"confidence": edge.confidence})
            return False

        # 3. Prevent fake re-export hijacking
        if edge.edge_type.value == "REEXPORTS":
            if "::" not in edge.target_symbol and not edge.target_symbol.startswith("."):
                # Global arbitrary string hijacking
                if edge.target_symbol in ("eval", "Function", "exec", "__import__"):
                    self._record_violation("REEXPORT_HIJACKING_ATTEMPT", {"target": edge.target_symbol})
                    return False

        return True

    def _record_violation(self, violation_type: str, details: Dict[str, Any]) -> None:
        """Log a detected security violation."""
        self.violations.append({
            "type": violation_type,
            "details": details,
        })
