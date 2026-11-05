"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: bridge.py
Master orchestrator executing the 11-stage closed-loop adaptive experimentation lifecycle.
"""

from __future__ import annotations

import time
import uuid
from typing import Callable, Dict, List, Optional, Tuple

from .adapters import Phase75BudgetAdapter, Phase78CausalHypothesisAdapter
from .belief_updater import BayesianBeliefUpdater
from .executor import ExperimentExecutor
from .information_theory import InformationTheoreticEngine
from .models import (
    AdaptiveExperimentationError,
    CandidateExperiment,
    ExperimentExecutionRecord,
    InvestigationSession,
    InvestigationState,
    OutcomeFidelity,
    ScientificHypothesis,
    StoppingReason,
)
from .persistence import AdaptiveExperimentStore
from .selector import AdaptiveExperimentSelector
from .stopping_engine import AdaptiveStoppingEvaluator


class AdaptiveExperimentationBridge:
    """
    Master bridge coordinating the 11-stage adaptive experimentation lifecycle:
    INTAKE -> PRIORS -> CANDIDATES -> INFORMATION VALUE -> UTILITY SCORING ->
    OPTIMAL SELECTION -> PREFLIGHT & AUTH -> EXECUTE & RECORD -> BAYESIAN UPDATE ->
    STOPPING EVALUATION -> AUDITABLE REPORT.
    """

    def __init__(self, store_dir: str = ".jarvis/adaptive_experimentation"):
        self.store = AdaptiveExperimentStore(base_dir=store_dir)
        self.sessions: Dict[str, InvestigationSession] = {}

    def create_investigation(
        self,
        question: str,
        hypotheses: List[ScientificHypothesis],
        candidate_experiments: List[CandidateExperiment],
        cost_budget: float = 1.0,
    ) -> InvestigationSession:
        """
        Stage 1 & 2: Initializes an adaptive investigation session and normalizes hypothesis priors.
        """
        if not hypotheses:
            raise AdaptiveExperimentationError("Cannot create investigation with empty hypothesis space.")

        # Normalize prior probabilities
        total_p = sum(max(0.0, h.prior_probability) for h in hypotheses)
        if total_p <= 0.0:
            total_p = float(len(hypotheses))
            for h in hypotheses:
                h.prior_probability = 1.0 / total_p
        else:
            for h in hypotheses:
                h.prior_probability = round(h.prior_probability / total_p, 4)

        for h in hypotheses:
            h.posterior_probability = h.prior_probability

        session_id = f"inv_{uuid.uuid4().hex[:8]}"
        session = InvestigationSession(
            session_id=session_id,
            question=question,
            hypotheses=hypotheses,
            candidate_experiments=candidate_experiments,
            cost_budget=cost_budget,
            belief_history=[{h.hypothesis_id: h.posterior_probability for h in hypotheses}],
            audit_trail=[f"INVESTIGATION_CREATED: question='{question}', hypotheses={len(hypotheses)}, budget={cost_budget}"],
        )

        self.sessions[session_id] = session
        self.store.save_session(session)
        return session

    def rank_experiments(
        self,
        session_id: str,
        lambda_cost: float = 1.0,
        lambda_risk: float = 1.0,
    ) -> List[CandidateExperiment]:
        """
        Stage 4 & 5: Evaluates Shannon EIG and cost/risk penalized utility for all remaining candidates.
        """
        session = self._get_session_or_recover(session_id)
        executed_ids = {r.experiment_id for r in session.executed_records}
        unexecuted = [e for e in session.candidate_experiments if e.experiment_id not in executed_ids]

        return AdaptiveExperimentSelector.rank_candidate_experiments(
            hypotheses=session.hypotheses,
            candidates=unexecuted,
            lambda_cost=lambda_cost,
            lambda_risk=lambda_risk,
        )

    def step_investigation(
        self,
        session_id: str,
        observation: str,
        auth_token: Optional[str] = None,
        is_synthetic: bool = False,
        lambda_cost: float = 1.0,
        lambda_risk: float = 1.0,
    ) -> Tuple[InvestigationSession, Optional[CandidateExperiment]]:
        """
        Stages 6 to 10: Selects the optimal experiment, executes it safely,
        updates posterior beliefs, and evaluates stopping rules.
        """
        session = self._get_session_or_recover(session_id)

        if session.state == InvestigationState.STOPPED:
            return session, None

        executed_ids = {r.experiment_id for r in session.executed_records}
        unexecuted = [e for e in session.candidate_experiments if e.experiment_id not in executed_ids]

        # Stage 4 & 5: Rank and score all remaining candidate experiments
        ranked_candidates = AdaptiveExperimentSelector.rank_candidate_experiments(
            hypotheses=session.hypotheses,
            candidates=unexecuted,
            lambda_cost=lambda_cost,
            lambda_risk=lambda_risk,
        )

        # Stage 10 Check: Pre-evaluation of stopping criteria
        should_stop, stop_reason, rationale = AdaptiveStoppingEvaluator.evaluate_stopping_criteria(
            hypotheses=session.hypotheses,
            remaining_candidates=ranked_candidates,
            accumulated_cost=session.accumulated_cost,
            cost_budget=session.cost_budget,
        )
        if should_stop:
            session.state = InvestigationState.STOPPED
            session.stopping_reason = stop_reason
            session.conclusion = rationale
            session.audit_trail.append(f"INVESTIGATION_STOPPED: reason={stop_reason.value}, rationale={rationale}")
            self.store.save_session(session)
            return session, None

        if not ranked_candidates:
            session.state = InvestigationState.STOPPED
            session.stopping_reason = StoppingReason.NO_SAFE_EXPERIMENTS_REMAIN
            session.conclusion = "No remaining candidate experiments."
            session.audit_trail.append("INVESTIGATION_STOPPED: NO_SAFE_EXPERIMENTS_REMAIN")
            self.store.save_session(session)
            return session, None

        best_exp = ranked_candidates[0]
        if best_exp.expected_info_gain < 0.05 or best_exp.utility_score <= 0.0:
            session.state = InvestigationState.STOPPED
            session.stopping_reason = StoppingReason.DIMINISHING_INFORMATION_GAIN
            session.conclusion = "No remaining experiment offers sufficient information gain."
            session.audit_trail.append("INVESTIGATION_STOPPED: DIMINISHING_INFORMATION_GAIN")
            self.store.save_session(session)
            return session, None

        # Stage 7 & 8: Preflight safety and execute
        session.state = InvestigationState.EXECUTING
        matched_outcome = BayesianBeliefUpdater.match_observation_to_outcome(best_exp, observation) or "unknown"
        record = ExperimentExecutor.execute_experiment(
            experiment=best_exp,
            simulated_or_real_observation=observation,
            matched_outcome=matched_outcome,
            auth_token=auth_token,
            is_synthetic=is_synthetic,
        )

        session.executed_records.append(record)
        session.accumulated_cost += record.cost_incurred

        # Stage 9: Bayesian belief update
        session.state = InvestigationState.UPDATING_BELIEFS
        updated_hyps, _ = BayesianBeliefUpdater.update_beliefs(
            hypotheses=session.hypotheses,
            experiment=best_exp,
            actual_observation=observation,
            is_synthetic=is_synthetic,
        )
        session.hypotheses = updated_hyps
        session.belief_history.append({h.hypothesis_id: h.posterior_probability for h in updated_hyps})

        session.audit_trail.append(
            f"EXPERIMENT_EXECUTED: id={best_exp.experiment_id}, observation='{observation}', "
            f"cost_incurred={record.cost_incurred}, new_top={max(session.hypotheses, key=lambda h: h.posterior_probability).hypothesis_id}"
        )

        # Stage 10: Post-experiment stopping evaluation
        remaining = [e for e in unexecuted if e.experiment_id != best_exp.experiment_id]
        ranked_remaining = AdaptiveExperimentSelector.rank_candidate_experiments(
            hypotheses=session.hypotheses,
            candidates=remaining,
            lambda_cost=lambda_cost,
            lambda_risk=lambda_risk,
        )
        should_stop, stop_reason, rationale = AdaptiveStoppingEvaluator.evaluate_stopping_criteria(
            hypotheses=session.hypotheses,
            remaining_candidates=ranked_remaining,
            accumulated_cost=session.accumulated_cost,
            cost_budget=session.cost_budget,
        )

        if should_stop:
            session.state = InvestigationState.STOPPED
            session.stopping_reason = stop_reason
            session.conclusion = rationale
            session.audit_trail.append(f"INVESTIGATION_STOPPED: reason={stop_reason.value}, rationale={rationale}")
        else:
            session.state = InvestigationState.SELECTING_EXPERIMENT

        # Update confidence interval
        top_h = max(session.hypotheses, key=lambda h: h.posterior_probability)
        margin = max(0.05, 0.3 * (1.0 - top_h.posterior_probability))
        session.confidence_interval = (
            max(0.0, round(top_h.posterior_probability - margin, 3)),
            min(1.0, round(top_h.posterior_probability + margin, 3)),
        )

        self.store.save_session(session)
        return session, best_exp

    def _get_session_or_recover(self, session_id: str) -> InvestigationSession:
        """Retrieves session from memory or reconstructs it from disk store."""
        if session_id in self.sessions:
            return self.sessions[session_id]

        raw = self.store.get_session(session_id)
        if not raw:
            raise KeyError(f"Investigation session '{session_id}' not found.")

        session = InvestigationSession(
            session_id=raw["session_id"],
            question=raw["question"],
            hypotheses=[ScientificHypothesis.from_dict(h) for h in raw.get("hypotheses", [])],
            candidate_experiments=[CandidateExperiment.from_dict(e) for e in raw.get("candidate_experiments", [])],
            executed_records=[ExperimentExecutionRecord.from_dict(r) for r in raw.get("executed_records", [])],
            belief_history=raw.get("belief_history", []),
            state=InvestigationState(raw.get("state", "INITIALIZED")),
            stopping_reason=StoppingReason(raw["stopping_reason"]) if raw.get("stopping_reason") else None,
            conclusion=raw.get("conclusion", ""),
            confidence_interval=tuple(raw.get("confidence_interval", (0.0, 1.0))),
            audit_trail=raw.get("audit_trail", []),
            accumulated_cost=raw.get("accumulated_cost", 0.0),
            cost_budget=raw.get("cost_budget", 1.0),
            timestamp=raw.get("timestamp", time.time()),
        )
        self.sessions[session_id] = session
        return session
