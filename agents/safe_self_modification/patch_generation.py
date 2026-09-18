"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: patch_generation.py
Synthesizes minimal, verified modification patches and their exact inverse
rollback patches, strictly constrained to the approved governance surface.
"""

from __future__ import annotations

import difflib
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import ModificationPatch, PlanStep


class PatchGenerator:
    """Generates minimal forward and rollback patches within approved architectural scope."""

    def generate_patch(
        self,
        step: PlanStep,
        target_files: List[str],
        target_symbols: List[str],
        before_contents: Dict[str, str],
        new_contents: Dict[str, str],
        approved_surface: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[ModificationPatch], str]:
        """Generate a patch ensuring all touched files are within approved surface."""
        # 1. Verify scope enforcement
        if approved_surface is not None:
            approved_set = set(approved_surface)
            for f in target_files:
                if f not in approved_set:
                    return (
                        False,
                        None,
                        f"SCOPE_VIOLATION: File '{f}' is outside approved surface {approved_surface}.",
                    )

        # 2. Build forward diff and rollback diff
        forward_diff_lines = []
        rollback_diff_lines = []

        for f in target_files:
            old_code = before_contents.get(f, "")
            new_code = new_contents.get(f, "")

            old_lines = old_code.splitlines(keepends=True)
            new_lines = new_code.splitlines(keepends=True)

            fwd_diff = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{f}",
                    tofile=f"b/{f}",
                )
            )
            rev_diff = list(
                difflib.unified_diff(
                    new_lines,
                    old_lines,
                    fromfile=f"b/{f}",
                    tofile=f"a/{f}",
                )
            )

            forward_diff_lines.extend(fwd_diff)
            rollback_diff_lines.extend(rev_diff)

        full_diff = "".join(forward_diff_lines)
        full_rollback = "".join(rollback_diff_lines)

        patch_id = f"patch_{step.step_id}_{int(time.time() * 1000) % 1000000}"

        patch = ModificationPatch(
            patch_id=patch_id,
            step_id=step.step_id,
            target_files=target_files,
            target_symbols=target_symbols,
            diff=full_diff,
            expected_effect=f"Apply {step.title}",
            provenance={
                "step_id": step.step_id,
                "step_type": step.step_type,
                "generated_at": time.time(),
            },
            risk="LOW" if len(target_files) <= 3 else "MEDIUM",
            rollback_patch=full_rollback,
            is_valid=True,
            new_contents=new_contents,
        )
        patch.patch_hash = patch.compute_hash()
        return True, patch, "PATCH_GENERATED: Minimal patch with inverse rollback constructed."
