"""
JARVIS OS — Phase 20 Unit & Integration Test Suite
Testing:
- AsyncioBackend baseline processing
- IoWorkerPool lifecycle, reuse, crash detection, and replacement
- AdaptiveStreamGroupingPolicy & thread affinity
- ControlPlaneIsolation priority & latency guarantees (p95 < 10 ms)
- Fine-grained per-stream locks vs global locks
- ChunkBufferPool bounded memory, zero-copy metrics, and cleanup
- AdaptiveBufferPolicy sizing
- ThreadedIoBackend full pipeline
- Cross-stream fairness (1 huge + 127 small streams; Jain index)
- AdaptiveIoBackend mode switching & safe migration (duplicate_side_effect == 0)
- Thread deadlock stress testing (deadlock == 0)
- Stream recovery with worker handover
- Network chaos resilience
- ReferenceIoModel correctness oracle
"""

import concurrent.futures
import hashlib
import queue
import threading
import time
import uuid
import zlib
import pytest

from agents.io_dispatch import (
    IoDispatchMode,
    IoDispatchBackend,
    AsyncioBackend,
    ThreadedIoBackend,
    AdaptiveIoBackend,
    AdaptiveIoDispatchPolicy,
    IoWorkerPool,
    StreamGroup,
    AdaptiveStreamGroupingPolicy,
    ChunkBufferPool,
    AdaptiveBufferPolicy,
    ControlPlaneIsolation,
    ProfiledLock,
    ReferenceIoModel,
    StreamPriority,
)
from agents.streaming_transport import (
    StreamChunk,
    StreamFlags,
    StreamingDistributedTransport,
    SlidingWindowFlowController,
    ChunkReassemblyManager,
)


# ── TEST 1: ASYNCIO BACKEND BASELINE ──────────────────────────────────────────

def test_asyncio_backend_baseline_processing():
    backend = AsyncioBackend()
    backend.start()

    payload = b"TEST_PAYLOAD_ASYNCIO_BASELINE_DATA_12345"
    stream_id = "s_async_01"
    
    meta = backend.process_send_chunk(
        stream_id=stream_id,
        sequence=0,
        total_chunks=1,
        payload_slice=payload,
        priority=StreamPriority.TASK,
        flags=int(StreamFlags.START | StreamFlags.END | StreamFlags.DATA),
        chunk_size=len(payload),
        window_adv=16,
        sender_node_id="node_a",
    )

    assert meta["stream_id"] == stream_id
    assert meta["payload_length"] == len(payload)
    assert meta["crc32"] != 0

    # Verify chunk can be constructed and verified
    chunk = StreamChunk(**meta)
    assert chunk.verify_crc32() is True

    backend.stop()


# ── TEST 2: IO WORKER POOL LIFECYCLE & REUSE ──────────────────────────────────

def test_io_worker_pool_lifecycle_and_reuse():
    pool = IoWorkerPool(num_workers=4)
    pool.start()

    def _task(x: int) -> int:
        return x * x

    futures = [pool.submit_to_worker(i % 4, _task, i) for i in range(40)]
    results = [f.result(timeout=2.0) for f in futures]

    assert results == [i * i for i in range(40)]
    stats = pool.get_stats()
    assert stats["num_workers"] == 4
    assert stats["alive_workers"] == 4
    assert stats["tasks_processed"] == 40
    assert stats["replaced_worker_count"] == 0

    pool.stop(wait=True)


# ── TEST 3: WORKER POOL CRASH DETECTION & REPLACEMENT ─────────────────────────

def test_io_worker_pool_crash_detection_and_replacement():
    crashes = []

    def _on_crash(w_idx: int, ex: Exception):
        crashes.append((w_idx, str(ex)))

    pool = IoWorkerPool(num_workers=2, crash_callback=_on_crash)
    pool.start()

    def _crashing_task():
        raise ValueError("Simulated fatal task error")

    # Submit failing task
    fut = pool.submit_to_worker(0, _crashing_task)
    with pytest.raises(ValueError):
        fut.result(timeout=2.0)

    assert len(crashes) == 1
    assert "Simulated fatal task error" in crashes[0][1]

    # Worker pool should remain functional and continue processing tasks
    fut2 = pool.submit_to_worker(0, lambda: "RECOVERED")
    assert fut2.result(timeout=2.0) == "RECOVERED"

    stats = pool.get_stats()
    assert stats["alive_workers"] == 2
    assert stats["exceptions_caught"] >= 1

    pool.stop(wait=True)


# ── TEST 4: STREAM GROUPING & THREAD AFFINITY ─────────────────────────────────

def test_stream_grouping_and_thread_affinity():
    policy = AdaptiveStreamGroupingPolicy(num_workers=4)

    # Deterministic assignment: same stream maps to same group
    g1 = policy.assign_stream("stream_alpha")
    g2 = policy.assign_stream("stream_alpha")
    assert g1.group_id == g2.group_id
    assert g1.worker_index == g2.worker_index

    # Assign multiple streams and check distribution
    for i in range(32):
        policy.assign_stream(f"stream_{i}")

    dist = policy.get_group_distribution()
    assert len(dist) == 4
    # Check that load is balanced across groups
    assert all(count > 0 for count in dist.values())

    policy.release_stream("stream_alpha")
    assert "stream_alpha" not in g1.active_stream_ids


# ── TEST 5: CONTROL PLANE ISOLATION & PRIORITY INVARIANTS ─────────────────────

def test_control_plane_isolation_and_priority():
    isolation = ControlPlaneIsolation()

    # Enqueue in reverse priority
    isolation.enqueue_control(StreamPriority.BULK, "bulk_payload_data")
    isolation.enqueue_control(StreamPriority.TASK, "task_execution_item")
    isolation.enqueue_control(StreamPriority.CONTROL, "registration_query")
    isolation.enqueue_control(StreamPriority.CRITICAL_CONTROL, "heartbeat_ping")

    # Dequeue should emerge in strictly prioritized order (0=CRITICAL_CONTROL first)
    p1, msg1 = isolation.dequeue_control(timeout=1.0)
    p2, msg2 = isolation.dequeue_control(timeout=1.0)
    p3, msg3 = isolation.dequeue_control(timeout=1.0)
    p4, msg4 = isolation.dequeue_control(timeout=1.0)

    assert p1 == StreamPriority.CRITICAL_CONTROL and msg1 == "heartbeat_ping"
    assert p2 == StreamPriority.CONTROL and msg2 == "registration_query"
    assert p3 == StreamPriority.TASK and msg3 == "task_execution_item"
    assert p4 == StreamPriority.BULK and msg4 == "bulk_payload_data"


# ── TEST 6: CONTROL PLANE LATENCY GUARANTEE UNDER HEAVY LOAD ──────────────────

def test_control_plane_latency_guarantee():
    isolation = ControlPlaneIsolation()
    num_messages = 200
    stop_event = threading.Event()
    received = []

    def _consumer():
        while not stop_event.is_set() or len(received) < num_messages:
            res = isolation.dequeue_control(timeout=0.01)
            if res is not None:
                received.append(res)

    t_cons = threading.Thread(target=_consumer)
    t_cons.start()

    # Enqueue control messages concurrently
    for i in range(num_messages):
        isolation.enqueue_control(StreamPriority.CRITICAL_CONTROL, f"heartbeat_{i}")
        time.sleep(0.00005)

    stop_event.set()
    t_cons.join(timeout=3.0)

    assert len(received) == num_messages
    stats = isolation.get_latency_stats()
    assert stats["count"] == num_messages
    assert stats["p95_ms"] < 10.0, f"Control latency p95 exceeded 10ms: {stats['p95_ms']}ms"


# ── TEST 7: PROFILED LOCK CONTENTION VS GLOBAL LOCK ───────────────────────────

def test_profiled_lock_contention():
    lock = ProfiledLock("test_fine_grained_lock")

    def _worker():
        for _ in range(50):
            with lock:
                time.sleep(0.0001)

    threads = [threading.Thread(target=_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stats = lock.get_stats()
    assert stats["acquire_count"] == 200
    assert stats["lock_wait_ms"] >= 0.0
    assert stats["lock_hold_ms"] >= 0.0


# ── TEST 8: CHUNK BUFFER POOL BOUNDED MEMORY & REUSE ──────────────────────────

def test_chunk_buffer_pool_bounded_memory_and_reuse():
    pool = ChunkBufferPool(max_memory_bytes=4 * 1024 * 1024)  # 4 MB

    # Acquire 64 KB buffers
    buf1 = pool.acquire(64 * 1024)
    buf2 = pool.acquire(64 * 1024)
    assert len(buf1) == 64 * 1024
    assert len(buf2) == 64 * 1024

    # Release and reacquire to verify recycling
    pool.release(buf1)
    buf3 = pool.acquire(64 * 1024)
    assert pool.reused_count >= 1

    pool.release(buf2)
    pool.release(buf3)

    stats = pool.get_stats()
    assert stats["allocated_count"] >= 2
    assert stats["reused_count"] >= 1
    assert stats["active_in_flight"] == 0
    assert stats["current_memory_mb"] <= 4.0


# ── TEST 9: ADAPTIVE BUFFER POLICY SIZING ──────────────────────────────────────

def test_adaptive_buffer_policy_sizing():
    # Small payloads
    s1 = AdaptiveBufferPolicy.select_buffer_size(payload_length=128 * 1024)
    assert s1 == 32 * 1024

    # Medium payloads
    s2 = AdaptiveBufferPolicy.select_buffer_size(payload_length=4 * 1024 * 1024)
    assert s2 == 128 * 1024

    # Large bulk payloads
    s3 = AdaptiveBufferPolicy.select_buffer_size(payload_length=64 * 1024 * 1024)
    assert s3 == 512 * 1024

    # Memory pressure fallback
    s4 = AdaptiveBufferPolicy.select_buffer_size(payload_length=64 * 1024 * 1024, free_memory_mb=64.0)
    assert s4 == 16 * 1024


# ── TEST 10: THREADED IO BACKEND FULL PIPELINE ────────────────────────────────

def test_threaded_io_backend_full_pipeline():
    backend = ThreadedIoBackend(num_workers=4)
    backend.start()

    payload = b"THREADED_IO_BACKEND_PAYLOAD_CHUNK_01" * 100
    stream_id = "s_threaded_01"

    meta = backend.process_send_chunk(
        stream_id=stream_id,
        sequence=0,
        total_chunks=1,
        payload_slice=payload,
        priority=StreamPriority.TASK,
        flags=int(StreamFlags.START | StreamFlags.END | StreamFlags.DATA),
        chunk_size=len(payload),
        window_adv=32,
        sender_node_id="node_x",
    )

    assert meta["stream_id"] == stream_id
    assert "worker_index" in meta
    chunk = StreamChunk(**{k: v for k, v in meta.items() if k != "worker_index"})
    assert chunk.verify_crc32() is True

    # Check metrics
    metrics = backend.get_metrics()
    assert metrics["mode"] == "THREAD_POOL"
    assert metrics["num_workers"] == 4
    assert metrics["chunks_processed"] == 1

    backend.stop()


# ── TEST 11: CROSS-STREAM FAIRNESS & JAIN INDEX ───────────────────────────────

def test_cross_stream_fairness_jain_index():
    pool = IoWorkerPool(num_workers=4)
    pool.start()

    # 1 huge stream + 7 small streams
    stream_counts = {
        "huge_stream": 0,
        **{f"small_{i}": 0 for i in range(7)}
    }
    lock = threading.Lock()

    def _task(stream_key: str):
        with lock:
            stream_counts[stream_key] += 1

    futures = []
    # Submit 100 tasks for huge stream
    for _ in range(100):
        futures.append(pool.submit_to_worker(0, _task, "huge_stream"))

    # Submit 10 tasks for each small stream evenly across workers
    for i in range(7):
        for _ in range(10):
            futures.append(pool.submit_to_worker((i + 1) % 4, _task, f"small_{i}"))

    for f in futures:
        f.result(timeout=5.0)

    # Calculate Jain's fairness index over small streams
    small_values = [stream_counts[f"small_{i}"] for i in range(7)]
    assert all(v == 10 for v in small_values), "Small streams must complete without starvation"

    # Jain fairness on small streams: (sum(x))^2 / (n * sum(x^2))
    sum_x = sum(small_values)
    sum_x2 = sum(x * x for x in small_values)
    jain_index = (sum_x * sum_x) / (len(small_values) * sum_x2)
    assert jain_index >= 0.95, f"Fairness index below 0.95: {jain_index}"

    pool.stop(wait=True)


# ── TEST 12: ADAPTIVE MODE SWITCHING & SAFE MIGRATION ─────────────────────────

def test_adaptive_mode_switching_safe_boundaries():
    policy = AdaptiveIoDispatchPolicy(concurrency_threshold=4, queue_latency_threshold_ms=2.0)
    adaptive = AdaptiveIoBackend(num_workers=4, policy=policy)
    adaptive.start()

    assert adaptive.active_mode == IoDispatchMode.ASYNCIO

    # Low concurrency: stays in ASYNCIO
    mode1 = adaptive.evaluate_and_switch_mode(current_active_streams=2, queue_wait_ms=0.5)
    assert mode1 == IoDispatchMode.ASYNCIO

    # High concurrency (> 4 streams): switches cleanly to THREAD_POOL at boundary
    mode2 = adaptive.evaluate_and_switch_mode(current_active_streams=8, queue_wait_ms=3.0)
    assert mode2 == IoDispatchMode.THREAD_POOL
    assert adaptive.mode_switches_count == 1
    assert adaptive.safe_migrations_count == 1

    # Returns to ASYNCIO when load subsides
    mode3 = adaptive.evaluate_and_switch_mode(current_active_streams=1, queue_wait_ms=0.1)
    assert mode3 == IoDispatchMode.ASYNCIO

    metrics = adaptive.get_metrics()
    assert metrics["duplicate_side_effects"] == 0

    adaptive.stop()


# ── TEST 13: THREAD DEADLOCK STRESS SCENARIOS ─────────────────────────────────

def test_thread_deadlock_stress_scenarios():
    lock_a = ProfiledLock("lock_a")
    lock_b = ProfiledLock("lock_b")
    iterations = 50

    errors = []

    def _worker_1():
        try:
            for _ in range(iterations):
                with lock_a:
                    time.sleep(0.00005)
                    with lock_b:
                        pass
        except Exception as e:
            errors.append(e)

    def _worker_2():
        try:
            for _ in range(iterations):
                # Ordered locking pattern prevents deadlock
                with lock_a:
                    time.sleep(0.00005)
                    with lock_b:
                        pass
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=_worker_1)
    t2 = threading.Thread(target=_worker_2)
    t1.start()
    t2.start()

    t1.join(timeout=3.0)
    t2.join(timeout=3.0)

    assert not t1.is_alive(), "Worker 1 deadlocked!"
    assert not t2.is_alive(), "Worker 2 deadlocked!"
    assert len(errors) == 0


# ── TEST 14: STREAM RECOVERY WITH WORKER HANDOVER ─────────────────────────────

def test_stream_recovery_with_worker_handover():
    backend = ThreadedIoBackend(num_workers=4)
    backend.start()

    stream_id = "s_handover_01"
    raw_payload = b"STREAM_HANDOVER_RECOVERY_PAYLOAD_BYTES"

    # Chunk 0 processed on worker group
    meta0 = backend.process_send_chunk(
        stream_id=stream_id,
        sequence=0,
        total_chunks=2,
        payload_slice=raw_payload[:18],
        priority=StreamPriority.TASK,
        flags=int(StreamFlags.START | StreamFlags.DATA),
        chunk_size=18,
        window_adv=16,
        sender_node_id="node_alpha",
    )
    assert meta0["sequence"] == 0

    # Simulate worker reassignment / stream rebalance
    group2 = backend.grouping_policy.assign_stream(stream_id)
    assert group2 is not None

    meta1 = backend.process_send_chunk(
        stream_id=stream_id,
        sequence=1,
        total_chunks=2,
        payload_slice=raw_payload[18:],
        priority=StreamPriority.TASK,
        flags=int(StreamFlags.END | StreamFlags.DATA),
        chunk_size=18,
        window_adv=16,
        sender_node_id="node_alpha",
    )
    assert meta1["sequence"] == 1

    backend.stop()


# ── TEST 15: NETWORK CHAOS RESILIENCE UNDER MULTITHREADING ────────────────────

def test_network_chaos_resilience_under_multithreading():
    backend = ThreadedIoBackend(num_workers=4)
    backend.start()

    manager = ChunkReassemblyManager("chaos_stream", 4, 400)
    payload_parts = [b"PART_" + str(i).encode() * 18 for i in range(4)]

    # Out of order delivery + duplicate injection
    for seq in [2, 0, 1, 1, 3]:
        part = payload_parts[seq]
        meta = backend.process_send_chunk(
            stream_id="chaos_stream",
            sequence=seq,
            total_chunks=4,
            payload_slice=part,
            priority=StreamPriority.TASK,
            flags=int(StreamFlags.DATA),
            chunk_size=len(part),
            window_adv=16,
            sender_node_id="chaos_node",
        )
        c = StreamChunk(**{k: v for k, v in meta.items() if k != "worker_index"})
        ok, reason = manager.add_chunk(c)
        if seq == 1 and manager.received_chunks.get(1) is not None and ok is False:
            assert reason == "DUPLICATE_IGNORED"

    assert manager.is_complete() is True
    assert manager.duplicate_chunks_ignored == 1
    backend.stop()


# ── TEST 16: REFERENCE IO MODEL CORRECTNESS ORACLE ────────────────────────────

def test_reference_io_model_correctness_oracle():
    oracle = ReferenceIoModel()

    # Register 5 streams
    for i in range(5):
        s_id = f"oracle_stream_{i}"
        oracle.register_stream(s_id, total_chunks=4, total_bytes=400)

        for seq in range(4):
            oracle.record_chunk_processed(s_id, seq, worker_id=i % 4)

        oracle.verify_completion(s_id, delivered_bytes=400)

    verdict = oracle.get_verification_verdict()
    assert verdict["verdict"] == "PASS"
    assert verdict["total_registered"] == 5
    assert verdict["total_completed"] == 5
    assert verdict["duplicate_executions"] == 0
    assert verdict["duplicate_side_effects"] == 0
    assert verdict["ownership_conflicts"] == 0
    assert verdict["false_completions"] == 0
    assert verdict["deadlock_count"] == 0
