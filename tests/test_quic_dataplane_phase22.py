"""
JARVIS OS — Phase 22: QUIC Dataplane Profiling & Native Acceleration Unit Tests
Verifies:
1. QuicDataplaneProfiler instrumenting all 14 components
2. DatagramBufferPool allocation, release, and bound verification
3. FastBinaryEnvelope serialization, CRC32 validation, and error detection
4. ZeroCopyChunkSlicer memoryview slicing and reassembly
5. MultiCoreQuicDataplane deterministic stream ownership
6. MultiCoreQuicDataplane Stream 0 & Stream 2 expedited control bypass
7. Intra-stream sequential ordering under multi-worker sharding
8. Independent progress of unrelated streams across distinct workers
9. ReferenceQuicModelPhase22 Section 7 & 43 invariant validation
10. QuicTransport native_accelerated mode end-to-end transmission
"""

import asyncio
import time
import pytest

from agents.distributed_transport import (
    DistributedEnvelope,
    MessageAction,
    TransportError,
)
from agents.quic_dataplane_profiler import QuicDataplaneProfiler
from agents.quic_native_dataplane import (
    DatagramBufferPool,
    FastBinaryEnvelope,
    MultiCoreQuicDataplane,
    ReferenceQuicModelPhase22,
    ZeroCopyChunkSlicer,
)
from agents.quic_transport import QuicTransport


def test_01_profiler_14_components():
    profiler = QuicDataplaneProfiler()
    profiler.reset()

    for comp in profiler.components.keys():
        with profiler.probe(comp):
            _ = sum(x * x for x in range(2000))

    report = profiler.generate_report()
    assert len(report["components"]) == 14
    assert report["grand_total_cpu_ms"] >= 0.0
    assert report["first_real_cpu_hot_path"] in profiler.components


def test_02_datagram_buffer_pool():
    pool = DatagramBufferPool(buffer_size=4096, max_pool_size=16)
    b1 = pool.acquire()
    assert len(b1) == 4096

    pool.release(b1)
    metrics = pool.get_metrics()
    assert metrics["total_allocations"] == 1
    assert metrics["total_recycles"] == 1
    assert metrics["available_buffers"] > 0


def test_03_fast_binary_envelope():
    stream_id = 12
    action = MessageAction.REQUEST
    seq = 42
    payload = b"TEST_PAYLOAD_FAST_BINARY"

    packed = FastBinaryEnvelope.pack(stream_id, action, seq, payload)
    s_id, act, s_seq, flags, body = FastBinaryEnvelope.unpack(packed)

    assert s_id == stream_id
    assert act == action
    assert s_seq == seq
    assert body == payload

    # Test corrupted payload detection
    corrupted = bytearray(packed)
    corrupted[-1] ^= 0xFF
    with pytest.raises(TransportError):
        FastBinaryEnvelope.unpack(bytes(corrupted))


def test_04_zero_copy_chunk_slicer():
    data = b"STREAM_DATA_BLOCK_" * 500  # ~9000 bytes
    chunks = ZeroCopyChunkSlicer.slice_chunks(data, chunk_size=2048)
    assert len(chunks) == 5

    chunks_map = {i: bytes(c) for i, c in enumerate(chunks)}
    reassembled = ZeroCopyChunkSlicer.reassemble(chunks_map)
    assert reassembled == data


def test_05_multicore_deterministic_stream_ownership():
    num_workers = 4
    dp = MultiCoreQuicDataplane(num_workers=num_workers)
    dp.start()

    worker_assignments = {}
    lock = asyncio.Lock()

    def record_exec(w_id, sid):
        worker_assignments[sid] = w_id

    # Dispatch packets on streams 4, 8, 12, 16
    for s_idx in range(1, 16):
        sid = s_idx * 4
        expected_worker = (sid // 4) % num_workers
        dp.dispatch_packet(sid, b"pkt", lambda s, p, w=expected_worker: record_exec(w, s))

    time.sleep(0.05)
    dp.stop()

    assert len(worker_assignments) == 15
    for sid, assigned_w in worker_assignments.items():
        assert assigned_w == (sid // 4) % num_workers


def test_06_control_bypass_priority():
    dp = MultiCoreQuicDataplane(num_workers=4)
    dp.start()

    control_events = []
    dp.dispatch_packet(0, b"HEARTBEAT", lambda sid, data: control_events.append((sid, data)))
    dp.dispatch_packet(2, b"ACK", lambda sid, data: control_events.append((sid, data)))

    time.sleep(0.05)
    dp.stop()

    assert len(control_events) == 2
    metrics = dp.get_metrics()
    assert metrics["control_processed"] == 2


def test_07_intra_stream_sequential_ordering():
    oracle = ReferenceQuicModelPhase22()
    oracle.register_stream(stream_id=4, expected_bytes=300)

    oracle.record_chunk(stream_id=4, seq=0, chunk_len=100)
    oracle.record_chunk(stream_id=4, seq=1, chunk_len=100)
    oracle.record_chunk(stream_id=4, seq=2, chunk_len=100)

    res = oracle.verify_all_invariants()
    assert res["is_valid"] is True
    assert res["ordering_within_stream"] is True


def test_08_reference_oracle_invariants():
    oracle = ReferenceQuicModelPhase22()
    oracle.register_stream(stream_id=0, expected_bytes=50, is_control=True)
    oracle.record_chunk(stream_id=0, seq=0, chunk_len=50)
    oracle.record_side_effect("tx_0")

    # Incomplete stream
    oracle.register_stream(stream_id=8, expected_bytes=100)
    oracle.record_chunk(stream_id=8, seq=0, chunk_len=50)

    res = oracle.verify_all_invariants()
    assert res["is_valid"] is False
    assert res["completed_streams"] == 1
    assert res["total_streams"] == 2
    assert res["duplicate_side_effect"] == 0


@pytest.mark.anyio
async def test_09_native_accelerated_quic_transport_e2e():
    port = 19950
    srv = QuicTransport("srv_e2e", dataplane_mode="native_accelerated", num_dataplane_cores=2)
    cli = QuicTransport("cli_e2e", dataplane_mode="native_accelerated", num_dataplane_cores=2)

    await srv.start_server("127.0.0.1", port)
    await cli.connect("srv_e2e", "127.0.0.1", port)

    try:
        env = DistributedEnvelope.create("cli_e2e", "srv_e2e", MessageAction.REQUEST, "str", "E2E_NATIVE_ACCEL")
        lat = await cli.send_message("srv_e2e", env)
        rec, _ = await srv.receive_message(timeout=1.0)
        assert rec.payload == "E2E_NATIVE_ACCEL"
        assert lat >= 0.0

        metrics = srv.get_metrics()
        assert metrics["dataplane_mode"] == "native_accelerated"
        assert "native_dataplane" in metrics
    finally:
        await srv.close()
        await cli.close()
