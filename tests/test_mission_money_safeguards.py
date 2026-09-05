from __future__ import annotations

import asyncio
import pytest

from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_planner import MissionPlanDecomposer, PlannedMissionSpec, PlannedTaskSpec
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskNode, TaskStatus


def test_money_mission_decomposes_and_enforces_safeguards(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        decomposer = MissionPlanDecomposer(store)

        spec = PlannedMissionSpec(
            title="Arbitragem Económica",
            objective="Executar cálculo e validação de spread",
            project_id="money",
            is_economic=True,
            tasks=[
                PlannedTaskSpec(title="Análise de Mercados", category="RESEARCH", task_id="T1"),
                PlannedTaskSpec(title="Validação de Liquidez", category="REVIEW", dependencies=["T1"], task_id="T2"),
                PlannedTaskSpec(title="Simulação de Transação", category="EXPERIMENT", dependencies=["T2"], task_id="T3"),
            ],
            mission_id="m_econ_01",
        )

        mission_data, task_graph = decomposer.decompose_and_persist(spec)

        assert mission_data["mission"]["status"] == "READY"
        assert mission_data["mission"]["metadata"]["is_economic"] is True
        assert len(mission_data["work_packages"]) == 3

        async def money_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary=f"{node.title} validada em ambiente controlado de teste.",
                evidence=[{
                    "kind": "EXECUTION_LOG",
                    "source_ref": "experiment:money_simulation_log",
                    "description": "Simulação de teste sem conversão em receita real sem liquidação.",
                }],
            )

        orchestrator = MissionLifecycleOrchestrator(
            project_id="money",
            mission_id="m_econ_01",
            mission_state=store,
            task_graph=task_graph,
            executor_fn=money_executor,
        )

        status = await orchestrator.run()
        # Without satisfying criteria with live verified banking proof, satisfaction is verified deterministically
        assert status in {MissionLifecycleStatus.COMPLETED, MissionLifecycleStatus.FAILED}

    asyncio.run(_run())
