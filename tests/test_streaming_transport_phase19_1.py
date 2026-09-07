"""
JARVIS OS — Phase 19.1: Comprehensive Unit & Integration Test Suite
Streaming Transport, Chunking, Windowed Flow Control & Large Payload Resilience
"""

import asyncio
import hashlib
import time
import pytest

from agents.streaming_transport import (
    AdaptiveChunkPolicy,
    ChunkReassemblyManager,
    ReferenceStreamingModel,
    SlidingWindowFlowController,
    StreamCancelledError,
    StreamCheckpoint,
    StreamChunk,
    StreamCorruptedChunkError,
    StreamError,
    StreamFlags,
    StreamPriority,
    StreamingDistributedTransport,
)
from agents.distributed_transport import TcpTransport


# ── TEST 1: STREAM CHUNK SERIALIZATION & CRC32 INTEGRITY ──────────────────────

def test_stream_chunk_serialization_and_crc32():
    payload = b"Hello, Jarvis OS Phase 19.1 Streaming Transport!"
    chunk = StreamChunk(
        message_id="a1b2c3d4e5f60718293a4b5c6d7e8f90",
        stream_id="11223344556677889900aabbccddeeff",
        sequence=0,
        total_chunks=1,
        chunk_size=len(payload),
        payload_length=len(payload),
        crc32=0,
        flags=int(StreamFlags.START | StreamFlags.DATA | StreamFlags.END),
        data=payload,
        priority=StreamPriority.TASK,
        window_advertisement=32,
        sack_ranges=[(0, 0)],
    )
    chunk.crc32 = chunk.compute_crc32()
    assert chunk.verify_crc32() is True

    raw = chunk.serialize()
    restored = StreamChunk.deserialize(raw)

    assert restored.message_id == chunk.message_id
    assert restored.stream_id == chunk.stream_id
    assert restored.sequence == 0
    assert restored.data == payload
    assert restored.priority == StreamPriority.TASK
    assert restored.sack_ranges == [(0, 0)]
    assert restored.verify_crc32() is True


# ── TEST 2: ADAPTIVE CHUNK POLICY SIZING ──────────────────────────────────────

def test_adaptive_chunk_policy_sizing():
    # 64 KB payload -> 16 KB chunks
    assert AdaptiveChunkPolicy.calculate_chunk_size(64 * 1024) == 16 * 1024
    # 512 KB payload -> 64 KB chunks
    assert AdaptiveChunkPolicy.calculate_chunk_size(512 * 1024) == 64 * 1024
    # 4 MB payload -> 128 KB chunks (or 64 KB if high loss)
    assert AdaptiveChunkPolicy.calculate_chunk_size(4 * 1024 * 1024, loss_rate=0.0) == 128 * 1024
    assert AdaptiveChunkPolicy.calculate_chunk_size(4 * 1024 * 1024, loss_rate=0.15) == 32 * 1024
    # 16 MB payload -> 256 KB chunks
    assert AdaptiveChunkPolicy.calculate_chunk_size(16 * 1024 * 1024, loss_rate=0.0) == 256 * 1024
    # 64 MB payload -> 512 KB chunks (or 256 KB if memory < 200MB)
    assert AdaptiveChunkPolicy.calculate_chunk_size(64 * 1024 * 1024, memory_available_mb=1000.0) == 512 * 1024
    assert AdaptiveChunkPolicy.calculate_chunk_size(64 * 1024 * 1024, memory_available_mb=150.0) == 256 * 1024


# ── TEST 3: SLIDING WINDOW FLOW CONTROLLER WITH SACK ──────────────────────────

def test_sliding_window_flow_controller_with_sack():
    controller = SlidingWindowFlowController(initial_window=4, min_window=2, max_window=16)

    chunks = []
    for i in range(8):
        c = StreamChunk(
            message_id=f"msg_{i}",
            stream_id="stream_flow_01",
            sequence=i,
            total_chunks=8,
            chunk_size=1024,
            payload_length=1024,
            crc32=0,
            flags=int(StreamFlags.DATA),
        )
        chunks.append(c)

    # Window is 4: can send 0, 1, 2, 3
    assert controller.can_send() is True
    for i in range(4):
        assert controller.can_send() is True
        controller.record_chunk_sent(chunks[i])
    assert controller.can_send() is False  # In-flight is 4/4

    # Simulate arrival of SACK for chunk 2, cumulative ACK 1 (chunks 0 and 1 acked)
    acked = controller.record_ack(cumulative_ack=1, sack_ranges=[(2, 2)])
    assert acked == [0, 1]
    assert 2 in controller.sacked_sequences
    # Now in-flight is 2 (chunk 2 sacked, chunk 3 unacked) -> can send more!
    assert controller.can_send() is True

    # Send chunk 4 and 5
    controller.record_chunk_sent(chunks[4])
    controller.record_chunk_sent(chunks[5])


# ── TEST 4: OUT-OF-ORDER CHUNK REASSEMBLY & DUPLICATE REJECTION ───────────────

def test_chunk_reassembly_out_of_order_and_duplicates():
    full_data = b"CHUNK_0_PAYLOAD__CHUNK_1_PAYLOAD__CHUNK_2_PAYLOAD__CHUNK_3_PAYLOAD__"
    c_size = 17
    total = 4

    manager = ChunkReassemblyManager(
        stream_id="stream_reorder_01",
        total_chunks=total,
        expected_payload_length=len(full_data),
    )

    chunks = []
    for i in range(total):
        chunk_slice = full_data[i * c_size : (i + 1) * c_size]
        c = StreamChunk(
            message_id=f"m_{i}",
            stream_id="stream_reorder_01",
            sequence=i,
            total_chunks=total,
            chunk_size=c_size,
            payload_length=len(chunk_slice),
            crc32=0,
            flags=int(StreamFlags.DATA),
            data=chunk_slice,
        )
        c.crc32 = c.compute_crc32()
        chunks.append(c)

    # Deliver out of order: 2, 0, 3
    ok2, _ = manager.add_chunk(chunks[2])
    assert ok2 is True
    ok0, _ = manager.add_chunk(chunks[0])
    assert ok0 is True
    ok3, _ = manager.add_chunk(chunks[3])
    assert ok3 is True

    # Cumulative ack is 0, sack range is [(2, 3)]
    assert manager.get_cumulative_ack() == 0
    assert manager.get_sack_ranges() == [(2, 3)]
    assert manager.is_complete() is False

    # Inject duplicate of chunk 0 -> rejected without side effect
    ok_dup, reason = manager.add_chunk(chunks[0])
    assert ok_dup is False
    assert reason == "DUPLICATE_IGNORED"
    assert manager.duplicate_chunks_ignored == 1

    # Deliver missing chunk 1
    ok1, _ = manager.add_chunk(chunks[1])
    assert ok1 is True
    assert manager.is_complete() is True
    assert manager.get_cumulative_ack() == 3

    # Reassemble
    result = manager.reassemble()
    assert result == full_data
    manager.cleanup()


# ── TEST 5: CORRUPTION REJECTION (BAD CRC32) ──────────────────────────────────

def test_corruption_rejection():
    manager = ChunkReassemblyManager("stream_corrupt", 2, 2048)
    chunk = StreamChunk(
        message_id="m_corr",
        stream_id="stream_corrupt",
        sequence=0,
        total_chunks=2,
        chunk_size=1024,
        payload_length=1024,
        crc32=999999,  # Bad CRC
        flags=int(StreamFlags.DATA),
        data=b"A" * 1024,
    )
    ok, reason = manager.add_chunk(chunk)
    assert ok is False
    assert reason == "CRC32_MISMATCH"
    assert manager.corrupted_chunks_rejected == 1
    assert manager.is_complete() is False
    manager.cleanup()


# ── TEST 6: SELECTIVE RETRANSMISSION UNDER TIMEOUT ─────────────────────────────

def test_selective_retransmission_under_timeout():
    controller = SlidingWindowFlowController(initial_window=4, initial_rto_s=0.05)

    c0 = StreamChunk("m0", "s_rexmit", 0, 3, 100, 100, 0, int(StreamFlags.DATA))
    c1 = StreamChunk("m1", "s_rexmit", 1, 3, 100, 100, 0, int(StreamFlags.DATA))
    c2 = StreamChunk("m2", "s_rexmit", 2, 3, 100, 100, 0, int(StreamFlags.DATA))

    controller.record_chunk_sent(c0)
    controller.record_chunk_sent(c1)
    controller.record_chunk_sent(c2)

    # Chunk 2 is SACKed (received out-of-order), chunk 0 and 1 unacked
    controller.record_ack(cumulative_ack=-1, sack_ranges=[(2, 2)])

    # Wait for RTO timeout
    time.sleep(0.06)

    # Retransmission must select chunks 0 and 1, but NOT chunk 2
    resend = controller.get_chunks_to_retransmit()
    resend_seqs = [c.sequence for c in resend]
    assert 0 in resend_seqs
    assert 1 in resend_seqs
    assert 2 not in resend_seqs  # Chunk 2 is SACKed!
    assert controller.retransmitted_chunks == 2


# ── TEST 7: SLIDING WINDOW BACKPRESSURE THROTTLING ────────────────────────────

def test_sliding_window_backpressure_throttling():
    controller = SlidingWindowFlowController(initial_window=8)
    c0 = StreamChunk("m0", "s_bp", 0, 10, 100, 100, 0, int(StreamFlags.DATA))
    controller.record_chunk_sent(c0)

    # Receiver advertises window = 0 (Backpressure!)
    controller.record_ack(cumulative_ack=0, advertised_window=0)
    assert controller.effective_window == controller.min_window  # Clipped to min_window
    assert controller.backpressure_events >= 1


# ── TEST 8: STREAM CHECKPOINT & RESUME ────────────────────────────────────────

def test_stream_checkpoint_and_resume():
    chk = StreamCheckpoint(
        stream_id="stream_resume_01",
        last_acked_sequence=50,
        total_chunks=100,
        chunk_size=64 * 1024,
        received_chunk_indices=[52, 53],
        generation=1,
        stream_checksum=hashlib.sha256(b"stream_resume_01").hexdigest(),
    )
    chk_dict = chk.to_dict()
    restored = StreamCheckpoint.from_dict(chk_dict)

    assert restored.stream_id == "stream_resume_01"
    assert restored.last_acked_sequence == 50
    assert restored.received_chunk_indices == [52, 53]


# ── TEST 9: DISK-BACKED STREAMING FOR LARGE PAYLOADS ──────────────────────────

def test_disk_backed_streaming_memory_bound():
    data = b"LARGE_DISK_CHUNK_1__" * 100
    chunk_size = len(data)
    total_chunks = 3
    full_payload = data * total_chunks

    manager = ChunkReassemblyManager(
        stream_id="stream_disk_01",
        total_chunks=total_chunks,
        expected_payload_length=len(full_payload),
        disk_threshold_bytes=100,  # Force disk backing
    )
    assert manager.is_disk_backed is True

    for i in range(total_chunks):
        c = StreamChunk(
            message_id=f"m_d_{i}",
            stream_id="stream_disk_01",
            sequence=i,
            total_chunks=total_chunks,
            chunk_size=chunk_size,
            payload_length=len(data),
            crc32=0,
            flags=int(StreamFlags.DATA),
            data=data,
        )
        c.crc32 = c.compute_crc32()
        ok, _ = manager.add_chunk(c)
        assert ok is True

    assert manager.is_complete() is True
    reassembled = manager.reassemble()
    assert reassembled == full_payload
    manager.cleanup()


# ── TEST 10: STREAM PRIORITY & HEAD-OF-LINE BLOCKING PREVENTION ───────────────

@pytest.mark.anyio
async def test_stream_priority_head_of_line_bypass():
    srv = TcpTransport(node_id="p_srv")
    cli = TcpTransport(node_id="p_cli")
    port = 19150

    try:
        await srv.start_server("127.0.0.1", port)
        await cli.connect("p_srv", "127.0.0.1", port)

        streaming_srv = StreamingDistributedTransport("p_srv", srv)
        streaming_cli = StreamingDistributedTransport("p_cli", cli)
        await streaming_srv.start()
        await streaming_cli.start()

        # Enqueue 5 bulk data chunks into inbox
        for i in range(5):
            bulk_c = StreamChunk("b_msg", "s_bulk", i, 5, 100, 100, 0, int(StreamFlags.DATA), priority=StreamPriority.BULK)
            bulk_c.crc32 = bulk_c.compute_crc32()
            await streaming_srv.data_inbox.put(bulk_c)

        # Enqueue 1 critical control chunk
        ctrl_c = StreamChunk("c_msg", "s_ctrl", 0, 1, 50, 50, 0, int(StreamFlags.CONTROL), priority=StreamPriority.CRITICAL_CONTROL)
        ctrl_c.crc32 = ctrl_c.compute_crc32()
        await streaming_srv.control_inbox.put(ctrl_c)

        # Receiver checking priority should see CRITICAL_CONTROL immediately, ahead of all bulk chunks
        c = await streaming_srv.control_inbox.get()
        assert c.priority == StreamPriority.CRITICAL_CONTROL
        assert c.stream_id == "s_ctrl"
    finally:
        await streaming_cli.stop()
        await streaming_srv.stop()
        await cli.close()
        await srv.close()


# ── TEST 11: END-TO-END STREAMING OVER TCP ────────────────────────────────────

@pytest.mark.anyio
async def test_end_to_end_streaming_pipeline_over_tcp():
    srv = TcpTransport(node_id="e2e_srv")
    cli = TcpTransport(node_id="e2e_cli")
    port = 19151

    try:
        await srv.start_server("127.0.0.1", port)
        await cli.connect("e2e_srv", "127.0.0.1", port)

        streaming_srv = StreamingDistributedTransport("e2e_srv", srv)
        streaming_cli = StreamingDistributedTransport("e2e_cli", cli)
        await streaming_srv.start()
        await streaming_cli.start()

        # 128 KB test payload
        payload = b"JARVIS_STREAM_" * (8 * 1024)

        # Send stream in background task
        async def _sender():
            return await streaming_cli.send_stream(
                target_node_id="e2e_srv",
                stream_id="stream_e2e_01",
                payload_data=payload,
                chunk_size=16 * 1024,
                initial_window=8,
            )

        send_task = asyncio.create_task(_sender())

        # Receive stream
        s_id, received_bytes, metrics = await streaming_srv.receive_stream(
            stream_id="stream_e2e_01",
            timeout=5.0,
        )

        send_metrics = await send_task

        assert s_id == "stream_e2e_01"
        assert received_bytes == payload
        assert metrics["total_bytes"] == len(payload)
        assert send_metrics["total_chunks"] == metrics["total_chunks"]
        assert send_metrics["throughput_mb_s"] > 0.0
    finally:
        await streaming_cli.stop()
        await streaming_srv.stop()
        await cli.close()
        await srv.close()


# ── TEST 12: REFERENCE STREAMING MODEL INVARIANT VERIFICATION ─────────────────

def test_reference_streaming_model_invariants():
    model = ReferenceStreamingModel()

    # Stream 1: clean execution
    model.record_chunk_sent("s1", 0)
    model.record_chunk_sent("s1", 1)
    model.record_chunk_received("s1", 0)
    model.record_chunk_received("s1", 1)
    model.record_side_effect("s1", "write_artifact_s1")
    model.record_completion("s1", expected_total_chunks=2)

    inv = model.verify_all_invariants()
    assert inv["is_valid"] is True
    assert inv["violations_count"] == 0
    assert inv["corrupted_payload_accepted"] == 0
    assert inv["duplicate_side_effect"] == 0
    assert inv["false_completion"] == 0
    assert inv["stream_leaks"] == 0
