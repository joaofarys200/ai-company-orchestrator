"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: persistence.py
Atomic persistence store, crash recovery, and diagnostic audit ledgers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from .models import DiagnosisReport


class CausalDiagnosisStore:
    """
    Durable filesystem storage for causal graphs, diagnostic hypotheses, and reports.
    Supports atomic writes and recovery across process restarts.
    """

    def __init__(self, base_dir: str = ".jarvis/causal_diagnosis"):
        self.base_dir = Path(base_dir)
        self.diagnoses_file = self.base_dir / "diagnoses.json"
        self.audit_ledger_file = self.base_dir / "audit_ledger.json"

        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_diagnosis(self, report: DiagnosisReport) -> None:
        """Atomically persist a diagnosis report."""
        records = self.load_all_diagnoses()
        records[report.diagnosis_id] = report.to_dict()

        temp_path = self.base_dir / "diagnoses.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        os.replace(temp_path, self.diagnoses_file)

    def load_all_diagnoses(self) -> Dict[str, Dict]:
        """Load all persisted diagnoses from disk."""
        if not self.diagnoses_file.exists():
            return {}
        try:
            with open(self.diagnoses_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def get_diagnosis(self, diagnosis_id: str) -> Optional[Dict]:
        """Retrieve a specific diagnosis dictionary."""
        return self.load_all_diagnoses().get(diagnosis_id)

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
