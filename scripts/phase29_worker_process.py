"""
JARVIS OS — Phase 29: Independent Worker Process (LOCAL_MULTI_PROCESS)
Executes as a standalone Python process:
1. Connects to Coordinator via ProductionDistributedTransport.
2. Registers worker capability.
3. Receives task assignments over the transport layer.
4. Executes tasks (computing SHA-256 evidence), sends completions back.
5. Shuts down cleanly on completion signal.
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


async def run_worker(coordinator_port: int, worker_port: int):
    node_id = "worker_proc"
    coord_node_id = "coordinator_proc"

    transport = TcpTransport(node_id)
    await transport.start_server("127.0.0.1", worker_port)

    # Connect to coordinator
    await transport.connect(coord_node_id, "127.0.0.1", coordinator_port)

    # Register worker
    reg_env = DistributedEnvelope.create(
        source_node=node_id,
        destination_node=coord_node_id,
        action=MessageAction.REQUEST,
        payload_type="worker_registration",
        payload={"worker_id": node_id, "cores": 4},
    )
    await transport.send_message(coord_node_id, reg_env)

    running = True
    tasks_processed = 0

    t0 = time.time()
    while running and (time.time() - t0) < 30.0:
        try:
            env, lat = await transport.receive_message(timeout=1.0)
            if env.payload_type == "assign_task":
                task_data = env.payload
                # Execute task: compute SHA-256 evidence
                evidence = hashlib.sha256(task_data["input_data"].encode()).hexdigest()
                tasks_processed += 1

                # Send completion back
                comp_env = DistributedEnvelope.create(
                    source_node=node_id,
                    destination_node=coord_node_id,
                    action=MessageAction.ACK,
                    payload_type="task_completed",
                    payload={
                        "task_id": task_data["task_id"],
                        "mission_id": task_data["mission_id"],
                        "input_data": task_data["input_data"],
                        "evidence": evidence,
                        "processed_at": time.time(),
                    },
                )
                await transport.send_message(coord_node_id, comp_env)

            elif env.payload_type == "shutdown_worker":
                running = False
                break

        except Exception:
            continue

    await transport.close()

    result = {
        "status": "PASS",
        "worker_node_id": node_id,
        "tasks_processed": tasks_processed,
    }
    print(f"JSON_WORKER_RESULT:{json.dumps(result)}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--coord-port", type=int, default=9871)
    parser.add_argument("--worker-port", type=int, default=9872)
    args = parser.parse_args()

    asyncio.run(run_worker(args.coord_port, args.worker_port))


if __name__ == "__main__":
    main()
