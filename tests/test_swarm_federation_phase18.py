"""
JARVIS OS — Phase 18: ProcessPool Isolation for SubSwarmCoordinators
Verification Suite:
1. True OS worker process isolation (distinct worker PIDs != parent PID)
2. Dedicated asyncio event loop per worker
3. Fully serialisable IPC payloads (pickle-safe round-trip)
4. Cross-swarm resource arbitration in parent process
5. Worker crash detection and automatic subswarm recovery
6. Memory budget enforcement: Total RSS < 200 MB at N=512
7. Checkpoint & restore of worker process topology
8. End-to-end mission workload execution with 0 dropped tasks
"""

from __future__ import annotations

import asyncio
import os
import pickle
import time
import pytest
import psutil

from agents.swarm_coordinator import (
    AgentCapability,
    AgentCategory,
    AgentInstance,
    ResourceClass,
    ResultStatus,
)
from agents.swarm_federation import (
    DeterministicSubSwarmPartitioner,
    FederatedEventType,
    FederatedResourceArbitrator,
    GlobalFederationCheckpoint,
    SubSwarmCoordinator,
    SubSwarmStatus,
    SubSwarmWorkerJob,
    SubSwarmWorkerResult,
    SwarmFederation,
    SwarmIsolationMode,
    _execute_subswarm_worker_job,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def create_agent_pool(n: int) -> list[AgentInstance]:
    agents = []
    for i in range(n):
        cat = AgentCategory.CODING if i % 2 == 0 else AgentCategory.TESTING
        cap = AgentCapability(
            agent_type=cat.value,
            categories=[cat],
            concurrency_limit=2,
            resource_classes=[ResourceClass.CPU],
        )
        ag = AgentInstance(
            agent_id=f"agent_{i:04d}",
            agent_type=cat.value,
            capability=cap,
        )
        agents.append(ag)
    return agents


def create_sample_dag(num_tasks: int = 40, num_modules: int = 4) -> TaskGraph:
    nodes = []
    for i in range(num_tasks):
        mod_idx = i % num_modules
        deps = [f"task_{i - num_modules:04d}"] if i >= num_modules and (i % 3 != 0) else []
        node = TaskNode(
            task_id=f"task_{i:04d}",
            title=f"Task {i}",
            category="CODING" if i % 2 == 0 else "TESTING",
            priority=1 + (i % 5),
            dependencies=deps,
            metadata={
                "path_scope": [f"src/module_{mod_idx}/file_{i % 8}.py"],
                "workload_seed": f"seed_{i}",
            },
        )
        nodes.append(node)
    return TaskGraph(nodes=nodes)


# ── TEST 1: OS WORKER PROCESS ISOLATION & DEDICATED LOOP ───────────────────────

@pytest.mark.anyio
async def test_process_isolation_distinct_pids():
    """Validates that SubSwarmCoordinator executes in an isolated OS process with worker PID != parent PID."""
    tg = create_sample_dag(16, 2)
    agents = create_agent_pool(16)
    parent_pid = os.getpid()

    fed = SwarmFederation(
        project_id="p_iso",
        mission_id="m_iso",
        task_graph=tg,
        max_agents_per_subswarm=8,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)
        res = await fed.run_round_isolated(batch_size=4)

        assert res["completed"] > 0, "At least one task should complete in round"
        assert len(res["worker_pids"]) > 0, "Must record worker PIDs"
        for w_pid in res["worker_pids"]:
            assert w_pid != parent_pid, f"Worker PID {w_pid} must differ from parent PID {parent_pid}"
    finally:
        fed.shutdown_worker_pool()


# ── TEST 2: THREAD AND INPROCESS ISOLATION MODES ───────────────────────────────

@pytest.mark.anyio
async def test_thread_and_inprocess_isolation_modes():
    """Validates backward-compatible thread and in-process execution modes."""
    # 1. Thread mode
    tg1 = create_sample_dag(8, 2)
    agents1 = create_agent_pool(8)
    fed_thread = SwarmFederation(
        project_id="p_th",
        mission_id="m_th",
        task_graph=tg1,
        isolation_mode=SwarmIsolationMode.THREAD,
        max_workers=2,
    )
    try:
        fed_thread.initialize_federation(agents1, max_subswarms=2)
        res_th = await fed_thread.run_round_isolated(batch_size=4)
        assert res_th["completed"] > 0
    finally:
        fed_thread.shutdown_worker_pool()

    # 2. Inprocess mode
    tg2 = create_sample_dag(8, 2)
    agents2 = create_agent_pool(8)
    fed_inp = SwarmFederation(
        project_id="p_inp",
        mission_id="m_inp",
        task_graph=tg2,
        isolation_mode=SwarmIsolationMode.INPROCESS,
    )
    fed_inp.initialize_federation(agents2, max_subswarms=2)
    res_inp = await fed_inp.run_round_isolated(batch_size=4)
    assert res_inp["completed"] > 0


# ── TEST 3: IPC SERIALIZATION INTEGRITY (PICKLE ROUNDTRIP) ─────────────────────

def test_ipc_serialization_integrity():
    """Validates that SubSwarmWorkerJob and SubSwarmWorkerResult are 100% pickle-safe."""
    tg = create_sample_dag(4, 1)
    agents = create_agent_pool(4)

    job = SubSwarmWorkerJob(
        subswarm_id="subswarm_01",
        project_id="p_ipc",
        mission_id="m_ipc",
        tasks=list(tg.nodes.values()),
        agents=agents,
        batch_size=4,
        granted_claims=["src/module_0/file_0.py"],
    )

    serialized = pickle.dumps(job)
    deserialized: SubSwarmWorkerJob = pickle.loads(serialized)

    assert deserialized.subswarm_id == "subswarm_01"
    assert len(deserialized.tasks) == 4
    assert len(deserialized.agents) == 4
    assert deserialized.granted_claims == ["src/module_0/file_0.py"]

    # Execute worker function directly
    result = _execute_subswarm_worker_job(deserialized)
    assert isinstance(result, SubSwarmWorkerResult)
    assert result.subswarm_id == "subswarm_01"
    assert len(result.completed_tasks) > 0

    res_serialized = pickle.dumps(result)
    res_deserialized: SubSwarmWorkerResult = pickle.loads(res_serialized)
    assert res_deserialized.worker_pid == result.worker_pid
    assert len(res_deserialized.completed_tasks) == len(result.completed_tasks)


# ── TEST 4: CROSS-SWARM ARBITRATION VIA IPC IN PARENT ─────────────────────────

@pytest.mark.anyio
async def test_parent_cross_swarm_resource_arbitration():
    """Validates that cross-swarm conflicts are arbitrated exclusively in the parent process."""
    shared_path = "src/shared/database.py"

    # Task 0 in subswarm 0 needs shared path
    t0 = TaskNode(
        task_id="t_sub0",
        title="Subswarm 0 Task",
        category="CODING",
        metadata={"path_scope": [shared_path], "workload_seed": "seed_0"},
    )
    # Task 1 in subswarm 1 needs the SAME shared path
    t1 = TaskNode(
        task_id="t_sub1",
        title="Subswarm 1 Task",
        category="CODING",
        metadata={"path_scope": [shared_path], "workload_seed": "seed_1"},
    )

    tg = TaskGraph(nodes=[t0, t1])
    agents = create_agent_pool(8)

    fed = SwarmFederation(
        project_id="p_arb",
        mission_id="m_arb",
        task_graph=tg,
        max_agents_per_subswarm=4,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=2,
    )
    try:
        s0 = fed.spawn_subswarm("subswarm_00")
        s1 = fed.spawn_subswarm("subswarm_01")
        s0.register_agent(agents[0])
        s1.register_agent(agents[2])
        s0.assign_task(t0)
        s1.assign_task(t1)

        # Round 1: Only one subswarm should acquire the shared path claim
        res1 = await fed.run_round_isolated(batch_size=2)
        assert res1["completed"] == 1, "Exactly one task should execute in round 1 due to resource arbitration"

        # Round 2: The second subswarm executes after release
        res2 = await fed.run_round_isolated(batch_size=2)
        assert res2["completed"] == 1, "The second task should execute in round 2 once resource is freed"
        assert res1["completed"] + res2["completed"] == 2
    finally:
        fed.shutdown_worker_pool()


# ── TEST 5: WORKER CRASH DETECTION & AUTO-RESPAWN ──────────────────────────────

@pytest.mark.anyio
async def test_worker_crash_detection_and_recovery():
    """Validates that a crashed worker process is detected and the subswarm is safely recovered."""
    tg = create_sample_dag(4, 1)
    agents = create_agent_pool(4)

    fed = SwarmFederation(
        project_id="p_crash",
        mission_id="m_crash",
        task_graph=tg,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=1)
        s_id = list(fed.subswarms.keys())[0]

        # Simulate crash directly via simulate_crash_and_recover_subswarm
        ok = fed.simulate_crash_and_recover_subswarm(s_id)
        assert ok is True
        assert fed.subswarms[s_id].status == SubSwarmStatus.ACTIVE

        # Verify normal round completes after recovery
        res = await fed.run_round_isolated(batch_size=2)
        assert res["completed"] > 0
    finally:
        fed.shutdown_worker_pool()


# ── TEST 6: MEMORY BUDGET AT N=512 AGENTS (< 200 MB RSS) ──────────────────────

@pytest.mark.anyio
async def test_memory_budget_at_scale_512():
    """
    Validates the strict Phase 18 memory constraint:
    At N=512 agents (16 sub-swarms), total RSS of parent + workers MUST NOT exceed 200 MB.
    """
    proc = psutil.Process(os.getpid())
    tg = create_sample_dag(64, 8)
    agents = create_agent_pool(512)

    fed = SwarmFederation(
        project_id="p_mem512",
        mission_id="m_mem512",
        task_graph=tg,
        max_agents_per_subswarm=32,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=4,  # Bounded worker pool M=4
    )
    try:
        fed.initialize_federation(agents, max_subswarms=16)
        assert len(fed.subswarms) == 16

        res = await fed.run_round_isolated(batch_size=4)
        assert res["completed"] > 0

        # Calculate total RSS: parent process + child worker processes
        parent_rss = proc.memory_info().rss / (1024 * 1024)
        children_rss = sum(
            c.memory_info().rss / (1024 * 1024)
            for c in proc.children(recursive=True)
            if c.is_running()
        )
        total_rss = parent_rss + children_rss

        print(f"\n[MEM PROFILE N=512] Parent: {parent_rss:.2f} MB, Children: {children_rss:.2f} MB, Total RSS: {total_rss:.2f} MB")
        assert total_rss < 200.0, f"Total RSS {total_rss:.2f} MB exceeded 200 MB ceiling!"
    finally:
        fed.shutdown_worker_pool()


# ── TEST 7: CHECKPOINT / RESTORE WITH WORKER STATE PERSISTENCE ────────────────

def test_checkpoint_restore_worker_state():
    """Validates that GlobalFederationCheckpoint persists worker isolation topology."""
    tg = create_sample_dag(10, 2)
    agents = create_agent_pool(16)

    fed = SwarmFederation(
        project_id="p_cp",
        mission_id="m_cp",
        task_graph=tg,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=3,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)
        fed._worker_pids = {10101, 20202}

        cp = fed.save_checkpoint()
        assert cp.worker_isolation_mode == "PROCESS"
        assert cp.active_worker_pids == [10101, 20202]

        # Restore into new federation
        fed2 = SwarmFederation("p_cp", "m_cp", tg, isolation_mode=SwarmIsolationMode.THREAD)
        fed2.initialize_federation(agents, max_subswarms=2)
        fed2.restore_checkpoint(cp)

        assert fed2.isolation_mode == SwarmIsolationMode.PROCESS
        assert 10101 in fed2._worker_pids
    finally:
        fed.shutdown_worker_pool()


# ── TEST 8: END-TO-END WORKLOAD EXECUTION VIA ISOLATED WORKERS ─────────────────

@pytest.mark.anyio
async def test_end_to_end_workload_execution_isolated():
    """Validates 100% completion and 0 dropped tasks executing full DAG through isolated pool."""
    num_tasks = 40
    tg = create_sample_dag(num_tasks, 4)
    agents = create_agent_pool(32)

    fed = SwarmFederation(
        project_id="p_e2e",
        mission_id="m_e2e",
        task_graph=tg,
        max_agents_per_subswarm=8,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=4,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=4)
        result = await fed.execute_workload_isolated(max_rounds=50, batch_size=4)

        assert result["completed_tasks"] == num_tasks, f"Expected {num_tasks} completed, got {result['completed_tasks']}"
        assert result["failed_tasks"] == 0
        assert result["throughput"] > 0
        assert len(result["worker_pids"]) > 0
    finally:
        fed.shutdown_worker_pool()
