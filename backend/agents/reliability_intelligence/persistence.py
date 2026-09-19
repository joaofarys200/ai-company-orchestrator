"""
Phase 72 — Persistence Layer
Serializes reliability intelligence state, decisions, and evidence.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List


class ReliabilityPersistence:
    """Manages disk persistence of decisions and calibration state."""

    def __init__(self, storage_dir: str = ".reliability_storage"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_decisions(self, filename: str, decisions: List[Dict[str, Any]]) -> str:
        path = os.path.join(self.storage_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(decisions, f, indent=2)
        return path

    def load_decisions(self, filename: str) -> List[Dict[str, Any]]:
        path = os.path.join(self.storage_dir, filename)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
