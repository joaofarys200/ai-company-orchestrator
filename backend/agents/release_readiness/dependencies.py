"""
Dependency Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Verifies dependency resolution, version pinning, lockfile integrity, and compatibility.
Crucial invariant: Never auto-installs packages without traversing security/policy gates.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import DependencyStatus, BlockerCategory, ReleaseBlocker


class DependencyReadiness:
    """Evaluates software supply chain, lockfile integrity, and package resolvability."""

    @classmethod
    def evaluate(
        cls,
        dependency_data: Dict[str, Any],
        require_pinned: bool = True
    ) -> Dict[str, Any]:
        """
        Verifies:
        - dependencies resolvable
        - versions pinned when required
        - lockfile consistency
        - runtime availability
        - known incompatible versions
        - missing packages
        """
        if not dependency_data:
            return {
                "status": DependencyStatus.UNRESOLVABLE,
                "blockers": [
                    ReleaseBlocker(
                        blocker_id="blocker-dep-missing-manifest",
                        category=BlockerCategory.DEPENDENCY_FAILURE,
                        description="Dependency manifest or scan results completely absent",
                        evidence="Empty dependency payload provided."
                    )
                ],
                "requires_human_review": True,
                "review_reasons": ["Missing dependency manifest"]
            }

        resolvable = dependency_data.get("dependencies_resolvable", True)
        unpinned_count = dependency_data.get("unpinned_dependencies_count", 0)
        lockfile_consistent = dependency_data.get("lockfile_consistent", True)
        runtime_available = dependency_data.get("runtime_available", True)
        incompatible_versions = dependency_data.get("incompatible_versions_count", 0)
        missing_packages = dependency_data.get("missing_packages_count", 0)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if not resolvable or missing_packages > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-dep-unresolvable",
                category=BlockerCategory.DEPENDENCY_FAILURE,
                description=f"Dependencies unresolvable or missing ({missing_packages} missing packages)",
                evidence=f"Resolvable: {resolvable}, missing packages: {missing_packages}."
            ))

        if incompatible_versions > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-dep-incompatible",
                category=BlockerCategory.DEPENDENCY_FAILURE,
                description=f"Known incompatible dependency versions detected ({incompatible_versions})",
                evidence="Package version constraints conflict with runtime environment."
            ))

        if not lockfile_consistent:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-dep-lockfile-drift",
                category=BlockerCategory.DEPENDENCY_FAILURE,
                description="Lockfile is inconsistent with declared project dependencies",
                evidence="Integrity checksum mismatch or out-of-sync package specifications."
            ))

        if not runtime_available:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-dep-runtime-missing",
                category=BlockerCategory.DEPENDENCY_FAILURE,
                description="Required runtime binaries or system packages unavailable in execution environment",
                evidence="Runtime availability check failed for native or system dependencies."
            ))

        if require_pinned and unpinned_count > 0:
            requires_human_review = True
            review_reasons.append(f"{unpinned_count} dependencies have floating or unpinned version ranges")

        status = DependencyStatus.READY
        if blockers:
            status = DependencyStatus.INCOMPATIBLE
        elif requires_human_review:
            status = DependencyStatus.RESOLVABLE_WITH_WARNINGS

        return {
            "status": status,
            "resolvable": resolvable,
            "unpinned_count": unpinned_count,
            "lockfile_consistent": lockfile_consistent,
            "runtime_available": runtime_available,
            "incompatible_versions": incompatible_versions,
            "missing_packages": missing_packages,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
