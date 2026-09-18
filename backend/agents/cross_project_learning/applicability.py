"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: applicability.py
KnowledgeApplicabilityEngine evaluates candidate items against target project constraints.
Produces fine-grained status classifications and structured natural language explanations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    ApplicabilityResult,
    ApplicabilityStatus,
    CandidateKnowledge,
    EngineeringKnowledgeItem,
    ProjectFingerprint,
)


class KnowledgeApplicabilityEngine:
    """Evaluates whether an engineering knowledge pattern is safely applicable to a target project."""

    @classmethod
    def evaluate_applicability(
        cls,
        candidate: CandidateKnowledge,
        target_fingerprint: ProjectFingerprint,
    ) -> ApplicabilityResult:
        """
        Determine applicability status with comprehensive why/why-not explanations.
        Never outputs a naked score without reasons.
        """
        item = candidate.item
        why_applicable: List[str] = []
        why_not_applicable: List[str] = []
        transformations: List[str] = []
        adapter_needed = False

        # 1. Inspect Languages
        target_langs = set(l.lower() for l in target_fingerprint.languages)
        item_ctx = item.context
        item_langs = set(l.lower() for l in item_ctx.get("languages", [item_ctx.get("language", "python")]))

        SUPPORTED_CROSS_LANGUAGES = {"python", "typescript", "javascript"}
        has_supported_adapter = any(l in SUPPORTED_CROSS_LANGUAGES for l in item_langs) and any(
            l in SUPPORTED_CROSS_LANGUAGES for l in target_langs
        )

        exact_lang_match = bool(target_langs.intersection(item_langs))
        if exact_lang_match:
            common_langs = list(target_langs.intersection(item_langs))
            why_applicable.append(f"Matching language environment: {', '.join(common_langs)}")
        elif has_supported_adapter:
            adapter_needed = True
            why_not_applicable.append(
                f"Language mismatch: pattern originates from {list(item_langs)}, target requires {list(target_langs)}"
            )
            transformations.append("Apply Phase 44 Semantic Cross-Language Adapter")
        else:
            adapter_needed = False
            why_not_applicable.append(
                f"Unsupported language pair: no semantic adapter exists between {list(item_langs)} and {list(target_langs)}"
            )

        # 2. Inspect Architecture Style
        target_arch = target_fingerprint.architecture_style.lower()
        item_arch = str(item_ctx.get("architecture_style", "")).lower()
        if item_arch:
            if item_arch == target_arch:
                why_applicable.append(f"Architectural alignment on {target_arch}")
            else:
                why_not_applicable.append(
                    f"Architectural divergence: pattern assumes {item_arch}, target is {target_arch}"
                )
                transformations.append(f"Map architectural boundaries from {item_arch} to {target_arch}")

        # 3. Inspect Preconditions
        unmet_preconditions: List[str] = []
        for pre in item.preconditions:
            pre_lower = pre.lower()
            # Heuristic check against target fingerprint capabilities
            if "browser" in pre_lower and "none" in target_fingerprint.browser_framework:
                unmet_preconditions.append(f"Browser automation missing ({pre})")
            elif "sqlite" in pre_lower and "sqlite" not in target_fingerprint.persistence_technologies:
                unmet_preconditions.append(f"Persistence engine mismatch ({pre})")
            elif "websocket" in pre_lower and "websocket" not in target_fingerprint.communication_mechanisms:
                unmet_preconditions.append(f"Communication protocol mismatch ({pre})")
            elif any(k in pre_lower for k in ("simulator", "mobile", "ios", "android")):
                unmet_preconditions.append(f"Unsupported mobile/platform environment requirement ({pre})")
            else:
                why_applicable.append(f"Precondition satisfied or adaptable: {pre}")

        if unmet_preconditions:
            why_not_applicable.extend(unmet_preconditions)

        # 4. Check Historical Harm & Confidence
        if item.harm_count > 0:
            why_not_applicable.append(f"Item has caused {item.harm_count} historical harm incidents")

        # 5. Classify Applicability Status
        confidence = candidate.applicability_confidence
        target_lang = list(target_langs)[0] if target_langs else "python"

        if not exact_lang_match and not has_supported_adapter:
            status = ApplicabilityStatus.INCOMPATIBLE
            confidence = min(0.15, confidence)
        elif not exact_lang_match and len(unmet_preconditions) > 1:
            status = ApplicabilityStatus.INCOMPATIBLE
            confidence = min(0.20, confidence)
        elif not exact_lang_match:
            status = ApplicabilityStatus.CONTEXT_REQUIRED
            confidence = min(0.65, confidence)
            transformations.append(f"Synthesize {target_lang} interface equivalent")
        elif unmet_preconditions:
            status = ApplicabilityStatus.PARTIALLY_APPLICABLE
            confidence = min(0.65, confidence)
        elif confidence >= 0.75 and len(why_not_applicable) == 0:
            status = ApplicabilityStatus.DIRECTLY_APPLICABLE
        elif confidence < 0.40:
            status = ApplicabilityStatus.LOW_CONFIDENCE
        else:
            status = ApplicabilityStatus.PARTIALLY_APPLICABLE

        return ApplicabilityResult(
            status=status,
            confidence=round(confidence, 4),
            why_applicable=why_applicable,
            why_not_applicable=why_not_applicable,
            required_transformations=transformations,
            adapter_needed=adapter_needed,
            target_language=target_lang,
        )
