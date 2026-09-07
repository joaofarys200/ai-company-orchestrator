"""
JARVIS OS — Phase 19: Comprehensive Unit & Integration Test Suite
Distributed Multi-Host Federation, Network Transport & Cross-Node Resilience
"""

import asyncio
import copy
import hashlib
import time
import pytest

from agents.distributed_transport import (
    CorruptedEnvelopeError,
    DistributedEnvelope,
    GrpcStatusCode,
    GrpcTransport,
    Http2Transport,
    MessageAction,
    SimulatedNetworkTransport,
    TcpTransport,
    TransportError,
    TransportType,
)
from agents.distributed_federation import (
    ClusterCheckpoint,
    CrossNodeDependencyUnsatisfiedError,
    DistributedDagReconciler,
    DistributedEventBridge,
    DistributedEventOrderingOracle,
    DistributedFederationCoordinator,
    DistributedFederationReferenceModel,
    DistributedLeaseManager,
    DistributedMessageDeduplicator,
    DistributedNode,
    DistributedNodeRegistry,
    DistributedTaskPartitioner,
    FencedLeaseToken,
    LeaseScope,
    NodeCapability,
    NodeIdentity,
    NodeMetadata,
    NodeState,
    SplitBrainViolationError,
    StaleLeaseFenceError,
    WorkPackage,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


# ── TEST 1: TCP TRANSPORT ROUNDTRIP & ENVELOPE INTEGRITY ──────────────────────

@pytest.mark.anyio
async def test_tcp_transport_roundtrip_and_envelope_integrity():
    server = TcpTransport(node_id="server_node")
    client = TcpTransport(node_id="client_node")
    port = 19101

    try:
        await server.start_server("127.0.0.1", port)
        await client.connect("server_node", "127.0.0.1", port)

        env = DistributedEnvelope.create(
            source_node="client_node",
            destination_node="server_node",
            action=MessageAction.REQUEST,
            payload_type="eval_expression",
            payload={"expr": "1 + 1", "data": [1, 2, 3, 4]},
            sequence=1,
            generation=1,
        )

        send_ms = await client.send_message("server_node", env)
        assert send_ms >= 0.0

        received_env, recv_ms = await server.receive_message(timeout=5.0)
        assert received_env.message_id == env.message_id
        assert received_env.payload == {"expr": "1 + 1", "data": [1, 2, 3, 4]}
        assert received_env.verify_checksum() is True
    finally:
        await client.close()
        await server.close()


# ── TEST 2: HTTP/2 TRANSPORT STREAMING & FRAMING ──────────────────────────────

@pytest.mark.anyio
async def test_http2_transport_streaming_and_framing():
    server = Http2Transport(node_id="h2_server")
    client = Http2Transport(node_id="h2_client")
    port = 19102

    try:
        await server.start_server("127.0.0.1", port)
        await client.connect("h2_server", "127.0.0.1", port)

        env = DistributedEnvelope.create(
            source_node="h2_client",
            destination_node="h2_server",
            action=MessageAction.REQUEST,
            payload_type="http2_chunk",
            payload={"stream_id": 1, "bytes": b"HTTP2_PAYLOAD_CHUNK"},
            sequence=42,
        )

        dur = await client.send_message("h2_server", env)
        assert dur >= 0.0

        received, _ = await server.receive_message(timeout=5.0)
        assert received.sequence == 42
        assert received.payload["bytes"] == b"HTTP2_PAYLOAD_CHUNK"
    finally:
        await client.close()
        await server.close()


# ── TEST 3: GRPC TRANSPORT WIRE RPC & STATUS CODES ────────────────────────────

@pytest.mark.anyio
async def test_grpc_transport_rpc_semantics_and_status_codes():
    server = GrpcTransport(node_id="grpc_server")
    client = GrpcTransport(node_id="grpc_client")
    port = 19103

    try:
        await server.start_server("127.0.0.1", port)
        await client.connect("grpc_server", "127.0.0.1", port)

        env = DistributedEnvelope.create(
            source_node="grpc_client",
            destination_node="grpc_server",
            action=MessageAction.RPC_CALL,
            payload_type="service.MethodCall",
            payload={"rpc_method": "ExecuteTask", "args": {"task_id": "t_01"}},
            grpc_status=GrpcStatusCode.OK,
        )

        dur = await client.send_message("grpc_server", env)
        assert dur >= 0.0

        received, _ = await server.receive_message(timeout=5.0)
        assert received.action == MessageAction.RPC_CALL
        assert received.grpc_status == GrpcStatusCode.OK
        assert received.payload["rpc_method"] == "ExecuteTask"
    finally:
        await client.close()
        await server.close()


# ── TEST 4: NODE REGISTRY LIFECYCLE & DRAIN ───────────────────────────────────

@pytest.mark.anyio
async def test_node_registry_lifecycle_and_drain():
    registry = DistributedNodeRegistry(cluster_id="test_cluster", heartbeat_timeout_seconds=0.3)
    ident = NodeIdentity(node_id="node_01", cluster_id="test_cluster", host="127.0.0.1", port=9001)
    cap = NodeCapability(cpu_cores=8, memory_bytes=8192, agent_capacity=32)

    meta = await registry.register_node(ident, cap)
    assert meta.state == NodeState.ACTIVE
    assert len(registry.get_active_nodes()) == 1

    # Heartbeat updates timestamp
    ok = await registry.heartbeat("node_01", current_load=0.25)
    assert ok is True
    assert registry.nodes["node_01"].current_load == 0.25

    # Drain node
    drained = await registry.drain_node("node_01")
    assert drained is True
    assert registry.nodes["node_01"].state == NodeState.DRAINING

    # Retire node
    retired = await registry.retire_node("node_01")
    assert retired is True
    assert registry.nodes["node_01"].state == NodeState.RETIRED
    assert len(registry.get_active_nodes()) == 0


# ── TEST 5: DETERMINISTIC WORK PACKAGE PARTITIONING ───────────────────────────

def test_deterministic_work_package_partitioning():
    nodes_meta = [
        NodeMetadata(
            identity=NodeIdentity(node_id=f"node_{i}", cluster_id="c1"),
            capability=NodeCapability(cpu_cores=4, browser_capability=(i % 2 == 0)),
            state=NodeState.ACTIVE,
        )
        for i in range(3)
    ]

    tasks = [
        TaskNode(
            task_id=f"t_{i}",
            title=f"Task {i}",
            category="CODING" if i % 2 == 0 else "BROWSER",
            priority=i % 3,
            metadata={"path_scope": [f"mod_{i % 2}/file_{i}.py"]},
        )
        for i in range(12)
    ]
    dag = TaskGraph(nodes=tasks)

    # Run partitioning twice with identical inputs
    packages_1 = DistributedTaskPartitioner.partition_dag("miss_1", dag, nodes_meta, target_package_size=4)
    packages_2 = DistributedTaskPartitioner.partition_dag("miss_1", dag, nodes_meta, target_package_size=4)

    assert len(packages_1) == len(packages_2)
    for p1, p2 in zip(packages_1, packages_2):
        assert p1.package_id == p2.package_id
        assert p1.assigned_node_id == p2.assigned_node_id
        assert len(p1.tasks) == len(p2.tasks)


# ── TEST 6: CROSS-NODE DEPENDENCIES & CAUSAL EVIDENCE ─────────────────────────

@pytest.mark.anyio
async def test_cross_node_dependencies_and_ordering():
    t1 = TaskNode(task_id="nodeA_t1", title="Task A1", category="CODING")
    t2 = TaskNode(task_id="nodeB_t2", title="Task B2", category="CODING", dependencies=["nodeA_t1"])
    dag = TaskGraph(nodes=[t1, t2])

    reconciler = DistributedDagReconciler(dag)
    await reconciler.register_cross_node_dependency("nodeB_t2", "nodeA_t1")

    # Before nodeA_t1 completes, nodeB_t2 cannot execute
    can_run = await reconciler.can_execute("nodeB_t2")
    assert can_run is False

    # Simulate completion on Node A with evidence
    evidence = hashlib.sha256(b"taskA_evidence").hexdigest()
    await reconciler.record_completion("nodeA_t1", evidence)

    # Now nodeB_t2 is unblocked
    can_run_now = await reconciler.can_execute("nodeB_t2")
    assert can_run_now is True
    assert dag.get_node("nodeA_t1").status == TaskStatus.COMPLETED


# ── TEST 7: DISTRIBUTED LEASE MANAGER & FENCING TOKENS ────────────────────────

@pytest.mark.anyio
async def test_distributed_lease_manager_fencing():
    registry = DistributedNodeRegistry(cluster_id="cluster_fencing")
    for i in range(3):
        await registry.register_node(
            NodeIdentity(node_id=f"node_{i}", cluster_id="cluster_fencing"),
            NodeCapability(),
        )

    mgr = DistributedLeaseManager(registry)
    token1 = await mgr.acquire_lease("resource_db", "node_0", scope=LeaseScope.CLUSTER_GLOBAL, ttl_seconds=10.0)
    assert token1.lease_token == 1
    assert token1.owner_node_id == "node_0"

    # Token 1 is valid
    assert await mgr.validate_fence("resource_db", 1) is True

    # Node 1 cannot steal active lease
    with pytest.raises(StaleLeaseFenceError):
        await mgr.acquire_lease("resource_db", "node_1", scope=LeaseScope.CLUSTER_GLOBAL)

    # Stale token validation fails
    assert await mgr.validate_fence("resource_db", 999) is False


# ── TEST 8: SPLIT-BRAIN QUORUM PROTECTION ─────────────────────────────────────

@pytest.mark.anyio
async def test_split_brain_quorum_protection():
    registry = DistributedNodeRegistry(cluster_id="cluster_quorum", heartbeat_timeout_seconds=0.1)
    # Register 4 nodes
    for i in range(4):
        await registry.register_node(
            NodeIdentity(node_id=f"node_{i}", cluster_id="cluster_quorum"),
            NodeCapability(),
        )

    mgr = DistributedLeaseManager(registry)
    assert registry.has_quorum() is True

    # Simulate network partition: 3 nodes fail
    registry.nodes["node_1"].state = NodeState.FAILED
    registry.nodes["node_2"].state = NodeState.FAILED
    registry.nodes["node_3"].state = NodeState.FAILED

    assert registry.has_quorum() is False

    # Minority node attempts to acquire global lease -> SplitBrainViolationError
    with pytest.raises(SplitBrainViolationError):
        await mgr.acquire_lease("global_table", "node_0", scope=LeaseScope.CLUSTER_GLOBAL)


# ── TEST 9: MESSAGE DEDUPLICATOR IDEMPOTENCY ──────────────────────────────────

@pytest.mark.anyio
async def test_message_deduplicator_idempotency():
    dedup = DistributedMessageDeduplicator(window_size=100)
    msg_id = "msg_unique_123"

    is_dup, res = await dedup.record_and_get_cached(msg_id, result={"status": "OK"})
    assert is_dup is False
    assert res == {"status": "OK"}

    # Second arrival is detected as duplicate
    is_dup_2, res_2 = await dedup.record_and_get_cached(msg_id, result={"status": "DIFFERENT"})
    assert is_dup_2 is True
    assert res_2 == {"status": "OK"}  # Returns original cached result without re-execution


# ── TEST 10: SIMULATED NETWORK FAULT INJECTION (CHAOS) ────────────────────────

@pytest.mark.anyio
async def test_simulated_network_fault_injection_recovery():
    base_server = TcpTransport(node_id="chaos_server")
    base_client = TcpTransport(node_id="chaos_client")
    port = 19104

    try:
        await base_server.start_server("127.0.0.1", port)
        await base_client.connect("chaos_server", "127.0.0.1", port)

        # Wrap client in chaos transport: 10ms latency, clock skew 50ms
        chaos = SimulatedNetworkTransport(
            base_transport=base_client,
            latency_ms=10.0,
            loss_rate=0.0,
            duplication_rate=0.0,
            clock_skew_ms=50.0,
            seed=123,
        )

        env = DistributedEnvelope.create(
            source_node="chaos_client",
            destination_node="chaos_server",
            action=MessageAction.REQUEST,
            payload_type="chaos_test",
            payload={"ping": "pong"},
        )

        t0 = time.perf_counter()
        _ = await chaos.send_message("chaos_server", env)
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert elapsed >= 8.0  # Latency injection verified

        received, _ = await base_server.receive_message(timeout=5.0)
        assert received.payload == {"ping": "pong"}
    finally:
        await base_client.close()
        await base_server.close()


# ── TEST 11: CLUSTER CHECKPOINT & CROSS-NODE RECOVERY ─────────────────────────

def test_cluster_checkpoint_and_cross_node_recovery():
    cp = ClusterCheckpoint(
        checkpoint_id="chk_001",
        cluster_id="cluster_prod",
        generation=1,
        global_dag_version=10,
        completed_tasks=["t1", "t2", "t3"],
        failed_tasks=[],
        active_nodes=["node_alpha", "node_beta"],
        lease_generations={"res_file": 1},
        package_assignments={"pkg_01": "node_alpha"},
    )

    sha = cp.compute_sha256()
    assert len(sha) == 64
    d = cp.to_dict()
    assert d["checkpoint_id"] == "chk_001"
    assert "t1" in d["completed_tasks"]


# ── TEST 12: DISTRIBUTED CORRECTNESS ORACLE INVARIANTS ────────────────────────

def test_distributed_correctness_oracle_invariants():
    oracle = DistributedFederationReferenceModel()

    # Normal valid execution
    oracle.record_task_execution("t_01", "node_01")
    oracle.record_side_effect("se_01")
    oracle.record_lease_grant("res_db", "node_01")
    oracle.record_transition("t_01", TaskStatus.PENDING, TaskStatus.READY)
    oracle.record_transition("t_01", TaskStatus.READY, TaskStatus.RUNNING)
    oracle.record_transition("t_01", TaskStatus.RUNNING, TaskStatus.COMPLETED)
    oracle.record_primary_declaration("part_1", "node_01")

    res = oracle.verify_all_invariants()
    assert res["is_valid"] is True
    assert res["violations_count"] == 0
    assert res["duplicate_execution"] == 0
    assert res["duplicate_side_effect"] == 0
    assert res["ownership_conflict"] == 0
    assert res["invalid_transition"] == 0
    assert res["split_brain"] == 0

    # Simulate violations
    oracle.record_task_execution("t_01", "node_02")  # duplicate execution
    oracle.record_side_effect("se_01")              # duplicate side effect
    oracle.record_lease_grant("res_db", "node_03")  # ownership conflict

    v_res = oracle.verify_all_invariants()
    assert v_res["is_valid"] is False
    assert v_res["violations_count"] == 3
