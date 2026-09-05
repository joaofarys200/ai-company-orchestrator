from __future__ import annotations

import asyncio
import pytest

from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_planner import (
    MissionPlanDecomposer,
    PlannedMissionSpec,
    PlannedTaskSpec,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import (
    FailureCategory,
    FailureInfo,
    RetryConfig,
    TaskGraph,
    TaskNode,
    TaskStatus,
)


def test_long_horizon_multi_step_mission_with_crash_and_recovery(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        decomposer = MissionPlanDecomposer(store)

        # 1. Define complex 10-task mission DAG:
        # T01: Architecture & Requirements
        # T02: Database Schema (depends on T01)
        # T03: Auth Backend (depends on T01)
        # T04: REST API Endpoints (depends on T02, T03) [has transient failure on first attempt]
        # T05: Frontend Core (depends on T01)
        # T06: Frontend Auth UI (depends on T05, T03)
        # T07: Frontend Dashboard (depends on T05, T04) [has validation error that gets repaired]
        # T08: Integration Testing (depends on T06, T07)
        # T09: Performance Benchmark (depends on T08)
        # T10: Deployment & Verification (depends on T09)

        spec = PlannedMissionSpec(
            title="Desenvolvimento de Plataforma E-Commerce",
            objective="Construir plataforma completa multi-camada",
            project_id="ecommerce-platform",
            mission_id="m_long_horizon_01",
            tasks=[
                PlannedTaskSpec(title="Architecture & Requirements", task_id="T01", category="RESEARCH"),
                PlannedTaskSpec(title="Database Schema", task_id="T02", dependencies=["T01"], category="CODING"),
                PlannedTaskSpec(title="Auth Backend", task_id="T03", dependencies=["T01"], category="CODING"),
                PlannedTaskSpec(title="REST API Endpoints", task_id="T04", dependencies=["T02", "T03"], category="CODING"),
                PlannedTaskSpec(title="Frontend Core", task_id="T05", dependencies=["T01"], category="CODING"),
                PlannedTaskSpec(title="Frontend Auth UI", task_id="T06", dependencies=["T05", "T03"], category="CODING"),
                PlannedTaskSpec(title="Frontend Dashboard", task_id="T07", dependencies=["T05", "T04"], category="CODING"),
                PlannedTaskSpec(title="Integration Testing", task_id="T08", dependencies=["T06", "T07"], category="REVIEW"),
                PlannedTaskSpec(title="Performance Benchmark", task_id="T09", dependencies=["T08"], category="EXPERIMENT"),
                PlannedTaskSpec(title="Deployment & Verification", task_id="T10", dependencies=["T09"], category="BUILD"),
            ],
        )

        mission_data, task_graph = decomposer.decompose_and_persist(spec)
        assert len(task_graph.nodes) == 10

        # Execution tracking
        attempt_map: dict[str, int] = {f"T{i:02d}": 0 for i in range(1, 11)}
        repaired_t07 = False

        async def realistic_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            nonlocal repaired_t07
            t_id = node.task_id
            attempt_map[t_id] += 1
            att = attempt_map[t_id]

            # Simulate transient network glitch on T04 attempt 1
            if t_id == "T04" and att == 1:
                return TaskExecutionResult(
                    success=False,
                    task_id=t_id,
                    failure_category=FailureCategory.TRANSIENT_FAILURE,
                    error_message="Transient DB connection timeout",
                )

            # Simulate validation syntax issue on T07 before repair
            if t_id == "T07" and not repaired_t07:
                return TaskExecutionResult(
                    success=False,
                    task_id=t_id,
                    failure_category=FailureCategory.VALIDATION_FAILURE,
                    error_message="JSX component syntax error: missing closing tag",
                )

            # Standard successful execution with real evidence
            return TaskExecutionResult(
                success=True,
                task_id=t_id,
                summary=f"{node.title} concluído com sucesso (Tentativa {att}).",
                evidence=[{
                    "kind": "EXECUTION_LOG",
                    "source_ref": f"validation:{t_id.lower()}_run",
                    "description": f"Output gerado para {node.title}",
                }],
            )

        async def minimal_repair_hook(project_id: str, node: TaskNode, fail_info: FailureInfo, context: dict) -> bool:
            nonlocal repaired_t07
            if node.task_id == "T07":
                repaired_t07 = True
                return True
            return False

        orchestrator = MissionLifecycleOrchestrator(
            project_id="ecommerce-platform",
            mission_id="m_long_horizon_01",
            mission_state=store,
            task_graph=task_graph,
            concurrency_limit=3,
            executor_fn=realistic_executor,
            repair_fn=minimal_repair_hook,
        )

        # 2. Run phase 1: Execute until T06 finishes, then simulate crash
        run_task = asyncio.create_task(orchestrator.run())
        
        # Let tasks progress through initial parallel wave (T01 -> T02, T03, T05...)
        await asyncio.sleep(0.15)
        orchestrator.save_checkpoint("Mid-execution checkpoint before simulated crash")

        # 3. Simulate Crash Recovery / Restart:
        # Create a fresh orchestrator instance from saved state
        recovered_orch = MissionLifecycleOrchestrator(
            project_id="ecommerce-platform",
            mission_id="m_long_horizon_01",
            mission_state=store,
            concurrency_limit=3,
            executor_fn=realistic_executor,
            repair_fn=minimal_repair_hook,
        )
        latest_cp = recovered_orch.load_latest_checkpoint()
        assert latest_cp is not None
        recovered_orch.recover_from_checkpoint(latest_cp)

        # Cancel old run task to finalize simulated crash
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            pass

        # 4. Resume recovered orchestrator to completion
        final_status = await recovered_orch.run()

        # 5. Satisfy all criteria with collected evidence
        loaded = store.load_mission("ecommerce-platform", "m_long_horizon_01")
        for crit in loaded["acceptance_criteria"]:
            wp_id = crit["owner_id"]
            node = recovered_orch.task_graph.get_node(wp_id)
            if node.evidence_refs:
                store.set_criterion_status(
                    "ecommerce-platform",
                    "m_long_horizon_01",
                    crit["criterion_id"],
                    "SATISFIED",
                    expected_version=crit["version"],
                    evidence_refs=node.evidence_refs,
                )

        # Final verification
        satisfied, reason = await recovered_orch.verify_satisfaction()
        assert satisfied is True

        # Assertions
        assert recovered_orch.task_graph.is_all_completed()
        assert attempt_map["T04"] == 2  # Retried after transient failure
        assert repaired_t07 is True  # Repaired after validation error
        assert recovered_orch.checkpoint_seq >= 3

    asyncio.run(_run())
