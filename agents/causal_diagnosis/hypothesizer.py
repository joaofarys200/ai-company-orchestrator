"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: hypothesizer.py
Generates and ranks competing root-cause hypotheses from paths in the causal graph.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Tuple

from .confidence import ConfidenceCalculator
from .graph import CausalGraphBuilder
from .models import (
    CausalEdgeType,
    CausalHypothesis,
    CausalNodeType,
    HypothesisStatus,
)


class HypothesisGenerator:
    """
    Synthesizes multiple competing root-cause hypotheses from causal graph paths,
    evaluating supporting evidence and computing calibrated confidence.
    """

    def __init__(self, graph_builder: CausalGraphBuilder):
        self.graph = graph_builder

    def generate_competing_hypotheses(
        self,
        symptom_node_id: str,
        contradicting_evidence_by_node: Optional[Dict[str, List[str]]] = None,
        has_uncertain_timestamps: bool = False,
        is_synthetic_only: bool = False,
    ) -> List[CausalHypothesis]:
        """
        Extracts all candidate causal paths to the symptom, constructing a CausalHypothesis for each.
        """
        contra_map = contradicting_evidence_by_node or {}
        paths = self.graph.find_paths_to_symptom(symptom_node_id)
        hypotheses: List[CausalHypothesis] = []

        for idx, path in enumerate(paths):
            root_id = path[0]
            root_node = self.graph.nodes.get(root_id)
            if not root_node:
                continue

            # Gather supporting evidence along the path
            # Root node evidence proves root trigger; edge evidence proves transitions.
            # Symptom evidence only proves symptom occurrence.
            supporting: List[str] = list(root_node.evidence_refs)
            contradicting: List[str] = list(contra_map.get(root_id, []))
            correlation_penalty = 0.0

            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                edge = self.graph.get_edge(u, v)
                if edge:
                    supporting.extend(edge.evidence_refs)
                    if edge.edge_type == CausalEdgeType.CORRELATED_WITH:
                        # Correlation is not causation! Apply explicit penalty
                        correlation_penalty += 0.35
                v_node = self.graph.nodes.get(v)
                if v_node and v_node.node_type != CausalNodeType.OBSERVABLE_SYMPTOM:
                    supporting.extend(v_node.evidence_refs)
                    contradicting.extend(contra_map.get(v, []))

            # Deduplicate evidence
            supporting = sorted(list(set(supporting)))
            contradicting = sorted(list(set(contradicting)))

            # If root node has zero evidence, flag as missing evidence
            missing_count = 1 if len(root_node.evidence_refs) == 0 else 0

            conf, penalty, interval, status = ConfidenceCalculator.calculate_hypothesis_confidence(
                supporting_evidence_count=len(supporting),
                contradicting_evidence_count=len(contradicting),
                missing_evidence_count=missing_count,
                has_uncertain_timestamps=has_uncertain_timestamps,
                is_synthetic_only=is_synthetic_only,
            )
            penalty += correlation_penalty
            conf = max(0.0, round(conf * (1.0 - correlation_penalty), 3))
            if correlation_penalty > 0 and status == HypothesisStatus.CONFIRMED:
                status = HypothesisStatus.SUPPORTED if conf >= 0.45 else HypothesisStatus.INCONCLUSIVE

            path_desc = " -> ".join(path)
            hyp = CausalHypothesis(
                hypothesis_id=f"hyp_{idx + 1}_{root_id}",
                title=f"Root cause in '{root_node.subsystem}': {root_node.description}",
                root_cause_node_id=root_id,
                causal_path=path,
                supporting_evidence=supporting,
                contradicting_evidence=contradicting,
                missing_evidence=["REQUIRES_RUNTIME_VALIDATION"] if missing_count > 0 else [],
                confidence=conf,
                uncertainty_penalty=penalty,
                status=status,
                rationale=f"Causal chain: [{path_desc}]. Confidence derived from {len(supporting)} supporting and {len(contradicting)} contradicting evidence items.",
            )
            hypotheses.append(hyp)

        # Rank hypotheses by confidence descending
        return sorted(hypotheses, key=lambda h: h.confidence, reverse=True)
