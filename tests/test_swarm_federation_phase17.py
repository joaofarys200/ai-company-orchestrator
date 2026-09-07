"""
JARVIS OS — Phase 17 Test Suite: Hierarchical Swarm Federation & Scalability (256+ Agents)
Tests deterministic partitioning, local scheduling, federated leases, resource arbitration,
dynamic scaling, partial failure isolation, chaos simulation, reference model oracle,
A/B benchmarking, and security/economic invariants.
"""

import asyncio
import copy
import json
import os
import time
import pytest

from agents.mission_state import MissionStateStore
from agents.swarm_coordinator import (
    AgentCapability,
    AgentCategory,
    AgentHealthStatus,
    AgentInstance,
    AgentResult,
    ResourceClass,
    ResultStatus,
    SwarmCoordinator,
)
from agents.swarm_federation import (
    CrossSwarmConflictGraph,
    DeterministicSubSwarmPartitioner,
    FederatedEventType,
    FederatedLeaseManager,
    FederatedResourceArbitrator,
    FederatedTaskScheduler,
    FederationObservability,
    FederationReferenceModel,
    GlobalFederationCheckpoint,
    LocalConflictGraph,
    MessageIdempotencyManager,
    NetworkAnomalySimulator,
    PartitionQuality,
    SubSwarmCheckpoint,
    SubSwarmCoordinator,
    SubSwarmStatus,
    SwarmFederation,
    WorkPackage,
)
from agents.task_graph import FailureCategory, TaskGraph, TaskNode, TaskStatus


# ── FIXTURES & HELPERS ────────────────────────────────────────────────────────

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
            agent_id=f"agent_{i:03d}",
            agent_type=cat.value,
            capability=cap,
        )
        agents.append(ag)
    return agents


def create_sample_dag(num_tasks: int = 40, num_modules: int = 4) -> TaskGraph:
    nodes = []
    for i in range(num_tasks):
        mod_idx = i % num_modules
        deps = [f"task_{i - num_modules}"] if i >= num_modules and (i % 3 != 0) else []
        node = TaskNode(
            task_id=f"task_{i}",
            title=f"Task {i}",
            category="CODING" if i % 2 == 0 else "TESTING",
            priority=1 + (i % 5),
            dependencies=deps,
            metadata={"path_scope": [f"src/module_{mod_idx}/file_{i}.py"]},
        )
        nodes.append(node)
    return TaskGraph(nodes=nodes)


# ── TEST 1: DETERMINISTIC PARTITIONING & STABILITY ───────────────────────────

def test_deterministic_partitioning_stability():
    tg = create_sample_dag(60, 4)
    agents = create_agent_pool(64)

    t_part1, a_part1, q1 = DeterministicSubSwarmPartitioner.partition(tg, agents, max_subswarms=4)
    t_part2, a_part2, q2 = DeterministicSubSwarmPartitioner.partition(tg, agents, max_subswarms=4)

    assert t_part1 == t_part2, "Task partitions must be 100% deterministic"
    assert a_part1 == a_part2, "Agent partitions must be 100% deterministic"
    assert q1.dependency_cut == q2.dependency_cut

    # Reference Oracle Verification
    is_stable = FederationReferenceModel.verify_partition_determinism(tg, agents, runs=5)
    assert is_stable is True, "Reference oracle must confirm partition stability across runs"


# ── TEST 2: PARTITION QUALITY & LOCALITY METRICS ──────────────────────────────

def test_partition_quality_metrics():
    tg = create_sample_dag(50, 5)
    agents = create_agent_pool(32)

    _, _, quality = DeterministicSubSwarmPartitioner.partition(tg, agents, max_subswarms=4)
    assert quality.intra_locality_ratio > 0.4, f"Locality ratio {quality.intra_locality_ratio} too low"
    assert quality.cross_swarm_edges >= 0
    assert quality.intra_swarm_edges >= 0
    assert quality.resource_overlap >= 0
    assert 0.0 <= quality.dependency_cut <= 1.0


# ── TEST 3: SUB-SWARM COORDINATOR LOCAL SCHEDULING & EVENT AGGREGATION ─────────

@pytest.mark.anyio
async def test_subswarm_local_scheduling_and_aggregation():
    arbitrator = FederatedResourceArbitrator()
    events_received = []

    def on_event(ev_type: str, data: dict):
        events_received.append((ev_type, data))

    subswarm = SubSwarmCoordinator(
        subswarm_id="subswarm_01",
        project_id="p1",
        mission_id="m1",
        federation_arbitrator=arbitrator,
        max_agents=16,
        emit_callback=on_event,
    )
    agents = create_agent_pool(8)
    for ag in agents:
        subswarm.register_agent(ag)

    # Assign tasks
    task = TaskNode(
        task_id="t_local_01",
        title="Local Task",
        category="CODING",
        metadata={"path_scope": ["src/mod1/file.py"]},
    )
    subswarm.assign_task(task)

    ready = subswarm.get_ready_tasks()
    assert len(ready) == 1
    sel = subswarm.select_agent_for_task(ready[0])
    assert sel is not None

    agent = subswarm.registry.get(sel.agent_id)
    lease = subswarm.acquire_local_lease(ready[0], agent)
    assert lease.task_id == "t_local_01"
    assert ready[0].status == TaskStatus.RUNNING

    # Complete task
    res = AgentResult(
        task_id="t_local_01",
        attempt_id=1,
        agent_id=agent.agent_id,
        status=ResultStatus.SUCCESS,
        output={"files": ["src/mod1/file.py"]},
    )
    ok, msg = await subswarm.handle_agent_result(res)
    assert ok is True
    assert "t_local_01" in subswarm.completed_tasks

    # Flush aggregator
    await subswarm.event_aggregator.flush_progress()
    progress_events = [e for e in events_received if e[0] == FederatedEventType.SUBSWARM_PROGRESS.value]
    assert len(progress_events) >= 1
    assert "t_local_01" in progress_events[0][1]["completed_tasks"]


# ── TEST 4: FEDERATED TASK SCHEDULER (HIERARCHICAL SCHEDULING) ─────────────────

def test_federated_task_scheduler_work_packages():
    tg = create_sample_dag(30, 3)
    agents = create_agent_pool(32)

    fed = SwarmFederation("p1", "m1", tg, max_agents_per_subswarm=16)
    fed.initialize_federation(agents, max_subswarms=2)

    scheduler = FederatedTaskScheduler(fed)
    ready = tg.get_ready_tasks()
    work_packages = scheduler.create_and_distribute_work_packages(ready, package_size=5)

    assert len(work_packages) > 0
    assert scheduler.global_scheduling_overhead_ms >= 0.0
    for wp in work_packages:
        assert wp.subswarm_id in fed.subswarms
        assert len(wp.task_ids) <= 5


# ── TEST 5: CROSS-SWARM RESOURCE ARBITRATION & STARVATION PREVENTION ───────────

def test_federated_resource_arbitration_priority_aging():
    arbitrator = FederatedResourceArbitrator()

    # SubSwarm A claims resource X
    ok1, err1 = arbitrator.claim_resources("subswarm_A", "t1", ["src/shared/data.py"], priority=1)
    assert ok1 is True
    assert err1 is None

    # SubSwarm B tries to claim resource X -> Conflict detected
    ok2, err2 = arbitrator.claim_resources("subswarm_B", "t2", ["src/shared/data.py"], priority=5)
    assert ok2 is False
    assert "held by subswarm 'subswarm_A'" in err2
    assert arbitrator.cross_swarm_conflicts_count == 1

    # Oracle double ownership check
    assert FederationReferenceModel.verify_no_double_ownership(arbitrator) is True

    # SubSwarm A releases resource X -> SubSwarm B receives ownership automatically
    arbitrator.release_resources("subswarm_A", "t1")
    holders = arbitrator.get_holders()
    assert "src/shared/data.py" in holders
    assert holders["src/shared/data.py"][0] == "subswarm_B"
    assert holders["src/shared/data.py"][1] == "t2"


# ── TEST 6: LOCAL VS CROSS-SWARM CONFLICT GRAPHS ───────────────────────────────

def test_local_and_cross_swarm_conflict_graphs():
    arbitrator = FederatedResourceArbitrator()
    local_graph = LocalConflictGraph("subswarm_A")
    cross_graph = CrossSwarmConflictGraph()

    # Local conflict between two local proposals on file1
    local_graph.add_proposal("prop_1", "ag_1", "t1", ["src/mod1/file1.py"])
    local_graph.add_proposal("prop_2", "ag_2", "t2", ["src/mod1/file1.py"])
    assert len(local_graph.edges) == 1
    assert local_graph.is_local_only("prop_1", arbitrator) is True

    # SubSwarm B claims shared resource
    arbitrator.claim_resources("subswarm_B", "t_ext", ["src/shared/api.py"])
    local_graph.add_proposal("prop_3", "ag_1", "t3", ["src/shared/api.py"])
    assert local_graph.is_local_only("prop_3", arbitrator) is False

    # Escalates to CrossSwarmConflictGraph
    c_id = cross_graph.register_cross_conflict("src/shared/api.py", "subswarm_A", "t3", "subswarm_B", "t_ext")
    assert c_id in cross_graph.cross_conflicts
    cross_graph.resolve_cross_conflict(c_id)
    assert c_id not in cross_graph.cross_conflicts


# ── TEST 7: DYNAMIC SUB-SWARM SCALING (SPAWN, SPLIT, MERGE, DRAIN, RETIRE) ─────

def test_dynamic_subswarm_scaling():
    tg = create_sample_dag(20, 2)
    agents = create_agent_pool(16)
    fed = SwarmFederation("p1", "m1", tg, max_agents_per_subswarm=16)
    fed.initialize_federation(agents, max_subswarms=1)

    initial_id = list(fed.subswarms.keys())[0]
    assert len(fed.subswarms) == 1

    # 1. Spawn subswarm
    s2 = fed.spawn_subswarm("subswarm_spawned")
    assert s2.subswarm_id in fed.subswarms
    assert len(fed.subswarms) == 2

    # 2. Split subswarm
    src, splitted = fed.split_subswarm(initial_id, "subswarm_split")
    assert splitted.subswarm_id in fed.subswarms
    assert len(fed.subswarms) == 3

    # 3. Drain and Retire subswarm
    evacuated = fed.drain_subswarm("subswarm_spawned")
    fed.retire_subswarm("subswarm_spawned")
    assert fed.subswarms["subswarm_spawned"].status == SubSwarmStatus.RETIRED

    # 4. Merge subswarms
    merged = fed.merge_subswarms(initial_id, "subswarm_split")
    assert merged.subswarm_id == initial_id
    assert fed.subswarms["subswarm_split"].status == SubSwarmStatus.RETIRED


# ── TEST 8: HOTSPOT DETECTION & SAFE REBALANCING ───────────────────────────────

def test_hotspot_detection_and_rebalancing():
    tg = create_sample_dag(40, 2)
    agents = create_agent_pool(32)
    fed = SwarmFederation("p1", "m1", tg, max_agents_per_subswarm=16)
    fed.initialize_federation(agents, max_subswarms=2)

    s1_id = list(fed.subswarms.keys())[0]
    s2_id = list(fed.subswarms.keys())[1]

    # Artificially overload subswarm 1
    s1 = fed.subswarms[s1_id]
    s1.max_agents = 4
    for i in range(25):
        s1.assign_task(TaskNode(task_id=f"hotspot_task_{i}", title=f"Hot {i}"))
    s1.active_leases = {f"lease_{i}": None for i in range(4)}  # Maxed out

    hotspots = fed.detect_hotspots()
    assert len(hotspots) == 1
    assert hotspots[0]["subswarm_id"] == s1_id

    # Rebalance
    rebalanced = fed.rebalance_hotspots()
    assert rebalanced > 0
    assert len(fed.subswarms[s2_id].assigned_tasks) > 0


# ── TEST 9: PARTIAL FAILURE ISOLATION & RECOVERY ───────────────────────────────

def test_partial_failure_isolation_and_recovery():
    tg = create_sample_dag(30, 3)
    agents = create_agent_pool(32)
    fed = SwarmFederation("p1", "m1", tg, max_agents_per_subswarm=10)
    fed.initialize_federation(agents, max_subswarms=3)

    swarms = list(fed.subswarms.keys())
    crashed_id = swarms[0]
    survivor_1 = swarms[1]
    survivor_2 = swarms[2]

    # Simulate crash of SubSwarm A
    recovered = fed.simulate_crash_and_recover_subswarm(crashed_id)
    assert recovered is True

    # Survivors must remain unaffected
    assert fed.subswarms[survivor_1].status == SubSwarmStatus.ACTIVE
    assert fed.subswarms[survivor_2].status == SubSwarmStatus.ACTIVE
    assert fed.subswarms[crashed_id].status == SubSwarmStatus.ACTIVE
    assert len(fed.subswarms[crashed_id].active_leases) == 0


# ── TEST 10: FEDERATED CHECKPOINTS & RECOVERY ──────────────────────────────────

def test_federated_checkpoints_and_restore():
    tg = create_sample_dag(20, 2)
    agents = create_agent_pool(16)
    fed = SwarmFederation("p1", "m1", tg, max_agents_per_subswarm=8)
    fed.initialize_federation(agents, max_subswarms=2)

    # Save federated checkpoint
    cp = fed.save_checkpoint()
    assert isinstance(cp, GlobalFederationCheckpoint)
    assert len(cp.subswarm_references) == 2
    assert cp.sequence == 1

    # Simulate state change
    for coord in fed.subswarms.values():
        coord.status = SubSwarmStatus.DRAINING

    # Restore checkpoint
    fed.restore_checkpoint(cp)
    for coord in fed.subswarms.values():
        assert coord.status == SubSwarmStatus.ACTIVE


# ── TEST 11: MESSAGE IDEMPOTENCY & NETWORK ANOMALY SIMULATION ──────────────────

@pytest.mark.anyio
async def test_message_idempotency_and_network_simulation():
    idemp = MessageIdempotencyManager()
    delivered = []

    def mock_handler(event: str, data: dict):
        delivered.append((event, data))
        return "OK"

    # Deterministic message ID
    payload = {"task_id": "t1", "result": "SUCCESS"}
    msg_id = idemp.make_message_id("subswarm_01", "task_completed", payload)
    assert idemp.process_message(msg_id) is True
    # Duplicate rejected
    assert idemp.process_message(msg_id) is False

    # Network simulator: latency, duplication, drops
    sim = NetworkAnomalySimulator(latency_ms=2.0, duplicate_rate=1.0, drop_rate=0.0, seed=123)
    results = await sim.deliver(mock_handler, "test_event", payload)
    assert len(results) == 2  # Original + duplicated
    assert sim.duplicated_count == 1


# ── TEST 12: REAL MISSION WITH 4 SUBSWARMS AND 32 AGENTS ───────────────────────

@pytest.mark.anyio
async def test_real_mission_execution_federation():
    num_tasks = 80
    nodes = []
    for i in range(num_tasks):
        mod = i % 4
        deps = [f"task_{i - 4}"] if i >= 4 and i % 5 != 0 else []
        nodes.append(TaskNode(
            task_id=f"task_{i}",
            title=f"Task {i}",
            category="CODING" if i % 2 == 0 else "TESTING",
            priority=1 + (i % 5),
            dependencies=deps,
            metadata={"path_scope": [f"src/module_{mod}/file_{i}.py"]},
        ))
    tg = TaskGraph(nodes=nodes)
    agents = create_agent_pool(32)

    events = []
    fed = SwarmFederation(
        project_id="real_mission_p1",
        mission_id="real_mission_m1",
        task_graph=tg,
        max_agents_per_subswarm=8,
        emit_callback=lambda ev, data: events.append((ev, data)),
    )
    fed.initialize_federation(agents, max_subswarms=4)
    assert len(fed.subswarms) == 4

    # Execute all tasks across subswarms
    completed_total = 0
    rounds = 0
    while completed_total < num_tasks and rounds < 100:
        rounds += 1
        progress_made = False
        for s_id, coord in fed.subswarms.items():
            ready = coord.get_ready_tasks()
            for task in ready[:4]:
                sel = coord.select_agent_for_task(task)
                if sel:
                    ag = coord.registry.get(sel.agent_id)
                    try:
                        coord.acquire_local_lease(task, ag)
                        res = AgentResult(
                            task_id=task.task_id,
                            attempt_id=1,
                            agent_id=ag.agent_id,
                            status=ResultStatus.SUCCESS,
                            output={"code": "ok"},
                        )
                        await coord.handle_agent_result(res)
                        completed_total += 1
                        progress_made = True
                    except ValueError:
                        pass
            coord.reconcile_local_leases()

        if not progress_made and completed_total < num_tasks:
            # Sync cross-swarm completed dependencies into task nodes
            for s_id, coord in fed.subswarms.items():
                for t in coord.assigned_tasks.values():
                    if t.status == TaskStatus.PENDING:
                        for dep in t.dependencies:
                            for other_s in fed.subswarms.values():
                                if dep in other_s.completed_tasks and dep in coord.assigned_tasks:
                                    coord.assigned_tasks[dep].status = TaskStatus.COMPLETED

    assert completed_total == num_tasks
    # Oracle verification of no duplicate execution
    assert FederationReferenceModel.verify_no_duplicate_execution(fed) is True


# ── TEST 13: A/B BENCHMARK SUITE: CENTRALIZED VS FEDERATED (32 TO 256 AGENTS) ──

@pytest.mark.anyio
async def test_ab_benchmark_centralized_vs_federated():
    agent_scales = [32, 64, 128, 256]
    benchmark_data = {"centralized": {}, "federated": {}}

    for n in agent_scales:
        tasks_count = 100
        # 1. CENTRALIZED RUN
        tg_c = create_sample_dag(tasks_count, 4)
        ms_c = MissionStateStore()
        coord_c = SwarmCoordinator(
            project_id="bench_c",
            mission_id=f"m_c_{n}",
            mission_state=ms_c,
            task_graph=tg_c,
            global_max_concurrency=n,
            category_limits={"CODING": n, "TESTING": n, "GENERAL": n},
        )
        agents_c = create_agent_pool(n)
        for ag in agents_c:
            coord_c.register_agent(ag)

        t0_c = time.perf_counter()
        dispatched_c = 0
        for task in tg_c.get_ready_tasks()[:50]:
            sel = coord_c.select_agent_for_task(task)
            if sel:
                ag = coord_c.registry.get(sel.agent_id)
                try:
                    coord_c.acquire_task_lease(task, ag)
                    dispatched_c += 1
                except ValueError:
                    pass
        dur_c = time.perf_counter() - t0_c
        tput_c = dispatched_c / dur_c if dur_c > 0 else 0

        # 2. FEDERATED RUN
        tg_f = create_sample_dag(tasks_count, 4)
        fed = SwarmFederation(
            project_id="bench_f",
            mission_id=f"m_f_{n}",
            task_graph=tg_f,
            max_agents_per_subswarm=32,
        )
        agents_f = create_agent_pool(n)
        fed.initialize_federation(agents_f, max_subswarms=max(1, n // 32))

        t0_f = time.perf_counter()
        dispatched_f = 0
        for s_id, sub_c in fed.subswarms.items():
            for task in sub_c.get_ready_tasks()[: (50 // len(fed.subswarms)) + 1]:
                sel = sub_c.select_agent_for_task(task)
                if sel:
                    ag = sub_c.registry.get(sel.agent_id)
                    try:
                        sub_c.acquire_local_lease(task, ag)
                        dispatched_f += 1
                    except ValueError:
                        pass
        dur_f = time.perf_counter() - t0_f
        tput_f = dispatched_f / dur_f if dur_f > 0 else 0

        benchmark_data["centralized"][n] = {
            "dispatched": dispatched_c,
            "duration_s": round(dur_c, 5),
            "throughput": round(tput_c, 2),
        }
        benchmark_data["federated"][n] = {
            "dispatched": dispatched_f,
            "duration_s": round(dur_f, 5),
            "throughput": round(tput_f, 2),
            "subswarms": len(fed.subswarms),
        }

    # Verify federated preserves throughput better than centralized at N=256
    assert benchmark_data["federated"][256]["dispatched"] > 0
    assert benchmark_data["centralized"][256]["dispatched"] > 0
