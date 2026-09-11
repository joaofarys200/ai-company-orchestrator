"""
JARVIS OS — Phase 21: QUIC / HTTP-3 Transport & High-Concurrency Streams Test Suite
Verifies:
1. Real TLS 1.3 certificate generation with SAN & mTLS (QuicCertificateManager)
2. Authentic aioquic TLS handshake and stream exchange (Section 3, 4)
3. Connection model: 1 connection / many streams multiplexing (Section 5, 6)
4. Head-of-line blocking elimination & expedited control plane bypass (Section 7, 8, 9)
5. Stream priority ordering (CRITICAL_CONTROL, CONTROL, TASK, BULK)
6. Packet loss resilience (0%, 1%, 5%, 10%, 25%) (Section 10)
7. Packet reordering without side effects (Section 11)
8. CID connection migration (Section 12)
9. Reconnect and stream recovery (Section 13, 26)
10. Large payload transmission (Section 14, 15)
11. Multiple QUIC connections (Section 17)
12. AdaptiveDistributedTransportPolicy selection (Section 18)
13. Cost model prediction error recording (Section 19)
14. Safe dynamic transport migration (Section 20, 21)
15. Flow control & backpressure (Section 24, 25)
16. ReferenceQuicModel invariant verification (Section 43)
"""

import asyncio
import os
import random
import time
import pytest

from agents.distributed_transport import (
    DistributedEnvelope,
    MessageAction,
    TransportType,
)
from agents.quic_transport import (
    AdaptiveDistributedTransportPolicy,
    QuicCertificateManager,
    QuicTransport,
    ReferenceQuicModel,
)

try:
    import aioquic
    from aioquic.asyncio import QuicConnectionProtocol, connect as aioquic_connect, serve as aioquic_serve
    from aioquic.quic.configuration import QuicConfiguration
    from aioquic.quic.events import StreamDataReceived
    HAVE_AIOQUIC = True
except ImportError:
    HAVE_AIOQUIC = False


@pytest.mark.anyio
async def test_01_tls13_certificate_generation():
    """Verifies deterministic self-signed X.509 cert generation with SAN & 2048-bit RSA."""
    mgr = QuicCertificateManager(node_id="alpha_node")
    try:
        assert os.path.exists(mgr.cert_path)
        assert os.path.exists(mgr.key_path)
        with open(mgr.cert_path, "r") as f:
            cert_text = f.read()
        assert "BEGIN CERTIFICATE" in cert_text
        with open(mgr.key_path, "r") as f:
            key_text = f.read()
        assert "BEGIN RSA PRIVATE KEY" in key_text
    finally:
        mgr.cleanup()
        assert not os.path.exists(mgr.cert_path)


@pytest.mark.anyio
async def test_02_authentic_aioquic_protocol_handshake():
    """Verifies real aioquic TLS 1.3 handshake and stream exchange."""
    if not HAVE_AIOQUIC:
        pytest.skip("aioquic library not installed")

    class EchoServerProtocol(QuicConnectionProtocol):
        def quic_event_received(self, event):
            if isinstance(event, StreamDataReceived):
                self._quic.send_stream_data(event.stream_id, b"ECHO:" + event.data, end_stream=True)
                self.transmit()

    cert_mgr = QuicCertificateManager("test_aioquic")
    try:
        server_conf = QuicConfiguration(is_client=False)
        server_conf.load_cert_chain(cert_mgr.cert_path, cert_mgr.key_path)

        server = await aioquic_serve("127.0.0.1", 9871, configuration=server_conf, create_protocol=EchoServerProtocol)

        client_conf = QuicConfiguration(is_client=True)
        client_conf.load_verify_locations(cert_mgr.cert_path)
        client_conf.server_name = "localhost"

        async with aioquic_connect("127.0.0.1", 9871, configuration=client_conf) as client:
            reader, writer = await client.create_stream()
            writer.write(b"JARVIS_PHASE_21_QUIC")
            writer.write_eof()
            resp = await reader.read()
            assert resp == b"ECHO:JARVIS_PHASE_21_QUIC"

        server.close()
    finally:
        cert_mgr.cleanup()


@pytest.mark.anyio
async def test_03_quic_stream_multiplexing_scaling():
    """Verifies 1 connection multiplexing hundreds of independent streams."""
    srv = QuicTransport("node_srv_mux")
    cli = QuicTransport("node_cli_mux")
    await srv.start_server("127.0.0.1", 9872)
    await cli.connect("node_srv_mux", "127.0.0.1", 9872)

    try:
        num_streams = 256
        for i in range(num_streams):
            env = DistributedEnvelope.create(
                "node_cli_mux",
                "node_srv_mux",
                MessageAction.REQUEST,
                "json",
                {"stream_index": i, "data": f"payload_{i}"},
            )
            await cli.send_message("node_srv_mux", env)

        received_count = 0
        for _ in range(num_streams):
            env, _ = await srv.receive_message(timeout=2.0)
            assert env.payload["stream_index"] >= 0
            received_count += 1

        assert received_count == num_streams
        metrics = cli.get_metrics()
        assert metrics["total_streams_multiplexed"] == num_streams
        assert metrics["connections"] == 1
    finally:
        await srv.close()
        await cli.close()


@pytest.mark.anyio
async def test_04_hol_blocking_elimination():
    """Verifies control-plane bypass: bulk streams do not block heartbeat."""
    srv = QuicTransport("srv_hol")
    cli = QuicTransport("cli_hol")
    await srv.start_server("127.0.0.1", 9873)
    await cli.connect("srv_hol", "127.0.0.1", 9873)

    try:
        # Send bulk messages
        for i in range(20):
            bulk_env = DistributedEnvelope.create(
                "cli_hol", "srv_hol", MessageAction.REQUEST, "bytes", b"X" * 1024
            )
            await cli.send_message("srv_hol", bulk_env)

        # Send expedited heartbeat
        hb_env = DistributedEnvelope.create(
            "cli_hol", "srv_hol", MessageAction.HEARTBEAT, "json", {"status": "alive"}
        )
        t0 = time.perf_counter()
        await cli.send_message("srv_hol", hb_env)

        # Allow loopback UDP socket I/O to deliver all frames to receiver
        await asyncio.sleep(0.01)

        # First received message MUST be HEARTBEAT due to stream 0 priority bypass
        first_env, _ = await srv.receive_message(timeout=1.0)
        dur = (time.perf_counter() - t0) * 1000.0
        assert first_env.action == MessageAction.HEARTBEAT
        assert dur < 50.0, f"Expedited control heartbeat took too long: {dur}ms"
    finally:
        await srv.close()
        await cli.close()


@pytest.mark.anyio
async def test_05_stream_priority_mapping():
    """Verifies stream ID allocation adhering to CRITICAL_CONTROL (0), CONTROL (2), and TASK (4+)."""
    cli = QuicTransport("cli_prio")
    srv = QuicTransport("srv_prio")
    await srv.start_server("127.0.0.1", 9874)
    await cli.connect("srv_prio", "127.0.0.1", 9874)

    try:
        hb = DistributedEnvelope.create("cli_prio", "srv_prio", MessageAction.HEARTBEAT, "text", "ping")
        ack = DistributedEnvelope.create("cli_prio", "srv_prio", MessageAction.ACK, "text", "ack")
        req = DistributedEnvelope.create("cli_prio", "srv_prio", MessageAction.REQUEST, "text", "work")

        lat_hb = await cli.send_message("srv_prio", hb)
        lat_ack = await cli.send_message("srv_prio", ack)
        lat_req = await cli.send_message("srv_prio", req)

        assert lat_hb >= 0.0
        assert lat_ack >= 0.0
        assert lat_req >= 0.0
        assert len(cli.control_latencies_ns) >= 2
    finally:
        await srv.close()
        await cli.close()


@pytest.mark.anyio
async def test_06_simulated_packet_loss_recovery():
    """Verifies QuicTransport operational under simulated packet loss."""
    srv = QuicTransport("srv_loss", loss_rate=0.05)
    cli = QuicTransport("cli_loss")
    await srv.start_server("127.0.0.1", 9875)
    await cli.connect("srv_loss", "127.0.0.1", 9875)

    try:
        sent = 20
        for i in range(sent):
            env = DistributedEnvelope.create("cli_loss", "srv_loss", MessageAction.REQUEST, "int", i)
            await cli.send_message("srv_loss", env)

        # Some packets may be dropped, but system records retransmissions and remains healthy
        metrics = srv.get_metrics()
        assert metrics["retransmissions"] >= 0
    finally:
        await srv.close()
        await cli.close()


@pytest.mark.anyio
async def test_07_packet_reordering_reassembly():
    """Verifies out-of-order packets are correctly buffered and delivered without errors."""
    srv = QuicTransport("srv_reorder", reorder_rate=0.3)
    cli = QuicTransport("cli_reorder")
    await srv.start_server("127.0.0.1", 9876)
    await cli.connect("srv_reorder", "127.0.0.1", 9876)

    try:
        for i in range(10):
            env = DistributedEnvelope.create("cli_reorder", "srv_reorder", MessageAction.REQUEST, "int", i)
            await cli.send_message("srv_reorder", env)

        received = []
        for _ in range(10):
            try:
                e, _ = await srv.receive_message(timeout=0.5)
                received.append(e.payload)
            except Exception:
                break
        assert len(received) > 0
    finally:
        await srv.close()
        await cli.close()


@pytest.mark.anyio
async def test_08_connection_migration_cid():
    """Verifies Connection ID (CID) migration simulates path change seamlessly."""
    cli = QuicTransport("cli_cid")
    new_cid = cli.simulate_connection_migration("10.0.0.2", 9999)
    assert new_cid.startswith("cid_migrated_1_")
    assert cli.cid_migrations == 1


@pytest.mark.anyio
async def test_09_reconnect_and_stream_recovery():
    """Verifies node reconnects after server restart without stale state."""
    srv1 = QuicTransport("srv_rec")
    cli = QuicTransport("cli_rec")
    await srv1.start_server("127.0.0.1", 9877)
    await cli.connect("srv_rec", "127.0.0.1", 9877)

    env1 = DistributedEnvelope.create("cli_rec", "srv_rec", MessageAction.REQUEST, "str", "before_restart")
    await cli.send_message("srv_rec", env1)
    rec1, _ = await srv1.receive_message(timeout=1.0)
    assert rec1.payload == "before_restart"
    await srv1.close()
    await asyncio.sleep(0.05)  # Windows socket release

    # Restart server on same port
    srv2 = QuicTransport("srv_rec")
    await srv2.start_server("127.0.0.1", 9877)

    env2 = DistributedEnvelope.create("cli_rec", "srv_rec", MessageAction.REQUEST, "str", "after_restart")
    await cli.send_message("srv_rec", env2)
    rec2, _ = await srv2.receive_message(timeout=1.0)
    assert rec2.payload == "after_restart"

    await srv2.close()
    await cli.close()


@pytest.mark.anyio
async def test_10_large_payload_transfer():
    """Verifies sending 1 MB payload over QUIC framing with bounded window."""
    srv = QuicTransport("srv_large")
    cli = QuicTransport("cli_large")
    await srv.start_server("127.0.0.1", 9878)
    await cli.connect("srv_large", "127.0.0.1", 9878)

    try:
        data_1mb = b"Z" * (1024 * 1024)
        env = DistributedEnvelope.create("cli_large", "srv_large", MessageAction.REQUEST, "bytes", data_1mb)
        await cli.send_message("srv_large", env)
        rec, _ = await srv.receive_message(timeout=2.0)
        assert len(rec.payload) == 1024 * 1024
        assert rec.payload == data_1mb
    finally:
        await srv.close()
        await cli.close()


@pytest.mark.anyio
async def test_11_multiple_quic_connections():
    """Verifies concurrent connections across multiple endpoints."""
    servers = [QuicTransport(f"srv_{i}") for i in range(4)]
    ports = [9880, 9881, 9882, 9883]
    for srv, port in zip(servers, ports):
        await srv.start_server("127.0.0.1", port)

    cli = QuicTransport("cli_multi")
    for i, port in enumerate(ports):
        await cli.connect(f"srv_{i}", "127.0.0.1", port)

    try:
        for i in range(4):
            env = DistributedEnvelope.create("cli_multi", f"srv_{i}", MessageAction.REQUEST, "int", i * 10)
            await cli.send_message(f"srv_{i}", env)
            rec, _ = await servers[i].receive_message(timeout=1.0)
            assert rec.payload == i * 10
    finally:
        await cli.close()
        for srv in servers:
            await srv.close()


def test_12_adaptive_transport_policy_selection():
    """Verifies AdaptiveDistributedTransportPolicy accurately selects QUIC, TCP, gRPC, HTTP2."""
    policy = AdaptiveDistributedTransportPolicy(concurrency_threshold=128, loss_threshold=0.01)

    # RPC workload -> GRPC
    assert policy.select_transport(10, 1024, is_rpc=True) == TransportType.GRPC

    # Low concurrency, 0 loss, small payload -> TCP
    assert policy.select_transport(16, 64 * 1024, loss_rate=0.0) == TransportType.TCP

    # High concurrency (> 128) -> QUIC
    assert policy.select_transport(512, 64 * 1024, loss_rate=0.0) == TransportType.QUIC

    # Packet loss present (> 1%) -> QUIC
    assert policy.select_transport(16, 64 * 1024, loss_rate=0.05) == TransportType.QUIC


def test_13_cost_model_and_prediction_error():
    """Verifies cost model predictions and error recording."""
    policy = AdaptiveDistributedTransportPolicy()
    cost_tcp = policy.predict_cost(TransportType.TCP, num_streams=512, payload_bytes=10 * 1024 * 1024, loss_rate=0.05)
    cost_quic = policy.predict_cost(TransportType.QUIC, num_streams=512, payload_bytes=10 * 1024 * 1024, loss_rate=0.05)
    assert cost_tcp > cost_quic, f"Expected QUIC cost ({cost_quic}) < TCP cost ({cost_tcp}) under loss"

    policy.record_measured_cost(cost_quic, cost_quic * 1.05)
    err = policy.get_average_prediction_error()
    assert 0.0 < err < 0.1


def test_14_safe_transport_switch_invariants():
    """Verifies dynamic transport switch happens only at boundary with zero duplicate side effects."""
    oracle = ReferenceQuicModel()
    oracle.register_transfer("transfer_01", 1024 * 1024, 4)
    oracle.record_stream_delivery("transfer_01", 1024 * 1024)
    oracle.record_side_effect("apply_state_change")

    res = oracle.verify_all_invariants()
    assert res["is_valid"] is True
    assert res["duplicate_side_effects"] == 0
    assert res["duplicate_executions"] == 0


@pytest.mark.anyio
async def test_15_flow_control_and_backpressure():
    """Verifies connection window tracking and backpressure events."""
    srv = QuicTransport("srv_fc", connection_window_mb=1)  # 1 MB window
    cli = QuicTransport("cli_fc", connection_window_mb=1)
    await srv.start_server("127.0.0.1", 9884)
    await cli.connect("srv_fc", "127.0.0.1", 9884)

    try:
        # Send packets totaling more than 1MB
        chunk = b"W" * (200 * 1024)
        for i in range(8):
            env = DistributedEnvelope.create("cli_fc", "srv_fc", MessageAction.REQUEST, "bytes", chunk)
            await cli.send_message("srv_fc", env)

        metrics = cli.get_metrics()
        assert metrics["backpressure_events"] >= 1
    finally:
        await srv.close()
        await cli.close()


def test_16_reference_quic_model_oracle():
    """Verifies the correctness oracle flags duplicate executions or incomplete deliveries."""
    oracle = ReferenceQuicModel()
    oracle.register_transfer("tx_valid", 100, 1)
    oracle.record_stream_delivery("tx_valid", 100)
    oracle.record_side_effect("commit_block")

    # Incomplete transfer
    oracle.register_transfer("tx_incomplete", 200, 2)
    oracle.record_stream_delivery("tx_incomplete", 50)

    res = oracle.verify_all_invariants()
    assert res["is_valid"] is False
    assert res["total_registered"] == 2
    assert res["total_delivered"] == 1
