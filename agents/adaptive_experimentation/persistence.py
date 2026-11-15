"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: persistence.py
Atomic persistence store, crash recovery, and investigation audit ledgers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from backend.atomic_io import atomic_write_json
from .models import InvestigationSession


class AdaptiveExperimentStore:
    """
    Durable filesystem storage for adaptive investigation sessions and audit records.
    """

    def __init__(self, base_dir: str = ".jarvis/adaptive_experimentation"):
        self.base_dir = Path(base_dir)
        self.sessions_file = self.base_dir / "sessions.json"
        self.audit_ledger_file = self.base_dir / "audit_ledger.json"

        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: InvestigationSession) -> None:
        """Atomically persist an investigation session."""
        from backend.atomic_io import atomic_write_json

        records = self.load_all_sessions()
        records[session.session_id] = session.to_dict()
        atomic_write_json(self.sessions_file, records, indent=2)

    def load_all_sessions(self) -> Dict[str, Dict]:
        """Load all persisted sessions from disk."""
        if not self.sessions_file.exists():
            return {}
        try:
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve a specific investigation session dictionary."""
        return self.load_all_sessions().get(session_id)

    def record_audit_entry(self, entry: Dict) -> None:
        """Append an entry to the audit ledger."""
        ledger = []
        if self.audit_ledger_file.exists():
            try:
                with open(self.audit_ledger_file, "r", encoding="utf-8") as f:
                    ledger = json.load(f)
            except Exception:
                ledger = []
        ledger.append(entry)
        atomic_write_json(self.audit_ledger_file, ledger, indent=2)
