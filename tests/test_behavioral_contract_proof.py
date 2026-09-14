"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Comprehensive 22-Scenario Automated Test Suite.
"""

import time
import pytest

from agents.behavioral_contract_proof.baseline import (
    BaselineImmutableError,
    BaselineIntegrityError,
    BehaviorBaselineStore,
    compute_baseline_hash,
)
from agents.behavioral_contract_proof.behavior_model import (
    BehavioralModelEngine,
    CANONICAL_STAGE_ORDER,
)
from agents.behavioral_contract_proof.bridge import BehavioralContractProofBridge
from agents.behavioral_contract_proof.cache import BehaviorProofCache
from agents.behavioral_contract_proof.comparator import BehaviorComparator
from agents.behavioral_contract_proof.counterexample import CounterexampleGenerator
from agents.behavioral_contract_proof.index import BehavioralIndex
from agents.behavioral_contract_proof.invariants import BehavioralInvariantEngine
from agents.behavioral_contract_proof.metrics import BehavioralProofTelemetry
from agents.behavioral_contract_proof.migration import (
    BehavioralMigrationController,
    FinishGateStatus,
)
from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    BehavioralInvariantType,
    BehavioralStage,
    BehavioralStageExecution,
    CompatibilityCategory,
    EquivalenceLevel,
    ExecutionGateDecision,
    LatencyClass,
    MigrationProof,
    ProofResult,
    RuntimeTrace,
)
from agents.behavioral_contract_proof.normalizer import RuntimeTraceNormalizer
from agents.behavioral_contract_proof.proof import MigrationProofEngine
from agents.behavioral_contract_proof.security import (
    BehavioralSecuritySentinel,
    SecurityAuthDowngradeError,
    SecurityBaselineTamperedError,
    SecuritySecretLeakageError,
    SecurityTraceTamperedError,
)
from agents.behavioral_contract_proof.trace import (
    RuntimeTraceCollector,
    compute_trace_hash,
)
from agents.behavioral_contract_proof.validator import (
    BehavioralValidationError,
    BehavioralValidator,
)


@pytest.fixture
def baseline_fixture() -> BehaviorBaseline:
    """Standard baseline for testing."""
    base = BehaviorBaseline(
        contract_id="getUserProfile",
        contract_version="1.0.0",
        consumer_id="frontend-dashboard",
        operation="GET /api/v1/users/{id}",
        input_shape={"user_id": "usr_123"},
        output_shape={"id": "usr_123", "name": "Alice", "role": "admin", "avatar": "https://img.com/a.png"},
        status_code=200,
        side_effects=[],
        events=[{"topic": "user.profile_accessed"}],
        economic_effects=[],
        authorization_state={"requires_auth": True, "roles": ["user", "admin"]},
        latency_class=LatencyClass.FAST,
        source="runtime_observation",
    )
    base.baseline_hash = compute_baseline_hash(base)
    return base


@pytest.fixture
def trace_collector() -> RuntimeTraceCollector:
    return RuntimeTraceCollector()


# 1. Identical behavior
def test_identical_behavior(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    trace = trace_collector.record_trace(
        mission_id="m_test_1",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=baseline_fixture.output_shape,
        status_code=200,
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_01",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.0.0",
        consumers=[baseline_fixture.consumer_id],
    )
    assert proof.result == ProofResult.PROVEN_COMPATIBLE
    assert proof.compatibility_category == CompatibilityCategory.BEHAVIORALLY_COMPATIBLE
    assert proof.equivalence_level == EquivalenceLevel.EXACT_EQUIVALENCE
    assert len(proof.counterexamples) == 0


# 2. Semantic equivalence
def test_semantic_equivalence(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    # Output with reordered keys and equivalent normalized types
    reordered_output = {
        "avatar": "https://img.com/a.png",
        "role": "admin",
        "id": "usr_123",
        "name": "Alice",
    }
    trace = trace_collector.record_trace(
        mission_id="m_test_2",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=reordered_output,
        status_code=200,
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_02",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.0.1",
        consumers=[baseline_fixture.consumer_id],
    )
    assert proof.result == ProofResult.PROVEN_COMPATIBLE
    assert proof.compatibility_category == CompatibilityCategory.BEHAVIORALLY_COMPATIBLE
    assert proof.equivalence_level in (EquivalenceLevel.EXACT_EQUIVALENCE, EquivalenceLevel.SEMANTIC_EQUIVALENCE)


# 3. Optional field addition
def test_optional_field_addition(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    extended_output = dict(baseline_fixture.output_shape)
    extended_output["created_at"] = "2026-09-13T20:00:00Z"
    extended_output["bio"] = "Autonomous Agent Lead"

    trace = trace_collector.record_trace(
        mission_id="m_test_3",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=extended_output,
        status_code=200,
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_03",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=[baseline_fixture.consumer_id],
        is_closed_exhaustive=False,
    )
    assert proof.result == ProofResult.PROVEN_COMPATIBLE
    assert proof.equivalence_level == EquivalenceLevel.ALLOWED_CHANGE
    assert len(proof.counterexamples) == 0


# 4. Field removal
def test_field_removal(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    shrunken_output = dict(baseline_fixture.output_shape)
    del shrunken_output["avatar"]  # Required field missing

    trace = trace_collector.record_trace(
        mission_id="m_test_4",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=shrunken_output,
        status_code=200,
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_04",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="2.0.0",
        consumers=[baseline_fixture.consumer_id],
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert proof.compatibility_category == CompatibilityCategory.BEHAVIORALLY_INCOMPATIBLE
    assert proof.equivalence_level == EquivalenceLevel.BREAKING_CHANGE
    assert len(proof.counterexamples) == 1
    assert "avatar" in proof.counterexamples[0].difference


# 5. Scalar-to-object change
def test_scalar_to_object_change(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    scalar_to_obj_output = dict(baseline_fixture.output_shape)
    scalar_to_obj_output["avatar"] = {"url": "https://img.com/a.png", "width": 64, "height": 64}

    trace = trace_collector.record_trace(
        mission_id="m_test_5",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=scalar_to_obj_output,
        status_code=200,
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_05",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="2.0.0",
        consumers=[baseline_fixture.consumer_id],
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert proof.equivalence_level == EquivalenceLevel.BREAKING_CHANGE
    assert len(proof.counterexamples) == 1
    assert "Scalar-to-object change" in proof.counterexamples[0].difference


# 6. Status code change
def test_status_code_change(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    trace = trace_collector.record_trace(
        mission_id="m_test_6",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=baseline_fixture.output_shape,
        status_code=201,  # 200 -> 201 unexpected
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_06",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=[baseline_fixture.consumer_id],
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert "Status code mismatch" in proof.counterexamples[0].difference


# 7. Event rename
def test_event_rename(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    renamed_events = [{"topic": "user.modified"}]  # was user.profile_accessed
    trace = trace_collector.record_trace(
        mission_id="m_test_7",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=baseline_fixture.output_shape,
        status_code=200,
        events=renamed_events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_07",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=[baseline_fixture.consumer_id],
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert any("Event removed or renamed" in c.difference or "EVENT_SEMANTICS_PRESERVED" in c.difference for c in proof.counterexamples)


# 8. Event addition
def test_event_addition(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    extra_events = list(baseline_fixture.events)
    extra_events.append({"topic": "analytics.ping"})
    trace = trace_collector.record_trace(
        mission_id="m_test_8",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=baseline_fixture.output_shape,
        status_code=200,
        events=extra_events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_08",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=[baseline_fixture.consumer_id],
        is_closed_exhaustive=False,
    )
    assert proof.result == ProofResult.PROVEN_COMPATIBLE
    assert proof.equivalence_level in (EquivalenceLevel.ALLOWED_CHANGE, EquivalenceLevel.SEMANTIC_EQUIVALENCE)


# 9. Closed exhaustive variant
def test_closed_exhaustive_variant(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    extended_output = dict(baseline_fixture.output_shape)
    extended_output["extra_key"] = "unexpected_for_closed_consumer"

    trace = trace_collector.record_trace(
        mission_id="m_test_9",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=extended_output,
        status_code=200,
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_09",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=[baseline_fixture.consumer_id],
        is_closed_exhaustive=True,  # Closed exhaustive consumer!
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert "CONSUMER_EXPECTATION_PRESERVED" in proof.counterexamples[0].difference


# 10. Open fallback variant
def test_open_fallback_variant(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    extended_output = dict(baseline_fixture.output_shape)
    extended_output["extra_key"] = "acceptable_for_open_consumer"

    trace = trace_collector.record_trace(
        mission_id="m_test_10",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=extended_output,
        status_code=200,
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_10",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=[baseline_fixture.consumer_id],
        is_closed_exhaustive=False,  # Open fallback consumer!
    )
    assert proof.result == ProofResult.PROVEN_COMPATIBLE


# 11. Dynamic consumer (Phase 49 resolved)
def test_dynamic_consumer(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    bridge = BehavioralContractProofBridge()
    consumer_res = {
        "consumer_id": "resolved-dispatch-handler",
        "evidence_state": "GENERATED",
        "resolution_status": "RESOLVED",
        "pattern_matching": "OPEN_WITH_FALLBACK",
        "resolution_id": "res_dyn_01",
    }
    trace = trace_collector.record_trace(
        mission_id="m_dyn_11",
        consumer_id=consumer_res["consumer_id"],
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=baseline_fixture.output_shape,
        status_code=200,
        events=baseline_fixture.events,
        authorization_state=baseline_fixture.authorization_state,
    )
    proof = bridge.evaluate_dynamic_consumer_proof(
        consumer_resolution=consumer_res,
        baseline=baseline_fixture,
        observed_trace=trace,
        migration_id="mig_dyn_11",
        before_version="1.0.0",
        after_version="1.0.0",
    )
    assert proof.result == ProofResult.PROVEN_COMPATIBLE
    assert proof.compatibility_category == CompatibilityCategory.BEHAVIORALLY_COMPATIBLE


# 12. Unknown dynamic consumer (Phase 49 UNCERTAIN)
def test_unknown_consumer(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    bridge = BehavioralContractProofBridge()
    consumer_res = {
        "consumer_id": "unbounded-getattr-invoker",
        "evidence_state": "UNCERTAIN",
        "resolution_status": "UNCERTAIN",
        "pattern_matching": "CLOSED_EXHAUSTIVE",
        "resolution_id": "res_unc_02",
    }
    trace = trace_collector.record_trace(
        mission_id="m_dyn_12",
        consumer_id=consumer_res["consumer_id"],
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=baseline_fixture.output_shape,
        status_code=200,
    )
    proof = bridge.evaluate_dynamic_consumer_proof(
        consumer_resolution=consumer_res,
        baseline=baseline_fixture,
        observed_trace=trace,
        migration_id="mig_dyn_12",
        before_version="1.0.0",
        after_version="1.0.0",
    )
    # MUST remain INSUFFICIENT_EVIDENCE (no silent guessing!)
    assert proof.result == ProofResult.INSUFFICIENT_EVIDENCE
    assert proof.compatibility_category == CompatibilityCategory.BEHAVIOR_UNKNOWN
    assert proof.confidence == 0.0


# 13. Auth behavior change
def test_auth_behavior_change(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    # Downgrade auth: required -> public
    downgraded_auth = {"requires_auth": False, "roles": []}
    trace = trace_collector.record_trace(
        mission_id="m_auth_13",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=baseline_fixture.output_shape,
        status_code=200,
        authorization_state=downgraded_auth,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_auth_13",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=[baseline_fixture.consumer_id],
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert any("AUTHORIZATION_PRESERVED" in c.difference or "Authorization requirement changed" in c.difference for c in proof.counterexamples)


# 14. Economic behavior change
def test_economic_behavior_change(trace_collector: RuntimeTraceCollector):
    econ_baseline = BehaviorBaseline(
        contract_id="settlePayment",
        contract_version="1.0.0",
        consumer_id="economic-gateway",
        operation="POST /api/v1/economic/settle",
        input_shape={"tx": "123", "amount": 100.0},
        output_shape={"settled": True},
        status_code=200,
        economic_effects=[{"amount": 100.0, "currency": "USD", "ledger_action": "COMMIT"}],
    )
    econ_baseline.baseline_hash = compute_baseline_hash(econ_baseline)

    # Divergent currency and amount
    trace = trace_collector.record_trace(
        mission_id="m_econ_14",
        consumer_id="economic-gateway",
        contract_id="settlePayment",
        operation="POST /api/v1/economic/settle",
        input_payload={"tx": "123", "amount": 100.0},
        output_payload={"settled": True},
        status_code=200,
        economic_effects=[{"amount": 95.0, "currency": "EUR", "ledger_action": "COMMIT"}],
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_econ_14",
        baseline=econ_baseline,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=["economic-gateway"],
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert any("ECONOMIC_VALUE_PRESERVED" in c.difference or "Currency mismatch" in c.difference for c in proof.counterexamples)


# 15. Side effect ordering
def test_side_effect_ordering(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    base = BehaviorBaseline(
        contract_id="processTask",
        contract_version="1.0.0",
        consumer_id="worker",
        operation="POST /tasks",
        input_shape={"id": "1"},
        output_shape={"ok": True},
        status_code=200,
        side_effects=[{"type": "AUDIT_LOG"}, {"type": "EMAIL_DISPATCH"}],
    )
    base.baseline_hash = compute_baseline_hash(base)

    # Reordered side effects
    trace = trace_collector.record_trace(
        mission_id="m_se_15",
        consumer_id="worker",
        contract_id="processTask",
        operation="POST /tasks",
        input_payload={"id": "1"},
        output_payload={"ok": True},
        status_code=200,
        side_effects=[{"type": "EMAIL_DISPATCH"}, {"type": "AUDIT_LOG"}],
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_se_15",
        baseline=base,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.1.0",
        consumers=["worker"],
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert any("SIDE_EFFECT_ORDER_PRESERVED" in c.difference or "Side effect" in c.difference for c in proof.counterexamples)


# 16. Counterexample generation
def test_counterexample_generation(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    trace = trace_collector.record_trace(
        mission_id="m_cex_16",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload={"id": "usr_123"},  # Name, role, avatar missing
        status_code=200,
    )
    cex = CounterexampleGenerator.generate(
        baseline=baseline_fixture,
        observed=trace,
        difference_summary="Missing required fields: name, role, avatar",
    )
    assert cex.counterexample_id.startswith("cex_")
    assert cex.consumer_id == baseline_fixture.consumer_id
    assert cex.expected_behavior["status_code"] == 200
    assert "name" in cex.difference


# 17. Baseline tampering
def test_baseline_tampering(baseline_fixture: BehaviorBaseline):
    store = BehaviorBaselineStore()
    store.register_baseline(baseline_fixture)

    # Tamper with content while keeping old hash
    tampered = BehaviorBaseline(
        contract_id=baseline_fixture.contract_id,
        contract_version=baseline_fixture.contract_version,
        consumer_id=baseline_fixture.consumer_id,
        operation=baseline_fixture.operation,
        input_shape={"tampered": True},
        output_shape={"tampered": True},
        status_code=500,
        baseline_hash=baseline_fixture.baseline_hash,  # Forged hash!
    )
    with pytest.raises((BaselineIntegrityError, SecurityBaselineTamperedError)):
        BehavioralSecuritySentinel.validate_baseline_integrity(tampered)


# 18. Trace tampering
def test_trace_tampering(trace_collector: RuntimeTraceCollector):
    trace = trace_collector.record_trace(
        mission_id="m_tamper_18",
        consumer_id="c_18",
        contract_id="cnt_18",
        operation="GET /data",
        input_payload={"q": 1},
        output_payload={"res": 1},
        status_code=200,
    )
    # Alter payload without updating trace_hash
    trace.output_payload = {"res": 9999}
    with pytest.raises(SecurityTraceTamperedError):
        BehavioralSecuritySentinel.validate_trace_integrity(trace)


# 19. Secret redaction
def test_secret_redaction():
    raw_payload = {
        "user_id": "usr_10",
        "auth_token": "secret_token_12345",
        "api_key": "sk-live-abcdef123456",
        "password": "SuperSecretPassword!",
        "profile": {
            "token": "nested_secret_token",
            "session_id": "sess_volatile_999",
            "created_at": "2026-09-13T21:00:00Z",
        },
    }
    normalized = RuntimeTraceNormalizer.normalize_payload(raw_payload)
    assert normalized["auth_token"] == "<REDACTED_SECRET>"
    assert normalized["api_key"] == "<REDACTED_SECRET>"
    assert normalized["password"] == "<REDACTED_SECRET>"
    assert normalized["profile"]["token"] == "<REDACTED_SECRET>"
    assert normalized["profile"]["session_id"] == "<CANONICAL_ID>"
    assert normalized["profile"]["created_at"] == "<CANONICAL_TIMESTAMP>"
    # Sentinel check should pass on normalized payload
    BehavioralSecuritySentinel.check_secret_leakage(normalized)


# 20. Rollback after proof failure
def test_rollback_after_proof_failure(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    ctrl = BehavioralMigrationController()
    broken_output = {"error": "Internal Error"}
    trace = trace_collector.record_trace(
        mission_id="m_rb_20",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=broken_output,
        status_code=500,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_rb_20",
        baseline=baseline_fixture,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="2.0.0",
        consumers=[baseline_fixture.consumer_id],
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE

    rollback = ctrl.execute_rollback(
        proof=proof,
        contract_id=baseline_fixture.contract_id,
        revert_to_version="1.0.0",
        policy_permits=True,
    )
    assert rollback is not None
    assert rollback.reverted_to_version == "1.0.0"
    assert len(ctrl.list_rollbacks()) == 1


# 21. Insufficient evidence
def test_insufficient_evidence():
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_insuff_21",
        baseline=None,  # Missing baseline
        observed_trace=None,
        before_version="1.0.0",
        after_version="2.0.0",
        consumers=["consumer-x"],
        has_sufficient_evidence=False,
    )
    assert proof.result == ProofResult.INSUFFICIENT_EVIDENCE
    assert proof.confidence == 0.0
    assert proof.compatibility_category == CompatibilityCategory.BEHAVIOR_UNKNOWN


# 22. False positive prevention
def test_false_positive_prevention(baseline_fixture: BehaviorBaseline, trace_collector: RuntimeTraceCollector):
    # Output has new volatile timestamps and IDs that are normalized away
    v2_output = dict(baseline_fixture.output_shape)
    v2_output["timestamp"] = time.time()
    v2_output["request_id"] = "req_random_uuid_999"

    base_with_volatile = dict(baseline_fixture.output_shape)
    base_with_volatile["timestamp"] = time.time() - 500
    base_with_volatile["request_id"] = "req_random_uuid_111"

    base = BehaviorBaseline(
        contract_id=baseline_fixture.contract_id,
        contract_version=baseline_fixture.contract_version,
        consumer_id=baseline_fixture.consumer_id,
        operation=baseline_fixture.operation,
        input_shape=baseline_fixture.input_shape,
        output_shape=base_with_volatile,
        status_code=200,
    )
    base.baseline_hash = compute_baseline_hash(base)

    trace = trace_collector.record_trace(
        mission_id="m_fp_22",
        consumer_id=baseline_fixture.consumer_id,
        contract_id=baseline_fixture.contract_id,
        operation=baseline_fixture.operation,
        input_payload=baseline_fixture.input_shape,
        output_payload=v2_output,
        status_code=200,
    )
    proof = MigrationProofEngine.prove_migration(
        migration_id="mig_fp_22",
        baseline=base,
        observed_trace=trace,
        before_version="1.0.0",
        after_version="1.0.1",
        consumers=[baseline_fixture.consumer_id],
    )
    # The volatile fields must normalize to canonical placeholders and not trigger false positive rejection
    assert proof.result == ProofResult.PROVEN_COMPATIBLE
