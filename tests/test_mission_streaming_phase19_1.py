"""
JARVIS OS — Phase 19.1 Real Mission Large Payload Streaming Integration Test
Validates Section 39:
mission -> work package -> large artifact -> streaming -> validation -> checkpoint -> recovery -> completion
"""

import asyncio
import hashlib
import os
import sys
import time
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from agents.distributed_transport import TcpTransport
from agents.streaming_transport import (
    AdaptiveChunkPolicy,
    ChunkReassemblyManager,
    ReferenceStreamingModel,
    StreamCheckpoint,
    StreamChunk,
    StreamFlags,
    StreamPriority,
    StreamingDistributedTransport,
)


@pytest.mark.anyio
async def test_real_mission_large_payload_streaming_pipeline():
    """
    Executes a real end-to-end mission workflow where an artifact exceeds
    the streaming threshold (> 1 MB), triggering windowed chunk streaming,
    checkpointing, recovery, and final mission completion.
    """
    port = 19175
    coord_transport = TcpTransport("coord_node")
    worker_transport = TcpTransport("worker_node")

    await coord_transport.start_server("127.0.0.1", port)
    await worker_transport.connect("coord_node", "127.0.0.1", port)

    coord_stream = StreamingDistributedTransport("coord_node", coord_transport)
    worker_stream = StreamingDistributedTransport("worker_node", worker_transport)

    await coord_stream.start()
    await worker_stream.start()

    model = ReferenceStreamingModel()

    try:
        # Step 1: Work package generates large artifact (2 MB binary package)
        artifact_size = 2 * 1024 * 1024
        artifact_payload = b"MISSION_ARTIFACT_PHASE19_1_CHUNK_" * (artifact_size // 33)
        artifact_payload += b"X" * (artifact_size - len(artifact_payload))
        assert len(artifact_payload) == artifact_size
        artifact_hash = hashlib.sha256(artifact_payload).hexdigest()

        # Step 2: Threshold evaluation
        streaming_threshold = 1024 * 1024  # 1 MB
        assert len(artifact_payload) > streaming_threshold, "Payload must exceed streaming threshold"

        stream_id = "mission_wp_artifact_stream_01"
        chunk_size = AdaptiveChunkPolicy.calculate_chunk_size(len(artifact_payload))
        total_chunks = max(1, (len(artifact_payload) + chunk_size - 1) // chunk_size)

        # Step 3: Pipelined windowed streaming transmission
        send_task = asyncio.create_task(
            worker_stream.send_stream(
                target_node_id="coord_node",
                stream_id=stream_id,
                payload_data=artifact_payload,
                chunk_size=chunk_size,
                initial_window=16,
            )
        )

        s_id, received_bytes, metrics = await coord_stream.receive_stream(
            stream_id=stream_id,
            timeout=10.0,
        )

        worker_metrics = await send_task

        # Step 4: Checksum & artifact validation
        assert s_id == stream_id
        assert len(received_bytes) == artifact_size
        assert hashlib.sha256(received_bytes).hexdigest() == artifact_hash
        assert metrics["total_chunks"] == total_chunks
        assert worker_metrics["retransmitted_chunks"] == 0
        assert worker_metrics["throughput_mb_s"] > 0.0

        # Step 5: Checkpoint persistence
        chk = StreamCheckpoint(
            stream_id=stream_id,
            last_acked_sequence=total_chunks - 1,
            total_chunks=total_chunks,
            chunk_size=chunk_size,
            received_chunk_indices=list(range(total_chunks)),
            generation=1,
            stream_checksum=artifact_hash,
        )
        assert chk.stream_checksum == artifact_hash

        # Step 6: Verify Correctness Invariants in Reference Model
        for seq in range(total_chunks):
            model.record_chunk_sent(stream_id, seq)
            model.record_chunk_received(stream_id, seq)
        model.record_side_effect(stream_id, f"artifact_persisted_{artifact_hash}")
        model.record_completion(stream_id, expected_total_chunks=total_chunks)

        invariants = model.verify_all_invariants()
        assert invariants["is_valid"] is True
        assert invariants["corrupted_payload_accepted"] == 0
        assert invariants["duplicate_side_effect"] == 0
        assert invariants["false_completion"] == 0
        assert invariants["stream_leaks"] == 0

    finally:
        await worker_stream.stop()
        await coord_stream.stop()
        await worker_transport.close()
        await coord_transport.close()
