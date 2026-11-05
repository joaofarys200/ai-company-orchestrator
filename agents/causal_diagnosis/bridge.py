"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: bridge.py
Master strategic orchestrator executing the 11-stage closed-loop causal diagnosis lifecycle.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional, Set, Tuple

from .adapters import (
    Phase71IncidentAdapter,
    Phase72ReliabilityAdapter,
    Phase73RefactoringAdapter,
    Phase77EvidenceAdapter,
)
from .confidence import ConfidenceCalculator
from .experiments import DiagnosticExperimentPlanner
from .graph import CausalGraphBuilder
from .hypothesizer import HypothesisGenerator
from .models import (
    CausalEdge,
    CausalEdgeType,
    CausalHypothesis,
    CausalNode,
    CausalNodeType,
    CorrectiveAction,
    DiagnosisReport,
    DiagnosticExperiment,
    DiagnosticOutcome,
    ExperimentOutcome,
    ExperimentScope,
    HypothesisStatus,
)
from .persistence import CausalDiagnosisStore
from .recommender import CorrectiveActionRecommender
from .reconciliation import OutcomeReconciler
from .timeline import TimelineReconstructor


class CausalDiagnosisBridge:
    """
    Master bridge coordinating the 11-stage evidence-grounded causal diagnosis lifecycle:
    INTAKE -> CONTEXT -> TIMELINE -> HYPOTHESES -> CAUSAL DAG -> EVIDENCE ASSESSMENT ->
    DISCRIMINATION -> CONFIDENCE -> ROOT-CAUSE ASSESSMENT -> RECOMMENDATIONS -> OUTCOME RECONCILIATION.
    """

    def __init__(self, store_dir: str = ".jarvis/causal_diagnosis"):
        self.store = CausalDiagnosisStore(base_dir=store_dir)
        self.timeline = TimelineReconstructor()
        self.graph = CausalGraphBuilder()
        self.hypothesizer = HypothesisGenerator(self.graph)
        self.experiments: Dict[str, DiagnosticExperiment] = {}
        self.diagnoses: Dict[str, DiagnosisReport] = {}

    def intake_incident(
        self,
        incident_id: str,
        service: str,
        category: str,
        description: str,
        detection_time: Optional[float] = None,
    ) -> str:
        """Stage 1: Ingest observable failure symptom."""
        ts = detection_time or time.time()
        symptom_id = Phase71IncidentAdapter.ingest_incident(
            incident_id=incident_id,
            service=service,
            category=category,
            description=description,
            detection_time=ts,
            timeline=self.timeline,
            graph=self.graph,
        )
        return symptom_id

    def add_context_event(
        self,
        event_id: str,
        subsystem: str,
        event_type: str,
        description: str,
        timestamp: Optional[float] = None,
        payload: Optional[Dict] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> None:
        """Stage 2 & 3: Reconstruct context and chronological timeline."""
        self.timeline.add_event(
            event_id=event_id,
            subsystem=subsystem,
            event_type=event_type,
            description=description,
            timestamp=timestamp,
            payload=payload,
            evidence_refs=evidence_refs,
        )

    def add_causal_node(
        self,
        node_id: str,
        node_type: CausalNodeType,
        description: str,
        subsystem: str,
        timestamp: Optional[float] = None,
        evidence_refs: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> CausalNode:
        """Stage 5: Add a causal node into the causal DAG."""
        return self.graph.add_node(
            node_id=node_id,
            node_type=node_type,
            description=description,
            subsystem=subsystem,
            timestamp=timestamp,
            evidence_refs=evidence_refs,
            metadata=metadata,
        )

    def add_causal_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: CausalEdgeType = CausalEdgeType.DIRECTLY_CAUSES,
        confidence: float = 1.0,
        evidence_refs: Optional[List[str]] = None,
        mechanism: str = "",
    ) -> CausalEdge:
        """Stage 5: Link causal nodes in the DAG, strictly verifying absence of cycles."""
        return self.graph.add_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            confidence=confidence,
            evidence_refs=evidence_refs,
            mechanism=mechanism,
        )

    def diagnose(
        self,
        symptom_node_id: str,
        incident_id: Optional[str] = None,
        contradicting_evidence_by_node: Optional[Dict[str, List[str]]] = None,
        is_synthetic: bool = False,
    ) -> DiagnosisReport:
        """
        Stage 4, 6, 8, 9, 10: Generate competing hypotheses, assess evidence,
        compute calibrated confidence, designate root causes, and formulate recommendations.
        """
        symptom_node = self.graph.nodes.get(symptom_node_id)
        if not symptom_node:
            raise KeyError(f"Symptom node '{symptom_node_id}' not found in causal graph.")

        inc_id = incident_id or f"inc_{symptom_node_id}"
        diag_id = f"diag_{uuid.uuid4().hex[:8]}"

        # Check for uncertain timestamps in timeline
        inversions = self.timeline.detect_temporal_inversions()
        has_uncertain = len(inversions) > 0

        # Generate competing hypotheses
        hypotheses = self.hypothesizer.generate_competing_hypotheses(
            symptom_node_id=symptom_node_id,
            contradicting_evidence_by_node=contradicting_evidence_by_node,
            has_uncertain_timestamps=has_uncertain,
            is_synthetic_only=is_synthetic,
        )

        confirmed_root_causes: List[str] = []
        causal_chains: List[str] = []
        recommendations: List[CorrectiveAction] = []
        overall_outcome = DiagnosticOutcome.NO_CAUSAL_LINK_FOUND

        if not hypotheses:
            overall_outcome = DiagnosticOutcome.INCONCLUSIVE_INSUFFICIENT_EVIDENCE
            interval = (0.0, 0.2)
        else:
            top_hyp = hypotheses[0]
            interval = (
                max(0.0, round(top_hyp.confidence - 0.1, 2)),
                min(1.0, round(top_hyp.confidence + 0.1, 2)),
            )

            # Filter for true root causes (excluding contributing factors)
            supported = [h for h in hypotheses if h.status in (HypothesisStatus.SUPPORTED, HypothesisStatus.CONFIRMED)]
            root_supported = [
                h for h in supported
                if self.graph.nodes.get(h.root_cause_node_id) and
                self.graph.nodes[h.root_cause_node_id].node_type == CausalNodeType.ROOT_CAUSE
            ]

            if len(root_supported) > 1 and abs(root_supported[0].confidence - root_supported[1].confidence) < 0.1:
                overall_outcome = DiagnosticOutcome.MULTIPLE_INTERACTING_CAUSES
                for s in root_supported:
                    confirmed_root_causes.append(s.root_cause_node_id)
                    causal_chains.append(" -> ".join(s.causal_path))
                    root_n = self.graph.nodes.get(s.root_cause_node_id)
                    if root_n:
                        recommendations.extend(
                            CorrectiveActionRecommender.recommend_actions_for_hypothesis(
                                s, root_n.subsystem, root_n.description
                            )
                        )
            elif root_supported:
                best = root_supported[0]
                if best.confidence >= 0.60 and len(best.contradicting_evidence) == 0:
                    overall_outcome = DiagnosticOutcome.ROOT_CAUSE_CONFIRMED
                    best.status = HypothesisStatus.CONFIRMED
                    confirmed_root_causes.append(best.root_cause_node_id)
                    causal_chains.append(" -> ".join(best.causal_path))
                    root_n = self.graph.nodes.get(best.root_cause_node_id)
                    if root_n:
                        recommendations.extend(
                            CorrectiveActionRecommender.recommend_actions_for_hypothesis(
                                best, root_n.subsystem, root_n.description
                            )
                        )
                else:
                    overall_outcome = DiagnosticOutcome.INCONCLUSIVE_INSUFFICIENT_EVIDENCE
            elif all(h.status == HypothesisStatus.REJECTED for h in hypotheses):
                overall_outcome = DiagnosticOutcome.CONTRADICTED_BY_EVIDENCE
            else:
                overall_outcome = DiagnosticOutcome.INCONCLUSIVE_INSUFFICIENT_EVIDENCE

        report = DiagnosisReport(
            diagnosis_id=diag_id,
            incident_id=inc_id,
            symptom_description=symptom_node.description,
            outcome=overall_outcome,
            hypotheses=hypotheses,
            confirmed_root_causes=confirmed_root_causes,
            causal_chain_descriptions=causal_chains,
            recommendations=recommendations,
            confidence_interval=interval,
            audit_trail=[
                f"DIAGNOSIS_COMPLETED: outcome={overall_outcome.value}, "
                f"hypotheses_evaluated={len(hypotheses)}, "
                f"confirmed_causes={confirmed_root_causes}"
            ],
            timestamp=time.time(),
        )

        self.diagnoses[diag_id] = report
        self.store.save_diagnosis(report)
        return report

    def plan_diagnostic_experiment(
        self,
        hypothesis_a_id: str,
        hypothesis_b_id: str,
        inspection_check: str,
        expected_if_a: str,
        expected_if_b: str,
        scope: ExperimentScope = ExperimentScope.READ_ONLY_INSPECTION,
        requires_authorization: bool = False,
    ) -> DiagnosticExperiment:
        """Stage 7: Plan a safe diagnostic experiment to discriminate between competing hypotheses."""
        hyp_a = next((h for d in self.diagnoses.values() for h in d.hypotheses if h.hypothesis_id == hypothesis_a_id), None)
        hyp_b = next((h for d in self.diagnoses.values() for h in d.hypotheses if h.hypothesis_id == hypothesis_b_id), None)

        if not hyp_a or not hyp_b:
            # Fallback dummy representation if standalone
            hyp_a = CausalHypothesis(hypothesis_a_id, hypothesis_a_id, "node_a", [])
            hyp_b = CausalHypothesis(hypothesis_b_id, hypothesis_b_id, "node_b", [])

        exp = DiagnosticExperimentPlanner.plan_discriminating_experiment(
            hyp_a=hyp_a,
            hyp_b=hyp_b,
            inspection_check=inspection_check,
            expected_if_a=expected_if_a,
            expected_if_b=expected_if_b,
            scope=scope,
            requires_authorization=requires_authorization,
        )
        self.experiments[exp.experiment_id] = exp
        return exp

    def run_diagnostic_experiment(
        self,
        experiment_id: str,
        actual_observation: str,
        auth_token: Optional[str] = None,
    ) -> Tuple[ExperimentOutcome, str]:
        """Stage 7: Evaluate a diagnostic experiment against observed results."""
        exp = self.experiments.get(experiment_id)
        if not exp:
            raise KeyError(f"Experiment '{experiment_id}' not found.")
        return DiagnosticExperimentPlanner.evaluate_experiment_outcome(exp, actual_observation, auth_token)

    def reconcile_remediation(
        self,
        diagnosis_id: str,
        action_id: str,
        post_remediation_telemetry: Dict,
    ) -> Tuple[bool, str]:
        """Stage 11: Reconcile outcome after corrective remediation has been applied."""
        report = self.diagnoses.get(diagnosis_id)
        if not report:
            raw = self.store.get_diagnosis(diagnosis_id)
            if raw:
                report = DiagnosisReport(
                    diagnosis_id=raw["diagnosis_id"],
                    incident_id=raw["incident_id"],
                    symptom_description=raw["symptom_description"],
                    outcome=DiagnosticOutcome(raw["outcome"]),
                    hypotheses=[CausalHypothesis.from_dict(h) for h in raw.get("hypotheses", [])],
                    confirmed_root_causes=raw.get("confirmed_root_causes", []),
                    causal_chain_descriptions=raw.get("causal_chain_descriptions", []),
                    recommendations=[CorrectiveAction(**a) for a in raw.get("recommendations", [])],
                    confidence_interval=tuple(raw.get("confidence_interval", (0.0, 1.0))),
                    audit_trail=raw.get("audit_trail", []),
                    timestamp=raw.get("timestamp", 0.0),
                )
                self.diagnoses[diagnosis_id] = report

        if not report:
            raise KeyError(f"Diagnosis report '{diagnosis_id}' not found.")

        action = next((a for a in report.recommendations if a.action_id == action_id), None)
        if not action:
            action = CorrectiveAction(
                action_id=action_id,
                target_root_cause_id="unknown",
                action_type="REMEDIATION",
                description="Remediation",
                risks="",
                expected_effect="",
                verification_criteria="",
            )

        resolved, expl = OutcomeReconciler.reconcile_post_remediation(
            report=report,
            action=action,
            post_remediation_telemetry=post_remediation_telemetry,
        )
        self.store.save_diagnosis(report)
        return resolved, expl
