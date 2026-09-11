"""
JARVIS OS — Phase 23: Windows Registered I/O (RIO) Unit Test Suite
Validates:
1. Native RIO binding detection and availability.
2. RioRegisteredBufferPool page allocation, slice acquisition, and release.
3. RioSocket creation, address binding, and socket option configuration.
4. RioSocket connect() and peer association.
5. Vectorized send_batch() submission.
6. Expedited control priority bypass for Stream 0 / Stream 2.
7. Graceful socket closure and resource cleanup.
8. Zero-copy buffer reuse rate measurement.
9. ReferenceQuicModelPhase23 invariant verification.
10. Fallback behavior when native RIO is forced inactive.
"""

import os
import sys
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.native_rio_transport import (
    RioNativeBinding,
    RioSocket,
    RioRegisteredBufferPool,
    RioCorrectnessOracle,
)
from agents.quic_native_dataplane import (
    MultiCoreQuicDataplane,
    ReferenceQuicModelPhase23,
    FastBinaryEnvelope,
)
from agents.distributed_transport import TransportType


def test_01_native_binding_detection():
    binding = RioNativeBinding.get_instance()
    assert binding is not None
    # On Windows 11 Enterprise x64 with MSVC, native RIO is supported and loaded
    if os.name == "nt":
        assert binding.available is True


def test_02_buffer_pool_slice_management():
    pool = RioRegisteredBufferPool(buffer_size=1024 * 1024, slice_size=64 * 1024)
    assert pool.total_slices == 16
    assert len(pool.free_slices) == 16

    s1 = pool.acquire_slice()
    s2 = pool.acquire_slice()
    assert s1 is not None and s2 is not None
    assert s1 != s2
    assert pool.buffer_reuse_rate >= 0.0

    pool.release_slice(s1)
    pool.release_slice(s2)
    assert len(pool.free_slices) == 16


def test_03_rio_socket_lifecycle():
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)
    assert sock is not None
    assert sock.bind_port > 0 or sock.is_native_active

    sock.close()
    assert sock._ctx is None
    assert sock.is_native_active is False


def test_04_rio_socket_connect_and_batch_send():
    s_sender = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)
    s_recv = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)

    connected = s_sender.connect("127.0.0.1", s_recv.bind_port)
    assert connected is True

    datagrams = [b"BATCH_PAYLOAD_" + str(i).encode() * 8 for i in range(16)]
    sent = s_sender.send_batch(datagrams)
    assert sent == 16
    assert s_sender.batches_sent == 1
    assert s_sender.packets_sent == 16

    s_sender.close()
    s_recv.close()


def test_05_priority_control_bypass():
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)
    sock.connect("127.0.0.1", 20999)

    ctrl_msg = b"CRITICAL_HEARTBEAT_STREAM_0"
    res = sock.send_priority_control(ctrl_msg)
    assert res is True
    assert sock.control_packets_sent == 1

    sock.close()


def test_06_oracle_phase23_completions_and_reuse():
    oracle = ReferenceQuicModelPhase23()
    oracle.register_stream(stream_id=10, expected_bytes=2400, is_control=False)
    oracle.record_buffer_acquire(slice_idx=3)
    oracle.record_chunk(stream_id=10, seq=0, chunk_len=1200)
    oracle.record_chunk(stream_id=10, seq=1, chunk_len=1200)
    oracle.record_buffer_release(slice_idx=3)

    oracle.record_rio_completion(request_id=1001)
    oracle.record_rio_completion(request_id=1002)

    audit = oracle.verify_all_invariants()
    assert audit["is_valid"] is True
    assert audit["rio_completion_exactly_once"] is True
    assert audit["buffer_reuse_safe"] is True
    assert audit["no_use_after_free"] is True
    assert audit["duplicate_execution"] == 0


def test_07_multicore_dataplane_with_rio_backend():
    dp = MultiCoreQuicDataplane(num_workers=2, io_backend="rio")
    dp.start()

    metrics = dp.get_metrics()
    assert metrics["io_backend"] == "rio"
    assert metrics["num_workers"] == 2

    # Verify packet dispatch
    results = []
    dp.submit_packet(stream_id=8, packet_data=b"RIO_DATA", callback=lambda s, d: results.append((s, d)))
    dp.submit_packet(stream_id=0, packet_data=b"RIO_CTRL", callback=lambda s, d: results.append((s, d)))

    import time
    time.sleep(0.05)
    assert len(results) == 2
    dp.stop()


def test_08_fallback_socket_behavior():
    # Force fallback branch
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, force_fallback=True)
    assert sock.is_native_active is False
    sock.connect("127.0.0.1", 20999)

    batch = [b"FALLBACK_DATAGRAM_" + str(i).encode() for i in range(4)]
    sent = sock.send_batch(batch)
    assert sent == 4
    ctrl_sent = sock.send_priority_control(b"FALLBACK_CTRL")
    assert ctrl_sent is True
    sock.close()


def test_09_adaptive_policy_quic_rio_selection():
    from agents.quic_transport import AdaptiveDistributedTransportPolicy
    policy = AdaptiveDistributedTransportPolicy()

    # Normal conditions -> QUIC
    t1 = policy.select_transport(num_concurrent_streams=256, payload_bytes=1024, loss_rate=0.0)
    assert t1 == TransportType.QUIC

    # prefer_rio -> QUIC_RIO
    t2 = policy.select_transport(num_concurrent_streams=256, payload_bytes=1024, prefer_rio=True)
    if os.name == "nt":
        assert t2 == TransportType.QUIC_RIO

    # High target bandwidth (e.g. 500 MB/s) -> QUIC_RIO
    t3 = policy.select_transport(num_concurrent_streams=512, payload_bytes=1024 * 1024, target_bandwidth_mb_s=500.0)
    if os.name == "nt":
        assert t3 == TransportType.QUIC_RIO

    # Cost prediction for QUIC_RIO should be significantly lower than TCP
    cost_tcp = policy.predict_cost(TransportType.TCP, 1024, 10 * 1024 * 1024, 0.0)
    cost_rio = policy.predict_cost(TransportType.QUIC_RIO, 1024, 10 * 1024 * 1024, 0.0)
    assert cost_rio < cost_tcp
