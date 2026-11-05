"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Module: persistence.py
JSON-backed persistence store for migrations, checkpoints, evidence ledgers, and audit trails.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    EvidenceRecord,
    InvalidationRecord,
    MacroMigration,
    MigrationCheckpoint,
    MigrationState,
    MigrationStep,
    MigrationStepType,
    StepState,
)


class MacroRefactoringStore:
    """
    Persists and recovers macro migrations, checkpoints, and evidence ledgers.
    """

    def __init__(self, base_dir: str = ".jarvis/macro_migrations"):
        self.base_dir = Path(base_dir)
        self.migrations_dir = self.base_dir / "migrations"
        self.checkpoints_dir = self.base_dir / "checkpoints"
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.migrations_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def save_migration(self, migration: MacroMigration) -> str:
        """Saves a MacroMigration instance to disk as JSON."""
        file_path = self.migrations_dir / f"{migration.migration_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(migration.to_dict(), f, indent=2)
        return str(file_path)

    def load_migration(self, migration_id: str) -> Optional[MacroMigration]:
        """Loads a MacroMigration instance from disk."""
        file_path = self.migrations_dir / f"{migration_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self._deserialize_migration(data)

    def save_checkpoint(self, checkpoint: MigrationCheckpoint) -> str:
        """Saves a checkpoint to disk."""
        file_path = self.checkpoints_dir / f"{checkpoint.checkpoint_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        return str(file_path)

    def load_checkpoint(self, checkpoint_id: str) -> Optional[MigrationCheckpoint]:
        """Loads a checkpoint from disk."""
        file_path = self.checkpoints_dir / f"{checkpoint_id}.json"
        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return MigrationCheckpoint(
            checkpoint_id=data["checkpoint_id"],
            sequence=data["sequence"],
            migration_id=data["migration_id"],
            current_step_id=data.get("current_step_id"),
            state_snapshot=data["state_snapshot"],
            checksum=data["checksum"],
            created_at=data["created_at"],
        )

    def list_migrations(self) -> List[str]:
        """Lists all stored migration IDs."""
        return [f.stem for f in self.migrations_dir.glob("*.json")]

    def _deserialize_migration(self, data: Dict[str, Any]) -> MacroMigration:
        steps: Dict[str, MigrationStep] = {}
        for s_id, s_data in data.get("steps", {}).items():
            steps[s_id] = MigrationStep(
                step_id=s_data["step_id"],
                step_type=MigrationStepType(s_data["step_type"]),
                title=s_data["title"],
                description=s_data["description"],
                affected_files=s_data.get("affected_files", []),
                affected_symbols=s_data.get("affected_symbols", []),
                dependencies=s_data.get("dependencies", []),
                state=StepState(s_data.get("state", StepState.PENDING.value)),
                preconditions=s_data.get("preconditions", []),
                postconditions=s_data.get("postconditions", []),
                verification_gates=s_data.get("verification_gates", []),
                compensation_action=s_data.get("compensation_action", ""),
                evidence_refs=s_data.get("evidence_refs", []),
                retry_count=s_data.get("retry_count", 0),
                max_retries=s_data.get("max_retries", 1),
                error=s_data.get("error"),
                applied_patch_hash=s_data.get("applied_patch_hash"),
                metadata=s_data.get("metadata", {}),
            )

        evidence_ledger: List[EvidenceRecord] = []
        for e_data in data.get("evidence_ledger", []):
            evidence_ledger.append(
                EvidenceRecord(
                    evidence_id=e_data["evidence_id"],
                    step_id=e_data["step_id"],
                    kind=e_data["kind"],
                    content_hash=e_data["content_hash"],
                    timestamp=e_data["timestamp"],
                    valid=e_data["valid"],
                    invalidation_reason=e_data.get("invalidation_reason"),
                    details=e_data.get("details", {}),
                )
            )

        invalidations: List[InvalidationRecord] = []
        for i_data in data.get("invalidations", []):
            invalidations.append(
                InvalidationRecord(
                    invalidation_id=i_data["invalidation_id"],
                    triggered_by_step_id=i_data["triggered_by_step_id"],
                    invalidated_step_id=i_data["invalidated_step_id"],
                    evidence_id=i_data["evidence_id"],
                    reason=i_data["reason"],
                    timestamp=i_data["timestamp"],
                )
            )

        checkpoints: List[MigrationCheckpoint] = []
        for c_data in data.get("checkpoints", []):
            checkpoints.append(
                MigrationCheckpoint(
                    checkpoint_id=c_data["checkpoint_id"],
                    sequence=c_data["sequence"],
                    migration_id=c_data["migration_id"],
                    current_step_id=c_data.get("current_step_id"),
                    state_snapshot=c_data["state_snapshot"],
                    checksum=c_data["checksum"],
                    created_at=c_data["created_at"],
                )
            )

        return MacroMigration(
            migration_id=data["migration_id"],
            objective=data["objective"],
            project_id=data["project_id"],
            status=MigrationState(data["status"]),
            blast_radius_nodes=data.get("blast_radius_nodes", 0),
            steps=steps,
            execution_order=data.get("execution_order", []),
            evidence_ledger=evidence_ledger,
            invalidations=invalidations,
            checkpoints=checkpoints,
            target_invariants=data.get("target_invariants", []),
            current_step_index=data.get("current_step_index", 0),
            risk_score=data.get("risk_score", 0.0),
            execution_cost_budget=data.get("execution_cost_budget", 100.0),
            consumed_budget=data.get("consumed_budget", 0.0),
            provenance_hash=data.get("provenance_hash", ""),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            unresolved_blockers=data.get("unresolved_blockers", []),
            metadata=data.get("metadata", {}),
        )
