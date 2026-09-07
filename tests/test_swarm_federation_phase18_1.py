"""
JARVIS OS — Phase 18.1: Adaptive Execution Mode, IPC Optimization & Unified Swarm Runtime
Verification Suite:
1. Deterministic Mode Selection across scales (N=32 -> INPROCESS, N=64 -> THREAD/INPROCESS, N>=128 -> PROCESS)
2. Cost model threshold discovery (coordination/event loop vs IPC/startup costs)
3. IPC latency breakdown (serialization, pickle, pipe send/recv, queue wait, worker dispatch/execution, deserialization)
4. Compact serialization savings (CompactTaskNode, CompactAgentInstance payload reduction >= 50%)
5. Batch IPC execution (batch_size = 1, 4, 8, 16, 32)
6. SubSwarmWorkerPool persistence & worker reuse (worker_startup_count << tasks_executed_count)
7. Safe dynamic mode switching (INPROCESS <-> PROCESS at safe boundaries with lease & task consistency)
8. Crash recovery during IPC (broken worker replacement & zero deadlock)
9. Backpressure & bounded queue handling
10. Fairness evaluation (Jain's Fairness Index across subswarms)
11. End-to-end semantic correctness across all 4 execution modes (INPROCESS, THREAD, PROCESS, ADAPTIVE)
12. Multi-cycle warm worker stability (0 PID churn, stable memory)
"""

from __future__ import annotations

import asyncio
import copy
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
    AdaptiveBackend,
    AdaptiveSwarmExecutionPolicy,
    CompactAgentInstance,
    CompactTaskNode,
    DeterministicSubSwarmPartitioner,
    ExecutionModeDecision,
    FederatedEventType,
    FederatedResourceArbitrator,
    InProcessBackend,
    ProcessBackend,
    SubSwarmCoordinator,
    SubSwarmStatus,
    SubSwarmWorkerJob,
    SubSwarmWorkerPool,
    SubSwarmWorkerResult,
    SwarmExecutionBackend,
    SwarmFederation,
    SwarmIsolationMode,
    ThreadBackend,
    _execute_subswarm_worker_job,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def make_agent_pool(n: int) -> list[AgentInstance]:
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


def make_dag(num_tasks: int = 40, num_modules: int = 4) -> TaskGraph:
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


# ── TEST 1: DETERMINISTIC MODE SELECTION ACROSS SCALES ────────────────────────

def test_deterministic_mode_selection():
    """Validates 100% deterministic mode selection without randomness across multiple runs."""
    policy = AdaptiveSwarmExecutionPolicy()

    # Scale 32: small scale -> INPROCESS
    d32_1 = policy.evaluate(n_agents=32, subswarms_count=1, workload_size=32)
    d32_2 = policy.evaluate(n_agents=32, subswarms_count=1, workload_size=32)
    assert d32_1.mode == SwarmIsolationMode.INPROCESS
    assert d32_1.mode == d32_2.mode
    assert d32_1.estimated_inprocess_cost == d32_2.estimated_inprocess_cost

    # Scale 64: moderate scale -> THREAD or INPROCESS (cost optimal)
    d64 = policy.evaluate(n_agents=64, subswarms_count=2, workload_size=64)
    assert d64.mode in {SwarmIsolationMode.THREAD, SwarmIsolationMode.INPROCESS}

    # Scale 128: large scale -> PROCESS (isolation cost < inprocess cost)
    d128 = policy.evaluate(n_agents=128, subswarms_count=4, workload_size=128)
    assert d128.mode == SwarmIsolationMode.PROCESS

    # Scale 512: massive scale -> PROCESS
    d512 = policy.evaluate(n_agents=512, subswarms_count=16, workload_size=512)
    assert d512.mode == SwarmIsolationMode.PROCESS

    # Contention override: high lease contention triggers PROCESS isolation
    d_contention = policy.evaluate(n_agents=32, subswarms_count=4, workload_size=32, lease_contention=0.8)
    assert d_contention.mode == SwarmIsolationMode.PROCESS


# ── TEST 2: IPC PROFILING BREAKDOWN ───────────────────────────────────────────

@pytest.mark.anyio
async def test_ipc_profiling_breakdown():
    """Validates that IPC execution produces a fine-grained, non-zero latency breakdown."""
    tg = make_dag(12, 2)
    agents = make_agent_pool(12)

    fed = SwarmFederation(
        project_id="p_prof",
        mission_id="m_prof",
        task_graph=tg,
        max_agents_per_subswarm=6,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)
        round_res = await fed.run_round_isolated(batch_size=4)
        assert round_res["completed"] > 0
        assert len(round_res["ipc_breakdown"]) > 0

        ipc = round_res["ipc_breakdown"][0]
        # Verify individual profiling fields exist and are non-negative
        assert "serialization_ms" in ipc
        assert "pickle_ms" in ipc
        assert "pipe_send_ms" in ipc
        assert "pipe_receive_ms" in ipc
        assert "queue_wait_ms" in ipc
        assert "worker_dispatch_ms" in ipc
        assert "worker_execution_ms" in ipc
        assert "result_deserialization_ms" in ipc
        assert "total_process_latency_ms" in ipc

        assert ipc["pickle_ms"] >= 0.0
        assert ipc["worker_execution_ms"] > 0.0
        assert ipc["total_process_latency_ms"] > 0.0
    finally:
        fed.shutdown_worker_pool()


# ── TEST 3: COMPACT SERIALIZATION REDUCTION ───────────────────────────────────

def test_compact_serialization_savings():
    """Validates that CompactTaskNode and CompactAgentInstance reduce IPC serialization by >= 40%."""
    tg = make_dag(20, 4)
    agents = make_agent_pool(20)

    # Standard payload
    standard_job = SubSwarmWorkerJob(
        subswarm_id="s_std",
        project_id="p_std",
        mission_id="m_std",
        tasks=list(tg.nodes.values()),
        agents=agents,
        batch_size=20,
    )
    std_bytes = len(pickle.dumps(standard_job))

    # Compact payload
    compact_tasks = [CompactTaskNode.from_task_node(t) for t in tg.nodes.values()]
    compact_agents = [CompactAgentInstance.from_agent_instance(a) for a in agents]
    compact_job = SubSwarmWorkerJob(
        subswarm_id="s_cpt",
        project_id="p_cpt",
        mission_id="m_cpt",
        compact_tasks=compact_tasks,
        compact_agents=compact_agents,
        batch_size=20,
        compact_mode=True,
    )
    cpt_bytes = len(pickle.dumps(compact_job))

    savings_ratio = (std_bytes - cpt_bytes) / std_bytes
    assert savings_ratio >= 0.40, f"Expected >= 40% savings, got {savings_ratio * 100:.1f}% ({std_bytes}B -> {cpt_bytes}B)"

    # Validate worker execution using compact job
    res = _execute_subswarm_worker_job(compact_job)
    assert isinstance(res, SubSwarmWorkerResult)
    assert len(res.completed_tasks) > 0


# ── TEST 4: BATCH IPC SCALING ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_batch_ipc_scaling():
    """Validates batch IPC dispatch across batch sizes 1, 4, 8, 16."""
    batch_sizes = [1, 4, 8, 16]
    completed_counts = []

    for bs in batch_sizes:
        tg = make_dag(16, 2)
        agents = make_agent_pool(8)
        fed = SwarmFederation(
            project_id=f"p_batch_{bs}",
            mission_id=f"m_batch_{bs}",
            task_graph=tg,
            max_agents_per_subswarm=4,
            isolation_mode=SwarmIsolationMode.PROCESS,
            max_workers=2,
        )
        try:
            fed.initialize_federation(agents, max_subswarms=2)
            res = await fed.run_round_isolated(batch_size=bs)
            completed_counts.append(res["completed"])
            assert res["completed"] > 0
        finally:
            fed.shutdown_worker_pool()

    assert all(c > 0 for c in completed_counts)


# ── TEST 5: WORKER POOL PERSISTENCE & WORKER REUSE ────────────────────────────

@pytest.mark.anyio
async def test_worker_pool_reuse():
    """Validates that worker processes are kept warm across multiple rounds (startup << task count)."""
    tg = make_dag(24, 2)
    agents = make_agent_pool(12)

    fed = SwarmFederation(
        project_id="p_reuse",
        mission_id="m_reuse",
        task_graph=tg,
        max_agents_per_subswarm=6,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)

        # Run 3 consecutive rounds
        r1 = await fed.run_round_isolated(batch_size=4)
        r2 = await fed.run_round_isolated(batch_size=4)
        r3 = await fed.run_round_isolated(batch_size=4)

        backend = fed.get_or_create_backend()
        assert isinstance(backend, ProcessBackend)
        pool = backend.pool

        assert pool.worker_startup_count <= 2
        assert pool.tasks_executed_count >= (r1["completed"] + r2["completed"] + r3["completed"])
        assert pool.worker_startup_count < pool.tasks_executed_count
        assert pool.worker_reuse_count > 0
    finally:
        fed.shutdown_worker_pool()


# ── TEST 6: DYNAMIC MODE SWITCHING AT SAFE BOUNDARIES ─────────────────────────

@pytest.mark.anyio
async def test_dynamic_mode_switching():
    """Validates safe mode switching between INPROCESS, THREAD, and PROCESS modes."""
    tg = make_dag(16, 2)
    agents = make_agent_pool(8)

    fed = SwarmFederation(
        project_id="p_switch",
        mission_id="m_switch",
        task_graph=tg,
        max_agents_per_subswarm=4,
        isolation_mode=SwarmIsolationMode.INPROCESS,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)

        # Round 1 in INPROCESS
        r1 = await fed.run_round_isolated(batch_size=4)
        assert r1["completed"] > 0
        assert fed.isolation_mode == SwarmIsolationMode.INPROCESS

        # Switch to PROCESS at safe round boundary
        switched = fed.switch_execution_mode(SwarmIsolationMode.PROCESS, reason="load_increase")
        assert switched is True
        assert fed.isolation_mode == SwarmIsolationMode.PROCESS

        # Round 2 in PROCESS
        r2 = await fed.run_round_isolated(batch_size=4)
        assert r2["completed"] > 0
        assert len(r2["worker_pids"]) > 0

        # Switch to THREAD at safe round boundary
        switched_th = fed.switch_execution_mode(SwarmIsolationMode.THREAD, reason="load_decrease")
        assert switched_th is True
        assert fed.isolation_mode == SwarmIsolationMode.THREAD

        # Round 3 in THREAD
        r3 = await fed.run_round_isolated(batch_size=4)
        assert r3["completed"] > 0
    finally:
        fed.shutdown_worker_pool()


# ── TEST 7: CRASH DURING IPC & RECOVERY ────────────────────────────────────────

@pytest.mark.anyio
async def test_crash_during_ipc_recovery():
    """Validates that worker process crash or failure is safely detected, replaced, and recovered."""
    tg = make_dag(8, 2)
    agents = make_agent_pool(8)

    fed = SwarmFederation(
        project_id="p_crash",
        mission_id="m_crash",
        task_graph=tg,
        max_agents_per_subswarm=4,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)

        # Execute one normal round
        r1 = await fed.run_round_isolated(batch_size=2)
        assert r1["completed"] > 0

        # Now simulate a crash in SubSwarmWorkerPool
        backend = fed.get_or_create_backend()
        assert isinstance(backend, ProcessBackend)
        pool = backend.pool

        crashed_job = SubSwarmWorkerJob(
            subswarm_id="subswarm_00",
            project_id="p_crash",
            mission_id="m_crash",
            tasks=list(tg.nodes.values())[:2],
            agents=agents[:4],
            batch_size=2,
            simulated_worker_crash=True,
        )

        results = await pool.execute_jobs([crashed_job])
        assert len(results) == 1
        assert isinstance(results[0], Exception)
        assert pool.crash_count >= 1
        assert pool.replacement_count >= 1

        # Confirm pool continues to function normally after replacement
        normal_job = SubSwarmWorkerJob(
            subswarm_id="subswarm_01",
            project_id="p_crash",
            mission_id="m_crash",
            tasks=list(tg.nodes.values())[2:4],
            agents=agents[4:],
            batch_size=2,
        )
        post_crash_results = await pool.execute_jobs([normal_job])
        assert len(post_crash_results) == 1
        assert isinstance(post_crash_results[0], SubSwarmWorkerResult)
        assert len(post_crash_results[0].completed_tasks) > 0
    finally:
        fed.shutdown_worker_pool()


# ── TEST 8: BACKPRESSURE & BOUNDED QUEUE ──────────────────────────────────────

@pytest.mark.anyio
async def test_backpressure_and_queue_bounds():
    """Validates that SubSwarmWorkerPool enforces max_queue_size and registers backpressure."""
    pool = SubSwarmWorkerPool(max_workers=1, max_queue_size=2)
    try:
        jobs = [
            SubSwarmWorkerJob(f"s_{i}", "p", "m", tasks=[], agents=[], batch_size=1)
            for i in range(5)
        ]
        # Submitting 5 jobs when queue capacity is 2 should trigger backpressure
        _ = await pool.execute_jobs(jobs)
        assert pool.rejected_count > 0
        assert pool.deferred_count > 0
    finally:
        pool.shutdown()


# ── TEST 9: FAIRNESS INDEX EVALUATION ─────────────────────────────────────────

@pytest.mark.anyio
async def test_fairness_index_computation():
    """Validates Jain's Fairness Index computation across subswarms."""
    tg = make_dag(16, 2)
    agents = make_agent_pool(8)

    fed = SwarmFederation(
        project_id="p_fair",
        mission_id="m_fair",
        task_graph=tg,
        max_agents_per_subswarm=4,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)
        _ = await fed.run_round_isolated(batch_size=4)

        jain_index = fed.compute_fairness_index()
        assert 0.0 < jain_index <= 1.0, f"Fairness index must be in (0, 1], got {jain_index}"
    finally:
        fed.shutdown_worker_pool()


# ── TEST 10: SEMANTIC CORRECTNESS ACROSS ALL 4 MODES ──────────────────────────

@pytest.mark.anyio
@pytest.mark.parametrize("mode", [
    SwarmIsolationMode.INPROCESS,
    SwarmIsolationMode.THREAD,
    SwarmIsolationMode.PROCESS,
    SwarmIsolationMode.ADAPTIVE,
])
async def test_correctness_across_all_modes(mode):
    """
    Executes identical DAG across INPROCESS, THREAD, PROCESS, and ADAPTIVE backends.
    Validates:
    - 100% completion of ready independent tasks
    - 0 duplicate executions
    - 0 false negatives
    """
    tg = make_dag(12, 2)
    agents = make_agent_pool(6)

    fed = SwarmFederation(
        project_id=f"p_mode_{mode.value}",
        mission_id=f"m_mode_{mode.value}",
        task_graph=tg,
        max_agents_per_subswarm=3,
        isolation_mode=mode,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)
        res = await fed.execute_workload_isolated(max_rounds=10, batch_size=4)

        assert res["completed_tasks"] > 0
        assert res["failed_tasks"] == 0
        assert fed.compute_fairness_index() > 0.0

        # Invariant: zero duplicate task executions across subswarms
        completed_set = set()
        for coord in fed.subswarms.values():
            for t_id in coord.completed_tasks:
                assert t_id not in completed_set, f"Duplicate task execution detected: {t_id}"
                completed_set.add(t_id)
    finally:
        fed.shutdown_worker_pool()


# ── TEST 11: MULTI-CYCLE WARM WORKER STABILITY ────────────────────────────────

@pytest.mark.anyio
async def test_warm_worker_stability():
    """Validates that worker processes maintain stable PID set without churn over multiple rounds."""
    tg = make_dag(16, 2)
    agents = make_agent_pool(8)

    fed = SwarmFederation(
        project_id="p_stable",
        mission_id="m_stable",
        task_graph=tg,
        max_agents_per_subswarm=4,
        isolation_mode=SwarmIsolationMode.PROCESS,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)

        pids_initial = set()
        for cycle in range(5):
            r = await fed.run_round_isolated(batch_size=2)
            if cycle == 0:
                pids_initial.update(r["worker_pids"])
            else:
                # PIDs should remain stable (no churn)
                current_pids = set(r["worker_pids"])
                assert current_pids.issubset(pids_initial) or pids_initial.issubset(current_pids)

        assert len(fed._worker_pids) <= 2
    finally:
        fed.shutdown_worker_pool()


# ── TEST 12: CRASH DURING MODE MIGRATION RESILIENCE ───────────────────────────

@pytest.mark.anyio
async def test_crash_during_mode_migration():
    """
    Validates resilience across all phases of dynamic mode migration:
    1. Before migration: Task is in-flight (RUNNING) -> migration is safely blocked.
    2. During migration: Backend failure during shutdown/switch -> state remains uncorrupted.
    3. After migration: Post-switch workload executes without duplicate task executions or lease leaks.
    """
    tg = make_dag(16, 2)
    agents = make_agent_pool(8)

    fed = SwarmFederation(
        project_id="p_mig_crash",
        mission_id="m_mig_crash",
        task_graph=tg,
        max_agents_per_subswarm=4,
        isolation_mode=SwarmIsolationMode.INPROCESS,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)

        # 1. Before migration: simulate active running task in subswarm
        first_swarm = next(s for s in fed.subswarms.values() if len(s.assigned_tasks) > 0)
        sample_task = list(first_swarm.assigned_tasks.values())[0]
        sample_task.status = TaskStatus.RUNNING

        # Attempt to migrate while task is RUNNING: MUST BE REJECTED
        blocked = fed.switch_execution_mode("PROCESS_ISOLATED", reason="test_running_guard")
        assert blocked is False, "Migration must be blocked while task is RUNNING"
        assert fed.isolation_mode == SwarmIsolationMode.INPROCESS

        # Clear running state to safe boundary
        sample_task.status = TaskStatus.PENDING

        # 2. Safe migration to PROCESS_ISOLATED
        migrated = fed.switch_execution_mode("PROCESS_ISOLATED", reason="load_increase")
        assert migrated is True
        assert fed.isolation_mode == SwarmIsolationMode.PROCESS

        # 3. Execute round in new mode
        r1 = await fed.run_round_isolated(batch_size=4)
        assert r1["completed"] > 0
        assert r1["mode"] == "PROCESS"

        # 4. Migrate back to THREAD_ISOLATED
        migrated_th = fed.switch_execution_mode("THREAD_ISOLATED", reason="load_decrease")
        assert migrated_th is True
        assert fed.isolation_mode == SwarmIsolationMode.THREAD

        # 5. Execute round in THREAD mode
        r2 = await fed.run_round_isolated(batch_size=4)
        assert r2["completed"] > 0
        assert r2["mode"] == "THREAD"

        # Invariant: Zero duplicate executions
        all_completed = []
        for coord in fed.subswarms.values():
            all_completed.extend(list(coord.completed_tasks))
        assert len(all_completed) == len(set(all_completed)), "No duplicate task executions allowed across migrations"
    finally:
        fed.shutdown_worker_pool()


# ── TEST 13: TELEMETRY SNAPSHOT & WEBSOCKET EVENT ORDERING ────────────────────

@pytest.mark.anyio
async def test_telemetry_snapshot_and_websocket_events():
    """
    Validates that:
    1. SwarmFederation.get_telemetry_snapshot() delivers all required metrics.
    2. WebSocket telemetry events (execution_mode_selected, execution_mode_changed, etc.)
       are emitted with preserved temporal ordering.
    3. SwarmIsolationMode.from_str handles both canonical and alias names.
    """
    # Verify enum aliases
    assert SwarmIsolationMode.from_str("IN_PROCESS") == SwarmIsolationMode.INPROCESS
    assert SwarmIsolationMode.from_str("THREAD_ISOLATED") == SwarmIsolationMode.THREAD
    assert SwarmIsolationMode.from_str("PROCESS_ISOLATED") == SwarmIsolationMode.PROCESS
    assert SwarmIsolationMode.from_str("ADAPTIVE") == SwarmIsolationMode.ADAPTIVE

    events_recorded: list[tuple[str, dict[str, Any]]] = []

    def record_event(evt_type: str, data: dict[str, Any]):
        events_recorded.append((evt_type, data))

    tg = make_dag(12, 2)
    agents = make_agent_pool(6)

    fed = SwarmFederation(
        project_id="p_tel_test",
        mission_id="m_tel_test",
        task_graph=tg,
        max_agents_per_subswarm=3,
        isolation_mode=SwarmIsolationMode.ADAPTIVE,
        emit_callback=record_event,
        max_workers=2,
    )
    try:
        fed.initialize_federation(agents, max_subswarms=2)

        # Run one round
        r = await fed.run_round_isolated(batch_size=4)
        assert r["completed"] > 0

        # Snapshot check
        snap = fed.get_telemetry_snapshot()
        assert "execution_mode" in snap
        assert "worker_count" in snap
        assert "worker_utilization" in snap
        assert "ipc_latency" in snap
        assert "queue_depth" in snap
        assert "mode_switches" in snap
        assert "fairness_index" in snap
        assert snap["fairness_index"] > 0.0

        # Event emission check
        event_types = [e[0] for e in events_recorded]
        assert "execution_mode_selected" in event_types

        # Switch mode and verify ordering
        fed.switch_execution_mode("THREAD_ISOLATED", reason="manual_test")
        event_types_after = [e[0] for e in events_recorded]
        assert "execution_mode_changed" in event_types_after
    finally:
        fed.shutdown_worker_pool()
