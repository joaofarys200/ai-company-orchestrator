"""
JARVIS OS — Phase 42: Conflicting Experience Detection & Resolution
Identifies contradictions among historical operational experiences, compares
causal evidence, success rates, and versions without arbitrary selection heuristics.
"""

from __future__ import annotations

from typing import Optional

from agents.experience_memory.models import (
    ConflictingExperience,
    ExperienceRecord,
    MemoryInfluenceType,
    RelevantExperience,
)


class ConflictResolver:
    """Analyzes retrieved experiences to detect and characterize empirical contradictions."""

    @classmethod
    def detect_conflicts(
        cls, relevant_experiences: list[RelevantExperience]
    ) -> list[ConflictingExperience]:
        """
        Detects opposing recommendations for the same failure class or intent category.
        e.g., Experience A: REPAIR vs Experience B: REPLAN or REQUEST_HUMAN.
        """
        conflicts: list[ConflictingExperience] = []
        n = len(relevant_experiences)

        for i in range(n):
            for j in range(i + 1, n):
                exp1 = relevant_experiences[i].experience
                exp2 = relevant_experiences[j].experience

                # Check if same failure class / intent category but conflicting decisions
                same_domain = (
                    exp1.intent_signature.intent_category == exp2.intent_signature.intent_category
                    or (
                        exp1.intent_signature.observed_failure != "NONE"
                        and exp1.intent_signature.observed_failure == exp2.intent_signature.observed_failure
                    )
                )

                if same_domain and exp1.decision != exp2.decision:
                    # Conflicting decision paths detected
                    summary = (
                        f"Divergent operational actions for '{exp1.intent_signature.observed_failure or exp1.intent_signature.intent_category}': "
                        f"[{exp1.experience_id}] recommends {exp1.decision} (Outcome: {exp1.outcome}) vs "
                        f"[{exp2.experience_id}] recommends {exp2.decision} (Outcome: {exp2.outcome})"
                    )

                    context_comp = {
                        "exp1_tech": list(exp1.intent_signature.technology),
                        "exp2_tech": list(exp2.intent_signature.technology),
                        "exp1_scope": exp1.intent_signature.scope,
                        "exp2_scope": exp2.intent_signature.scope,
                    }

                    evidence_comp = {
                        "exp1_evidence_count": len(exp1.evidence_refs),
                        "exp2_evidence_count": len(exp2.evidence_refs),
                        "exp1_evidence_refs": list(exp1.evidence_refs),
                        "exp2_evidence_refs": list(exp2.evidence_refs),
                    }

                    success_comp = {
                        "exp1_confidence": exp1.confidence,
                        "exp2_confidence": exp2.confidence,
                    }

                    conflicts.append(
                        ConflictingExperience(
                            primary_experience_id=exp1.experience_id,
                            conflicting_experience_id=exp2.experience_id,
                            divergence_summary=summary,
                            context_comparison=context_comp,
                            evidence_comparison=evidence_comp,
                            success_rate_comparison=success_comp,
                            policy_version_delta=f"{exp1.policy_version} vs {exp2.policy_version}",
                            severity_delta=f"{exp1.severity} vs {exp2.severity}",
                        )
                    )

        return conflicts

    @classmethod
    def resolve_conflict(
        cls,
        conflict: ConflictingExperience,
        exp1: ExperienceRecord,
        exp2: ExperienceRecord,
    ) -> tuple[str, MemoryInfluenceType]:
        """
        Resolves conflict using applicability, evidence, success rate, and policy.
        Never uses naive recency. If ambiguity remains, marks CONFLICT_UNRESOLVED
        and constrains influence strictly to CONTEXT_ONLY.
        """
        # 1. Applicability comparison
        if exp1.applicability == "RELEVANT" and exp2.applicability != "RELEVANT":
            return exp1.experience_id, MemoryInfluenceType.DIAGNOSTIC
        if exp2.applicability == "RELEVANT" and exp1.applicability != "RELEVANT":
            return exp2.experience_id, MemoryInfluenceType.DIAGNOSTIC

        # 2. Evidence weight comparison
        ev1_count = len(exp1.evidence_refs)
        ev2_count = len(exp2.evidence_refs)
        if ev1_count >= ev2_count + 2 and exp1.confidence > exp2.confidence:
            return exp1.experience_id, MemoryInfluenceType.DIAGNOSTIC
        if ev2_count >= ev1_count + 2 and exp2.confidence > exp1.confidence:
            return exp2.experience_id, MemoryInfluenceType.DIAGNOSTIC

        # 3. Policy version comparison
        try:
            p1_major = int(exp1.policy_version.split(".")[0])
            p2_major = int(exp2.policy_version.split(".")[0])
            if p1_major > p2_major + 1:
                return exp1.experience_id, MemoryInfluenceType.DIAGNOSTIC
            if p2_major > p1_major + 1:
                return exp2.experience_id, MemoryInfluenceType.DIAGNOSTIC
        except (ValueError, IndexError):
            pass

        # Ambiguous conflict: Recency is strictly forbidden from acting as tiebreaker!
        return "CONFLICT_UNRESOLVED", MemoryInfluenceType.CONTEXT_ONLY
