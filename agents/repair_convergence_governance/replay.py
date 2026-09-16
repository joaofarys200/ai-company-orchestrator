"""
JARVIS OS — Phase 56: Deterministic Replay Engine
Enables bit-for-bit identical reproduction of repair trajectories and state transitions.
"""

from __future__ import annotations

import random
from typing import Dict, Any, List, Optional, Tuple
from agents.repair_convergence_governance.models import (
    RepairStepSnapshot,
    compute_deterministic_hash,
)


class DeterministicReplayEngine:
    """Replays repair executions deterministically from initial state, seed, and patch sequence."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def replay_sequence(
        self,
        initial_snapshot: RepairStepSnapshot,
        patch_sequence: List[Dict[str, Any]],
        environment_seed: Optional[int] = None,
    ) -> List[RepairStepSnapshot]:
        """Simulates identical state sequence playback."""
        current_seed = environment_seed if environment_seed is not None else self.seed
        rng = random.Random(current_seed)

        snapshots: List[RepairStepSnapshot] = [initial_snapshot]
        active = list(initial_snapshot.active_failures)
        fixed = list(initial_snapshot.fixed_failures)

        for idx, patch_info in enumerate(patch_sequence, start=1):
            patch_id = patch_info.get("patch_id", f"patch_{idx}")
            targets_resolved = patch_info.get("resolves", [])

            # Deterministic resolution
            for t in targets_resolved:
                if t in active:
                    active.remove(t)
                    fixed.append(t)

            new_introduced = patch_info.get("introduces", [])
            for n in new_introduced:
                if n not in active:
                    active.append(n)

            cov = min(1.0, initial_snapshot.behavioral_proof_coverage + (0.05 * idx))
            risk = max(0.0, initial_snapshot.risk_score - (0.08 * idx))

            snap = RepairStepSnapshot(
                iteration_id=idx,
                timestamp=initial_snapshot.timestamp + (idx * 1.5),
                active_failures=list(active),
                fixed_failures=list(fixed),
                newly_introduced_failures=list(new_introduced),
                patches_applied=[patch_id],
                modified_files=patch_info.get("files", ["src/module.py"]),
                test_pass_rate=1.0 if not active else max(0.0, 1.0 - (len(active) * 0.15)),
                behavioral_proof_coverage=round(cov, 4),
                code_entropy=0.12,
                risk_score=round(risk, 4),
                tests_failed=len(active),
            )
            snapshots.append(snap)

        return snapshots

    def verify_replay_identity(
        self,
        original_hashes: List[str],
        replayed_hashes: List[str],
    ) -> Tuple[bool, List[str]]:
        """Verifies that the replayed state hashes match original trace exactly."""
        if len(original_hashes) != len(replayed_hashes):
            return False, [f"Length mismatch: original {len(original_hashes)} vs replayed {len(replayed_hashes)}"]

        discrepancies = []
        for i, (orig, rep) in enumerate(zip(original_hashes, replayed_hashes)):
            if orig != rep:
                discrepancies.append(f"Step {i}: original {orig} != replayed {rep}")

        return len(discrepancies) == 0, discrepancies
