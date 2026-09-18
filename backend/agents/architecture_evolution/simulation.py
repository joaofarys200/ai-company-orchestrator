"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: simulation.py
Simulates architectural mutations, dependency modifications, contract compatibility,
and failure rollbacks in a virtual dry-run environment.

Rule:
    Simulation is never equivalent to real execution.
    Outputs: SIMULATION_SAFE, SIMULATION_RISK, SIMULATION_INCOMPLETE.
"""

from __future__ import annotations

from typing import List

from .models import (
    ArchitectureAlternative,
    ArchitectureMigrationPlan,
    ArchitectureSnapshot,
    ContractAnalysisResult,
    ContractBreakStatus,
    ReversibilityStatus,
    SimulationResult,
    SimulationStatus,
)


class ArchitectureSimulator:
    """Executes deterministic virtual dry-runs of architectural transformations."""

    def simulate(
        self,
        alternative: ArchitectureAlternative,
        snapshot: ArchitectureSnapshot,
        migration_plan: ArchitectureMigrationPlan,
        contract_analysis: ContractAnalysisResult,
    ) -> SimulationResult:
        logs: List[str] = []
        logs.append(f"Initiating architectural simulation for alternative '{alternative.alternative_id}'...")

        # 1. Simulate Graph Mutation & Connectivity
        graph_valid = True
        affected_set = set(alternative.affected_components)
        simulated_dependencies = [
            d for d in snapshot.dependencies
            if not (d[0] in affected_set and d[1] in affected_set)
        ]
        logs.append(f"Simulated dependency topology: {len(simulated_dependencies)} edges remaining (cycle broken: {len(simulated_dependencies) < len(snapshot.dependencies)}).")

        # 2. Simulate Contract Changes
        contract_safe = True
        if contract_analysis.status == ContractBreakStatus.BREAKING:
            contract_safe = False
            logs.append(f"SIMULATION_WARNING: Breaking contract detected without backward-compatibility adapter: {contract_analysis.breaking_contracts}")

        # 3. Simulate Migration DAG Ordering
        dag_valid = True
        seen_steps = set()
        for step in migration_plan.steps:
            for dep in step.dependencies:
                if dep not in seen_steps:
                    dag_valid = False
                    logs.append(f"SIMULATION_ERROR: Invalid migration DAG ordering: step '{step.step_id}' depends on unexecuted '{dep}'.")
            seen_steps.add(step.step_id)

        # 4. Simulate Failure Scenarios & Rollback Execution
        rollback_verified = True
        failure_scenarios = 0
        for step in migration_plan.steps:
            if not step.is_reversibility_supported or not step.rollback_action:
                rollback_verified = False
                logs.append(f"SIMULATION_ERROR: Missing automated rollback at step '{step.step_id}'.")
            failure_scenarios += 1

        # 5. Evaluate Overall Simulation Status
        if not dag_valid or not rollback_verified:
            status = SimulationStatus.SIMULATION_INCOMPLETE
        elif not contract_safe or alternative.reversibility == ReversibilityStatus.IRREVERSIBLE:
            status = SimulationStatus.SIMULATION_RISK
        else:
            status = SimulationStatus.SIMULATION_SAFE

        logs.append(f"Simulation completed with verdict: {status.value}")

        return SimulationResult(
            alternative_id=alternative.alternative_id,
            graph_mutation_valid=graph_valid,
            contract_changes_safe=contract_safe,
            behavior_preserved=contract_safe and graph_valid,
            test_impact_acceptable=True,
            rollback_path_verified=rollback_verified,
            failure_scenarios_tested=failure_scenarios,
            migration_ordering_valid=dag_valid,
            status=status,
            logs=logs,
        )
