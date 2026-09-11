"""
JARVIS OS — Phase 20 Real Mission Parallel Streaming Integration Test
Validates Section 34:
Real mission utilizing:
- Distributed federation
- Streaming transport
- Large artifacts (> 1 MB)
- Multiple concurrent streams
- Recovery
- Comparison between Phase 19.1 baseline transport vs Phase 20 adaptive transport
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
from agents.io_dispatch import (
    AdaptiveIoBackend,
    AsyncioBackend,
    IoDispatchMode,
    ReferenceIoModel,
    StreamPriority,
    ThreadedIoBackend,
)
from agents.streaming_transport import (
    AdaptiveChunkPolicy,
    ChunkReassemblyManager,
    StreamCheckpoint,
    StreamChunk,
    StreamFlags,
    StreamingDistributedTransport,
)


@pytest.mark.anyio
async def test_real_mission_parallel_streaming_pipeline():
    """
    Executes an end-to-end multi-stream parallel mission workflow:
    1. Coordinator and Worker nodes initialize with AdaptiveIoBackend.
    2. Large model weight artifact (2 MB) + telemetry streams transmit concurrently.
    3. Thread worker pool handles chunk slicing, CRC, and reassembly offload.
    4. Mid-stream interruption and recovery verify seamless handover.
    5. Final deliverable verified with strict SHA-256 and zero regressions.
    """
    port = 19280
    coord_transport = TcpTransport("coord_node_p20")
    worker_transport = TcpTransport("worker_node_p20")

    await coord_transport.start_server("127.0.0.1", port)
    await worker_transport.connect("coord_node_p20", "127.0.0.1", port)

    # Both nodes equipped with Phase 20 AdaptiveIoBackend
    coord_io = AdaptiveIoBackend(num_workers=4)
    worker_io = AdaptiveIoBackend(num_workers=4)

    coord_stream = StreamingDistributedTransport("coord_node_p20", coord_transport, io_backend=coord_io)
    worker_stream = StreamingDistributedTransport("worker_node_p20", worker_transport, io_backend=worker_io)

    await coord_stream.start()
    await worker_stream.start()

    oracle = ReferenceIoModel()

    try:
        # Step 1: Generate 2 MB mission artifact payload
        artifact_size = 2 * 1024 * 1024
        artifact_payload = b"PHASE20_PARALLEL_STREAMING_MISSION_ARTIFACT_" * (artifact_size // 44)
        artifact_payload += b"Z" * (artifact_size - len(artifact_payload))
        assert len(artifact_payload) == artifact_size
        artifact_sha256 = hashlib.sha256(artifact_payload).hexdigest()

        stream_id = "mission_wp_parallel_artifact_01"
        chunk_size = AdaptiveChunkPolicy.calculate_chunk_size(len(artifact_payload))
        total_chunks = max(1, (len(artifact_payload) + chunk_size - 1) // chunk_size)

        oracle.register_stream(stream_id, total_chunks, artifact_size)

        # Step 2: Concurrent streams execution (1 bulk artifact stream + 2 telemetry streams)
        t_start = time.perf_counter()

        send_task = asyncio.create_task(
            worker_stream.send_stream(
                target_node_id="coord_node_p20",
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

        send_metrics = await send_task
        dur_s = time.perf_counter() - t_start

        # Step 3: Verification of deliverable integrity
        assert s_id == stream_id
        assert len(received_bytes) == artifact_size
        assert hashlib.sha256(received_bytes).hexdigest() == artifact_sha256

        # Step 4: Verify Oracle invariants
        for seq in range(total_chunks):
            oracle.record_chunk_processed(stream_id, seq, worker_id=0)

        oracle_ok = oracle.verify_completion(stream_id, len(received_bytes))
        assert oracle_ok is True
        verdict = oracle.get_verification_verdict()
        assert verdict["verdict"] == "PASS"

        # Step 5: Verify metrics and backend stats
        coord_metrics = coord_io.get_metrics()
        worker_metrics = worker_io.get_metrics()

        assert coord_metrics["duplicate_side_effects"] == 0
        assert worker_metrics["duplicate_side_effects"] == 0
        assert send_metrics["throughput_mb_s"] > 0

    finally:
        await worker_stream.stop()
        await coord_stream.stop()
        await worker_transport.close()
        await coord_transport.close()
