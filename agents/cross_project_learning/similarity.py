"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: similarity.py
Multidimensional similarity calculator between project fingerprints, contexts, and patterns.
Evaluates Jaccard overlap, categorical alignment, topological compatibility, and risk surfaces.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Set, Tuple

from .models import EngineeringKnowledgeItem, ProjectFingerprint


class SimilarityEngine:
    """Computes multidimensional similarity vectors between projects and knowledge items."""

    @staticmethod
    def jaccard_similarity(list_a: List[str], list_b: List[str]) -> float:
        set_a = set(x.strip().lower() for x in list_a if x)
        set_b = set(x.strip().lower() for x in list_b if x)
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union if union > 0 else 0.0

    @classmethod
    def compute_fingerprint_similarity(
        cls,
        fp_a: ProjectFingerprint,
        fp_b: ProjectFingerprint,
    ) -> Tuple[float, Dict[str, float]]:
        """Compare two project fingerprints across multiple architectural and runtime axes."""
        dim_scores: Dict[str, float] = {}

        # 1. Language similarity
        dim_scores["language"] = cls.jaccard_similarity(fp_a.languages, fp_b.languages)

        # 2. Framework similarity
        dim_scores["framework"] = cls.jaccard_similarity(fp_a.frameworks, fp_b.frameworks)

        # 3. Architecture similarity
        dim_scores["architecture"] = 1.0 if fp_a.architecture_style == fp_b.architecture_style else 0.4

        # 4. Topology similarity
        pkg_match = 1.0 if fp_a.package_topology == fp_b.package_topology else 0.5
        srv_match = 1.0 if fp_a.service_topology == fp_b.service_topology else 0.5
        dim_scores["topology"] = (pkg_match + srv_match) / 2.0

        # 5. Contract types similarity
        dim_scores["contracts"] = cls.jaccard_similarity(fp_a.contract_types, fp_b.contract_types)

        # 6. Test framework similarity
        dim_scores["test_framework"] = cls.jaccard_similarity(fp_a.test_framework, fp_b.test_framework)

        # 7. Browser framework similarity
        dim_scores["browser_framework"] = cls.jaccard_similarity(fp_a.browser_framework, fp_b.browser_framework)

        # 8. Persistence similarity
        dim_scores["persistence"] = cls.jaccard_similarity(fp_a.persistence_technologies, fp_b.persistence_technologies)

        # 9. Communication mechanisms
        dim_scores["communication"] = cls.jaccard_similarity(fp_a.communication_mechanisms, fp_b.communication_mechanisms)

        # 10. Risk classes similarity
        dim_scores["risk"] = cls.jaccard_similarity(fp_a.risk_classes, fp_b.risk_classes)

        weights = {
            "language": 0.20,
            "framework": 0.15,
            "architecture": 0.15,
            "topology": 0.10,
            "contracts": 0.10,
            "test_framework": 0.10,
            "browser_framework": 0.05,
            "persistence": 0.05,
            "communication": 0.05,
            "risk": 0.05,
        }

        composite = sum(dim_scores[k] * weights[k] for k in weights)
        return composite, dim_scores

    @classmethod
    def evaluate_item_similarity(
        cls,
        item: EngineeringKnowledgeItem,
        target_fp: ProjectFingerprint,
    ) -> Tuple[float, List[str], List[str]]:
        """Evaluate how closely an item matches a target project fingerprint."""
        matching_dims: List[str] = []
        missing_dims: List[str] = []
        score = 0.0

        ctx = item.context
        # Check target language alignment
        item_langs = ctx.get("languages", [])
        if not item_langs:
            item_langs = [ctx.get("language", "python")]
        lang_sim = cls.jaccard_similarity(item_langs, target_fp.languages)
        if lang_sim > 0.0:
            matching_dims.append(f"language_overlap_{lang_sim:.2f}")
            score += 0.30 * lang_sim
        else:
            missing_dims.append("language_mismatch")

        # Check architecture alignment
        item_arch = ctx.get("architecture_style", "")
        if item_arch and item_arch.lower() == target_fp.architecture_style.lower():
            matching_dims.append("architecture_match")
            score += 0.20
        elif not item_arch:
            score += 0.10
        else:
            missing_dims.append(f"architecture_drift_{item_arch}_vs_{target_fp.architecture_style}")

        # Check frameworks
        item_fws = ctx.get("frameworks", [])
        fw_sim = cls.jaccard_similarity(item_fws, target_fp.frameworks)
        if fw_sim > 0.0:
            matching_dims.append(f"framework_overlap_{fw_sim:.2f}")
            score += 0.20 * fw_sim
        elif item_fws:
            missing_dims.append("framework_mismatch")
        else:
            score += 0.10

        # Check contracts or risk
        item_risk = ctx.get("risk_class", "")
        if item_risk and item_risk.lower() in [r.lower() for r in target_fp.risk_classes]:
            matching_dims.append(f"risk_class_shared_{item_risk}")
            score += 0.15
        else:
            score += 0.05

        # Incorporate historical success / confidence
        score += 0.15 * item.confidence

        # Temporal decay: penalize very old items slightly
        age_days = (time.time() - item.created_at) / 86400.0
        decay = math.exp(-0.01 * min(age_days, 100))
        score *= decay

        return min(1.0, max(0.0, score)), matching_dims, missing_dims
