"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: evaluator.py
Combinatorial portfolio evaluator: multi-initiative synergies, redundancies,
hard-constraint enforcement, risk adjustment, and deterministic selection.
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Optional, Set, Tuple

from .dependency_graph import DependencyGraphEngine
from .models import (
    EngineeringInitiative,
    InfeasiblePortfolioError,
    PortfolioEvaluationResult,
    RedundancyDefinition,
    SynergyDefinition,
)


class PortfolioEvaluator:
    """
    Evaluates candidate sets as combinatorial portfolios rather than ranking candidates independently.
    Accounts for synergies, redundancies, cannibalization, risk penalties, and strict hard constraints.
    """

    def __init__(
        self,
        graph_engine: Optional[DependencyGraphEngine] = None,
        synergies: Optional[List[SynergyDefinition]] = None,
        redundancies: Optional[List[RedundancyDefinition]] = None,
        risk_weight: float = 15.0,
    ):
        self.graph_engine = graph_engine or DependencyGraphEngine()
        self.synergies = synergies or []
        self.redundancies = redundancies or []
        self.risk_weight = risk_weight

    def evaluate_candidate_set(
        self,
        candidate_ids: Set[str],
        initiatives: Dict[str, EngineeringInitiative],
        max_cost: float,
        max_effort: float,
    ) -> Tuple[bool, float, float, float, float, List[str]]:
        """
        Evaluate a single candidate set for feasibility and compute:
        (is_feasible, net_utility, total_cost, total_effort, total_benefit, infeasibility_reasons)
        """
        reasons: List[str] = []
        if not candidate_ids:
            return True, 0.0, 0.0, 0.0, 0.0, []

        # 1. Check Hard Prerequisite Closure: Every selected initiative's prerequisites must be in candidate_ids
        for c_id in candidate_ids:
            init = initiatives.get(c_id)
            if not init:
                reasons.append(f"MISSING_INITIATIVE: '{c_id}' not found in registry")
                continue
            for prereq in init.prerequisites:
                if prereq in initiatives and prereq not in candidate_ids:
                    # Check if prerequisite is already COMPLETED
                    if initiatives[prereq].state != "COMPLETED":
                        reasons.append(f"UNFULFILLED_PREREQUISITE: '{c_id}' requires '{prereq}' which is not selected")

        # 2. Check Mutual Exclusions
        for c_id in candidate_ids:
            init = initiatives.get(c_id)
            if not init:
                continue
            for excl in init.mutual_exclusions:
                if excl in candidate_ids:
                    reasons.append(f"MUTUAL_EXCLUSION: Both '{c_id}' and '{excl}' cannot be in the same portfolio")

        # 3. Check Approval Requirements
        for c_id in candidate_ids:
            init = initiatives.get(c_id)
            if init and init.requires_approval and not init.approval_token:
                reasons.append(f"UNAUTHORIZED_INITIATIVE: '{c_id}' requires human approval token")

        # 4. Check Budget and Effort
        total_cost = sum(initiatives[c].budget_cost for c in candidate_ids if c in initiatives)
        total_effort = sum(initiatives[c].effort_units for c in candidate_ids if c in initiatives)

        if total_cost > max_cost:
            reasons.append(f"BUDGET_EXCEEDED: Total cost {total_cost:.1f} exceeds budget {max_cost:.1f}")
        if total_effort > max_effort:
            reasons.append(f"EFFORT_EXCEEDED: Total effort {total_effort:.1f} exceeds capacity {max_effort:.1f}")

        if reasons:
            return False, 0.0, total_cost, total_effort, 0.0, reasons

        # 5. Compute Expected Benefit with Explicit Uncertainty
        # benefit_i = expected_benefit * confidence
        base_benefit = sum(
            initiatives[c].expected_benefit * initiatives[c].confidence
            for c in candidate_ids
            if c in initiatives
        )

        # 6. Synergies: Bonus when specific co-selected sets are present
        synergy_bonus = 0.0
        for syn in self.synergies:
            if syn.initiative_ids.issubset(candidate_ids):
                synergy_bonus += syn.bonus_benefit

        # 7. Redundancies: Penalty / double-counting deduction
        redundancy_penalty = 0.0
        for red in self.redundancies:
            if red.initiative_ids.issubset(candidate_ids):
                redundancy_penalty += red.penalty_benefit

        # Also detect automatic redundancy if two initiatives touch overlapping components with same goal
        selected_nodes = [initiatives[c] for c in candidate_ids if c in initiatives]
        for i in range(len(selected_nodes)):
            for j in range(i + 1, len(selected_nodes)):
                n_a, n_b = selected_nodes[i], selected_nodes[j]
                if n_a.initiative_type == n_b.initiative_type:
                    overlap = set(n_a.affected_components).intersection(set(n_b.affected_components))
                    if overlap and len(n_a.affected_components) > 0:
                        ratio = len(overlap) / max(len(n_a.affected_components), len(n_b.affected_components))
                        # Deduct fraction to avoid double-counting overlapping benefits
                        overlap_deduction = min(n_a.expected_benefit, n_b.expected_benefit) * ratio * 0.4
                        redundancy_penalty += overlap_deduction

        # 8. Prerequisite Value: Bonus for unlocking downstream opportunities
        prereq_bonus = 0.0
        for c_id in candidate_ids:
            dependents = self.graph_engine._dependents.get(c_id, set())
            for dep in dependents:
                if dep in candidate_ids and dep in initiatives:
                    prereq_bonus += initiatives[dep].expected_benefit * 0.15

        # 9. Risk Penalty
        risk_penalty = sum(
            initiatives[c].risk_score * self.risk_weight
            for c in candidate_ids
            if c in initiatives
        )

        total_benefit = base_benefit + synergy_bonus + prereq_bonus - redundancy_penalty
        net_utility = total_benefit - (total_cost * 0.5) - risk_penalty

        return True, net_utility, total_cost, total_effort, total_benefit, []

    def select_optimal_portfolio(
        self,
        candidates: List[EngineeringInitiative],
        max_cost: float,
        max_effort: float,
    ) -> PortfolioEvaluationResult:
        """
        Find the optimal subset of candidate initiatives maximizing net utility
        subject to hard constraints.
        Deterministic: Identical inputs always yield the exact same selection.
        """
        init_map = {init.id: init for init in candidates}
        for init in candidates:
            self.graph_engine.add_initiative(init)

        # Check for dependency cycles first
        self.graph_engine.detect_cycles(set(init_map.keys()))

        candidate_ids = sorted(list(init_map.keys()))
        n = len(candidate_ids)

        best_utility = -float("inf")
        best_set: Set[str] = set()
        best_stats = (0.0, 0.0, 0.0)  # cost, effort, benefit
        all_reasons: Set[str] = set()

        # Combinatorial search: for reasonable n (<= 15), explore power set or greedy branch-and-bound
        # For n <= 14, 2^14 = 16384 evaluations is virtually instantaneous in memory
        if n <= 14:
            subsets = []
            for r in range(1, n + 1):
                for subset in itertools.combinations(candidate_ids, r):
                    subsets.append(set(subset))
            # Sort subsets deterministically by size, then alphabetically
            subsets.sort(key=lambda s: (len(s), sorted(list(s))))

            for s in subsets:
                feasible, util, cost, effort, benefit, reasons = self.evaluate_candidate_set(
                    s, init_map, max_cost, max_effort
                )
                if feasible:
                    if util > best_utility:
                        best_utility = util
                        best_set = s
                        best_stats = (cost, effort, benefit)
                else:
                    all_reasons.update(reasons)
        else:
            # Deterministic greedy branch-and-bound for large n
            # Start with singletons and greedily add best non-conflicting candidate
            current_set: Set[str] = set()
            remaining = sorted(candidate_ids, key=lambda x: (
                -(init_map[x].expected_benefit * init_map[x].confidence / max(1.0, init_map[x].budget_cost)),
                x
            ))
            for cand in remaining:
                trial = set(current_set).union({cand})
                # Add transitive prerequisites
                trial = trial.union(self.graph_engine.compute_prerequisite_transitive_closure(cand))
                feasible, util, cost, effort, benefit, reasons = self.evaluate_candidate_set(
                    trial, init_map, max_cost, max_effort
                )
                if feasible and util > best_utility:
                    best_utility = util
                    best_set = trial
                    best_stats = (cost, effort, benefit)
                    current_set = trial
                else:
                    all_reasons.update(reasons)

        if not best_set:
            # Check if any single candidate was feasible
            return PortfolioEvaluationResult(
                selected_initiatives=[],
                rejected_initiatives=candidate_ids,
                total_benefit=0.0,
                total_cost=0.0,
                total_effort=0.0,
                net_utility=0.0,
                synergy_bonus=0.0,
                redundancy_penalty=0.0,
                risk_penalty=0.0,
                is_feasible=False,
                infeasibility_reasons=sorted(list(all_reasons)) or ["No candidate combination satisfied the constraints."],
            )

        cost, effort, benefit = best_stats
        selected = sorted(list(best_set))
        rejected = sorted(list(set(candidate_ids) - best_set))

        # Calculate isolated components for metrics
        syn_bonus = sum(
            s.bonus_benefit for s in self.synergies if s.initiative_ids.issubset(best_set)
        )
        red_pen = sum(
            r.penalty_benefit for r in self.redundancies if r.initiative_ids.issubset(best_set)
        )
        risk_pen = sum(init_map[c].risk_score * self.risk_weight for c in best_set)

        return PortfolioEvaluationResult(
            selected_initiatives=selected,
            rejected_initiatives=rejected,
            total_benefit=benefit,
            total_cost=cost,
            total_effort=effort,
            net_utility=best_utility,
            synergy_bonus=syn_bonus,
            redundancy_penalty=red_pen,
            risk_penalty=risk_pen,
            is_feasible=True,
            infeasibility_reasons=[],
        )
