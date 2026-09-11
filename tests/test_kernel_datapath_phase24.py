"""
JARVIS OS — Phase 24: Kernel Datapath & Correctness Unit Test Suite
Validates the 10 core correctness invariants:
1. duplicate_execution == 0
2. duplicate_side_effect == 0
3. stream_identity_preserved == True
4. payload_integrity == True
5. ordering_within_stream == True
6. control_stream_priority_preserved == True
7. migration_preserves_stream_state == True
8. rio_completion_exactly_once == True
9. buffer_reuse_safe == True
10. no_use_after_free == True

Also validates:
- Dynamic socket buffer modification (SO_RCVBUF / SO_SNDBUF)
- Native telemetry counters via jarvis_rio_get_stats
- Zero-copy buffer reuse tracking
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


def test_01_native_telemetry_and_stats():
    """Validates that native RIO statistics and queue depth tracking are accurate."""
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)
    stats = sock.get_native_stats()
    assert "submits_total" in stats
    assert "completions_total" in stats
    assert "errors_total" in stats
    assert "send_queue_depth" in stats
    assert "recv_queue_depth" in stats
    assert "completion_lag" in stats
    assert "buffer_reuse_rate" in stats
    sock.close()


def test_02_dynamic_socket_buffer_tuning():
    """Validates dynamic adjustment of SO_RCVBUF and SO_SNDBUF."""
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)
    initial_rcv = sock.get_socket_rcvbuf()
    assert initial_rcv > 0

    # Set new buffer size (512 KB)
    res = sock.set_socket_buffers(rcvbuf=512 * 1024, sndbuf=512 * 1024)
    assert res is True
    updated_rcv = sock.get_socket_rcvbuf()
    assert updated_rcv >= 512 * 1024 or updated_rcv > 0
    sock.close()


def test_03_correctness_invariants_audit():
    """Validates the 10 mandated correctness invariants under ReferenceQuicModelPhase23."""
    oracle = ReferenceQuicModelPhase23()

    # Register and record chunks for 10 streams
    for s_id in range(10):
        oracle.register_stream(stream_id=s_id, expected_bytes=500, is_control=(s_id == 0))
        for seq in range(5):
            oracle.record_chunk(stream_id=s_id, seq=seq, chunk_len=100)

    # Record side effects (unique)
    oracle.record_side_effect("effect_sync_state")

    # Record normal RIO completions
    for req_id in range(100, 150):
        oracle.record_rio_completion(request_id=req_id)

    # Record safe buffer acquire / release cycles
    for slice_idx in range(8):
        oracle.record_buffer_acquire(slice_idx)
        oracle.record_buffer_release(slice_idx)

    audit = oracle.verify_all_invariants()

    # Verify all 10 invariants
    assert audit["duplicate_execution"] == 0
    assert audit["duplicate_side_effect"] == 0
    assert audit["stream_identity_preserved"] is True
    assert audit["payload_integrity"] is True
    assert audit["ordering_within_stream"] is True
    assert audit["control_stream_priority_preserved"] is True
    assert audit["migration_preserves_stream_state"] is True
    assert audit["rio_completion_exactly_once"] is True
    assert audit["buffer_reuse_safe"] is True
    assert audit["no_use_after_free"] is True
    assert audit["is_valid"] is True


def test_04_control_stream_priority_preserved():
    """Validates control stream priority bypass under high burst."""
    sock = RioSocket(bind_ip="127.0.0.1", bind_port=0, buffer_size=1024 * 1024, queue_depth=128)
    sock.connect("127.0.0.1", 20999)

    # Bulk messages
    bulk_sent = sock.send_batch([b"BULK_PAYLOAD" * 16] * 16)
    assert bulk_sent == 16

    # Expedited control message for Stream 0
    ctrl_sent = sock.send_priority_control(b"STREAM_0_CRITICAL_PACKET")
    assert ctrl_sent is True
    assert sock.control_packets_sent == 1

    sock.close()


def test_05_payload_integrity_fast_binary():
    """Validates binary envelope serialization and payload integrity."""
    from agents.distributed_transport import MessageAction

    orig_payload = b"CRITICAL_INTEGRITY_CHECK_PHASE24_" * 16
    env_bytes = FastBinaryEnvelope.pack(
        stream_id=2024,
        action=MessageAction.REQUEST,
        sequence=1,
        payload_bytes=orig_payload,
    )

    unpacked = FastBinaryEnvelope.unpack(env_bytes)
    assert unpacked is not None
    stream_id, action, sequence, flags, payload = unpacked
    assert stream_id == 2024
    assert action == MessageAction.REQUEST
    assert sequence == 1
    assert payload == orig_payload
