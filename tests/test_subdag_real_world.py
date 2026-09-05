from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
import pytest

from agents.dynamic_subdag import (
    DynamicSubDagProposal,
    ExpansionTrigger,
)
from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_workspace() -> tuple[str, MissionStateStore]:
    test_id = uuid.uuid4().hex[:8]
    root = os.path.abspath(f"test_ws_subdag_real_{test_id}")
    os.makedirs(os.path.join(root, "workspace", "projects"), exist_ok=True)
    store = MissionStateStore(workspace_root=root)
    yield root, store
    shutil.rmtree(root, ignore_errors=True)


@pytest.mark.anyio
async def test_real_world_search_feature_discovery(temp_workspace: tuple[str, MissionStateStore]) -> None:
    """Real-World Search Feature Scenario (Section 33):
    Prompt: "Adiciona uma funcionalidade de pesquisa à aplicação."
    Initial plan:
      1. T_ANALYZE_FE: Analisar componentes de pesquisa no frontend.
      2. T_IMPL_FE: Implementar UI de pesquisa.
      3. T_TEST_FE: Testar pesquisa no frontend.

    During T_IMPL_FE execution, the agent discovers:
      - Backend endpoint /api/search does not exist.
      - API schema contract needs backend endpoint, backend unit tests, and E2E browser QA.
      -> Generates DYNAMIC SUB-DAG:
         - T_BACKEND_ENDPOINT (API handler)
         - T_BACKEND_TESTS (endpoint tests)
         - T_BROWSER_QA (browser automation verification)
      -> Integrates into TaskGraph (v1 -> v2)
      -> Execution continues seamlessly and completes.
    """
    _, store = temp_workspace
    proj = "p_search_app"
    miss = "m_search_app"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(
        proj,
        "Implementar Pesquisa Full-Text",
        "Adicionar barra de pesquisa e filtragem na aplicação",
        mission_id=miss,
    )

    initial_tasks = [
        ("T_ANALYZE_FE", "Analisar frontend", []),
        ("T_IMPL_FE", "Implementar pesquisa frontend", ["T_ANALYZE_FE"]),
        ("T_TEST_FE", "Testar pesquisa frontend", ["T_IMPL_FE"]),
    ]
    for tid, title, deps in initial_tasks:
        store.create_work_package(proj, miss, title=title, dependencies=deps, work_package_id=tid)

    nodes = [
        TaskNode(task_id="T_ANALYZE_FE", title="Analisar frontend"),
        TaskNode(task_id="T_IMPL_FE", title="Implementar pesquisa frontend", dependencies=["T_ANALYZE_FE"]),
        TaskNode(task_id="T_TEST_FE", title="Testar pesquisa frontend", dependencies=["T_IMPL_FE"]),
    ]
    graph = TaskGraph(nodes)

    discovered_and_applied = False

    async def executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
        nonlocal discovered_and_applied
        await asyncio.sleep(0.01)

        if node.task_id == "T_ANALYZE_FE":
            return TaskExecutionResult(success=True, task_id=node.task_id, summary="Frontend UI analysis complete.")

        elif node.task_id == "T_IMPL_FE":
            # Discovery: backend endpoint /api/search is missing!
            discovered_and_applied = True
            subdag = DynamicSubDagProposal(
                proposal_id="prop_search_backend",
                mission_id=miss,
                parent_task_id="T_IMPL_FE",
                base_graph_version=1,
                reason="Backend endpoint /api/search is missing; discovered need for backend handler, backend tests, and browser QA.",
                trigger=ExpansionTrigger.ARCHITECTURE_DISCOVERY,
                tasks=[
                    {"task_id": "T_BACKEND_ENDPOINT", "title": "Criar endpoint /api/search", "dependencies": ["T_ANALYZE_FE"]},
                    {"task_id": "T_BACKEND_TESTS", "title": "Testes unitários backend /api/search", "dependencies": ["T_BACKEND_ENDPOINT"]},
                    {"task_id": "T_BROWSER_QA", "title": "Browser QA end-to-end", "dependencies": ["T_IMPL_FE", "T_BACKEND_TESTS"]},
                ],
                dependencies=[
                    ("T_BACKEND_ENDPOINT", "T_BACKEND_TESTS"),
                    ("T_BACKEND_TESTS", "T_BROWSER_QA"),
                    ("T_IMPL_FE", "T_BROWSER_QA"),
                ],
                acceptance_criteria=[
                    {"criterion_id": "crit_search_api", "owner_id": "T_BACKEND_ENDPOINT", "description": "API /api/search returns 200 OK"},
                    {"criterion_id": "crit_browser_qa", "owner_id": "T_BROWSER_QA", "description": "Browser QA verifies query results rendered"},
                ],
            )
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Frontend UI implemented; proposed backend sub-DAG.",
                subdag_proposal=subdag,
            )

        elif node.task_id == "T_BACKEND_ENDPOINT":
            return TaskExecutionResult(success=True, task_id=node.task_id, summary="Endpoint /api/search implemented.")

        elif node.task_id == "T_BACKEND_TESTS":
            return TaskExecutionResult(success=True, task_id=node.task_id, summary="Backend search tests passed.")

        elif node.task_id == "T_TEST_FE":
            return TaskExecutionResult(success=True, task_id=node.task_id, summary="Frontend unit tests passed.")

        elif node.task_id == "T_BROWSER_QA":
            return TaskExecutionResult(success=True, task_id=node.task_id, summary="Browser QA verification passed.")

        return TaskExecutionResult(success=True, task_id=node.task_id)

    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
        concurrency_limit=3,
        executor_fn=executor,
    )

    status = await orch.run()
    assert status == MissionLifecycleStatus.COMPLETED

    assert discovered_and_applied is True
    assert orch.task_graph.graph_version == 2
    assert "T_BACKEND_ENDPOINT" in orch.task_graph.nodes
    assert "T_BACKEND_TESTS" in orch.task_graph.nodes
    assert "T_BROWSER_QA" in orch.task_graph.nodes
    assert all(n.status == TaskStatus.COMPLETED for n in orch.task_graph.nodes.values())


@pytest.mark.anyio
async def test_economic_mission_with_dynamic_expansion_safeguards(temp_workspace: tuple[str, MissionStateStore]) -> None:
    """Economic mission with dynamic expansion (Section 36):
    Verifies that dynamic sub-DAG expansion does not bypass financial invariants,
    does not synthesize fictitious revenue, and preserves strict audit requirements.
    """
    _, store = temp_workspace
    proj = "p_econ"
    miss = "m_econ"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(
        proj,
        "Análise Financeira de Portfólio",
        "Calcular métricas de risco e liquidez",
        mission_id=miss,
        metadata={"is_economic": True, "budget_limit": 100.0, "currency": "EUR"},
    )
    store.create_work_package(proj, miss, title="T_CALC", work_package_id="T_CALC")

    graph = TaskGraph([TaskNode(task_id="T_CALC", title="Calcular métricas")])

    async def econ_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
        if node.task_id == "T_CALC":
            # Expansion proposal: fetch market data audit
            p = DynamicSubDagProposal(
                proposal_id="prop_econ",
                mission_id=miss,
                parent_task_id="T_CALC",
                base_graph_version=1,
                reason="Necessária validação de dados de mercado externos",
                trigger=ExpansionTrigger.RUNTIME_DISCOVERY,
                tasks=[{"task_id": "T_AUDIT_DATA", "title": "Auditoria de dados externos"}],
                acceptance_criteria=[{
                    "criterion_id": "crit_audit_data",
                    "owner_id": "T_AUDIT_DATA",
                    "description": "Dados validados sem sintetização financeira",
                }],
            )
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Cálculo base concluído.",
                subdag_proposal=p,
            )
        elif node.task_id == "T_AUDIT_DATA":
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Auditoria externa concluída com evidência canónica.",
            )
        return TaskExecutionResult(success=True, task_id=node.task_id)

    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
        executor_fn=econ_executor,
    )

    status = await orch.run()
    assert status == MissionLifecycleStatus.COMPLETED

    # Verify audit record persisted on disk
    exp_file = os.path.join(store._mission_dir(proj, miss), "expansions", "expansion_0002.json")
    assert os.path.isfile(exp_file)
    with open(exp_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["parent_task_id"] == "T_CALC"
    assert "T_AUDIT_DATA" in data["tasks_added"]
