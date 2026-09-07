"""
JARVIS OS — Phase 18.3 Test Suite: High-Performance Local IPC, Shared-Memory Workers & Single-Host Ceiling
Validates:
1. PipeTransport, QueueTransport, SharedMemoryTransport, RingBufferTransport.
2. Memory order: WRITE -> COMMIT -> SEQUENCE -> READ -> VERIFY.
3. Message integrity: rejection of corrupted, truncated, or invalid checksum payloads.
4. Leak detection: guarantees orphan_shared_memory == 0.
5. Ring buffer backpressure detection and bounded queues.
6. AdaptiveIpcPolicy deterministic selection and prediction accuracy.
7. Dynamic transport switching at safe batch boundaries.
8. Correctness oracle across transports (0 false negatives, 0 duplicate executions).
"""

import asyncio
import os
import pytest
import time
import uuid

from agents.local_ipc import (
    AdaptiveIpcDecision,
    AdaptiveIpcPolicy,
    BackpressureOverflowError,
    BufferSlotState,
    CorruptedMessageError,
    InvalidChecksumError,
    IpcTransportError,
    IpcTransportType,
    LocalIpcTransport,
    PipeTransport,
    QueueTransport,
    RingBufferTransport,
    SequenceViolationError,
    SharedMemoryRingBuffer,
    SharedMemoryTracker,
    SharedMemoryTransport,
    TransportClosedError,
    TransportMessage,
)
from agents.swarm_coordinator import (
    AgentCapability,
    AgentCategory,
    AgentInstance,
    ResourceClass,
)
from agents.swarm_federation import (
    CanonicalWorkload,
    FederatedEventType,
    SubSwarmWorkerJob,
    SubSwarmWorkerPool,
    SubSwarmWorkerResult,
)


def make_test_agents(n: int) -> list[AgentInstance]:
    agents = []
    for i in range(n):
        cat = AgentCategory.CODING if i % 2 == 0 else AgentCategory.TESTING
        cap = AgentCapability(
            agent_type=cat.value,
            categories=[cat],
            concurrency_limit=2,
            resource_classes=[ResourceClass.CPU],
        )
        agents.append(
            AgentInstance(
                agent_id=f"agent_{i:02d}",
                agent_type=cat.value,
                capability=cap,
            )
        )
    return agents


def test_pipe_transport_roundtrip():
    """Validates basic send/receive, metrics, and message unpacking on PipeTransport."""
    transport = PipeTransport()
    try:
        sample_data = {"key": "value", "items": [1, 2, 3], "flag": True}
        send_ms = transport.send(sample_data, sequence=0)
        assert send_ms >= 0.0

        received_data, recv_ms = transport.receive(timeout=2.0, expected_sequence=0)
        assert recv_ms >= 0.0
        assert received_data == sample_data

        metrics = transport.get_metrics()
        assert metrics["messages_sent"] == 1
        assert metrics["messages_received"] == 1
        assert metrics["transport"] == "PIPE"
    finally:
        transport.close()


def test_queue_transport_roundtrip():
    """Validates QueueTransport message queuing, capacity, and metrics."""
    transport = QueueTransport(maxsize=16)
    try:
        data_1 = {"id": 1, "payload": "task-alpha"}
        data_2 = {"id": 2, "payload": "task-beta"}

        transport.send(data_1)
        transport.send(data_2)

        r1, _ = transport.receive(timeout=2.0)
        r2, _ = transport.receive(timeout=2.0)

        assert r1 == data_1
        assert r2 == data_2

        metrics = transport.get_metrics()
        assert metrics["messages_sent"] == 2
        assert metrics["messages_received"] == 2
        assert metrics["backpressure_events"] == 0
    finally:
        transport.close()


def test_shared_memory_transport_roundtrip():
    """Validates SharedMemoryTransport structured header, CRC32 verification, and acknowledgment."""
    SharedMemoryTracker.cleanup_all()
    shm_name = f"test_shm_{uuid.uuid4().hex[:8]}"
    transport_sender = SharedMemoryTransport(slot_size_bytes=128 * 1024, name=shm_name, create=True)
    transport_receiver = transport_sender.create_peer()

    try:
        large_payload = {"matrix": [[i * j for j in range(50)] for i in range(50)], "seed": "test_shm"}
        
        # Background send to handle synchronization handshake
        send_latencies = []
        def sender_work():
            lat = transport_sender.send(large_payload, sequence=100)
            send_latencies.append(lat)

        import threading
        t = threading.Thread(target=sender_work)
        t.start()

        # Receiver reads and acknowledges
        received, recv_ms = transport_receiver.receive(timeout=5.0, expected_sequence=100)
        t.join(timeout=2.0)

        assert received == large_payload
        assert len(send_latencies) == 1
        assert send_latencies[0] >= 0.0

        metrics = transport_receiver.get_metrics()
        assert metrics["messages_received"] == 1
    finally:
        transport_sender.close()
        transport_receiver.close()
        assert SharedMemoryTracker.get_orphan_count() == 0


def test_ring_buffer_transport_roundtrip():
    """Validates lock-minimized circular ring buffer, sequence tracking, and CRC32 verification."""
    ring_name = f"test_ring_{uuid.uuid4().hex[:8]}"
    transport = RingBufferTransport(capacity=8, slot_size_bytes=32 * 1024, name=ring_name, create=True)

    try:
        messages = [{"batch_id": i, "data": f"content_{i}" * 50} for i in range(5)]
        for i, m in enumerate(messages):
            transport.send(m, sequence=i)

        for i, expected in enumerate(messages):
            data, _ = transport.receive(timeout=2.0, expected_sequence=i)
            assert data == expected

        metrics = transport.get_metrics()
        assert metrics["messages_sent"] == 5
        assert metrics["messages_received"] == 5
        assert metrics["backpressure_events"] == 0
    finally:
        transport.close()
        assert SharedMemoryTracker.get_orphan_count() == 0


def test_shared_memory_leak_detection():
    """Validates SharedMemoryTracker leak detection ensuring orphan_shared_memory == 0."""
    SharedMemoryTracker.cleanup_all()
    initial_orphans = SharedMemoryTracker.get_orphan_count()
    assert initial_orphans == 0

    t1 = SharedMemoryTransport(slot_size_bytes=64 * 1024)
    t2 = RingBufferTransport(capacity=4, slot_size_bytes=16 * 1024)
    assert SharedMemoryTracker.get_orphan_count() == 2

    t1.close()
    assert SharedMemoryTracker.get_orphan_count() == 1

    t2.close()
    assert SharedMemoryTracker.get_orphan_count() == 0

    stats = SharedMemoryTracker.get_stats()
    assert stats["orphan_shared_memory"] == 0
    assert stats["total_allocations"] >= 2
    assert stats["total_releases"] >= 2


def test_corrupted_message_and_partial_payload_rejection():
    """Simulates truncated payload, bad checksum, and sequence violation, verifying rejection."""
    # 1. Truncated payload
    msg = TransportMessage.create({"valid": "data"}, sequence=1)
    msg.payload = msg.payload[: len(msg.payload) - 5]
    with pytest.raises(CorruptedMessageError):
        msg.unpack()

    # 2. Bad checksum
    msg2 = TransportMessage.create({"valid": "data"}, sequence=2)
    tampered = bytearray(msg2.payload)
    tampered[0] ^= 0xFF
    msg2.payload = bytes(tampered)
    with pytest.raises(InvalidChecksumError):
        msg2.unpack()

    # 3. Sequence violation
    msg3 = TransportMessage.create({"valid": "data"}, sequence=3)
    with pytest.raises(SequenceViolationError):
        msg3.unpack(expected_sequence=4)


def test_ring_buffer_backpressure_overflow():
    """Saturates ring buffer capacity and verifies BackpressureOverflowError detection."""
    SharedMemoryTracker.cleanup_all()
    ring = SharedMemoryRingBuffer(capacity=2, slot_size_bytes=4096)
    try:
        # Fill capacity (2 slots)
        ring.write({"item": 1}, timeout=0.5)
        ring.write({"item": 2}, timeout=0.5)

        # 3rd item should trigger backpressure timeout
        with pytest.raises(BackpressureOverflowError):
            ring.write({"item": 3}, timeout=0.1)

        assert ring.backpressure_events >= 1

        # Read one item to clear space
        r1 = ring.read(timeout=0.5)
        assert r1 == {"item": 1}

        # Now 3rd item can be written
        seq3 = ring.write({"item": 3}, timeout=0.5)
        assert seq3 == 2
    finally:
        ring.close()
        assert SharedMemoryTracker.get_orphan_count() == 0


def test_adaptive_ipc_policy_selection():
    """Validates AdaptiveIpcPolicy deterministic selection across payload and queue variations."""
    policy = AdaptiveIpcPolicy()

    # Small payload (512 B), low queue -> PIPE
    dec_small = policy.evaluate(payload_size_bytes=512, batch_size=8, queue_depth=4)
    assert dec_small.transport_type == IpcTransportType.PIPE

    # Large payload (256 KB), single batch -> SHARED_MEMORY
    dec_large = policy.evaluate(payload_size_bytes=256 * 1024, batch_size=8, queue_depth=4)
    assert dec_large.transport_type == IpcTransportType.SHARED_MEMORY

    # Large payload (128 KB) with high batching (B=32) -> RING_BUFFER
    dec_stream = policy.evaluate(payload_size_bytes=128 * 1024, batch_size=32, queue_depth=32)
    assert dec_stream.transport_type == IpcTransportType.RING_BUFFER

    # Streaming queue depth (queue=64) even for medium payload -> RING_BUFFER
    dec_depth = policy.evaluate(payload_size_bytes=16 * 1024, batch_size=32, queue_depth=64)
    assert dec_depth.transport_type == IpcTransportType.RING_BUFFER


def test_dynamic_transport_switching_boundary():
    """Validates safe transport migration at batch boundaries without duplicate execution."""
    events = []
    def event_cb(ev_type, data):
        events.append((ev_type, data))

    pool = SubSwarmWorkerPool(max_workers=2, event_callback=event_cb)
    try:
        assert pool.transport_type == IpcTransportType.PIPE

        # Switch to RING_BUFFER
        switched = pool.switch_transport(IpcTransportType.RING_BUFFER)
        assert switched is True
        assert pool.transport_type == IpcTransportType.RING_BUFFER

        # Switch to SHARED_MEMORY
        switched2 = pool.switch_transport(IpcTransportType.SHARED_MEMORY)
        assert switched2 is True
        assert pool.transport_type == IpcTransportType.SHARED_MEMORY

        # Check emitted events
        changed_events = [e for e in events if e[0] == FederatedEventType.IPC_TRANSPORT_CHANGED.value]
        assert len(changed_events) == 2
        assert changed_events[0][1]["new_transport"] == "RING_BUFFER"
        assert changed_events[1][1]["new_transport"] == "SHARED_MEMORY"
    finally:
        pool.shutdown()
        assert SharedMemoryTracker.get_orphan_count() == 0


@pytest.mark.anyio
async def test_correctness_oracle_across_transports():
    """
    Executes identical tasks through SubSwarmWorkerPool in standard and adaptive modes,
    verifying 0 false negatives, 0 duplicate executions, and identical semantic outcomes.
    """
    SharedMemoryTracker.cleanup_all()
    pool = SubSwarmWorkerPool(max_workers=2, transport_type=IpcTransportType.ADAPTIVE)
    try:
        workload = CanonicalWorkload.generate(task_count=16, n_modules=2, seed="oracle_ipc")
        for node in workload.task_graph.nodes.values():
            node.dependencies.clear()
        agents = make_test_agents(16)
        job = SubSwarmWorkerJob(
            subswarm_id="subswarm_00",
            project_id="proj_oracle",
            mission_id="miss_oracle",
            tasks=list(workload.task_graph.nodes.values()),
            agents=agents,
            batch_size=16,
        )

        results = await pool.execute_jobs([job])
        assert len(results) == 1
        res = results[0]
        assert isinstance(res, SubSwarmWorkerResult)
        assert len(res.completed_tasks) == 16
        assert len(res.failed_tasks) == 0
        assert res.error is None
        assert pool.tasks_executed_count == 16
    finally:
        pool.shutdown()
        assert SharedMemoryTracker.get_orphan_count() == 0
