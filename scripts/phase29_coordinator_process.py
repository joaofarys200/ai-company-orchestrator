"""
JARVIS OS — Phase 29: Independent Coordinator Process (LOCAL_MULTI_PROCESS)
Executes as a standalone Python process:
1. Initializes ProductionDistributedTransport on a dedicated port.
2. Waits for Worker registration.
3. Submits WorkPackage tasks over the transport layer.
4. Receives task results, verifies SHA-256 evidence, and saves Checkpoint.
5. Emits structured JSON summary to stdout.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.distributed_transport import (
    DistributedEnvelope,
    MessageAction,
    ProductionDistributedTransport,
    TcpTransport,
)


async def run_coordinator(port: int, num_tasks: int):
    node_id = "coordinator_proc"
    worker_node_id = "worker_proc"
    mission_id = f"mission_proc_{int(time.time())}"

    transport = TcpTransport(node_id)
    await transport.start_server("127.0.0.1", port)

    # Signal that server is listening by printing READY
    print(f"COORDINATOR_LISTENING:{port}", flush=True)

    completed_tasks = []
    received_results = {}
    checkpoint_hash = ""

    # Wait for worker registration
    t0 = time.time()
    while len(completed_tasks) < num_tasks and (time.time() - t0) < 30.0:
        try:
            env, lat = await transport.receive_message(timeout=1.0)
            if env.payload_type == "worker_registration":
                # Submit tasks to worker
                for i in range(num_tasks):
                    task_id = f"task_{mission_id}_{i+1}"
                    task_env = DistributedEnvelope.create(
                        source_node=node_id,
                        destination_node=worker_node_id,
                        action=MessageAction.REQUEST,
                        payload_type="assign_task",
                        payload={
                            "task_id": task_id,
                            "mission_id": mission_id,
                            "task_index": i,
                            "input_data": f"INPUT_DATA_PAYLOAD_{i}",
                        },
                    )
                    await transport.send_message(worker_node_id, task_env)

            elif env.payload_type == "task_completed":
                payload = env.payload
                t_id = payload["task_id"]
                evidence = payload["evidence"]
                expected = hashlib.sha256(payload["input_data"].encode()).hexdigest()
                assert evidence == expected, f"Evidence mismatch: {evidence} != {expected}"
                received_results[t_id] = evidence
                completed_tasks.append(t_id)

        except Exception:
            continue

    # Create checkpoint
    ch_raw = f"{mission_id}:{sorted(completed_tasks)}"
    checkpoint_hash = hashlib.sha256(ch_raw.encode()).hexdigest()

    # Send shutdown to worker
    try:
        shut_env = DistributedEnvelope.create(
            source_node=node_id,
            destination_node=worker_node_id,
            action=MessageAction.REQUEST,
            payload_type="shutdown_worker",
            payload={"checkpoint": checkpoint_hash},
        )
        await transport.send_message(worker_node_id, shut_env)
    except Exception:
        pass

    await transport.close()

    result = {
        "status": "PASS" if len(completed_tasks) == num_tasks else "FAIL",
        "execution_mode": "LOCAL_MULTI_PROCESS",
        "mission_id": mission_id,
        "tasks_assigned": num_tasks,
        "tasks_completed": len(completed_tasks),
        "checkpoint_sha256": checkpoint_hash,
        "duration_sec": round(time.time() - t0, 3),
    }
    print(f"JSON_RESULT:{json.dumps(result)}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9871)
    parser.add_argument("--tasks", type=int, default=5)
    args = parser.parse_args()

    asyncio.run(run_coordinator(args.port, args.tasks))


if __name__ == "__main__":
    main()
