"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Focused Test Suite covering all scenarios from Section 9.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from backend.agents.adaptive_experimentation import (
    AdaptiveExperimentSelector,
    AdaptiveExperimentStore,
    AdaptiveExperimentationBridge,
    AdaptiveExperimentationError,
    AdaptiveStoppingEvaluator,
    BayesianBeliefUpdater,
    CandidateExperiment,
    InformationTheoreticEngine,
    InvestigationSession,
    InvestigationState,
    OutcomeFidelity,
    Phase75BudgetAdapter,
    Phase78CausalHypothesisAdapter,
    ScientificHypothesis,
    StoppingReason,
    UnauthorizedExperimentError,
)


class TestAdaptiveExperimentationEngine:

    @pytest.fixture(autouse=True)
    def setup_temp_env(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_phase79_test_")
        self.bridge = AdaptiveExperimentationBridge(store_dir=self.temp_dir)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Correct Shannon entropy calculation
    # -------------------------------------------------------------------------
    def test_01_shannon_entropy_calculation(self):
        # Uniform distribution across 2 hypotheses has exactly 1.0 bit entropy
        h2 = InformationTheoreticEngine.calculate_entropy([0.5, 0.5])
        assert h2 == 1.0

        # Uniform across 4 hypotheses has 2.0 bits entropy
        h4 = InformationTheoreticEngine.calculate_entropy([0.25, 0.25, 0.25, 0.25])
        assert h4 == 2.0

        # Deterministic certainty has 0.0 bits entropy
        h_cert = InformationTheoreticEngine.calculate_entropy([1.0, 0.0])
        assert h_cert == 0.0

    # -------------------------------------------------------------------------
    # Scenario 2: Correct Expected Information Gain (EIG) calculation
    # -------------------------------------------------------------------------
    def test_02_expected_information_gain_calculation(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.5, 0.5),
            ScientificHypothesis("H2", "Issue 2", 0.5, 0.5),
        ]
        # Perfect discriminator: outcome A occurs 100% under H1, outcome B 100% under H2
        perfect_exp = CandidateExperiment(
            experiment_id="E_perf",
            title="Perfect Discriminator",
            probe_check="probe_check",
            outcome_likelihoods={
                "Outcome_A": {"H1": 1.0, "H2": 0.0},
                "Outcome_B": {"H1": 0.0, "H2": 1.0},
            },
        )
        eig = InformationTheoreticEngine.calculate_expected_information_gain(hyps, perfect_exp)
        # Should reduce prior entropy (1.0 bit) to 0.0 bits -> EIG = 1.0 bit
        assert eig == 1.0

    # -------------------------------------------------------------------------
    # Scenario 3: Uninformative experiment yields zero EIG
    # -------------------------------------------------------------------------
    def test_03_uninformative_experiment_zero_eig(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.5, 0.5),
            ScientificHypothesis("H2", "Issue 2", 0.5, 0.5),
        ]
        # Useless check: outcome occurs with equal probability under both hypotheses
        useless_exp = CandidateExperiment(
            experiment_id="E_useless",
            title="Uninformative Check",
            probe_check="dummy_check",
            outcome_likelihoods={
                "Observed": {"H1": 0.5, "H2": 0.5},
            },
        )
        eig = InformationTheoreticEngine.calculate_expected_information_gain(hyps, useless_exp)
        assert eig == 0.0

    # -------------------------------------------------------------------------
    # Scenario 4: Prefer low-cost experiment over equivalent high-cost alternative
    # -------------------------------------------------------------------------
    def test_04_prefer_low_cost_experiment(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.5, 0.5),
            ScientificHypothesis("H2", "Issue 2", 0.5, 0.5),
        ]
        # Both experiments have identical EIG (1.0 bit)
        exp_cheap = CandidateExperiment(
            experiment_id="E_cheap",
            title="Cheap Metric Check",
            probe_check="check_metric",
            outcome_likelihoods={"A": {"H1": 1.0, "H2": 0.0}, "B": {"H1": 0.0, "H2": 1.0}},
            cost=0.05,
            risk=0.0,
        )
        exp_expensive = CandidateExperiment(
            experiment_id="E_expensive",
            title="Heavy Bench Check",
            probe_check="heavy_bench",
            outcome_likelihoods={"A": {"H1": 1.0, "H2": 0.0}, "B": {"H1": 0.0, "H2": 1.0}},
            cost=0.90,
            risk=0.0,
        )

        ranked = AdaptiveExperimentSelector.rank_candidate_experiments(hyps, [exp_expensive, exp_cheap])
        assert ranked[0].experiment_id == "E_cheap"
        assert ranked[0].utility_score > ranked[1].utility_score

    # -------------------------------------------------------------------------
    # Scenario 5: Prefer low-risk experiment over equivalent high-risk alternative
    # -------------------------------------------------------------------------
    def test_05_prefer_low_risk_experiment(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.5, 0.5),
            ScientificHypothesis("H2", "Issue 2", 0.5, 0.5),
        ]
        exp_safe = CandidateExperiment(
            experiment_id="E_safe",
            title="Read-only Probe",
            probe_check="read_only_probe",
            outcome_likelihoods={"A": {"H1": 1.0, "H2": 0.0}, "B": {"H1": 0.0, "H2": 1.0}},
            cost=0.1,
            risk=0.0,
        )
        exp_risky = CandidateExperiment(
            experiment_id="E_risky",
            title="Intrusive Probe",
            probe_check="intrusive_probe",
            outcome_likelihoods={"A": {"H1": 1.0, "H2": 0.0}, "B": {"H1": 0.0, "H2": 1.0}},
            cost=0.1,
            risk=0.7,
        )

        ranked = AdaptiveExperimentSelector.rank_candidate_experiments(hyps, [exp_risky, exp_safe])
        assert ranked[0].experiment_id == "E_safe"
        assert ranked[0].utility_score > ranked[1].utility_score

    # -------------------------------------------------------------------------
    # Scenario 6: Bayesian belief update increases probability of supported hypothesis
    # -------------------------------------------------------------------------
    def test_06_bayesian_belief_update_success(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.5, 0.5),
            ScientificHypothesis("H2", "Issue 2", 0.5, 0.5),
        ]
        exp = CandidateExperiment(
            experiment_id="E1",
            title="Check A",
            probe_check="probe_a",
            outcome_likelihoods={
                "MATCH_A": {"H1": 0.95, "H2": 0.05},
                "MATCH_B": {"H1": 0.05, "H2": 0.95},
            },
        )
        updated, matched = BayesianBeliefUpdater.update_beliefs(hyps, exp, "MATCH_A detected")
        assert matched == "MATCH_A"
        h1 = next(h for h in updated if h.hypothesis_id == "H1")
        h2 = next(h for h in updated if h.hypothesis_id == "H2")
        assert h1.posterior_probability > 0.90
        assert h2.posterior_probability < 0.10
        assert h1.status == "CONFIRMED"

    # -------------------------------------------------------------------------
    # Scenario 7: Contradictory observation refutes leading hypothesis
    # -------------------------------------------------------------------------
    def test_07_contradictory_observation_refutes_leading_hypothesis(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.8, 0.8),
            ScientificHypothesis("H2", "Issue 2", 0.2, 0.2),
        ]
        exp = CandidateExperiment(
            experiment_id="E1",
            title="Check B",
            probe_check="probe_b",
            outcome_likelihoods={
                "MATCH_B": {"H1": 0.01, "H2": 0.99},
            },
        )
        updated, _ = BayesianBeliefUpdater.update_beliefs(hyps, exp, "MATCH_B found")
        h1 = next(h for h in updated if h.hypothesis_id == "H1")
        h2 = next(h for h in updated if h.hypothesis_id == "H2")
        # H1 collapsed, H2 surged
        assert h1.posterior_probability < 0.10
        assert h2.posterior_probability > 0.90

    # -------------------------------------------------------------------------
    # Scenario 8: Adaptive stopping when hypothesis confirmed
    # -------------------------------------------------------------------------
    def test_08_stopping_when_hypothesis_confirmed(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.92, 0.92),
            ScientificHypothesis("H2", "Issue 2", 0.08, 0.08),
        ]
        should_stop, reason, rationale = AdaptiveStoppingEvaluator.evaluate_stopping_criteria(
            hypotheses=hyps,
            remaining_candidates=[],
            accumulated_cost=0.1,
            cost_budget=1.0,
        )
        assert should_stop is True
        assert reason == StoppingReason.HYPOTHESIS_CONFIRMED
        assert "confirmed" in rationale.lower()

    # -------------------------------------------------------------------------
    # Scenario 9: Adaptive stopping when minimal entropy reached
    # -------------------------------------------------------------------------
    def test_09_stopping_when_minimal_entropy_reached(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.97, 0.97),
            ScientificHypothesis("H2", "Issue 2", 0.03, 0.03),
        ]
        should_stop, reason, _ = AdaptiveStoppingEvaluator.evaluate_stopping_criteria(
            hypotheses=hyps,
            remaining_candidates=[],
            accumulated_cost=0.2,
            cost_budget=1.0,
        )
        assert should_stop is True
        assert reason in (StoppingReason.HYPOTHESIS_CONFIRMED, StoppingReason.MINIMAL_UNCERTAINTY)

    # -------------------------------------------------------------------------
    # Scenario 10: Adaptive stopping when cost budget exhausted
    # -------------------------------------------------------------------------
    def test_10_stopping_when_budget_exhausted(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.55, 0.55),
            ScientificHypothesis("H2", "Issue 2", 0.45, 0.45),
        ]
        should_stop, reason, rationale = AdaptiveStoppingEvaluator.evaluate_stopping_criteria(
            hypotheses=hyps,
            remaining_candidates=[],
            accumulated_cost=1.05,
            cost_budget=1.0,
        )
        assert should_stop is True
        assert reason == StoppingReason.BUDGET_EXHAUSTED
        assert "budget" in rationale.lower()

    # -------------------------------------------------------------------------
    # Scenario 11: Adaptive stopping when diminishing returns on EIG
    # -------------------------------------------------------------------------
    def test_11_stopping_when_diminishing_information_gain(self):
        hyps = [
            ScientificHypothesis("H1", "Issue 1", 0.55, 0.55),
            ScientificHypothesis("H2", "Issue 2", 0.45, 0.45),
        ]
        weak_exp = CandidateExperiment(
            experiment_id="E_weak",
            title="Weak Check",
            probe_check="weak_check",
            outcome_likelihoods={"A": {"H1": 0.51, "H2": 0.49}},
            expected_info_gain=0.001,  # < 0.05
        )
        should_stop, reason, rationale = AdaptiveStoppingEvaluator.evaluate_stopping_criteria(
            hypotheses=hyps,
            remaining_candidates=[weak_exp],
            accumulated_cost=0.1,
            cost_budget=1.0,
        )
        assert should_stop is True
        assert reason == StoppingReason.DIMINISHING_INFORMATION_GAIN

    # -------------------------------------------------------------------------
    # Scenario 12: Prevention of destructive experiment commands
    # -------------------------------------------------------------------------
    def test_12_prevention_of_destructive_commands(self):
        from backend.agents.adaptive_experimentation.executor import ExperimentExecutor
        destructive_exp = CandidateExperiment(
            experiment_id="E_rm",
            title="Destructive check",
            probe_check="rm -rf /tmp/data",
            outcome_likelihoods={},
        )
        with pytest.raises(UnauthorizedExperimentError):
            ExperimentExecutor.execute_experiment(destructive_exp, "observation", "matched")

    # -------------------------------------------------------------------------
    # Scenario 13: Privileged experiment requires authorization token
    # -------------------------------------------------------------------------
    def test_13_privileged_experiment_requires_authorization(self):
        from backend.agents.adaptive_experimentation.executor import ExperimentExecutor
        priv_exp = CandidateExperiment(
            experiment_id="E_priv",
            title="Privileged trace",
            probe_check="perf record -a",
            outcome_likelihoods={},
            requires_authorization=True,
        )
        # Without auth token
        with pytest.raises(UnauthorizedExperimentError):
            ExperimentExecutor.execute_experiment(priv_exp, "observation", "matched", auth_token=None)

        # With auth token
        rec = ExperimentExecutor.execute_experiment(priv_exp, "observation", "matched", auth_token="AUTH_PRIV_79")
        assert rec.experiment_id == "E_priv"

    # -------------------------------------------------------------------------
    # Scenario 14: Synthetic fixture evidence applies discount
    # -------------------------------------------------------------------------
    def test_14_synthetic_fixture_evidence_applies_discount(self):
        hyps_real = [ScientificHypothesis("H1", "H1", 0.5, 0.5), ScientificHypothesis("H2", "H2", 0.5, 0.5)]
        hyps_syn = [ScientificHypothesis("H1", "H1", 0.5, 0.5), ScientificHypothesis("H2", "H2", 0.5, 0.5)]
        exp = CandidateExperiment(
            experiment_id="E",
            title="Check",
            probe_check="probe",
            outcome_likelihoods={"A": {"H1": 1.0, "H2": 0.0}},
        )
        # Real update
        up_real, _ = BayesianBeliefUpdater.update_beliefs(hyps_real, exp, "A", is_synthetic=False)
        # Synthetic update
        up_syn, _ = BayesianBeliefUpdater.update_beliefs(hyps_syn, exp, "A", is_synthetic=True)

        # Synthetic update should be more conservative (blended with prior)
        assert up_real[0].posterior_probability > up_syn[0].posterior_probability

    # -------------------------------------------------------------------------
    # Scenario 15: Full adaptive investigation step loop via bridge
    # -------------------------------------------------------------------------
    def test_15_full_investigation_step_loop(self):
        hyps = [
            ScientificHypothesis("H_deadlock", "DB Deadlock", 0.5, 0.5),
            ScientificHypothesis("H_pool_starve", "Pool Starvation", 0.5, 0.5),
        ]
        cand1 = CandidateExperiment(
            experiment_id="E_pool_metric",
            title="Poll Pool Active Count",
            probe_check="curl -s localhost:8080/metrics",
            outcome_likelihoods={
                "POOL_FULL": {"H_deadlock": 0.1, "H_pool_starve": 0.95},
                "POOL_IDLE": {"H_deadlock": 0.9, "H_pool_starve": 0.05},
            },
            cost=0.05,
            risk=0.0,
        )
        session = self.bridge.create_investigation("High DB Latency", hyps, [cand1], cost_budget=0.5)
        assert session.state == InvestigationState.INITIALIZED

        # Execute step with observation POOL_FULL
        updated_session, executed_exp = self.bridge.step_investigation(
            session.session_id,
            observation="POOL_FULL detected: active==max",
        )
        assert executed_exp.experiment_id == "E_pool_metric"
        # Belief updated in favor of pool starvation
        h_starve = next(h for h in updated_session.hypotheses if h.hypothesis_id == "H_pool_starve")
        assert h_starve.posterior_probability > 0.85
        assert updated_session.state == InvestigationState.STOPPED
        assert updated_session.stopping_reason == StoppingReason.HYPOTHESIS_CONFIRMED

    # -------------------------------------------------------------------------
    # Scenario 16: Persistence and recovery of investigation session
    # -------------------------------------------------------------------------
    def test_16_persistence_and_recovery(self):
        hyps = [ScientificHypothesis("H1", "Issue", 0.5, 0.5)]
        session = self.bridge.create_investigation("Crash Investigation", hyps, [], cost_budget=1.0)

        # Recover from disk in fresh bridge
        fresh_bridge = AdaptiveExperimentationBridge(store_dir=self.temp_dir)
        recovered = fresh_bridge._get_session_or_recover(session.session_id)
        assert recovered.session_id == session.session_id
        assert recovered.question == "Crash Investigation"

    # -------------------------------------------------------------------------
    # Scenario 17: Adapting Phase 78 Causal Hypotheses
    # -------------------------------------------------------------------------
    def test_17_adapter_for_phase_78_hypotheses(self):
        class MockCausalHypothesis:
            def __init__(self, hid, title, conf):
                self.hypothesis_id = hid
                self.title = title
                self.confidence = conf
                self.supporting_evidence = ["ev1"]
                self.status = "SUPPORTED"

        causal_hyps = [
            MockCausalHypothesis("h1", "Cause 1", 0.8),
            MockCausalHypothesis("h2", "Cause 2", 0.2),
        ]
        adapted = Phase78CausalHypothesisAdapter.adapt_causal_hypotheses(causal_hyps)
        assert len(adapted) == 2
        # Sum of normalized priors must equal 1.0
        assert round(adapted[0].prior_probability + adapted[1].prior_probability, 2) == 1.0

    # -------------------------------------------------------------------------
    # Scenario 18: Adapting Phase 75 Portfolio Budget
    # -------------------------------------------------------------------------
    def test_18_adapter_for_phase_75_budget(self):
        b1 = Phase75BudgetAdapter.derive_cost_budget({"remaining_budget": 0.8})
        assert b1 == 0.8
        b_default = Phase75BudgetAdapter.derive_cost_budget(None)
        assert b_default == 1.0

    # -------------------------------------------------------------------------
    # Scenario 19: Provenance SHA-256 hash generated on execution
    # -------------------------------------------------------------------------
    def test_19_provenance_hash_generated(self):
        from backend.agents.adaptive_experimentation.executor import ExperimentExecutor
        exp = CandidateExperiment("E1", "T", "p", {})
        rec = ExperimentExecutor.execute_experiment(exp, "Observed text", "m")
        assert len(rec.provenance_hash) == 64  # SHA-256 hex string

    # -------------------------------------------------------------------------
    # Scenario 20: Stepping a stopped investigation returns without execution
    # -------------------------------------------------------------------------
    def test_20_stepping_stopped_investigation_is_noop(self):
        hyps = [ScientificHypothesis("H1", "H1", 0.95, 0.95)]
        session = self.bridge.create_investigation("Q", hyps, [], cost_budget=1.0)
        session.state = InvestigationState.STOPPED

        sess, exp = self.bridge.step_investigation(session.session_id, "observation")
        assert exp is None

    # -------------------------------------------------------------------------
    # Scenario 21: Ambiguous observation keeps beliefs unchanged
    # -------------------------------------------------------------------------
    def test_21_ambiguous_observation_preserves_beliefs(self):
        hyps = [ScientificHypothesis("H1", "H1", 0.5, 0.5), ScientificHypothesis("H2", "H2", 0.5, 0.5)]
        exp = CandidateExperiment(
            "E1", "T", "p",
            {"OUTCOME_1": {"H1": 1.0, "H2": 0.0}, "OUTCOME_2": {"H1": 0.0, "H2": 1.0}}
        )
        updated, matched = BayesianBeliefUpdater.update_beliefs(hyps, exp, "unmatched random garbage")
        assert matched is None
        assert updated[0].posterior_probability == 0.5

    # -------------------------------------------------------------------------
    # Scenario 22: Ranking multiple candidate experiments with cost trade-offs
    # -------------------------------------------------------------------------
    def test_22_ranking_multiple_candidates(self):
        hyps = [ScientificHypothesis("H1", "H1", 0.5, 0.5), ScientificHypothesis("H2", "H2", 0.5, 0.5)]
        c1 = CandidateExperiment("C1", "C1", "p", {"A": {"H1": 1.0, "H2": 0.0}}, cost=0.1, risk=0.0)
        c2 = CandidateExperiment("C2", "C2", "p", {"A": {"H1": 0.6, "H2": 0.4}}, cost=0.1, risk=0.0)
        ranked = self.bridge.rank_experiments(
            session_id=self.bridge.create_investigation("Q", hyps, [c1, c2]).session_id
        )
        assert ranked[0].experiment_id == "C1"

    # -------------------------------------------------------------------------
    # Scenario 23: Empty hypothesis space raises error
    # -------------------------------------------------------------------------
    def test_23_empty_hypothesis_space_raises_error(self):
        with pytest.raises(AdaptiveExperimentationError):
            self.bridge.create_investigation("Q", [], [])

    # -------------------------------------------------------------------------
    # Scenario 24: Single hypothesis has 0 prior entropy
    # -------------------------------------------------------------------------
    def test_24_single_hypothesis_zero_entropy(self):
        ent = InformationTheoreticEngine.calculate_entropy([1.0])
        assert ent == 0.0

    # -------------------------------------------------------------------------
    # Scenario 25: Multi-hypothesis 3-way distribution
    # -------------------------------------------------------------------------
    def test_25_three_way_hypothesis_space(self):
        hyps = [
            ScientificHypothesis("H1", "H1", 0.333, 0.333),
            ScientificHypothesis("H2", "H2", 0.333, 0.333),
            ScientificHypothesis("H3", "H3", 0.334, 0.334),
        ]
        ent = InformationTheoreticEngine.calculate_entropy([h.posterior_probability for h in hyps])
        assert round(ent, 1) == 1.6  # log2(3) = 1.585

    # -------------------------------------------------------------------------
    # Scenario 26: Tie-breaking on equal utility favors lower cost
    # -------------------------------------------------------------------------
    def test_26_tie_breaking_favors_lower_cost(self):
        hyps = [ScientificHypothesis("H1", "H1", 0.5, 0.5), ScientificHypothesis("H2", "H2", 0.5, 0.5)]
        e1 = CandidateExperiment("E1", "E1", "p", {"A": {"H1": 1.0, "H2": 0.0}}, cost=0.2, risk=0.1)
        e2 = CandidateExperiment("E2", "E2", "p", {"A": {"H1": 1.0, "H2": 0.0}}, cost=0.1, risk=0.1)
        ranked = AdaptiveExperimentSelector.rank_candidate_experiments(hyps, [e1, e2])
        assert ranked[0].experiment_id == "E2"

    # -------------------------------------------------------------------------
    # Scenario 27: Investigation accumulates cost accurately
    # -------------------------------------------------------------------------
    def test_27_investigation_accumulates_cost(self):
        hyps = [ScientificHypothesis("H1", "H1", 0.5, 0.5), ScientificHypothesis("H2", "H2", 0.5, 0.5)]
        exp = CandidateExperiment("E1", "E1", "p", {"A": {"H1": 0.7, "H2": 0.3}}, cost=0.25)
        sess = self.bridge.create_investigation("Q", hyps, [exp], cost_budget=1.0)
        sess, _ = self.bridge.step_investigation(sess.session_id, "A")
        assert sess.accumulated_cost == 0.25

    # -------------------------------------------------------------------------
    # Scenario 28: Recovering non-existent session raises KeyError
    # -------------------------------------------------------------------------
    def test_28_non_existent_session_raises_keyerror(self):
        with pytest.raises(KeyError):
            self.bridge._get_session_or_recover("ghost_session_id")

    # -------------------------------------------------------------------------
    # Scenario 29: Audit entry recording in persistence store
    # -------------------------------------------------------------------------
    def test_29_audit_ledger_recording(self):
        store = AdaptiveExperimentStore(base_dir=self.temp_dir)
        store.record_audit_entry({"event": "TEST_AUDIT", "ts": time.time()})
        assert store.audit_ledger_file.exists()

    # -------------------------------------------------------------------------
    # Scenario 30: Belief history tracks trajectory over steps
    # -------------------------------------------------------------------------
    def test_30_belief_history_tracking(self):
        hyps = [ScientificHypothesis("H1", "H1", 0.5, 0.5), ScientificHypothesis("H2", "H2", 0.5, 0.5)]
        exp = CandidateExperiment("E1", "E1", "p", {"A": {"H1": 0.9, "H2": 0.1}}, cost=0.1)
        sess = self.bridge.create_investigation("Q", hyps, [exp], cost_budget=1.0)
        assert len(sess.belief_history) == 1
        sess, _ = self.bridge.step_investigation(sess.session_id, "A")
        assert len(sess.belief_history) == 2

    # -------------------------------------------------------------------------
    # Scenario 31: Unexecuted candidates filter out executed records
    # -------------------------------------------------------------------------
    def test_31_executed_candidates_filtered_out(self):
        hyps = [ScientificHypothesis("H1", "H1", 0.5, 0.5), ScientificHypothesis("H2", "H2", 0.5, 0.5)]
        exp = CandidateExperiment("E1", "E1", "p", {"A": {"H1": 0.7, "H2": 0.3}}, cost=0.1)
        sess = self.bridge.create_investigation("Q", hyps, [exp], cost_budget=1.0)
        sess, _ = self.bridge.step_investigation(sess.session_id, "A")
        remaining = self.bridge.rank_experiments(sess.session_id)
        assert len(remaining) == 0

    # -------------------------------------------------------------------------
    # Scenario 32: Normalizing unnormalized priors on creation
    # -------------------------------------------------------------------------
    def test_32_normalizing_unnormalized_priors(self):
        hyps = [ScientificHypothesis("H1", "H1", 20.0, 20.0), ScientificHypothesis("H2", "H2", 80.0, 80.0)]
        sess = self.bridge.create_investigation("Q", hyps, [])
        assert sess.hypotheses[0].prior_probability == 0.2
        assert sess.hypotheses[1].prior_probability == 0.8

    # -------------------------------------------------------------------------
    # Scenario 33: Two-step sequential investigation stops on second step
    # -------------------------------------------------------------------------
    def test_33_two_step_investigation(self):
        hyps = [
            ScientificHypothesis("H1", "H1", 0.33, 0.33),
            ScientificHypothesis("H2", "H2", 0.33, 0.33),
            ScientificHypothesis("H3", "H3", 0.34, 0.34),
        ]
        # E1 eliminates H3 with high utility
        e1 = CandidateExperiment("E1", "E1", "p", {"NOT_H3": {"H1": 1.0, "H2": 1.0, "H3": 0.0}}, cost=0.01)
        # E2 discriminates H1 from H2
        e2 = CandidateExperiment("E2", "E2", "p", {"CONFIRM_1": {"H1": 0.95, "H2": 0.05, "H3": 0.5}}, cost=0.5)

        sess = self.bridge.create_investigation("Q", hyps, [e1, e2], cost_budget=1.0)

        # Step 1: Execute E1
        sess, executed1 = self.bridge.step_investigation(sess.session_id, "NOT_H3")
        assert executed1 is not None
        assert executed1.experiment_id == "E1"
        assert sess.state == InvestigationState.SELECTING_EXPERIMENT

        # Step 2: Execute E2
        sess, executed2 = self.bridge.step_investigation(sess.session_id, "CONFIRM_1")
        assert executed2 is not None
        assert executed2.experiment_id == "E2"
        assert sess.state == InvestigationState.STOPPED
        assert sess.stopping_reason == StoppingReason.HYPOTHESIS_CONFIRMED

    # -------------------------------------------------------------------------
    # Scenario 34: Zero entropy yields 0 utility
    # -------------------------------------------------------------------------
    def test_34_zero_eig_yields_zero_utility(self):
        u = InformationTheoreticEngine.calculate_utility(eig=0.0, cost=0.1, risk=0.1)
        assert u == 0.0

    # -------------------------------------------------------------------------
    # Scenario 35: Negative cost or risk normalized to zero in utility
    # -------------------------------------------------------------------------
    def test_35_negative_cost_normalized(self):
        u = InformationTheoreticEngine.calculate_utility(eig=1.0, cost=-0.5, risk=-0.2)
        assert u == 1.0
