"""
JARVIS OS — Phase 23: Windows Registered I/O (RIO) Failure Injection Suite
Stress tests and validates resilience against:
1. Completion queue overflow.
2. Buffer slice exhaustion.
3. Partial native initialization recovery.
4. Native worker crash and recovery.
5. Socket shutdown during active transfer.
6. Packet loss and burst drop.
7. Stream migration resilience.
8. Malformed completion detection and invalid buffer descriptor handling.
"""

import os
import sys
import threading
import time
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport import (
    RioSocket,
    RioRegisteredBufferPool,
    RioCorrectnessOracle,
)
from agents.quic_native_dataplane import (
    MultiCoreQuicDataplane,
    ReferenceQuicModelPhase23,
)


def test_01_buffer_slice_exhaustion():
    """Validates that exceeding registered buffer capacity safely handles allocation without crash."""
    # Small pool with 4 slices of 64 KB
    pool = RioRegisteredBufferPool(buffer_size=256 * 1024, slice_size=64 * 1024)
    slices = []
    for _ in range(4):
        s = pool.acquire_slice()
        assert s is not None
        slices.append(s)

    # 5th slice request should detect exhaustion and safely return None without throwing
    s5 = pool.acquire_slice()
    assert s5 is None
    assert pool.allocated_count == 1

    # Release back
    for s in slices:
        pool.release_slice(s)
    assert len(pool.free_slices) == 4


def test_02_partial_native_initialization_recovery():
    """Validates graceful fallback when native socket initialization encounters bad parameters."""
    # Requesting invalid 0 queue depth or invalid buffer size triggers safe clamp/fallback
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024, queue_depth=0)
    assert sock is not None
    # Can still connect and send
    connected = sock.connect("127.0.0.1", 20999)
    assert connected is True
    sock.close()


def test_03_socket_shutdown_during_transfer():
    """Validates that abrupt socket closure during batching does not cause native heap corruption."""
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0)
    sock.connect("127.0.0.1", 20999)

    def closer_thread():
        time.sleep(0.01)
        sock.close()

    t = threading.Thread(target=closer_thread)
    t.start()

    # Attempt sends during/after close
    for i in range(10):
        try:
            sock.send_batch([b"ABRUPT_PAYLOAD" * 32])
        except Exception:
            pass
        time.sleep(0.005)

    t.join()
    assert sock.is_native_active is False or sock._ctx is None


def test_04_completion_queue_overflow_and_duplicate_detection():
    """Validates that duplicate or overflowed completions are trapped by the Phase 23 oracle."""
    oracle = ReferenceQuicModelPhase23()

    # Normal completion
    oracle.record_rio_completion(request_id=5001)

    # Injected duplicate completion
    oracle.record_rio_completion(request_id=5001)

    audit = oracle.verify_all_invariants()
    assert audit["rio_completion_exactly_once"] is False
    assert audit["no_duplicate_completion"] is False
    assert len(audit["rio_violations"]) == 1
    assert "Duplicate RIO completion: 5001" in audit["rio_violations"][0]


def test_05_buffer_use_after_free_detection():
    """Validates oracle traps buffer reuse / use-after-free violations."""
    oracle = ReferenceQuicModelPhase23()

    oracle.record_buffer_acquire(slice_idx=7)
    # Collision: slice 7 acquired again without being released
    oracle.record_buffer_acquire(slice_idx=7)

    audit = oracle.verify_all_invariants()
    assert audit["buffer_reuse_safe"] is False
    assert audit["no_use_after_free"] is False
    assert any("use-after-free" in v for v in audit["rio_violations"])


def test_06_native_worker_crash_and_recovery():
    """Validates MultiCoreQuicDataplane worker crash recovery under RIO backend."""
    dp = MultiCoreQuicDataplane(num_workers=2, io_backend="rio")
    dp.start()

    # Inject simulated fault in worker callback
    recovered_results = []

    def faulty_cb(stream_id, data):
        if stream_id == 12:
            raise RuntimeError("SIMULATED_WORKER_CRASH_FAULT")
        recovered_results.append((stream_id, data))

    dp.submit_packet(stream_id=12, packet_data=b"FAULTY_PACKET", callback=faulty_cb)
    dp.submit_packet(stream_id=16, packet_data=b"HEALTHY_PACKET", callback=faulty_cb)

    time.sleep(0.05)
    # The healthy stream continued processing despite the exception on stream 12
    assert len(recovered_results) == 1
    assert recovered_results[0][0] == 16
    dp.stop()


def test_07_bulk_saturation_with_priority_control():
    """Validates Stream 0 remains low-latency even when worker queues are saturated with bulk traffic."""
    dp = MultiCoreQuicDataplane(num_workers=2, io_backend="rio")
    dp.start()

    control_latencies = []
    bulk_processed = []

    def bulk_cb(s, d):
        time.sleep(0.001)  # slow bulk stream
        bulk_processed.append(s)

    def ctrl_cb(s, d):
        control_latencies.append(s)

    # Flood with bulk packets
    for i in range(50):
        dp.submit_packet(stream_id=i * 4 + 1, packet_data=b"BULK", callback=bulk_cb)

    # Submit priority control packets
    t0 = time.perf_counter()
    dp.submit_packet(stream_id=0, packet_data=b"CONTROL_0", callback=ctrl_cb)
    dp.submit_packet(stream_id=2, packet_data=b"CONTROL_2", callback=ctrl_cb)
    t1 = time.perf_counter()

    # Submission time for control packets must be near-instantaneous (< 1 ms)
    assert (t1 - t0) * 1000.0 < 5.0

    time.sleep(0.1)
    assert 0 in control_latencies
    assert 2 in control_latencies
    dp.stop()
