"""
Phase 71 — Production Operations Persistence
Serializes operational snapshots, ledgers, and incident logs to disk.
"""

from __future__ import annotations

import json
import os
from enum import Enum
from typing import Any, Dict, List


def _sanitize(obj: Any) -> Any:
    """Recursively converts enums, dataclasses, and objects to JSON-serializable primitives."""
    if hasattr(obj, "to_dict"):
        return _sanitize(obj.to_dict())
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_sanitize(v) for v in obj]
    return obj


class OperationsPersistence:
    """Handles JSON disk persistence for Phase 71 operational governance data."""

    def __init__(self, storage_dir: str = "docs"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_json(self, filename: str, data: Any) -> str:
        filepath = os.path.join(self.storage_dir, filename)
        sanitized = _sanitize(data)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=2)
        return filepath

    def load_json(self, filename: str) -> Any:
        filepath = os.path.join(self.storage_dir, filename)
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
