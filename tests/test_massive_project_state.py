import time
import pytest
from concurrent.futures import ThreadPoolExecutor

from backend.agents.massive_project_state import (
    ContractRecord,
    DeterministicLRUCache,
    FileRecord,
    GraphEdge,
    ImpactScope,
    PartitionManager,
    PartitionType,
    ProjectMemoryBudget,
    ProjectStateFabric,
    StateShard,
    StateTier,
    SymbolRecord,
    TaskRecord,
)


@pytest.fixture
def state_fabric():
    fabric = ProjectStateFabric(db_path=":memory:")
    return fabric


def test_01_state_fabric_creation(state_fabric):
    """Test state fabric initialization with default shards and metrics."""
    overview = state_fabric.get_state_overview()
    assert overview["total_shards"] >= 5
    shard_names = [s["shard_id"] for s in overview["shards"]]
    assert "frontend" in shard_names
    assert "backend" in shard_names
    assert "workers" in shard_names
    assert "infra" in shard_names
    assert "shared" in shard_names


def test_02_partitioning(state_fabric):
    """Test partition assignment and detection for varied paths."""
    assert state_fabric.partitions.detect_shard_for_path("frontend/src/App.tsx") == "frontend"
    assert state_fabric.partitions.detect_shard_for_path("backend/api/users.py") == "backend"
    assert state_fabric.partitions.detect_shard_for_path("workers/celery_job.py") == "workers"
    assert state_fabric.partitions.detect_shard_for_path("scripts/deploy.sh") == "infra"
    assert state_fabric.partitions.detect_shard_for_path("contracts/openapi.json") == "shared"


def test_03_hot_warm_cold_state(state_fabric):
    """Test state tiering across HOT, WARM, and COLD."""
    shard = state_fabric.partitions.get_shard("backend")
    assert shard is not None

    # Promote to HOT
    state_fabric.partitions.activate_shard("backend", tier=StateTier.HOT)
    assert shard.tier == StateTier.HOT

    # Evict to COLD
    state_fabric.partitions.evict_shard("backend")
    assert shard.tier == StateTier.COLD


def test_04_lazy_loading(state_fabric):
    """Test on-demand lazy loading from cold storage into warm cache."""
    sym = SymbolRecord(
        symbol_id="sym_auth_login",
        name="login",
        kind="function",
        file_path="backend/auth.py",
        shard_id="backend",
        language="python",
        signature_hash="sig123",
        consumers=["sym_client_login"],
    )
    state_fabric.storage.save_symbol(sym)

    # Initial state: not in memory index
    state_fabric.indexes.symbols.clear()
    assert state_fabric.indexes.symbols.get_symbol("sym_auth_login") is None

    # Lazy load
    loaded = state_fabric.loader.load_symbol("sym_auth_login")
    assert loaded is not None
    assert loaded.name == "login"
    assert state_fabric.loader.cold_fetches >= 1


def test_05_cache_policy():
    """Test deterministic LRU eviction under memory and entry limits."""
    cache = DeterministicLRUCache(max_entries=3, max_bytes=100)
    cache.put("k1", "v1", size=10)
    cache.put("k2", "v2", size=10)
    cache.put("k3", "v3", size=10)

    # Access k1 so k2 becomes the LRU candidate
    assert cache.get("k1") == "v1"

    evicted = cache.put("k4", "v4", size=10)
    assert evicted == "k2"
    assert cache.get("k2") is None
    assert cache.get("k1") == "v1"


def test_06_invalidation(state_fabric):
    """Test targeted surgical invalidation when a file changes."""
    sym1 = SymbolRecord("s1", "fetchUser", "function", "frontend/api.ts", "frontend", "typescript", "sig1", consumers=["s2"])
    state_fabric.register_file("frontend/api.ts", "function fetchUser() {}", symbols=[sym1])

    assert state_fabric.indexes.symbols.get_symbol("s1") is not None

    # Invalidate file with new content
    report = state_fabric.invalidate_file("frontend/api.ts", "function fetchUser(id) { return id; }")
    assert report["file_path"] == "frontend/api.ts"
    assert "s1" in report["invalidated_symbols"]
    assert report["after_index_revision"] > report["before_index_revision"]


def test_07_incremental_indexing(state_fabric):
    """Test incremental update of shard metrics and revision bump without full rebuild."""
    shard = state_fabric.partitions.get_shard("backend")
    initial_rev = shard.last_indexed_revision

    sym = SymbolRecord("sym_svc", "execute", "function", "backend/svc.py", "backend", "python", "h1")
    state_fabric.register_file("backend/svc.py", "def execute(): pass", symbols=[sym])

    assert shard.last_indexed_revision > initial_rev
    assert shard.file_count >= 1


def test_08_reverse_indexes(state_fabric):
    """Test O(1) reverse index lookups for symbol -> consumers and contract -> consumers."""
    sym = SymbolRecord(
        symbol_id="sym_core_calc",
        name="calculate",
        kind="function",
        file_path="backend/math.py",
        shard_id="backend",
        language="python",
        signature_hash="h2",
        consumers=["sym_ui_view", "sym_worker_job"],
        contracts=["contract_billing_v1"],
    )
    state_fabric.indexes.symbols.add_symbol(sym)

    consumers = state_fabric.indexes.symbols.get_consumers("sym_core_calc")
    assert "sym_ui_view" in consumers
    assert "sym_worker_job" in consumers
    assert "contract_billing_v1" in state_fabric.indexes.symbols.get_contracts("sym_core_calc")


def test_09_targeted_subgraph(state_fabric):
    """Test extracting a targeted subgraph without loading the full repository graph."""
    sym_api = SymbolRecord("sym_api_checkout", "checkout", "endpoint", "backend/checkout.py", "backend", "python", "h3")
    sym_ui = SymbolRecord("sym_ui_btn", "CheckoutButton", "component", "frontend/Button.tsx", "frontend", "typescript", "h4")
    state_fabric.indexes.symbols.add_symbol(sym_api)
    state_fabric.indexes.symbols.add_symbol(sym_ui)

    # Register edge: UI button calls API
    state_fabric.register_edge("sym_ui_btn", "sym_api_checkout", edge_type="calls")

    subgraph = state_fabric.extract_targeted_subgraph(root_symbols=["sym_api_checkout"])
    assert "sym_api_checkout" in subgraph.nodes
    assert "sym_ui_btn" in subgraph.nodes
    assert len(subgraph.edges) >= 1
    assert subgraph.extraction_time_ms >= 0.0


def test_10_snapshot_creation(state_fabric):
    """Test creating an incremental point-in-time state snapshot."""
    snap = state_fabric.create_snapshot("Pre-refactor snapshot")
    assert snap.snapshot_id.startswith("snap_")
    assert len(snap.repository_state_hash) == 16
    assert len(snap.partition_hashes) >= 5


def test_11_snapshot_restore(state_fabric):
    """Test restoring repository state from snapshot."""
    snap = state_fabric.create_snapshot("Base state")
    backend_shard = state_fabric.partitions.get_shard("backend")
    orig_hash = backend_shard.state_hash

    # Mutate shard hash
    backend_shard.state_hash = "tampered_hash_00"

    # Restore snapshot
    restored = state_fabric.restore_snapshot(snap.snapshot_id)
    assert restored is not None
    assert state_fabric.partitions.get_shard("backend").state_hash == orig_hash


def test_12_memory_budget_enforcement(state_fabric):
    """Test that memory limits trigger deterministic eviction of cold/warm shards."""
    budget = ProjectMemoryBudget(max_hot_files=2, max_hot_symbols=5)
    fabric = ProjectStateFabric(budget=budget)

    # Register files exceeding budget
    for i in range(4):
        sym = SymbolRecord(f"s_m_{i}", f"func_{i}", "function", f"backend/f_{i}.py", "backend", "python", f"h_{i}")
        fabric.register_file(f"backend/f_{i}.py", f"content_{i}", symbols=[sym], loc=10)

    # Check that memory manager recorded eviction events
    assert fabric.memory.get_status()["eviction_count"] >= 1


def test_13_concurrent_reads(state_fabric):
    """Test thread-safe concurrent read queries."""
    sym = SymbolRecord("sym_conc_01", "readData", "function", "backend/read.py", "backend", "python", "sig_c")
    state_fabric.indexes.symbols.add_symbol(sym)

    queries = [("symbol", "sym_conc_01") for _ in range(10)]
    results = state_fabric.query_engine.execute_concurrent_queries(queries)
    assert len(results) == 10
    assert all(r is not None and r.name == "readData" for r in results)


def test_14_concurrent_writes(state_fabric):
    """Test write serialization without graph or index corruption."""
    def write_op(idx):
        sym = SymbolRecord(f"sym_w_{idx}", f"write_{idx}", "function", f"backend/w_{idx}.py", "backend", "python", f"sig_{idx}")
        state_fabric.register_file(f"backend/w_{idx}.py", f"def write_{idx}(): pass", symbols=[sym])

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write_op, range(8)))

    assert state_fabric.indexes.files.size() >= 8


def test_15_change_planning(state_fabric):
    """Test RepositoryChangePlanner producing a ChangePlan with blast radius scope."""
    sym_api = SymbolRecord("sym_api_orders", "getOrders", "endpoint", "backend/orders.py", "backend", "python", "h_ord")
    state_fabric.register_file("backend/orders.py", "def getOrders(): pass", symbols=[sym_api])

    plan = state_fabric.plan_repository_change(
        objective="Atualizar endpoint de encomendas",
        changed_files=["backend/orders.py"],
    )

    assert plan.plan_id.startswith("plan_")
    assert "backend/orders.py" in plan.changed_files
    assert plan.scope in (ImpactScope.LOCAL, ImpactScope.REGIONAL, ImpactScope.CROSS_SERVICE)
    assert len(plan.required_validation) >= 1


def test_16_cross_service_graph(state_fabric):
    """Test cross-service dependency tracing (Backend API -> Contract -> Frontend)."""
    contract = ContractRecord(
        contract_id="contract_user_api",
        name="UserAPIContract",
        version="2.0.0",
        shard_id="shared",
        endpoints=["/api/users"],
        consumers=["frontend"],
        providers=["backend"],
    )
    state_fabric.register_contract(contract)

    sym_be = SymbolRecord("sym_be_user", "getUser", "endpoint", "backend/user.py", "backend", "python", "h_be", contracts=["contract_user_api"])
    sym_fe = SymbolRecord("sym_fe_profile", "UserProfile", "component", "frontend/Profile.tsx", "frontend", "typescript", "h_fe", contracts=["contract_user_api"])
    state_fabric.register_file("backend/user.py", "code", symbols=[sym_be])
    state_fabric.register_file("frontend/Profile.tsx", "code", symbols=[sym_fe])

    state_fabric.register_edge("sym_be_user", "contract_user_api", edge_type="provides_contract")
    state_fabric.register_edge("sym_fe_profile", "contract_user_api", edge_type="consumes_contract")

    plan = state_fabric.plan_repository_change(
        objective="Modificar esquema de utilizador",
        changed_files=["backend/user.py"],
        changed_contracts=["contract_user_api"],
    )

    assert plan.scope in (ImpactScope.CROSS_SERVICE, ImpactScope.REPOSITORY_WIDE)
    assert "shared" in plan.affected_services or "frontend" in plan.affected_services


def test_17_stale_index_detection(state_fabric):
    """Test detecting stale indexed records against file updates."""
    sym = SymbolRecord("sym_v1", "v1Func", "function", "backend/v.py", "backend", "python", "h_v1")
    state_fabric.register_file("backend/v.py", "version 1", symbols=[sym])

    # Re-invalidate with new symbol
    sym2 = SymbolRecord("sym_v2", "v2Func", "function", "backend/v.py", "backend", "python", "h_v2")
    state_fabric.invalidate_file("backend/v.py", "version 2", new_symbols=[sym2])

    assert state_fabric.indexes.symbols.get_symbol("sym_v1") is None
    assert state_fabric.indexes.symbols.get_symbol("sym_v2") is not None


def test_18_state_tampering_security(state_fabric):
    """Test Security Sentinel blocking content hash tampering and path escapes."""
    # Path traversal rejection
    with pytest.raises(PermissionError):
        state_fabric.register_file("../outside.py", "malicious_code")

    # Content hash tampering
    tampered = state_fabric.security.verify_content_hash("real content", "wrong_hash_abc")
    assert tampered is False
    assert len(state_fabric.security.get_violations()) >= 1


def test_19_large_repository_scaling(state_fabric):
    """Test stability with multiple modular shards and indexed symbols."""
    for i in range(20):
        sym = SymbolRecord(f"sym_scale_{i}", f"scaleFunc_{i}", "function", f"shared/m_{i}.py", "shared", "python", f"sig_{i}")
        state_fabric.indexes.symbols.add_symbol(sym)

    assert state_fabric.indexes.symbols.size() >= 20
    summary = state_fabric.indexes.get_index_summary()
    assert summary["total_symbols"] >= 20


def test_20_mission_integration(state_fabric):
    """Test integrating ChangePlan into Phase 57 AutonomousMission format."""
    plan = state_fabric.plan_repository_change(
        objective="Integrar pipeline de tarefas da missão",
        changed_files=["frontend/src/App.tsx"],
    )

    # Mission-consumable representation
    mission_scope_data = {
        "plan_id": plan.plan_id,
        "scope": plan.scope.value,
        "affected_files": plan.changed_files,
        "predicted_risk": plan.predicted_risk,
        "required_validation": plan.required_validation,
    }
    assert mission_scope_data["scope"] in ("LOCAL", "REGIONAL", "CROSS_SERVICE", "REPOSITORY_WIDE")
    assert len(mission_scope_data["required_validation"]) >= 1


def test_21_predictive_impact_integration(state_fabric):
    """Test targeted subgraph feeding predictive impact precision."""
    sym_a = SymbolRecord("sym_pred_a", "calcTotal", "function", "backend/billing.py", "backend", "python", "sig_a")
    sym_b = SymbolRecord("sym_pred_b", "displayTotal", "component", "frontend/Total.tsx", "frontend", "typescript", "sig_b")
    state_fabric.indexes.symbols.add_symbol(sym_a)
    state_fabric.indexes.symbols.add_symbol(sym_b)
    state_fabric.register_edge("sym_pred_b", "sym_pred_a", edge_type="calls")

    subgraph = state_fabric.extract_targeted_subgraph(["sym_pred_a"])
    assert "sym_pred_b" in subgraph.nodes


def test_22_memory_integration(state_fabric):
    """Test experience memory recording hotspot zones."""
    state_fabric.memory.record_experience_hotspot(shard_id="backend", change_frequency=42, avg_blast_radius=6)
    hotspots = state_fabric.memory.get_learned_hotspots()
    assert len(hotspots) == 1
    assert hotspots[0]["shard_id"] == "backend"
    assert hotspots[0]["change_frequency"] == 42


def test_23_browser_integration(state_fabric):
    """Test browser scenario derivation in change plan when UI components are touched."""
    sym_ui = SymbolRecord("sym_ui_page", "DashboardPage", "component", "frontend/Dashboard.tsx", "frontend", "typescript", "h_dash")
    state_fabric.register_file("frontend/Dashboard.tsx", "export const DashboardPage = () => <div/>;", symbols=[sym_ui])

    plan = state_fabric.plan_repository_change(
        objective="Atualizar layout do Dashboard",
        changed_files=["frontend/Dashboard.tsx"],
    )
    assert len(plan.browser_scenarios) >= 1


def test_24_oom_protection():
    """Test that extreme data volume does not cause OOM and stays within bounded budget."""
    strict_budget = ProjectMemoryBudget(max_hot_files=5, max_hot_symbols=10, max_ram_bytes=1000)
    fabric = ProjectStateFabric(budget=strict_budget)

    # Push 50 files
    for i in range(50):
        fabric.register_file(f"backend/bulk_{i}.py", f"content_data_{i}", loc=5)

    status = fabric.memory.get_status()
    # Memory budget manager must actively record evictions
    assert status["eviction_count"] > 0
