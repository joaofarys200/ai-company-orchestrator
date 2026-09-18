"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: snapshot.py
Captures immutable, pre-modification snapshots with cryptographic SHA-256 fingerprints
of target and dependent files, symbols, contracts, and execution environments.
"""

from __future__ import annotations

import hashlib
import os
import platform
import time
from typing import Any, Dict, List, Optional

from .models import TransactionalSnapshot


class TransactionalSnapshotManager:
    """Manages creation and verification of immutable pre-modification snapshots."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.getcwd()

    def create_snapshot(
        self,
        snapshot_id: str,
        files: List[str],
        governance_decision_hash: str,
        architecture_hash: str = "",
        symbol_hashes: Optional[Dict[str, str]] = None,
        contract_hashes: Optional[Dict[str, str]] = None,
    ) -> TransactionalSnapshot:
        """Create an immutable snapshot of specified files with content and SHA-256."""
        files_state: Dict[str, str] = {}
        file_contents: Dict[str, str] = {}

        for rel_path in files:
            abs_path = os.path.join(self.workspace_root, rel_path) if not os.path.isabs(rel_path) else rel_path
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    file_contents[rel_path] = content
                    files_state[rel_path] = hashlib.sha256(content.encode("utf-8")).hexdigest()
                except Exception as e:
                    files_state[rel_path] = f"ERROR: {e}"
            else:
                # Track non-existent file so rollback can cleanly delete it
                files_state[rel_path] = "FILE_DOES_NOT_EXIST"
                file_contents[rel_path] = ""

        env_metadata = {
            "os": platform.system(),
            "python_version": platform.python_version(),
            "timestamp": time.time(),
        }

        snapshot = TransactionalSnapshot(
            snapshot_id=snapshot_id,
            files_state=files_state,
            file_contents=file_contents,
            symbol_hashes=symbol_hashes or {},
            contract_hashes=contract_hashes or {},
            architecture_hash=architecture_hash or "arch_hash_default",
            environment_metadata=env_metadata,
            governance_decision_hash=governance_decision_hash,
            created_at=time.time(),
        )
        snapshot.snapshot_sha256 = snapshot.compute_hash()
        return snapshot

    def verify_snapshot_integrity(self, snapshot: TransactionalSnapshot) -> bool:
        """Verify that snapshot hash matches recomputed value."""
        return snapshot.compute_hash() == snapshot.snapshot_sha256
