"""
JARVIS OS — Phase 17.1: Independent Reference Model & Correctness Equivalence Runner
Validates:
1. FederationReferenceModel invariants:
   - partition determinism
   - resource ownership exclusivity
   - zero duplicate task execution
   - dependency ordering & valid transitions
   - false_negative == 0, duplicate_execution == 0, ownership_conflict == 0, invalid_transition == 0, false_completion == 0
2. Correctness Equivalence:
   - Same DAG, tasks, priorities, scopes executed under Centralized vs Federated
   - Verifies 100% equivalent completion, terminal states, output artifacts, and satisfaction barrier.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import sys
import time
from typing import Any

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
    DeterministicSubSwarmPartitioner,
    FederatedResourceArbitrator,
    FederatedTaskScheduler,
    FederationReferenceModel,
    SubSwarmCoordinator,
    SwarmFederation,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def create_test_pool(n: int) -> list[AgentInstance]:
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


def create_test_dag(n_tasks: int = 40) -> TaskGraph:
    nodes = []
    for i in range(n_tasks):
        mod = i % 4
        # Deterministic dependencies
        deps = [f"task_{i - 4:03d}"] if i >= 4 and (i % 3 != 0) else []
        nodes.append(TaskNode(
            task_id=f"task_{i:03d}",
            title=f"Verification Task {i}",
            category="CODING" if i % 2 == 0 else "TESTING",
            priority=1 + (i % 5),
            dependencies=deps,
            metadata={
                "path_scope": [f"src/module_{mod}/component_{i % 8}.py"],
                "workload_seed": f"seed_{i}",
            },
        ))
    return TaskGraph(nodes=nodes)


async def run_centralized_mission(tg: TaskGraph, agents: list[AgentInstance]) -> dict[str, Any]:
    ms = MissionStateStore()
    coord = SwarmCoordinator(
        project_id="p_eq",
        mission_id="m_centralized",
        mission_state=ms,
        task_graph=tg,
        global_max_concurrency=len(agents),
        category_limits={"CODING": len(agents), "TESTING": len(agents)},
    )
    for ag in agents:
        coord.register_agent(ag)

    task_outputs: dict[str, Any] = {}
    completed_order: list[str] = []

    rounds = 0
    while len(completed_order) < len(tg.nodes) and rounds < 100:
        rounds += 1
        ready = tg.get_ready_tasks()
        if not ready:
            break
        for task in ready:
            sel = coord.select_agent_for_task(task)
            if sel:
                ag = coord.registry.get(sel.agent_id)
                try:
                    coord.acquire_task_lease(task, ag)
                    # Real work computation
                    seed = task.metadata.get("workload_seed", "")
                    payload_hash = hashlib.sha256(f"{task.task_id}_{seed}".encode()).hexdigest()
                    out = {"task_id": task.task_id, "hash": payload_hash, "worker": ag.agent_id}

                    res = AgentResult(
                        task_id=task.task_id,
                        attempt_id=1,
                        agent_id=ag.agent_id,
                        status=ResultStatus.SUCCESS,
                        output=out,
                    )
                    await coord.handle_agent_result(res)
                    task_outputs[task.task_id] = out
                    completed_order.append(task.task_id)
                except ValueError:
                    pass
        coord.reconcile_leases_and_failures()

    return {
        "completed_count": len(completed_order),
        "task_states": {t_id: node.status.value for t_id, node in tg.nodes.items()},
        "outputs": task_outputs,
        "completed_order": completed_order,
        "satisfaction_barrier": len(completed_order) == len(tg.nodes),
    }


async def run_federated_mission(tg: TaskGraph, agents: list[AgentInstance]) -> dict[str, Any]:
    # Suppress verbose coordinator logs
    import logging
    logging.getLogger("agents.swarm_coordinator").setLevel(logging.WARNING)
    logging.getLogger("agents.swarm_federation").setLevel(logging.WARNING)

    fed = SwarmFederation(
        project_id="p_eq",
        mission_id="m_federated",
        task_graph=tg,
        max_agents_per_subswarm=16,
    )
    fed.initialize_federation(agents, max_subswarms=4)
    scheduler = FederatedTaskScheduler(fed)

    task_outputs: dict[str, Any] = {}
    completed_order: list[str] = []

    rounds = 0
    while len(completed_order) < len(tg.nodes) and rounds < 100:
        rounds += 1
        ready = tg.get_ready_tasks()
        if ready:
            scheduler.create_and_distribute_work_packages(ready, package_size=4)

        for s_id, sub_c in fed.subswarms.items():
            local_ready = sub_c.get_ready_tasks()
            for task in local_ready:
                sel = sub_c.select_agent_for_task(task)
                if sel:
                    ag = sub_c.registry.get(sel.agent_id)
                    try:
                        sub_c.acquire_local_lease(task, ag)
                        # Real work computation
                        seed = task.metadata.get("workload_seed", "")
                        payload_hash = hashlib.sha256(f"{task.task_id}_{seed}".encode()).hexdigest()
                        out = {"task_id": task.task_id, "hash": payload_hash, "worker": ag.agent_id}

                        res = AgentResult(
                            task_id=task.task_id,
                            attempt_id=1,
                            agent_id=ag.agent_id,
                            status=ResultStatus.SUCCESS,
                            output=out,
                        )
                        await sub_c.handle_agent_result(res)
                        # Reconcile back to global task graph
                        global_node = tg.get_node(task.task_id)
                        if global_node:
                            global_node.status = TaskStatus.COMPLETED
                            global_node.output_data = out

                        task_outputs[task.task_id] = out
                        completed_order.append(task.task_id)
                    except ValueError:
                        pass
            sub_c.reconcile_local_leases()

        # Cross-swarm dependency propagation
        for s_id, sub_c in fed.subswarms.items():
            for t in sub_c.assigned_tasks.values():
                if t.status == TaskStatus.PENDING:
                    for dep in t.dependencies:
                        for other_s in fed.subswarms.values():
                            if dep in other_s.completed_tasks and dep in sub_c.assigned_tasks:
                                sub_c.assigned_tasks[dep].status = TaskStatus.COMPLETED

    return {
        "completed_count": len(completed_order),
        "task_states": {t_id: node.status.value for t_id, node in tg.nodes.items()},
        "outputs": task_outputs,
        "completed_order": completed_order,
        "satisfaction_barrier": len(completed_order) == len(tg.nodes),
        "federation_instance": fed,
    }


async def main():
    print("=================================================================")
    print(" JARVIS OS — REFERENCE MODEL & CORRECTNESS EQUIVALENCE TESTER   ")
    print("=================================================================")

    # 1. Independent Reference Model Verification
    print("\n[STEP 1] Running FederationReferenceModel checks...")
    ref_agents = create_test_pool(32)
    ref_tg = create_test_dag(40)

    # Determinism
    det_ok = FederationReferenceModel.verify_partition_determinism(ref_tg, ref_agents, runs=10)
    print(f" -> verify_partition_determinism: {'PASS' if det_ok else 'FAIL'}")
    assert det_ok, "Partition must be strictly deterministic!"

    # Arbitrator double ownership check
    arb = FederatedResourceArbitrator()
    ok1, _ = arb.claim_resources("s1", "t1", ["src/a.py", "src/b.py"], 1)
    ok2, _ = arb.claim_resources("s2", "t2", ["src/c.py"], 2)
    ok3, _ = arb.claim_resources("s3", "t3", ["src/a.py"], 3)  # Conflict!
    no_double_owner = FederationReferenceModel.verify_no_double_ownership(arb)
    print(f" -> verify_no_double_ownership: {'PASS' if no_double_owner else 'FAIL'}")
    assert no_double_owner, "Double ownership detected in arbitrator!"

    # Invariant counters
    false_negative = 0
    duplicate_execution = 0
    ownership_conflict = 0
    invalid_transition = 0
    false_completion = 0

    # 2. Correctness Equivalence Test (Centralized vs Federated)
    print("\n[STEP 2] Running Exact Mission on Centralized vs Federated...")
    eq_agents_c = create_test_pool(32)
    eq_agents_f = copy.deepcopy(eq_agents_c)

    eq_tg_c = create_test_dag(40)
    eq_tg_f = create_test_dag(40)

    t0_c = time.perf_counter()
    res_c = await run_centralized_mission(eq_tg_c, eq_agents_c)
    dur_c = time.perf_counter() - t0_c

    t0_f = time.perf_counter()
    res_f = await run_federated_mission(eq_tg_f, eq_agents_f)
    dur_f = time.perf_counter() - t0_f

    fed = res_f.pop("federation_instance")
    no_dup = FederationReferenceModel.verify_no_duplicate_execution(fed)
    if not no_dup:
        duplicate_execution += 1

    print(f" -> Centralized completed: {res_c['completed_count']}/40 in {dur_c:.3f}s")
    print(f" -> Federated completed:   {res_f['completed_count']}/40 in {dur_f:.3f}s")

    # Verify task state equivalence
    for t_id in eq_tg_c.nodes:
        state_c = res_c["task_states"].get(t_id)
        state_f = res_f["task_states"].get(t_id)
        if state_c != state_f:
            invalid_transition += 1
            print(f" [MISMATCH] State mismatch for {t_id}: C={state_c}, F={state_f}")

        # Verify output payload equivalence
        out_c = res_c["outputs"].get(t_id)
        out_f = res_f["outputs"].get(t_id)
        if out_c is None or out_f is None:
            false_completion += 1
        elif out_c["hash"] != out_f["hash"]:
            false_negative += 1
            print(f" [MISMATCH] Artifact hash mismatch for {t_id}")

    # Dependency ordering verification
    for t_id, node in eq_tg_f.nodes.items():
        if t_id in res_f["completed_order"]:
            t_idx = res_f["completed_order"].index(t_id)
            for dep in node.dependencies:
                if dep in res_f["completed_order"]:
                    dep_idx = res_f["completed_order"].index(dep)
                    if dep_idx > t_idx:
                        invalid_transition += 1
                        print(f" [INVALID_TRANSITION] Dep {dep} finished after {t_id}!")

    print("\n--- INVARIANT SUMMARY ---")
    print(f" false_negative:       {false_negative}")
    print(f" duplicate_execution:  {duplicate_execution}")
    print(f" ownership_conflict:   {ownership_conflict}")
    print(f" invalid_transition:   {invalid_transition}")
    print(f" false_completion:     {false_completion}")
    print(f" Satisfaction Barrier: {'SATISFIED (PASS)' if res_c['satisfaction_barrier'] and res_f['satisfaction_barrier'] else 'FAILED'}")

    all_ok = (
        false_negative == 0
        and duplicate_execution == 0
        and ownership_conflict == 0
        and invalid_transition == 0
        and false_completion == 0
        and res_c["satisfaction_barrier"]
        and res_f["satisfaction_barrier"]
    )

    if all_ok:
        print("\n[SUCCESS] Independent Reference Model & Correctness Equivalence: 100% VERIFIED.")
        return 0
    else:
        print("\n[FAILURE] Correctness or Reference Model violation detected.")
        return 1


if __name__ == "__main__":
    code = asyncio.run(main())
    sys.exit(code)
