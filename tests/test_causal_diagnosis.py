"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Focused Test Suite covering all scenarios from Section 8.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from backend.agents.causal_diagnosis import (
    CausalDiagnosisBridge,
    CausalDiagnosisError,
    CausalEdgeType,
    CausalNodeType,
    ConfidenceCalculator,
    CyclicCausalGraphError,
    DiagnosticOutcome,
    ExperimentOutcome,
    ExperimentScope,
    HypothesisStatus,
    InconclusiveDiagnosisError,
    TimelineReconstructor,
    UnauthorizedDiagnosticActionError,
)


class TestCausalDiagnosisEngine:

    @pytest.fixture(autouse=True)
    def setup_temp_env(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_phase78_test_")
        self.bridge = CausalDiagnosisBridge(store_dir=self.temp_dir)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Correct reconstruction of a known causal chain
    # -------------------------------------------------------------------------
    def test_01_reconstruct_known_causal_chain(self):
        # Chain: Config error -> Connection pool exhaustion -> Gateway Timeout (504)
        n1 = self.bridge.add_causal_node("n_conf", CausalNodeType.ROOT_CAUSE, "Config error: max_conn set to 1", "config", evidence_refs=["ev_conf"])
        n2 = self.bridge.add_causal_node("n_pool", CausalNodeType.INTERMEDIATE_EVENT, "Connection pool exhausted", "db", evidence_refs=["ev_pool"])
        n3 = self.bridge.add_causal_node("n_symp", CausalNodeType.OBSERVABLE_SYMPTOM, "HTTP 504 Gateway Timeout", "api_gateway", evidence_refs=["ev_504"])

        self.bridge.add_causal_edge("n_conf", "n_pool", CausalEdgeType.DIRECTLY_CAUSES)
        self.bridge.add_causal_edge("n_pool", "n_symp", CausalEdgeType.DIRECTLY_CAUSES)

        report = self.bridge.diagnose("n_symp")
        assert report.outcome == DiagnosticOutcome.ROOT_CAUSE_CONFIRMED
        assert "n_conf" in report.confirmed_root_causes
        assert "n_conf -> n_pool -> n_symp" in report.causal_chain_descriptions

    # -------------------------------------------------------------------------
    # Scenario 2: Distinguishing a symptom from its upstream cause
    # -------------------------------------------------------------------------
    def test_02_distinguish_symptom_from_upstream_cause(self):
        self.bridge.add_causal_node("cause", CausalNodeType.ROOT_CAUSE, "OOM killed background worker", "worker", evidence_refs=["ev_oom"])
        self.bridge.add_causal_node("symp", CausalNodeType.OBSERVABLE_SYMPTOM, "Job queue latency breached SLO", "queue", evidence_refs=["ev_lat"])
        self.bridge.add_causal_edge("cause", "symp", CausalEdgeType.DIRECTLY_CAUSES)

        candidates = self.bridge.graph.identify_candidate_root_causes("symp")
        assert "cause" in candidates
        assert "symp" not in candidates  # Symptom must never be identified as its own root cause

    # -------------------------------------------------------------------------
    # Scenario 3: Multiple competing root-cause hypotheses
    # -------------------------------------------------------------------------
    def test_03_multiple_competing_hypotheses(self):
        # Two competing root causes for high error rate
        self.bridge.add_causal_node("rc_a", CausalNodeType.ROOT_CAUSE, "Schema migration syntax error", "db", evidence_refs=["ev_a1", "ev_a2"])
        self.bridge.add_causal_node("rc_b", CausalNodeType.ROOT_CAUSE, "Third-party payment gateway 502", "payment", evidence_refs=["ev_b1"])
        self.bridge.add_causal_node("symptom", CausalNodeType.OBSERVABLE_SYMPTOM, "Checkout endpoint 500 error", "checkout")

        self.bridge.add_causal_edge("rc_a", "symptom", CausalEdgeType.DIRECTLY_CAUSES)
        self.bridge.add_causal_edge("rc_b", "symptom", CausalEdgeType.DIRECTLY_CAUSES)

        report = self.bridge.diagnose("symptom")
        assert len(report.hypotheses) == 2
        # rc_a has 2 evidence items vs 1 for rc_b -> rc_a ranks first
        assert report.hypotheses[0].root_cause_node_id == "rc_a"
        assert report.hypotheses[1].root_cause_node_id == "rc_b"

    # -------------------------------------------------------------------------
    # Scenario 4: Correlation without sufficient causal evidence
    # -------------------------------------------------------------------------
    def test_04_correlation_without_sufficient_causal_evidence(self):
        # Unrelated cron job ran at the same time as service crash
        self.bridge.add_causal_node("cron", CausalNodeType.CONTRIBUTING_FACTOR, "Hourly backup cron executed", "cron", evidence_refs=[])
        self.bridge.add_causal_node("crash", CausalNodeType.OBSERVABLE_SYMPTOM, "Web process segfault", "web", evidence_refs=["ev_core"])
        self.bridge.add_causal_edge("cron", "crash", CausalEdgeType.CORRELATED_WITH)

        report = self.bridge.diagnose("crash")
        # Missing evidence causes confidence to stay low and inconclusive
        assert report.outcome in (DiagnosticOutcome.INCONCLUSIVE_INSUFFICIENT_EVIDENCE, DiagnosticOutcome.NO_CAUSAL_LINK_FOUND)
        assert len(report.confirmed_root_causes) == 0

    # -------------------------------------------------------------------------
    # Scenario 5: Incorrect temporal ordering and missing timestamps
    # -------------------------------------------------------------------------
    def test_05_missing_timestamps_triggers_uncertainty_penalty(self):
        self.bridge.add_context_event("ev1", "auth", "LOGIN_ATTEMPT", "User login", timestamp=None)  # Missing timestamp
        self.bridge.add_context_event("ev2", "auth", "CRASH", "Auth crashed", timestamp=100.0)

        inversions = self.bridge.timeline.detect_temporal_inversions()
        assert len(inversions) > 0

        self.bridge.add_causal_node("auth_bug", CausalNodeType.ROOT_CAUSE, "Auth null pointer", "auth", evidence_refs=["ev_auth"])
        self.bridge.add_causal_node("auth_down", CausalNodeType.OBSERVABLE_SYMPTOM, "Auth service unreachable", "gateway")
        self.bridge.add_causal_edge("auth_bug", "auth_down")

        report = self.bridge.diagnose("auth_down")
        # Uncertainty penalty applied due to uncertain timestamps
        assert report.hypotheses[0].uncertainty_penalty > 0.0

    # -------------------------------------------------------------------------
    # Scenario 6: Contradictory observations reject hypothesis
    # -------------------------------------------------------------------------
    def test_06_contradictory_evidence_rejects_hypothesis(self):
        self.bridge.add_causal_node("rc_mem", CausalNodeType.ROOT_CAUSE, "Memory leak", "server", evidence_refs=["ev_oom"])
        self.bridge.add_causal_node("symp_perf", CausalNodeType.OBSERVABLE_SYMPTOM, "High latency", "server")
        self.bridge.add_causal_edge("rc_mem", "symp_perf")

        # Contradicting evidence: memory profile shows memory was 20% free and stable
        report = self.bridge.diagnose(
            "symp_perf",
            contradicting_evidence_by_node={"rc_mem": ["ev_mem_normal_profile", "ev_no_swap"]}
        )
        assert report.hypotheses[0].status == HypothesisStatus.REJECTED
        assert report.outcome == DiagnosticOutcome.CONTRADICTED_BY_EVIDENCE

    # -------------------------------------------------------------------------
    # Scenario 7: Missing, stale, or invalidated evidence
    # -------------------------------------------------------------------------
    def test_07_missing_evidence_keeps_diagnosis_inconclusive(self):
        self.bridge.add_causal_node("rc_hypothetical", CausalNodeType.ROOT_CAUSE, "Network partition", "net", evidence_refs=[])
        self.bridge.add_causal_node("symp_timeout", CausalNodeType.OBSERVABLE_SYMPTOM, "RPC timeout", "client")
        self.bridge.add_causal_edge("rc_hypothetical", "symp_timeout")

        report = self.bridge.diagnose("symp_timeout")
        assert report.outcome == DiagnosticOutcome.INCONCLUSIVE_INSUFFICIENT_EVIDENCE
        assert report.hypotheses[0].status == HypothesisStatus.INCONCLUSIVE

    # -------------------------------------------------------------------------
    # Scenario 8: Synthetic evidence penalized versus real execution evidence
    # -------------------------------------------------------------------------
    def test_08_synthetic_evidence_receives_uncertainty_penalty(self):
        self.bridge.add_causal_node("rc_syn", CausalNodeType.ROOT_CAUSE, "Synthetic load bottleneck", "perf", evidence_refs=["ev_syn"])
        self.bridge.add_causal_node("symp_syn", CausalNodeType.OBSERVABLE_SYMPTOM, "Throughput dip", "perf")
        self.bridge.add_causal_edge("rc_syn", "symp_syn")

        report = self.bridge.diagnose("symp_syn", is_synthetic=True)
        assert report.hypotheses[0].uncertainty_penalty >= 0.20

    # -------------------------------------------------------------------------
    # Scenario 9: Cycle detection in causal DAG
    # -------------------------------------------------------------------------
    def test_09_cycle_detection_in_causal_dag(self):
        self.bridge.add_causal_node("A", CausalNodeType.INTERMEDIATE_EVENT, "State A", "sys")
        self.bridge.add_causal_node("B", CausalNodeType.INTERMEDIATE_EVENT, "State B", "sys")
        self.bridge.add_causal_edge("A", "B")

        # Adding B -> A creates a cycle
        with pytest.raises(CyclicCausalGraphError):
            self.bridge.add_causal_edge("B", "A")

    # -------------------------------------------------------------------------
    # Scenario 10: Multiple interacting causes
    # -------------------------------------------------------------------------
    def test_10_multiple_interacting_causes(self):
        self.bridge.add_causal_node("rc_1", CausalNodeType.ROOT_CAUSE, "CPU throttling", "infra", evidence_refs=["ev1", "ev2"])
        self.bridge.add_causal_node("rc_2", CausalNodeType.ROOT_CAUSE, "Unindexed SQL query", "db", evidence_refs=["ev3", "ev4"])
        self.bridge.add_causal_node("symp_slow", CausalNodeType.OBSERVABLE_SYMPTOM, "API degraded", "api")

        self.bridge.add_causal_edge("rc_1", "symp_slow")
        self.bridge.add_causal_edge("rc_2", "symp_slow")

        report = self.bridge.diagnose("symp_slow")
        assert report.outcome == DiagnosticOutcome.MULTIPLE_INTERACTING_CAUSES
        assert "rc_1" in report.confirmed_root_causes
        assert "rc_2" in report.confirmed_root_causes

    # -------------------------------------------------------------------------
    # Scenario 11: A misleading but plausible hypothesis is out-ranked
    # -------------------------------------------------------------------------
    def test_11_misleading_hypothesis_outranked(self):
        # Misleading: DNS issue (1 weak log) vs True cause: Bad deploy commit (3 solid logs)
        self.bridge.add_causal_node("dns_lag", CausalNodeType.ROOT_CAUSE, "DNS latency spike", "dns", evidence_refs=["dns_log"])
        self.bridge.add_causal_node("bad_commit", CausalNodeType.ROOT_CAUSE, "Buggy regex in v2.1 commit", "app", evidence_refs=["git_diff", "stack_trace", "test_failure"])
        self.bridge.add_causal_node("crash_app", CausalNodeType.OBSERVABLE_SYMPTOM, "App crash", "app")

        self.bridge.add_causal_edge("dns_lag", "crash_app")
        self.bridge.add_causal_edge("bad_commit", "crash_app")

        report = self.bridge.diagnose("crash_app")
        assert report.hypotheses[0].root_cause_node_id == "bad_commit"
        assert report.hypotheses[0].confidence > report.hypotheses[1].confidence

    # -------------------------------------------------------------------------
    # Scenario 12: Insufficient evidence and an inconclusive diagnosis
    # -------------------------------------------------------------------------
    def test_12_insufficient_evidence_returns_inconclusive(self):
        self.bridge.add_causal_node("unknown_node", CausalNodeType.ROOT_CAUSE, "Possible issue", "sys", evidence_refs=[])
        self.bridge.add_causal_node("symp_iso", CausalNodeType.OBSERVABLE_SYMPTOM, "Spike", "sys")
        self.bridge.add_causal_edge("unknown_node", "symp_iso")

        report = self.bridge.diagnose("symp_iso")
        assert report.outcome == DiagnosticOutcome.INCONCLUSIVE_INSUFFICIENT_EVIDENCE
        assert len(report.confirmed_root_causes) == 0

    # -------------------------------------------------------------------------
    # Scenario 13: Confidence rationale and deterministic ranking
    # -------------------------------------------------------------------------
    def test_13_deterministic_confidence_calculation(self):
        c1, p1, i1, s1 = ConfidenceCalculator.calculate_hypothesis_confidence(3, 0, 0)
        c2, p2, i2, s2 = ConfidenceCalculator.calculate_hypothesis_confidence(3, 0, 0)
        assert c1 == c2
        assert s1 == HypothesisStatus.CONFIRMED

        # Contradictions reduce confidence
        c_contra, _, _, s_contra = ConfidenceCalculator.calculate_hypothesis_confidence(3, 2, 0)
        assert c_contra < c1

    # -------------------------------------------------------------------------
    # Scenario 14: Selection of a useful discriminating observation
    # -------------------------------------------------------------------------
    def test_14_plan_discriminating_experiment(self):
        h1 = self.bridge.hypothesizer.generate_competing_hypotheses
        exp = self.bridge.plan_diagnostic_experiment(
            hypothesis_a_id="hyp_thread_deadlock",
            hypothesis_b_id="hyp_oom_kill",
            inspection_check="jstack -l <pid>",
            expected_if_a="Found 1 deadlock",
            expected_if_b="No deadlock found",
        )
        assert exp.is_read_only is True
        assert exp.scope == ExperimentScope.READ_ONLY_INSPECTION

    # -------------------------------------------------------------------------
    # Scenario 15: Diagnostic experiment execution and outcome evaluation
    # -------------------------------------------------------------------------
    def test_15_execute_diagnostic_experiment_success(self):
        exp = self.bridge.plan_diagnostic_experiment(
            hypothesis_a_id="hyp_pool_starve",
            hypothesis_b_id="hyp_db_down",
            inspection_check="curl localhost:8080/metrics",
            expected_if_a="pool.active == 50",
            expected_if_b="pool.active == 0",
        )
        outcome, expl = self.bridge.run_diagnostic_experiment(
            exp.experiment_id,
            actual_observation="pool.active == 50; queue.waiting == 120"
        )
        assert outcome == ExperimentOutcome.SUCCESS
        assert "confirms hypothesis" in expl

    # -------------------------------------------------------------------------
    # Scenario 16: Prevention of unauthorised or destructive experiments
    # -------------------------------------------------------------------------
    def test_16_prevent_destructive_experiment(self):
        with pytest.raises(UnauthorizedDiagnosticActionError):
            self.bridge.plan_diagnostic_experiment(
                "hyp1", "hyp2",
                inspection_check="rm -rf /var/log/*",  # Destructive!
                expected_if_a="", expected_if_b=""
            )

    # -------------------------------------------------------------------------
    # Scenario 17: Experiment requiring authorization is blocked without token
    # -------------------------------------------------------------------------
    def test_17_experiment_requires_authorization(self):
        exp = self.bridge.plan_diagnostic_experiment(
            "hyp1", "hyp2",
            inspection_check="tcpdump -i eth0 -c 100",
            expected_if_a="SYN flood",
            expected_if_b="normal",
            scope=ExperimentScope.PRIVILEGED_CHECK,
            requires_authorization=True,
        )
        outcome, expl = self.bridge.run_diagnostic_experiment(
            exp.experiment_id,
            actual_observation="SYN flood detected",
            auth_token=None  # No token!
        )
        assert outcome == ExperimentOutcome.BLOCKED
        assert "authorization token required" in expl

    # -------------------------------------------------------------------------
    # Scenario 18: Experiment with valid authorization succeeds
    # -------------------------------------------------------------------------
    def test_18_experiment_with_valid_authorization_token(self):
        exp = self.bridge.plan_diagnostic_experiment(
            "hyp1", "hyp2",
            inspection_check="tcpdump -i eth0 -c 100",
            expected_if_a="SYN flood",
            expected_if_b="normal",
            scope=ExperimentScope.PRIVILEGED_CHECK,
            requires_authorization=True,
        )
        outcome, expl = self.bridge.run_diagnostic_experiment(
            exp.experiment_id,
            actual_observation="SYN flood detected",
            auth_token="AUTH_TOKEN_SEC_2026",
        )
        assert outcome == ExperimentOutcome.SUCCESS

    # -------------------------------------------------------------------------
    # Scenario 19: Outcome reconciliation after remediation
    # -------------------------------------------------------------------------
    def test_19_outcome_reconciliation_success(self):
        n_rc = self.bridge.add_causal_node("n_leak", CausalNodeType.ROOT_CAUSE, "Goroutine leak", "app", evidence_refs=["ev_leak"])
        n_sym = self.bridge.add_causal_node("n_crash", CausalNodeType.OBSERVABLE_SYMPTOM, "OOM crash", "app")
        self.bridge.add_causal_edge("n_leak", "n_crash")

        report = self.bridge.diagnose("n_crash")
        assert len(report.recommendations) > 0
        action = report.recommendations[0]

        # Post-remediation telemetry shows all healthy
        resolved, expl = self.bridge.reconcile_remediation(
            report.diagnosis_id,
            action.action_id,
            post_remediation_telemetry={"failed_tests": 0, "has_active_incidents": False}
        )
        assert resolved is True
        assert "successfully eliminated root cause" in expl

    # -------------------------------------------------------------------------
    # Scenario 20: Outcome reconciliation detects remediation failure
    # -------------------------------------------------------------------------
    def test_20_outcome_reconciliation_detects_failure(self):
        n_rc = self.bridge.add_causal_node("n_rc_fail", CausalNodeType.ROOT_CAUSE, "Defect", "sys", evidence_refs=["ev1"])
        n_sym = self.bridge.add_causal_node("n_sym_fail", CausalNodeType.OBSERVABLE_SYMPTOM, "Crash", "sys")
        self.bridge.add_causal_edge("n_rc_fail", "n_sym_fail")

        report = self.bridge.diagnose("n_sym_fail")
        action = report.recommendations[0]

        # Post-remediation telemetry still shows active failure
        resolved, expl = self.bridge.reconcile_remediation(
            report.diagnosis_id,
            action.action_id,
            post_remediation_telemetry={"failed_tests": 2, "has_active_incidents": True}
        )
        assert resolved is False
        assert "did NOT resolve the incident" in expl

    # -------------------------------------------------------------------------
    # Scenario 21: Integration with Phase 71 Incident Ingestion
    # -------------------------------------------------------------------------
    def test_21_integration_with_phase_71_incident_ingest(self):
        symptom_id = self.bridge.intake_incident(
            incident_id="INC-2026-901",
            service="order_service",
            category="PROCESS_CRASH",
            description="Process terminated with exit code 137 (SIGKILL)",
        )
        assert symptom_id == "node_symptom_INC-2026-901"
        assert symptom_id in self.bridge.graph.nodes

    # -------------------------------------------------------------------------
    # Scenario 22: Integration with Phase 72 Reliability Signals
    # -------------------------------------------------------------------------
    def test_22_integration_with_phase_72_signals(self):
        from backend.agents.causal_diagnosis.adapters import Phase72ReliabilityAdapter
        node_id = Phase72ReliabilityAdapter.ingest_signal(
            signal_id="sig_cpu_99",
            service="order_service",
            signal_type="ANOMALY",
            details="CPU usage spiked to 99%",
            timestamp=100.0,
            timeline=self.bridge.timeline,
            graph=self.bridge.graph,
        )
        assert node_id in self.bridge.graph.nodes
        assert self.bridge.graph.nodes[node_id].node_type == CausalNodeType.CONTRIBUTING_FACTOR

    # -------------------------------------------------------------------------
    # Scenario 23: Integration with Phase 73 Macro-Refactoring Step Failure
    # -------------------------------------------------------------------------
    def test_23_integration_with_phase_73_refactoring(self):
        from backend.agents.causal_diagnosis.adapters import Phase73RefactoringAdapter
        node_id = Phase73RefactoringAdapter.ingest_step_failure(
            step_id="step_split_monolith",
            migration_id="mig_01",
            reason="Invariant INV_ZERO_CYCLIC_DEPENDENCY violated",
            timestamp=200.0,
            timeline=self.bridge.timeline,
            graph=self.bridge.graph,
        )
        assert node_id in self.bridge.graph.nodes
        assert self.bridge.graph.nodes[node_id].node_type == CausalNodeType.ROOT_CAUSE

    # -------------------------------------------------------------------------
    # Scenario 24: Persistence and crash recovery
    # -------------------------------------------------------------------------
    def test_24_persistence_and_crash_recovery(self):
        n_rc = self.bridge.add_causal_node("n_persist", CausalNodeType.ROOT_CAUSE, "Config error", "app", evidence_refs=["ev_p"])
        n_sym = self.bridge.add_causal_node("n_pers_sym", CausalNodeType.OBSERVABLE_SYMPTOM, "Timeout", "app")
        self.bridge.add_causal_edge("n_persist", "n_pers_sym")

        report = self.bridge.diagnose("n_pers_sym")

        # Load from disk with new bridge instance
        restarted_bridge = CausalDiagnosisBridge(store_dir=self.temp_dir)
        persisted_raw = restarted_bridge.store.get_diagnosis(report.diagnosis_id)
        assert persisted_raw is not None
        assert persisted_raw["outcome"] == report.outcome.value

    # -------------------------------------------------------------------------
    # Scenario 25: Topological sort enforces causes precede effects
    # -------------------------------------------------------------------------
    def test_25_topological_sort_enforces_order(self):
        self.bridge.add_causal_node("n1", CausalNodeType.ROOT_CAUSE, "C1", "s")
        self.bridge.add_causal_node("n2", CausalNodeType.INTERMEDIATE_EVENT, "C2", "s")
        self.bridge.add_causal_node("n3", CausalNodeType.OBSERVABLE_SYMPTOM, "C3", "s")

        self.bridge.add_causal_edge("n1", "n2")
        self.bridge.add_causal_edge("n2", "n3")

        order = self.bridge.graph.topological_sort()
        assert order == ["n1", "n2", "n3"]

    # -------------------------------------------------------------------------
    # Scenario 26: Graceful handling of empty causal graph
    # -------------------------------------------------------------------------
    def test_26_empty_graph_diagnose_raises_keyerror(self):
        with pytest.raises(KeyError):
            self.bridge.diagnose("non_existent_symptom")

    # -------------------------------------------------------------------------
    # Scenario 27: Isolated symptom with no edges
    # -------------------------------------------------------------------------
    def test_27_isolated_symptom_returns_no_causal_link(self):
        self.bridge.add_causal_node("iso_sym", CausalNodeType.OBSERVABLE_SYMPTOM, "Isolated event", "s")
        report = self.bridge.diagnose("iso_sym")
        assert report.outcome == DiagnosticOutcome.INCONCLUSIVE_INSUFFICIENT_EVIDENCE
        assert len(report.confirmed_root_causes) == 0

    # -------------------------------------------------------------------------
    # Scenario 28: Rejecting edge between non-existent nodes
    # -------------------------------------------------------------------------
    def test_28_edge_between_non_existent_nodes_raises_keyerror(self):
        with pytest.raises(KeyError):
            self.bridge.add_causal_edge("ghost_1", "ghost_2")

    # -------------------------------------------------------------------------
    # Scenario 29: Complex diamond causal graph
    # -------------------------------------------------------------------------
    def test_29_diamond_causal_graph(self):
        # A -> B -> D and A -> C -> D
        self.bridge.add_causal_node("A", CausalNodeType.ROOT_CAUSE, "Origin", "s", evidence_refs=["eA"])
        self.bridge.add_causal_node("B", CausalNodeType.INTERMEDIATE_EVENT, "Path 1", "s", evidence_refs=["eB"])
        self.bridge.add_causal_node("C", CausalNodeType.INTERMEDIATE_EVENT, "Path 2", "s", evidence_refs=["eC"])
        self.bridge.add_causal_node("D", CausalNodeType.OBSERVABLE_SYMPTOM, "Symptom", "s")

        self.bridge.add_causal_edge("A", "B")
        self.bridge.add_causal_edge("B", "D")
        self.bridge.add_causal_edge("A", "C")
        self.bridge.add_causal_edge("C", "D")

        paths = self.bridge.graph.find_paths_to_symptom("D")
        assert len(paths) == 2
        assert ["A", "B", "D"] in paths
        assert ["A", "C", "D"] in paths

    # -------------------------------------------------------------------------
    # Scenario 30: Ambiguous experiment observation returns INCONCLUSIVE
    # -------------------------------------------------------------------------
    def test_30_ambiguous_experiment_observation(self):
        exp = self.bridge.plan_diagnostic_experiment(
            "hyp1", "hyp2",
            inspection_check="netstat -an",
            expected_if_a="ESTABLISHED 100",
            expected_if_b="TIME_WAIT 100",
        )
        outcome, expl = self.bridge.run_diagnostic_experiment(
            exp.experiment_id,
            actual_observation="CLOSE_WAIT 50"  # Matches neither branch
        )
        assert outcome == ExperimentOutcome.INCONCLUSIVE
        assert "ambiguous" in expl.lower()

    # -------------------------------------------------------------------------
    # Scenario 31: Auditing trail recorded on every diagnosis
    # -------------------------------------------------------------------------
    def test_31_audit_trail_recorded(self):
        n_rc = self.bridge.add_causal_node("n_rc_audit", CausalNodeType.ROOT_CAUSE, "RC", "s", evidence_refs=["e"])
        n_sym = self.bridge.add_causal_node("n_sym_audit", CausalNodeType.OBSERVABLE_SYMPTOM, "SYM", "s")
        self.bridge.add_causal_edge("n_rc_audit", "n_sym_audit")

        report = self.bridge.diagnose("n_sym_audit")
        assert len(report.audit_trail) > 0
        assert "DIAGNOSIS_COMPLETED" in report.audit_trail[0]

    # -------------------------------------------------------------------------
    # Scenario 32: Recovery when base store directory is clean
    # -------------------------------------------------------------------------
    def test_32_recovery_from_clean_store(self):
        empty_bridge = CausalDiagnosisBridge(store_dir=tempfile.mkdtemp())
        assert len(empty_bridge.diagnoses) == 0

    # -------------------------------------------------------------------------
    # Scenario 33: Contributing factors do not mask primary root cause
    # -------------------------------------------------------------------------
    def test_33_contributing_factor_not_labeled_as_root_cause(self):
        self.bridge.add_causal_node("rc_prim", CausalNodeType.ROOT_CAUSE, "Primary flaw", "app", evidence_refs=["e1", "e2"])
        self.bridge.add_causal_node("contrib", CausalNodeType.CONTRIBUTING_FACTOR, "Heavy traffic", "net", evidence_refs=["e3"])
        self.bridge.add_causal_node("sym_fail", CausalNodeType.OBSERVABLE_SYMPTOM, "Outage", "app")

        self.bridge.add_causal_edge("rc_prim", "sym_fail")
        self.bridge.add_causal_edge("contrib", "sym_fail", CausalEdgeType.EXACERBATES)

        report = self.bridge.diagnose("sym_fail")
        assert "rc_prim" in report.confirmed_root_causes
        # contributing factor alone is not confirmed as independent root cause
        assert len(report.confirmed_root_causes) == 1

    # -------------------------------------------------------------------------
    # Scenario 34: Unverified edge confidence propagation
    # -------------------------------------------------------------------------
    def test_34_unverified_edge_confidence(self):
        edge = self.bridge.add_causal_node("n_a", CausalNodeType.ROOT_CAUSE, "A", "s")
        node_b = self.bridge.add_causal_node("n_b", CausalNodeType.OBSERVABLE_SYMPTOM, "B", "s")
        e = self.bridge.add_causal_edge("n_a", "n_b", confidence=0.4)
        assert e.confidence == 0.4

    # -------------------------------------------------------------------------
    # Scenario 35: Reconciling multiple corrective actions
    # -------------------------------------------------------------------------
    def test_35_reconcile_multiple_corrective_actions(self):
        n_rc = self.bridge.add_causal_node("n_rc_m", CausalNodeType.ROOT_CAUSE, "Multi defect", "s", evidence_refs=["e1"])
        n_sym = self.bridge.add_causal_node("n_sym_m", CausalNodeType.OBSERVABLE_SYMPTOM, "Crash", "s")
        self.bridge.add_causal_edge("n_rc_m", "n_sym_m")

        report = self.bridge.diagnose("n_sym_m")
        action = report.recommendations[0]

        # First attempt fails
        resolved_1, _ = self.bridge.reconcile_remediation(report.diagnosis_id, action.action_id, {"failed_tests": 1})
        assert resolved_1 is False

        # Second attempt succeeds
        resolved_2, _ = self.bridge.reconcile_remediation(report.diagnosis_id, action.action_id, {"failed_tests": 0, "has_active_incidents": False})
        assert resolved_2 is True

    # -------------------------------------------------------------------------
    # Scenario 36: ChatMissionBridge integration routing
    # -------------------------------------------------------------------------
    def test_36_chat_mission_bridge_routes_diagnosis_intent(self):
        from backend.services.chat_mission_bridge import ChatRequestResolver, ChatIntentType
        resolver = ChatRequestResolver()
        resolved = resolver.resolve_request("faz um diagnóstico da causa raiz do erro de timeout")
        assert resolved.intent == ChatIntentType.ROOT_CAUSE_DIAGNOSIS
        assert resolved.confidence >= 0.95
        assert resolved.planned_action == "causal_diagnosis"


