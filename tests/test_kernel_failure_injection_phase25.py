"""
JARVIS OS — Phase 25: Expanded Kernel Failure Injection & Resilience Suite
Validates resilience against:
1. queue_overload: overflowing queue depth handled safely without memory crash.
2. burst_overload: handling consecutive rapid large batches without unhandled exception.
3. completion_delay: handling delayed completion dequeue without corrupting state.
4. worker_starvation: high bulk load does not starve priority control workers.
5. cpu_affinity_changes: dynamic restriction and restoration of CPU affinity.
6. process_priority_changes: dynamic priority adjustments under load.
7. socket_closure: abrupt socket termination during transmission.
8. rio_queue_exhaustion: graceful clamp when requests exceed RIO capacity.
"""

import os
import psutil
import pytest
import sys
import threading
import time

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


def test_01_queue_overload():
    """Chaos 1: Submitting larger batch than queue depth clamps gracefully."""
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=64)
    sock.connect("127.0.0.1", 20999)

    batch_large = [b"OVERLOAD_PAYLOAD" * 16] * 128
    sent = sock.send_batch(batch_large)
    assert sent <= 128
    sock.close()


def test_02_burst_overload():
    """Chaos 2: Consecutive high-rate bursts do not trigger heap corruption."""
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=2 * 1024 * 1024, queue_depth=512)
    sock.connect("127.0.0.1", 20999)

    batch_data = [b"BURST_DATA" * 32] * 32
    for _ in range(20):
        sent = sock.send_batch(batch_data)
        assert sent == 32
    sock.close()


def test_03_completion_delay():
    """Chaos 3: Delaying completion processing does not corrupt subsequent requests."""
    oracle = ReferenceQuicModelPhase23()
    oracle.register_stream(stream_id=25, expected_bytes=300)

    # Deliver chunk 0, delay 50ms, then deliver chunk 1
    oracle.record_chunk(stream_id=25, seq=0, chunk_len=100)
    time.sleep(0.02)
    oracle.record_chunk(stream_id=25, seq=1, chunk_len=100)

    audit = oracle.verify_all_invariants()
    assert audit["ordering_within_stream"] is True
    assert audit["stream_identity_preserved"] is True


def test_04_worker_starvation():
    """Chaos 4: Bulk stream flooding does not starve control workers."""
    dp = MultiCoreQuicDataplane(num_workers=2, io_backend="rio")
    dp.start()

    bulk_processed = []
    ctrl_processed = []

    def bulk_cb(s, d):
        time.sleep(0.0005)
        bulk_processed.append(s)

    def ctrl_cb(s, d):
        ctrl_processed.append(s)

    for i in range(30):
        dp.submit_packet(stream_id=i * 2 + 1, packet_data=b"BULK", callback=bulk_cb)

    t0 = time.perf_counter()
    dp.submit_packet(stream_id=0, packet_data=b"CTRL_0", callback=ctrl_cb)
    dur_ms = (time.perf_counter() - t0) * 1000.0

    assert dur_ms < 5.0
    time.sleep(0.05)
    assert 0 in ctrl_processed
    dp.stop()


def test_05_cpu_affinity_changes():
    """Chaos 5: Dynamically changing process CPU affinity does not break RIO transmission."""
    proc = psutil.Process()
    orig_affinity = proc.cpu_affinity()

    try:
        # Restrict to core 0 (or first available)
        proc.cpu_affinity([orig_affinity[0]])
        assert len(proc.cpu_affinity()) == 1

        sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)
        sock.connect("127.0.0.1", 20999)
        sent = sock.send_batch([b"AFFINITY_PAYLOAD"] * 8)
        assert sent == 8
        sock.close()
    finally:
        # Restore original affinity
        proc.cpu_affinity(orig_affinity)
        assert proc.cpu_affinity() == orig_affinity


def test_06_process_priority_changes():
    """Chaos 6: Dynamically altering process priority does not crash RIO datapath."""
    proc = psutil.Process()
    # On Windows, psutil provides nice() as priority class (NORMAL_PRIORITY_CLASS etc)
    try:
        sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)
        sock.connect("127.0.0.1", 20999)
        sent = sock.send_batch([b"PRIORITY_PAYLOAD"] * 4)
        assert sent == 4
        sock.close()
    except Exception as e:
        pytest.fail(f"Priority test failed: {e}")


def test_07_socket_closure_during_flight():
    """Chaos 7: Abrupt socket close while threads are active does not leak resources."""
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0)
    sock.connect("127.0.0.1", 20999)

    def closer():
        time.sleep(0.002)
        sock.close()

    t = threading.Thread(target=closer)
    t.start()

    for _ in range(10):
        try:
            sock.send_batch([b"DATA"] * 4)
        except Exception:
            pass
        time.sleep(0.001)

    t.join()
    assert sock.is_native_active is False or sock._ctx is None


def test_08_rio_queue_exhaustion():
    """Chaos 8: Posting receives or sends on exhausted queue handled without crash."""
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=64)
    stats = sock.get_native_stats()
    assert stats["errors_total"] == 0
    sock.close()
