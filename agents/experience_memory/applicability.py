"""
JARVIS OS — Phase 42: Experience Applicability Validator
Evaluates 8 compatibility axes to guarantee that historical operational experiences
are technically and legally valid for the current mission context before any influence.
"""

from __future__ import annotations

from typing import Any

from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperiencePolarity,
    ExperienceRecord,
    MemoryInfluenceType,
    PolicyCompatibilityStatus,
    TemporalValidity,
)


class ExperienceApplicabilityValidator:
    """Validates whether a retrieved experience is safely and technically applicable."""

    @classmethod
    def evaluate_policy_compatibility(
        cls, experience_policy: str, current_policy: str
    ) -> PolicyCompatibilityStatus:
        """Deterministically evaluates cross-policy compatibility."""
        try:
            exp_major = int(experience_policy.split(".")[0]) if experience_policy else 40
            curr_major = int(current_policy.split(".")[0]) if current_policy else 43
        except (ValueError, IndexError):
            return PolicyCompatibilityStatus.POLICY_REQUIRES_VALIDATION

        delta = curr_major - exp_major
        if delta == 0:
            return PolicyCompatibilityStatus.CURRENT_POLICY_COMPATIBLE
        elif delta <= 2:
            return PolicyCompatibilityStatus.POLICY_REQUIRES_VALIDATION
        else:
            return PolicyCompatibilityStatus.POLICY_MISMATCH

    @classmethod
    def validate(
        cls,
        experience: ExperienceRecord,
        current_mission_state: dict[str, Any],
        current_architecture: dict[str, Any],
        current_policy_version: str,
        current_security_level: str = "STRICT",
    ) -> tuple[ExperienceApplicabilityRating, MemoryInfluenceType, list[str], str]:
        return cls.validate_applicability(
            experience, current_mission_state, current_architecture, current_policy_version, current_security_level
        )

    @classmethod
    def validate_applicability(
        cls,
        experience: ExperienceRecord,
        current_mission_state: dict[str, Any],
        current_architecture: dict[str, Any],
        current_policy_version: str,
        current_security_level: str = "STRICT",
    ) -> tuple[ExperienceApplicabilityRating, MemoryInfluenceType, list[str], str]:
        """
        Validates 8 distinct compatibility axes:
        1. Technology compatibility
        2. Architecture compatibility (including drift detection)
        3. Mission state compatibility
        4. Policy version compatibility
        5. Security context compatibility
        6. Dependency context
        7. Evidence freshness
        8. Intent compatibility
        """
        rejection_reasons: list[str] = []
        validation_notes: list[str] = []

        sig = experience.intent_signature

        # 1. Technology compatibility
        curr_techs = {t.lower() for t in current_architecture.get("technology", ["vanilla_ts"])}
        exp_techs = {t.lower() for t in sig.technology}
        if exp_techs and not curr_techs.intersection(exp_techs):
            rejection_reasons.append(
                f"Technology mismatch: experience uses {list(exp_techs)}, active uses {list(curr_techs)}"
            )

        # 2. Architecture compatibility & Drift detection
        curr_arch = {a.lower() for a in current_architecture.get("components", ["frontend", "backend"])}
        exp_arch = {a.lower() for a in sig.affected_architecture}
        if exp_arch and not curr_arch.intersection(exp_arch):
            rejection_reasons.append(
                f"Architecture mismatch: experience touches {list(exp_arch)}, active touches {list(curr_arch)}"
            )

        # Architecture drift (e.g., monolith vs microservices)
        curr_paradigm = current_architecture.get("paradigm") or current_architecture.get("architecture") or "modular"
        exp_paradigm = experience.mission_context.get("architecture_paradigm") or experience.mission_context.get("architecture") or "modular"
        if curr_paradigm and exp_paradigm and curr_paradigm.lower() != exp_paradigm.lower():
            rejection_reasons.append(
                f"Architecture drift: historical paradigm '{exp_paradigm}' conflicts with current '{curr_paradigm}'"
            )

        # 3. Mission state compatibility
        curr_stage = current_mission_state.get("current_stage", "EXECUTION")
        if curr_stage == "SNAPSHOT" and "finish" in experience.tags:
            rejection_reasons.append("Stage mismatch: finish gate experience inapplicable during early snapshot")

        # 4. Policy version compatibility
        policy_status = cls.evaluate_policy_compatibility(experience.policy_version, current_policy_version)
        if policy_status == PolicyCompatibilityStatus.POLICY_MISMATCH:
            rejection_reasons.append(
                f"Policy version mismatch: {experience.policy_version} incompatible with current {current_policy_version}"
            )
        elif policy_status == PolicyCompatibilityStatus.POLICY_REQUIRES_VALIDATION:
            validation_notes.append(
                f"Cross-policy validation required: {experience.policy_version} vs current {current_policy_version}"
            )

        # 5. Security context compatibility
        if current_security_level == "STRICT" and "bypass" in experience.tags:
            rejection_reasons.append("Security context violation: historical bypass strictly forbidden under STRICT level")

        # 6. Dependency context
        missing_deps = current_mission_state.get("missing_dependencies", [])
        if "missing_dependency" in experience.tags and not missing_deps and experience.decision == "REPLAN":
            validation_notes.append("Dependency context divergence: active has no missing dependencies")

        # 7. Evidence freshness & Stale check
        if experience.temporal_validity == TemporalValidity.STALE:
            rejection_reasons.append("Evidence is marked STALE in operational repository")

        # 8. Intent compatibility
        curr_intent = current_mission_state.get("user_goal", "")
        if "delete" in curr_intent.lower() and "create" in experience.tags:
            validation_notes.append("Intent divergence: destructive goal vs creation memory")

        # Final Rating Assignment
        if rejection_reasons:
            rating = ExperienceApplicabilityRating.INAPPLICABLE
            influence = MemoryInfluenceType.NONE
            summary = f"Inapplicable: {'; '.join(rejection_reasons)}"
        elif validation_notes:
            rating = ExperienceApplicabilityRating.POSSIBLY_RELEVANT
            influence = MemoryInfluenceType.CONTEXT_ONLY
            summary = f"Possibly relevant with caveats: {'; '.join(validation_notes)}"
        else:
            rating = ExperienceApplicabilityRating.RELEVANT
            # Default influence depending on polarity and decision
            if experience.polarity == ExperiencePolarity.NEGATIVE_EXPERIENCE:
                influence = MemoryInfluenceType.DIAGNOSTIC
                summary = "Negative experience applicable as cautionary diagnostic guidance."
            elif experience.decision == "REPAIR":
                influence = MemoryInfluenceType.REPAIR_HINT
                summary = "Fully applicable repair pattern across all 8 compatibility axes."
            elif experience.decision == "REPLAN":
                influence = MemoryInfluenceType.PLANNING_HINT
                summary = "Fully applicable planning pattern across all 8 compatibility axes."
            elif experience.decision == "REQUEST_HUMAN":
                influence = MemoryInfluenceType.ESCALATION_HINT
                summary = "Fully applicable escalation pattern across all 8 compatibility axes."
            else:
                influence = MemoryInfluenceType.DIAGNOSTIC
                summary = "Fully applicable across all 8 compatibility axes."

        return rating, influence, rejection_reasons + validation_notes, summary
