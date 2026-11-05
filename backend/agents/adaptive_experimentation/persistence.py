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
        records = self.load_all_sessions()
        records[session.session_id] = session.to_dict()

        temp_path = self.base_dir / "sessions.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        os.replace(temp_path, self.sessions_file)

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

        temp_path = self.base_dir / "audit_ledger.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)
        os.replace(temp_path, self.audit_ledger_file)
